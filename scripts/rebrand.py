#!/usr/bin/env python3
"""
Post-clone rebrand tool.

Reads a rebrand.json config and applies string/asset replacements across a
cloned project directory (HTML, JSX, TSX, JSON, CSS, MD, text files). Case
preservation: replacing "Foo" -> "Bar" also maps "foo"->"bar", "FOO"->"BAR".

Usage:
    python3 rebrand.py --config clones/example.com/rebrand.json --target clones/example.com/my-template

rebrand.json schema:
    {
      "name_replacements": [
        {"from": "Source", "to": "Target"}
      ],
      "domain_replacements": [
        {"from": "source.com", "to": "target.com"}
      ],
      "asset_replacements": [
        {"from": "favicon.ico", "to": "target-favicon.ico"}
      ],
      "delete_files": ["brand-specific-asset.png"],
      "extensions": [".html", ".jsx", ".tsx", ".ts", ".js", ".json", ".css", ".md", ".txt", ".mdx"],
      "skip_dirs": ["node_modules", ".next", ".git", "dist", "build"]
    }
"""

import argparse
import json
import re
import shutil
import sys
from pathlib import Path


DEFAULT_EXTENSIONS = [
    ".html", ".htm", ".jsx", ".tsx", ".ts", ".js", ".mjs",
    ".json", ".css", ".scss", ".md", ".mdx", ".txt", ".xml", ".svg",
]
DEFAULT_SKIP_DIRS = {"node_modules", ".next", ".git", "dist", "build", ".turbo", ".cache"}


def case_variants(src: str, dst: str) -> list[tuple[str, str]]:
    """Produce case-preserving variants. 'Foo'->'Bar' also yields foo->bar, FOO->BAR."""
    variants: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for s, d in [
        (src, dst),
        (src.lower(), dst.lower()),
        (src.upper(), dst.upper()),
        (src.capitalize(), dst.capitalize()),
        (src.title(), dst.title()),
    ]:
        key = (s, d)
        if s and key not in seen:
            variants.append(key)
            seen.add(key)
    # Longest source first so longer strings replace before their substrings
    variants.sort(key=lambda p: len(p[0]), reverse=True)
    return variants


def apply_replacements(text: str, replacements: list[tuple[str, str]]) -> tuple[str, int]:
    count = 0
    for src, dst in replacements:
        if src not in text:
            continue
        occurrences = text.count(src)
        text = text.replace(src, dst)
        count += occurrences
    return text, count


def should_process(path: Path, extensions: list[str], skip_dirs: set[str]) -> bool:
    if any(part in skip_dirs for part in path.parts):
        return False
    return path.suffix.lower() in extensions


def main():
    parser = argparse.ArgumentParser(description="Post-clone rebrand tool")
    parser.add_argument("--config", required=True, type=Path, help="rebrand.json config")
    parser.add_argument("--target", required=True, type=Path, help="Target project directory")
    parser.add_argument("--dry-run", action="store_true", help="Print changes without writing")
    args = parser.parse_args()

    if not args.config.exists():
        print(f"Config not found: {args.config}", file=sys.stderr)
        sys.exit(1)
    if not args.target.exists():
        print(f"Target directory not found: {args.target}", file=sys.stderr)
        sys.exit(1)

    cfg = json.loads(args.config.read_text())

    replacements: list[tuple[str, str]] = []
    for entry in cfg.get("name_replacements", []) + cfg.get("domain_replacements", []):
        replacements.extend(case_variants(entry["from"], entry["to"]))
    replacements.sort(key=lambda p: len(p[0]), reverse=True)

    extensions = [e.lower() for e in cfg.get("extensions", DEFAULT_EXTENSIONS)]
    skip_dirs = set(cfg.get("skip_dirs", DEFAULT_SKIP_DIRS))

    files_touched = 0
    total_replacements = 0
    for path in args.target.rglob("*"):
        if not path.is_file():
            continue
        if not should_process(path, extensions, skip_dirs):
            continue
        try:
            original = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, PermissionError):
            continue
        new, n = apply_replacements(original, replacements)
        if n == 0:
            continue
        files_touched += 1
        total_replacements += n
        if args.dry_run:
            print(f"  [dry-run] {path} ({n} replacements)")
        else:
            path.write_text(new, encoding="utf-8")
            print(f"  {path} ({n} replacements)")

    for asset in cfg.get("asset_replacements", []):
        src_path = args.target / asset["from"]
        dst_path = args.target / asset["to"]
        if src_path.exists():
            if args.dry_run:
                print(f"  [dry-run] rename asset {src_path} -> {dst_path}")
            else:
                dst_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(src_path), str(dst_path))
                print(f"  rename asset {src_path} -> {dst_path}")

    for rel in cfg.get("delete_files", []):
        target = args.target / rel
        if target.exists():
            if args.dry_run:
                print(f"  [dry-run] delete {target}")
            else:
                target.unlink() if target.is_file() else shutil.rmtree(target)
                print(f"  delete {target}")

    print(f"\nRebrand {'preview ' if args.dry_run else ''}complete.")
    print(f"   Files touched: {files_touched}")
    print(f"   Replacements: {total_replacements}")


if __name__ == "__main__":
    main()
