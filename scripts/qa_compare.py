#!/usr/bin/env python3
"""
QA Comparison Tool for a cloned site.
Screenshots original vs clone, compares pixel differences, generates report.

Override ORIGINAL_BASE, CLONE_BASE, OUTPUT_DIR, URLS_FILE, and SAMPLE_PAGES
for your target before running. See README.md for /qa skill integration.
"""

import asyncio
import json
import os
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

from playwright.async_api import async_playwright
from PIL import Image, ImageChops, ImageDraw, ImageFont
import math

ORIGINAL_BASE = "https://www.example.com"
CLONE_BASE = "http://localhost:8787"
OUTPUT_DIR = Path("projects/example_clone/qa_report")
URLS_FILE = Path("example_urls.json")

# Pages to compare (representative sample across page types) — override per target
SAMPLE_PAGES = [
    "/",
    "/about",
    "/pricing",
    "/features",
    "/contact",
    "/privacy",
]


def url_to_filename(path: str) -> str:
    """Convert URL path to safe filename."""
    if path == "/" or path == "":
        return "index"
    return path.strip("/").replace("/", "_")


def compare_images(img1_path: str, img2_path: str) -> dict:
    """Compare two screenshots and return similarity metrics."""
    img1 = Image.open(img1_path).convert("RGB")
    img2 = Image.open(img2_path).convert("RGB")

    # Resize to same dimensions (use smaller height to avoid scroll differences)
    w = min(img1.width, img2.width)
    h = min(img1.height, img2.height)
    img1 = img1.crop((0, 0, w, h))
    img2 = img2.crop((0, 0, w, h))

    # Pixel difference
    diff = ImageChops.difference(img1, img2)
    pixels = list(diff.getdata())
    total_pixels = len(pixels)

    # Count pixels that differ significantly (threshold > 30 per channel)
    threshold = 30
    diff_pixels = sum(1 for p in pixels if any(c > threshold for c in p))
    similarity = 1 - (diff_pixels / total_pixels) if total_pixels > 0 else 1

    # RMS difference
    sum_sq = sum(sum(c * c for c in p) for p in pixels)
    rms = math.sqrt(sum_sq / (total_pixels * 3)) if total_pixels > 0 else 0

    # Save diff image with red highlights
    diff_highlight = img1.copy()
    draw = ImageDraw.Draw(diff_highlight)
    for y in range(h):
        for x in range(w):
            p = diff.getpixel((x, y))
            if any(c > threshold for c in p):
                draw.point((x, y), fill=(255, 0, 0))

    diff_path = str(img1_path).replace("-original.", "-diff.")
    diff_highlight.save(diff_path)

    return {
        "similarity": round(similarity * 100, 2),
        "rms_error": round(rms, 2),
        "diff_pixels": diff_pixels,
        "total_pixels": total_pixels,
        "diff_image": diff_path,
    }


async def screenshot_page(page, url: str, output_path: str, scroll: bool = True):
    """Navigate to URL and take a viewport screenshot."""
    try:
        await page.goto(url, wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(1500)

        if scroll:
            # Scroll down to trigger lazy loading, then back to top
            await page.evaluate("""
                async () => {
                    for (let y = 0; y < Math.min(document.body.scrollHeight, 5000); y += 500) {
                        window.scrollTo(0, y);
                        await new Promise(r => setTimeout(r, 100));
                    }
                    window.scrollTo(0, 0);
                }
            """)
            await page.wait_for_timeout(500)

        await page.screenshot(path=output_path, full_page=False, timeout=15000)
        return True
    except Exception as e:
        print(f"    ERROR screenshotting {url}: {e}")
        return False


async def run_comparison(pages=None):
    """Run the full QA comparison."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if pages is None:
        pages = SAMPLE_PAGES

    print(f"\n🔍 QA Comparison: {len(pages)} pages\n")

    results = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        # Two contexts with same viewport
        ctx_original = await browser.new_context(viewport={"width": 1920, "height": 1080})
        ctx_clone = await browser.new_context(viewport={"width": 1920, "height": 1080})

        page_orig = await ctx_original.new_page()
        page_clone = await ctx_clone.new_page()

        for i, path in enumerate(pages):
            name = url_to_filename(path)
            print(f"  [{i+1}/{len(pages)}] {path}")

            orig_url = f"{ORIGINAL_BASE}{path}"
            clone_path = path.strip("/")
            if not clone_path:
                clone_url = f"{CLONE_BASE}/index.html"
            else:
                clone_url = f"{CLONE_BASE}/{clone_path}.html"

            orig_img = str(OUTPUT_DIR / f"{name}-original.png")
            clone_img = str(OUTPUT_DIR / f"{name}-clone.png")

            # Screenshot both
            ok1 = await screenshot_page(page_orig, orig_url, orig_img)
            ok2 = await screenshot_page(page_clone, clone_url, clone_img)

            if ok1 and ok2:
                # Compare
                comparison = compare_images(orig_img, clone_img)
                status = "✅" if comparison["similarity"] >= 95 else "⚠️" if comparison["similarity"] >= 80 else "❌"
                print(f"    {status} Similarity: {comparison['similarity']}%  (RMS: {comparison['rms_error']})")

                results.append({
                    "page": path,
                    "original_screenshot": orig_img,
                    "clone_screenshot": clone_img,
                    "diff_screenshot": comparison["diff_image"],
                    **comparison,
                })
            else:
                results.append({
                    "page": path,
                    "error": "Screenshot failed",
                    "similarity": 0,
                })

        await browser.close()

    # Summary
    avg_similarity = sum(r.get("similarity", 0) for r in results) / len(results) if results else 0
    passing = sum(1 for r in results if r.get("similarity", 0) >= 95)
    warnings = sum(1 for r in results if 80 <= r.get("similarity", 0) < 95)
    failing = sum(1 for r in results if r.get("similarity", 0) < 80)

    print(f"\n{'='*50}")
    print(f"📊 QA Summary")
    print(f"{'='*50}")
    print(f"  Average similarity: {avg_similarity:.1f}%")
    print(f"  ✅ Passing (≥95%):  {passing}/{len(results)}")
    print(f"  ⚠️  Warning (80-95%): {warnings}/{len(results)}")
    print(f"  ❌ Failing (<80%):   {failing}/{len(results)}")

    if failing > 0 or warnings > 0:
        print(f"\n  Pages needing fixes:")
        for r in sorted(results, key=lambda x: x.get("similarity", 0)):
            if r.get("similarity", 0) < 95:
                print(f"    {r['page']}: {r.get('similarity', 0)}%")

    # Save report
    report_path = OUTPUT_DIR / "qa_report.json"
    with open(report_path, "w") as f:
        json.dump({
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "average_similarity": round(avg_similarity, 2),
            "passing": passing,
            "warnings": warnings,
            "failing": failing,
            "results": results,
        }, f, indent=2)

    print(f"\n  Report saved: {report_path}")
    print(f"  Screenshots: {OUTPUT_DIR}/")

    return results


if __name__ == "__main__":
    # Allow passing specific pages as args
    pages = sys.argv[1:] if len(sys.argv) > 1 else None
    asyncio.run(run_comparison(pages))
