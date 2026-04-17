#!/usr/bin/env python3
"""
Record and replay user interaction flows as portable JSON specs.

Two modes:

  --record   Launches a visible browser. Monitors user interactions (clicks,
             fills, selects, uploads, navigations, keypresses). Writes a
             flow spec JSON to ./flows/{name}.json on exit.

  --playback Reads a flow spec JSON. Replays each step against a target URL
             using Playwright async. Produces a parallel JSON report with
             per-step PASS/FAIL and screenshot paths.

Spec JSON shape:
  {
    "name": "flow-name",
    "description": "one line",
    "start_url": "https://...",
    "steps": [
      { "type": "click", "selector": { "role": "button", "name": "Continue" }, "note": "..." },
      { "type": "fill",  "selector": { "role": "textbox", "name": "Email" },   "value": "test@example.com" }
    ]
  }

Selector priority order (most portable first):
  1. role + name  — aria role + accessible name (most portable across implementations)
  2. text         — visible text content (fragile if copy changes)
  3. id           — DOM id (ok if stable; fragile if generated)
  4. data-attr    — stable data-testid / data-qa / data-cy
  5. css          — fallback; last resort

Usage:
  # Record a new flow
  python3 scripts/record_flow.py --record --name create-project \
      --start-url https://app.example.com/projects \
      --cookies clones/example.com/cookies.json

  # Play back a recorded flow against a target
  python3 scripts/record_flow.py --playback --spec flows/create-project.json \
      --target-url https://localhost:3000 \
      --cookies clones/example.com/cookies.json \
      --out flows/reports/create-project-report.json
"""

import argparse
import asyncio
import json
import os
import sys
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Locator

FLOWS_DIR = Path("./flows")
SCREENSHOTS_DIR = Path("./flows/screenshots")
REPORTS_DIR = Path("./flows/reports")

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class Selector:
    """Semantic selector in priority order. Recorder fills the highest-priority
    field it can determine; playback tries them in order until one resolves."""
    role: str | None = None
    name: str | None = None   # accessible name (aria-label, text, title)
    text: str | None = None   # visible text content (partial match)
    id: str | None = None
    data_attr: str | None = None   # e.g. data-testid="submit-btn"
    css: str | None = None         # last resort css selector


@dataclass
class Step:
    type: str   # navigate | click | fill | select | upload | press | wait-for | screenshot
    selector: Selector | None = None
    url: str | None = None         # for navigate steps
    value: str | None = None       # for fill / select / press steps
    files: list[str] | None = None # for upload steps
    timeout_ms: int | None = None  # for wait-for steps
    note: str | None = None        # human-readable annotation


@dataclass
class FlowSpec:
    name: str
    description: str
    start_url: str
    steps: list[Step] = field(default_factory=list)


@dataclass
class StepResult:
    step_index: int
    step_type: str
    result: str          # PASS | FAIL | SKIP
    error: str | None = None
    screenshot: str | None = None
    note: str | None = None


@dataclass
class PlaybackReport:
    spec_name: str
    target_url: str
    timestamp: str
    total: int
    passed: int
    failed: int
    skipped: int
    steps: list[StepResult] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------

def selector_to_dict(sel: Selector | None) -> dict | None:
    if sel is None:
        return None
    return {k: v for k, v in asdict(sel).items() if v is not None}


def step_to_dict(step: Step) -> dict:
    d: dict[str, Any] = {"type": step.type}
    if step.selector:
        d["selector"] = selector_to_dict(step.selector)
    if step.url:
        d["url"] = step.url
    if step.value:
        d["value"] = step.value
    if step.files:
        d["files"] = step.files
    if step.timeout_ms:
        d["timeout_ms"] = step.timeout_ms
    if step.note:
        d["note"] = step.note
    return d


def flow_to_dict(spec: FlowSpec) -> dict:
    return {
        "name": spec.name,
        "description": spec.description,
        "start_url": spec.start_url,
        "steps": [step_to_dict(s) for s in spec.steps],
    }


def dict_to_selector(d: dict | None) -> Selector | None:
    if not d:
        return None
    return Selector(
        role=d.get("role"),
        name=d.get("name"),
        text=d.get("text"),
        id=d.get("id"),
        data_attr=d.get("data_attr"),
        css=d.get("css"),
    )


def dict_to_step(d: dict) -> Step:
    return Step(
        type=d["type"],
        selector=dict_to_selector(d.get("selector")),
        url=d.get("url"),
        value=d.get("value"),
        files=d.get("files"),
        timeout_ms=d.get("timeout_ms"),
        note=d.get("note"),
    )


def dict_to_flow(d: dict) -> FlowSpec:
    return FlowSpec(
        name=d["name"],
        description=d.get("description", ""),
        start_url=d["start_url"],
        steps=[dict_to_step(s) for s in d.get("steps", [])],
    )


def report_to_dict(report: PlaybackReport) -> dict:
    return {
        "spec_name": report.spec_name,
        "target_url": report.target_url,
        "timestamp": report.timestamp,
        "summary": {
            "total": report.total,
            "passed": report.passed,
            "failed": report.failed,
            "skipped": report.skipped,
        },
        "steps": [asdict(s) for s in report.steps],
    }


# ---------------------------------------------------------------------------
# Cookie loading
# ---------------------------------------------------------------------------

async def load_cookies(context: BrowserContext, cookies_path: Path) -> int:
    cookies = json.loads(cookies_path.read_text())
    await context.add_cookies(cookies)
    return len(cookies)


# ---------------------------------------------------------------------------
# Selector resolution (playback)
# ---------------------------------------------------------------------------

async def resolve_locator(page: Page, sel: Selector) -> Locator | None:
    """Try selector strategies in priority order. Return first that finds >= 1 element."""
    if sel.role and sel.name:
        try:
            loc = page.get_by_role(sel.role, name=sel.name)
            count = await loc.count()
            if count > 0:
                return loc.first
        except Exception:
            pass

    if sel.role and not sel.name:
        try:
            loc = page.get_by_role(sel.role)
            count = await loc.count()
            if count > 0:
                return loc.first
        except Exception:
            pass

    if sel.text:
        try:
            loc = page.get_by_text(sel.text, exact=False)
            count = await loc.count()
            if count > 0:
                return loc.first
        except Exception:
            pass

    if sel.id:
        try:
            loc = page.locator(f"#{sel.id}")
            count = await loc.count()
            if count > 0:
                return loc.first
        except Exception:
            pass

    if sel.data_attr:
        try:
            # data_attr format: "data-testid=value"
            if "=" in sel.data_attr:
                attr_name, attr_val = sel.data_attr.split("=", 1)
                loc = page.locator(f"[{attr_name}='{attr_val}']")
            else:
                loc = page.locator(f"[{sel.data_attr}]")
            count = await loc.count()
            if count > 0:
                return loc.first
        except Exception:
            pass

    if sel.css:
        try:
            loc = page.locator(sel.css)
            count = await loc.count()
            if count > 0:
                return loc.first
        except Exception:
            pass

    return None


# ---------------------------------------------------------------------------
# Recorder — JS injection to capture interactions
# ---------------------------------------------------------------------------

RECORDER_SCRIPT = """
(function() {
  if (window.__flowRecorder) return;
  window.__flowRecorder = { steps: [], _lastNav: null };

  // Navigation
  var origPushState = history.pushState.bind(history);
  var origReplaceState = history.replaceState.bind(history);
  function recordNav(url) {
    window.__flowRecorder.steps.push({
      type: 'navigate',
      url: url,
      timestamp: Date.now()
    });
  }
  history.pushState = function() { origPushState.apply(this, arguments); recordNav(location.href); };
  history.replaceState = function() { origPushState.apply(this, arguments); };

  // Clicks
  document.addEventListener('click', function(e) {
    var el = e.target.closest('button,a,[role="button"],[role="link"],[role="menuitem"],[role="option"],[role="tab"],[role="checkbox"],[role="radio"]') || e.target;
    if (!el) return;

    var role = el.getAttribute('role') || el.tagName.toLowerCase();
    if (role === 'a') role = 'link';
    if (role === 'button') role = 'button';

    var name = el.getAttribute('aria-label')
      || el.getAttribute('title')
      || el.textContent.trim().slice(0, 80)
      || null;

    var sel = { role: role };
    if (name) sel.name = name;
    if (el.id) sel.id = el.id;
    var testId = el.getAttribute('data-testid') || el.getAttribute('data-qa') || el.getAttribute('data-cy');
    if (testId) {
      var attrName = el.getAttribute('data-testid') ? 'data-testid'
                   : el.getAttribute('data-qa') ? 'data-qa'
                   : 'data-cy';
      sel.data_attr = attrName + '=' + testId;
    }

    window.__flowRecorder.steps.push({
      type: 'click',
      selector: sel,
      note: el.textContent.trim().slice(0, 40) || null,
      timestamp: Date.now()
    });
  }, true);

  // Fill (input / textarea change)
  document.addEventListener('change', function(e) {
    var el = e.target;
    if (!['INPUT','TEXTAREA','SELECT'].includes(el.tagName)) return;

    var role = el.tagName === 'SELECT' ? 'combobox' : el.getAttribute('role') || 'textbox';
    if (el.type === 'checkbox' || el.type === 'radio') return; // handled by click

    var label = el.getAttribute('aria-label')
      || el.getAttribute('placeholder')
      || el.getAttribute('name')
      || el.id
      || null;

    var sel = { role: role };
    if (label) sel.name = label;
    if (el.id) sel.id = el.id;

    var stepType = el.tagName === 'SELECT' ? 'select' : 'fill';
    var value = el.tagName === 'SELECT'
      ? (el.options[el.selectedIndex] ? el.options[el.selectedIndex].text : el.value)
      : el.value;

    window.__flowRecorder.steps.push({
      type: stepType,
      selector: sel,
      value: value,
      timestamp: Date.now()
    });
  }, true);

  // Key presses (Enter, Escape, Tab — meaningful ones)
  var RECORD_KEYS = new Set(['Enter','Escape','Tab','ArrowUp','ArrowDown']);
  document.addEventListener('keydown', function(e) {
    if (!RECORD_KEYS.has(e.key)) return;
    window.__flowRecorder.steps.push({
      type: 'press',
      value: e.key,
      timestamp: Date.now()
    });
  }, true);

  console.log('[flow-recorder] Attached. Interact with the page. Steps accumulate in window.__flowRecorder.steps');
})();
"""


async def record_mode(
    name: str,
    start_url: str,
    description: str,
    cookies_path: Path | None,
    out_dir: Path,
) -> int:
    print(f"[record] Starting browser at {start_url}")
    print("[record] Interact with the page. Close the browser when done.")
    print("[record] Steps are captured automatically.")

    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{name}.json"

    async with async_playwright() as pw:
        browser: Browser = await pw.chromium.launch(headless=False, slow_mo=100)
        context: BrowserContext = await browser.new_context()

        if cookies_path:
            n = await load_cookies(context, cookies_path)
            print(f"[record] Loaded {n} cookies from {cookies_path}")

        page: Page = await context.new_page()

        # Seed the recorder script on every navigation
        await page.add_init_script(RECORDER_SCRIPT)
        await page.goto(start_url, wait_until="domcontentloaded")
        await page.evaluate(RECORDER_SCRIPT)  # inject into already-loaded page too

        spec = FlowSpec(name=name, description=description, start_url=start_url)

        print("[record] Browser open. Waiting for you to close it...")
        try:
            await page.wait_for_event("close", timeout=0)  # wait indefinitely
        except Exception:
            pass

        # Pull recorded steps
        try:
            raw_steps = await page.evaluate("() => window.__flowRecorder ? window.__flowRecorder.steps : []")
        except Exception:
            raw_steps = []

        # Deduplicate adjacent fill events (keep last fill per field before a click/navigate)
        deduped: list[dict] = []
        for step in raw_steps:
            if deduped and step["type"] in ("fill", "select") and deduped[-1]["type"] in ("fill", "select"):
                if deduped[-1].get("selector", {}).get("name") == step.get("selector", {}).get("name"):
                    deduped[-1] = step  # replace with latest value
                    continue
            deduped.append(step)

        for raw in deduped:
            s = Step(type=raw["type"])
            if raw.get("selector"):
                s.selector = Selector(**{k: v for k, v in raw["selector"].items() if k in Selector.__dataclass_fields__})
            s.url = raw.get("url")
            s.value = raw.get("value")
            s.note = raw.get("note")
            spec.steps.append(s)

        await browser.close()

    out_path.write_text(json.dumps(flow_to_dict(spec), indent=2))
    print(f"[record] Wrote {len(spec.steps)} steps to {out_path}")
    return 0


# ---------------------------------------------------------------------------
# Playback
# ---------------------------------------------------------------------------

async def take_screenshot(page: Page, label: str, screenshots_dir: Path) -> str:
    screenshots_dir.mkdir(parents=True, exist_ok=True)
    fname = f"{label}.png"
    fpath = screenshots_dir / fname
    await page.screenshot(path=str(fpath), full_page=False)
    return str(fpath)


async def play_step(page: Page, step: Step, idx: int, screenshots_dir: Path) -> StepResult:
    label = f"step-{idx:03d}-{step.type}"
    result = StepResult(step_index=idx, step_type=step.type, result="FAIL")

    try:
        if step.type == "navigate":
            url = step.url or step.value
            if not url:
                result.result = "SKIP"
                result.note = "No URL provided for navigate step"
                return result
            await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
            result.result = "PASS"

        elif step.type in ("click", "fill", "select"):
            if not step.selector:
                result.result = "SKIP"
                result.note = "No selector"
                return result

            loc = await resolve_locator(page, step.selector)
            if not loc:
                result.error = f"Could not resolve selector: {selector_to_dict(step.selector)}"
                return result

            await loc.scroll_into_view_if_needed(timeout=5_000)

            if step.type == "click":
                await loc.click(timeout=10_000)
                await page.wait_for_load_state("networkidle", timeout=5_000)
            elif step.type == "fill":
                await loc.fill(step.value or "", timeout=10_000)
            elif step.type == "select":
                await loc.select_option(label=step.value, timeout=10_000)

            result.result = "PASS"

        elif step.type == "upload":
            if not step.selector or not step.files:
                result.result = "SKIP"
                result.note = "Missing selector or files for upload step"
                return result
            loc = await resolve_locator(page, step.selector)
            if not loc:
                result.error = f"Could not resolve selector: {selector_to_dict(step.selector)}"
                return result
            await loc.set_input_files(step.files, timeout=10_000)
            result.result = "PASS"

        elif step.type == "press":
            if not step.value:
                result.result = "SKIP"
                result.note = "No key value for press step"
                return result
            await page.keyboard.press(step.value)
            result.result = "PASS"

        elif step.type == "wait-for":
            timeout = step.timeout_ms or 3_000
            if step.selector:
                loc = await resolve_locator(page, step.selector)
                if loc:
                    await loc.wait_for(state="visible", timeout=timeout)
                    result.result = "PASS"
                else:
                    await page.wait_for_timeout(timeout)
                    result.result = "PASS"
            else:
                await page.wait_for_timeout(timeout)
                result.result = "PASS"

        elif step.type == "screenshot":
            # An explicit screenshot step — just capture, always PASS
            result.result = "PASS"

        else:
            result.result = "SKIP"
            result.note = f"Unknown step type: {step.type}"
            return result

    except Exception as e:
        result.error = str(e)
        result.result = "FAIL"

    # Always capture screenshot after each step
    try:
        screenshot_path = await take_screenshot(page, label, screenshots_dir)
        result.screenshot = screenshot_path
    except Exception:
        pass

    return result


async def playback_mode(
    spec: FlowSpec,
    target_url: str | None,
    cookies_path: Path | None,
    out_path: Path,
) -> int:
    start_url = target_url or spec.start_url
    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)

    print(f"[playback] Replaying '{spec.name}' against {start_url}")
    print(f"[playback] {len(spec.steps)} steps to replay")

    report = PlaybackReport(
        spec_name=spec.name,
        target_url=start_url,
        timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        total=len(spec.steps),
        passed=0,
        failed=0,
        skipped=0,
    )

    async with async_playwright() as pw:
        browser: Browser = await pw.chromium.launch(headless=True)
        context: BrowserContext = await browser.new_context(
            viewport={"width": 1440, "height": 900}
        )

        if cookies_path:
            n = await load_cookies(context, cookies_path)
            print(f"[playback] Loaded {n} cookies from {cookies_path}")

        page: Page = await context.new_page()
        await page.goto(start_url, wait_until="domcontentloaded", timeout=30_000)

        for idx, step in enumerate(spec.steps):
            print(f"[playback] Step {idx:03d}: {step.type}", end="")
            if step.selector and step.selector.name:
                print(f" — '{step.selector.name}'", end="")
            print()

            step_result = await play_step(page, step, idx, SCREENSHOTS_DIR)
            report.steps.append(step_result)

            if step_result.result == "PASS":
                report.passed += 1
                print(f"  PASS")
            elif step_result.result == "FAIL":
                report.failed += 1
                print(f"  FAIL: {step_result.error}")
            else:
                report.skipped += 1
                print(f"  SKIP: {step_result.note}")

        await browser.close()

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report_to_dict(report), indent=2))

    print(f"\n[playback] Done: {report.passed}/{report.total} PASS, {report.failed} FAIL, {report.skipped} SKIP")
    print(f"[playback] Report written to {out_path}")

    return 0 if report.failed == 0 else 1


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Record and replay user interaction flows as portable JSON specs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--record", action="store_true", help="Record mode: launch visible browser, capture interactions")
    mode.add_argument("--playback", action="store_true", help="Playback mode: replay a spec JSON against a target URL")

    # Record args
    parser.add_argument("--name", help="Flow name (slug, no spaces). Required for --record.")
    parser.add_argument("--start-url", help="URL to open at start of recording.")
    parser.add_argument("--description", default="", help="One-line description of the flow.")

    # Playback args
    parser.add_argument("--spec", type=Path, help="Path to flow spec JSON. Required for --playback.")
    parser.add_argument("--target-url", help="Override start_url from spec (e.g. localhost:3000 for clone testing).")
    parser.add_argument("--out", type=Path, help="Playback report output path. Default: flows/reports/{name}-report.json")

    # Shared
    parser.add_argument("--cookies", type=Path, help="Path to Playwright-compatible cookies JSON (from import_browser_cookies.py).")
    parser.add_argument("--flows-dir", type=Path, default=FLOWS_DIR, help="Directory to write flow specs. Default: ./flows")

    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if args.record:
        if not args.name:
            print("Error: --name is required for --record mode", file=sys.stderr)
            return 1
        if not args.start_url:
            print("Error: --start-url is required for --record mode", file=sys.stderr)
            return 1
        cookies_path = args.cookies if args.cookies else None
        if cookies_path and not cookies_path.exists():
            print(f"Error: cookies file not found: {cookies_path}", file=sys.stderr)
            return 1
        return asyncio.run(record_mode(
            name=args.name,
            start_url=args.start_url,
            description=args.description,
            cookies_path=cookies_path,
            out_dir=args.flows_dir,
        ))

    if args.playback:
        if not args.spec:
            print("Error: --spec is required for --playback mode", file=sys.stderr)
            return 1
        if not args.spec.exists():
            print(f"Error: spec file not found: {args.spec}", file=sys.stderr)
            return 1

        raw = json.loads(args.spec.read_text())
        spec = dict_to_flow(raw)

        cookies_path = args.cookies if args.cookies else None
        if cookies_path and not cookies_path.exists():
            print(f"Error: cookies file not found: {cookies_path}", file=sys.stderr)
            return 1

        out_path = args.out or REPORTS_DIR / f"{spec.name}-report.json"

        return asyncio.run(playback_mode(
            spec=spec,
            target_url=args.target_url,
            cookies_path=cookies_path,
            out_path=out_path,
        ))

    return 0


if __name__ == "__main__":
    sys.exit(main())
