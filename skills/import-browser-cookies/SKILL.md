---
name: import-browser-cookies
description: This skill should be used when the user asks to "import cookies", "log into a site using my browser", "get cookies from Chrome", "authenticate Playwright with my session", or when the clone/audit/manual-qa pipeline needs an authenticated session on a target site. Extracts decrypted cookies from a local Chromium-based browser (Chrome, Brave, Edge, Arc, Opera, Chromium, Comet) and saves them as a Playwright-compatible JSON file. Loads them into the current Playwright MCP session via context.addCookies. Macos + Linux supported.
version: 0.1.0
---

# Import browser cookies for Playwright

Extract logged-in cookies from a real Chromium-based browser and drop them into the Playwright session so the agent can drive authenticated surfaces (editor, dashboard, settings, paywalled features).

Without this, the clone pipeline is limited to public marketing pages. With it, every flow the user can reach in their real browser, the agent can reach.

## Script location

```
scripts/import_browser_cookies.py
```

Uses `cryptography` (Python 3.11+). No third-party service required; decryption is local via Keychain (macOS) or libsecret (Linux).

## Supported browsers

| Browser | macOS | Linux | Keychain service |
|---|---|---|---|
| Chrome | yes | yes | Chrome Safe Storage |
| Brave | yes | yes | Brave Safe Storage |
| Edge | yes | yes | Microsoft Edge Safe Storage |
| Arc | yes | - | Arc Safe Storage |
| Opera | yes | yes | Opera Safe Storage |
| Chromium | yes | yes | Chromium Safe Storage |
| Comet (Perplexity) | yes | yes | Comet Safe Storage |

## Workflow

### Step 1: Detect the right profile

Users often have several Chrome profiles (work / personal / client). The session cookies are stored per-profile. Always list profiles first:

```bash
python3 scripts/import_browser_cookies.py --browser chrome --list
```

Output shape:
```
chrome profiles:
  Default      -  Your Chrome       (user@example.com)
  Profile 1    -  Work              (work@example.com)
  Profile 6    -  Side              (side@example.com)
```

Ask the user which profile has the logged-in session (sometimes the Google identity in the profile differs from the site account — e.g., user is signed into Gmail as one address but signed into the target site as another).

### Step 2: Extract cookies

```bash
python3 scripts/import_browser_cookies.py \
  --browser chrome --profile "Default" \
  --domain example.com \
  --out clones/example.com/cookies.json
```

- `--domain` can be repeated. Suffix matching: `--domain example.com` picks up `.example.com`, `app.example.com`, `auth.example.com`, etc.
- Omit `--domain` entirely to export the full cookie jar (rarely needed).
- First run on macOS triggers a Keychain password dialog — user must click **Always Allow**. Subsequent runs are silent for that service.

Output written to the JSON file and a summary printed to stderr: `Wrote N cookies ... (M failed decryption, D domains)`.

### Step 3: Load into Playwright MCP

Load a JS file into the session via `mcp__plugin_playwright_playwright__browser_run_code`. The script must live under `~/.playwright-mcp/` (MCP's allowed root).

Build the loader:

```bash
# Build a tight single-line JSON for JS inlining
python3 -c "
import json
cookies = json.load(open('clones/example.com/cookies.json'))
print(json.dumps(cookies))
" > ~/.playwright-mcp/cookies_compact.json

# Wrap in a Playwright callback that clears + loads
python3 -c "
import json
with open('~/.playwright-mcp/cookies_compact.json') as f:
    payload = f.read().strip()
script = '''async (page) => {
  const context = page.context();
  await context.clearCookies();
  const cookies = JSON.parse(%s);
  await context.addCookies(cookies);
  return { added: cookies.length };
}''' % json.dumps(payload)
open('~/.playwright-mcp/add_cookies.js','w').write(script)
"
```

Then call:
```
mcp__plugin_playwright_playwright__browser_run_code
  filename: ~/.playwright-mcp/add_cookies.js
```

The callback returns `{added: N}` on success.

### Step 4: Verify auth

Navigate to an authenticated URL. If it redirects to the login page, cookies are insufficient. Common causes:

1. **Wrong profile** — user signs into target site from a non-default Chrome profile
2. **Target site uses NextAuth on a subdomain you haven't covered** — e.g., `app.example.com` needs `__Secure-next-auth.session-token` on that exact domain. Check the Chrome DB directly:
   ```bash
   python3 -c "
   import sqlite3, tempfile
   from pathlib import Path
   src = Path.home() / 'Library/Application Support/Google/Chrome/Default/Cookies'
   with tempfile.NamedTemporaryFile(suffix='.sqlite', delete=False) as tmp:
       tmp.write(src.read_bytes()); tmp_path = tmp.name
   conn = sqlite3.connect(tmp_path)
   rows = conn.execute('SELECT host_key, name FROM cookies WHERE host_key LIKE \"%TARGET%\" ORDER BY host_key').fetchall()
   for r in rows: print(r)
   "
   ```
3. **Short-TTL token** — target uses JWT access tokens (5-15 min expiry) with long-lived refresh tokens. You may need to refresh the cookie set periodically or find the refresh endpoint.
4. **User never logged into that subdomain** — e.g., they use the iOS app but not the web app. Need them to log in at the specific URL once.

### Step 5: Rotate after use

Token cookies in this conversation's context are sensitive. After the audit is complete:
- Tell the user to sign out + sign back in to rotate tokens
- Delete the cookies JSON from disk
- Clear the Playwright session: `await context.clearCookies()`

## Algorithm reference

Ported from gstack's `cookie-import-browser.ts`. Pipeline:

1. **Locate DB** — `~/Library/Application Support/<browser>/<profile>/Cookies` (macOS, old) or `.../<profile>/Network/Cookies` (macOS, modern Chromium 96+).
2. **Derive AES key**:
   - macOS v10: PBKDF2(keychain_password, salt=`saltysalt`, iter=1003, keylen=16, SHA1)
   - Linux v10: PBKDF2(`peanuts`, salt=`saltysalt`, iter=1, keylen=16, SHA1)
   - Linux v11: PBKDF2(libsecret_password, salt=`saltysalt`, iter=1, keylen=16, SHA1)
3. **Decrypt each row** where `encrypted_value` starts with `b"v10"` or `b"v11"`:
   - ciphertext = `encrypted_value[3:]`
   - IV = `b" " * 16` (16 ASCII spaces / 0x20)
   - AES-128-CBC decrypt, remove PKCS7 padding
   - Skip first 32 bytes (SHA-256 integrity hash prefix, present on modern Chromium)
   - Remaining = UTF-8 cookie value
4. **Time conversion** — Chromium uses microseconds since 1601-01-01. Unix seconds = `(chrome_us - 11644473600_000_000) / 1_000_000`.
5. **SameSite mapping** — DB values 0→"None", 1→"Lax", 2→"Strict" (fallback Lax).

## Keychain command that works vs doesn't

```bash
# WORKS — service match + password-only output
security find-generic-password -s "Chrome Safe Storage" -w

# FAILS with "item not found" — the -a flag treats the arg as account name, not service
security find-generic-password -wa "Chrome Safe Storage"
```

## Security notes

- Cookie values decrypt locally; nothing leaves the machine.
- The Playwright session's context holds cookies until browser close / clearCookies.
- Tokens may show up in console output of `browser_run_code` — MCP tool results print the full JS body back. Minimize inline-cookie tool calls; prefer file-based loaders.
- Never commit the cookies JSON to git. Add to `.gitignore`: `*cookies.json`, `*-ref/`, `.*-ref/`.

## Common pitfalls

1. **Wrong Chrome profile** — always `--list` first.
2. **Keychain denies read** — user must click Allow / Always Allow in the popup. If they click Deny, they need to revoke: Keychain Access.app → login → search "Chrome Safe Storage" → right-click → Access Control → remove your terminal.
3. **DB locked** — Chrome holds an open SQLite handle. The script copies the DB before reading, so this is handled automatically.
4. **Stale cookies after refresh** — if the user logs out and back in, the cookie JSON needs re-extraction. Rerun the script.
5. **Subdomain mismatch** — logging into `site.com` does NOT give you cookies for `app.site.com` unless the cookie is set on the parent domain with `.site.com`.

## Integration with framework skills

- **`/clone`** — after discovery (Step 2), if auth-required pages detected: invoke this skill to get cookies instead of running the visible-browser login (Step 4 alternative).
- **`/manual-qa`** — before driving a gated SPA, invoke this skill to authenticate.
- **`/capture-editor-states`** — accepts `--cookies FILE` arg; pass the JSON produced here.
