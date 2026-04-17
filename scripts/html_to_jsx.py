#!/usr/bin/env python3
"""
HTML-to-JSX Converter (Pass 1: Mechanical)
Converts a static clone directory into a working Vite+React project.
Keeps original CSS verbatim for 99%+ visual fidelity.

Usage: python3 html_to_jsx.py <clone_dir> [output_dir]
Example: python3 html_to_jsx.py clones/example.com/static-clone clones/example.com/jsx-project
"""

import json
import os
import re
import shutil
import sys
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import urlparse

# ── HTML attribute → JSX attribute mapping ──────────────────────────────
ATTR_MAP = {
    "class": "className",
    "for": "htmlFor",
    "tabindex": "tabIndex",
    "readonly": "readOnly",
    "maxlength": "maxLength",
    "minlength": "minLength",
    "cellpadding": "cellPadding",
    "cellspacing": "cellSpacing",
    "colspan": "colSpan",
    "rowspan": "rowSpan",
    "enctype": "encType",
    "novalidate": "noValidate",
    "autocomplete": "autoComplete",
    "autofocus": "autoFocus",
    "autoplay": "autoPlay",
    "crossorigin": "crossOrigin",
    "formaction": "formAction",
    "formmethod": "formMethod",
    "formnovalidate": "formNoValidate",
    "formtarget": "formTarget",
    "accesskey": "accessKey",
    "contenteditable": "contentEditable",
    "contextmenu": "contextMenu",
    "spellcheck": "spellCheck",
    "srcdoc": "srcDoc",
    "srcset": "srcSet",
    "inputmode": "inputMode",
    "charset": "charSet",
    "viewbox": "viewBox",
    "preserveaspectratio": "preserveAspectRatio",
    "baseprofile": "baseProfile",
    "clip-path": "clipPath",
    "clip-rule": "clipRule",
    "fill-opacity": "fillOpacity",
    "fill-rule": "fillRule",
    "flood-color": "floodColor",
    "flood-opacity": "floodOpacity",
    "font-family": "fontFamily",
    "font-size": "fontSize",
    "font-style": "fontStyle",
    "font-weight": "fontWeight",
    "letter-spacing": "letterSpacing",
    "marker-end": "markerEnd",
    "marker-mid": "markerMid",
    "marker-start": "markerStart",
    "stop-color": "stopColor",
    "stop-opacity": "stopOpacity",
    "stroke-dasharray": "strokeDasharray",
    "stroke-dashoffset": "strokeDashoffset",
    "stroke-linecap": "strokeLinecap",
    "stroke-linejoin": "strokeLinejoin",
    "stroke-miterlimit": "strokeMiterlimit",
    "stroke-opacity": "strokeOpacity",
    "stroke-width": "strokeWidth",
    "text-anchor": "textAnchor",
    "text-decoration": "textDecoration",
    "dominant-baseline": "dominantBaseline",
    "alignment-baseline": "alignmentBaseline",
    "xlink:href": "xlinkHref",
    "xml:space": "xmlSpace",
}

# Void elements that must self-close in JSX
VOID_ELEMENTS = {
    "area", "base", "br", "col", "embed", "hr", "img", "input",
    "link", "meta", "param", "source", "track", "wbr",
}

# Boolean attributes
BOOLEAN_ATTRS = {
    "checked", "disabled", "selected", "readonly", "multiple", "autofocus",
    "autoplay", "controls", "loop", "muted", "default", "required",
    "novalidate", "formnovalidate", "hidden", "open", "defer", "async",
}


def css_style_to_jsx(style_str: str) -> str:
    """Convert CSS style string to JSX style object string."""
    if not style_str or not style_str.strip():
        return "{{}}"

    props = []
    for decl in style_str.split(";"):
        decl = decl.strip()
        if ":" not in decl:
            continue
        prop, _, val = decl.partition(":")
        prop = prop.strip()
        val = val.strip()
        if not prop or not val:
            continue

        # Convert kebab-case to camelCase
        parts = prop.split("-")
        camel = parts[0] + "".join(p.capitalize() for p in parts[1:])

        # Quote the value
        # Numbers without units can stay as numbers
        if re.match(r'^-?\d+(\.\d+)?$', val):
            props.append(f"{camel}: {val}")
        else:
            val = val.replace("'", "\\'")
            props.append(f"{camel}: '{val}'")

    return "{{" + ", ".join(props) + "}}"


def convert_attribute(name: str, value: str, tag: str) -> str:
    """Convert a single HTML attribute to JSX."""
    lower_name = name.lower()

    # data-* and aria-* stay as-is
    if lower_name.startswith("data-") or lower_name.startswith("aria-"):
        if value is None:
            return f'{name}=""'
        return f'{name}="{value}"'

    # Map attribute name
    jsx_name = ATTR_MAP.get(lower_name, name)

    # Style attribute → object
    if lower_name == "style":
        return f"style={css_style_to_jsx(value)}"

    # Event handlers
    if lower_name.startswith("on"):
        # onclick="..." → onClick={() => { ... }}
        camel = "on" + lower_name[2:].capitalize()
        safe_val = value.replace('"', "'") if value else ""
        return f'{camel}={{() => {{ {safe_val} }}}}'

    # Boolean attributes
    if lower_name in BOOLEAN_ATTRS:
        if value is None or value == "" or value == lower_name:
            return jsx_name
        return f'{jsx_name}={{{value.lower()}}}'

    # Normal attributes
    if value is None:
        return f'{jsx_name}=""'

    # Escape curly braces in values
    value = value.replace("{", "&#123;").replace("}", "&#125;")

    return f'{jsx_name}="{value}"'


class HTMLToJSXConverter(HTMLParser):
    """Converts HTML string to JSX string."""

    def __init__(self):
        super().__init__()
        self.output = []
        self.in_body = False
        self.body_depth = 0
        self.skip_tags = {"script", "noscript"}
        self.skip_depth = 0

    def handle_starttag(self, tag, attrs):
        lower_tag = tag.lower()

        # Track body
        if lower_tag == "body":
            self.in_body = True
            self.body_depth = 0
            return
        if not self.in_body:
            return

        # Skip script/noscript
        if lower_tag in self.skip_tags:
            self.skip_depth += 1
            return
        if self.skip_depth > 0:
            return

        self.body_depth += 1

        # Convert attributes
        jsx_attrs = []
        for name, value in attrs:
            jsx_attrs.append(convert_attribute(name, value, lower_tag))

        attrs_str = " " + " ".join(jsx_attrs) if jsx_attrs else ""

        # Self-closing void elements
        if lower_tag in VOID_ELEMENTS:
            self.output.append(f"<{tag}{attrs_str} />")
        else:
            self.output.append(f"<{tag}{attrs_str}>")

    def handle_endtag(self, tag):
        lower_tag = tag.lower()

        if lower_tag == "body":
            self.in_body = False
            return
        if not self.in_body:
            return

        if lower_tag in self.skip_tags:
            self.skip_depth = max(0, self.skip_depth - 1)
            return
        if self.skip_depth > 0:
            return

        # Don't close void elements
        if lower_tag not in VOID_ELEMENTS:
            self.output.append(f"</{tag}>")
            self.body_depth -= 1

    def handle_data(self, data):
        if not self.in_body or self.skip_depth > 0:
            return
        # Escape characters that break JSX using placeholder approach
        # to avoid double-escaping
        PH_LB = "\x00LB\x00"  # left brace placeholder
        PH_RB = "\x00RB\x00"  # right brace placeholder
        PH_LT = "\x00LT\x00"  # less-than placeholder
        PH_GT = "\x00GT\x00"  # greater-than placeholder

        data = data.replace("{", PH_LB)
        data = data.replace("}", PH_RB)
        data = re.sub(r'<(?![a-zA-Z/!])', PH_LT, data)
        data = re.sub(r'(?<![a-zA-Z"\'0-9/])>', PH_GT, data)

        data = data.replace(PH_LB, "{'{'}")
        data = data.replace(PH_RB, "{'}'}")
        data = data.replace(PH_LT, "{'<'}")
        data = data.replace(PH_GT, "{'>'}")
        self.output.append(data)

    def handle_comment(self, data):
        # Convert HTML comments to JSX comments
        if not self.in_body or self.skip_depth > 0:
            return
        self.output.append(f"{{/* {data.strip()} */}}")

    def handle_entityref(self, name):
        if not self.in_body or self.skip_depth > 0:
            return
        self.output.append(f"&{name};")

    def handle_charref(self, name):
        if not self.in_body or self.skip_depth > 0:
            return
        self.output.append(f"&#{name};")

    def get_jsx(self):
        return "".join(self.output)


def html_file_to_jsx(html_path: Path) -> str:
    """Convert an HTML file to a JSX component string."""
    html = html_path.read_text(encoding="utf-8", errors="ignore")

    converter = HTMLToJSXConverter()
    try:
        converter.feed(html)
    except Exception as e:
        print(f"  WARN: Parser error in {html_path.name}: {e}")

    jsx_body = converter.get_jsx().strip()
    if not jsx_body:
        jsx_body = "<p>Empty page</p>"

    # Extract title from HTML
    title_match = re.search(r"<title>([^<]+)</title>", html)
    title = title_match.group(1) if title_match else html_path.stem

    # Generate component name from file path
    comp_name = path_to_component_name(html_path)

    return f"""// Auto-generated from {html_path.name}
// Title: {title}
export default function {comp_name}() {{
  return (
    <>
      {jsx_body}
    </>
  )
}}
"""


def path_to_component_name(html_path: Path) -> str:
    """Convert file path to valid React component name."""
    stem = html_path.stem
    if stem == "index":
        parent = html_path.parent.name
        if parent and parent != "." and parent != "static-clone":
            stem = parent + "_index"
        else:
            stem = "Home"

    # PascalCase
    parts = re.split(r'[-_./]', stem)
    name = "".join(p.capitalize() for p in parts if p)

    # Ensure starts with letter
    if name and not name[0].isalpha():
        name = "Page" + name

    return name or "UnnamedPage"


def rewrite_asset_paths(jsx_content: str) -> str:
    """Rewrite relative asset paths to absolute /assets/ paths."""
    # ./assets/ → /assets/
    jsx_content = re.sub(r'(?:\.\.?/)+assets/', '/assets/', jsx_content)
    # Remaining ../ relative paths for assets
    jsx_content = re.sub(r'"(?:\.\./)+([^"]*\.(css|js|png|jpg|webp|svg|woff2?|ttf|ico))"',
                         r'"/assets/\1"', jsx_content)
    return jsx_content


def rewrite_html_links(jsx_content: str) -> str:
    """Rewrite .html href links to React Router paths."""
    def fix_link(m):
        path = m.group(1)
        clean = re.sub(r'^(?:\.\.?/)+', '', path)
        clean = re.sub(r'\.html$', '', clean)
        if clean == 'index' or clean == '':
            return 'href="/"'
        if not clean.startswith('/'):
            clean = '/' + clean
        return f'href="{clean}"'

    jsx_content = re.sub(r'href="((?:\.\.?/)*[^"]*\.html)"', fix_link, jsx_content)
    # Also fix onclick navigation
    jsx_content = re.sub(
        r"window\.location\.href='((?:\.\.?/)*[^']*\.html)'",
        lambda m: "window.location.href='" + re.sub(r'\.html$', '', re.sub(r'^(?:\.\.?/)+', '/', m.group(1))) + "'",
        jsx_content
    )
    return jsx_content


def scaffold_vite_project(output_dir: Path):
    """Create the Vite+React project scaffolding."""
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "src" / "pages").mkdir(parents=True, exist_ok=True)
    (output_dir / "src" / "styles").mkdir(parents=True, exist_ok=True)
    (output_dir / "public" / "assets").mkdir(parents=True, exist_ok=True)

    # package.json
    (output_dir / "package.json").write_text(json.dumps({
        "name": "jsx-project",
        "private": True,
        "version": "0.0.1",
        "type": "module",
        "scripts": {
            "dev": "vite",
            "build": "vite build",
            "preview": "vite preview"
        },
        "dependencies": {
            "react": "^18.3.0",
            "react-dom": "^18.3.0",
            "react-router-dom": "^6.26.0"
        },
        "devDependencies": {
            "@vitejs/plugin-react": "^4.3.0",
            "vite": "^5.4.0"
        }
    }, indent=2))

    # vite.config.js
    (output_dir / "vite.config.js").write_text("""import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
})
""")

    # index.html
    (output_dir / "index.html").write_text("""<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Clone</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.jsx"></script>
  </body>
</html>
""")


def generate_router(pages: dict, output_dir: Path):
    """Generate App.jsx with React Router and main.jsx."""
    # Sort routes: specific before wildcards, shorter before longer
    routes = sorted(pages.items(), key=lambda x: (x[0].count("/"), x[0]))

    imports = []
    route_elements = []

    for url_path, component_name in routes:
        imports.append(
            f"const {component_name} = React.lazy(() => import('./pages/{component_name}'))"
        )
        route_elements.append(
            f'          <Route path="{url_path}" element={{<{component_name} />}} />'
        )

    app_jsx = f"""import React, {{ Suspense }} from 'react'
import {{ Routes, Route }} from 'react-router-dom'

{chr(10).join(imports)}

export default function App() {{
  return (
    <Suspense fallback={{<div style={{{{padding: '2rem', textAlign: 'center'}}}}>Loading...</div>}}>
      <Routes>
{chr(10).join(route_elements)}
      </Routes>
    </Suspense>
  )
}}
"""

    (output_dir / "src" / "App.jsx").write_text(app_jsx)

    # main.jsx
    main_jsx = """import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App'
import './styles/original.css'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </React.StrictMode>
)
"""
    (output_dir / "src" / "main.jsx").write_text(main_jsx)


def copy_assets(clone_dir: Path, output_dir: Path):
    """Copy CSS and assets from clone to project."""
    public_assets = output_dir / "public" / "assets"

    # Copy CSS file(s)
    for css in clone_dir.glob("assets/*.css"):
        dest = output_dir / "src" / "styles" / "original.css"
        shutil.copy2(css, dest)
        print(f"  CSS: {css.name} → src/styles/original.css")

    # Copy all asset files (images, fonts, JS, external)
    assets_dir = clone_dir / "assets"
    if assets_dir.exists():
        for item in assets_dir.rglob("*"):
            if item.is_file() and not item.name.endswith(".css"):
                rel = item.relative_to(assets_dir)
                dest = public_assets / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(item, dest)

    # Copy any top-level images
    for ext in ["*.png", "*.jpg", "*.svg", "*.ico", "*.webp"]:
        for img in clone_dir.glob(ext):
            shutil.copy2(img, output_dir / "public" / img.name)

    print(f"  Assets: {sum(1 for _ in public_assets.rglob('*') if _.is_file())} files copied")


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 html_to_jsx.py <clone_dir> [output_dir]")
        sys.exit(1)

    clone_dir = Path(sys.argv[1])
    if not clone_dir.exists():
        print(f"Error: {clone_dir} does not exist")
        sys.exit(1)

    output_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else clone_dir.parent / "jsx-project"

    if output_dir.exists():
        print(f"Output dir {output_dir} exists. Removing...")
        shutil.rmtree(output_dir)

    print(f"\n🔧 HTML-to-JSX Converter (Pass 1)")
    print(f"   Input:  {clone_dir}")
    print(f"   Output: {output_dir}\n")

    # Step 1: Scaffold
    print("1. Scaffolding Vite+React project...")
    scaffold_vite_project(output_dir)

    # Step 2: Copy assets
    print("2. Copying assets...")
    copy_assets(clone_dir, output_dir)

    # Step 3: Convert HTML files
    print("3. Converting HTML → JSX...")
    html_files = sorted(clone_dir.rglob("*.html"))
    # Exclude non-page files
    html_files = [f for f in html_files if not any(
        skip in str(f) for skip in ["qa_report", "screenshots", "serve.py"]
    )]

    pages = {}  # url_path → component_name
    converted = 0
    errors = 0

    for html_file in html_files:
        rel = html_file.relative_to(clone_dir)
        # Determine URL path
        url_path = "/" + str(rel.with_suffix("")).replace("\\", "/")
        if url_path.endswith("/index"):
            url_path = url_path[:-6] or "/"

        comp_name = path_to_component_name(html_file)

        try:
            jsx_content = html_file_to_jsx(html_file)
            jsx_content = rewrite_asset_paths(jsx_content)
            jsx_content = rewrite_html_links(jsx_content)

            # Save JSX file
            jsx_path = output_dir / "src" / "pages" / f"{comp_name}.jsx"
            jsx_path.parent.mkdir(parents=True, exist_ok=True)
            jsx_path.write_text(jsx_content, encoding="utf-8")

            pages[url_path] = comp_name
            converted += 1
        except Exception as e:
            print(f"  ERROR converting {rel}: {e}")
            errors += 1

    print(f"   Converted {converted} pages ({errors} errors)")

    # Step 4: Generate router
    print("4. Generating React Router...")
    generate_router(pages, output_dir)
    print(f"   {len(pages)} routes created")

    # Summary
    print(f"\n✅ Pass 1 complete!")
    print(f"   Pages: {converted}")
    print(f"   Assets: {sum(1 for _ in (output_dir / 'public').rglob('*') if _.is_file())}")
    print(f"   Output: {output_dir}/")
    print(f"\n   Next steps:")
    print(f"   cd {output_dir} && npm install && npm run dev")
    print(f"   Then run QA comparison to verify 99%+ fidelity")


if __name__ == "__main__":
    main()
