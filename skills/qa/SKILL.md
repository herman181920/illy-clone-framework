---
name: qa
description: This skill should be used when the user asks to "compare screenshots", "QA the clone", "check visual fidelity", "compare clone vs original", "run QA comparison", or wants to verify a cloned site matches the original. Runs automated pixel-level screenshot comparison with benchmark tracking.
version: 0.1.0
---

# QA Screenshot Comparison

Automated visual QA system that compares the original live site against a local clone or framework template. Produces per-page similarity percentages, diff images with highlighted differences, and zone-level analysis to pinpoint exactly where and why visual gaps exist.

## How It Works

The QA comparison follows a five-stage process: serve the clone, screenshot both sites, compute pixel differences, analyze zones, and generate a report.

### Stage 1: Serve the Clone Locally

Before comparing, ensure the clone is being served on a local HTTP server. Start the generated server script:

```bash
cd projects/{domain}_clone && python3 serve.py &
```

Use a unique port for each project to avoid conflicts when multiple clones exist. The default `serve.py` uses port 8000, but modify it if that port is occupied. Verify the server is running by checking that `curl -s http://localhost:{port}/index.html` returns HTML content.

For framework templates (Vite, Next.js), always rebuild before comparing:

```bash
# Vite + React
cd projects/{domain}_template && npm run build && npx serve dist -p {port} &

# Next.js
cd projects/{domain}_template && npm run build && npm start -- -p {port} &
```

Stale builds are the single most common cause of false QA failures. If the QA score drops unexpectedly after code changes, rebuild first and re-run before investigating further.

### Stage 2: Take Viewport Screenshots

Use headless Playwright via the Python sync/async API to screenshot every page on both the original and clone sites. Critically, use `playwright.async_api` in Python directly — do NOT use the Playwright MCP server. The MCP server controls a single shared browser instance, and running QA through it conflicts with any other browser automation happening in the session.

Run the comparison script:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/qa_compare.py
```

Before running, update the script's configuration variables:
- `ORIGINAL_BASE` = the original site's URL (e.g., `https://www.example.com`)
- `CLONE_BASE` = the local server URL (e.g., `http://localhost:8000`)
- `OUTPUT_DIR` = where to save screenshots and the report
- `SAMPLE_PAGES` = list of URL paths to compare (or use the full URL list from the clone step)

Screenshot parameters:
- Viewport: 1920x1080 (desktop standard)
- `full_page=False` — capture only the viewport, not the scrolled page. Full-page screenshots introduce height mismatches that inflate diff percentages. Viewport-only gives consistent, comparable captures.
- Wait for `networkidle` plus an additional 1500ms delay to allow fonts, images, and CSS animations to settle.
- Scroll down and back to top before screenshotting to trigger lazy-loaded content, ensuring the viewport shows fully loaded content.

For each page, the script produces three files:
- `{page}-original.png` — screenshot of the live site
- `{page}-clone.png` — screenshot of the local clone
- `{page}-diff.png` — diff image with red pixels marking differences

### Stage 3: Pixel Comparison

For each page pair, compute pixel-level similarity:

1. Open both screenshots with Pillow (PIL).
2. Crop both to the same dimensions (use the smaller of the two heights/widths to avoid mismatch from scroll differences).
3. Compute `ImageChops.difference()` to get per-pixel RGB differences.
4. Apply a threshold of 30 per RGB channel. Any pixel where all three channels differ by less than 30 is considered matching. This threshold filters out antialiasing artifacts, sub-pixel rendering differences, and minor color space variations between browser instances.
5. Count the number of pixels exceeding the threshold.
6. Calculate similarity as `(1 - differing_pixels / total_pixels) * 100`.

The threshold of 30 is calibrated from empirical testing. Lower values (10-20) produce false positives from font antialiasing. Higher values (50+) mask real differences in color or layout. Adjust only if you have a specific reason.

### Stage 4: Zone Analysis

Divide each page into horizontal bands (typically 10-20 bands depending on page height). For each band, compute the local similarity percentage. This reveals WHERE differences concentrate:

- **Top zone (header/nav):** Differences here usually indicate missing fonts, logo issues, or navigation styling gaps.
- **Middle zones (content):** Differences suggest missing images, layout shifts, or CSS property discrepancies.
- **Bottom zone (footer):** Often affected by dynamic content (copyright year, live counters) or cookie consent banners.

Zone analysis is more actionable than the aggregate score because it directs fix efforts to specific page regions.

To implement zone analysis:

```python
def analyze_zones(diff_image, num_zones=10):
    """Analyze which horizontal zones have the most differences."""
    width, height = diff_image.size
    zone_height = height // num_zones
    zones = []

    for i in range(num_zones):
        y_start = i * zone_height
        y_end = min((i + 1) * zone_height, height)
        zone = diff_image.crop((0, y_start, width, y_end))
        pixels = list(zone.getdata())
        total = len(pixels)
        diff_count = sum(1 for p in pixels if any(c > 30 for c in p))
        similarity = (1 - diff_count / total) * 100 if total > 0 else 100
        zones.append({
            "zone": i + 1,
            "y_range": f"{y_start}-{y_end}",
            "similarity": round(similarity, 2),
            "diff_pixels": diff_count
        })

    return zones
```

### Stage 5: Generate Report

The script produces a JSON report saved to the output directory:

```json
{
  "timestamp": "2026-03-29 14:30:00",
  "average_similarity": 97.5,
  "passing": 10,
  "warnings": 2,
  "failing": 1,
  "results": [
    {
      "page": "/",
      "similarity": 99.1,
      "rms_error": 3.2,
      "diff_pixels": 1847,
      "total_pixels": 2073600,
      "zones": [...]
    }
  ]
}
```

Present the results to the user with a clear summary: average score, number of passing/warning/failing pages, and the specific pages that need attention sorted by similarity (worst first).

## Benchmark Targets

| Clone Type | Target | Rationale |
|------------|--------|-----------|
| Static clone (HTML/CSS only) | >= 99% | Same HTML, same CSS — only antialiasing and font rendering should differ |
| Framework template (React/Next.js) | >= 98% | Minor differences from JSX rendering, component boundaries, CSS-in-JS hydration |

Pages below the target should be investigated. Pages below 90% almost always indicate a missing asset, broken CSS reference, or stripped script that was actually needed for layout.

## Interpreting Common Gaps

Understanding what causes similarity gaps is essential for efficient debugging. Here are the most common causes ranked by frequency:

### Font Rendering (1-3% impact)
Different font files or missing fonts cause text to render with different metrics (width, height, spacing). This is the most common source of small gaps. Check that all Google Fonts and custom fonts were captured during the clone step. System font fallbacks have different metrics that cascade into layout shifts.

### Missing CSS (5-20% impact)
If a CSS file was not captured or its URL was not rewritten correctly, entire sections lose styling. Check the browser console for 404 errors on `.css` files. Verify that `<link rel="stylesheet">` tags point to files that exist locally.

### Missing Images (2-10% impact)
Images that failed to download or whose `src` was not rewritten show as broken image icons or blank spaces. Check for images loaded via CSS `background-image` (not captured by HTML attribute rewriting) and images loaded by JavaScript after page load.

### Layout Shifts (3-15% impact)
Differences in element positioning caused by:
- Missing fonts changing text dimensions and line breaks
- CSS grid/flex items wrapping differently due to missing styles
- Responsive images at wrong dimensions
- Removed scripts that controlled layout (sliders, masonry grids)

### Dynamic Content (1-5% impact)
Content that changes between screenshots of the original site:
- Timestamps, counters, "posted X minutes ago"
- Rotating testimonials or hero images
- A/B test variants
- Cookie consent banners (present on first visit, absent on subsequent)

Dynamic content differences are not bugs — they are expected. If QA scores fluctuate between runs without any code changes, dynamic content is likely the cause.

### CSS Animations (1-2% impact)
Animations captured at different frames produce pixel differences. Adding a longer wait time (2-3 seconds) after page load helps animations reach their final state. For CSS transitions triggered by scroll or hover, they may never reach the same state in both screenshots.

## Running QA Manually

To run QA on specific pages instead of the full site:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/qa_compare.py / /about /pricing
```

Pass URL paths as arguments to compare only those pages. This is faster for iterating on fixes to specific problem pages.

## Port Management

Always use unique ports per server to avoid conflicts:
- Static clones: ports 8000-8099
- Framework dev servers: ports 3000-3099
- Framework production builds: ports 8100-8199

Check for occupied ports before starting a server:

```bash
lsof -i :{port} 2>/dev/null
```

Kill stale servers from previous QA runs to free ports.

## Integration with the Clone Pipeline

When invoked from the `/clone` skill (Step 7), the QA results determine the pipeline flow:
- Score >= 98%: pipeline proceeds to framework conversion
- Score < 98%: pipeline enters the fix loop (up to `max_fix_iterations` automated rounds — read from clone-config.json per `docs/clone-config.md`; default 5)
- Score < 80% after fixes: pipeline pauses for human review

The QA script's exit code and JSON report are consumed by the clone pipeline to make these routing decisions automatically.

TODO: port the explicit convergence-loop recipe from `/diff-flow-match` Stage 6 into this skill so the fix rounds are structured identically (ticket list → scoped fixer subagent → rebuild → re-QA). Currently each round is free-form; Stage 6 in diff-flow-match is the reference implementation.
