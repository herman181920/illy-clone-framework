#!/usr/bin/env python3
"""
Import cookies from a local Chromium-based browser into a Playwright-compatible JSON file.

Supports macOS + Linux. Decrypts v10 / v11 encrypted values using the browser's
AES key (macOS Keychain / Linux libsecret).

Algorithm (per Chromium source + gstack's cookie-import-browser.ts):
  1. Open the cookie SQLite DB from the browser profile dir
  2. Derive an AES-128 key:
     - macOS v10: PBKDF2(keychain_password, salt="saltysalt", iter=1003, keylen=16, SHA1)
     - Linux v10: PBKDF2("peanuts",          salt="saltysalt", iter=1,    keylen=16, SHA1)
     - Linux v11: PBKDF2(libsecret_password, salt="saltysalt", iter=1,    keylen=16, SHA1)
  3. For each row with encrypted_value starting with b"v10" or b"v11":
     - ciphertext = encrypted_value[3:]
     - IV = b" " * 16 (16 spaces / 0x20)
     - AES-128-CBC decrypt
     - Remove PKCS7 padding
     - Skip first 32 bytes (Chromium metadata prefix, present on modern versions)
     - Remaining bytes = UTF-8 cookie value
  4. Chromium epoch -> Unix: (chrome_us - 11644473600_000_000) / 1_000_000

Usage:
  python3 import_browser_cookies.py \\
      --browser chrome \\
      --domain example.com \\
      --out cookies.json

  # Multiple domains and profiles
  python3 import_browser_cookies.py --browser chrome --profile "Default" \\
      --domain example.com --domain auth-provider.example \\
      --out cookies.json

  # List detected browsers + profiles without extracting
  python3 import_browser_cookies.py --list
"""

import argparse
import base64
import json
import os
import platform
import sqlite3
import struct
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from cryptography.hazmat.primitives import hashes, padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

CHROME_EPOCH_US = 11644473600_000_000  # microseconds between 1601-01-01 and 1970-01-01
AES_KEY_LEN = 16
AES_SALT = b"saltysalt"
AES_IV = b" " * 16


@dataclass
class BrowserSpec:
    name: str
    mac_subdir: str  # under ~/Library/Application Support/
    linux_subdir: str  # under ~/.config/
    keychain_service: str
    aliases: tuple[str, ...]


BROWSERS: list[BrowserSpec] = [
    BrowserSpec(
        name="chrome",
        mac_subdir="Google/Chrome",
        linux_subdir="google-chrome",
        keychain_service="Chrome Safe Storage",
        aliases=("chrome", "google-chrome"),
    ),
    BrowserSpec(
        name="brave",
        mac_subdir="BraveSoftware/Brave-Browser",
        linux_subdir="BraveSoftware/Brave-Browser",
        keychain_service="Brave Safe Storage",
        aliases=("brave", "brave-browser"),
    ),
    BrowserSpec(
        name="edge",
        mac_subdir="Microsoft Edge",
        linux_subdir="microsoft-edge",
        keychain_service="Microsoft Edge Safe Storage",
        aliases=("edge", "microsoft-edge", "msedge"),
    ),
    BrowserSpec(
        name="arc",
        mac_subdir="Arc/User Data",
        linux_subdir="",
        keychain_service="Arc Safe Storage",
        aliases=("arc",),
    ),
    BrowserSpec(
        name="opera",
        mac_subdir="com.operasoftware.Opera",
        linux_subdir="opera",
        keychain_service="Opera Safe Storage",
        aliases=("opera",),
    ),
    BrowserSpec(
        name="chromium",
        mac_subdir="Chromium",
        linux_subdir="chromium",
        keychain_service="Chromium Safe Storage",
        aliases=("chromium",),
    ),
    BrowserSpec(
        name="comet",
        mac_subdir="Perplexity/Comet",
        linux_subdir="Perplexity/Comet",
        keychain_service="Comet Safe Storage",
        aliases=("comet",),
    ),
]


def resolve_browser(alias: str) -> BrowserSpec:
    alias = alias.lower().strip()
    for b in BROWSERS:
        if alias in b.aliases:
            return b
    raise SystemExit(
        f"Unknown browser {alias!r}. Known: {', '.join(b.name for b in BROWSERS)}"
    )


def profile_root(spec: BrowserSpec) -> Path:
    system = platform.system()
    if system == "Darwin":
        return Path.home() / "Library/Application Support" / spec.mac_subdir
    if system == "Linux":
        if not spec.linux_subdir:
            raise SystemExit(f"{spec.name} not supported on Linux")
        return Path.home() / ".config" / spec.linux_subdir
    raise SystemExit(f"Unsupported OS: {system}")


def list_profiles(spec: BrowserSpec) -> list[tuple[str, str]]:
    """Return [(profile_dir_name, display_name), ...]"""
    root = profile_root(spec)
    if not root.exists():
        return []
    result: list[tuple[str, str]] = []
    for entry in sorted(root.iterdir()):
        if not entry.is_dir():
            continue
        name = entry.name
        if name in ("System Profile", "Guest Profile"):
            continue
        cookies_path = entry / "Cookies"
        network_cookies = entry / "Network" / "Cookies"
        if not (cookies_path.exists() or network_cookies.exists()):
            continue
        display = name
        prefs = entry / "Preferences"
        if prefs.exists():
            try:
                data = json.loads(prefs.read_text("utf-8", errors="ignore"))
                profile = data.get("profile") or {}
                if isinstance(profile.get("name"), str):
                    display = profile["name"]
            except Exception:
                pass
        result.append((name, display))
    return result


def cookies_db(spec: BrowserSpec, profile: str) -> Path:
    root = profile_root(spec)
    network = root / profile / "Network" / "Cookies"
    if network.exists():
        return network
    fallback = root / profile / "Cookies"
    if fallback.exists():
        return fallback
    raise SystemExit(f"Cookies DB not found under {root / profile}")


def mac_keychain_password(service: str) -> bytes:
    # `-s SERVICE -w` returns just the password.
    try:
        out = subprocess.check_output(
            ["security", "find-generic-password", "-s", service, "-w"],
            stderr=subprocess.PIPE,
        )
    except subprocess.CalledProcessError as e:
        raise SystemExit(
            f"Could not read {service!r} from Keychain. "
            f"If a Keychain dialog appeared, click Always Allow and retry. "
            f"Details: {e.stderr.decode('utf-8', 'ignore').strip()}"
        )
    return out.strip()


def derive_key(password: bytes, iterations: int) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA1(),
        length=AES_KEY_LEN,
        salt=AES_SALT,
        iterations=iterations,
    )
    return kdf.derive(password)


def derive_keys_for_platform(spec: BrowserSpec) -> dict[str, bytes]:
    system = platform.system()
    if system == "Darwin":
        password = mac_keychain_password(spec.keychain_service)
        return {"v10": derive_key(password, 1003)}
    if system == "Linux":
        keys: dict[str, bytes] = {"v10": derive_key(b"peanuts", 1)}
        try:
            v11_pw = subprocess.check_output(
                [
                    "secret-tool",
                    "lookup",
                    "application",
                    spec.name,
                ]
            ).strip()
            if v11_pw:
                keys["v11"] = derive_key(v11_pw, 1)
        except (FileNotFoundError, subprocess.CalledProcessError):
            pass
        return keys
    raise SystemExit(f"Unsupported OS: {system}")


def decrypt_value(encrypted: bytes, keys: dict[str, bytes]) -> str | None:
    if not encrypted:
        return ""
    prefix = encrypted[:3].decode("ascii", "ignore")
    if prefix not in ("v10", "v11"):
        try:
            return encrypted.decode("utf-8")
        except UnicodeDecodeError:
            return None
    key = keys.get(prefix)
    if not key:
        return None
    ciphertext = encrypted[3:]
    if len(ciphertext) % 16 != 0:
        return None
    cipher = Cipher(algorithms.AES(key), modes.CBC(AES_IV))
    decryptor = cipher.decryptor()
    try:
        decrypted = decryptor.update(ciphertext) + decryptor.finalize()
        unpadder = padding.PKCS7(128).unpadder()
        plaintext = unpadder.update(decrypted) + unpadder.finalize()
    except Exception:
        return None
    # Modern Chromium prefixes the plaintext with 32 bytes of metadata
    # (SHA256 integrity hash) before the actual cookie value.
    if len(plaintext) >= 32:
        value = plaintext[32:]
    else:
        value = plaintext
    try:
        return value.decode("utf-8")
    except UnicodeDecodeError:
        # Older Chromium versions don't have the 32-byte prefix
        try:
            return plaintext.decode("utf-8")
        except UnicodeDecodeError:
            return None


def chrome_us_to_unix_sec(chrome_us: int) -> float:
    if chrome_us <= 0:
        return -1.0  # session cookie
    return (chrome_us - CHROME_EPOCH_US) / 1_000_000.0


def samesite(value: int | None) -> str:
    mapping = {0: "None", 1: "Lax", 2: "Strict"}
    return mapping.get(value or 0, "Lax")


def domain_matches(row_host: str, wanted: Iterable[str]) -> bool:
    wanted = list(wanted)
    if not wanted:
        return True
    host = row_host.lstrip(".").lower()
    for d in wanted:
        d = d.lstrip(".").lower()
        if host == d or host.endswith("." + d):
            return True
    return False


def extract(
    spec: BrowserSpec,
    profile: str,
    domains: list[str],
) -> tuple[list[dict], dict[str, int], int]:
    src = cookies_db(spec, profile)
    keys = derive_keys_for_platform(spec)

    # Copy DB because Chromium may have an active connection
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp) / "cookies.sqlite"
        tmp_path.write_bytes(src.read_bytes())

        conn = sqlite3.connect(str(tmp_path))
        try:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT host_key, name, value, encrypted_value, path,
                       expires_utc, is_secure, is_httponly, samesite
                  FROM cookies
                """
            ).fetchall()
        finally:
            conn.close()

    cookies: list[dict] = []
    domain_counts: dict[str, int] = {}
    failed = 0

    for row in rows:
        host = row["host_key"]
        if not domain_matches(host, domains):
            continue
        encrypted = row["encrypted_value"] or b""
        plain_value = row["value"] or ""
        if encrypted:
            value = decrypt_value(encrypted, keys)
            if value is None:
                failed += 1
                continue
        else:
            value = plain_value

        cookie = {
            "name": row["name"],
            "value": value,
            "domain": host,
            "path": row["path"] or "/",
            "expires": chrome_us_to_unix_sec(row["expires_utc"] or 0),
            "secure": bool(row["is_secure"]),
            "httpOnly": bool(row["is_httponly"]),
            "sameSite": samesite(row["samesite"]),
        }
        cookies.append(cookie)
        domain_counts[host] = domain_counts.get(host, 0) + 1

    return cookies, domain_counts, failed


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract browser cookies as Playwright JSON")
    parser.add_argument("--browser", default="chrome", help="chrome, brave, edge, arc, opera, chromium, comet")
    parser.add_argument("--profile", default="Default", help="Profile dir name (default: Default)")
    parser.add_argument("--domain", action="append", default=[], help="Filter by domain (repeatable). Omit for all.")
    parser.add_argument("--out", type=Path, help="Write JSON to this path. Omit to print to stdout.")
    parser.add_argument("--list", action="store_true", help="List detected profiles and exit")
    args = parser.parse_args()

    spec = resolve_browser(args.browser)

    if args.list:
        profiles = list_profiles(spec)
        if not profiles:
            print(f"No profiles found for {spec.name}. Checked {profile_root(spec)}", file=sys.stderr)
            return 1
        print(f"{spec.name} profiles:")
        for d, display in profiles:
            print(f"  {d}  -  {display}")
        return 0

    cookies, domain_counts, failed = extract(spec, args.profile, args.domain)

    output = json.dumps(cookies, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(output)
        print(
            f"Wrote {len(cookies)} cookies to {args.out}  "
            f"({failed} failed decryption, {len(domain_counts)} domains)",
            file=sys.stderr,
        )
        for host, count in sorted(domain_counts.items(), key=lambda p: (-p[1], p[0])):
            print(f"  {count:4d}  {host}", file=sys.stderr)
    else:
        print(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
