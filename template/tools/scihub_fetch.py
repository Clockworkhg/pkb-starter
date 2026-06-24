#!/usr/bin/env python3
"""Fetch papers via multi-source pipeline (scansci-pdf) with Sci-Hub fallback.

Upgraded from single-source Sci-Hub to scansci-pdf's 13-source parallel resolver.
Fail-open: if scansci-pdf is unavailable, falls back to direct Sci-Hub scraping.

## Architecture

    fetch_paper(doi, output_path)
    ├── Strategy 0: scansci_bridge (13-source race)  ← PRIMARY (NEW)
    │   ├── OA first: Unpaywall, arXiv, EuropePMC, DOAJ, OpenAIRE
    │   ├── Publisher: Nature, ScienceDirect, Springer, etc.
    │   └── Sci-Hub (via scansci-pdf's own scihub module)
    ├── Strategy 1: Direct Sci-Hub scraping          ← FALLBACK
    └── Strategy 2: Alternative URL                  ← LAST RESORT

## Usage

    # As CLI (hardcoded batch - backward compat)
    python tools/scihub_fetch.py

    # As library (new)
    from tools.scihub_fetch import fetch_paper
    result = fetch_paper("10.1038/s41586-020-2649-2", "/path/to/output.pdf")
"""

import os
import re
import sys
import time
import urllib.parse
from pathlib import Path

try:
    import requests
except ImportError:
    print("ERROR: requests not installed. Run: pip install requests")
    sys.exit(1)

# ── Fail-open: try to import scansci_bridge ────────────────────────────────
_SCANSCI_AVAILABLE = False
try:
    # Add project root to path so we can import our own bridge
    _TOOLS_DIR = Path(__file__).resolve().parent
    _PROJECT_ROOT = _TOOLS_DIR.parent
    if str(_PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(_PROJECT_ROOT))

    from tools.scansci_bridge import download_paper as _scansci_download
    from tools.scansci_bridge import is_available as _scansci_available
    _SCANSCI_AVAILABLE = _scansci_available()
except ImportError:
    pass

# ── Configuration ──────────────────────────────────────────────────────────

ROOT = str(_PROJECT_ROOT / "raw" / "papers")

SCI_HUB_DOMAINS = [
    "sci-hub.shop",
    "sci-hub.ee",
    "sci-hub.st",
    "sci-hub.se",
    "sci-hub.ru",
]

PAPERS = [
    {
        "filename": "2025_青少年网络社会心态概念流变_南通大学学报.pdf",
        "doi": "10.12451/202508.02261",
        "title": "燕道成、吴涵 — 青少年网络社会心态的概念流变",
        "alt_url": "https://zsyyb.cn/abs/202508.02261v1",  # preprint
    },
    {
        "filename": "2023_社交媒体使用青少年心理健康_中国学校卫生.pdf",
        "doi": "10.16835/j.cnki.1000-9817.2023.12.033",
        "title": "陈益涵、谢斌 — 社交媒体使用对青少年心理健康",
        "alt_url": "https://r.cnki.net/kcms/detail/detail.aspx?DbCode=CFJD&dbname=CFJDLAST2024&filename=XIWS202312033",
    },
    {
        "filename": "2025_未成年人数字行为风险治理_社会政策研究.pdf",
        "doi": None,
        "title": "李鑫、李韬、周瑞春 — 未成年人数字行为及风险治理",
        "alt_url": "http://mp.weixin.qq.com/s?__biz=MzAxMzU5NDY2MQ==&mid=2650940706&idx=1&sn=3d85b7f19bce31cbb9c06a07100773f8",
    },
    # Bonus: other domains' key missing papers
    {
        "filename": None,  # will save to algorithm-power dir
        "doi": "10.6092/issn.1825-9618/19863",
        "title": "Theories and Dimensions of Algorithmic Power — Unibo",
        "save_dir": "algorithmic-power",
        "save_as": "2024_Theories_Dimensions_Algorithmic_Power.pdf",
    },
]


# ── Public API ─────────────────────────────────────────────────────────────


def fetch_paper(
    doi: str,
    output_path: str | Path,
    *,
    strategy: str = "fastest",
    use_tor: bool = False,
    fallback_scihub: bool = True,
) -> dict:
    """Download a paper by DOI.

    Tries scansci-pdf multi-source first, falls back to direct Sci-Hub.

    Args:
        doi: Paper DOI (e.g. "10.1038/s41586-020-2649-2")
        output_path: Where to save the PDF
        strategy: Download strategy for scansci-pdf
                  ("fastest", "oa_first", "scihub_only", "legal_only")
        use_tor: Route through Tor
        fallback_scihub: If True and scansci-pdf fails, try direct Sci-Hub

    Returns:
        {"success": bool, "file": str, "source": str, "size": int, ...}
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Strategy 0: scansci-pdf multi-source (PRIMARY)
    if _SCANSCI_AVAILABLE:
        try:
            result = _scansci_download(
                identifier=doi,
                output_dir=str(output_path.parent),
                strategy=strategy,
                use_tor=use_tor,
            )
            if result.get("success"):
                src_file = result.get("file", "")
                if src_file and Path(src_file).exists():
                    # If scansci-pdf saved to a different filename, copy to expected path
                    if Path(src_file) != output_path:
                        import shutil
                        shutil.copy2(src_file, output_path)
                    return {
                        "success": True,
                        "file": str(output_path),
                        "source": result.get("source", "scansci-pdf"),
                        "size": os.path.getsize(output_path),
                        "method": "scansci-pdf",
                        "renamed": result.get("renamed", False),
                    }
                return {
                    "success": False,
                    "error": "scansci-pdf reported success but file not found",
                    "method": "scansci-pdf",
                }
            # scansci-pdf failed — continue to fallback
        except Exception as exc:
            # scansci-pdf errored — continue to fallback
            pass

    if not fallback_scihub:
        return {
            "success": False,
            "error": "scansci-pdf unavailable and fallback disabled",
            "method": "none",
        }

    # Strategy 1: Direct Sci-Hub (FALLBACK)
    session = _create_session()
    ok, content, msg = _try_scihub(session, doi)
    if ok and content and len(content) > 10000:
        with open(output_path, "wb") as f:
            f.write(content)
        return {
            "success": True,
            "file": str(output_path),
            "source": "sci-hub-direct",
            "size": len(content),
            "method": "sci-hub-direct",
            "detail": msg,
        }

    return {
        "success": False,
        "error": msg or "All strategies failed",
        "method": "sci-hub-direct-failed",
    }


# ── Internal: HTTP session & Sci-Hub scraping ──────────────────────────────


def _create_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    })
    return s


def _try_scihub(session: requests.Session, doi: str, timeout: int = 30) -> tuple:
    """Try Sci-Hub with multiple domains. Returns (ok, content, message)."""
    for domain in SCI_HUB_DOMAINS:
        url = f"https://{domain}/{doi}"
        try:
            print(f"  → Trying {domain}...")
            resp = session.get(url, timeout=timeout, allow_redirects=True)
            print(f"    Status: {resp.status_code}, Content-type: {resp.headers.get('Content-Type','?')[:60]}")

            ct = resp.headers.get("Content-Type", "").lower()
            if "pdf" in ct:
                return True, resp.content, f"Direct PDF from {domain}"

            text = resp.text[:100000]

            # Look for PDF iframe
            iframe_match = re.search(r'<iframe[^>]+src=["\']([^"\']+)["\']', text)
            if iframe_match:
                iframe_src = iframe_match.group(1)
                full_url = urllib.parse.urljoin(url, iframe_src)
                print(f"    Found iframe: {full_url[:120]}")
                pdf_resp = session.get(full_url, timeout=timeout, allow_redirects=True,
                                       headers={"Referer": url})
                if "pdf" in pdf_resp.headers.get("Content-Type", "").lower():
                    return True, pdf_resp.content, f"PDF via iframe from {domain}"
                if len(pdf_resp.content) > 10000 and pdf_resp.content[:4] == b"%PDF":
                    return True, pdf_resp.content, f"PDF via iframe (magic) from {domain}"

            # Look for PDF links
            pdf_urls = re.findall(r'(https?://[^"\s<>]+\.pdf[^"\s<>]*)', text)
            for pdf_url in pdf_urls[:3]:
                try:
                    pdf_resp = session.get(pdf_url, timeout=timeout, headers={"Referer": url})
                    if len(pdf_resp.content) > 10000 and pdf_resp.content[:4] == b"%PDF":
                        return True, pdf_resp.content, f"PDF via link from {domain}: {pdf_url[:80]}"
                except Exception:
                    pass

            # Look for embed/object
            embed_match = re.search(r'<embed[^>]+src=["\']([^"\']+)["\']', text)
            if embed_match:
                embed_src = embed_match.group(1)
                full_url = urllib.parse.urljoin(url, embed_src)
                pdf_resp = session.get(full_url, timeout=timeout, headers={"Referer": url})
                if len(pdf_resp.content) > 10000 and pdf_resp.content[:4] == b"%PDF":
                    return True, pdf_resp.content, f"PDF via embed from {domain}"

            # Check if there's a captcha
            if "captcha" in text.lower() or "verify" in text.lower():
                print(f"    ⚠️  Captcha detected on {domain}")

            time.sleep(1)

        except requests.ConnectionError as e:
            print(f"    Connection error: {e}")
        except requests.Timeout:
            print(f"    Timeout")
        except Exception as e:
            print(f"    Error: {type(e).__name__}: {e}")

    return False, None, "All Sci-Hub domains failed"


def _try_alternative(session: requests.Session, paper: dict, timeout: int = 30) -> tuple:
    """Try alternative download sources. Returns (ok, content, message)."""
    alt = paper.get("alt_url")
    if not alt:
        return False, None, "No alternative URL"

    try:
        print(f"  → Trying alt: {alt[:100]}...")
        resp = session.get(alt, timeout=timeout, allow_redirects=True)
        ct = resp.headers.get("Content-Type", "").lower()

        if "pdf" in ct:
            return True, resp.content, "PDF from alt URL"

        # Check magic bytes
        if len(resp.content) > 10000 and resp.content[:4] == b"%PDF":
            return True, resp.content, "PDF from alt URL (magic)"

        # Parse HTML for PDF links
        text = resp.text[:100000]
        pdf_urls = re.findall(r'(https?://[^"\s<>]+\.pdf[^"\s<>]*)', text)
        for pdf_url in pdf_urls[:3]:
            try:
                pdf_resp = session.get(pdf_url, timeout=timeout, headers={"Referer": alt})
                if len(pdf_resp.content) > 10000 and pdf_resp.content[:4] == b"%PDF":
                    return True, pdf_resp.content, f"PDF via alt link: {pdf_url[:80]}"
            except Exception:
                pass

        return False, None, f"Alt URL returned {ct} ({len(resp.content)} bytes)"

    except Exception as e:
        return False, None, f"Alt error: {e}"


# ── CLI: backward-compatible batch mode ────────────────────────────────────


def main():
    os.makedirs(ROOT, exist_ok=True)
    results = {"success": [], "failed": []}

    print(f"🔬 scihub_fetch (scansci-pdf: {'✅ available' if _SCANSCI_AVAILABLE else '❌ unavailable'})")
    print(f"   Strategy: scansci-pdf multi-source → direct Sci-Hub fallback\n")

    for i, paper in enumerate(PAPERS):
        title = paper["title"]
        save_dir = paper.get("save_dir", "youth-social-mentality")
        if save_dir != "youth-social-mentality":
            paper["filename"] = paper["save_as"]
            save_path = os.path.join(ROOT.replace("youth-social-mentality", save_dir), paper["save_as"])
        else:
            save_path = os.path.join(ROOT, paper["filename"])

        os.makedirs(os.path.dirname(save_path), exist_ok=True)

        if os.path.exists(save_path) and os.path.getsize(save_path) > 10000:
            results["success"].append((title, save_path, "already exists"))
            print(f"⏭  [{i+1}/4] {title} (exists)")
            continue

        print(f"\n📥 [{i+1}/4] {title}")

        ok, content, msg = False, None, ""

        # Strategy 0: scansci-pdf bridge (PRIMARY)
        if _SCANSCI_AVAILABLE and paper.get("doi"):
            print(f"  Strategy 0: scansci-pdf multi-source (DOI: {paper['doi']})")
            try:
                result = _scansci_download(
                    identifier=paper["doi"],
                    output_dir=str(Path(save_path).parent),
                    strategy="fastest",
                )
                if result.get("success"):
                    src_file = result.get("file", "")
                    if src_file and Path(src_file).exists():
                        import shutil
                        if Path(src_file) != Path(save_path):
                            shutil.copy2(src_file, save_path)
                        ok = True
                        content = b""  # not needed — file already saved
                        msg = f"scansci-pdf: {result.get('source', 'unknown')} ({os.path.getsize(save_path):,} bytes)"
                        print(f"  ✅ {msg}")
                    else:
                        print(f"  ❌ scansci-pdf: file not found after download")
                else:
                    err = result.get("error", "unknown")
                    print(f"  ❌ scansci-pdf: {err}")
            except Exception as exc:
                print(f"  ❌ scansci-pdf error: {exc}")

        # Strategy 1: Direct Sci-Hub
        if not ok and paper.get("doi"):
            session = _create_session()
            print(f"  Strategy 1: Direct Sci-Hub (DOI: {paper['doi']})")
            ok, content, msg = _try_scihub(session, paper["doi"])

        # Strategy 2: Alternative URL
        if not ok and paper.get("alt_url"):
            session = _create_session() if 'session' not in dir() else session
            print(f"  Strategy 2: Alternative URL")
            ok, content, msg = _try_alternative(session, paper)

        if ok and content and len(content) > 10000:
            with open(save_path, "wb") as f:
                f.write(content)
            size = len(content)
        elif ok:
            # Already saved by scansci-pdf
            size = os.path.getsize(save_path) if os.path.exists(save_path) else 0
        else:
            size = 0

        if ok and (size > 10000):
            results["success"].append((title, save_path, msg))
            print(f"  ✅ {msg} ({size:,} bytes)" if size > 10000 else f"  ✅ {msg}")
        else:
            results["failed"].append((title, msg or "Failed"))
            print(f"  ❌ {msg}")

        time.sleep(1)

    print("\n" + "=" * 60)
    print(f"SCIHUB FETCH SUMMARY: ✅ {len(results['success'])} | ❌ {len(results['failed'])}")
    for title, path, msg in results["success"]:
        print(f"  ✅ {title} → {Path(path).name}")
    for title, msg in results["failed"]:
        print(f"  ❌ {title} — {msg}")

    return len(results["success"])


if __name__ == "__main__":
    main()
