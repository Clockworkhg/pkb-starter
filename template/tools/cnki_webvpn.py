#!/usr/bin/env python3
"""Test CNKI paper download via WebVPN institutional proxy.

Concept: CUC WebVPN encrypts CNKI URLs → institutional access bypasses paywall.
Requirements: CUC CAS credentials + scansci-pdf + selenium.

Usage:
    python tools/cnki_webvpn.py setup          # Configure school + login
    python tools/cnki_webvpn.py test <url>     # Test CNKI page through WebVPN
    python tools/cnki_webvpn.py download <url> # Full fetch: login → CNKI page → PDF link
"""

from __future__ import annotations

import argparse
import os
import pickle
import re
import sys
import time
from pathlib import Path
from typing import Any

try:
    import requests
except ImportError:
    print("ERROR: requests not installed")
    sys.exit(1)

# Project paths
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_COOKIE_FILE = _PROJECT_ROOT / ".pkb-local" / "webvpn_cookies.pkl"


def _load_scansci_config() -> dict[str, Any]:
    """Load scansci-pdf config, importing only if available."""
    try:
        from scansci_pdf.config import load_config
        return load_config()
    except ImportError:
        return {}


def _save_scansci_config(config: dict[str, Any]) -> None:
    """Save scansci-pdf config via its config module."""
    try:
        from scansci_pdf.config import update_config
        for key, value in config.items():
            update_config(key, value)
    except ImportError:
        pass


def _get_webvpn_base() -> str | None:
    """Get current WebVPN base URL from scansci-pdf config or env."""
    config = _load_scansci_config()
    base = config.get("vpnsci_base_url", "").strip()
    if base:
        return base

    # Try to resolve from school name
    school = config.get("vpnsci_school", "").strip()
    if school:
        try:
            from scansci_pdf.schools import search_schools
            results = search_schools(school)
            if results:
                return results[0].host
        except ImportError:
            pass

    return None


def setup_school(school_name: str) -> bool:
    """Configure school in scansci-pdf and open browser for CAS login."""
    try:
        from scansci_pdf.schools import search_schools
        from scansci_pdf.config import update_config
    except ImportError:
        print("❌ scansci-pdf not installed. Run: pip install scansci-pdf")
        return False

    results = search_schools(school_name)
    if not results:
        print(f"❌ School '{school_name}' not found in scansci-pdf database (137 schools)")
        print("   Available schools (sample):")
        try:
            from scansci_pdf.schools import list_schools
            for s in list_schools()[:20]:
                print(f"     {s.name} — {s.host}")
        except Exception:
            pass
        return False

    school = results[0]
    print(f"✅ Found: {school.name} ({school.province})")
    print(f"   WebVPN: {school.host}")
    print()

    # Write config
    update_config("vpnsci_school", school.name)
    update_config("vpnsci_base_url", school.host)
    update_config("vpnsci_enabled", True)
    print("✅ scansci-pdf config updated")

    # Ensure pkb-local dir exists
    os.makedirs(_COOKIE_FILE.parent, exist_ok=True)

    # Open browser for CAS login
    print()
    print("=" * 60)
    print("  Opening browser for CAS login...")
    print(f"  Log in to: {school.host}")
    print("=" * 60)

    try:
        from scansci_pdf.sources.vpnsci import vpnsci_login
        config = _load_scansci_config()
        ok = vpnsci_login(config)
        if ok:
            print("✅ CAS login successful — cookies saved")
            return True
        else:
            print("❌ CAS login failed or timed out")
            return False
    except ImportError:
        print("❌ scansci-pdf vpnsci module not available")
        return False
    except Exception as e:
        print(f"❌ Login error: {e}")
        return False


def _load_saved_cookies() -> dict[str, str]:
    """Load cookies from saved session."""
    cookies = {}

    # Try scansci-pdf's cookie file first
    from scansci_pdf.config import load_config
    config = load_config()
    cookie_file = config.get("vpnsci_cookie_file", "")
    if cookie_file and os.path.exists(cookie_file):
        try:
            with open(cookie_file, "rb") as f:
                cookies_list = pickle.load(f)
            cookies = {c["name"]: c["value"] for c in cookies_list}
            if cookies:
                return cookies
        except Exception:
            pass

    # Try our own cookie file
    if _COOKIE_FILE.exists():
        try:
            with open(_COOKIE_FILE, "rb") as f:
                cookies_list = pickle.load(f)
            cookies = {c["name"]: c["value"] for c in cookies_list}
        except Exception:
            pass

    return cookies


def convert_cnki_url(cnki_url: str) -> str | None:
    """Convert a CNKI URL to go through the configured WebVPN."""
    base = _get_webvpn_base()
    if not base:
        print("❌ WebVPN not configured. Run: python tools/cnki_webvpn.py setup")
        return None

    try:
        from scansci_pdf.sources.vpnsci import convert_url
        from scansci_pdf.config import load_config
        config = load_config()
        return convert_url(cnki_url, base, config)
    except ImportError:
        pass

    # Fallback: basic URL construction (no encryption, but works for some WebVPNs)
    from urllib.parse import urlparse, quote
    parsed = urlparse(cnki_url)
    encrypted_host = quote(parsed.netloc, safe="")
    path = parsed.path + ("?" + parsed.query if parsed.query else "")
    return f"{base}/https/{encrypted_host}{path}"


def test_cnki_access(cnki_url: str) -> dict[str, Any]:
    """Test if a CNKI page is accessible through WebVPN."""
    vpn_url = convert_cnki_url(cnki_url)
    if not vpn_url:
        return {"success": False, "error": "URL conversion failed"}

    cookies = _load_saved_cookies()
    if not cookies:
        return {
            "success": False,
            "error": "No saved cookies. Run setup first to log in.",
            "vpn_url": vpn_url,
        }

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }

    print(f"🔗 Testing CNKI access through WebVPN...")
    print(f"   Original: {cnki_url[:100]}...")
    print(f"   Via VPN:  {vpn_url[:120]}...")
    print()

    try:
        session = requests.Session()
        session.cookies.update(cookies)
        resp = session.get(vpn_url, headers=headers, timeout=30, allow_redirects=True)
        print(f"   Status: {resp.status_code}")
        print(f"   Content-Type: {resp.headers.get('Content-Type', '?')[:80]}")
        print(f"   Size: {len(resp.text):,} chars")

        # Check if we got a CNKI page or were redirected to login
        text = resp.text

        if "login" in text.lower() and "cas" in text.lower():
            print("   ⚠️  Redirected to CAS login — cookies may have expired")
            return {
                "success": False,
                "error": "CAS login required (cookies expired)",
                "vpn_url": vpn_url,
                "status": resp.status_code,
            }

        if "知网" in text or "cnki" in text.lower() or "kcms" in text.lower():
            print("   ✅ CNKI page accessible through WebVPN!")

            # Try to find PDF download link
            pdf_links = []
            # Common CNKI PDF patterns
            for pattern in [
                r'href=["\']([^"\']*download[^"\']*\.pdf[^"\']*)["\']',
                r'href=["\']([^"\']*download[^"\']*)["\']',
                r'window\.location\s*=\s*["\']([^"\']+)["\']',
                r'<a[^>]*href=["\']([^"\']*pdf[^"\']*)["\'][^>]*>',
                r'<iframe[^>]*src=["\']([^"\']*pdf[^"\']*)["\']',
            ]:
                matches = re.findall(pattern, text, re.IGNORECASE)
                pdf_links.extend(matches)

            if pdf_links:
                print(f"   📄 Found {len(pdf_links)} potential PDF links:")
                for link in pdf_links[:5]:
                    print(f"      {link[:120]}")

            return {
                "success": True,
                "vpn_url": vpn_url,
                "status": resp.status_code,
                "has_cnki_content": True,
                "pdf_links": pdf_links[:10],
                "page_size": len(text),
            }
        else:
            print("   ⚠️  Unexpected page content (may not be CNKI)")
            return {
                "success": False,
                "error": "Unexpected page content",
                "vpn_url": vpn_url,
                "status": resp.status_code,
                "preview": text[:500],
            }

    except requests.RequestException as e:
        print(f"   ❌ Request failed: {e}")
        return {"success": False, "error": str(e), "vpn_url": vpn_url}


def main():
    parser = argparse.ArgumentParser(
        prog="cnki_webvpn",
        description="Test CNKI paper access via institutional WebVPN",
    )
    sub = parser.add_subparsers(dest="command")

    setup_p = sub.add_parser("setup", help="Configure school and login via CAS")
    setup_p.add_argument(
        "school",
        nargs="?",
        default="中国传媒大学",
        help="School name (default: 中国传媒大学)",
    )

    test_p = sub.add_parser("test", help="Test CNKI URL access through WebVPN")
    test_p.add_argument("url", help="CNKI paper URL")

    dl_p = sub.add_parser("download", help="Full pipeline: test access + find PDF")
    dl_p.add_argument("url", help="CNKI paper URL")

    args = parser.parse_args()

    if args.command == "setup":
        ok = setup_school(args.school)
        if ok:
            print()
            print("=" * 60)
            print("  ✅ Setup complete! You can now test CNKI access:")
            print(f"     python tools/cnki_webvpn.py test <CNKI_URL>")
            print("=" * 60)

    elif args.command in ("test", "download"):
        result = test_cnki_access(args.url)
        if result.get("success"):
            print()
            print("=" * 60)
            print("  ✅ WebVPN → CNKI working!")
            if result.get("pdf_links"):
                print(f"  📄 {len(result['pdf_links'])} potential PDF links found")
            else:
                print("  ⚠️  No PDF links found (may need page interaction)")
            print("=" * 60)
        else:
            print()
            print("=" * 60)
            print(f"  ❌ {result.get('error', 'Failed')}")
            print("=" * 60)
    else:
        parser.print_help()
        print()
        print("Quick start:")
        print("  1. python tools/cnki_webvpn.py setup")
        print("  2. python tools/cnki_webvpn.py test <CNKI_URL>")


if __name__ == "__main__":
    main()
