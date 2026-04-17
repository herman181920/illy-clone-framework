# Known HTML Fixes Reference

Comprehensive documentation of fixes applied during the HTML auto-fix stage (Step 6) of the cloning pipeline. Each fix includes what to detect, why it breaks, and how to resolve it.

---

## 1. SPA Script Stripping

### Problem

Single-page application (SPA) frameworks ship JavaScript bundles that take control of the DOM after initial render. When serving cloned HTML statically, these scripts attempt to hydrate or mount the application, fail to connect to the original server's API endpoints, and either show a blank page, a 404 error, or corrupt the rendered HTML.

### What to Strip

**Module entry points:**
- All `<script type="module">` tags. These are ES module entry points that bootstrap the SPA framework. Without the original server's module resolution, they throw import errors and break rendering.
- Scripts with `src` containing `index-` followed by a hash (e.g., `index-Dk4f8s.js`). These are Vite/Rollup entry bundles.

**Framework-specific hydration scripts:**
- Next.js: Any `<script>` containing `__NEXT_DATA__`, `_next/static/chunks/`, or inline scripts referencing `self.__next_f`. These drive Next.js client-side navigation and data fetching.
- React: Inline scripts calling `ReactDOM.hydrate`, `ReactDOM.createRoot`, `hydrateRoot`, or `render`. These attempt to re-render the entire page from React components.
- Vue: Scripts referencing `__VUE__`, `createApp`, or `app.mount`. These initialize the Vue application instance.
- Nuxt: Scripts containing `__NUXT__` or `nuxt.config`. These bootstrap the Nuxt runtime.

**Analytics and tracking:**
- Google Analytics: Scripts with `src` containing `googletagmanager.com` or `google-analytics.com`, and inline scripts referencing `gtag(` or GA measurement IDs (pattern: `G-XXXXXXXXXX`).
- Ahrefs: Scripts with `src` containing `analytics.ahrefs.com`.
- Hotjar: Scripts containing `hotjar.com` or `_hjSettings`.
- Mixpanel: Scripts containing `mixpanel.com` or `mixpanel.init`.
- Generic: Any script with `src` matching common CDN patterns for tracking (Segment, Amplitude, Heap).

### What to Keep

- `<script>` tags without `type="module"` that handle UI interactions (dropdowns, modals, accordions, carousels). These are typically inline scripts or non-module external scripts.
- CSS-in-JS style injection scripts (though these are rare in SSR output since styles are usually inlined).
- Schema.org JSON-LD scripts (`<script type="application/ld+json">`). These are metadata, not executable.

### Implementation Pattern

```python
for script in soup.find_all("script"):
    src = script.get("src", "")
    text = script.string or ""
    script_type = script.get("type", "")

    # Strip module entry points
    if script_type == "module":
        script.decompose()
        continue

    # Strip analytics
    if any(tracker in src for tracker in [
        "googletagmanager", "google-analytics", "gtag",
        "analytics.ahrefs", "hotjar", "mixpanel"
    ]):
        script.decompose()
        continue

    # Strip framework hydration
    if any(pattern in text for pattern in [
        "__NEXT_DATA__", "ReactDOM", "createRoot", "hydrateRoot",
        "__VUE__", "createApp", "__NUXT__", "self.__next_f"
    ]):
        script.decompose()
        continue

    # Strip Vite/Rollup entry bundles
    if "index-" in src and script_type == "module":
        script.decompose()
        continue
```

---

## 2. Nested `<a>` Tag Detection and Fix

### Problem

HTML spec forbids nesting `<a>` elements inside other `<a>` elements. When browsers encounter `<a><a>`, they auto-close the outer `<a>` before opening the inner one. This breaks:
- Layout: the outer link's children get split across two separate elements, destroying flex/grid layouts.
- Click behavior: clicking the area that was supposed to be the outer link does nothing or navigates to the wrong destination.
- Visual rendering: padding, background, and border from the outer link get applied incorrectly.

This is extremely common in cloned sites because many frameworks render card-like components with an outer link wrapping a title that is also a link.

### Detection

Search all HTML files for nested anchor patterns:

```python
import re

# Find <a> tags that contain other <a> tags
# This regex catches the common case; BeautifulSoup traversal is more reliable
for a_tag in soup.find_all("a"):
    nested = a_tag.find("a")
    if nested:
        # This a_tag has a nested anchor — needs fixing
```

### Fix: Convert Outer to `<div>` with `onclick`

Replace the outer `<a>` with a `<div>` that preserves the link behavior via JavaScript:

```python
def fix_nested_anchors(soup):
    """Fix nested <a> tags by converting outer to clickable <div>."""
    changed = True
    while changed:
        changed = False
        for a_tag in soup.find_all("a"):
            if a_tag.find("a"):
                # Get the outer link's href
                href = a_tag.get("href", "#")

                # Create replacement div
                div = soup.new_tag("div")

                # Copy all attributes except href
                for attr, val in a_tag.attrs.items():
                    if attr != "href":
                        div[attr] = val

                # Add click behavior and cursor styling
                existing_style = div.get("style", "")
                div["style"] = f"cursor: pointer; {existing_style}".strip()
                div["onclick"] = f"window.location.href='{href}'"
                div["role"] = "link"
                div["tabindex"] = "0"

                # Move children
                for child in list(a_tag.children):
                    div.append(child.extract())

                a_tag.replace_with(div)
                changed = True
                break  # Restart scan since DOM changed
```

The `while changed` loop handles deeply nested cases where fixing one level reveals another.

### Accessibility Considerations

When converting to `<div onclick>`, add `role="link"` and `tabindex="0"` to maintain keyboard navigation. Add an `onkeydown` handler for Enter key activation:

```python
div["onkeydown"] = f"if(event.key==='Enter')window.location.href='{href}'"
```

---

## 3. URL Rewriting Patterns

### Problem

Cloned HTML contains absolute URLs pointing to the original domain. When served locally, these either fetch from the live site (defeating the purpose of cloning) or fail if the site is unreachable.

### Absolute to Relative Conversion

For each HTML file, calculate the depth from the output root directory to determine the relative prefix:

```python
def get_relative_prefix(html_filepath, output_root):
    """Calculate ../ prefix for relative URLs."""
    rel = html_filepath.parent.relative_to(output_root)
    depth = len(rel.parts)
    return "../" * depth if depth > 0 else "./"
```

### Attributes to Rewrite

Process these HTML attributes on their respective elements:

| Element | Attribute | Notes |
|---------|-----------|-------|
| `<a>` | `href` | Internal navigation links |
| `<link>` | `href` | CSS stylesheets, favicons, preload |
| `<script>` | `src` | JavaScript files |
| `<img>` | `src` | Image sources |
| `<img>` | `srcset` | Responsive image sources (comma-separated, each entry has URL + descriptor) |
| `<source>` | `src`, `srcset` | Picture/video/audio sources |
| `<video>` | `src`, `poster` | Video file and poster image |
| `<audio>` | `src` | Audio files |
| `<meta>` | `content` | Open Graph images (`og:image`), canonical URLs |

### CSS `url()` References

Also rewrite `url()` references inside `<style>` blocks and inline `style` attributes:

```python
import re

def rewrite_css_urls(css_text, prefix):
    """Rewrite url() references in CSS."""
    def replace_url(match):
        url = match.group(1).strip("'\"")
        if url.startswith("data:") or url.startswith("http"):
            return match.group(0)
        return f"url({prefix}{url})"
    return re.sub(r'url\(([^)]+)\)', replace_url, css_text)
```

### Internal Link Rewriting

For `<a href>` pointing to pages on the same domain, convert the URL path to the local HTML filename:

- `/` becomes `{prefix}index.html`
- `/about` becomes `{prefix}about.html`
- `/blog/post-1` becomes `{prefix}blog/post-1.html`
- Fragment-only links (`#section`) are left unchanged
- External links (different domain) are left unchanged
- Protocol-relative links (`//cdn.example.com/...`) are left unchanged

### `srcset` Handling

The `srcset` attribute requires special parsing because it contains comma-separated entries, each with a URL and an optional size descriptor:

```
srcset="image-300.jpg 300w, image-600.jpg 600w, image-1200.jpg 1200w"
```

Split on commas, rewrite each URL independently, preserve the descriptors, rejoin.

---

## 4. Google Fonts Handling

### Problem

Google Fonts are loaded via `<link>` tags pointing to `fonts.googleapis.com` (CSS) and `fonts.gstatic.com` (font files). When serving locally:
- The CSS link fetches a stylesheet containing `@font-face` rules with URLs to `.woff2` files on `fonts.gstatic.com`.
- CORS policies on the font CDN may block requests from `localhost`.
- If the user is offline, fonts fail to load entirely, causing significant visual differences.

### Solution: Capture During Crawl

During the Playwright crawl (Step 5), the response interceptor already captures font files. Ensure the interceptor's `should_capture` logic includes:

```python
should_capture = any(t in content_type for t in [
    "font/", "application/font", "woff", "woff2"
])
# Also capture by URL pattern
if "fonts.gstatic.com" in parsed.netloc or "fonts.googleapis.com" in parsed.netloc:
    should_capture = True
```

After cloning, rewrite the Google Fonts CSS link to point to a locally saved copy of the CSS file. Inside that CSS file, rewrite the `@font-face` `src` URLs to point to the locally saved `.woff2` files.

### Fallback: System Font Stack

If fonts were not captured during the crawl, add a fallback CSS rule:

```css
/* Fallback for missing Google Fonts */
body {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}
```

This prevents layout shifts from drastically different font metrics while maintaining a visually similar appearance.

---

## 5. Lazy-Loaded Image Handling

### Problem

Many modern sites use lazy loading for images below the fold. Images may have:
- `loading="lazy"` attribute (browser-native lazy loading)
- Placeholder `src` (1x1 transparent pixel, blur placeholder) with the real source in `data-src`
- IntersectionObserver-based loading triggered by JavaScript

When Playwright captures the page without scrolling, these images appear as placeholders in the HTML.

### Solution: Scroll Before Capture

The clone script must scroll the full page height before capturing HTML to trigger all lazy-load observers:

```javascript
async () => {
    const delay = ms => new Promise(r => setTimeout(r, ms));
    const height = document.body.scrollHeight;
    for (let y = 0; y < height; y += 500) {
        window.scrollTo(0, y);
        await delay(150);  // Allow observers to fire and images to start loading
    }
    window.scrollTo(0, 0);  // Return to top
    await delay(500);  // Allow final images to finish loading
}
```

### Post-Processing: Swap `data-src` to `src`

After capturing HTML, swap lazy-load attributes to ensure images display without JavaScript:

```python
for img in soup.find_all("img"):
    # Swap data-src to src
    data_src = img.get("data-src")
    if data_src and (not img.get("src") or "placeholder" in img.get("src", "")):
        img["src"] = data_src
        del img["data-src"]

    # Swap data-srcset to srcset
    data_srcset = img.get("data-srcset")
    if data_srcset:
        img["srcset"] = data_srcset
        del img["data-srcset"]

    # Remove lazy loading attribute (images should load eagerly in static clone)
    if img.get("loading") == "lazy":
        img["loading"] = "eager"
```

### Edge Case: CSS Background Images

Some lazy-load implementations use CSS background images toggled by JavaScript class changes. These are harder to capture. The scroll-and-wait approach triggers most of them, but if images are still missing after QA, inspect the diff zones for background-image references and manually add the correct CSS.
