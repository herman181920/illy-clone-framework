# Cloning Learnings

Patterns discovered during cloning. Auto-updated after each clone. Skills read this at start to apply known fixes automatically.

---

## Pattern: SPA Script Stripping
**Discovered:** during R&D on a Next.js marketing site (2026-03-29)
**Problem:** SPA JavaScript (React/Vue/Next.js) overrides server-rendered HTML with client-side router, showing 404 on static serve
**Fix:** Strip `<script type="module">` and main entry scripts from all HTML files
**Detection:** Check for `type="module"` attribute or `index-` in script src
**Applies to:** All React, Vue, Next.js, Vite-built SPAs

## Pattern: Nested `<a>` Tag Fix
**Discovered:** during R&D on a Next.js marketing site (2026-03-29)
**Problem:** HTML spec forbids `<a>` inside `<a>`. Browsers auto-close outer `<a>`, breaking card layouts (e.g., 256 grid children instead of 64)
**Fix:** Convert outer card `<a>` to `<div>` with `onclick="window.location.href='...'"` and `style="cursor:pointer"`
**Detection:** Look for `<a>` tags whose innerHTML contains other `<a>` tags
**Applies to:** Any site with clickable card wrappers containing inner links (very common in React SPAs)

## Pattern: Google Fonts CORS
**Discovered:** during R&D on a Next.js marketing site (2026-03-29)
**Problem:** Google Fonts woff2 files can't be downloaded via curl (CORS blocks). Even `fetch()` from page context returns error pages.
**Fix:** Capture font files during Playwright crawl via response interception, OR keep Google Fonts CDN reference in HTML
**Applies to:** Any site using Google Fonts

## Pattern: Lazy-Loaded Images
**Discovered:** during R&D on a Next.js marketing site (2026-03-29)
**Problem:** Images using IntersectionObserver don't load until scrolled into view
**Fix:** After page.goto(), scroll the full page in 500px increments with 150ms delays, then scroll back to top
**Applies to:** Most modern sites with image-heavy pages

## Pattern: URL Rewriting for Offline Serving
**Discovered:** during R&D on a Next.js marketing site (2026-03-29)
**Problem:** Cloned HTML has absolute URLs pointing to original domain
**Fix:** Rewrite `href`, `src`, `srcset` to relative paths. Internal links get `.html` suffix. Preserve `_next/static/` structure for Next.js chunk loading.
**Applies to:** All cloned sites

---

## Pattern: Public audit is not enough for authenticated SPAs
**Applies to:** Any target with an `/app`, `/dashboard`, or `desktop.*` subdomain
Crawling a modern SaaS from the outside gives you the marketing shell — roughly 10% of the actual product surface. The editor, project list, library, and tool flows all live behind auth. Before writing a clone spec, drive the authenticated surfaces. If you can't authenticate, say "audit is incomplete" explicitly. Pretending the public view is the full picture wastes the next session's first hour re-discovering what's actually there.

## Pattern: Cookie-subdomain pitfall
**Applies to:** Any target using NextAuth or per-subdomain session cookies
A session cookie scoped to `app.target.com` does not exist on `target.com` or `auth.provider.app`. Users who log into the marketing site (or use only the mobile/desktop app) will have zero browser cookies for the web app. "I'm already logged in" means nothing until you confirm `__Secure-next-auth.session-token` exists on the exact app subdomain. Re-run `import_browser_cookies.py` after the user logs into the specific web app URL. Full topology breakdown in `docs/patterns/nextauth-subdomain-auth.md`.

## Pattern: `security -wa` keychain command is a silent footgun (macOS)
**Discovered:** cookie extraction on macOS Chrome
`security find-generic-password -wa "Chrome Safe Storage"` treats the argument as an ACCOUNT name, not a service name, and returns "item not found" silently. The correct form is `security find-generic-password -s "Chrome Safe Storage" -w`. Already fixed in `scripts/import_browser_cookies.py`.

## Pattern: Original visual design is the legal firewall; structural match is the competitive value
**Applies to:** Any clone of a commercial product
Copyrightable: marketing copy, distinctive icons, illustrations, specific brand tokens (exact color/font combos that form a recognizable brand identity), verbatim code. Not copyrightable: information architecture, feature grouping, flow sequences, interaction patterns, standard layouts common to the category. The right move is structural match (same screens, same flows, same functional layout) + completely original visual layer (different font, different color palette, different icons, original copy). Skipping the structural work to "avoid legal risk" is backwards — the structural work is the product value. Visual originality is the compliance.

## Pattern: Reuse the modern-saas-editor IA skeleton
**Applies to:** Timeline-centric creation SaaS (video editors, DAWs, design tools, animation tools)
The 4-zone editor layout (icon sidebar + preview + timeline + right rail), icon sidebar slot taxonomy, right-rail accordion structure, project-list card grid with metadata tuple, bottom-anchored prompt widget, 2-3 step funnel pattern, and profile single-column sections are common across all timeline-centric creation tools. See `docs/patterns/modern-saas-editor.md`. Before cloning any tool in this category, map the target against that template in the first 15 minutes. Only document deviations — don't re-derive the skeleton from scratch.

## Pattern: beforeunload should be dirty-state only
**Discovered:** multi-step wizard + modal routes
A naive `useEffect(() => { window.addEventListener('beforeunload', ...) }, [])` fires the "leave site?" dialog on every pristine visit, which is terrible UX and blocks Playwright driving. Gate the listener on a `dirty` boolean (non-empty input, past step 1, non-default values). Source apps only arm the guard when the user actually has unsaved state — your clone should match.
