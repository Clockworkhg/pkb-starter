#!/usr/bin/env python3
"""
PKB compat base for z-web-pack — web_research_pack_base (v0.1.0)

Provides the 19 symbols that collect_web_pack.py expects from the missing
1-web-research-pack module. Adapted from PKB web_pack.py core logic.

This is NOT the real 1-web-research-pack. It is a PKB compatibility layer
that makes z-web-pack runnable when the original base module is unavailable.
All third-party z-skills source remains unmodified.

Placed at: .pkb_local/patches/web_research_pack_base.py
Deployed by: zskill_bridge.py run (auto-copies to .agent/skills/1-web-research-pack/scripts/)
"""

from __future__ import annotations

import hashlib
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup, Tag

# -- Optional: markdownify -------------------------------------------------

HAS_MARKDOWNIFY = False
try:
    from markdownify import markdownify as _md_convert
    HAS_MARKDOWNIFY = True
except ImportError:
    pass


# -- Constants -------------------------------------------------------------

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)

SKIP_EXTENSIONS = {
    ".pdf", ".zip", ".tar", ".gz", ".exe", ".dmg", ".iso",
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".webp",
    ".mp4", ".webm", ".mp3", ".wav", ".ogg",
    ".css", ".js", ".map", ".woff", ".woff2", ".ttf", ".eot",
    ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
}

IMAGE_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".webp",
    ".bmp", ".tiff", ".tif", ".apng", ".avif",
}

# Auth-related URL fragments to skip
_AUTH_PATTERNS = re.compile(
    r"/(login|signin|signup|register|auth|oauth|logout|account|profile|"
    r"settings|admin|dashboard|api)",
    re.IGNORECASE,
)

# Content selectors for body extraction
_CONTENT_SELECTORS = [
    "article", '[role="main"]', "main",
    ".post-content", ".article-content", ".entry-content",
    ".content", "#content", ".post", ".article",
    "#mw-content-text", ".markdown-body", "#readme", ".blog-post",
]

# Elements to remove before content extraction
_REMOVE_SELECTORS = [
    "script", "style", "noscript",
    "nav", "header", "footer",
    ".sidebar", ".nav", ".navigation", ".menu",
    ".advertisement", ".ads", ".ad",
    ".cookie-banner", ".cookie-consent", ".gdpr",
    ".social-share", ".comments", "#comments",
    '[role="navigation"]', '[role="banner"]', '[role="contentinfo"]',
]


# -- PageResult ------------------------------------------------------------

class PageResult:
    """Result of collecting a single page."""
    __slots__ = ("url", "final_url", "title", "filename", "status",
                 "depth", "role", "links", "images", "error", "videos")

    def __init__(self, url="", final_url="", title="", filename="",
                 status="ok", depth=0, role="", links=None, images=None,
                 error="", videos=None):
        self.url = url
        self.final_url = final_url
        self.title = title
        self.filename = filename
        self.status = status
        self.depth = depth
        self.role = role
        self.links = links or []
        self.images = images or []
        self.error = error
        self.videos = videos or []


# -- URL utilities ---------------------------------------------------------

def normalize_url(url: str) -> str:
    """Remove fragments and trailing slashes."""
    parsed = urlparse(url)
    return urlunparse((
        parsed.scheme,
        parsed.netloc,
        parsed.path.rstrip("/") or "/",
        parsed.params,
        parsed.query,
        "",
    ))


def slugify(text: str, fallback: str = "untitled", max_len: int = 80) -> str:
    """Convert text to a safe filename slug."""
    if not text:
        text = fallback
    text = re.sub(r'[<>:"/\\|?*]', "-", text)
    text = re.sub(r"\s+", "-", text)
    text = text.strip("-")
    if len(text) > max_len:
        text = text[:max_len].rstrip("-")
    return text or fallback


# -- URL filtering ---------------------------------------------------------

def should_skip_url(url: str, root_hosts: set[str],
                    same_domain_only: bool) -> tuple[bool, str]:
    """Check if a URL should be skipped during crawl."""
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return True, "non-http"

    # Check path extension
    path = parsed.path.lower()
    ext = Path(path).suffix
    if ext in SKIP_EXTENSIONS:
        return True, f"skip-ext:{ext}"
    if ext in IMAGE_EXTENSIONS:
        return True, "asset-link"

    # Check auth patterns
    if _AUTH_PATTERNS.search(parsed.path):
        return True, "auth-page"

    # Same-domain filter
    if same_domain_only and parsed.netloc.lower() not in root_hosts:
        return True, "different-domain"

    return False, ""


# -- Image utilities -------------------------------------------------------

def _choose_img_url(tag: Tag, base_url: str) -> str:
    """Select the best image URL from a tag. Basic implementation;
    z-web-pack monkey-patches an enhanced version with srcset support."""
    for attr in ("data-src", "data-original", "data-lazy-src", "data-actualsrc",
                 "data-echo", "data-url", "src"):
        value = tag.get(attr)
        if value:
            candidate = str(value).strip()
            if candidate and not candidate.lower().startswith("data:"):
                return urljoin(base_url, candidate)
    return ""


def _asset_name(index: int, source_url: str, response=None) -> str:
    """Generate a filename for a downloaded asset."""
    parsed = urlparse(source_url)
    stem = Path(parsed.path).stem or "image"
    stem = re.sub(r'[<>:"/\\|?*]', "-", stem)[:60]
    ext = Path(parsed.path).suffix.lower() or ".img"
    if response is not None:
        ct = (response.headers.get("Content-Type") or "").lower()
        if "png" in ct:
            ext = ".png"
        elif "jpeg" in ct or "jpg" in ct:
            ext = ".jpg"
        elif "gif" in ct:
            ext = ".gif"
        elif "webp" in ct:
            ext = ".webp"
        elif "svg" in ct:
            ext = ".svg"
    return f"{index:04d}-{stem}{ext}"


def download_image(source_url: str, page_url: str,
                   session: requests.Session,
                   assets_dir: Path,
                   global_image_index: list[int]) -> dict:
    """Download an image. Basic implementation;
    z-web-pack monkey-patches an enhanced version with SHA256 dedup + magic bytes."""
    source_url = urljoin(page_url, source_url)
    if not source_url or source_url.startswith("data:"):
        return {"source_url": source_url, "status": "skipped",
                "error": "inline-or-empty-image"}
    try:
        response = session.get(source_url, timeout=20, headers={
            "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
            "Referer": page_url,
        })
        response.raise_for_status()
        content = response.content
        if len(content) < 128:
            return {"source_url": source_url, "status": "skipped",
                    "error": "too-small"}
        if not content:
            return {"source_url": source_url, "status": "failed",
                    "error": "empty-response"}
        global_image_index[0] += 1
        filename = _asset_name(global_image_index[0], source_url, response)
        local_path = assets_dir / filename
        local_path.write_bytes(content)
        return {
            "source_url": source_url,
            "local_path": f"assets/{filename}",
            "status": "ok",
            "bytes": len(content),
        }
    except Exception as exc:
        return {"source_url": source_url, "status": "failed",
                "error": str(exc)[:200]}


# -- Content extraction ----------------------------------------------------

def _extract_article_soup(session: requests.Session, url: str) -> tuple[str, list[dict]]:
    """Fetch page, extract body content, return (markdown, images_list).
    Uses BeautifulSoup + markdownify (NOT readability-lxml)."""
    try:
        resp = session.get(url, timeout=30, allow_redirects=True)
        resp.raise_for_status()
    except Exception as exc:
        return "", [{"error": str(exc)[:200]}]

    final_url = resp.url
    html = resp.text
    soup = BeautifulSoup(html, "lxml" if _has_parser("lxml") else "html.parser")

    # Remove noise elements
    for sel in _REMOVE_SELECTORS:
        for el in soup.select(sel):
            el.decompose()

    # Extract title
    title = ""
    title_tag = soup.find("title")
    if title_tag:
        title = title_tag.get_text(strip=True)

    # Extract body
    body = None
    for sel in _CONTENT_SELECTORS:
        body = soup.select_one(sel)
        if body:
            break
    if body is None:
        body = soup.find("body")
    if body is None:
        return "", [{"error": "no-body"}]

    # Extract images
    images = []
    for img in body.find_all("img"):
        img_url = _choose_img_url(img, final_url)
        alt = img.get("alt", "")
        if img_url:
            images.append({"url": img_url, "alt": str(alt)[:200]})

    # Extract links
    links = []
    for a in body.find_all("a"):
        href = a.get("href")
        if href:
            abs_url = urljoin(final_url, str(href))
            text = a.get_text(strip=True)
            links.append({"url": abs_url, "text": text[:200]})

    # Convert to markdown
    if HAS_MARKDOWNIFY:
        body_html = str(body)
        markdown = _md_convert(body_html, heading_style="ATX", strip=["script", "style"])
    else:
        markdown = body.get_text(separator="\n", strip=True)

    return markdown, images


def _has_parser(name: str) -> bool:
    """Check if a BeautifulSoup parser is available."""
    try:
        BeautifulSoup("", name)
        return True
    except Exception:
        return False


# -- Markdown post-processing ----------------------------------------------

_MD_IMAGE_RE = re.compile(r'!\[([^\]]*)\]\(([^)]+)\)')
_MD_LINK_RE = re.compile(r'\[([^\]]*)\]\(([^)]+)\)')


def localize_markdown_images(
    markdown: str, session: requests.Session, page_url: str,
    assets_dir: Path, global_image_index: list[int],
) -> tuple[str, list[dict]]:
    """Find ![]() references in markdown, download images, replace with local paths."""
    images = []

    def _replace(match):
        alt = match.group(1)
        src = match.group(2)
        if src.startswith("data:") or src.startswith("assets/"):
            return match.group(0)
        result = download_image(src, page_url, session, assets_dir, global_image_index)
        images.append(result)
        if result.get("status") == "ok":
            return f"![{alt}]({result['local_path']})"
        return f"![{alt}]({src})"  # keep original on failure

    new_md = _MD_IMAGE_RE.sub(_replace, markdown)
    return new_md, images


def extract_markdown_links(
    markdown: str, page_url: str, root_hosts: set[str], same_domain_only: bool,
) -> list[dict]:
    """Extract []() links from markdown, filter, return link dicts."""
    links = []
    seen = set()
    for match in _MD_LINK_RE.finditer(markdown):
        text = match.group(1)
        href = match.group(2)
        if href.startswith("assets/") or href.startswith("#"):
            continue
        abs_url = urljoin(page_url, href)
        skip, reason = should_skip_url(abs_url, root_hosts, same_domain_only)
        if skip:
            links.append({"url": abs_url, "text": text[:200], "skipped": True, "reason": reason})
        elif abs_url not in seen:
            seen.add(abs_url)
            links.append({"url": abs_url, "text": text[:200]})
    return links


# -- Page processing -------------------------------------------------------

def page_role(depth: int) -> str:
    """Return the role label for a page at given depth."""
    if depth == 0:
        return "MAIN"
    return "LINKED"


def page_filename(index: int, title: str, depth: int) -> str:
    """Generate a filename for a collected page."""
    role = page_role(depth)
    slug = slugify(title, "page", 60)
    return f"{role}-{index:02d}-{slug}.md"


def write_page_markdown(
    path: Path, title: str, url: str, final_url: str,
    role: str, markdown: str, images: list[dict],
    page_type: str = "MAIN",
    error: str = "",
) -> None:
    """Write a collected page as a markdown file."""
    lines = [
        f"# {title or 'Untitled'}",
        "",
        f"> Source: {url}",
    ]
    if final_url != url:
        lines.append(f"> Final URL: {final_url}")
    lines += [
        f"> Collected: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        f"> Role: {role}",
        "",
    ]
    if error:
        lines.append(f"> Error: {error}")
        lines.append("")
    lines.append(markdown)
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def process_page(
    session: requests.Session, url: str, depth: int,
    out_dir: Path, assets_dir: Path, index: int,
    root_hosts: set[str], same_domain_only: bool,
    global_image_index: list[int],
) -> PageResult:
    """Process a single page: fetch, extract, save, return PageResult."""
    markdown, page_images = _extract_article_soup(session, url)

    if not markdown or len(markdown) < 50:
        return PageResult(
            url=url, final_url=url, title="", filename="",
            status="failed", depth=depth, role=page_role(depth),
            error="empty-or-too-short",
        )

    # Extract title from first # heading or use URL
    title_match = re.search(r'^#\s+(.+)$', markdown, re.MULTILINE)
    title = title_match.group(1).strip() if title_match else urlparse(url).path.strip("/") or url

    final_url = url  # simplified; real implementation would track redirects

    # Localize images
    markdown, localized_images = localize_markdown_images(
        markdown, session, url, assets_dir, global_image_index,
    )

    # Extract links
    links = extract_markdown_links(markdown, url, root_hosts, same_domain_only)

    # Write page
    role = page_role(depth)
    filename = page_filename(index, title, depth)
    write_page_markdown(
        out_dir / filename, title, url, final_url, role,
        markdown, localized_images, page_type=role,
    )

    return PageResult(
        url=url, final_url=final_url, title=title, filename=filename,
        status="ok", depth=depth, role=role, links=links,
        images=localized_images,
    )


# -- Output utilities ------------------------------------------------------

def make_out_dir(out_root: Path, title: str) -> Path:
    """Create a dated output directory: YYYY-MM-DD-title."""
    date_str = datetime.now().strftime("%Y-%m-%d")
    slug = slugify(title, "collection", 60)
    dirname = f"{date_str}-{slug}"
    out_dir = out_root / dirname
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def _escape_table(text: Any) -> str:
    """Escape pipe and newline characters for markdown tables."""
    s = str(text) if text is not None else ""
    return s.replace("|", "\\|").replace("\n", " ").replace("\r", "")


def write_inventory(
    out_dir: Path, title: str, roots: list[str], pages: list[PageResult],
    skipped_queue: list[dict], max_depth: int, max_pages: int,
) -> None:
    """Generate README.md and inventory files for the webpack."""
    # README.md
    readme = [
        f"# {title}",
        "",
        f"> Collected: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        f"> Collector: `1-web-research-pack` (PKB compat base v0.1.0)",
        f"> Pages: {sum(1 for p in pages if p.status == 'ok')}/{len(pages)}",
        "",
        "## Entry URLs",
        "",
    ]
    for r in roots:
        readme.append(f"- {r}")
    readme += [
        "",
        "## Pages",
        "",
    ]
    for p in pages:
        readme.append(
            f"- [{p.title or p.url}]({p.filename}) "
            f"-- depth={p.depth} role={p.role} status={p.status}"
        )
    if skipped_queue:
        readme += ["", "## Skipped", ""]
        for s in skipped_queue:
            readme.append(f"- {s['url']} ({s.get('reason', 'unknown')})")
    readme += [
        "",
        "## Files",
        "",
        "- `README.md`",
        "- `00-research-brief.md`",
        "- `01-link-inventory.md`",
        "- `02-image-inventory.md`",
        "- `03-reading-map.md`",
        "- `04-media-inventory.md`",
        "- `MAIN-*.md` / `LINKED-*.md`",
        "- `assets/`",
        "",
    ]
    (out_dir / "README.md").write_text("\n".join(readme), encoding="utf-8")

    # 00-research-brief.md
    brief = [
        f"# Research Brief: {title}",
        "",
        f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        "## Scope",
        f"- Max depth: {max_depth}",
        f"- Max pages: {max_pages}",
        f"- Entry URLs: {len(roots)}",
        "",
        "## Summary",
        f"- Pages collected: {sum(1 for p in pages if p.status == 'ok')}",
        f"- Failed: {sum(1 for p in pages if p.status != 'ok')}",
        f"- Skipped URLs: {len(skipped_queue)}",
        "",
    ]
    (out_dir / "00-research-brief.md").write_text("\n".join(brief), encoding="utf-8")

    # 01-link-inventory.md
    all_links: list[dict] = []
    for p in pages:
        for link in p.links:
            all_links.append(link)
    link_lines = [
        "# Link Inventory",
        "",
        f"| # | URL | Text | Page | Skipped |",
        "| --- | --- | --- | --- | --- |",
    ]
    for i, link in enumerate(all_links, 1):
        skipped = link.get("skipped", False)
        link_lines.append(
            f"| {i} | {_escape_table(link.get('url', ''))} | "
            f"{_escape_table(link.get('text', ''))} | "
            f"{_escape_table(link.get('page', ''))} | "
            f"{'yes' if skipped else ''} |"
        )
    if not all_links:
        link_lines.append("| - | no links found | - | - | - |")
    (out_dir / "01-link-inventory.md").write_text("\n".join(link_lines) + "\n", encoding="utf-8")

    # 02-image-inventory.md
    all_images: list[dict] = []
    for p in pages:
        for img in p.images:
            img_with_page = dict(img)
            img_with_page["page"] = p.filename or p.url
            all_images.append(img_with_page)
    img_lines = [
        "# Image Inventory",
        "",
        f"| # | Source URL | Local Path | Status | Page |",
        "| --- | --- | --- | --- | --- |",
    ]
    for i, img in enumerate(all_images, 1):
        img_lines.append(
            f"| {i} | {_escape_table(img.get('source_url', ''))} | "
            f"{_escape_table(img.get('local_path', ''))} | "
            f"{_escape_table(img.get('status', ''))} | "
            f"{_escape_table(img.get('page', ''))} |"
        )
    if not all_images:
        img_lines.append("| - | no images found | - | - | - |")
    (out_dir / "02-image-inventory.md").write_text("\n".join(img_lines) + "\n", encoding="utf-8")

    # 03-reading-map.md
    rmap = [
        "# Reading Map",
        "",
        f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        "## Page Graph",
        "",
        "```",
    ]
    for p in pages:
        rmap.append(f"{p.filename} (depth={p.depth}, role={p.role})")
        for link in p.links[:5]:
            rmap.append(f"  -> {_escape_table(link.get('url', ''))}")
    rmap += ["```", ""]
    (out_dir / "03-reading-map.md").write_text("\n".join(rmap), encoding="utf-8")
