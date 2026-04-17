# Cloning Pipeline Architecture

## Pipeline Stages

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│ Discover │───▶│  Clone   │───▶│   Fix    │───▶│    QA    │───▶│ Convert  │
│  URLs    │    │  Pages   │    │  HTML    │    │ Compare  │    │ to React │
└──────────┘    └──────────┘    └──────────┘    └──────────┘    └──────────┘
  Playwright      Playwright     Strip SPA JS    Screenshot       HTML→JSX
  + sitemap       + intercept    Fix nested <a>  pixel diff       (TODO)
                  all resources  Rewrite URLs    per page
```

## Stage Details

### 1. Discover URLs
- **Input:** Target URL
- **Tool:** Playwright `browser_evaluate` to extract all `<a href>` from homepage
- **Also:** Fetch sitemap.xml if available
- **Output:** `{domain}_urls.json` — deduplicated, sorted URL list

### 2. Clone Pages
- **Input:** URL list
- **Tool:** `clone_{site}.py` using Playwright async API
- **Method:** For each URL:
  - `page.goto(url, wait_until="networkidle")`
  - `page.on("response")` captures CSS, JS, images, fonts, API data
  - Scroll full page to trigger lazy-loaded images
  - `page.content()` saves rendered HTML
- **Auth:** Manual login via visible browser, cookies saved for reuse
- **Output:** `static-clone/` directory with all HTML + assets

### 3. Fix HTML
- Strip `<script type="module">` (SPA entry points that override SSR HTML)
- Fix nested `<a>` tags (convert outer to `<div>` with onclick)
- Rewrite URLs from absolute to relative (for local serving)
- Strip analytics (GA4, Ahrefs)
- **Output:** Fixed static clone that serves correctly offline

### 4. QA Compare
- **Tool:** `qa_compare.py`
- **Method:** Screenshot each page on both original and clone at 1920x1080
- **Metrics:**
  - Per-pixel difference with threshold (>30 RGB per channel)
  - Similarity percentage per page
  - Diff image with red highlights on differences
  - Zone analysis (divide page into 10-20 horizontal bands)
- **Target:** ≥99% for static clone, ≥97% for framework template
- **Output:** `qa-reports/` with screenshots, diff images, JSON results

### 5. Convert to Framework (TODO — the HTML-to-React converter)
- **Input:** Static clone directory
- **Output:** Editable React/Next.js project
- **Method (planned):**
  1. Keep original CSS verbatim (don't recreate with Tailwind)
  2. Parse HTML → detect repeated patterns → extract React components
  3. Convert HTML attributes to JSX (class→className, etc.)
  4. Extract dynamic content into JSON data files
  5. Generate React Router config from URL structure
  6. Wire up components into pages

## The 95% Wall

Building React from visual reference hits ~95% max. Breaking through requires:

| Approach | Ceiling | Why |
|----------|---------|-----|
| Write new JSX that "looks like" original | ~95% | Font rendering, padding, shadow differences |
| Convert original HTML to JSX + keep original CSS | ~99% | Same code, just restructured |
| Use original Vite chunks directly | ~100% | But not editable |

The HTML-to-React converter is the key tool needed.

## Benchmarks Tracking

Each clone tracks:
- **Revision log** — what changed, why, what improved
- **QA scores per revision** — similarity % per page
- **Gap analysis** — what specific zones differ and why
- **Conclusions** — what we learned for the framework
