---
name: clone
description: This skill should be used when the user asks to "clone a website", "clone this site", "copy a website", "scrape and clone", "download a website", or provides a URL and wants a complete local copy. Guides the user through a systematic cloning pipeline with auto-detection, QA verification, and framework conversion.
version: 0.1.0
---

# Website Cloning Pipeline

Guided pipeline that discovers, clones, fixes, QA-verifies, and optionally converts any website into a local, editable project. The pipeline handles everything from initial URL acceptance through framework conversion, with automated quality gates at each stage.

## Pipeline Overview

The cloning pipeline follows thirteen sequential steps. Each step produces artifacts consumed by subsequent steps. The pipeline is designed to be resumed at any step if interrupted.

```
[Step 0: Load config] -> URL -> Detect -> Confirm -> [Auth] -> Clone -> Fix -> QA -> [Fix Loop] -> Convert -> Analyze -> Document
```

## Step 0: Load clone-config.json

Before any pipeline work, resolve the effective `clone-config.json` per `docs/clone-config.md`. This file is the framework's policy source of truth. The fields this skill reads directly:

- `auto_commit` — if true, commit automatically between pipeline phases (Clone, Convert, Analyze each produce a commit). Default true.
- `allow_plan_mode` — forwarded into any subagent dispatched from this pipeline. If false (default), subagents must not `EnterPlanMode`.
- `auto_push_end` — if true, push to remote at end of Step 13. Default false — push is a conscious act.
- `commit_author_email` — email used in automated commits.

Resolve once at pipeline start:

```bash
CLONE_CONFIG=$(
  for candidate in \
    "clones/${DOMAIN}/clone-config.json" \
    "${HOME}/.claude/clone-config.json" \
    "${CLAUDE_PLUGIN_ROOT}/.claude-plugin/clone-config.default.json"; do
    [ -f "$candidate" ] && cat "$candidate" && break
  done
)
```

Do not ask the user about these values. The config is the contract. Only ask if it's missing or unparseable.

## Step 1: Accept Target URL

Accept the target URL from the user. Normalize it to include the protocol (add `https://` if missing). Validate that the URL is reachable by making a HEAD request. Extract the domain name for use as the project directory name.

Store the target URL and domain in a project context object that persists through all subsequent steps.

## Step 2: Auto-Detect Site Characteristics

Run a Playwright crawl to discover the site's properties before committing to a cloning strategy. Use headless Playwright (Python async API, not Playwright MCP) to:

1. Navigate to the homepage and wait for `networkidle`.
2. Detect the framework by inspecting page source and DOM:
   - React: look for `__REACT_DEVTOOLS_GLOBAL_HOOK__`, `data-reactroot`, `_reactRootContainer`
   - Next.js: look for `__NEXT_DATA__`, `_next/` asset paths
   - Vue: look for `__VUE__`, `data-v-` attributes
   - Nuxt: look for `__NUXT__`, `_nuxt/` paths
   - Static: none of the above detected
3. Attempt to fetch `/sitemap.xml` and `/sitemap_index.xml`. Parse all `<loc>` entries.
4. If no sitemap, crawl internal links from the homepage by extracting all `<a href>` values that share the same domain. Follow links up to 2 levels deep to build a comprehensive URL list.
5. Detect auth-required pages by scanning for:
   - Login forms (`input[type="password"]`, forms with `action` containing "login" or "auth")
   - Dashboard routes (`/dashboard`, `/admin`, `/account`, `/settings`)
   - 401/403 redirect patterns (pages that redirect to a login URL)
   - OAuth buttons (links containing "oauth", "sso", "authorize")
6. Count total discovered pages and categorize them as public vs. auth-required.

Save the URL list to `{domain}_urls.json` in the project directory.

### Detection Heuristics for Common Frameworks

When auto-detection is ambiguous, use these secondary signals:
- **Next.js vs plain React:** Next.js always has `/_next/data/` requests and `__NEXT_DATA__` JSON in a script tag. Plain React (Create React App or Vite) has a single `<div id="root">` with no server-rendered content inside it.
- **Nuxt vs plain Vue:** Nuxt injects `window.__NUXT__` and serves assets from `/_nuxt/`. Plain Vue apps mount via `createApp` without framework-specific globals.
- **Static site generators (Hugo, Jekyll, Gatsby):** These produce plain HTML with no hydration scripts. Gatsby is an exception — it hydrates like React but ships pre-rendered HTML, identifiable by `gatsby-` prefixed class names and `window.___gatsby`.
- **Webflow / Squarespace / Wix:** Identifiable by platform-specific class naming (`w-`, `sqsp-`, `wix-`) and CDN domains. These require special handling because they inject platform scripts for animations and interactions.

## Step 3: Present Findings and Confirm

Present the detection results to the user as a structured question:

> Found X pages on {domain} ({framework}). Detected Y authenticated pages ({list of auth paths}).
> Options:
> (A) Clone everything — login required
> (B) Public pages only
> (C) Public now, add auth later

Wait for the user's choice before proceeding. If no auth-required pages were detected, skip directly to Step 5 after confirming the page count.

## Step 4: Authentication (If Required)

If the user chose option A or is adding auth later (option C, second pass):

1. Launch a **visible** (non-headless) Playwright browser so the user can see it.
2. Navigate to the site's login page.
3. Ask the user to log in manually in the visible browser window.
4. Once the user confirms login is complete, capture all cookies from the browser context.
5. Save cookies to `{domain}_cookies.json` for reuse in the clone step.
6. Close the visible browser.

This approach handles any auth method (OAuth, MFA, SSO, CAPTCHA) because the user performs the login themselves.

## Step 5: Run Clone Script

Execute the clone script to visit every URL and capture all resources:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/clone_site.py
```

Before running, update the script's configuration variables to match the current project:
- `BASE` = the target URL
- `PROJECT_DIR` = the output directory path
- `URLS_FILE` = path to the URL list from Step 2
- `COOKIES_FILE` = path to cookies from Step 4 (if auth was used)
- `DELAY` = seconds between page loads (start with 1.2, increase if rate-limited)

The script performs these operations for each URL:
- `page.goto(url, wait_until="networkidle")` to load the fully rendered page
- `page.on("response")` intercepts all network responses to capture CSS, JS, images, fonts, and JSON
- Scrolls the full page height to trigger lazy-loaded images and IntersectionObserver callbacks
- Calls `page.content()` to get the final rendered HTML
- Rewrites URLs in HTML from absolute to relative paths
- Saves HTML files preserving the URL path structure
- Downloads any missing assets referenced in HTML but not intercepted

Output lands in `projects/{domain}_clone/` with a `clone_report.json` summarizing pages cloned, resources saved, and any errors.

### Rate Limiting and Politeness

Respect the target site's rate limits. If the clone script encounters 429 (Too Many Requests) responses, increase the `DELAY` variable. Start with 1.2 seconds between pages and increase to 2-3 seconds if needed. For sites behind Cloudflare or similar WAFs, a delay of 2+ seconds with randomized jitter (add 0-500ms random) helps avoid detection. If the site has a `robots.txt` with crawl-delay directives, honor them.

### Handling Clone Errors

After the script completes, review `clone_report.json` for errors. Common error types:
- **Timeout errors:** Pages that took longer than 30 seconds to load. Re-run just those pages with a longer timeout.
- **404 errors:** Pages that no longer exist on the live site (stale sitemap entries). Remove them from the URL list.
- **Navigation errors:** Pages behind client-side routing that require JavaScript to load. These are resolved by the SPA script stripping in Step 6.

## Step 6: Auto-Fix HTML

After cloning, apply automatic fixes to the static HTML. These fixes are essential for the clone to render correctly when served locally. The three critical fixes are:

1. **Strip SPA module scripts** — Remove `<script type="module">` tags and SPA entry points (React hydration, Next.js data scripts, Vue app mounting). These scripts attempt to take over the DOM and break the static HTML. See `${CLAUDE_PLUGIN_ROOT}/skills/clone/references/known-fixes.md` for the full list of patterns to strip.

2. **Fix nested `<a>` tags** — Browsers auto-close `<a>` tags when they encounter a nested `<a>`, breaking link structure and layout. Convert the outer `<a>` to a `<div>` with `cursor: pointer` styling and an `onclick` handler for navigation. Detailed patterns in the references file.

3. **Rewrite URLs to relative** — Convert all absolute URLs pointing to the original domain into relative paths. This includes `href`, `src`, `srcset` attributes, CSS `url()` references, and inline styles. Calculate the correct `../` prefix depth based on the HTML file's position in the directory tree.

Also strip analytics scripts (Google Analytics, Ahrefs, Hotjar, Mixpanel) and tracking pixels.

## Step 7: Auto-Trigger QA

Invoke the `/qa` skill to perform automated screenshot comparison between the original site and the local clone. Start a local server to serve the clone:

```bash
cd projects/{domain}_clone && python3 serve.py
```

Then run the QA comparison script:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/qa_compare.py
```

The QA skill takes viewport screenshots (1920x1080) of every page on both the original and clone, performs pixel comparison with a 30 RGB threshold, and generates per-page similarity percentages and diff images.

## Step 8: Fix Loop (If QA < 98%)

If the average QA score is below 98%, enter an automated fix loop:

**Round 1:** Analyze the diff images and zone analysis from the QA report. Identify the specific causes of each difference (missing fonts, CSS issues, stripped scripts that were needed, layout shifts). Apply targeted fixes to the HTML and CSS files. Re-run QA.

**Round 2:** If still below 98% after Round 1, apply a second round of fixes. Focus on edge cases: viewport-specific rendering, font fallback chains, animation states captured mid-transition, cookie consent banners.

**If still failing after 2 rounds:** Do not continue fixing automatically. Instead, perform a detailed code review of the worst-performing pages. Present the analysis to the user with:
- Which pages are failing and by how much
- What specific visual differences remain
- Suggested manual fixes
- Whether the remaining gaps are acceptable (some differences like cookie banners or live data are expected)

Let the user decide whether to accept the current quality, continue fixing manually, or re-clone with different settings.

## Step 9: Framework Selection (If QA >= 98%)

Once QA passes, ask the user which framework to convert to:

> QA passed at {score}%. Which framework should the template use?
> (A) Vite + React
> (B) Next.js
> (C) Keep as static HTML
> (D) Other (specify)

Wait for the user's choice.

## Step 10: Trigger Conversion

Invoke the `/convert` skill with the user's chosen framework. Pass the static clone directory path and the target framework as parameters. The convert skill handles HTML-to-JSX transformation, component extraction, CSS preservation, and project scaffolding.

## Step 11: Trigger Analysis

Invoke the `/analyze` skill to generate an `ANALYSIS.md` file documenting:
- Site architecture and page hierarchy
- Component patterns discovered (headers, footers, cards, forms)
- CSS methodology used (Tailwind, CSS modules, styled-components, plain CSS)
- Color palette and typography
- Responsive breakpoints
- Third-party integrations detected

## Step 12: Update Learnings

Append new patterns discovered during this clone to `${CLAUDE_PLUGIN_ROOT}/docs/learnings.md`. Document:
- Site-specific quirks encountered and how they were resolved
- New fix patterns that should be added to the known-fixes reference
- Performance observations (clone speed, QA accuracy)
- Framework detection accuracy

This creates institutional knowledge that improves future cloning operations.

## Step 13: Update Benchmarks

Append an entry to `${CLAUDE_PLUGIN_ROOT}/benchmarks/benchmark-log.json` with:
- Domain and timestamp
- Total pages and resources cloned
- QA scores (per-page and average)
- Clone duration
- Fix rounds required
- Final framework chosen

This enables tracking improvement over time and comparing different site types. Over time, this log reveals which site types (static, SPA, Webflow, custom) consistently achieve high QA scores and which require more manual intervention, allowing prioritization of pipeline improvements.

## Error Recovery and Edge Cases

Handle these common edge cases during the pipeline:
- **Sites behind Cloudflare challenge pages:** If the initial crawl returns a challenge page instead of content, fall back to the visible browser approach from Step 4 and let the user solve the challenge before proceeding.
- **Sites with infinite scroll:** Detect pages that load content dynamically on scroll by monitoring DOM changes during the scroll step. Set a maximum scroll depth (10,000px) to avoid infinite loops.
- **Password-protected staging sites:** If the user provides HTTP Basic Auth credentials, pass them via the Playwright context's `httpCredentials` option rather than the cookie-based auth flow.
- **Very large sites (500+ pages):** Warn the user about estimated clone time and disk space. Offer to clone a subset (e.g., top-level pages only) as a first pass.

## Resuming an Interrupted Pipeline

If the pipeline is interrupted at any step, it can be resumed by:
1. Checking which artifacts already exist (URL list, cookies, clone directory, QA report)
2. Skipping completed steps
3. Resuming from the first incomplete step

Always check for existing project directories before starting a new clone of the same domain.

## Reference Files

For detailed technical documentation on specific fixes and patterns, consult:
- `${CLAUDE_PLUGIN_ROOT}/skills/clone/references/known-fixes.md` — comprehensive catalog of HTML fixes, SPA stripping rules, URL rewriting patterns, and edge cases
- `${CLAUDE_PLUGIN_ROOT}/docs/architecture.md` — overall pipeline architecture and stage relationships
- `${CLAUDE_PLUGIN_ROOT}/scripts/clone_site.py` — the clone script source (read before modifying configuration)
- `${CLAUDE_PLUGIN_ROOT}/scripts/qa_compare.py` — the QA comparison script source
