---
name: improve
description: This skill should be used when the user asks to "fix the clone", "improve QA score", "fix visual differences", "close the gap", "make it match better", or when the QA comparison shows the clone is below the benchmark target. Iterates on visual differences until the benchmark is met.
---

# Iterative Gap Fixing

## Overview

Diagnose and fix visual differences between a clone and the original website by iterating through a structured fix-verify loop until the benchmark target is met. Each iteration identifies the highest-impact failing zones, applies targeted fixes, and re-runs QA on affected pages only. The goal is to close the gap between the clone's current score and the target fidelity (99%+ for static clones, 97%+ for framework templates).

## When to Use

- QA comparison report shows pages below the benchmark target
- User reports that the clone "doesn't look right" or "something is off"
- After initial cloning, before declaring the clone complete
- After converting to a framework template, to verify fidelity held
- When specific visual elements are noticeably wrong (fonts, colors, layout)

## Improvement Process

### Step 1: Read the QA Report

Locate the most recent QA report for the clone:
- Check `clones/{domain}/qa-reports/` for comparison results
- Read per-page scores (overall fidelity percentage per page)
- Examine zone analysis data (header, hero, content, sidebar, footer scores)
- Review diff images showing pixel-level differences

If no QA report exists, run the QA comparison first using the `/qa` skill or the QA compare tool at `${CLAUDE_PLUGIN_ROOT}/scripts/qa_compare.py`.

Sort pages by score ascending — fix the worst pages first for maximum impact.

### Step 2: Identify Top 3 Failing Zones

For each failing page, break the viewport into zones and rank by impact:

| Zone | Viewport Area | Common Failure Causes |
|------|---------------|----------------------|
| Header/Nav | Top 80-120px | Missing logo, wrong nav links, missing hamburger menu |
| Hero | First viewport below nav | Wrong background image, missing gradient, font size mismatch |
| Content Body | Main content area | Missing images, wrong grid layout, text overflow differences |
| Sidebar | Left/right column | Missing widgets, wrong width, collapsed on desktop |
| Cards/Grid | Repeated element sections | Inconsistent card heights, missing shadows, wrong gap spacing |
| Footer | Bottom section | Missing columns, wrong background color, missing social icons |

Focus on the 3 zones with the largest pixel difference area. Fixing a hero image that covers 40% of the viewport has more impact than fixing a 20px footer margin.

### Step 3: Diagnose Each Failing Zone

For each of the top 3 failing zones, determine the root cause category:

**Missing Asset (image, font, icon not downloaded):**
- Symptoms: Blank space where image should be, wrong font rendering, missing icon
- Diagnosis: Check if the referenced file exists in the clone's asset directory. Inspect `<img>` src paths, `@font-face` declarations, SVG references.
- Verify: `ls` the expected asset path. Check for 404-equivalent missing files.

**CSS Difference (wrong class, missing style, specificity issue):**
- Symptoms: Wrong colors, spacing, borders, shadows, or sizing
- Diagnosis: Compare the clone's CSS class usage against the original HTML. Check for missing classes, typos in class names, or styles overridden by a different cascade order.
- Verify: Inspect the specific CSS rule that should apply and confirm it exists in the clone's stylesheet.

**HTML Structure Issue (broken nesting, missing element, wrong attribute):**
- Symptoms: Layout completely different, elements in wrong order, missing sections
- Diagnosis: Diff the clone's HTML against the original source. Look for missing `<div>` wrappers, incorrectly closed tags, stripped elements.
- Verify: Count child elements in the failing zone and compare to original.

**Layout Shift (viewport behavior, responsive breakpoint issue):**
- Symptoms: Layout correct at one width but broken at another, elements overlapping
- Diagnosis: Check media queries in the CSS. Verify the viewport meta tag matches. Look for fixed-width containers that should be responsive.
- Verify: Test at multiple viewport widths (375px, 768px, 1024px, 1440px).

**Font Rendering (wrong font loaded, weight mismatch):**
- Symptoms: Text looks "close but not right", wrong boldness, different letter spacing
- Diagnosis: Check `@font-face` declarations. Verify font files are present and correctly referenced. Compare font-weight, font-style, and font-display values.
- Verify: Inspect computed font-family in the browser to confirm which font is actually rendering.

### Step 4: Apply Targeted Fixes

For each diagnosed issue, apply the minimal fix that addresses the root cause:

**Missing Asset Fixes:**
- Re-download the asset from the original URL
- Fix broken file paths (relative vs absolute, case sensitivity)
- For fonts: add the correct `@font-face` declaration or CDN link
- For images: ensure the correct format and dimensions

**CSS Fixes:**
- Add missing classes to HTML elements
- Fix class name typos
- Restore missing CSS rules
- Fix import order if cascade specificity is wrong
- Do NOT rewrite CSS — patch the specific rule

**HTML Structure Fixes:**
- Restore missing wrapper elements
- Fix tag nesting (especially `<a>` inside `<a>`, `<p>` inside `<p>`)
- Add missing attributes (`alt`, `aria-*`, `data-*`)
- Convert nested `<a>` tags: change the outer `<a>` to `<div>` with an `onclick` handler

**Layout Fixes:**
- Restore missing media queries
- Fix container width values
- Add missing `box-sizing: border-box` declarations
- Restore viewport meta tag if missing or altered

**Font Fixes:**
- Download missing font files from Google Fonts or the original CDN
- Correct `font-weight` values (400 for regular, 500 for medium, 600 for semibold, 700 for bold)
- Match `font-display` strategy (usually `swap`)

### Step 5: Re-run QA on Affected Pages

After applying fixes, re-run the QA comparison only on the pages that were modified. This is faster than a full-site comparison and provides immediate feedback.

Use the QA compare tool: `python ${CLAUDE_PLUGIN_ROOT}/scripts/qa_compare.py --pages <affected-urls>`

Compare the new score against the previous score for each page. Record the delta.

### Step 6: Check Benchmark

Compare current scores against targets:

| Clone Type | Target | Action if Below |
|------------|--------|-----------------|
| Static clone | 99%+ | Continue fixing |
| Framework template | 97%+ | Continue fixing |
| Below 95% | Any | Investigate structural issues — likely missing CSS file or broken HTML |

If the target is met, log the final scores to `${CLAUDE_PLUGIN_ROOT}/benchmarks/benchmark-log.json` and mark the clone as complete.

## Auto-Improvement Loop

The improvement process runs in an automated loop with guardrails:

**Round 1 (Automatic):**
1. Read QA report
2. Identify top 3 failing zones
3. Diagnose and fix each
4. Re-run QA on affected pages

**Round 2 (Automatic):**
1. Read updated QA report
2. Check if benchmark met — if yes, stop
3. Identify remaining top 3 failing zones
4. Diagnose and fix each
5. Re-run QA on affected pages

**Round 3+ (Manual Decision Required):**
If still below benchmark after 2 automatic rounds:
1. Pause the loop
2. Perform a detailed code review analysis of the remaining gaps
3. Categorize remaining issues by difficulty (quick fix vs structural problem)
4. Present findings to the user with options:
   - Continue with targeted fixes (list what would be attempted)
   - Accept current score as sufficient
   - Re-clone specific pages with different strategy
   - Investigate if the original site has changed since cloning

This prevents infinite loops on issues that require human judgment (e.g., dynamic content that differs between captures, A/B test variations on the original site, or anti-bot measures that served different content).

## Common Fixes Reference

Quick lookup for frequently encountered issues:

| Problem | Fix |
|---------|-----|
| SPA shows blank page | Strip `<script type="module">` tags so static HTML is visible |
| Nested `<a>` tags break layout | Convert outer `<a>` to `<div>` with `onclick` navigation |
| Google Fonts not loading | Add CDN `<link>` tag or capture font files during Playwright crawl |
| Images show broken icon | Re-download from original URL, check path case sensitivity |
| Grid layout collapsed | Verify CSS Grid classes match original, check for missing `display: grid` |
| Cards different heights | Add `min-height` or check for missing content that equalized heights |
| Wrong background color | Check for dark mode class applied incorrectly, verify CSS custom property values |
| Sticky nav not working | Restore `position: sticky` or `fixed` and `z-index` values |
| Animations missing | Restore `@keyframes` declarations and `animation` properties |
| SVGs not rendering | Check for missing `xmlns` attribute, verify `viewBox` values |
| Favicon missing | Copy `favicon.ico` and any `apple-touch-icon` files |
| Social meta images broken | Fix `og:image` path to use absolute URL |

## Updating Learnings

After each improvement cycle, update `${CLAUDE_PLUGIN_ROOT}/docs/learnings.md` with any new patterns discovered:

- New site-specific quirks (e.g., "Site X uses CSS-in-JS that requires special handling")
- New fix patterns not in the common fixes table above
- Failure modes that required manual intervention and why
- Time estimates for common fix categories

## Updating Benchmarks

After successful improvement, log results to `${CLAUDE_PLUGIN_ROOT}/benchmarks/benchmark-log.json`:

```json
{
  "domain": "example.com",
  "date": "2026-03-29",
  "type": "static-clone",
  "pages_tested": 12,
  "scores": {
    "average": 99.2,
    "min": 98.1,
    "max": 99.9
  },
  "rounds_needed": 2,
  "issues_fixed": [
    "missing hero image",
    "wrong nav font-weight",
    "footer grid collapsed"
  ]
}
```

This historical data informs future cloning strategy — sites with repeated issues on certain zones indicate areas where the cloning tool itself may need improvement.

## Common Mistakes

- **Fixing symptoms instead of root cause**: A wrong color might be caused by a missing CSS file import, not a wrong hex value. Always trace to the root cause before patching.
- **Editing the CSS instead of the HTML**: If an element has the wrong style, check whether the correct class is applied before modifying CSS rules. The CSS is usually correct — the class assignment is wrong.
- **Running full-site QA after every fix**: Re-run only on affected pages. Full-site QA is for milestone checks, not iteration loops.
- **Continuing past 3 rounds without user input**: Diminishing returns kick in fast. If 2 rounds did not reach the target, the remaining issues likely need a different approach, not more of the same.
- **Ignoring responsive breakpoints**: A fix at desktop width can break mobile layout. Always verify at least 2 viewport widths after structural changes.
