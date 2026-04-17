#!/usr/bin/env python3
"""
Generic site cloner for IllyCloneFramework.

Usage:
    python3 clone_site.py \\
        --base https://example.com \\
        --project-dir clones/example.com/static-clone \\
        --urls-file clones/example.com/example_urls.json \\
        [--cookies-file clones/example.com/example_cookies.json] \\
        [--delay 1.2] \\
        [--viewport 1920x1080] \\
        [--timeout 30000]

Clones every URL in the list using Playwright, captures all network
resources, rewrites absolute URLs to relative, strips SPA entry scripts,
and writes a clone_report.json summary plus a serve.py local-server script.
"""

import argparse
import asyncio
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse, urljoin

from playwright.async_api import async_playwright, Response
from bs4 import BeautifulSoup
import aiohttp


class SiteCloner:
    def __init__(
        self,
        base: str,
        project_dir: Path,
        urls_file: Path,
        cookies_file: Path | None,
        delay: float,
        viewport: tuple[int, int],
        timeout_ms: int,
    ):
        self.base = base.rstrip("/")
        self.base_host = urlparse(self.base).netloc
        self.output = project_dir
        self.output.mkdir(parents=True, exist_ok=True)
        self.urls_file = urls_file
        self.cookies_file = cookies_file
        self.delay = delay
        self.viewport = viewport
        self.timeout_ms = timeout_ms

        self.resources: dict[str, bytes] = {}
        self.resource_paths: dict[str, str] = {}
        self.pages_cloned = 0
        self.errors: list[dict] = []
        self.start_time = time.time()

    def url_to_filepath(self, url: str) -> Path:
        parsed = urlparse(url)
        path = parsed.path.strip("/")
        if not path:
            return self.output / "index.html"
        if "." not in path.split("/")[-1]:
            return self.output / f"{path}.html"
        return self.output / path

    def resource_local_path(self, url: str) -> str:
        parsed = urlparse(url)
        path = parsed.path.strip("/")
        if not path:
            return ""
        if path.startswith("_next/"):
            return path
        if parsed.netloc and parsed.netloc != self.base_host:
            safe_name = re.sub(r"[^\w./\-]", "_", f"{parsed.netloc}/{path}")
            ext = Path(path).suffix or ".bin"
            if not safe_name.endswith(ext):
                safe_name += ext
            return f"assets/external/{safe_name}"
        return path

    async def capture_response(self, response: Response):
        url = response.url
        if response.status != 200:
            return
        content_type = response.headers.get("content-type", "")
        should_capture = any(
            t in content_type
            for t in [
                "text/css",
                "javascript",
                "image/",
                "font/",
                "application/font",
                "woff",
                "svg",
                "json",
            ]
        )
        parsed = urlparse(url)
        if "/_next/" in parsed.path or "/fonts/" in parsed.path:
            should_capture = True
        if not should_capture or url in self.resources:
            return
        try:
            body = await response.body()
            self.resources[url] = body
            local = self.resource_local_path(url)
            if local:
                self.resource_paths[url] = local
        except Exception:
            pass

    def rewrite_html(self, html: str, page_url: str) -> str:
        soup = BeautifulSoup(html, "html.parser")
        page_path = self.url_to_filepath(page_url)
        page_dir = page_path.parent
        try:
            rel = page_dir.relative_to(self.output)
            depth = len(rel.parts)
        except ValueError:
            depth = 0
        prefix = "../" * depth if depth > 0 else "./"

        for tag in soup.find_all(["link", "script", "img", "source", "video", "audio"]):
            for attr in ["href", "src", "srcset"]:
                val = tag.get(attr)
                if not val:
                    continue
                if attr == "srcset":
                    parts = []
                    for entry in val.split(","):
                        entry = entry.strip()
                        if not entry:
                            continue
                        tokens = entry.split()
                        src = tokens[0]
                        rest = " ".join(tokens[1:])
                        new_src = self._rewrite_single_url(src, page_url, prefix)
                        parts.append(f"{new_src} {rest}" if rest else new_src)
                    tag[attr] = ", ".join(parts)
                else:
                    tag[attr] = self._rewrite_single_url(val, page_url, prefix)

        for a in soup.find_all("a", href=True):
            href = a["href"]
            if href.startswith(self.base):
                path = urlparse(href).path.strip("/")
                a["href"] = f"{prefix}index.html" if not path else f"{prefix}{path}.html"
            elif href.startswith("/") and not href.startswith("//"):
                path = href.strip("/")
                a["href"] = f"{prefix}index.html" if not path else f"{prefix}{path}.html"

        for script in soup.find_all("script"):
            src = script.get("src", "")
            text = script.string or ""
            if any(k in src for k in ["googletagmanager", "gtag", "analytics", "hotjar", "mixpanel"]):
                script.decompose()
                continue
            if script.get("type") == "module" or re.search(r"/index-[\w]+\.js", src):
                script.decompose()
                continue
            if any(k in text for k in ["__NEXT_DATA__", "ReactDOM", "createRoot", "hydrateRoot"]):
                script.decompose()

        return str(soup)

    def _rewrite_single_url(self, url: str, page_url: str, prefix: str) -> str:
        if url.startswith(("data:", "blob:", "#", "mailto:", "tel:")):
            return url
        full_url = urljoin(page_url, url)
        if full_url in self.resource_paths:
            return prefix + self.resource_paths[full_url]
        parsed = urlparse(full_url)
        if parsed.netloc in (self.base_host, ""):
            path = parsed.path.strip("/")
            if path.startswith("_next/"):
                return prefix + path
        return url

    async def save_resources(self) -> int:
        saved = 0
        for url, content in self.resources.items():
            local = self.resource_paths.get(url)
            if not local:
                continue
            filepath = self.output / local
            filepath.parent.mkdir(parents=True, exist_ok=True)
            filepath.write_bytes(content)
            saved += 1
        return saved

    async def clone_page(self, page, url: str, idx: int, total: int):
        try:
            print(f"  [{idx+1}/{total}] {urlparse(url).path or '/'}")
            resp = await page.goto(url, wait_until="networkidle", timeout=self.timeout_ms)
            if resp and resp.status >= 400:
                self.errors.append({"url": url, "status": resp.status})
                return
            try:
                await page.wait_for_function("window.__NEXT_DATA__ !== undefined", timeout=3000)
            except Exception:
                pass
            await page.evaluate(
                """async () => {
                    const delay = ms => new Promise(r => setTimeout(r, ms));
                    for (let y = 0; y < document.body.scrollHeight; y += 500) {
                        window.scrollTo(0, y);
                        await delay(150);
                    }
                    window.scrollTo(0, 0);
                }"""
            )
            await page.wait_for_timeout(500)
            html = await page.content()
            html = self.rewrite_html(html, url)
            filepath = self.url_to_filepath(url)
            filepath.parent.mkdir(parents=True, exist_ok=True)
            filepath.write_text(html, encoding="utf-8")
            self.pages_cloned += 1
        except Exception as e:
            self.errors.append({"url": url, "error": str(e)})
            print(f"    ERROR: {e}")

    async def run(self):
        urls = json.loads(self.urls_file.read_text())
        print(f"\nCloning {len(urls)} pages from {self.base}\n")

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-setuid-sandbox"],
            )
            context = await browser.new_context(
                viewport={"width": self.viewport[0], "height": self.viewport[1]},
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/131.0.0.0 Safari/537.36"
                ),
            )
            if self.cookies_file and self.cookies_file.exists():
                cookies = json.loads(self.cookies_file.read_text())
                await context.add_cookies(cookies)
                print("Loaded saved cookies\n")

            page = await context.new_page()
            page.on("response", self.capture_response)

            print("Cloning pages...\n")
            for i, url in enumerate(urls):
                await self.clone_page(page, url, i, len(urls))
                if i < len(urls) - 1:
                    await asyncio.sleep(self.delay)

            await browser.close()

        print(f"\nSaving {len(self.resources)} captured resources...")
        saved = await self.save_resources()
        print(f"   Saved {saved} resource files\n")

        await self.download_missing_assets()
        self.generate_server()

        elapsed = time.time() - self.start_time
        report = {
            "timestamp": datetime.now().isoformat(),
            "base": self.base,
            "pages_cloned": self.pages_cloned,
            "pages_total": len(urls),
            "resources_captured": len(self.resources),
            "resources_saved": saved,
            "errors": self.errors,
            "elapsed_seconds": round(elapsed, 1),
        }
        (self.output / "clone_report.json").write_text(json.dumps(report, indent=2))

        print("Clone complete.")
        print(f"   Pages: {self.pages_cloned}/{len(urls)}")
        print(f"   Resources: {saved}")
        print(f"   Errors: {len(self.errors)}")
        print(f"   Time: {elapsed:.0f}s")
        print(f"   Output: {self.output}/")
        print(f"\n   To serve: cd {self.output} && python serve.py")

    async def download_missing_assets(self):
        print("Checking for missing assets...")
        missing = set()
        for html_file in self.output.rglob("*.html"):
            content = html_file.read_text(errors="ignore")
            for match in re.finditer(r'(?:src|href)="(\.?\.?/?_next/[^"]+)"', content):
                path = match.group(1).lstrip("./")
                if not (self.output / path).exists():
                    missing.add(f"{self.base}/{path}")
            for match in re.finditer(r'(?:src|href)="(\.?\.?/?images/[^"]+)"', content):
                path = match.group(1).lstrip("./")
                if not (self.output / path).exists():
                    missing.add(f"{self.base}/{path}")

        if not missing:
            print("   No missing assets\n")
            return

        print(f"   Downloading {len(missing)} missing assets...")
        async with aiohttp.ClientSession() as session:
            tasks = [self._download_asset(session, url) for url in missing]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            downloaded = sum(1 for r in results if r is True)
            print(f"   Downloaded {downloaded}/{len(missing)} assets\n")

    async def _download_asset(self, session: aiohttp.ClientSession, url: str) -> bool:
        try:
            parsed = urlparse(url)
            filepath = self.output / parsed.path.strip("/")
            if filepath.exists():
                return True
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status != 200:
                    return False
                filepath.parent.mkdir(parents=True, exist_ok=True)
                filepath.write_bytes(await resp.read())
                return True
        except Exception:
            return False

    def generate_server(self):
        server_code = '''#!/usr/bin/env python3
"""Local server for cloned static site."""
import http.server
import os
import sys

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
os.chdir(os.path.dirname(os.path.abspath(__file__)))


class CloneHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        path = self.path.split("?")[0].split("#")[0]
        if path != "/" and "." not in path.split("/")[-1]:
            html_path = path.strip("/") + ".html"
            if os.path.exists(html_path):
                self.path = "/" + html_path
        super().do_GET()

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        super().end_headers()


print(f"Serving clone at http://localhost:{PORT}")
print("Press Ctrl+C to stop")
http.server.HTTPServer(("", PORT), CloneHandler).serve_forever()
'''
        (self.output / "serve.py").write_text(server_code)


def parse_viewport(s: str) -> tuple[int, int]:
    try:
        w, h = s.lower().split("x")
        return int(w), int(h)
    except Exception:
        raise argparse.ArgumentTypeError(f"viewport must be WIDTHxHEIGHT, got {s!r}")


def main():
    parser = argparse.ArgumentParser(description="Generic site cloner (IllyCloneFramework)")
    parser.add_argument("--base", required=True, help="Target base URL, e.g. https://example.com")
    parser.add_argument("--project-dir", required=True, type=Path, help="Output directory for clone")
    parser.add_argument("--urls-file", required=True, type=Path, help="JSON file: list of URLs to clone")
    parser.add_argument("--cookies-file", type=Path, help="Optional cookies.json captured from auth flow")
    parser.add_argument("--delay", type=float, default=1.2, help="Seconds between page loads")
    parser.add_argument("--viewport", type=parse_viewport, default=(1920, 1080))
    parser.add_argument("--timeout", type=int, default=30000, help="Per-page timeout in ms")
    args = parser.parse_args()

    if not args.urls_file.exists():
        print(f"URLs file not found: {args.urls_file}", file=sys.stderr)
        sys.exit(1)

    cloner = SiteCloner(
        base=args.base,
        project_dir=args.project_dir,
        urls_file=args.urls_file,
        cookies_file=args.cookies_file,
        delay=args.delay,
        viewport=args.viewport,
        timeout_ms=args.timeout,
    )
    asyncio.run(cloner.run())


if __name__ == "__main__":
    main()
