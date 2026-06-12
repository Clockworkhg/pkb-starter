#!/usr/bin/env python3
"""
PKB web_pack -- Basic Web Collector (v0.1.0)

Clean-room implementation. Fetches public web pages and produces standardized
webpack output. No third-party skill code is included.

Functional design inspired by the web-pack concept (structured web content
collection with inventory files). All code is independently written.

Usage:
    python tools/web_pack.py --topic "topic" --url "https://..."
    python tools/web_pack.py --topic "topic" --url "u1" --url "u2"
    python tools/web_pack.py --topic "topic" --url "u1" --max-depth 1

Output structure:
    raw/webpacks/<date>-<topic>/
      README.md
      manifest.json
      01-link-inventory.md
      02-image-inventory.md
      03-reading-map.md
      04-media-inventory.md
      MAIN-<topic>.md
      snapshots/<page>.md
      assets/

Dependencies:
    pip install requests beautifulsoup4 markdownify
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse, urlunparse

# ── Optional dependency detection ──────────────────────────────────

HAS_REQUESTS = False
HAS_BS4 = False
HAS_MARKDOWNIFY = False

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    pass

try:
    from bs4 import BeautifulSoup, Tag
    HAS_BS4 = True
except ImportError:
    pass

try:
    from markdownify import markdownify as md_convert
    HAS_MARKDOWNIFY = True
except ImportError:
    pass

# ── Constants ──────────────────────────────────────────────────────

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)

REQUEST_TIMEOUT = 30
REQUEST_DELAY = 0.3  # seconds between requests

# URL patterns to skip (binary, assets, auth pages)
SKIP_URL_PATTERNS = re.compile(
    r"\.(pdf|zip|tar|gz|exe|dmg|iso|deb|rpm|jar|war|"
    r"png|jpg|jpeg|gif|svg|ico|webp|bmp|tiff?|"
    r"mp4|webm|mp3|wav|ogg|flac|avi|mov|mkv|"
    r"woff2?|ttf|eot|otf|"
    r"css|js|map)(\?|#|$)",
    re.IGNORECASE,
)

# Auth-related URL fragments to skip
AUTH_PATTERNS = re.compile(
    r"/(login|signin|signup|register|auth|oauth|logout|account|profile|"
    r"settings|admin|dashboard|api)",
    re.IGNORECASE,
)

# Content selectors -- tried in order for body extraction
CONTENT_SELECTORS = [
    "article",
    '[role="main"]',
    "main",
    ".post-content",
    ".article-content",
    ".entry-content",
    ".content",
    "#content",
    ".post",
    ".article",
    "#mw-content-text",
    ".markdown-body",
    "#readme",
    ".blog-post",
]

# Elements to remove before content extraction
REMOVE_SELECTORS = [
    "script", "style", "noscript",
    "nav", "header", "footer",
    ".sidebar", ".nav", ".navigation", ".menu",
    ".advertisement", ".ads", ".ad",
    ".cookie-banner", ".cookie-consent", ".gdpr",
    ".social-share", ".comments", "#comments",
    '[role="navigation"]', '[role="banner"]', '[role="contentinfo"]',
]

# File extensions to skip when crawling links
SKIP_EXTENSIONS = {
    ".pdf", ".zip", ".tar", ".gz", ".exe", ".dmg", ".iso",
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".webp",
    ".mp4", ".webm", ".mp3", ".wav", ".ogg",
    ".css", ".js", ".map", ".woff", ".woff2", ".ttf", ".eot",
    ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
}

# GitHub URL patterns
GITHUB_BLOB_RE = re.compile(
    r"^https?://github\.com/([^/]+)/([^/]+)/blob/(.+)$", re.IGNORECASE
)
GITHUB_TREE_RE = re.compile(
    r"^https?://github\.com/([^/]+)/([^/]+)/tree/(.+)$", re.IGNORECASE
)
GITHUB_REPO_RE = re.compile(
    r"^https?://github\.com/([^/]+)/([^/]+)/?$", re.IGNORECASE
)


# ── Utility Functions ──────────────────────────────────────────────

def sanitize_filename(name: str, max_len: int = 80) -> str:
    """Convert a string to a safe filename."""
    name = re.sub(r'[<>:"/\\|?*]', "-", name)
    name = re.sub(r"\s+", "-", name)
    name = name.strip("-")
    if len(name) > max_len:
        name = name[:max_len].rstrip("-")
    return name or "untitled"


def url_to_filename(url: str) -> str:
    """Derive a readable filename from a URL."""
    parsed = urlparse(url)
    path = parsed.path.strip("/")
    if not path:
        return sanitize_filename(parsed.netloc)
    parts = path.split("/")
    name = parts[-1] if parts else parsed.netloc
    # Remove extension
    name = re.sub(r"\.[^.]+$", "", name)
    return sanitize_filename(name)


def normalize_url(url: str) -> str:
    """Remove fragments and trailing slashes from URL."""
    parsed = urlparse(url)
    return urlunparse((
        parsed.scheme,
        parsed.netloc,
        parsed.path.rstrip("/") or "/",
        parsed.params,
        parsed.query,
        "",  # drop fragment
    ))


def is_same_domain(url1: str, url2: str) -> bool:
    """Check if two URLs share the same domain."""
    return urlparse(url1).netloc == urlparse(url2).netloc


def github_to_raw(url: str) -> str | None:
    """Convert a GitHub URL to its raw equivalent. Returns None if not a GitHub URL."""
    m = GITHUB_BLOB_RE.match(url)
    if m:
        return f"https://raw.githubusercontent.com/{m.group(1)}/{m.group(2)}/{m.group(3)}"
    m = GITHUB_TREE_RE.match(url)
    if m:
        # tree -> use GitHub API to list, return the URL for later handling
        return None  # tree URLs need directory listing, not raw conversion
    m = GITHUB_REPO_RE.match(url)
    if m:
        return f"https://raw.githubusercontent.com/{m.group(1)}/{m.group(2)}/refs/heads/main/README.md"
    return None


def detect_content_weakness(text: str) -> bool:
    """Check if extracted text is too weak to be useful (e.g., JS-only pages)."""
    weak_phrases = [
        "enable javascript",
        "javascript is not available",
        "this browser is no longer supported",
        "something went wrong",
        "access denied",
        "checking your browser",
        "just a moment",
        "verify you are human",
        "log in to",
        "sign up now",
    ]
    lowered = text.lower()
    return any(phrase in lowered for phrase in weak_phrases)


def should_skip_url(url: str) -> bool:
    """Check if a URL should be skipped (binary, auth page, etc.)."""
    if SKIP_URL_PATTERNS.search(url):
        return True
    if AUTH_PATTERNS.search(urlparse(url).path):
        return True
    return False


# ── HTTP Fetching ──────────────────────────────────────────────────

def fetch_page(url: str, session: requests.Session | None = None) -> str | None:
    """Fetch a web page and return its HTML content. Returns None on failure."""
    if session is None:
        sess = requests.Session()
        sess.headers.update({"User-Agent": USER_AGENT})
    else:
        sess = session

    try:
        resp = sess.get(url, timeout=REQUEST_TIMEOUT, allow_redirects=True)
        resp.raise_for_status()

        content_type = resp.headers.get("Content-Type", "")
        if "text/html" not in content_type and "text/plain" not in content_type:
            return None  # not a text page

        # Try UTF-8 first, fall back to response-detected encoding
        resp.encoding = resp.apparent_encoding or "utf-8"
        return resp.text
    except requests.RequestException:
        return None


def fetch_github_raw(url: str, session: requests.Session | None = None) -> str | None:
    """Fetch content from a GitHub raw URL. Returns text content or None."""
    if session is None:
        sess = requests.Session()
        sess.headers.update({"User-Agent": USER_AGENT})
    else:
        sess = session

    try:
        resp = sess.get(url, timeout=REQUEST_TIMEOUT, allow_redirects=True)
        resp.raise_for_status()
        return resp.text
    except requests.RequestException:
        return None


# ── HTML Parsing ───────────────────────────────────────────────────

def parse_html(html: str, base_url: str) -> tuple[str, str, list[dict], list[dict]]:
    """
    Parse HTML and extract: title, body_markdown, links, images.

    Returns: (title, body_markdown, links_list, images_list)
    """
    soup = BeautifulSoup(html, "html.parser")

    # Extract title
    title = ""
    title_tag = soup.find("title")
    if title_tag:
        title = title_tag.get_text(strip=True)
    if not title:
        h1 = soup.find("h1")
        if h1:
            title = h1.get_text(strip=True)

    # Remove unwanted elements
    for selector in REMOVE_SELECTORS:
        for el in soup.select(selector):
            el.decompose()

    # Extract body content
    body = None
    for selector in CONTENT_SELECTORS:
        body = soup.select_one(selector)
        if body:
            break
    if body is None:
        body = soup.find("body")
    if body is None:
        body = soup

    # Convert body to markdown
    body_html = str(body)
    if HAS_MARKDOWNIFY:
        body_md = md_convert(body_html, heading_style="ATX")
    else:
        # Fallback: extract text
        body_md = body.get_text("\n", strip=True)

    # Extract links
    links = []
    for a_tag in soup.find_all("a", href=True):
        href = a_tag.get("href", "")
        absolute = urljoin(base_url, href)
        if should_skip_url(absolute):
            continue
        text = a_tag.get_text(strip=True) or absolute
        links.append({
            "url": absolute,
            "text": text[:200],
        })

    # Deduplicate links
    seen_urls = set()
    unique_links = []
    for link in links:
        norm = normalize_url(link["url"])
        if norm not in seen_urls:
            seen_urls.add(norm)
            unique_links.append(link)
    links = unique_links

    # Extract images
    images = []
    for img_tag in soup.find_all("img"):
        src = img_tag.get("src") or img_tag.get("data-src") or ""
        if not src:
            continue
        absolute = urljoin(base_url, src)
        if SKIP_URL_PATTERNS.search(absolute):
            continue
        alt = img_tag.get("alt", "") or ""
        images.append({
            "url": absolute,
            "alt": alt[:200],
        })

    return title, body_md, links, images


# ── Image Download ─────────────────────────────────────────────────

def download_image(url: str, dest_dir: Path, session: requests.Session | None = None) -> str | None:
    """Download an image to dest_dir. Returns the local filename or None on failure."""
    if session is None:
        sess = requests.Session()
        sess.headers.update({"User-Agent": USER_AGENT, "Referer": url})
    else:
        sess = session

    try:
        resp = sess.get(url, timeout=REQUEST_TIMEOUT, stream=True)
        resp.raise_for_status()

        content_type = resp.headers.get("Content-Type", "")
        if not content_type.startswith("image/"):
            return None

        # Determine extension
        ext_map = {
            "image/jpeg": ".jpg",
            "image/png": ".png",
            "image/gif": ".gif",
            "image/webp": ".webp",
            "image/svg+xml": ".svg",
            "image/bmp": ".bmp",
        }
        ext = ext_map.get(content_type.split(";")[0].strip(), ".img")

        # Generate unique filename
        content_hash = hashlib.sha256(resp.content).hexdigest()[:12]
        filename = f"{content_hash}{ext}"
        filepath = dest_dir / filename

        if not filepath.exists():
            filepath.write_bytes(resp.content)

        return filename
    except requests.RequestException:
        return None


# ── WebPack Collector ──────────────────────────────────────────────

class WebPackCollector:
    """Basic web content collector. Fetches pages and produces webpack output."""

    def __init__(
        self,
        topic: str,
        urls: list[str],
        output_dir: Path,
        max_depth: int = 0,
        max_pages: int = 50,
        download_images: bool = True,
    ):
        self.topic = topic
        self.start_urls = urls
        self.output_dir = output_dir
        self.max_depth = max_depth
        self.max_pages = max_pages
        self.download_images_flag = download_images

        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})

        self.collected_pages: list[dict] = []
        self.all_links: list[dict] = []
        self.all_images: list[dict] = []
        self.failed_urls: list[dict] = []
        self.seen_urls: set[str] = set()

        # Output subdirectories
        self.snapshots_dir = output_dir / "snapshots"
        self.assets_dir = output_dir / "assets"

    # ── Main collection ─────────────────────────────────────

    def collect(self):
        """Run the collection pipeline."""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.snapshots_dir.mkdir(parents=True, exist_ok=True)
        self.assets_dir.mkdir(parents=True, exist_ok=True)

        # BFS crawl starting from each URL
        queue: list[tuple[str, int]] = [(url, 0) for url in self.start_urls]

        while queue and len(self.collected_pages) < self.max_pages:
            url, depth = queue.pop(0)
            norm = normalize_url(url)

            if norm in self.seen_urls:
                continue
            self.seen_urls.add(norm)

            if should_skip_url(url):
                continue

            # Handle GitHub URLs
            raw_url = github_to_raw(url)
            if raw_url:
                page = self._collect_github_page(url, raw_url)
            else:
                page = self._collect_page(url, depth)

            if page:
                self.collected_pages.append(page)

                # Add discovered links to queue if within depth
                if depth < self.max_depth:
                    for link in page.get("links", []):
                        link_url = link["url"]
                        if is_same_domain(url, link_url):
                            queue.append((link_url, depth + 1))

            time.sleep(REQUEST_DELAY)

    def _collect_page(self, url: str, depth: int) -> dict | None:
        """Collect a single page. Returns page dict or None."""
        print(f"  [{len(self.collected_pages) + 1}/{self.max_pages}] Fetching: {url[:120]}")

        html = fetch_page(url, self.session)
        if html is None:
            self.failed_urls.append({"url": url, "reason": "fetch_failed"})
            print(f"    [FAIL] Could not fetch")
            return None

        title, body_md, links, images = parse_html(html, url)

        if not body_md or len(body_md) < 100:
            self.failed_urls.append({"url": url, "reason": "empty_body"})
            print(f"    [WARN] Content too short ({len(body_md)} chars)")
            return None

        if detect_content_weakness(body_md):
            print(f"    [WARN] Content appears weak (JS-only page?)")

        # Save snapshot
        filename = url_to_filename(url)
        snapshot_path = self.snapshots_dir / f"{filename}.md"

        snapshot_content = f"# {title or filename}\n\n"
        snapshot_content += f"> Source: {url}\n"
        snapshot_content += f"> Collected: {datetime.now(timezone.utc).isoformat()}\n\n"
        snapshot_content += body_md
        snapshot_content += "\n"
        snapshot_path.write_text(snapshot_content, encoding="utf-8")

        # Aggregate links
        self.all_links.extend(links)

        # Download images
        downloaded_images = []
        if self.download_images_flag:
            for img in images:
                local_name = download_image(img["url"], self.assets_dir, self.session)
                img_info = {
                    "url": img["url"],
                    "alt": img["alt"],
                    "local": local_name or "[FAIL]",
                }
                downloaded_images.append(img_info)
                self.all_images.append(img_info)
                if local_name:
                    print(f"    [OK] Image: {local_name}")
        else:
            for img in images:
                self.all_images.append({
                    "url": img["url"],
                    "alt": img["alt"],
                    "local": None,
                })

        print(f"    [OK] {len(body_md)} chars, {len(links)} links, {len(images)} images")

        return {
            "url": url,
            "title": title,
            "depth": depth,
            "body_length": len(body_md),
            "links": links,
            "images": images,
            "downloaded_images": downloaded_images,
            "snapshot": str(snapshot_path.relative_to(self.output_dir)),
        }

    def _collect_github_page(self, original_url: str, raw_url: str) -> dict | None:
        """Collect content from a GitHub raw URL."""
        print(f"  [{len(self.collected_pages) + 1}/{self.max_pages}] GitHub: {original_url[:120]}")

        content = fetch_github_raw(raw_url, self.session)
        if content is None:
            # Try to construct the URL differently -- some repos use 'master' not 'main'
            alt_raw = raw_url.replace("/refs/heads/main/", "/refs/heads/master/")
            content = fetch_github_raw(alt_raw, self.session)
        if content is None:
            self.failed_urls.append({"url": original_url, "reason": "github_fetch_failed"})
            print(f"    [FAIL] Could not fetch from raw")
            return None

        title = url_to_filename(original_url)
        filename = f"github-{title}"
        snapshot_path = self.snapshots_dir / f"{filename}.md"

        # Determine if content is markdown
        is_md = raw_url.lower().endswith((".md", ".markdown", ".rst"))

        snapshot_content = f"# {title}\n\n"
        snapshot_content += f"> Source: {original_url}\n"
        snapshot_content += f"> Raw: {raw_url}\n"
        snapshot_content += f"> Collected: {datetime.now(timezone.utc).isoformat()}\n\n"
        if is_md:
            snapshot_content += content
        else:
            snapshot_content += "```\n"
            snapshot_content += content[:50000]
            snapshot_content += "\n```\n"
        snapshot_content += "\n"
        snapshot_path.write_text(snapshot_content, encoding="utf-8")

        links = []
        # Extract links from markdown
        for match in re.finditer(r'\[([^\]]*)\]\(([^)]+)\)', content):
            link_url = match.group(2)
            if not link_url.startswith(("http://", "https://")):
                link_url = urljoin(f"https://github.com", link_url)
            links.append({"url": link_url, "text": match.group(1)[:200]})

        print(f"    [OK] {len(content)} chars, {len(links)} links")

        return {
            "url": original_url,
            "raw_url": raw_url,
            "title": title,
            "depth": 0,
            "body_length": len(content),
            "links": links,
            "images": [],
            "downloaded_images": [],
            "snapshot": str(snapshot_path.relative_to(self.output_dir)),
            "is_github": True,
        }

    # ── Output generation ──────────────────────────────────

    def write_output(self):
        """Generate all output files."""
        self._write_readme()
        self._write_manifest()
        self._write_link_inventory()
        self._write_image_inventory()
        self._write_reading_map()
        self._write_media_inventory()
        self._write_main_summary()

    def _write_readme(self):
        """Generate README.md for the webpack."""
        lines = [
            f"# {self.topic}",
            "",
            f"> Collected: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
            f"> Collector: PKB web_pack v0.1.0 (basic collector)",
            f"> Pages: {len(self.collected_pages)}",
            f"> Links: {len(self.all_links)}",
            f"> Images: {len(self.all_images)}",
            f"> Failed: {len(self.failed_urls)}",
            "",
            "## Contents",
            "",
        ]
        for page in self.collected_pages:
            title = page.get("title", "Untitled")
            url = page.get("url", "")
            snapshot = page.get("snapshot", "")
            lines.append(f"- [{title}]({snapshot}) -- {url}")

        if self.failed_urls:
            lines.append("")
            lines.append("## Failed URLs")
            lines.append("")
            for f in self.failed_urls:
                lines.append(f"- {f['url']} ({f['reason']})")

        lines.append("")
        lines.append("## Files")
        lines.append("")
        lines.append("- [01-link-inventory.md](01-link-inventory.md)")
        lines.append("- [02-image-inventory.md](02-image-inventory.md)")
        lines.append("- [03-reading-map.md](03-reading-map.md)")
        lines.append("- [04-media-inventory.md](04-media-inventory.md)")
        lines.append("- [manifest.json](manifest.json)")
        lines.append("")
        lines.append("---")
        lines.append("*Generated by PKB web_pack v0.1.0*")
        lines.append("")

        (self.output_dir / "README.md").write_text("\n".join(lines), encoding="utf-8")

    def _write_manifest(self):
        """Generate manifest.json."""
        manifest = {
            "topic": self.topic,
            "collected_at": datetime.now(timezone.utc).isoformat(),
            "collector_version": "0.1.0",
            "collector": "PKB web_pack basic collector",
            "start_urls": self.start_urls,
            "total_pages": len(self.collected_pages),
            "total_links": len(self.all_links),
            "total_images": len(self.all_images),
            "failed_urls": self.failed_urls,
            "pages": [
                {
                    "url": p.get("url"),
                    "title": p.get("title"),
                    "snapshot": p.get("snapshot"),
                    "body_length": p.get("body_length", 0),
                }
                for p in self.collected_pages
            ],
        }
        (self.output_dir / "manifest.json").write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    def _write_link_inventory(self):
        """Generate 01-link-inventory.md."""
        lines = [
            "# Link Inventory",
            "",
            f"Total unique links: {len(self.all_links)}",
            "",
        ]
        # Deduplicate
        seen = set()
        unique = []
        for link in self.all_links:
            norm = normalize_url(link["url"])
            if norm not in seen:
                seen.add(norm)
                unique.append(link)

        for i, link in enumerate(unique, 1):
            lines.append(f"{i}. [{link['text']}]({link['url']})")

        lines.append("")
        lines.append("---")
        lines.append("*Generated by PKB web_pack v0.1.0*")
        lines.append("")
        (self.output_dir / "01-link-inventory.md").write_text("\n".join(lines), encoding="utf-8")

    def _write_image_inventory(self):
        """Generate 02-image-inventory.md."""
        lines = [
            "# Image Inventory",
            "",
            f"Total images: {len(self.all_images)}",
            "",
        ]
        for i, img in enumerate(self.all_images, 1):
            local = img.get("local")
            if local and local != "[FAIL]":
                lines.append(f"{i}. ![{img['alt']}](assets/{local}) -- {img['url']}")
            else:
                lines.append(f"{i}. ![{img['alt']}]({img['url']}) [FAIL]")

        lines.append("")
        lines.append("---")
        lines.append("*Generated by PKB web_pack v0.1.0*")
        lines.append("")
        (self.output_dir / "02-image-inventory.md").write_text("\n".join(lines), encoding="utf-8")

    def _write_reading_map(self):
        """Generate 03-reading-map.md."""
        lines = [
            "# Reading Map",
            "",
            "## Page Graph",
            "",
        ]
        for i, page in enumerate(self.collected_pages):
            title = page.get("title", "Untitled")
            url = page.get("url", "")
            snapshot = page.get("snapshot", "")
            links = page.get("links", [])
            lines.append(f"### {i + 1}. [{title}]({snapshot})")
            lines.append(f"Source: {url}")
            lines.append(f"Links out: {len(links)}")
            lines.append("")

        lines.append("## Link Density")
        lines.append("")
        for page in sorted(self.collected_pages, key=lambda p: len(p.get("links", [])), reverse=True):
            lines.append(f"- {page.get('title', 'Untitled')}: {len(page.get('links', []))} links")

        lines.append("")
        lines.append("---")
        lines.append("*Generated by PKB web_pack v0.1.0*")
        lines.append("")
        (self.output_dir / "03-reading-map.md").write_text("\n".join(lines), encoding="utf-8")

    def _write_media_inventory(self):
        """Generate 04-media-inventory.md."""
        lines = [
            "# Media Inventory",
            "",
            f"Total images: {len(self.all_images)}",
            "",
            "## Images",
            "",
        ]
        downloaded = [img for img in self.all_images if img.get("local") and img["local"] != "[FAIL]"]
        failed = [img for img in self.all_images if not img.get("local") or img["local"] == "[FAIL]"]

        if downloaded:
            lines.append(f"Downloaded: {len(downloaded)}")
            for img in downloaded:
                lines.append(f"- `assets/{img['local']}` -- {img['alt'][:80]}")
            lines.append("")

        if failed:
            lines.append(f"Failed: {len(failed)}")
            for img in failed:
                lines.append(f"- {img['url'][:120]}")

        lines.append("")
        lines.append("---")
        lines.append("*Generated by PKB web_pack v0.1.0*")
        lines.append("")
        (self.output_dir / "04-media-inventory.md").write_text("\n".join(lines), encoding="utf-8")

    def _write_main_summary(self):
        """Generate MAIN-<topic>.md summary file."""
        lines = [
            f"# {self.topic} -- Collection Summary",
            "",
            f"> Collected: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
            f"> Pages: {len(self.collected_pages)}",
            "",
            "## Pages",
            "",
        ]
        for page in self.collected_pages:
            title = page.get("title", "Untitled")
            url = page.get("url", "")
            snapshot = page.get("snapshot", "")
            body_len = page.get("body_length", 0)
            lines.append(f"- [{title}]({snapshot}) ({body_len} chars) -- {url}")

        lines.append("")
        lines.append(f"## Statistics")
        lines.append("")
        lines.append(f"- Total pages: {len(self.collected_pages)}")
        lines.append(f"- Total links: {len(self.all_links)}")
        lines.append(f"- Total images: {len(self.all_images)}")
        lines.append(f"- Failed URLs: {len(self.failed_urls)}")
        lines.append("")
        lines.append("---")
        lines.append("*Generated by PKB web_pack v0.1.0*")
        lines.append("")

        safe_topic = sanitize_filename(self.topic)
        (self.output_dir / f"MAIN-{safe_topic}.md").write_text("\n".join(lines), encoding="utf-8")

    def print_summary(self):
        """Print a human-readable collection summary."""
        print()
        print("=" * 60)
        print(f"  PKB WebPack Collection Complete")
        print("=" * 60)
        print(f"  Topic: {self.topic}")
        print(f"  Pages: {len(self.collected_pages)}")
        print(f"  Links: {len(self.all_links)}")
        print(f"  Images: {len(self.all_images)}")
        print(f"  Failed: {len(self.failed_urls)}")
        print(f"  Output: {self.output_dir}")
        print("=" * 60)

        # JSON report for agent parsing
        report = {
            "topic": self.topic,
            "output_dir": str(self.output_dir),
            "pages_collected": len(self.collected_pages),
            "links_found": len(self.all_links),
            "images_found": len(self.all_images),
            "failed_count": len(self.failed_urls),
            "failed": self.failed_urls,
            "files": [
                "README.md",
                "manifest.json",
                "01-link-inventory.md",
                "02-image-inventory.md",
                "03-reading-map.md",
                "04-media-inventory.md",
            ],
        }
        print()
        print("--- JSON REPORT ---")
        print(json.dumps(report, indent=2, ensure_ascii=False))


# ── CLI ────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="PKB web_pack -- Basic Web Collector (v0.1.0)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python tools/web_pack.py --topic "llm-wiki" --url "https://karpathy.bearblog.dev/llm-wiki/"
    python tools/web_pack.py --topic "research" --url "https://a.com" --url "https://b.com"
    python tools/web_pack.py --topic "repo" --url "https://github.com/user/repo" --max-depth 1
        """,
    )
    parser.add_argument("--topic", required=True, help="Topic name for this webpack")
    parser.add_argument("--url", action="append", dest="urls", required=True,
                        help="URL to collect (repeat for multiple)")
    parser.add_argument("--max-depth", type=int, default=0,
                        help="Maximum link-following depth (default: 0)")
    parser.add_argument("--max-pages", type=int, default=50,
                        help="Maximum pages to collect (default: 50)")
    parser.add_argument("--no-images", action="store_true",
                        help="Skip image downloading")
    parser.add_argument("--output", default=None,
                        help="Output directory (default: raw/webpacks/<date>-<topic>)")

    args = parser.parse_args()

    # Check dependencies
    if not HAS_REQUESTS:
        print("[FAIL] Missing required dependency: requests")
        print("       Run: pip install requests")
        sys.exit(1)
    if not HAS_BS4:
        print("[FAIL] Missing required dependency: beautifulsoup4")
        print("       Run: pip install beautifulsoup4")
        sys.exit(1)
    if not HAS_MARKDOWNIFY:
        print("[WARN] markdownify not installed -- falling back to plain text extraction")
        print("      Run: pip install markdownify for better output")

    # Determine PKB root
    pkb_root = Path(os.environ.get("PKB_ROOT", str(Path(__file__).resolve().parent.parent)))

    # Build output directory
    if args.output:
        output_dir = Path(args.output)
    else:
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        safe_topic = sanitize_filename(args.topic)
        output_dir = pkb_root / "raw" / "webpacks" / f"{date_str}-{safe_topic}"

    # Run collector
    collector = WebPackCollector(
        topic=args.topic,
        urls=args.urls,
        output_dir=output_dir,
        max_depth=args.max_depth,
        max_pages=args.max_pages,
        download_images=not args.no_images,
    )

    collector.collect()
    collector.write_output()
    collector.print_summary()


if __name__ == "__main__":
    main()
