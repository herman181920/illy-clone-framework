---
name: analyze
description: This skill should be used when the user asks to "analyze this website", "generate architecture analysis", "SEO analysis", "what tech stack does this site use", "reverse engineer this site", or wants a comprehensive technical breakdown of a cloned website. Generates an ANALYSIS.md document.
---

# Architecture & SEO Analysis

## Overview

Generate a comprehensive ANALYSIS.md document for any cloned website by examining its static HTML, CSS, JavaScript, and captured API data. The analysis covers tech stack detection, architecture patterns, inferred database schema, SEO strategy, design system extraction, and content strategy. Every finding must be grounded in observable evidence from the clone files — do not speculate or assume.

## When to Use

- After completing a clone (static files are available in `clones/{domain}/static-clone/`)
- When the user asks what technology a site uses
- When planning a conversion to understand the original architecture
- When performing competitive analysis on a cloned site
- Before improving a clone, to understand what patterns to preserve

## Analysis Process

### Step 1: Inventory the Clone

Read the clone directory structure to understand what was captured:

- Count HTML pages and their URL paths
- List CSS files (external stylesheets, inline `<style>` blocks)
- List JavaScript files (bundles, inline scripts, third-party)
- Identify captured assets (images, fonts, SVGs, videos)
- Check for captured API responses or JSON data files
- Note any `robots.txt`, `sitemap.xml`, or manifest files

### Step 2: Tech Stack Detection

Detect frameworks and libraries from observable markers in the HTML and JS:

**Frontend Framework Detection:**

| Marker | Framework |
|--------|-----------|
| `__NEXT_DATA__` script tag or `_next/` paths | Next.js |
| `__NUXT__` or `/_nuxt/` paths | Nuxt.js |
| `data-reactroot` attribute | React (generic) |
| `ng-version` attribute or `ng-*` directives | Angular |
| `data-v-` attribute prefixes | Vue.js |
| `data-svelte-h` or Svelte-specific class hashes | SvelteKit |
| `__GATSBY` or `/static/` Gatsby patterns | Gatsby |
| `astro-island` or `client:*` attributes | Astro |

**CSS Framework Detection:**

| Marker | Framework |
|--------|-----------|
| Utility classes like `flex`, `pt-4`, `text-sm`, `bg-gray-100` | Tailwind CSS |
| `bootstrap` in class names or CSS file references | Bootstrap |
| `chakra-ui` classes or data attributes | Chakra UI |
| `MuiButton`, `MuiTypography` class patterns | Material UI |
| `mantine-` prefixed classes | Mantine |
| CSS custom properties with systematic naming | Custom design system |

**UI Component Libraries:**

Scan for data attributes and class patterns indicating component libraries:
- Radix UI: `data-radix-*` attributes
- Headless UI: `data-headless-*` attributes
- shadcn/ui: Combination of Tailwind + Radix markers
- Framer Motion: `data-framer-*` or motion-specific CSS

**Third-Party Services:**

| Pattern | Service |
|---------|---------|
| `gtag`, `GA_MEASUREMENT_ID`, `google-analytics` | Google Analytics |
| `hotjar` or `_hj` | Hotjar |
| `intercom` or `intercomSettings` | Intercom |
| `stripe` in script sources | Stripe |
| `sentry` or `Sentry.init` | Sentry |
| `segment` or `analytics.js` | Segment |
| `supabase` in script sources or API calls | Supabase |
| `firebase` references | Firebase |
| `clerk` references or `__clerk` | Clerk Auth |
| `auth0` references | Auth0 |

### Step 3: Architecture Analysis

Examine the HTML structure and JavaScript to determine architecture patterns:

**Routing Pattern:**
- SPA: Single HTML file with client-side routing (hash or history mode)
- SSR: Multiple HTML pages with server-rendered content, hydration scripts
- SSG: Multiple HTML pages without hydration, fully static
- Hybrid: Mix of static and dynamic pages

**Component Hierarchy:**
- Map the DOM tree of each page type
- Identify shared layout elements (nav, footer, sidebar)
- Note component nesting depth and patterns
- Document any web component usage (`<custom-element>` tags)

**Code Splitting:**
- Check for multiple JS bundle files (chunk-based splitting)
- Look for dynamic import patterns in scripts
- Note lazy-loaded components or routes

**API Patterns:**
- Examine captured network data for REST endpoints, GraphQL queries
- Document base API URLs and endpoint patterns
- Note authentication headers or token patterns observed

### Step 4: Database Schema Inference

If API responses or JSON data were captured during cloning:

- Examine Supabase REST paths to infer table names (e.g., `/rest/v1/users` implies a `users` table)
- Parse GraphQL queries for type names and field structures
- Map JSON response shapes to infer entity relationships
- Document field types, nullable fields, and array relationships
- Note any pagination patterns (cursor-based, offset-based)

Present as a table:

| Entity | Fields (inferred) | Source |
|--------|--------------------|--------|
| users | id, email, name, avatar_url, created_at | `/rest/v1/users` response |
| posts | id, title, content, author_id, published_at | GraphQL `posts` query |

### Step 5: SEO Strategy Analysis

Examine each page type's SEO implementation:

**Meta Tags Per Page Type:**
- `<title>` tag content and pattern (e.g., "Page Title | Site Name")
- `<meta name="description">` content and length
- `<meta name="keywords">` if present
- Canonical URLs (`<link rel="canonical">`)
- Viewport meta tag configuration

**Open Graph & Social:**
- `og:title`, `og:description`, `og:image`, `og:type`, `og:url`
- Twitter Card tags (`twitter:card`, `twitter:title`, `twitter:image`)
- LinkedIn-specific tags if present

**Technical SEO:**
- Presence and contents of `robots.txt`
- Sitemap structure (`sitemap.xml`)
- Structured data (`<script type="application/ld+json">`) — document the schema types used
- Internal linking patterns (how pages link to each other)
- Heading hierarchy (H1-H6 usage per page)
- Image alt text coverage (percentage of images with meaningful alt text)
- URL structure and slug patterns

**Site Navigation & Directory:**
- Main navigation links and hierarchy
- Footer navigation structure
- Breadcrumb patterns
- Sidebar navigation if present

### Step 6: Design System Extraction

Extract the design system from the CSS files:

**CSS Custom Properties:**
Parse `:root` or `html` blocks for custom properties and organize by category:
- Colors (primary, secondary, accent, neutral, semantic)
- Typography (font families, sizes, weights, line heights)
- Spacing (padding/margin scale)
- Shadows (elevation levels)
- Border radius values
- Animation/transition values
- Breakpoints (from media queries)

**Typography System:**
- Font families loaded (Google Fonts, local fonts, system fonts)
- Font size scale (minimum to maximum, and the steps)
- Font weight usage across the site
- Line height patterns

**Color Palette:**
Extract all unique colors used and organize by:
- Brand colors (logo, primary CTA)
- Text colors (heading, body, muted, link)
- Background colors (page, card, section alternates)
- Border colors
- State colors (success, warning, error, info)

**Spacing and Layout:**
- Identify the spacing scale by collecting all unique margin and padding values
- Document common layout patterns (CSS Grid vs Flexbox usage)
- Note maximum content width (typically 1200-1440px containers)
- Record gap values used in grid and flex layouts

**Motion and Interaction:**
- Catalog `transition` and `animation` properties
- Document `@keyframes` declarations
- Note hover, focus, and active state styles
- Record any scroll-triggered animation patterns (intersection observer, scroll-linked)

### Step 7: Content Strategy

Document the site's content architecture:

**Page Types and Their Purpose:**
- Landing/home page structure and goals
- Product/feature pages
- Blog/content pages
- Documentation pages
- Legal pages (privacy, terms)
- Authentication pages (login, signup)

**Conversion Flows:**
- CTA placement patterns (above fold, in-content, sticky)
- Form types and their placement
- Pricing page structure
- Signup/onboarding flow

**Content Patterns:**
- Social proof elements (testimonials, logos, stats)
- Trust signals (security badges, certifications)
- Content update frequency (dates on posts/pages)

## Output Format

Save the analysis as `clones/{domain}/ANALYSIS.md`. Use the analysis template in `${CLAUDE_PLUGIN_ROOT}/skills/analyze/references/analysis-template.md` as the structural guide.

Organize with clear markdown sections, use tables for structured data, and include code blocks for CSS custom property values or JSON schema examples. Every section must cite the specific file or element where the evidence was found.

## Cross-Referencing Findings

After completing all analysis steps, cross-reference findings to identify patterns:

- If the site uses Next.js (Step 2) and has strong SEO (Step 5), document the SSR/SSG strategy that enables this
- If Supabase is detected (Step 2) and API responses were captured (Step 4), the database schema inference will be higher confidence
- If a design system with CSS custom properties is found (Step 6), note which properties the framework conversion should preserve
- If the site has complex conversion flows (Step 7), flag these as components that need careful handling during conversion

These cross-references make the ANALYSIS.md actionable for the subsequent `/convert` and `/improve` steps.

## Common Mistakes

- **Guessing the framework without evidence**: If no definitive markers are found, document "Unknown" with a list of what was checked. Do not guess based on visual appearance.
- **Confusing SSR and SSG**: Both produce multiple HTML files. SSR includes hydration scripts and `__NEXT_DATA__` with dynamic content; SSG has fully rendered HTML without runtime data fetching. Check for the presence of hydration markers.
- **Missing CSS custom properties in dark mode**: Many sites define a separate set of custom properties under a `.dark` or `[data-theme="dark"]` selector. Check for these in addition to `:root`.
- **Ignoring inline styles**: Some components use inline `style` attributes for dynamic values (especially in SSR frameworks). These are part of the design system even if not in the stylesheet.
- **Counting coverage incorrectly**: When reporting "X of Y pages have og:image", count distinct page types, not total HTML files (a blog with 50 posts counts as one page type).

## Analysis Principles

- **Factual only**: Document what is observable in the clone files. If a technology cannot be confirmed from markers, note it as "possible" with the ambiguous evidence cited.
- **Evidence-based**: Every claim must reference a specific file path, class name, attribute, or code snippet from the clone.
- **Complete**: Cover all sections even if some have minimal findings. An empty section with "No structured data detected" is better than an omitted section.
- **Actionable**: Frame findings in terms of what they mean for cloning fidelity and conversion planning.

## Additional Resources

### Reference Files

For the complete output template with all sections and placeholder content:
- **`references/analysis-template.md`** — Full ANALYSIS.md template showing expected structure and format for every section
