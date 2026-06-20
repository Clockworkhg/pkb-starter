#!/usr/bin/env python3
"""PKB bridge to scansci-pdf multi-source paper download engine.

Wraps the scansci_pdf Python API for use within PKB's paper download pipeline.
Replaces single-source Sci-Hub with 13-source parallel resolution ("赛马模式").

## Quick Start

    # Download a single paper
    python tools/scansci_bridge.py download 10.1038/s41586-020-2649-2

    # Batch download
    python tools/scansci_bridge.py download 10.1038/s41586-020-2649-2 10.1126/science.aay5050

    # Search for papers
    python tools/scansci_bridge.py search "perovskite solar cells" --limit 5

    # Health check
    python tools/scansci_bridge.py --check

## Architecture

    PKB paper download pipeline (upgraded)
    ├── Chinese papers → /pkb-cnki (CNKI MCP + Chrome)    ← unchanged
    ├── English papers → tools/scansci_bridge.py 🆕         ← multi-source
    │   ├── 13-source parallel race (fastest wins)
    │   ├── Institutional WebVPN (100+ Chinese universities)
    │   ├── Resume/retry + batch download
    │   └── Tor anonymous channel
    ├── Metadata → scholarly_enrich.py (Crossref/OpenAlex)  ← unchanged
    └── Health → scansci_bridge --check 🆕

## Fail-Open Design

If scansci-pdf is unavailable, prints diagnostic and suggests fallback to
scihub_fetch.py single-source mode. No hard dependency — PKB pipelines
that import this module should catch ImportError and degrade gracefully.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

# ── Fail-open import ──────────────────────────────────────────────────────
_SCANSCI_AVAILABLE = False
_SCANSCI_ERROR: str | None = None

try:
    import scansci_pdf  # noqa: F401
    _SCANSCI_AVAILABLE = True
except ImportError as exc:
    _SCANSCI_ERROR = str(exc)


def _require_scansci() -> None:
    """Check scansci-pdf availability; print help and exit if missing."""
    if _SCANSCI_AVAILABLE:
        return
    print("=" * 60)
    print("  ❌ scansci-pdf not available")
    print("=" * 60)
    print(f"  Import error: {_SCANSCI_ERROR}")
    print()
    print("  Install via:")
    print("    pip install scansci-pdf")
    print()
    print("  Fallback: use single-source Sci-Hub mode instead:")
    print("    python tools/scihub_fetch.py")
    print("=" * 60)
    sys.exit(1)


# ── Public API (callable from other PKB tools) ────────────────────────────


def download_paper(
    identifier: str,
    output_dir: str | Path | None = None,
    *,
    strategy: str = "fastest",
    use_tor: bool = False,
    use_vpnsci: bool = False,
    scihub_enabled: bool | None = None,
    bibtex: bool = False,
) -> dict[str, Any]:
    """Download a single paper by DOI or arXiv ID.

    Uses scansci-pdf's multi-source pipeline: tries OA sources first
    (Unpaywall, arXiv, EuropePMC, DOAJ, OpenAIRE), then Sci-Hub as backup.

    Args:
        identifier: DOI (e.g. "10.1038/s41586-020-2649-2") or arXiv ID
        output_dir: Target directory (default: scansci-pdf config default)
        strategy: "fastest" (race-all, default), "oa_first" (legal first),
                  "scihub_only" (bypass OA), "legal_only" (no Sci-Hub)
        use_tor: Route through Tor SOCKS5 proxy
        use_vpnsci: Try WebVPN institutional proxy as last resort
        scihub_enabled: Explicit override for Sci-Hub toggle
        bibtex: Also return BibTeX citation

    Returns:
        {"success": bool, "file": str, "source": str, "identifier": str, ...}
    """
    _require_scansci()
    from scansci_pdf.server import download as _scansci_download

    return _scansci_download(
        identifier=identifier,
        output_dir=str(output_dir) if output_dir else None,
        scihub_enabled=scihub_enabled,
        use_tor=use_tor,
        use_vpnsci=use_vpnsci,
        bibtex=bibtex,
        strategy=strategy,
    )


def batch_download_papers(
    identifiers: list[str],
    output_dir: str | Path | None = None,
    *,
    strategy: str = "fastest",
    use_tor: bool = False,
    use_vpnsci: bool = False,
    scihub_enabled: bool | None = None,
    resume: bool = True,
) -> dict[str, Any]:
    """Download multiple papers in parallel.

    Args:
        identifiers: List of DOIs or arXiv IDs
        output_dir: Target directory
        strategy: Download strategy (fastest/oa_first/scihub_only/legal_only)
        use_tor: Route through Tor
        use_vpnsci: Try WebVPN as last resort
        scihub_enabled: Override Sci-Hub toggle
        resume: Resume from previous progress (default: True)

    Returns:
        {"total": int, "succeeded": int, "failed": int, "results": [...], ...}
    """
    _require_scansci()
    from scansci_pdf.server import batch_download as _scansci_batch

    return _scansci_batch(
        identifiers=identifiers,
        output_dir=str(output_dir) if output_dir else None,
        scihub_enabled=scihub_enabled,
        use_tor=use_tor,
        use_vpnsci=use_vpnsci,
        resume=resume,
    )


def search_papers(
    query: str,
    limit: int = 10,
    year_from: int | None = None,
    year_to: int | None = None,
    sort: str | None = None,
) -> list[dict[str, Any]]:
    """Search papers via OpenAlex + Semantic Scholar + Crossref (parallel).

    Args:
        query: Search query string
        limit: Max results (default: 10)
        year_from: Filter by start year
        year_to: Filter by end year
        sort: Sort order

    Returns:
        List of paper dicts with title, doi, year, authors, citations, etc.
    """
    _require_scansci()
    from scansci_pdf.search import search_papers as _scansci_search

    return _scansci_search(
        query=query,
        limit=limit,
        year_from=year_from,
        year_to=year_to,
        sort=sort,
    )


def health_check(detailed: bool = False) -> dict[str, Any]:
    """Check availability of all download sources.

    Probes: EuropePMC, Unpaywall, CORE, Semantic Scholar, OpenAlex, Crossref,
            plus Sci-Hub domain stats from cache (if detailed=True).

    Args:
        detailed: Include Sci-Hub domain latency stats

    Returns:
        {"source_name": {"status": "ok"|"error", "latency_ms": int}, ...}
    """
    _require_scansci()
    from scansci_pdf.server import scansci_pdf_health_check

    result = scansci_pdf_health_check(detailed=detailed)
    return json.loads(result)


def get_config() -> dict[str, Any]:
    """Return current scansci-pdf configuration dict."""
    _require_scansci()
    from scansci_pdf.config import load_config
    return load_config()


def is_available() -> bool:
    """Check if scansci-pdf is importable (for fail-open checks)."""
    return _SCANSCI_AVAILABLE


# ── CLI ───────────────────────────────────────────────────────────────────


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="scansci_bridge",
        description="PKB → scansci-pdf bridge: multi-source paper download",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python tools/scansci_bridge.py download 10.1038/s41586-020-2649-2
  python tools/scansci_bridge.py download --strategy oa_first DOI1 DOI2
  python tools/scansci_bridge.py search "machine learning" --limit 5
  python tools/scansci_bridge.py --check
  python tools/scansci_bridge.py --check --detailed
""",
    )

    parser.add_argument(
        "--check",
        action="store_true",
        help="Run health check on all download sources",
    )
    parser.add_argument(
        "--detailed",
        action="store_true",
        help="Include Sci-Hub domain stats in health check",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output results as JSON (for programmatic use)",
    )

    subparsers = parser.add_subparsers(dest="command", help="Subcommands")

    # ── download ──
    dl = subparsers.add_parser("download", help="Download paper(s) by DOI/arXiv ID")
    dl.add_argument(
        "identifiers",
        nargs="+",
        help="DOI(s) or arXiv ID(s) to download",
    )
    dl.add_argument(
        "-o", "--output-dir",
        default=None,
        help="Output directory (default: scansci-pdf config default)",
    )
    dl.add_argument(
        "-s", "--strategy",
        choices=["fastest", "oa_first", "scihub_only", "legal_only"],
        default="fastest",
        help="Download strategy (default: fastest)",
    )
    dl.add_argument(
        "--tor",
        action="store_true",
        dest="use_tor",
        help="Route through Tor SOCKS5 proxy",
    )
    dl.add_argument(
        "--vpnsci",
        action="store_true",
        dest="use_vpnsci",
        help="Try WebVPN institutional proxy as last resort",
    )
    dl.add_argument(
        "--no-scihub",
        action="store_true",
        dest="no_scihub",
        help="Disable Sci-Hub (equivalent to --strategy legal_only)",
    )
    dl.add_argument(
        "--scihub-only",
        action="store_true",
        dest="scihub_only",
        help="Only use Sci-Hub (equivalent to --strategy scihub_only)",
    )
    dl.add_argument(
        "--bibtex",
        action="store_true",
        help="Also return BibTeX citation",
    )
    dl.add_argument(
        "--no-resume",
        action="store_true",
        dest="no_resume",
        help="Don't resume from previous progress",
    )
    dl.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output as JSON",
    )

    # ── search ──
    sr = subparsers.add_parser("search", help="Search papers by keyword")
    sr.add_argument("query", help="Search query")
    sr.add_argument(
        "-n", "--limit",
        type=int,
        default=10,
        help="Max results (default: 10)",
    )
    sr.add_argument(
        "--year-from",
        type=int,
        default=None,
        help="Filter by start year",
    )
    sr.add_argument(
        "--year-to",
        type=int,
        default=None,
        help="Filter by end year",
    )
    sr.add_argument(
        "--sort",
        default=None,
        help="Sort order",
    )
    sr.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output as JSON",
    )

    return parser


def _print_result(result: dict[str, Any]) -> None:
    """Print download result in human-readable format."""
    success = result.get("success", False)
    identifier = result.get("identifier", result.get("doi", "?"))
    source = result.get("source", "unknown")
    filepath = result.get("file", "")
    cached = result.get("cached", False)
    error = result.get("error", "")

    tag = "✅" if success else "❌"
    cached_tag = " [cached]" if cached else ""
    print(f"{tag} {identifier}")
    if success:
        print(f"   Source: {source}{cached_tag}")
        print(f"   File: {filepath}")
    else:
        print(f"   Error: {error}")


def _print_batch_result(result: dict[str, Any]) -> None:
    """Print batch download result."""
    total = result.get("total", result.get("unique", 0))
    succeeded = result.get("succeeded", 0)
    failed = result.get("failed", 0)
    skipped = result.get("skipped_duplicates", 0) + result.get("skipped_completed", 0)

    print(f"\n{'=' * 60}")
    print(f"  BATCH DOWNLOAD SUMMARY")
    print(f"{'=' * 60}")
    print(f"  Total:    {total}")
    print(f"  ✅ Success: {succeeded}")
    print(f"  ❌ Failed:  {failed}")
    if skipped:
        print(f"  ⏭  Skipped: {skipped}")
    print(f"{'=' * 60}")

    results = result.get("results", [])
    if results:
        for r in results:
            if isinstance(r, dict):
                _print_result(r)


def _print_search_results(results: list[dict[str, Any]]) -> None:
    """Print search results in human-readable format."""
    if not results:
        print("No results found.")
        return

    print(f"\n{'=' * 80}")
    print(f"  SEARCH RESULTS ({len(results)} found)")
    print(f"{'=' * 80}")

    for i, paper in enumerate(results):
        title = paper.get("title", "Untitled")
        doi = paper.get("doi", "")
        year = paper.get("year", paper.get("publication_year", "?"))
        authors = paper.get("authors", [])
        if isinstance(authors, list):
            author_str = ", ".join(authors[:3])
            if len(authors) > 3:
                author_str += f" et al. ({len(authors)} authors)"
        else:
            author_str = str(authors) if authors else "Unknown"

        citations = paper.get("cited_by_count", paper.get("citations_count", "?"))
        journal = paper.get("journal", paper.get("venue", "?"))

        print(f"\n  [{i+1}] {title}")
        print(f"      Authors:   {author_str}")
        print(f"      Year:      {year}  |  Journal: {journal}")
        print(f"      DOI:       {doi}")
        print(f"      Citations: {citations}")

    print()


def _print_health(checks: dict[str, Any]) -> None:
    """Print health check results."""
    print(f"\n{'=' * 60}")
    print(f"  SCANSCI-PDF HEALTH CHECK")
    print(f"{'=' * 60}")

    all_ok = True
    for name, info in sorted(checks.items()):
        status = info.get("status", "?")
        latency = info.get("latency_ms", "?")
        reason = info.get("reason", "")

        tag = "✅" if status == "ok" else "❌"
        latency_str = f"{latency}ms" if isinstance(latency, (int, float)) else str(latency)
        detail = f" — {reason}" if reason else ""
        print(f"  {tag} {name:<25} {latency_str:>8}{detail}")
        if status != "ok":
            all_ok = False

    print(f"{'=' * 60}")
    print(f"  Overall: {'✅ All sources reachable' if all_ok else '❌ Some sources unreachable'}")
    print()


def main() -> None:
    # Windows: force UTF-8 output to avoid GBK encoding errors
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = _build_parser()
    args = parser.parse_args()

    # ── Health check ──
    if args.check:
        _require_scansci()
        checks = health_check(detailed=args.detailed)
        if args.json_output:
            print(json.dumps(checks, ensure_ascii=False, indent=2))
        else:
            _print_health(checks)
        return

    # ── No command given, show help ──
    if not args.command:
        # If --check was not passed and no subcommand, show availability
        if not _SCANSCI_AVAILABLE:
            _require_scansci()
        else:
            parser.print_help()
            print()
            print("Tip: run with --check for source health diagnostics")
        return

    # ── Download ──
    if args.command == "download":
        _require_scansci()

        # Resolve strategy from flags
        strategy = args.strategy
        if args.no_scihub:
            strategy = "legal_only"
        elif args.scihub_only:
            strategy = "scihub_only"

        identifiers = args.identifiers

        if len(identifiers) == 1:
            # Single download
            result = download_paper(
                identifier=identifiers[0],
                output_dir=args.output_dir,
                strategy=strategy,
                use_tor=args.use_tor,
                use_vpnsci=args.use_vpnsci,
                scihub_enabled=None if not args.no_scihub else False,
                bibtex=args.bibtex,
            )
            if args.json_output:
                print(json.dumps(result, ensure_ascii=False, indent=2))
            else:
                _print_result(result)
        else:
            # Batch download
            result = batch_download_papers(
                identifiers=identifiers,
                output_dir=args.output_dir,
                strategy=strategy,
                use_tor=args.use_tor,
                use_vpnsci=args.use_vpnsci,
                scihub_enabled=None if not args.no_scihub else False,
                resume=not args.no_resume,
            )
            if args.json_output:
                print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
            else:
                _print_batch_result(result)

    # ── Search ──
    elif args.command == "search":
        _require_scansci()
        results = search_papers(
            query=args.query,
            limit=args.limit,
            year_from=args.year_from,
            year_to=args.year_to,
            sort=args.sort,
        )
        if args.json_output:
            print(json.dumps(results, ensure_ascii=False, indent=2))
        else:
            _print_search_results(results)


if __name__ == "__main__":
    main()
