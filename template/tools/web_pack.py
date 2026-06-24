#!/usr/bin/env python3
"""
PKB web_pack v3 — Windows 版 z-web-pack 对齐采集器

基于 tjxj/z-skills z-web-pack (1-web-pack) 的功能标准重写。

能力对齐:
  - 图片: 16 项完整能力 (srcset, magic bytes, SHA256 去重, tracking 过滤...)
  - 视频: yt-dlp 平台视频 + <video> 直链下载
  - 正文: readability-lxml → trafilatura → BeautifulSoup → Jina 四级 fallback
  - GitHub: API → git clone --depth 1 → Jina 兜底 (v2 Collector)
  - 输出: 标准 z-web-pack 结构 + manifest.json + snapshots/
  - 模式: --mode full (默认) / --mode safe

用法:
    python tools/web_pack.py --topic "主题" --url "https://..."
    python tools/web_pack.py --topic "主题" --url "u1" --url "u2" --mode full
    python tools/web_pack.py --topic "主题" --url "u1" --mode safe --videos off

依赖:
    pip install requests beautifulsoup4 markdownify readability-lxml trafilatura
    pip install yt-dlp  # 可选，用于平台视频下载

对齐标准:
    z-web-pack SKILL.md + scripts/collect_web_pack.py
    skills/_vendor/tjxj-z-skills/z-web-pack/
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse, urlunparse


def configure_stdout_utf8() -> None:
    """防御性配置 stdout 为 UTF-8，使 Windows GBK 终端支持 emoji 和中文。

    仅在 stdout 支持 reconfigure 且可调用时设置。
    捕获 ValueError（编码不可用）和 OSError（stdout 被重定向/管道化时可能抛出）。
    不在 pytest 捕获 stdout 时报错。
    """
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if callable(reconfigure):
        try:
            reconfigure(encoding="utf-8")
        except (ValueError, OSError):
            pass

# ── PKB 内部模块 ──
# 确保 tools/ 目录在 sys.path 上（兼容 python tools/web_pack.py 和 python -m tools.web_pack）
_TOOLS_DIR = Path(__file__).resolve().parent
if str(_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOLS_DIR))

try:
    from content_quality import assess_article, QualityIssue, ISSUE_LABELS
    HAS_CONTENT_QUALITY = True
except ImportError:
    HAS_CONTENT_QUALITY = False

try:
    from playwright_renderer import (
        PlaywrightRenderer, RenderOptions, RenderResult,
        HAS_PLAYWRIGHT as _HAS_PW,
    )
    HAS_PLAYWRIGHT = _HAS_PW
except ImportError:
    HAS_PLAYWRIGHT = False
    PlaywrightRenderer = None  # type: ignore[assignment]
    RenderOptions = None  # type: ignore[assignment]
    RenderResult = None  # type: ignore[assignment]

try:
    from selection_engine import (
        ExtractionCandidate,
        BestNetworkCandidate,
        SelectionResult,
        select_best_network_candidate,
        select_best_result,
    )
    HAS_SELECTION_ENGINE = True
except ImportError:
    HAS_SELECTION_ENGINE = False
    ExtractionCandidate = None  # type: ignore[assignment]
    BestNetworkCandidate = None  # type: ignore[assignment]
    SelectionResult = None  # type: ignore[assignment]
    select_best_network_candidate = None  # type: ignore[assignment]
    select_best_result = None  # type: ignore[assignment]

# ───────────────────────────────────────────────────────────────
# 依赖检测
# ───────────────────────────────────────────────────────────────

HAS_REQUESTS = False
HAS_BS4 = False
HAS_MARKDOWNIFY = False
HAS_READABILITY = False
HAS_TRAFILATURA = False
HAS_YTDLP = False

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

try:
    from readability import Document as ReadabilityDocument
    HAS_READABILITY = True
except ImportError:
    pass

try:
    import trafilatura
    HAS_TRAFILATURA = True
except ImportError:
    pass

YTDLP_PATH = shutil.which("yt-dlp")
if YTDLP_PATH:
    HAS_YTDLP = True


# ───────────────────────────────────────────────────────────────
# 配置常量
# ───────────────────────────────────────────────────────────────

PKB_ROOT = Path(os.environ.get("PKB_ROOT", r"<PKB_ROOT>"))
WEBPACKS_DIR = PKB_ROOT / "raw" / "webpacks"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

REQUEST_TIMEOUT = 30
DEFAULT_DELAY = 0.2
MIN_CONTENT_LENGTH = 350  # 可见文字少于此值触发 Jina 兜底

# ───────────────────────────────────────────────────────────────
# 图片配置
# ───────────────────────────────────────────────────────────────

IMAGE_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp", ".bmp",
    ".ico", ".avif", ".apng", ".tiff", ".tif",
}

IMAGE_LAZY_ATTRS = [
    "data-src", "data-original", "data-lazy-src",
    "data-actualsrc", "data-echo", "data-url", "src",
]

MAGIC_BYTES = [
    (b"\xff\xd8\xff", ".jpg"),
    (b"\x89PNG\r\n\x1a\n", ".png"),
    (b"GIF8", ".gif"),
]

TRACKING_IMG_RE = re.compile(
    r"(pixel|spacer|blank\.|1x1|tracking|beacon|impression|"
    r"shields\.io|badge\.svg|badgen\.net|herokuapp\.com/badge|favicon)",
    re.IGNORECASE,
)

# ───────────────────────────────────────────────────────────────
# 视频配置
# ───────────────────────────────────────────────────────────────

VIDEO_EXTENSIONS = {".mp4", ".webm", ".mov", ".m4v", ".mkv", ".flv", ".ogv"}

PLATFORM_VIDEO_RE = re.compile(
    r"("
    r"(?:www\.|m\.)?youtube\.com/(?:watch\?|embed/|shorts/|v/)"
    r"|youtu\.be/"
    r"|(?:www\.)?bilibili\.com/video/"
    r"|player\.bilibili\.com/player\.html"
    r"|(?:www\.)?vimeo\.com/\d+"
    r"|player\.vimeo\.com/video/"
    r"|(?:twitter|x)\.com/[^/]+/status/\d+"
    r"|(?:www\.)?tiktok\.com/@[^/]+/video/"
    r"|\.m3u8(?:\?|$)"
    r")",
    re.IGNORECASE,
)

# ───────────────────────────────────────────────────────────────
# GitHub 配置
# ───────────────────────────────────────────────────────────────

GITHUB_PRIORITY_FILES = [
    "README.md", "readme.md", "Readme.md",
    "SKILL.md", "skill.md",
    "AGENTS.md", "agents.md",
    "CLAUDE.md", "claude.md",
    "COMMANDS.md", "commands.md",
    "package.json", "pyproject.toml", "requirements.txt",
    "Cargo.toml", "go.mod", "Makefile", "Dockerfile",
]

GITHUB_PRIORITY_DIRS = ["docs", "examples", "scripts", "src", "tools"]

GITHUB_REPO_RE = re.compile(r"^https?://github\.com/([\w.-]+)/([\w.-]+?)(?:\.git)?/?$")
GITHUB_BLOB_RE = re.compile(r"^https?://github\.com/([\w.-]+)/([\w.-]+)/blob/([^/]+)/(.+)$")
GITHUB_TREE_RE = re.compile(r"^https?://github\.com/([\w.-]+)/([\w.-]+)/tree/([^/]+)/(.+)$")

# ───────────────────────────────────────────────────────────────
# URL 过滤配置
# ───────────────────────────────────────────────────────────────

SKIP_EXTENSIONS = {
    ".css", ".js", ".woff", ".woff2", ".ttf", ".eot", ".otf",
    ".map", ".jsonld", ".xml",
}

SENSITIVE_URL_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in [
        r'/login', r'/signin', r'/signup', r'/sign-in', r'/sign-up',
        r'/auth', r'/oauth', r'/session', r'/cookie',
        r'/account', r'/profile', r'/settings',
        r'/admin', r'/dashboard', r'/billing', r'/checkout',
        r'/privacy', r'/terms', r'/tos',
    ]
]

SKIP_LINK_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in [
        r'/login', r'/signin', r'/signup', r'/sign-in', r'/sign-up',
        r'/register', r'/auth', r'/oauth',
        r'/privacy', r'/terms', r'/tos', r'/legal',
        r'/jobs?', r'/careers?', r'/hiring', r'/recruit',
        r'/advertise?', r'/sponsor',
        r'/share', r'/rss', r'/feed', r'/subscribe',
        r'/comment', r'/reply',
        r'avatar', r'logo', r'favicon', r'icon',
        r'\.(jpg|jpeg|png|gif|svg|webp|ico|css|js|woff2?|ttf|eot)(\?|$|#)',
        r'^#', r'^javascript:', r'^mailto:', r'^tel:',
        r'/cdn-cgi/', r'/__/', r'/wp-json/', r'/wp-admin/',
        r'facebook\.com', r'twitter\.com', r'x\.com', r'linkedin\.com',
        r'instagram\.com', r'youtube\.com', r'tiktok\.com',
    ]
]

PRIORITY_LINK_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in [
        r'github\.com/[^/]+/[^/]+$',
        r'github\.com/[^/]+/[^/]+/blob/.*\.md$',
        r'github\.com/[^/]+/[^/]+/tree/',
        r'github\.com/[^/]+/[^/]+/raw/',
        r'readme\.md$', r'docs?/', r'examples?/',
        r'arxiv\.org/(abs|pdf)/',
        r'openreview\.net/',
        r'paperswithcode\.com/',
        r'doi\.org/',
        r'scholar\.google\.', r'semanticscholar\.org/',
        r'python\.org/', r'pypi\.org/', r'npmjs\.com/',
        r'rust-lang\.org/', r'golang\.org/',
        r'blog\.', r'dev\.to/', r'medium\.com/',
        r'docs\.', r'documentation', r'guide',
        r'tutorial', r'example', r'sample',
        r'awesome-', r'/awesome/',
        r'wikipedia\.org/wiki/',
        r'stackoverflow\.com/', r'stackexchange\.com/',
    ]
]

# 正文噪音选择器
NOISE_SELECTORS = [
    "script", "style", "noscript", "iframe", "object", "embed",
    "nav", "footer", "header:not(article header):not(main header)",
    "aside", ".sidebar", ".side-bar", "#sidebar",
    ".advertisement", ".ad", ".ads", ".sponsor", ".banner",
    ".cookie-banner", ".cookie-consent", ".gdpr",
    ".login", ".signin", ".signup", ".register",
    ".comment", ".comments", "#comments", ".discussion",
    ".recommended", ".related-posts", ".related-articles",
    ".social-share", ".social-media", ".share-buttons",
    ".newsletter", ".subscribe", ".subscription",
    ".popup", ".modal", ".overlay",
    ".pagination", ".breadcrumb",
    '[role="navigation"]', '[role="banner"]', '[role="contentinfo"]',
    '[aria-label*="navigation" i]', '[aria-label*="footer" i]',
]

# 正文内容选择器
CONTENT_SELECTORS = [
    "article", "main", '[role="main"]',
    ".markdown-body", ".markdown",
    ".post-content", ".article-content", ".entry-content",
    ".content", "#content",
    ".readme", "#readme", ".repository-content",
    ".post-body", ".article-body",
    ".doc-content", ".documentation-content",
    ".tutorial-content", ".guide-content",
    "#mw-content-text",
    ".post", ".article", ".blog-post",
]

# Jina WEAK_MARKERS (from z-web-pack)
WEAK_MARKERS = [
    "enable javascript",
    "javascript is not available",
    "this browser is no longer supported",
    "something went wrong",
    "please enable cookies",
    "access denied",
    "checking your browser",
    "just a moment",
    "performing security verification",
    "requiring captcha",
    "verify you are human",
    "target url returned error 403",
    "log in to",
    "sign up now",
]

JINA_CLEAN_DROP_EXACT = {
    "Don't miss what's happening",
    "Don't miss what's happening",
    "People on X are the first to know.",
    "See new posts",
    "Sign up with Apple",
    "Create account",
    "Appearance settings",
    "Toggle navigation",
}


# ───────────────────────────────────────────────────────────────
# 工具函数
# ───────────────────────────────────────────────────────────────

_WIN_ILLEGAL = re.compile(r'[\\/:*?"<>|]')


def slugify(text: str, fallback: str = "untitled", max_len: int = 80) -> str:
    """转换为 Windows 安全的文件名 slug。"""
    text = text.strip() if text else fallback
    text = _WIN_ILLEGAL.sub('', text)
    text = re.sub(r'[\s\-—]+', '-', text)
    text = re.sub(r'[^\w\-]', '', text)
    text = re.sub(r'-{2,}', '-', text)
    text = text.strip('-').lower()
    if not text:
        text = fallback
    return text[:max_len]


def normalize_url(url: str) -> str:
    """规范化 URL 用于去重（去 fragment）。"""
    parsed = urlparse(url)
    return urlunparse(parsed._replace(fragment=""))


def is_github_url(url: str) -> bool:
    """判断是否为 GitHub URL。"""
    return 'github.com' in urlparse(url).netloc


def detect_github_url_type(url: str) -> dict | None:
    """识别 GitHub URL 类型。返回 {type, owner, repo, branch, path} 或 None。"""
    parsed = urlparse(url)
    if 'github.com' not in parsed.netloc and 'raw.githubusercontent.com' not in parsed.netloc:
        return None

    # raw 文件
    raw_match = re.match(r'^/([^/]+)/([^/]+)/([^/]+)/(.+)$', parsed.path)
    if 'raw.githubusercontent.com' in parsed.netloc and raw_match:
        return {
            "type": "raw", "owner": raw_match.group(1),
            "repo": raw_match.group(2), "branch": raw_match.group(3),
            "path": raw_match.group(4),
        }

    # blob 文件页
    blob_match = GITHUB_BLOB_RE.match(url)
    if blob_match:
        return {
            "type": "blob", "owner": blob_match.group(1),
            "repo": blob_match.group(2), "branch": blob_match.group(3),
            "path": blob_match.group(4),
        }

    # tree 目录页
    tree_match = GITHUB_TREE_RE.match(url)
    if tree_match:
        return {
            "type": "tree", "owner": tree_match.group(1),
            "repo": tree_match.group(2), "branch": tree_match.group(3),
            "path": tree_match.group(4),
        }

    # 仓库主页
    repo_match = GITHUB_REPO_RE.match(url)
    if repo_match:
        return {
            "type": "repo", "owner": repo_match.group(1),
            "repo": repo_match.group(2).removesuffix('.git'),
            "branch": "main", "path": "",
        }

    return None


def is_sensitive_url(url: str) -> tuple[bool, str]:
    """检查 URL 是否指向敏感页面。"""
    parsed = urlparse(url)
    path = parsed.path.lower()
    for pat in SENSITIVE_URL_PATTERNS:
        if pat.search(path):
            return True, pat.pattern
    return False, ""


def should_skip_link(url: str) -> tuple[bool, str]:
    """判断链接是否应该跳过。"""
    parsed = urlparse(url)
    if parsed.scheme not in ('http', 'https'):
        return True, f"非 HTTP 协议: {parsed.scheme}"
    path_query = parsed.path.lower() + ('?' + parsed.query.lower() if parsed.query else '')
    ext = Path(parsed.path).suffix.lower()
    if ext in SKIP_EXTENSIONS or ext in IMAGE_EXTENSIONS:
        return True, f"静态资源: {ext}"
    for pat in SKIP_LINK_PATTERNS:
        if pat.search(path_query):
            return True, f"匹配跳过: {pat.pattern}"
    return False, ""


def is_priority_link(url: str) -> tuple[bool, str]:
    """判断链接是否为优先展开的高价值链接。"""
    url_lower = url.lower()
    for pat in PRIORITY_LINK_PATTERNS:
        if pat.search(url_lower):
            return True, f"匹配优先: {pat.pattern}"
    return False, ""


def escape_table(value: Any) -> str:
    """转义 Markdown 表格中的特殊字符。"""
    s = str(value if value is not None else "")
    return s.replace("|", "\\|").replace("\n", " ")


# ───────────────────────────────────────────────────────────────
# 图片处理模块 (z-web-pack 16 项能力)
# ───────────────────────────────────────────────────────────────

def _srcset_largest(srcset: str) -> str:
    """从 srcset 中选取最大宽度档的 URL。"""
    best, best_w = "", -1
    for part in str(srcset).split(","):
        bits = part.strip().split()
        if not bits:
            continue
        width = 0
        if len(bits) > 1 and bits[1].endswith("w"):
            try:
                width = int(float(bits[1][:-1]))
            except ValueError:
                width = 0
        if width > best_w:
            best, best_w = bits[0], width
    return best


def _looks_like_placeholder(value: str) -> bool:
    """判断图片 URL 是否为占位图。"""
    lowered = value.lower()
    return (
        lowered.startswith("data:")
        or "placeholder" in lowered
        or "/loading." in lowered
        or lowered.endswith("blank.gif")
    )


def choose_best_img_url(tag, base_url: str) -> str:
    """
    选择最佳图片 URL (对齐 z-web-pack patched_choose_img_url)。

    优先级链: srcset最大档 → picture>source srcset → 懒加载属性 → src
    """
    candidates: list[str] = []

    # 1. img srcset (最大档)
    srcset = tag.get("srcset") or tag.get("data-srcset")
    if srcset:
        largest = _srcset_largest(str(srcset))
        if largest:
            candidates.append(largest)

    # 2. picture > source srcset
    picture = tag.find_parent("picture") if isinstance(tag, Tag) else None
    if picture is not None:
        for source in picture.find_all("source"):
            source_set = source.get("srcset") or source.get("data-srcset")
            if source_set:
                largest = _srcset_largest(str(source_set))
                if largest:
                    candidates.append(largest)
                break

    # 3. 懒加载属性 (覆盖所有已知懒加载库)
    for attr in IMAGE_LAZY_ATTRS:
        value = tag.get(attr)
        if value:
            candidates.append(str(value))

    # 4. 过滤占位图，返回第一个有效 URL
    for candidate in candidates:
        candidate = candidate.strip()
        if not candidate or _looks_like_placeholder(candidate):
            continue
        return urljoin(base_url, candidate)

    return ""


def _is_tracking_or_decorative(tag_or_none, url: str) -> bool:
    """判断图片是否为追踪像素或装饰图。"""
    if TRACKING_IMG_RE.search(url):
        return True
    if isinstance(tag_or_none, Tag):
        for attr in ("width", "height"):
            value = str(tag_or_none.get(attr) or "").strip().rstrip("px")
            if value.isdigit() and int(value) <= 3:
                return True
    return False


def _sniff_ext(content: bytes, fallback: str) -> str:
    """通过文件魔数 (magic bytes) 纠正扩展名。"""
    head = content[:64]
    for magic, ext in MAGIC_BYTES:
        if head.startswith(magic):
            return ext
    if head.startswith(b"RIFF") and b"WEBP" in head[:16]:
        return ".webp"
    if head[4:12] in (b"ftypavif", b"ftypavis"):
        return ".avif"
    if head.lstrip().startswith((b"<svg", b"<?xml")):
        return ".svg"
    return fallback


def download_image(
    img_url: str,
    page_url: str,
    session: requests.Session,
    assets_dir: Path,
    img_counter: list[int],
    image_hashes: dict[str, str],
    max_image_mb: float = 20.0,
    mode: str = "full",
) -> dict:
    """
    下载单张图片 (对齐 z-web-pack patched_download_image)。

    增强级 (mode=full):
      - Referer 防盗链
      - Magic bytes 纠错
      - SHA256 去重
      - Tracking pixel / badge 过滤
      - Content-Type 验证
    """
    full_url = urljoin(page_url, img_url)
    if not full_url or full_url.startswith("data:"):
        return {"source_url": img_url, "status": "skipped", "error": "inline-or-empty"}

    # tracking 过滤
    if mode == "full" and _is_tracking_or_decorative(None, full_url):
        return {"source_url": full_url, "status": "skipped", "error": "tracking-or-decorative"}

    try:
        headers = {
            "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
            "User-Agent": USER_AGENT,
        }
        if mode == "full":
            headers["Referer"] = page_url

        resp = session.get(full_url, timeout=20, headers=headers)
        resp.raise_for_status()
        content = resp.content

        limit = int(max_image_mb * 1024 * 1024)
        if len(content) > limit:
            return {"source_url": full_url, "status": "failed",
                    "error": f"image-larger-than-{max_image_mb}MB"}
        if len(content) < 128:
            return {"source_url": full_url, "status": "skipped", "error": "too-small"}

        # Content-Type 验证
        content_type = (resp.headers.get("Content-Type") or "").lower()
        path_ext = Path(urlparse(full_url).path).suffix.lower()

        if mode == "full":
            sniffed = _sniff_ext(content, "")
            if "image" not in content_type and path_ext not in IMAGE_EXTENSIONS and not sniffed:
                return {"source_url": full_url, "status": "failed",
                        "error": f"not-image: {content_type or 'unknown'}"}
        else:
            sniffed = ""

        # SHA256 去重
        if mode == "full":
            digest = hashlib.sha256(content).hexdigest()
            if digest in image_hashes:
                return {"source_url": full_url, "local_path": image_hashes[digest],
                        "status": "ok", "bytes": len(content), "note": "dedup"}
        else:
            digest = None

        # 确定扩展名
        ext = sniffed or path_ext or ".jpg"
        img_counter[0] += 1
        filename = f"image-{img_counter[0]:03d}{ext}"
        if ext and not filename.lower().endswith(ext):
            filename = str(Path(filename).with_suffix(ext))

        # 写入
        local_path = assets_dir / filename
        local_path.write_bytes(content)

        if mode == "full" and digest:
            image_hashes[digest] = f"assets/{filename}"

        return {
            "source_url": full_url,
            "local_path": f"assets/{filename}",
            "status": "ok",
            "bytes": len(content),
            "width": None,
            "height": None,
            "content_type": content_type.split(";")[0] if content_type else "",
        }

    except Exception as exc:
        return {"source_url": full_url, "status": "failed", "error": str(exc)[:200]}


def extract_images_from_html(soup, base_url: str, mode: str = "full") -> list[dict]:
    """从 HTML soup 中提取所有图片 (对齐 z-web-pack 完整属性覆盖)。"""
    images = []
    seen = set()

    for img in soup.find_all("img"):
        # 优先用增强选择器
        best_url = choose_best_img_url(img, base_url) if mode == "full" else ""
        if not best_url:
            # fallback: 简单属性扫描
            for attr in ("src", "data-src", "data-lazy-src"):
                v = img.get(attr)
                if v:
                    best_url = urljoin(base_url, str(v))
                    break

        if best_url and best_url not in seen:
            seen.add(best_url)
            # 基础过滤 (safe 模式也做)
            if mode == "full" and _is_tracking_or_decorative(img, best_url):
                continue
            if _looks_like_placeholder(best_url):
                continue

            images.append({
                "url": best_url,
                "alt": (img.get("alt") or "").strip(),
                "width": img.get("width", ""),
                "height": img.get("height", ""),
            })

    # CSS background-image (仅 full 模式)
    if mode == "full":
        for el in soup.find_all(style=True):
            style = el.get("style", "")
            for match in re.finditer(r'background-image:\s*url\(["\']?([^"\'()]+)["\']?\)', style, re.I):
                bg_url = urljoin(base_url, match.group(1).strip())
                if bg_url not in seen and not _is_tracking_or_decorative(None, bg_url):
                    seen.add(bg_url)
                    images.append({"url": bg_url, "alt": "background-image", "width": "", "height": ""})

    return images


def extract_images_from_markdown(markdown: str, base_url: str) -> list[dict]:
    """从 Markdown 中提取图片。"""
    images = []
    seen = set()
    for match in re.finditer(r'!\[([^\]]*)\]\(((?:https?:)?//[^\)]+)\)', markdown):
        img_url = match.group(2)
        if img_url not in seen:
            seen.add(img_url)
            images.append({"url": img_url, "alt": match.group(1).strip()})
    return images


def localize_markdown_images(
    markdown: str, page_url: str, session: requests.Session,
    assets_dir: Path, img_counter: list[int],
    image_hashes: dict[str, str], max_image_mb: float = 20.0, mode: str = "full",
) -> tuple[str, list[dict]]:
    """将 Markdown 中的外部图片本地化。返回 (新markdown, 图片记录列表)。"""
    img_records = []
    seen = set()

    def _replace(match):
        nonlocal img_records
        alt = match.group(1)
        img_url = match.group(2).strip()
        if img_url in seen:
            return match.group(0)
        seen.add(img_url)
        result = download_image(img_url, page_url, session, assets_dir,
                                img_counter, image_hashes, max_image_mb, mode)
        result["alt"] = alt
        img_records.append(result)
        if result.get("status") == "ok":
            result["source_page"] = page_url
            return f"![{alt}]({result['local_path']})"
        result["source_page"] = page_url
        return match.group(0)

    new_md = re.sub(r'!\[([^\]]*)\]\(([^)\s]+)\)', _replace, markdown)
    return new_md, img_records


def absolutize_markdown_images(markdown: str, raw_base: str) -> str:
    """将 Markdown 中的相对图片路径绝对化 (用于 GitHub raw 内容)。"""
    def _fix(match):
        alt, target = match.group(1), match.group(2).strip()
        if target.startswith(("http://", "https://", "data:")):
            return match.group(0)
        return f"![{alt}]({urljoin(raw_base, target.lstrip('./'))})"
    return re.sub(r"!\[([^\]]*)\]\(([^)\s]+)\)", _fix, markdown)


# ───────────────────────────────────────────────────────────────
# 视频/媒体模块 (对齐 z-web-pack)
# ───────────────────────────────────────────────────────────────

def collect_videos_from_html(html: str, final_url: str) -> list[str]:
    """从 HTML 中收集所有视频 URL (对齐 z-web-pack collect_videos_from_html)。"""
    urls: list[str] = []
    try:
        soup = BeautifulSoup(html, "lxml")
    except Exception:
        return urls

    # <video src/data-src>
    for video in soup.find_all("video"):
        for attr in ("src", "data-src"):
            if video.get(attr):
                urls.append(urljoin(final_url, str(video[attr])))
        for source in video.find_all("source"):
            for attr in ("src", "data-src"):
                if source.get(attr):
                    urls.append(urljoin(final_url, str(source[attr])))

    # <iframe>/<embed> 平台视频
    for frame in soup.find_all(["iframe", "embed"]):
        src = frame.get("src") or frame.get("data-src") or ""
        if src and PLATFORM_VIDEO_RE.search(str(src)):
            urls.append(urljoin(final_url, str(src)))

    # <a href> 直链视频
    for anchor in soup.find_all("a", href=True):
        href = urljoin(final_url, str(anchor["href"]))
        if Path(urlparse(href).path).suffix.lower() in VIDEO_EXTENSIONS:
            urls.append(href)

    # 去重
    deduped: list[str] = []
    for url in urls:
        if url.startswith(("http://", "https://")) and url not in deduped:
            deduped.append(url)
    return deduped


def download_direct_video(
    session: requests.Session, url: str, page_url: str,
    assets_dir: Path, video_counter: list[int], max_video_mb: float = 300.0,
) -> dict:
    """
    下载直链视频 (对齐 z-web-pack download_direct_video)。

    流式下载，实时检查大小限制。
    """
    record = {"url": url, "kind": "direct", "status": "failed", "local_path": ""}
    try:
        resp = session.get(url, timeout=30, stream=True,
                          headers={"Referer": page_url})
        resp.raise_for_status()
        limit = int(max_video_mb * 1024 * 1024)
        length = resp.headers.get("Content-Length")
        if length and int(length) > limit:
            record["error"] = f"video-larger-than-{max_video_mb}MB"
            return record

        video_counter[0] += 1
        ext = Path(urlparse(url).path).suffix.lower() or ".mp4"
        stem = slugify(Path(urlparse(url).path).stem or "video", "video", 40)
        filename = f"video-{video_counter[0]:02d}-{stem}{ext}"
        target = assets_dir / filename

        size = 0
        with open(target, "wb") as handle:
            for chunk in resp.iter_content(1024 * 256):
                size += len(chunk)
                if size > limit:
                    handle.close()
                    target.unlink(missing_ok=True)
                    record["error"] = f"video-larger-than-{max_video_mb}MB"
                    return record
                handle.write(chunk)

        record["status"] = "ok"
        record["local_path"] = f"assets/{filename}"
        record["bytes"] = size
        return record

    except Exception as exc:
        record["error"] = str(exc)[:200]
        return record


def download_platform_video(
    url: str, assets_dir: Path, video_counter: list[int],
    max_video_mb: float = 300.0, browser_cookies: str = "",
    download_media: bool = False,
) -> dict:
    """
    下载平台视频 (对齐 z-web-pack download_platform_video)。

    使用 yt-dlp，可带字幕和封面。
    """
    record = {"url": url, "kind": "platform", "status": "failed", "local_path": ""}

    if not download_media:
        record["status"] = "skipped"
        record["error"] = "use --download-media to download platform videos"
        return record

    if not HAS_YTDLP:
        record["error"] = "yt-dlp not installed"
        return record

    video_counter[0] += 1
    template = str(assets_dir / f"video-{video_counter[0]:02d}-%(title).50s.%(ext)s")
    cmd = [
        "yt-dlp", "--no-playlist", "--no-progress", "--restrict-filenames",
        "--max-filesize", f"{int(max_video_mb)}M",
        "-f", "bv*[height<=1080]+ba/b[height<=1080]/b",
        "--merge-output-format", "mp4",
        "--write-subs", "--write-auto-subs", "--sub-langs", "en,zh-CN,zh",
        "--write-thumbnail",
        "--convert-thumbnails", "jpg",
        "-o", template, url,
    ]
    if browser_cookies:
        cmd[1:1] = ["--cookies-from-browser", browser_cookies]

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
        produced = sorted(assets_dir.glob(f"video-{video_counter[0]:02d}-*"))
        if proc.returncode == 0 and produced:
            # 找主视频文件
            video_files = [p for p in produced if p.suffix in VIDEO_EXTENSIONS or p.suffix == '.mp4']
            if video_files:
                video_file = video_files[0]
                record["status"] = "ok"
                record["local_path"] = f"assets/{video_file.name}"
                record["bytes"] = video_file.stat().st_size
                # 记录字幕和封面
                subtitles = [p for p in produced if p.suffix in ('.vtt', '.srt')]
                if subtitles:
                    record["subtitles"] = [f"assets/{p.name}" for p in subtitles]
                thumbnails = [p for p in produced if p.suffix in ('.jpg', '.webp', '.png')]
                if thumbnails:
                    record["thumbnail"] = f"assets/{thumbnails[0].name}"
        else:
            tail = (proc.stderr or proc.stdout or "").strip().splitlines()
            record["error"] = (tail[-1] if tail else f"yt-dlp-exit-{proc.returncode}")[:200]
        return record

    except subprocess.TimeoutExpired:
        record["error"] = "yt-dlp timeout (900s)"
        return record
    except Exception as exc:
        record["error"] = str(exc)[:200]
        return record


def get_media_metadata(url: str, browser_cookies: str = "") -> dict | None:
    """提取媒体元数据（使用 yt-dlp --dump-json，不下载）。"""
    if not HAS_YTDLP:
        return None
    cmd = ["yt-dlp", "--dump-json", "--no-playlist", "--no-progress", url]
    if browser_cookies:
        cmd[1:1] = ["--cookies-from-browser", browser_cookies]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if proc.returncode == 0 and proc.stdout.strip():
            return json.loads(proc.stdout)
    except Exception:
        pass
    return None


def handle_videos(
    video_urls: list[str], page_url: str, session: requests.Session,
    assets_dir: Path, video_counter: list[int], video_seen: set[str],
    videos_mode: str = "direct", max_video_mb: float = 300.0,
    browser_cookies: str = "", download_media: bool = False,
) -> list[dict]:
    """处理页面视频 (对齐 z-web-pack handle_page_videos)。"""
    records: list[dict] = []
    if videos_mode == "off":
        return records

    for url in video_urls:
        normalized = normalize_url(url)
        if normalized in video_seen:
            continue
        video_seen.add(normalized)

        ext = Path(urlparse(url).path).suffix.lower()
        if ext in VIDEO_EXTENSIONS:
            if videos_mode in ("direct", "all"):
                records.append(download_direct_video(session, url, page_url,
                                                     assets_dir, video_counter, max_video_mb))
        elif PLATFORM_VIDEO_RE.search(url):
            if videos_mode == "all":
                records.append(download_platform_video(
                    url, assets_dir, video_counter, max_video_mb,
                    browser_cookies, download_media))
            else:
                records.append({
                    "url": url, "kind": "platform", "status": "skipped",
                    "local_path": "", "error": "use --videos all for platform videos",
                })

    return records


def apply_videos_to_markdown(md_path: Path, videos: list[dict]) -> None:
    """将视频信息写入 Markdown 文件 (对齐 z-web-pack apply_videos_to_page)。"""
    if not videos or not md_path.exists():
        return
    text = md_path.read_text(encoding="utf-8")

    # 替换正文中的直链为本地路径
    for video in videos:
        if video.get("status") == "ok" and video.get("kind") == "direct":
            text = text.replace(f"({video['url']})", f"({video['local_path']})")

    ok_videos = [v for v in videos if v.get("status") == "ok"]
    if ok_videos:
        lines = ["", "## 本页视频", ""]
        for video in ok_videos:
            name = Path(video["local_path"]).name
            lines.append(f"- [{name}]({video['local_path']}) ← <{video['url']}>")
            if video.get("subtitles"):
                for sub in video["subtitles"]:
                    lines.append(f"  - 字幕: [{Path(sub).name}]({sub})")
            if video.get("thumbnail"):
                lines.append(f"  - 封面: ![]({video['thumbnail']})")
        text = text.rstrip() + "\n" + "\n".join(lines) + "\n"

    md_path.write_text(text, encoding="utf-8")


# ───────────────────────────────────────────────────────────────
# 正文提取管线 (readability → trafilatura → bs4 → jina)
# ───────────────────────────────────────────────────────────────

def extract_content_readability(html: str, url: str) -> tuple[str, str] | None:
    """使用 readability-lxml 提取正文。返回 (title, markdown) 或 None。"""
    if not HAS_READABILITY:
        return None
    try:
        doc = ReadabilityDocument(html)
        title = doc.title() or ""
        summary_html = doc.summary()
        if not summary_html or len(summary_html) < 100:
            return None
        if HAS_MARKDOWNIFY:
            markdown = md_convert(summary_html, heading_style="ATX")
        else:
            soup = BeautifulSoup(summary_html, "lxml")
            markdown = soup.get_text("\n", strip=True)
        return title, markdown
    except Exception:
        return None


def extract_content_trafilatura(html: str, url: str) -> tuple[str, str] | None:
    """使用 trafilatura 提取正文。返回 (title, markdown) 或 None。"""
    if not HAS_TRAFILATURA:
        return None
    try:
        result = trafilatura.extract(html, output_format="markdown",
                                     with_metadata=True, url=url)
        if not result or len(result) < 100:
            return None
        # trafilatura 返回的 markdown 可能以元数据行开头
        title = ""
        lines = result.splitlines()
        for i, line in enumerate(lines[:10]):
            if line.startswith("# "):
                title = line[2:].strip()
                break
        return title, result
    except Exception:
        return None


def extract_content_bs4(html: str, url: str) -> tuple[str, str] | None:
    """使用 BeautifulSoup 选择器提取正文 (PKB legacy)。返回 (title, markdown) 或 None。"""
    if not HAS_BS4:
        return None
    try:
        soup = BeautifulSoup(html, "lxml")

        # 提取标题
        title = ""
        if soup.title and soup.title.string:
            title = soup.title.string.strip()
        h1 = soup.find("h1")
        if not title and h1:
            title = h1.get_text(strip=True)
        if not title:
            title = urlparse(url).netloc

        # 去噪音
        for selector in NOISE_SELECTORS:
            for tag in soup.select(selector):
                tag.decompose()

        # 找正文容器
        main_content = None
        for selector in CONTENT_SELECTORS:
            main_content = soup.select_one(selector)
            if main_content and len(main_content.get_text(strip=True)) > 100:
                break

        if not main_content:
            main_content = soup.find("body") or soup

        text = main_content.get_text("\n", strip=True)

        if HAS_MARKDOWNIFY:
            markdown = md_convert(str(main_content), heading_style="ATX")
        else:
            markdown = text

        return title, markdown
    except Exception:
        return None


def _text_is_weak(text: str) -> bool:
    """
    检测内容是否太弱而需要 Jina 兜底 (对齐 z-web-pack _text_is_weak)。

    TODO(phase-2): 逐步替换为 content_quality.assess_article()，
    以获得更细粒度的质量评分和问题诊断。
    本函数暂时保留以维持现有 Jina 兜底逻辑的稳定。
    """
    lowered = text.lower()
    if any(marker in lowered for marker in WEAK_MARKERS):
        return True
    # 去链接和图片后算可见文字长度
    body = re.sub(r'https?://\S+', '', text)
    body = re.sub(r'!\[[^\]]*\]\([^)]*\)', '', body)
    body = re.sub(r'\[[^\]]*\]\([^)]*\)', '', body)
    visible = re.sub(r'\s+', '', body)
    return len(visible) < MIN_CONTENT_LENGTH


# ───────────────────────────────────────────────────────────────
# Jina Reader 兜底 (对齐 z-web-pack)
# ───────────────────────────────────────────────────────────────

def jina_reader_url(url: str) -> str:
    """构造 Jina Reader URL (对齐 z-web-pack)。"""
    return f"https://r.jina.ai/http://{url}"


def parse_jina_markdown(raw: str, fallback_url: str) -> tuple[str, str]:
    """解析 Jina Reader 返回的 Markdown (对齐 z-web-pack parse_jina_markdown)。"""
    title = ""
    for line in raw.splitlines()[:20]:
        if line.startswith("Title:"):
            title = line.replace("Title:", "", 1).strip()
            break
    body = raw
    marker = "Markdown Content:"
    if marker in raw:
        body = raw.split(marker, 1)[1].strip()
    title = title or urlparse(fallback_url).path.strip("/") or fallback_url
    return title, clean_jina_markdown(body)


def clean_jina_markdown(markdown: str) -> str:
    """清洗 Jina Reader 返回的 Markdown (对齐 z-web-pack clean_reader_markdown)。"""
    lines = markdown.splitlines()
    cleaned: list[str] = []
    skip_until_heading = False

    for raw_line in lines:
        line = raw_line.strip()
        lower = line.lower()

        if line in {"## New to X?", "New to X?"}:
            skip_until_heading = True
            continue
        if skip_until_heading:
            if line.startswith("#") and "new to x" not in lower:
                skip_until_heading = False
            else:
                continue

        if line in JINA_CLEAN_DROP_EXACT:
            continue
        if re.search(r"\]\(https://x\.com/(login|i/flow/signup|tos|privacy)", line):
            continue
        if lower.startswith("by signing up, you agree"):
            continue

        cleaned.append(raw_line)

    body = "\n".join(cleaned)
    body = re.sub(r"\n{4,}", "\n\n\n", body).strip()
    return body


def try_jina_reader(url: str) -> dict | None:
    """使用 Jina Reader 兜底抓取。"""
    jina_url = jina_reader_url(url)
    print(f"   🔄 Jina Reader 兜底: {url}")
    try:
        resp = requests.get(
            jina_url,
            headers={"User-Agent": USER_AGENT, "Accept": "text/plain,*/*"},
            timeout=REQUEST_TIMEOUT,
            allow_redirects=True,
        )
        resp.raise_for_status()
        title, markdown = parse_jina_markdown(resp.text, url)

        if _text_is_weak(f"{title}\n{markdown}"):
            return None

        # 提取链接和图片
        images = extract_images_from_markdown(markdown, url)
        links = []
        seen = set()
        for match in re.finditer(r'\[([^\]]*)\]\(((?:https?:)?//[^\)]+)\)', markdown):
            href = match.group(2)
            if href not in seen:
                seen.add(href)
                skip, skip_reason = should_skip_link(href)
                is_pri, pri_reason = is_priority_link(href)
                links.append({
                    "url": href, "text": match.group(1).strip()[:200],
                    "skip": skip, "skip_reason": skip_reason,
                    "priority": is_pri, "priority_reason": pri_reason,
                })

        return {
            "url": url,
            "title": title,
            "html": "",
            "text": markdown,
            "markdown": markdown,
            "images": images,
            "links": links,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "extraction_method": "jina_reader",
            "via_jina": True,
        }
    except Exception as e:
        print(f"   ❌ Jina Reader 失败: {e}")
        return None


# ───────────────────────────────────────────────────────────────
# GitHub Collector v2 (tree + git clone 兜底)
# ───────────────────────────────────────────────────────────────

def fetch_github_api_contents(owner: str, repo: str, path: str, branch: str = "main") -> list[dict] | None:
    """通过 GitHub API 获取目录内容。"""
    api_url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}?ref={branch}"
    print(f"   📡 GitHub API: {api_url}")
    try:
        resp = requests.get(
            api_url,
            headers={"User-Agent": USER_AGENT, "Accept": "application/vnd.github.v3+json"},
            timeout=REQUEST_TIMEOUT,
        )
        if resp.status_code == 403:
            print(f"   ⚠️  GitHub API rate limit 触发")
            return None
        resp.raise_for_status()
        try:
            data = resp.json()
        except ValueError:
            print(f"   ⚠️  GitHub API 返回非 JSON 响应体")
            return None
        if data is None:
            print(f"   ⚠️  GitHub API 返回 null")
            return None
        return data
    except requests.RequestException as e:
        print(f"   ❌ GitHub API 失败: {e}")
        return None


def git_clone_temp(owner: str, repo: str, branch: str) -> Path | None:
    """临时 shallow clone 仓库。"""
    tmp_dir = Path(tempfile.mkdtemp(prefix="pkb_gh_"))
    repo_url = f"https://github.com/{owner}/{repo}.git"
    print(f"   📦 git clone --depth 1 {repo_url}")
    try:
        result = subprocess.run(
            ["git", "clone", "--depth", "1", "--branch", branch,
             "--single-branch", repo_url, str(tmp_dir)],
            capture_output=True, text=True, timeout=120,
        )
        if result.returncode != 0:
            print(f"   ❌ git clone 失败: {result.stderr[:200]}")
            shutil.rmtree(tmp_dir, ignore_errors=True)
            return None
        return tmp_dir
    except Exception as e:
        print(f"   ❌ git clone 异常: {e}")
        return None


def read_github_file_content(
    file_info: dict, owner: str, repo: str, branch: str,
    local_clone: Path | None = None,
) -> str | None:
    """读取 GitHub 文件内容。优先 raw URL，其次本地 clone。"""
    path = file_info.get("path", "")
    download_url = file_info.get("download_url", "")
    file_type = file_info.get("type", "file")
    name = file_info.get("name", "")

    if file_type != "file":
        return None

    # 跳过二进制
    skip_exts = {'.exe', '.dll', '.so', '.dylib', '.bin', '.zip', '.tar', '.gz',
                 '.7z', '.rar', '.whl', '.egg', '.pyc', '.pyo', '.class', '.jar',
                 '.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', '.ico', '.bmp',
                 '.mp3', '.mp4', '.avi', '.mov', '.wav', '.flac',
                 '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
                 '.ttf', '.woff', '.woff2', '.eot', '.otf'}
    if any(name.lower().endswith(ext) for ext in skip_exts):
        return None

    size = file_info.get("size", 0)
    if size > 1024 * 1024:
        return None

    # raw URL
    if download_url:
        try:
            resp = requests.get(download_url, headers={"User-Agent": USER_AGENT}, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            return resp.text
        except requests.RequestException:
            pass

    # 本地 clone
    if local_clone and local_clone.exists():
        file_path = local_clone / path
        if file_path.exists():
            try:
                return file_path.read_text(encoding="utf-8", errors="replace")
            except Exception:
                pass

    return None


def collect_github_tree(
    owner: str, repo: str, branch: str, path: str,
) -> tuple[list[dict], list[dict], dict | None]:
    """
    GitHub tree 目录采集 (PKB v2)。

    返回 (pages, links, github_meta)。
    """
    pages = []
    links = []
    now = datetime.now(timezone.utc).isoformat()

    contents = fetch_github_api_contents(owner, repo, path, branch)
    mode = "api"

    local_clone = None
    if contents is None:
        mode = "git_clone"
        local_clone = git_clone_temp(owner, repo, branch)
        if local_clone:
            target_dir = local_clone / path
            if target_dir.exists() and target_dir.is_dir():
                contents = []
                for f in sorted(target_dir.iterdir()):
                    stat = f.stat()
                    contents.append({
                        "name": f.name, "path": str(f.relative_to(local_clone)).replace("\\", "/"),
                        "type": "file" if f.is_file() else "dir",
                        "size": stat.st_size if f.is_file() else 0, "download_url": None,
                    })
            else:
                contents = None

    if not contents:
        return pages, links, {"owner": owner, "repo": repo, "branch": branch,
                              "path": path, "mode": mode, "files_collected": 0}

    # 分类
    all_files, all_dirs = [], []
    for item in contents:
        if isinstance(item, dict):
            if item.get("type") == "dir":
                all_dirs.append(item)
            elif item.get("type") == "file":
                all_files.append(item)

    priority_files = [f for f in all_files if f.get("name", "") in GITHUB_PRIORITY_FILES]
    other_files = [f for f in all_files if f.get("name", "") not in GITHUB_PRIORITY_FILES]
    readable_exts = {'.md', '.txt', '.py', '.js', '.ts', '.json', '.yaml', '.yml',
                     '.toml', '.cfg', '.ini', '.html', '.css', '.rst', '.sh', '.bat',
                     '.ps1', '.c', '.h', '.cpp', '.hpp', '.rs', '.go', '.java', '.rb'}
    readable_files = [f for f in other_files if any(f.get("name", "").lower().endswith(ext) for ext in readable_exts)]
    skipped_files = [f for f in other_files if f not in readable_files]

    repo_url = f"https://github.com/{owner}/{repo}"
    links.append({
        "url": repo_url, "text": f"仓库: {owner}/{repo}", "source_page": repo_url,
        "type": "github_repo", "priority": True, "priority_reason": "GitHub 仓库主页",
        "skip": False, "skip_reason": "", "expanded": False,
    })

    files_collected = 0
    for file_info in priority_files + readable_files:
        name = file_info.get("name", "")
        file_path = file_info.get("path", "")
        content = read_github_file_content(file_info, owner, repo, branch, local_clone)

        file_url = f"https://github.com/{owner}/{repo}/blob/{branch}/{file_path}"
        links.append({
            "url": file_url, "text": f"文件: {name}",
            "source_page": f"{repo_url}/tree/{branch}/{path}",
            "type": "github_file",
            "priority": name in GITHUB_PRIORITY_FILES,
            "priority_reason": "优先文件" if name in GITHUB_PRIORITY_FILES else "",
            "skip": content is None, "skip_reason": "" if content else "无法读取",
            "expanded": True,
        })

        if content:
            files_collected += 1
            lang = "markdown" if name.endswith('.md') else (
                "python" if name.endswith('.py') else (
                    "json" if name.endswith('.json') else (
                        "yaml" if name.endswith(('.yaml', '.yml')) else "text")))
            md_content = f"```{lang}\n{content}\n```" if lang != "markdown" else content

            pages.append({
                "url": file_url, "title": f"{name} — {owner}/{repo}",
                "html": "", "text": content, "markdown": md_content,
                "images": [], "links": [],
                "fetched_at": now, "extraction_method": f"github_{mode}",
                "via_jina": False,
                "_github_file": True, "_original_name": name,
            })

    for file_info in skipped_files:
        links.append({
            "url": f"https://github.com/{owner}/{repo}/blob/{branch}/{file_info.get('path', '')}",
            "text": f"跳过: {file_info.get('name', '')}",
            "source_page": f"{repo_url}/tree/{branch}/{path}",
            "type": "github_file", "priority": False, "priority_reason": "",
            "skip": True, "skip_reason": "非文本文件或二进制", "expanded": False,
        })

    for dir_info in all_dirs:
        dir_name = dir_info.get("name", "")
        if dir_name.startswith('.') or dir_name in {'node_modules', '__pycache__', '.git'}:
            continue
        links.append({
            "url": f"https://github.com/{owner}/{repo}/tree/{branch}/{dir_info.get('path', '')}",
            "text": f"目录: {dir_name}/",
            "source_page": f"{repo_url}/tree/{branch}/{path}",
            "type": "github_dir",
            "priority": dir_name in GITHUB_PRIORITY_DIRS,
            "priority_reason": "优先目录" if dir_name in GITHUB_PRIORITY_DIRS else "",
            "skip": True, "skip_reason": "达到深度限制", "expanded": False,
        })

    github_meta = {
        "owner": owner, "repo": repo, "branch": branch, "path": path,
        "mode": mode, "files_collected": files_collected,
    }

    if local_clone and local_clone.exists():
        shutil.rmtree(local_clone, ignore_errors=True)
        print(f"   🧹 已清理临时 clone")

    return pages, links, github_meta


def try_github_blob(
    session: requests.Session, url: str,
    assets_dir: Path, img_counter: list[int],
    image_hashes: dict[str, str], max_image_mb: float, mode: str,
) -> dict | None:
    """
    尝试用 GitHub blob/raw 方式抓取 (对齐 z-web-pack try_github_page)。
    """
    blob_match = GITHUB_BLOB_RE.match(url)
    if blob_match:
        owner, repo, branch, file_path = blob_match.groups()
        rest = f"{branch}/{file_path}"
        raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{rest}"
        try:
            resp = session.get(raw_url, timeout=20)
            resp.raise_for_status()
            name = Path(urlparse(raw_url).path).name
            title = f"{name} — {owner}/{repo}"
            text = resp.text
            if name.lower().endswith((".md", ".markdown", ".rst", ".txt")):
                markdown = absolutize_markdown_images(text, raw_url.rsplit("/", 1)[0] + "/")
            else:
                lang = Path(name).suffix.lstrip(".")
                markdown = f"```{lang}\n{text}\n```"

            # 本地化图片
            markdown, images = localize_markdown_images(
                markdown, raw_url, session, assets_dir, img_counter,
                image_hashes, max_image_mb, mode)

            return {
                "url": url, "title": title, "html": "", "text": text,
                "markdown": markdown, "images": images, "links": [],
                "fetched_at": datetime.now(timezone.utc).isoformat(),
                "extraction_method": "github_raw", "via_jina": False,
            }
        except Exception:
            return None

    repo_match = GITHUB_REPO_RE.match(url)
    if repo_match:
        owner, repo = repo_match.group(1), repo_match.group(2)
        try:
            api_url = f"https://api.github.com/repos/{owner}/{repo}/readme"
            resp = session.get(api_url, timeout=20,
                             headers={"Accept": "application/vnd.github.raw+json"})
            resp.raise_for_status()
            title = f"{owner}/{repo} README"
            markdown = absolutize_markdown_images(
                resp.text, f"https://raw.githubusercontent.com/{owner}/{repo}/HEAD/")
            markdown, images = localize_markdown_images(
                markdown, api_url, session, assets_dir, img_counter,
                image_hashes, max_image_mb, mode)
            return {
                "url": url, "title": title, "html": "", "text": resp.text,
                "markdown": markdown, "images": images, "links": [],
                "fetched_at": datetime.now(timezone.utc).isoformat(),
                "extraction_method": "github_api", "via_jina": False,
            }
        except Exception:
            return None

    return None


# ───────────────────────────────────────────────────────────────
# 页面抓取管线
# ───────────────────────────────────────────────────────────────

def _extract_content_from_html(html: str, url: str) -> tuple[str, str, str] | None:
    """从 HTML 中提取正文。返回 (title, markdown, extraction_method) 或 None。

    提取管线: readability-lxml → trafilatura → BeautifulSoup
    供 fetch_page() 和 Playwright DOM 渲染共用。
    """
    # readability-lxml
    result = extract_content_readability(html, url)
    if result:
        return result[0], result[1], "readability-lxml"

    # trafilatura
    result = extract_content_trafilatura(html, url)
    if result:
        return result[0], result[1], "trafilatura"

    # BeautifulSoup
    result = extract_content_bs4(html, url)
    if result:
        return result[0], result[1], "beautifulsoup"

    return None


def _quality_report_to_dict(report) -> dict:
    """将 QualityReport 转为可 JSON 序列化的 dict。"""
    if report is None:
        return {}
    return {
        "complete": report.complete,
        "score": report.score,
        "issues": [issue.value for issue in report.issues],
        "metrics": dict(report.metrics),
    }


def _write_network_debug(
    render_options, net_opts, pkb_root: Path,
) -> None:
    """写入脱敏后的网络捕获调试信息到 .pkbcache/network-debug/。

    不写入: body, content, html, headers, cookies, authorization, post_data。
    写入失败不影响正文采集。
    """
    # 仅标记 debug 模式已启用，实际文件在每次渲染后写入
    # 占位符 — 文件写入逻辑在 Collector 中处理
    debug_dir = pkb_root / ".pkbcache" / "network-debug"
    try:
        debug_dir.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass


def _save_network_debug_file(
    page_url: str,
    net_diag: dict | None,
    best_net: Any | None,
    selection_diag: dict | None,
    pkb_root: Path,
) -> str | None:
    """保存单次采集的网络调试文件。

    只写入脱敏后的元数据，不写入正文内容。
    """
    if net_diag is None:
        return None

    debug_dir = pkb_root / ".pkbcache" / "network-debug"
    try:
        debug_dir.mkdir(parents=True, exist_ok=True)
    except Exception:
        return None

    # 脱敏页面 URL
    try:
        from network_capture import sanitize_url
        safe_url = sanitize_url(page_url)
    except ImportError:
        safe_url = page_url

    from datetime import datetime, timezone
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    # 净化 domain：去除端口（: 在 Windows 上创建 NTFS ADS）、替换特殊字符
    raw_domain = urlparse(page_url).netloc or "unknown"
    domain = raw_domain.replace(":", "-").replace(".", "-").replace("/", "-")[:40]
    # 去除尾部连字符
    domain = domain.strip("-") or "unknown"
    filename = f"{timestamp}-{domain}.json"
    filepath = debug_dir / filename

    debug_data: dict[str, Any] = {
        "page_url": safe_url,
        "timestamp": timestamp,
        "responses": [],
        "candidates": [],
        "selected_method": selection_diag.get("selected_method", "unknown") if selection_diag else "unknown",
    }

    # 添加脱敏的响应摘要（不含 body）
    if net_diag:
        debug_data["diagnostic"] = {
            "total_responses_seen": net_diag.get("total_responses_seen", 0),
            "analyzed_responses": net_diag.get("analyzed_responses", 0),
            "candidates_found": net_diag.get("candidates_found", 0),
            "best_candidate_score": net_diag.get("best_candidate_score", 0),
            "best_candidate_complete": net_diag.get("best_candidate_complete", False),
            "capture_limited": net_diag.get("capture_limited", False),
        }

    # 添加脱敏的候选摘要（不含 content/html）
    if best_net is not None:
        try:
            candidate_summary = {
                "source_url": getattr(best_net, 'source_url', ''),
                "source_kind": getattr(best_net, 'source_kind', ''),
                "json_path": getattr(best_net, 'json_path', ''),
                "raw_length": len(getattr(best_net, 'content', '') or ''),
                "quality_score": getattr(best_net, 'quality_score', 0),
                "ranking_score": getattr(best_net, 'ranking_score', 0),
                "complete": getattr(best_net, 'quality_complete', False),
                "content_sha256": getattr(best_net, 'content_sha256', ''),
                "hints": list(getattr(best_net, 'hints', [])),
            }
            debug_data["candidates"].append(candidate_summary)
        except Exception:
            pass

    if selection_diag:
        debug_data["selection"] = selection_diag

    try:
        filepath.write_text(
            json.dumps(debug_data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return str(filepath)
    except Exception:
        return None


def _build_render_diagnostic(
    http_quality: dict | None,
    render_quality: dict | None,
    chosen: str,
    reason: str,
    network_diagnostic: dict | None = None,
    selection_diagnostic: dict | None = None,
) -> dict:
    """构建渲染 fallback 诊断信息。"""
    diag: dict[str, Any] = {
        "triggered": render_quality is not None,
        "used": chosen in ("playwright_dom", "playwright_network"),
        "chosen_method": chosen,
        "reason": reason,
        "http_quality": http_quality or {},
        "render_quality": render_quality or {},
    }
    if network_diagnostic:
        diag["network"] = network_diagnostic
    if selection_diagnostic:
        diag["selection"] = selection_diagnostic
    return diag


def fetch_page(
    url: str, session: requests.Session,
    assets_dir: Path, img_counter: list[int],
    image_hashes: dict[str, str],
    max_image_mb: float = 20.0, mode: str = "full",
) -> dict | None:
    """
    抓取单个页面。提取管线：
      1. GitHub repo/blob → GitHub raw/API
      2. readability-lxml
      3. trafilatura
      4. BeautifulSoup + markdownify
      5. Jina Reader (由调用方触发)
      6. Playwright DOM (由 WebPackCollector.run() 管理)

    每个页面记录 extraction_method 和 quality_report。
    """
    # ── 0. GitHub 快捷路径 ──
    gh_result = try_github_blob(session, url, assets_dir, img_counter,
                                 image_hashes, max_image_mb, mode)
    if gh_result is not None:
        # GitHub 结果也加质量报告
        if HAS_CONTENT_QUALITY:
            gh_result["quality_report"] = _quality_report_to_dict(
                assess_article(gh_result["title"], gh_result["text"], gh_result.get("html", ""))
            )
        return gh_result

    # ── 1. HTTP 抓取 ──
    headers = {"User-Agent": USER_AGENT}
    try:
        resp = session.get(url, headers=headers, timeout=REQUEST_TIMEOUT,
                          allow_redirects=True)
        if resp.status_code in (403, 429):
            print(f"   ⚠️  HTTP {resp.status_code}: {url}")
            return None
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"   ❌ 抓取失败: {url} — {e}")
        return None

    content_type = resp.headers.get("Content-Type", "").lower()
    if "text/html" not in content_type and "text/plain" not in content_type:
        if "application/pdf" in content_type:
            print(f"   ⚠️  PDF 不处理: {url}")
            return None

    html = resp.text
    final_url = resp.url

    # ── 2-4. 正文提取管线 ──
    extracted = _extract_content_from_html(html, final_url)
    if not extracted:
        return None

    title, markdown, extraction_method = extracted

    # ── 图片提取 ──
    soup = BeautifulSoup(html, "lxml") if HAS_BS4 else None
    images = extract_images_from_html(soup, final_url, mode) if soup else []

    # 本地化 markdown 中的图片
    markdown, localized_images = localize_markdown_images(
        markdown, final_url, session, assets_dir, img_counter,
        image_hashes, max_image_mb, mode)

    # 合并图片记录
    for img in images:
        record = download_image(img["url"], final_url, session, assets_dir,
                                img_counter, image_hashes, max_image_mb, mode)
        record["alt"] = img.get("alt", "")
        localized_images.append(record)

    # ── 链接提取 ──
    links = []
    seen_links = set()
    if soup:
        for a in soup.find_all("a", href=True):
            href = urljoin(final_url, a["href"])
            href_clean = normalize_url(href)
            if href_clean not in seen_links and href_clean != normalize_url(final_url):
                seen_links.add(href_clean)
                skip, skip_reason = should_skip_link(href_clean)
                is_pri, pri_reason = is_priority_link(href_clean)
                links.append({
                    "url": href_clean, "text": a.get_text(strip=True)[:200],
                    "skip": skip, "skip_reason": skip_reason,
                    "priority": is_pri, "priority_reason": pri_reason,
                })

    # ── 质量检查 ──
    quality_report = {}
    if HAS_CONTENT_QUALITY:
        try:
            report = assess_article(title, markdown, html)
            quality_report = _quality_report_to_dict(report)
        except Exception:
            pass  # 质量检查失败不影响采集

    return {
        "url": url,
        "title": title or urlparse(url).netloc,
        "html": html,
        "text": markdown,
        "markdown": markdown,
        "images": localized_images,
        "links": links,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "extraction_method": extraction_method,
        "via_jina": False,
        "quality_report": quality_report,
        "_render_diagnostic": None,
    }


# ───────────────────────────────────────────────────────────────
# WebPackCollector — 主采集器
# ───────────────────────────────────────────────────────────────

class WebPackCollector:
    """PKB Raw 层网页素材包采集器 v3 — z-web-pack 对齐版。"""

    def __init__(
        self,
        topic: str,
        source_urls: list[str],
        max_depth: int = 1,
        max_pages: int = 80,
        output_root: Path = WEBPACKS_DIR,
        privacy: str = "public",
        mode: str = "full",
        videos: str = "direct",
        max_image_mb: float = 20.0,
        max_video_mb: float = 300.0,
        browser_cookies: str = "",
        download_media: bool = False,
        same_domain_only: bool = False,
        delay: float = DEFAULT_DELAY,
        no_jina: bool = False,
        render_options: Any = None,
        debug_network: bool = False,
    ):
        self.topic = topic
        self.source_urls = source_urls
        self.max_depth = max_depth
        self.max_pages = max_pages
        self.output_root = Path(output_root)
        self.privacy = privacy
        self.mode = mode
        self.videos_mode = videos
        self.max_image_mb = max_image_mb
        self.max_video_mb = max_video_mb
        self.browser_cookies = browser_cookies
        self.download_media = download_media
        self.same_domain_only = same_domain_only
        self.delay = delay
        self.no_jina = no_jina
        self.render_options = render_options
        self.debug_network = debug_network

        # 运行时状态
        self.collected_pages: list[dict] = []
        self.failed_urls: list[dict] = []
        self.all_images: list[dict] = []
        self.all_links: list[dict] = []
        self.all_videos: list[dict] = []
        self.visited_urls: set[str] = set()
        self.pack_dir: Path | None = None
        self.assets_dir: Path | None = None
        self.started_at = datetime.now(timezone.utc)
        self.github_meta: dict | None = None

        # 全局去重
        self.image_hashes: dict[str, str] = {}
        self.video_seen: set[str] = set()
        self.img_counter = [0]
        self.video_counter = [0]

        # Playwright 渲染器（由 run() 管理生命周期）
        self._renderer: Any = None
        self._render_stats: dict[str, int] = {"attempted": 0, "used": 0, "failed": 0}

    def _ensure_pack_dir(self) -> Path:
        """创建输出目录，自动处理重名。"""
        today = datetime.now().strftime("%Y-%m-%d")
        topic_slug = slugify(self.topic)
        base_name = f"{today}-{topic_slug}"
        pack_dir = self.output_root / base_name

        if pack_dir.exists():
            counter = 1
            while (self.output_root / f"{base_name}-{counter:02d}").exists():
                counter += 1
            pack_dir = self.output_root / f"{base_name}-{counter:02d}"

        pack_dir.mkdir(parents=True, exist_ok=True)
        self.assets_dir = pack_dir / "assets"
        self.assets_dir.mkdir(exist_ok=True)
        self.pack_dir = pack_dir
        return pack_dir

    def _build_page_from_network_candidate(
        self, best_net, url: str, session: requests.Session,
        assets_dir: Path, img_counter: list[int],
        image_hashes: dict[str, str],
        max_image_mb: float = 20.0, mode: str = "full",
    ) -> dict | None:
        """从最佳网络候选构建与 fetch_page() 兼容的 page dict。

        网络候选的内容（JSON 文本/HTML）进入现有 Markdown 管线：
          1. 如有 HTML → 复用 readability/trafilatura/bs4 提取器
          2. 否则 → 纯文本作为 Markdown 正文
        不创建第二套 Markdown 输出格式。
        """
        if best_net is None:
            return None

        content = getattr(best_net, 'content', '') or ''
        if not content:
            return None

        title = getattr(best_net, 'title', '') or ''
        html = getattr(best_net, 'html', '') or ''
        source_kind = getattr(best_net, 'source_kind', '') or ''
        net_url = getattr(best_net, 'source_url', url) or url

        extraction_method = f"playwright_network_{source_kind}"

        # 如果网络候选是 HTML，复用现有 HTML 提取器
        if html and source_kind in ('html_document', 'json_html'):
            try:
                extracted = _extract_content_from_html(html, url)
                if extracted:
                    ext_title, markdown, ext_method = extracted
                    if ext_title and (not title or len(ext_title) > len(title)):
                        title = ext_title
                    extraction_method = f"playwright_network_{ext_method}"
                else:
                    markdown = content
            except Exception:
                markdown = content
        else:
            markdown = content

        # 标题回退
        if not title:
            title = urlparse(url).netloc

        # 质量检查
        quality_report = {}
        if HAS_CONTENT_QUALITY:
            try:
                report = assess_article(title, markdown, html)
                quality_report = _quality_report_to_dict(report)
            except Exception:
                pass

        # 图片：从 Markdown 中提取并本地化
        markdown, localized_images = localize_markdown_images(
            markdown, url, session, assets_dir, img_counter,
            image_hashes, max_image_mb, mode)

        return {
            "url": url,
            "title": title,
            "html": html,
            "text": markdown,
            "markdown": markdown,
            "images": localized_images,
            "links": [],
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "extraction_method": extraction_method,
            "via_jina": False,
            "quality_report": quality_report,
            "_render_diagnostic": None,
            "_network_diagnostic": None,
        }

    def _try_playwright_dom(
        self, url: str, session: requests.Session,
        assets_dir: Path, img_counter: list[int],
        image_hashes: dict[str, str],
        max_image_mb: float = 20.0, mode: str = "full",
    ) -> tuple[dict | None, Any | None, Any | None]:
        """使用 Playwright 渲染页面 DOM 并提取正文。

        返回 (page_dict, best_network_candidate, network_diagnostic_dict)。
        best_network_candidate 是 BestNetworkCandidate 或 NetworkContentCandidate。
        """
        if self._renderer is None:
            return None, None, None

        try:
            result = self._renderer.render_page(url)
            if not result.success:
                print(f"   ⚠️  Playwright 渲染失败: {result.error}")
                return None, None, None

            rendered_html = result.html
            rendered_url = result.final_url
            rendered_title = result.title

            # 运行正文提取管线
            extracted = _extract_content_from_html(rendered_html, rendered_url)
            if not extracted:
                return None, None, None

            title, markdown, extraction_method = extracted
            # Playwright 的 title 可能更准确
            if rendered_title and (not title or len(rendered_title) > len(title)):
                title = rendered_title

            extraction_method = f"playwright_{extraction_method}"

            # 图片提取
            soup = BeautifulSoup(rendered_html, "lxml") if HAS_BS4 else None
            images = extract_images_from_html(soup, rendered_url, mode) if soup else []

            # 本地化图片
            markdown, localized_images = localize_markdown_images(
                markdown, rendered_url, session, assets_dir, img_counter,
                image_hashes, max_image_mb, mode)

            for img in images:
                record = download_image(img["url"], rendered_url, session, assets_dir,
                                        img_counter, image_hashes, max_image_mb, mode)
                record["alt"] = img.get("alt", "")
                localized_images.append(record)

            # 链接提取
            links = []
            seen_links = set()
            if soup:
                for a in soup.find_all("a", href=True):
                    href = urljoin(rendered_url, a["href"])
                    href_clean = normalize_url(href)
                    if href_clean not in seen_links and href_clean != normalize_url(rendered_url):
                        seen_links.add(href_clean)
                        skip, skip_reason = should_skip_link(href_clean)
                        is_pri, pri_reason = is_priority_link(href_clean)
                        links.append({
                            "url": href_clean, "text": a.get_text(strip=True)[:200],
                            "skip": skip, "skip_reason": skip_reason,
                            "priority": is_pri, "priority_reason": pri_reason,
                        })

            # 质量检查
            quality_report = {}
            if HAS_CONTENT_QUALITY:
                try:
                    report = assess_article(title, markdown, rendered_html)
                    quality_report = _quality_report_to_dict(report)
                except Exception:
                    pass

            # 网络诊断 + 最佳网络候选选择
            net_diag = None
            best_net_candidate = None
            if result.network_diagnostic is not None:
                try:
                    nd = result.network_diagnostic
                    net_diag = {
                        "total_responses_seen": nd.total_responses_seen,
                        "analyzed_responses": nd.analyzed_responses,
                        "candidates_found": nd.candidates_found,
                        "best_candidate_score": 0,
                        "best_candidate_complete": False,
                        "capture_limited": (
                            nd.skipped_by_limit > 0 or nd.skipped_by_size > 0
                        ),
                    }
                    if result.network_candidates:
                        # 选择最佳网络候选
                        if HAS_SELECTION_ENGINE and select_best_network_candidate is not None:
                            best_net_candidate = select_best_network_candidate(
                                list(result.network_candidates)
                            )
                        else:
                            # Fallback: 使用第一个候选
                            raw_best = result.network_candidates[0]
                            if raw_best.content and len(raw_best.content) >= 200:
                                best_net_candidate = raw_best

                        if best_net_candidate is not None:
                            net_diag["best_candidate_score"] = best_net_candidate.quality_score
                            net_diag["best_candidate_complete"] = best_net_candidate.quality_complete
                except Exception:
                    pass

            return {
                "url": url,
                "title": title or urlparse(url).netloc,
                "html": rendered_html,
                "text": markdown,
                "markdown": markdown,
                "images": localized_images,
                "links": links,
                "fetched_at": datetime.now(timezone.utc).isoformat(),
                "extraction_method": extraction_method,
                "via_jina": False,
                "quality_report": quality_report,
                "_render_diagnostic": None,
                "_network_diagnostic": net_diag,
            }, best_net_candidate, net_diag

        except Exception as e:
            print(f"   ❌ Playwright DOM 提取异常: {e}")
            return None, None, None

    def run(self) -> dict:
        """执行采集流程。"""
        self._ensure_pack_dir()
        render_enabled = (
            self.render_options is not None
            and hasattr(self.render_options, 'enabled')
            and self.render_options.enabled
        )

        print(f"\n[PKB] WebPack v3 采集器")
        print(f"   主题: {self.topic}")
        print(f"   输出: {self.pack_dir}")
        print(f"   模式: {self.mode}")
        print(f"   入口: {len(self.source_urls)} URL(s)")
        print(f"   最大深度: {self.max_depth} | 最大页面: {self.max_pages}")
        print(f"   视频: {self.videos_mode} | 下载媒体: {self.download_media}")
        if render_enabled:
            print(f"   🎭 Playwright 动态渲染: 启用 (headed={self.render_options.headed})")
        print()

        # ── Playwright 初始化 ──
        if render_enabled:
            if not HAS_PLAYWRIGHT or PlaywrightRenderer is None:
                print("❌ Playwright 未安装。请运行:")
                print(f"   {PlaywrightRenderer.install_hint() if HAS_PLAYWRIGHT else 'pip install -r requirements-playwright.txt'}")
                print("   继续使用普通采集模式。")
                render_enabled = False
            else:
                try:
                    self._renderer = PlaywrightRenderer(self.render_options)
                    self._renderer.start()
                    print("   ✅ Playwright 浏览器已启动")
                except Exception as e:
                    print(f"   ⚠️  Playwright 启动失败: {e}")
                    print("   继续使用普通采集模式。")
                    render_enabled = False
                    self._renderer = None

        try:
            session = requests.Session()
            session.headers.update({
                "User-Agent": USER_AGENT,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,text/plain;q=0.8,*/*;q=0.7",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            })

            # 确定 root hosts
            root_hosts = {urlparse(u).netloc.lower() for u in self.source_urls}
            force_roots = {normalize_url(u) for u in self.source_urls}

            # BFS 队列
            queue: deque[tuple[str, int, str]] = deque()
            for url in self.source_urls:
                queue.append((url, 0, "main"))

            page_idx = 0
            skipped_queue: list[dict] = []

            while queue and len(self.collected_pages) < self.max_pages:
                url, depth, role = queue.popleft()
                normalized = normalize_url(url)

                if normalized in self.visited_urls:
                    continue
                self.visited_urls.add(normalized)

                # 安全检测
                is_sens, sens_reason = is_sensitive_url(url)
                if is_sens and self.mode == "safe":
                    print(f"   🔒 跳过敏感页面: {url} ({sens_reason})")
                    self.failed_urls.append({"url": url, "reason": f"敏感页面: {sens_reason}"})
                    continue

                # ── GitHub tree 专用采集 ──
                gh_info = detect_github_url_type(url)
                is_github_tree = gh_info and gh_info["type"] in ("tree", "repo") if gh_info else False

                if is_github_tree and gh_info["type"] == "tree":
                    print(f"   🐙 GitHub Collector: {gh_info['owner']}/{gh_info['repo']}"
                          f" tree/{gh_info['branch']}/{gh_info['path']}")
                    gh_pages, gh_links, gh_meta = collect_github_tree(
                        gh_info["owner"], gh_info["repo"],
                        gh_info["branch"], gh_info["path"] or "",
                    )
                    self.github_meta = gh_meta

                    for gp in gh_pages:
                        if len(self.collected_pages) >= self.max_pages:
                            break
                        gp["depth"] = depth
                        gp["role"] = "main" if gp.get("_original_name") in GITHUB_PRIORITY_FILES else "linked"
                        page_idx += 1
                        self.collected_pages.append(gp)

                    for gl in gh_links:
                        self.all_links.append(gl)

                    print(f"   ✅ GitHub Collector: {len(gh_pages)} 文件 "
                          f"(mode={gh_meta.get('mode', '?')})")
                    continue

                # ── 通用网页抓取 ──
                print(f"   📄 [{len(self.collected_pages)+1}/{self.max_pages}] "
                      f"depth={depth} {url[:80]}")
                page = fetch_page(
                    url, session, self.assets_dir, self.img_counter,
                    self.image_hashes, self.max_image_mb, self.mode,
                )

                # ── Jina 兜底 ──
                if page is None and not self.no_jina:
                    page = try_jina_reader(url)
                    if page is not None and HAS_CONTENT_QUALITY:
                        try:
                            page["quality_report"] = _quality_report_to_dict(
                                assess_article(page["title"], page["text"], page.get("html", ""))
                            )
                        except Exception:
                            pass
                elif page and not page.get("via_jina"):
                    # 使用 assess_article() 判断是否需要 Jina；
                    # 保留 _text_is_weak() 作为兼容回退
                    need_jina = False
                    if HAS_CONTENT_QUALITY:
                        qr = page.get("quality_report", {})
                        if qr and not qr.get("complete", True) and not self.no_jina:
                            need_jina = True
                    elif _text_is_weak(page["text"]) and not self.no_jina:
                        need_jina = True

                    if need_jina:
                        print(f"   ⚠️  内容偏弱 (评分: {page.get('quality_report', {}).get('score', '?')}), 尝试 Jina...")
                        jina_page = try_jina_reader(url)
                        if jina_page:
                            if HAS_CONTENT_QUALITY:
                                try:
                                    jina_page["quality_report"] = _quality_report_to_dict(
                                        assess_article(jina_page["title"], jina_page["text"], jina_page.get("html", ""))
                                    )
                                except Exception:
                                    pass
                            # 比较 Jina 和原始结果
                            use_jina = True
                            if HAS_CONTENT_QUALITY:
                                orig_score = page.get("quality_report", {}).get("score", 0)
                                jina_score = jina_page.get("quality_report", {}).get("score", 0)
                                if jina_score <= orig_score:
                                    use_jina = False
                            if use_jina:
                                page = jina_page

                # ── Playwright 动态渲染 + 网络候选 ──
                if page is not None and render_enabled and self._renderer is not None:
                    quality = page.get("quality_report", {})
                    if not quality.get("complete", True):
                        print(f"   🎭 尝试 Playwright 动态渲染: {url[:60]}")
                        self._render_stats["attempted"] += 1
                        try:
                            pw_result = self._try_playwright_dom(
                                url, session, self.assets_dir, self.img_counter,
                                self.image_hashes, self.max_image_mb, self.mode,
                            )
                            pw_page, best_net, net_diag = pw_result

                            if pw_page is not None:
                                pw_quality = pw_page.get("quality_report", {})
                                pw_score = pw_quality.get("score", 0) if pw_quality else 0
                                orig_score = quality.get("score", 0) if quality else 0

                                # ── 三方选择 ──
                                http_candidate = ExtractionCandidate(
                                    method="http",
                                    title=page.get("title", ""),
                                    content=page.get("text", ""),
                                    html=page.get("html", ""),
                                    final_url=page.get("url", url),
                                    quality_score=orig_score,
                                    quality_complete=quality.get("complete", False),
                                ) if HAS_SELECTION_ENGINE and ExtractionCandidate is not None else None

                                dom_candidate = ExtractionCandidate(
                                    method="playwright_dom",
                                    title=pw_page.get("title", ""),
                                    content=pw_page.get("text", ""),
                                    html=pw_page.get("html", ""),
                                    final_url=pw_page.get("url", url),
                                    quality_score=pw_score,
                                    quality_complete=pw_quality.get("complete", False),
                                ) if HAS_SELECTION_ENGINE and ExtractionCandidate is not None else None

                                net_candidate = BestNetworkCandidate(
                                    source_url=getattr(best_net, 'source_url', '') if best_net else '',
                                    source_content_type=getattr(best_net, 'source_content_type', '') if best_net else '',
                                    source_kind=getattr(best_net, 'source_kind', '') if best_net else '',
                                    json_path=getattr(best_net, 'json_path', '') if best_net else '',
                                    content=getattr(best_net, 'content', '') if best_net else '',
                                    title=getattr(best_net, 'title', '') if best_net else '',
                                    html=getattr(best_net, 'html', '') if best_net else '',
                                    quality_score=getattr(best_net, 'quality_score', 0) if best_net else 0,
                                    ranking_score=getattr(best_net, 'ranking_score', 0) if best_net else 0,
                                    quality_complete=getattr(best_net, 'quality_complete', False) if best_net else False,
                                    hints=list(getattr(best_net, 'hints', [])) if best_net else [],
                                    content_sha256=getattr(best_net, 'content_sha256', '') if best_net else '',
                                ) if best_net is not None and HAS_SELECTION_ENGINE and BestNetworkCandidate is not None else None

                                # 执行三方选择
                                if HAS_SELECTION_ENGINE and select_best_result is not None:
                                    selection = select_best_result(
                                        http_candidate, dom_candidate, net_candidate,
                                    )
                                    sel_diag = selection.to_dict()
                                    chosen = selection.selected_method
                                    reason = selection.selection_reason
                                else:
                                    # Fallback: 简单的 DOM vs HTTP 选择
                                    sel_diag = None
                                    if pw_quality.get("complete", False) and not quality.get("complete", True):
                                        chosen = "playwright_dom"
                                        reason = "rendered_result_complete"
                                    elif pw_score > orig_score:
                                        chosen = "playwright_dom"
                                        reason = "rendered_score_higher"
                                    else:
                                        chosen = "http"
                                        reason = "rendered_not_better"

                                # 构建诊断
                                # 构建诊断
                                render_diag = _build_render_diagnostic(
                                    quality, pw_quality, chosen, reason,
                                    network_diagnostic=net_diag,
                                    selection_diagnostic=sel_diag,
                                )
                                page["_render_diagnostic"] = render_diag

                                # 根据选择替换页面内容
                                if chosen == "playwright_dom":
                                    page = pw_page
                                    if render_diag:
                                        page["_render_diagnostic"] = render_diag
                                    page["_render_diagnostic"]["used"] = True
                                    self._render_stats["used"] += 1
                                    print(f"   ✅ 采用 Playwright DOM (评分: {pw_score}, 原因: {reason})")
                                elif chosen == "playwright_network" and best_net is not None:
                                    # 使用网络候选内容构建页面
                                    net_page = self._build_page_from_network_candidate(
                                        best_net, url, session, self.assets_dir,
                                        self.img_counter, self.image_hashes,
                                        self.max_image_mb, self.mode,
                                    )
                                    if net_page is not None:
                                        page = net_page
                                    if render_diag:
                                        page["_render_diagnostic"] = render_diag
                                    page["_render_diagnostic"]["used"] = True
                                    self._render_stats["used"] += 1
                                    print(f"   ✅ 采用 Playwright Network (评分: {getattr(best_net, 'quality_score', 0)}, 原因: {reason})")
                                else:
                                    print(f"   ⚠️  保留原结果 (HTTP:{orig_score}, 原因: {reason})")

                                # 添加 extraction_method 和 selection_diagnostic
                                if sel_diag:
                                    page["selection_diagnostic"] = sel_diag
                                page["extraction_method"] = chosen

                                # --debug-network: 写入脱敏调试文件
                                if self.debug_network:
                                    try:
                                        _save_network_debug_file(
                                            url, net_diag, best_net, sel_diag, PKB_ROOT,
                                        )
                                    except Exception:
                                        pass

                            else:
                                self._render_stats["failed"] += 1
                                print(f"   ❌ Playwright 渲染无结果")
                                page["_render_diagnostic"] = _build_render_diagnostic(
                                    quality, None, "http", "renderer_returned_none",
                                )
                        except Exception as e:
                            self._render_stats["failed"] += 1
                            print(f"   ❌ Playwright 渲染异常: {e}")
                            page["_render_diagnostic"] = _build_render_diagnostic(
                                quality, None, "http", f"renderer_error: {str(e)[:100]}",
                            )

                if page is None:
                    print(f"   ❌ 彻底失败: {url}")
                    self.failed_urls.append({"url": url, "reason": "所有抓取方式均失败"})
                    self.all_links.append({
                        "url": url, "text": url, "source_page": "",
                        "type": "entry" if depth == 0 else "linked",
                        "priority": False, "priority_reason": "",
                        "skip": True, "skip_reason": "抓取失败", "expanded": False,
                    })
                    continue

            page["depth"] = depth
            page["role"] = role
            page_idx += 1
            self.collected_pages.append(page)

            # ── 处理图片 ──
            for img_info in page.get("images", []):
                if isinstance(img_info, dict) and img_info.get("status"):
                    img_info["source_page"] = url
                    self.all_images.append(img_info)
                elif isinstance(img_info, dict) and img_info.get("url"):
                    result = download_image(
                        img_info["url"], url, session, self.assets_dir,
                        self.img_counter, self.image_hashes,
                        self.max_image_mb, self.mode,
                    )
                    result["alt"] = img_info.get("alt", "")
                    result["source_page"] = url
                    self.all_images.append(result)

            # ── 处理链接 ──
            for link_info in page.get("links", []):
                link_record = {
                    **link_info,
                    "source_page": url,
                    "type": "entry" if depth == 0 else "linked",
                    "expanded": False,
                }
                self.all_links.append(link_record)

            # ── 视频处理 ──
            if self.videos_mode != "off":
                page_videos = collect_videos_from_html(page.get("html", ""), url)
                # 入口本身是视频页
                if PLATFORM_VIDEO_RE.search(url) or Path(urlparse(url).path).suffix.lower() in VIDEO_EXTENSIONS:
                    page_videos.insert(0, url)
                # 链接中的视频
                for link in page.get("links", []):
                    link_url = link.get("url", "")
                    if Path(urlparse(link_url).path).suffix.lower() in VIDEO_EXTENSIONS:
                        page_videos.append(link_url)
                    elif PLATFORM_VIDEO_RE.search(link_url):
                        page_videos.append(link_url)

                videos = handle_videos(
                    list(dict.fromkeys(page_videos)), url, session,
                    self.assets_dir, self.video_counter, self.video_seen,
                    self.videos_mode, self.max_video_mb,
                    self.browser_cookies, self.download_media,
                )
                self.all_videos.extend(videos)

                # 视频写入页面 Markdown（在后续生成文件时处理）
                page["_videos"] = videos

            # ── 展开链接 ──
            if depth < self.max_depth and len(self.collected_pages) < self.max_pages:
                priority_links = [
                    l for l in page.get("links", [])
                    if l.get("priority") and not l.get("skip")
                    and normalize_url(l["url"]) not in self.visited_urls
                ]
                for pl in priority_links[:5]:
                    queue.append((pl["url"], depth + 1, "linked"))
                    for al in self.all_links:
                        if al["url"] == pl["url"]:
                            al["expanded"] = True
                            break

            time.sleep(self.delay)

            # 剩余未处理链接
            while queue:
                url, _depth, _role = queue.popleft()
                if normalize_url(url) not in self.visited_urls:
                    skipped_queue.append({"url": url, "reason": "max-pages-reached"})

            # 生成输出文件
            self._save_page_files()
            self._generate_readme()
            self._generate_brief()
            self._generate_link_inventory()
            self._generate_image_inventory()
            self._generate_media_inventory()
            self._generate_reading_map()
            self._generate_manifest()
            self._print_report()

            return self._build_result()

        finally:
            # ── Playwright 清理 ──
            if self._renderer is not None:
                try:
                    self._renderer.close()
                    print("   🧹 Playwright 浏览器已关闭")
                except Exception as e:
                    print(f"   ⚠️  Playwright 关闭异常: {e}")
                self._renderer = None

    def _save_page_files(self):
        """为每个采集页面生成 MAIN-xx / LINKED-xx Markdown 文件。"""
        # 构建 page_url → images 映射
        page_images_map: dict[str, list[dict]] = {}
        for img in self.all_images:
            source_page = img.get("source_page", "")
            if source_page:
                page_images_map.setdefault(source_page, []).append(img)

        for i, page in enumerate(self.collected_pages, 1):
            slug = slugify(page.get("title", f"page-{i}"), "page", 50)
            role = page.get("role", "main")
            prefix = "MAIN" if role == "main" else "LINKED"
            filename = f"{prefix}-{i:02d}-{slug}.md"

            md_content = page.get("markdown", page.get("text", ""))
            page_url = page.get("url", "")

            # 替换图片链接为本地路径
            page_imgs = page_images_map.get(page_url, [])
            for img_rec in page_imgs:
                src_url = img_rec.get("source_url", "")
                if src_url and img_rec.get("status") == "ok":
                    local_file = img_rec.get("local_path", "")
                    if local_file and src_url in md_content:
                        md_content = md_content.replace(src_url, local_file)

            # 处理 readability-lxml 导致的空图片引用 ![]()
            empty_img_pattern = re.compile(r'!\[([^\]]*)\]\(\s*\)')
            remaining_ok_imgs = [
                img for img in page_imgs
                if img.get("status") == "ok"
                and img.get("local_path")
                and img.get("source_url", "") not in md_content
            ]
            if empty_img_pattern.search(md_content) and remaining_ok_imgs:
                img_iter = iter(remaining_ok_imgs)
                def _fill_empty_img(match):
                    alt = match.group(1)
                    try:
                        next_img = next(img_iter)
                        return f"![{alt}]({next_img['local_path']})"
                    except StopIteration:
                        return match.group(0)
                md_content = empty_img_pattern.sub(_fill_empty_img, md_content)

            # 构建 frontmatter
            extraction = page.get("extraction_method", "unknown")
            fm = [
                "---",
                f"type: web_page",
                f"source_url: {page['url']}",
                f"collected_at: {page['fetched_at']}",
                f"topic: {self.topic}",
                f"role: {role}",
                f"privacy: {self.privacy}",
                f"depth: {page.get('depth', 0)}",
                f"extraction_method: {extraction}",
                f"mode: {self.mode}",
            ]
            if page.get("via_jina"):
                fm.append("via_jina: true")
            fm.append("---\n")

            content = "\n".join(fm) + "\n"
            content += f"# {page['title']}\n\n"
            content += f"> 来源: [{page['url']}]({page['url']})\n"
            content += f"> 采集时间: {page['fetched_at']}\n"
            content += f"> 提取方法: {extraction}\n"
            content += f"> 深度: {page.get('depth', 0)} | 类型: {role}\n"
            if page.get("via_jina"):
                content += "> ⚠️ 通过 Jina Reader 抓取\n"
            content += "\n" + md_content
            content += "\n\n---\n*由 PKB web_pack v3 采集器生成 · z-web-pack 对齐*\n"

            filepath = self.pack_dir / filename
            filepath.write_text(content, encoding="utf-8")

            page["_file"] = filename

            # 视频写入
            if page.get("_videos"):
                apply_videos_to_markdown(filepath, page["_videos"])

    def _generate_readme(self):
        """生成 README.md。"""
        collected = len(self.collected_pages)
        failed = len(self.failed_urls)
        images_downloaded = sum(1 for i in self.all_images if i.get("status") == "ok")
        main_pages = [p for p in self.collected_pages if p.get("role") == "main"]
        linked_pages = [p for p in self.collected_pages if p.get("role") == "linked"]

        lines = [
            f"# Webpack: {self.topic}",
            "",
            f"> 创建时间: {self.started_at.strftime('%Y-%m-%d %H:%M:%S')}",
            f"> 采集器: PKB web_pack v3 (z-web-pack aligned)",
            f"> 模式: {self.mode}",
            f"> 采集页面: {collected} 个 (MAIN: {len(main_pages)}, LINKED: {len(linked_pages)})",
            f"> 图片: 发现 {len(self.all_images)} 张, 下载 {images_downloaded} 张",
            f"> 视频: 发现 {len(self.all_videos)} 个, 下载 {sum(1 for v in self.all_videos if v.get('status') == 'ok')} 个",
            f"> 失败链接: {failed} 个",
            f"> 隐私级别: {self.privacy}",
        ]

        if self.github_meta:
            gh = self.github_meta
            lines += [
                "", "## 🐙 GitHub 专用采集模式", "",
                f"- 仓库: [{gh['owner']}/{gh['repo']}](https://github.com/{gh['owner']}/{gh['repo']})",
                f"- 分支: {gh['branch']}", f"- 目标路径: {gh['path'] or '/'}",
                f"- 采集方式: {gh['mode']}", f"- 文件采集数: {gh['files_collected']}",
            ]

        lines += [
            "", "## 入口链接", "",
        ]
        for url in self.source_urls:
            lines.append(f"- [{url}]({url})")

        lines += [
            "", "## 目录结构", "", "```", f"{self.pack_dir.name}/",
            "├── README.md", "├── 00-research-brief.md",
            "├── 01-link-inventory.md", "├── 02-image-inventory.md",
            "├── 03-reading-map.md", "├── 04-media-inventory.md",
            "├── manifest.json",
        ]
        for p in self.collected_pages:
            lines.append(f"├── {p.get('_file', '?')}")
        lines.append("└── assets/")
        if images_downloaded > 0:
            lines.append(f"    └── (images + videos)")
        lines += ["```", "", "---", "*由 PKB web_pack v3 采集器生成 · z-web-pack 对齐*"]

        (self.pack_dir / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _generate_brief(self):
        """生成 00-research-brief.md。"""
        now = datetime.now(timezone.utc).isoformat()
        lines = [
            "---", f"created: {now}", f"topic: {self.topic}",
            "type: research-brief", "---", "",
            f"# 研究摘要: {self.topic}", "",
            "## 采集概况", "",
            f"- 采集器: PKB web_pack v3", f"- 模式: {self.mode}",
            f"- 入口链接数: {len(self.source_urls)}",
            f"- 成功采集: {len(self.collected_pages)} 页",
            f"- 失败: {len(self.failed_urls)} 个",
            f"- 最大深度: {self.max_depth}",
            f"- 采集时间: {now}", "",
            "## 提取方法统计", "",
        ]
        methods = {}
        for p in self.collected_pages:
            m = p.get("extraction_method", "unknown")
            methods[m] = methods.get(m, 0) + 1
        for m, c in sorted(methods.items()):
            lines.append(f"- {m}: {c} 页")

        lines += ["", "## 页面摘要", ""]
        for p in self.collected_pages:
            text_preview = p.get("text", "")[:300].replace("\n", " ")
            lines.append(f"### {p['title']}")
            lines.append(f"- 来源: {p['url']}")
            lines.append(f"- 文件: [{p.get('_file', '?')}]({p.get('_file', '?')})")
            lines.append(f"- 方法: {p.get('extraction_method', '?')}")
            lines.append(f"- 正文: {len(p.get('text', ''))} chars")
            lines.append(f"- 摘要: {text_preview}...")
            lines.append("")

        if self.failed_urls:
            lines += ["## 失败的链接", ""]
            for f in self.failed_urls:
                lines.append(f"- {f['url']}: {f['reason']}")

        (self.pack_dir / "00-research-brief.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _generate_link_inventory(self):
        """生成 01-link-inventory.md。"""
        now = datetime.now(timezone.utc).isoformat()
        expanded = [l for l in self.all_links if l.get("expanded")]
        skipped = [l for l in self.all_links if l.get("skip") or not l.get("expanded")]
        priority_links = [l for l in self.all_links if l.get("priority")]

        lines = [
            "---", f"created: {now}", f"topic: {self.topic}",
            "type: link-inventory", "---", "",
            f"# 链接清单: {self.topic}", "",
            f"## 统计", "",
            f"- 发现链接总数: {len(self.all_links)}",
            f"- 优先链接: {len(priority_links)}",
            f"- 已展开: {len(expanded)}",
            f"- 未展开: {len(skipped)}", "",
            "## 已展开链接", "",
            "| URL | 来源 | 类型 | 优先原因 |",
            "|-----|------|------|---------|",
        ]
        for l in expanded:
            lines.append(
                f"| {escape_table(str(l.get('url', ''))[:100])} "
                f"| {escape_table(l.get('source_page', '')[:60])} "
                f"| {escape_table(l.get('type', ''))} "
                f"| {escape_table(l.get('priority_reason', ''))} |"
            )

        lines += [
            "", "## 已发现但未展开", "",
            "| URL | 来源 | 跳过原因 |",
            "|-----|------|---------|",
        ]
        for l in skipped[:100]:
            lines.append(
                f"| {escape_table(str(l.get('url', ''))[:100])} "
                f"| {escape_table(l.get('source_page', '')[:60])} "
                f"| {escape_table(l.get('skip_reason', ''))} |"
            )

        (self.pack_dir / "01-link-inventory.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _generate_image_inventory(self):
        """生成 02-image-inventory.md。"""
        now = datetime.now(timezone.utc).isoformat()
        downloaded = [i for i in self.all_images if i.get("status") == "ok"]
        deduped = [i for i in downloaded if i.get("note") == "dedup"]
        failed = [i for i in self.all_images if i.get("status") not in ("ok",)]

        lines = [
            "---", f"created: {now}", f"topic: {self.topic}",
            "type: image-inventory", "---", "",
            f"# 图片清单: {self.topic}", "",
            f"## 统计", "",
            f"- 发现图片: {len(self.all_images)} 张",
            f"- 成功下载: {len(downloaded)} 张",
            f"- 去重: {len(deduped)} 张",
            f"- 失败: {len(failed)} 张", "",
        ]

        if downloaded:
            lines += [
                "## 已下载图片", "",
                "| 原始 URL | 本地路径 | 来源 | 大小 | 备注 |",
                "|---------|---------|------|------|------|",
            ]
            for img in downloaded:
                size_kb = img.get("bytes", 0) / 1024
                note = img.get("note", "")
                lines.append(
                    f"| {escape_table(img.get('source_url', '')[:80])} "
                    f"| {img.get('local_path', '')} "
                    f"| {escape_table(img.get('source_page', '')[:40])} "
                    f"| {size_kb:.1f}KB "
                    f"| {note} |"
                )

        if failed:
            lines += ["", "## 失败", "",
                      "| URL | 原因 |", "|-----|------|"]
            for img in failed:
                lines.append(f"| {escape_table(img.get('source_url', '')[:80])} "
                           f"| {img.get('error', '')} |")

        (self.pack_dir / "02-image-inventory.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _generate_media_inventory(self):
        """生成 04-media-inventory.md (对齐 z-web-pack write_media_inventory)。"""
        lines = [
            f"# Media Inventory: {self.topic}", "",
            "## Videos", "",
            "| Status | Kind | Page | Local Path | Source URL | Note |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
        has_video = False
        for page in self.collected_pages:
            for video in getattr(page, "_videos", page.get("_videos", [])) or []:
                has_video = True
                note = video.get("error") or f"{video.get('bytes', 0)} bytes" if video.get("bytes") else ""
                lines.append(
                    "| " + " | ".join([
                        escape_table(video.get("status")),
                        escape_table(video.get("kind")),
                        escape_table(page.get("_file", page.get("url", ""))),
                        escape_table(video.get("local_path")),
                        escape_table(video.get("url")),
                        escape_table(str(note)),
                    ]) + " |"
                )

        # 也包含全局视频记录
        for video in self.all_videos:
            if not has_video:
                has_video = True
            note = video.get("error") or f"{video.get('bytes', 0)} bytes" if video.get("bytes") else ""
            lines.append(
                "| " + " | ".join([
                    escape_table(video.get("status")),
                    escape_table(video.get("kind")),
                    "-",
                    escape_table(video.get("local_path")),
                    escape_table(video.get("url")),
                    escape_table(str(note)),
                ]) + " |"
            )

        if not has_video:
            lines.append("| none | none | none | none | none | no videos found |")

        # 字幕和封面
        subtitles = []
        thumbnails = []
        for video in self.all_videos:
            if video.get("subtitles"):
                subtitles.extend(video["subtitles"])
            if video.get("thumbnail"):
                thumbnails.append(video["thumbnail"])

        if subtitles:
            lines += ["", "## Subtitles", ""]
            for s in subtitles:
                lines.append(f"- [{Path(s).name}]({s})")

        if thumbnails:
            lines += ["", "## Thumbnails", ""]
            for t in thumbnails:
                lines.append(f"- ![]({t})")

        (self.pack_dir / "04-media-inventory.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _generate_reading_map(self):
        """生成 03-reading-map.md。"""
        now = datetime.now(timezone.utc).isoformat()
        lines = [
            "---", f"created: {now}", f"topic: {self.topic}",
            "type: reading-map", "---", "",
            f"# 阅读路线图: {self.topic}", "",
            "## 推荐阅读顺序", "",
        ]
        for i, page in enumerate(self.collected_pages, 1):
            role_label = "⭐ 入口" if page.get("role") == "main" else "🔗 关联"
            lines.append(f"{i}. {role_label} [{page['title']}]({page.get('_file', '?')})")
            lines.append(f"   - 来源: {page['url']}")
            lines.append(f"   - 方法: {page.get('extraction_method', '?')}")
            lines.append(f"   - 深度: {page.get('depth', 0)}, 正文: {len(page.get('text', ''))} chars")
            lines.append("")

        lines += [
            "## 阅读建议",
            "- 按顺序阅读可建立递进理解",
            "- 入口页面 (MAIN) 提供核心内容，关联页面 (LINKED) 提供补充视角",
            "- 使用 Obsidian 的图谱视图查看概念关联", "",
            "---", "*由 PKB web_pack v3 采集器生成 · z-web-pack 对齐*",
        ]
        (self.pack_dir / "03-reading-map.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _generate_manifest(self):
        """生成 manifest.json。"""
        images_downloaded = sum(1 for i in self.all_images if i.get("status") == "ok")
        videos_downloaded = sum(1 for v in self.all_videos if v.get("status") == "ok")

        status = "completed_with_errors" if self.failed_urls else "completed"

        manifest = {
            "type": "web_pack",
            "version": "3.0.0",
            "collector": "PKB web_pack v3 (z-web-pack aligned)",
            "topic": self.topic,
            "created": self.started_at.strftime("%Y-%m-%dT%H:%M:%S"),
            "output_dir": str(self.pack_dir),
            "source_urls": self.source_urls,
            "mode": self.mode,
            "max_depth": self.max_depth,
            "max_pages": self.max_pages,
            "videos_mode": self.videos_mode,
            "pages_collected": len(self.collected_pages),
            "images_discovered": len(self.all_images),
            "images_downloaded": images_downloaded,
            "videos_discovered": len(self.all_videos),
            "videos_downloaded": videos_downloaded,
            "links_discovered": len(self.all_links),
            "links_expanded": sum(1 for l in self.all_links if l.get("expanded")),
            "failed_links": len(self.failed_urls),
            "extraction_methods": list(set(
                p.get("extraction_method", "unknown") for p in self.collected_pages
            )),
            "privacy": self.privacy,
            "status": status,
        }
        if self.github_meta:
            manifest["github"] = self.github_meta

        (self.pack_dir / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    def _print_report(self):
        """打印采集报告。"""
        images_ok = sum(1 for i in self.all_images if i.get("status") == "ok")
        videos_ok = sum(1 for v in self.all_videos if v.get("status") == "ok")
        expanded = sum(1 for l in self.all_links if l.get("expanded"))
        status = "completed" if not self.failed_urls else "completed_with_errors"
        jina_count = sum(1 for p in self.collected_pages if p.get("via_jina"))

        print()
        print("=" * 60)
        print("🌐 PKB WebPack v3 采集报告")
        print("=" * 60)
        print(f"   主题: {self.topic}")
        print(f"   输出: {self.pack_dir}")
        print(f"   状态: {status}")
        print(f"   模式: {self.mode}")
        print(f"   📄 页面: {len(self.collected_pages)}"
              f" (Jina: {jina_count})")
        print(f"   🔗 链接: {len(self.all_links)} (展开: {expanded})")
        print(f"   🖼️  图片: {len(self.all_images)} (下载: {images_ok})")
        print(f"   🎬 视频: {len(self.all_videos)} (下载: {videos_ok})")
        print(f"   ❌ 失败: {len(self.failed_urls)}")
        if self._render_stats["attempted"] > 0:
            print(f"   🎭 Playwright: 尝试 {self._render_stats['attempted']} 次, "
                  f"采用 {self._render_stats['used']} 次, "
                  f"失败 {self._render_stats['failed']} 次")
            # 打印网络诊断摘要
            for p in self.collected_pages:
                rd = p.get("_render_diagnostic")
                if rd and rd.get("network"):
                    nd = rd["network"]
                    if nd.get("total_responses_seen", 0) > 0:
                        print(f"   🌐 Network: {nd.get('total_responses_seen', 0)} 响应, "
                              f"{nd.get('candidates_found', 0)} 候选")
                        sel = rd.get("selection", {})
                        if sel:
                            print(f"      选择: {sel.get('selected_method', '?')} "
                                  f"({sel.get('selection_reason', '?')})")
                        break
        print()
        print("   提取方法:")
        methods = {}
        for p in self.collected_pages:
            m = p.get("extraction_method", "unknown")
            methods[m] = methods.get(m, 0) + 1
        for m, c in sorted(methods.items()):
            print(f"      {m}: {c} 页")
        # 打印选择诊断
        for p in self.collected_pages:
            sel = p.get("selection_diagnostic")
            if sel:
                print()
                print("   最终选择诊断:")
                print(f"      HTTP: {sel.get('http_score', 0)} (完整: {sel.get('http_complete', False)})")
                print(f"      DOM:  {sel.get('dom_score', 0)} (完整: {sel.get('dom_complete', False)})")
                print(f"      Network: {sel.get('network_score', 0)} (完整: {sel.get('network_complete', False)})")
                print(f"      → 选择: {sel.get('selected_method', '?')} ({sel.get('selection_reason', '?')})")
                break
        print()
        print("   生成文件:")
        for f in sorted(self.pack_dir.glob("*")):
            if f.is_file():
                print(f"      {f.name}")
            elif f.is_dir() and f.name == "assets":
                asset_count = len(list(f.iterdir()))
                print(f"      assets/ ({asset_count} 个文件)")
        print("=" * 60)

    def _build_result(self) -> dict:
        """构建返回结果 JSON。"""
        result: dict[str, Any] = {
            "topic": self.topic,
            "output_dir": str(self.pack_dir),
            "mode": self.mode,
            "pages_collected": len(self.collected_pages),
            "images_discovered": len(self.all_images),
            "images_downloaded": sum(1 for i in self.all_images if i.get("status") == "ok"),
            "videos_discovered": len(self.all_videos),
            "videos_downloaded": sum(1 for v in self.all_videos if v.get("status") == "ok"),
            "links_discovered": len(self.all_links),
            "links_expanded": sum(1 for l in self.all_links if l.get("expanded")),
            "failed_links": len(self.failed_urls),
            "status": "completed" if not self.failed_urls else "completed_with_errors",
            "extraction_methods": list(set(
                p.get("extraction_method", "unknown") for p in self.collected_pages
            )),
            "manifest_generated": (self.pack_dir / "manifest.json").exists(),
        }
        if self._render_stats["attempted"] > 0:
            result["render_stats"] = dict(self._render_stats)
        return result


# ───────────────────────────────────────────────────────────────
# CLI
# ───────────────────────────────────────────────────────────────

def main():
    configure_stdout_utf8()

    parser = argparse.ArgumentParser(
        description="PKB web_pack v3 — z-web-pack aligned web content collector",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Modes:
  --mode full    All features: full image pipeline, video, cookies (default)
  --mode safe    Conservative: no cookies, no video download, basic images

Examples:
  python tools/web_pack.py --topic "AI Safety" --url "https://example.com/article"
  python tools/web_pack.py --topic "GitHub Skill" --url "https://github.com/u/r/tree/main/path"
  python tools/web_pack.py --topic "Videos" --url "url1" --url "url2" --videos all --download-media
  python tools/web_pack.py --topic "Research" --url "url" --mode safe --videos off
        """,
    )
    parser.add_argument("--topic", required=True, help="采集主题名")
    parser.add_argument("--url", action="append", default=[], dest="urls",
                        help="要采集的网页 URL (可多次使用)")
    parser.add_argument("--urls-file", default=None, help="URL 列表文件 (每行一个)")
    parser.add_argument("--max-depth", type=int, default=1, help="链接展开深度 (默认: 1)")
    parser.add_argument("--max-pages", type=int, default=80, help="最大页面数 (默认: 80)")
    parser.add_argument("--output-root", default=str(WEBPACKS_DIR),
                        help=f"输出根目录 (默认: {WEBPACKS_DIR})")
    parser.add_argument("--privacy", default="public", choices=["public", "internal"],
                        help="隐私级别 (默认: public)")

    # ── 模式 ──
    parser.add_argument("--mode", default="full", choices=["safe", "full"],
                        help="采集模式: safe (基础) / full (全部能力, 默认)")

    # ── 视频/媒体 ──
    parser.add_argument("--videos", default="direct", choices=["off", "direct", "all"],
                        help="视频模式: off=不下载 / direct=仅直链(默认) / all=含平台视频")
    parser.add_argument("--download-media", action="store_true",
                        help="启用完整媒体下载 (平台视频/字幕/封面)")
    parser.add_argument("--browser-cookies", default="",
                        choices=["", "chrome", "edge", "firefox", "safari"],
                        help="平台视频遇到风控时从指定浏览器读取 cookie (仅 --mode full)")
    parser.add_argument("--max-video-mb", type=float, default=300.0,
                        help="单个视频上限 MB (默认: 300)")
    parser.add_argument("--max-image-mb", type=float, default=20.0,
                        help="单张图片上限 MB (默认: 20)")

    # ── 链接 ──
    parser.add_argument("--same-domain-only", action="store_true",
                        help="仅采集同域链接")
    parser.add_argument("--delay", type=float, default=DEFAULT_DELAY,
                        help=f"页面间隔延迟秒 (默认: {DEFAULT_DELAY})")
    parser.add_argument("--no-jina", action="store_true",
                        help="禁用 Jina Reader 兜底")

    # ── Playwright 动态渲染 ──
    parser.add_argument("--render", action="store_true",
                        help="当普通提取质量不足时，启用 Playwright 动态渲染")
    parser.add_argument("--headed", action="store_true",
                        help="Playwright 以可视模式启动（自动启用 --render）")
    parser.add_argument("--debug-network", action="store_true",
                        help="输出脱敏后的网络捕获诊断到 .pkbcache/network-debug/（自动启用 --render）")

    args = parser.parse_args()

    # ── 验证 ──
    urls = list(args.urls)
    if args.urls_file:
        urls_file = Path(args.urls_file)
        if urls_file.exists():
            with open(urls_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        urls.append(line)

    if not urls:
        print("❌ 请提供至少一个 URL (--url 或 --urls-file)")
        sys.exit(1)

    if not HAS_REQUESTS or not HAS_BS4:
        print("❌ 缺少必要依赖。请运行:")
        print("   pip install requests beautifulsoup4 lxml markdownify readability-lxml trafilatura")
        sys.exit(1)

    # ── 安全校验 ──
    if args.browser_cookies and args.mode != "full":
        print("⚠️  --browser-cookies 仅在 --mode full 下可用，已忽略")
        args.browser_cookies = ""

    if args.browser_cookies and not args.download_media:
        print("⚠️  --browser-cookies 需要 --download-media，已忽略")
        args.browser_cookies = ""

    # ── Playwright 渲染配置 ──
    render_options = None
    debug_network = args.debug_network
    if args.render or args.headed or args.debug_network:
        if not HAS_PLAYWRIGHT:
            print("❌ Playwright 未安装。请运行:")
            if PlaywrightRenderer is not None:
                print(f"   {PlaywrightRenderer.install_hint()}")
            else:
                print("   pip install -r requirements-playwright.txt")
                print("   playwright install chromium")
            sys.exit(1)

        use_persistent = args.mode != "safe"
        profile_dir = None
        if use_persistent:
            profile_dir = PKB_ROOT / ".pkbcache" / "playwright-profile"

        # 网络捕获配置
        try:
            from network_capture import NetworkCaptureOptions
            net_opts = NetworkCaptureOptions(enabled=True)
        except ImportError:
            net_opts = None

        render_options = RenderOptions(
            enabled=True,
            headed=args.headed,
            use_persistent_profile=use_persistent,
            profile_dir=profile_dir,
            network=net_opts,
            html_extractor=_extract_content_from_html,
        )

        # --debug-network 写入诊断文件
        if debug_network:
            _write_network_debug(render_options, net_opts, PKB_ROOT)

    # ── 运行 ──
    collector = WebPackCollector(
        topic=args.topic,
        source_urls=urls,
        max_depth=args.max_depth,
        max_pages=args.max_pages,
        output_root=Path(args.output_root),
        privacy=args.privacy,
        mode=args.mode,
        videos=args.videos,
        max_image_mb=args.max_image_mb,
        max_video_mb=args.max_video_mb,
        browser_cookies=args.browser_cookies,
        download_media=args.download_media,
        same_domain_only=args.same_domain_only,
        delay=args.delay,
        no_jina=args.no_jina,
        render_options=render_options,
        debug_network=debug_network,
    )
    result = collector.run()

    # JSON REPORT
    print()
    print("--- JSON REPORT ---")
    print(json.dumps(result, ensure_ascii=False, indent=2))

    sys.exit(0 if result["status"] == "completed" else 1)


if __name__ == "__main__":
    main()
