# IllyCloneFramework — Claude Code Plugin Design Spec

## Problem
We have Python scripts that clone websites at 99.9% static fidelity, but converting clones into editable projects caps at ~95%. The tools are manual, site-specific, and don't learn from past runs. We need a guided, self-improving system that hits 98%+ on any site and helps us build new products from clones.

## Solution
A Claude Code plugin with skills that guide the user through a systematic cloning pipeline. Each clone produces documented learnings that improve the next clone. Once benchmarks are consistently met (98%+), the framework is stable and becomes a production tool.

## Two Phases
1. **R&D phase (now):** Build and test each skill iteratively. Improve until example.com + 2-3 other sites consistently hit 98%+.
2. **Production phase (later):** Skills are stable. User types `/clone https://example.com` and the pipeline runs with minimal intervention.

---

## Project Structure

```
IllyCloneFramework/
├── plugin.json                     # Claude Code plugin manifest
├── CLAUDE.md                       # Auto-updated project context
├── skills/
│   ├── clone.md                    # /clone — full cloning pipeline (guided)
│   ├── qa.md                       # /qa — screenshot comparison loop
│   ├── convert.md                  # /convert — static HTML → editable framework
│   ├── analyze.md                  # /analyze — architecture + SEO analysis doc
│   └── improve.md                  # /improve — iterate on gaps until benchmark hit
├── agents/
│   ├── cloner.md                   # Autonomous cloning agent
│   ├── qa-reviewer.md              # Autonomous QA comparison agent
│   └── converter.md                # Autonomous HTML→framework converter
├── hooks/
│   └── post-clone-qa.md            # Auto-trigger QA after every clone completes
├── tools/                          # Python scripts invoked by skills
│   ├── clone_site.py               # Generalized Playwright cloner
│   └── qa_compare.py               # Generalized screenshot comparator
├── docs/
│   ├── architecture.md             # Pipeline design
│   └── learnings.md                # Auto-updated: patterns, gotchas, fixes per site
├── benchmarks/
│   └── benchmark-log.json          # Machine-readable: {site, scores[], dates[], pass/fail}
└── clones/                         # Output directory (one folder per cloned site)
    └── example.com/                  # First clone (R&D reference)
        ├── static-clone/           # 99.9% pixel-perfect HTML
        ├── react-template/         # Editable Vite+React project
        ├── qa-reports/             # Screenshots + diffs
        ├── revisions/              # Revision log with benchmarks
        └── ANALYSIS.md             # Architecture + SEO analysis
```

---

## Skill Designs

### `/clone` — Main Pipeline Skill

The entry point. Guides the user through the full cloning process.

**Flow:**

1. Ask: "What URL do you want to clone?"
2. **Auto-detect** site characteristics:
   - Crawl homepage, extract all URLs
   - Check for sitemap.xml
   - Detect framework (React/Next.js/Vue/static)
   - Detect auth requirements (login pages, /dashboard routes, 401 redirects, OAuth buttons)
3. **Present findings as a question:**
   - "Found 140 pages on example.com (Next.js SPA). Detected 3 authenticated pages (/dashboard, /dashboard/submit, /settings). What would you like to do?"
   - Options: (A) Clone everything — you'll need to log in (B) Public pages only (C) Public now, add auth later
4. If auth needed: open visible browser, ask user to log in, capture session
5. Clone all pages (Playwright, resource interception, lazy-load scrolling)
6. Auto-fix (strip SPA scripts, fix nested `<a>`, rewrite URLs)
7. Auto-trigger `/qa`
8. If QA < 98%: auto-trigger `/improve` → fix → re-QA loop
9. If QA ≥ 98%: present results, ask "Which framework do you want to convert to?"
   - Options: Vite+React, Next.js, Static HTML (keep as-is), Other
10. Trigger `/convert` with chosen framework
11. Trigger `/analyze`
12. Update `docs/learnings.md` with patterns discovered
13. Update `benchmarks/benchmark-log.json`
14. Summary: pages cloned, QA score, framework output, analysis doc

### `/qa` — Screenshot Comparison

Automated visual QA. Can be run standalone or triggered by `/clone`.

**Flow:**

1. Takes: original URL base + clone directory (or dev server URL)
2. Screenshots every page on both at 1920x1080 (headless Playwright)
3. Pixel comparison with 30-threshold (filters antialiasing noise)
4. Zone analysis (horizontal bands) to identify WHERE differences are
5. Generates diff images with red highlights
6. Outputs: per-page similarity %, average %, pass/fail against benchmark
7. If any page < benchmark: lists specific zones and likely causes

**Benchmark targets:**
- Static clone: ≥99%
- Framework template: ≥98%

### `/convert` — HTML → Editable Framework

Converts the static clone into an editable project.

**Key insight (from R&D):** Don't rebuild from visual reference (caps at 95%). Instead:
1. Keep the original CSS file verbatim
2. Parse clone HTML → detect repeated DOM patterns (nav, footer, cards)
3. Convert HTML to JSX (class→className, etc.)
4. Extract dynamic data into JSON
5. Generate routing from URL structure
6. Result: React project that uses the original CSS → 99%+ fidelity

**This is the tool that doesn't exist yet.** Building it is the main R&D task.

### `/analyze` — Architecture + SEO Analysis

Generates a comprehensive analysis document for the cloned site.

**Output (ANALYSIS.md):**
- Tech stack identification
- Database schema (inferred from API calls)
- SEO strategy (meta tags, sitemap, robots.txt, internal linking)
- Design system (colors, typography, spacing, shadows)
- Component inventory
- Content strategy
- Conversion flows

### `/improve` — Iterate Until Benchmark

Runs when QA score is below benchmark. Automated fix loop.

**Flow:**
1. Read QA report (which zones differ, by how much)
2. For each failing zone: diagnose likely cause (missing asset, wrong CSS, broken HTML structure)
3. Apply fix
4. Re-run `/qa` on affected pages
5. Repeat until benchmark met or max iterations (5)
6. If stuck: present remaining gaps to user for manual decision

---

## Hooks

### `post-clone-qa`
Trigger: After any clone operation completes
Action: Auto-run `/qa` and present results

---

## Data Flow

```
User: "/clone https://example.com"
  ↓
/clone skill (guided)
  ├── Detect site → present findings → user chooses options
  ├── Clone pages → tools/clone_site.py
  ├── Auto-fix HTML
  ├── /qa → tools/qa_compare.py → benchmark check
  │   └── If < 98%: /improve → fix → /qa (loop)
  ├── /convert → HTML-to-React converter
  ├── /analyze → ANALYSIS.md
  └── Update learnings + benchmarks
  ↓
Output: clones/{domain}/ with static-clone, react-template, QA reports, analysis
```

---

## Learnings System

`docs/learnings.md` is auto-updated after each clone:

```markdown
## Pattern: SPA Script Stripping
**Discovered:** example.com (2026-03-29)
**Problem:** SPA JavaScript overrides SSR HTML, shows 404 on static serve
**Fix:** Strip <script type="module"> and main entry scripts
**Applies to:** All React/Vue/Next.js SPAs

## Pattern: Nested <a> Tags
**Discovered:** example.com (2026-03-29)
**Problem:** Browsers auto-close outer <a> when inner <a> found, breaking card layouts
**Fix:** Convert outer <a> to <div> with onclick
**Applies to:** Any site with clickable card wrappers containing links
```

Each pattern becomes a rule the `/clone` skill checks automatically on future sites.

---

## Benchmark Tracking

`benchmarks/benchmark-log.json`:
```json
{
  "sites": [
    {
      "domain": "example.com",
      "date": "2026-03-29",
      "static_clone": { "pages": 115, "avg_similarity": 99.9, "pass": true },
      "react_template": { "pages": 10, "avg_similarity": 94.8, "pass": false },
      "revisions": 4,
      "learnings": ["spa-script-stripping", "nested-a-fix"]
    }
  ],
  "benchmark": { "static": 99, "template": 98 }
}
```

---

## Success Criteria (R&D Phase Complete When)

1. `/clone` produces 99%+ static clone on 3+ different site types (SPA, static, SSR)
2. `/convert` produces 98%+ editable React project on 3+ sites
3. Full pipeline runs with ≤2 manual interventions per site
4. `docs/learnings.md` has patterns covering major site architectures
5. All skills are documented and can be used by a fresh Claude session via CLAUDE.md
