---
name: convert
description: This skill should be used when the user asks to "convert the clone to React", "make it editable", "create a React project from the clone", "convert to Next.js", "restructure into a framework", or wants to turn a static HTML clone into an editable project. Currently in R&D — the HTML-to-JSX converter is being developed.
---

# HTML to Framework Converter

## Overview

Convert a static HTML clone into an editable framework project (React, Next.js, Vue, etc.) while preserving the original styling with maximum fidelity. The core principle: keep the original CSS verbatim and convert the HTML structure to components, rather than recreating styles from scratch.

**Current Status: R&D Phase.** The automated HTML-to-JSX converter pipeline is not yet built. This skill documents the planned approach and provides a manual workaround for immediate needs.

## The 95% Wall

When converting a static clone to a framework project, there is a well-known fidelity ceiling at approximately 95%. This happens because of how the conversion is typically attempted:

**The wrong approach (rebuilding from visual reference):**
1. Open the original site side-by-side
2. Recreate each component from scratch using Tailwind or custom CSS
3. Eyeball-match colors, spacing, fonts, layout
4. Result: looks close but never exact — shadows are slightly off, spacing differs by 1-2px, font weights mismatch, hover states are forgotten, border-radius values are guessed

This ceiling exists because CSS is extremely precise. A `box-shadow: 0 1px 3px 0 rgb(0 0 0 / 0.1), 0 1px 2px -1px rgb(0 0 0 / 0.1)` cannot be reliably recreated by visual inspection. Multiplied across hundreds of properties on dozens of components, these micro-differences accumulate into a noticeable gap.

**The correct approach (converting original HTML + keeping original CSS):**
1. Take the clone's static HTML and CSS files as-is
2. Parse the HTML into a component tree
3. Convert HTML attributes to JSX syntax
4. Keep the original CSS file completely untouched
5. Import the original CSS into the framework project
6. Result: pixel-perfect because the exact same styles are used

The CSS file IS the design system. Recreating it is unnecessary work that introduces error. The conversion challenge is purely structural (HTML to JSX), not visual (CSS to Tailwind).

## Planned Converter Pipeline

When the automated converter is built, it will follow this sequence:

### Phase 1: HTML Analysis and Pattern Detection

Scan the clone's static HTML files to detect repeated DOM patterns:

- **Navigation**: `<nav>`, `<header>` elements, logo + menu link patterns
- **Footer**: `<footer>` elements, column-based link lists, copyright patterns
- **Cards**: Repeated sibling elements with identical class structures
- **Hero sections**: Large heading + subtext + CTA button patterns
- **Forms**: `<form>` elements with labeled inputs
- **Lists**: `<ul>`/`<ol>` with repeated `<li>` structures

Group pages by shared patterns to identify which components are reused across the site.

### Phase 2: HTML-to-JSX Attribute Conversion

Convert HTML attributes to valid JSX:

| HTML Attribute | JSX Equivalent |
|----------------|----------------|
| `class="..."` | `className="..."` |
| `for="..."` | `htmlFor="..."` |
| `style="color: red; font-size: 14px"` | `style={{ color: 'red', fontSize: '14px' }}` |
| `tabindex="0"` | `tabIndex={0}` |
| `onclick="..."` | `onClick={...}` |
| `colspan="2"` | `colSpan={2}` |
| `readonly` | `readOnly` |
| `autocomplete` | `autoComplete` |

Handle self-closing tags: `<img>`, `<br>`, `<hr>`, `<input>` must become `<img />`, `<br />`, etc.

Convert HTML comments `<!-- ... -->` to JSX comments `{/* ... */}`.

### Phase 3: CSS Preservation Strategy

The original CSS file stays verbatim. Do not convert to Tailwind, CSS modules, or styled-components unless explicitly requested.

- Copy the clone's CSS file(s) into the framework project's `public/` or `styles/` directory
- Import via `import '../styles/original.css'` in the root layout component
- Preserve all `@font-face` declarations, CSS custom properties (`--var-name`), and media queries
- If the clone uses multiple CSS files, maintain the same import order to preserve cascade specificity

### Phase 4: Dynamic Data Extraction

Identify content that should become dynamic:

- Repeated card content (titles, descriptions, images, links) into JSON arrays
- Navigation links into a config object
- Page metadata (title, description) into route-level data
- Feature lists, pricing tiers, testimonials into data files

Store extracted data in `src/data/` as JSON files. Components map over these arrays instead of containing hardcoded content.

### Phase 5: Routing Configuration

Generate route configuration from the clone's URL structure:

- Map each HTML file to a route path (e.g., `about.html` to `/about`)
- Detect nested URL patterns for dynamic routes (e.g., `/blog/post-1` to `/blog/[slug]`)
- Create a layout component wrapping shared elements (nav, footer)
- Set up framework-specific routing (React Router for Vite+React, file-based routing for Next.js)

### Phase 6: Component Assembly

Wire detected components into the page tree:

```
src/
  components/
    Navbar.jsx          # Shared navigation
    Footer.jsx          # Shared footer
    Card.jsx            # Reusable card component
    Hero.jsx            # Hero section
  pages/
    Home.jsx            # / route
    About.jsx           # /about route
    Blog.jsx            # /blog route
  data/
    navigation.json     # Nav links
    features.json       # Feature cards data
  styles/
    original.css        # Verbatim clone CSS
```

## Current Workaround (Manual Rebuild)

Until the automated converter is built, convert manually:

1. Create a new framework project (e.g., `npm create vite@latest -- --template react`)
2. Copy the clone's CSS file into the project
3. Import the CSS in the root component
4. Open the clone's HTML in a browser alongside the new project
5. Manually extract each section into a component, converting attributes to JSX
6. Use the original class names — they map to the copied CSS

This approach reaches approximately 95% fidelity. The remaining 5% gap comes from:
- Missed hover/focus/active states
- Forgotten SVG attributes that need JSX conversion
- Responsive behavior differences due to layout container changes
- Font loading timing differences

## Framework Selection

Before starting any conversion, ask the user which framework to target:

| Framework | Best For | Output Directory |
|-----------|----------|------------------|
| Vite + React | SPAs, dashboards, internal tools | `clones/{domain}/react-template/` |
| Next.js | Marketing sites, SEO-heavy, blogs | `clones/{domain}/next-template/` |
| Astro | Content sites, documentation, portfolios | `clones/{domain}/astro-template/` |
| Vue + Vite | Vue preference, similar to React use cases | `clones/{domain}/vue-template/` |

If the user does not specify, recommend based on the original site's architecture:
- SSR/SSG with heavy SEO needs: Next.js
- SPA with client-side routing: Vite + React
- Content-heavy with minimal interactivity: Astro

## Benchmark References

After conversion, compare the editable project against the original using the QA comparison tool. Log results to `${CLAUDE_PLUGIN_ROOT}/benchmarks/benchmark-log.json`. Target benchmarks:

- Static clone fidelity: 99%+ (baseline before conversion)
- Framework template fidelity: 97%+ (target after conversion)
- Below 95%: conversion has regressed — investigate CSS import issues first

## Common Mistakes

- **Recreating CSS with Tailwind**: Introduces the 95% wall. Keep original CSS.
- **Converting all content to dynamic data**: Only extract genuinely repeated patterns. A single hero section with unique text should stay hardcoded.
- **Forgetting SVG namespace attributes**: SVG attributes like `xmlns`, `viewBox`, `fill-rule` need JSX conversion (`fillRule`, etc.).
- **Breaking CSS cascade**: Changing the CSS import order or wrapping elements in new containers can alter specificity. Test layout after every structural change.
- **Skipping the framework question**: Always ask which framework the user wants. Do not default silently.
