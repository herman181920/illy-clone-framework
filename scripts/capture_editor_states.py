#!/usr/bin/env python3
"""
Multi-state editor capture.

Opens a visible Playwright browser, optionally loads cookies, navigates to an
editor URL, and lets the user (or a scripted tour) walk through UI states.
Each state produces a full-page screenshot + DOM snapshot saved as
editor-states/{slug}.html + editor-states/{slug}.png.

Usage:
    python3 capture_editor_states.py \\
        --url https://example.com/editor \\
        --output clones/example.com/editor-states \\
        [--cookies clones/example.com/cookies.json] \\
        [--viewport 1920x1080]

Interactive flow:
    1. Browser opens, navigates to URL.
    2. User logs in (if needed) and interacts to reach each desired state.
    3. Press ENTER in terminal to snapshot the current state.
    4. Enter a slug name (e.g., "empty", "timeline-with-clip").
    5. Repeat until done; type "quit" to exit.
"""

import argparse
import asyncio
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

from playwright.async_api import async_playwright


SLUG_RE = re.compile(r"[^a-z0-9\-]+")


def slugify(name: str) -> str:
    return SLUG_RE.sub("-", name.lower().strip()).strip("-") or "state"


def parse_viewport(s: str) -> tuple[int, int]:
    w, h = s.lower().split("x")
    return int(w), int(h)


async def prompt(msg: str) -> str:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: input(msg))


async def capture_state(page, output: Path, slug: str):
    html = await page.content()
    (output / f"{slug}.html").write_text(html, encoding="utf-8")
    await page.screenshot(path=output / f"{slug}.png", full_page=True)
    print(f"  saved: {slug}.html + {slug}.png")


async def run(url: str, output: Path, cookies_file: Path | None, viewport: tuple[int, int]):
    output.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            viewport={"width": viewport[0], "height": viewport[1]},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
        )
        if cookies_file and cookies_file.exists():
            cookies = json.loads(cookies_file.read_text())
            await context.add_cookies(cookies)
            print(f"Loaded cookies from {cookies_file}")

        page = await context.new_page()
        print(f"\nNavigating to {url}")
        await page.goto(url, wait_until="networkidle", timeout=60000)
        print("Page loaded. Interact to reach each UI state you want to capture.\n")

        # If no cookies, offer to save after login
        if not cookies_file or not cookies_file.exists():
            choice = (await prompt("Log in if needed, then press ENTER to save cookies, or 's' to skip: ")).strip()
            if choice != "s":
                domain_host = urlparse(url).netloc
                save_path = output.parent / f"{domain_host.replace('.', '_')}_cookies.json"
                cookies_out = await context.cookies()
                save_path.write_text(json.dumps(cookies_out, indent=2))
                print(f"  cookies saved to {save_path}\n")

        print("Capture loop. Interact in the browser, then enter a state name in the terminal.")
        print("Commands: <slug-name> to capture, 'quit' to exit.\n")

        while True:
            name = (await prompt("state name (or 'quit'): ")).strip()
            if name.lower() in ("quit", "q", "exit"):
                break
            if not name:
                continue
            slug = slugify(name)
            await capture_state(page, output, slug)

        await browser.close()
        print(f"\nDone. States saved under {output}/")


def main():
    parser = argparse.ArgumentParser(description="Multi-state SPA editor capture")
    parser.add_argument("--url", required=True, help="Editor URL to open")
    parser.add_argument("--output", required=True, type=Path, help="Output dir for state snapshots")
    parser.add_argument("--cookies", type=Path, help="Optional pre-saved cookies.json")
    parser.add_argument("--viewport", type=parse_viewport, default=(1920, 1080))
    args = parser.parse_args()

    asyncio.run(run(args.url, args.output, args.cookies, args.viewport))


if __name__ == "__main__":
    main()
