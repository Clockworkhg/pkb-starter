#!/usr/bin/env python3
"""PKB Structured Literature Filter — frontmatter-based scanner.

Scans wiki/ Markdown files and filters by scholarly metadata fields.
No network calls, no file writes. Designed for scriptable pipelines.

Usage:
    python tools/filter_literature.py --ranking CSSCI
    python tools/filter_literature.py --ranking CSSCI --edition 2025-2026
    python tools/filter_literature.py --ranking AMI --level authoritative
    python tools/filter_literature.py --year-from 2020 --year-to 2026
    python tools/filter_literature.py --journal "新闻与传播研究"
    python tools/filter_literature.py --doi "10.xxxx/..."
    python tools/filter_literature.py --min-citations 10
    python tools/filter_literature.py --needs-review
    python tools/filter_literature.py --missing citation
    python tools/filter_literature.py --format table
    python tools/filter_literature.py --format json
    python tools/filter_literature.py --format paths
    python tools/filter_literature.py --export-citations gbt7714-numeric

Multiple conditions are ANDed. Multiple values for the same flag are ORed.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Ensure tools/ is on path
_TOOLS_DIR = Path(__file__).resolve().parent
if str(_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOLS_DIR))


# ─────────────────────────────────────────────
# Match record
# ─────────────────────────────────────────────

@dataclass
class LiteratureMatch:
    """One filtered literature result."""
    path: str                          # Relative path from root
    title: str = ""
    doi: str = ""
    journal: str = ""
    year: str = ""
    authors: str = ""                  # Semicolon-joined
    rankings: List[Dict[str, str]] = field(default_factory=list)
    citations_count: int = 0
    has_citation: bool = False
    citation_texts: Dict[str, str] = field(default_factory=dict)
    needs_review: bool = False
    locked: bool = False
    scholarly_complete: bool = False


# ─────────────────────────────────────────────
# Frontmatter parsing
# ─────────────────────────────────────────────

def parse_frontmatter(content: str) -> Tuple[Dict[str, Any], str]:
    """Parse YAML frontmatter. Returns (frontmatter_dict, body)."""
    if not content.startswith("---"):
        return {}, content
    end = content.find("---", 3)
    if end == -1:
        return {}, content
    fm_raw = content[3:end].strip()
    body = content[end + 3:].strip()
    fm = _parse_simple_yaml(fm_raw)
    return fm, body


def _parse_simple_yaml(raw: str) -> Dict[str, Any]:
    """Parse simple YAML with nested dict and list-of-dict support."""
    result: Dict[str, Any] = {}
    current_nested: Optional[str] = None
    current_sub: Optional[str] = None
    current_list: Optional[str] = None
    current_list_item: Optional[Dict[str, Any]] = None

    for line in raw.split("\n"):
        if not line.strip() or line.strip().startswith("#"):
            continue
        indent = len(line) - len(line.lstrip())
        stripped = line.strip()

        # List item marker: "- key: value" or "- value"
        if stripped.startswith("- "):
            item_content = stripped[2:].strip()
            if ":" in item_content:
                k, _, v = item_content.partition(":")
                k = k.strip()
                v = v.strip()
                if indent == 2 and current_nested is not None:
                    # First list item under a key
                    current_list = current_nested
                    current_list_item = {k: v.strip("'\"")}
                    if not isinstance(result.get(current_list), list):
                        result[current_list] = []
                    result[current_list].append(current_list_item)
                elif current_list is not None:
                    current_list_item = {k: v.strip("'\"")}
                    result[current_list].append(current_list_item)
            elif current_list is not None and current_list_item is not None:
                # Scalar list item
                if not isinstance(result.get(current_list), list):
                    result[current_list] = []
                result[current_list].append(item_content.strip("'\""))
            continue

        if ":" not in stripped:
            continue

        key, _, value = stripped.partition(":")
        key = key.strip()
        value = value.strip()

        if indent == 0:
            current_nested = None
            current_sub = None
            current_list = None
            current_list_item = None
            if value == "":
                current_nested = key
                result[key] = {}
            elif value.startswith("[") and value.endswith("]"):
                inner = value[1:-1]
                result[key] = [v.strip().strip("'\"") for v in inner.split(",") if v.strip()]
            else:
                result[key] = value.strip("'\"")
        elif indent == 4 and current_list is not None and current_list_item is not None:
            # Sub-field of a list item (4-space indent under "- key: val")
            current_list_item[key] = value.strip("'\"")
        elif indent == 2 and current_list is not None and current_list_item is not None:
            # Sub-field of a list item (2-space indent under "- key: val")
            current_list_item[key] = value.strip("'\"")
        elif indent == 2 and current_nested is not None:
            if value == "":
                current_sub = key
                result.setdefault(current_nested, {})[key] = {}
            else:
                result.setdefault(current_nested, {})[key] = value.strip("'\"")
        elif indent == 4 and current_nested is not None and current_sub is not None:
            result.setdefault(current_nested, {}).setdefault(current_sub, {})[key] = value.strip("'\"")
    return result


# ─────────────────────────────────────────────
# Filters
# ─────────────────────────────────────────────

def _has_ranking(fm: Dict[str, Any], scheme: str, edition: Optional[str],
                 level: Optional[str]) -> bool:
    """Check if frontmatter matches a journal ranking filter."""
    rankings = fm.get("journal_rankings", [])
    if not isinstance(rankings, list):
        return False
    for r in rankings:
        if not isinstance(r, dict):
            continue
        scheme_match = r.get("scheme", "").upper() == scheme.upper()
        if not scheme_match:
            continue
        if edition and r.get("edition", "") != edition:
            continue
        if level and r.get("level", "").lower() != level.lower():
            continue
        return True
    return False


def _get_year(fm: Dict[str, Any]) -> Optional[int]:
    """Extract year from frontmatter."""
    # Try scholarly.year first
    scholarly = fm.get("scholarly", {})
    if isinstance(scholarly, dict):
        y = scholarly.get("year", "")
        if y:
            try:
                return int(y)
            except (ValueError, TypeError):
                pass
    # Try top-level year
    y = fm.get("year", "")
    if y:
        try:
            return int(y)
        except (ValueError, TypeError):
            pass
    return None


def _get_journal(fm: Dict[str, Any]) -> str:
    """Extract journal name from frontmatter."""
    scholarly = fm.get("scholarly", {})
    if isinstance(scholarly, dict):
        return str(scholarly.get("journal", ""))
    return str(fm.get("journal", fm.get("journal_name", "")))


def _get_doi(fm: Dict[str, Any]) -> str:
    """Extract DOI from frontmatter."""
    scholarly = fm.get("scholarly", {})
    if isinstance(scholarly, dict):
        doi = scholarly.get("doi", "")
        if doi:
            return str(doi)
    return str(fm.get("doi", ""))


def _get_citation_count(fm: Dict[str, Any]) -> int:
    """Extract citation count from metrics."""
    metrics = fm.get("metrics", {})
    if isinstance(metrics, dict):
        oa = metrics.get("openalex", {})
        if isinstance(oa, dict):
            count = oa.get("cited_by_count", 0)
            if count:
                try:
                    return int(count)
                except (ValueError, TypeError):
                    pass
    return 0


def _needs_review(fm: Dict[str, Any]) -> bool:
    """Check if metadata_match.needs_review is true."""
    mm = fm.get("metadata_match", {})
    if isinstance(mm, dict):
        return bool(mm.get("needs_review", False))
    return False


def _is_locked(fm: Dict[str, Any]) -> bool:
    """Check if scholarly.locked is true."""
    scholarly = fm.get("scholarly", {})
    if isinstance(scholarly, dict):
        return bool(scholarly.get("locked", False))
    return False


def _has_field(fm: Dict[str, Any], field: str) -> bool:
    """Check if a scholarly field is present and has data."""
    if field == "citation":
        c = fm.get("citation", {})
        return isinstance(c, dict) and len(c) > 0
    if field == "metrics":
        m = fm.get("metrics", {})
        return isinstance(m, dict) and len(m) > 0
    if field == "rankings" or field == "journal_rankings":
        r = fm.get("journal_rankings", [])
        return isinstance(r, list) and len(r) > 0
    if field == "scholarly":
        s = fm.get("scholarly", {})
        return isinstance(s, dict) and s.get("detected", False)
    return False


def _extract_citation_texts(fm: Dict[str, Any]) -> Dict[str, str]:
    """Extract available citation texts from frontmatter."""
    citation = fm.get("citation", {})
    texts: Dict[str, str] = {}
    if isinstance(citation, dict):
        for style, data in citation.items():
            if isinstance(data, dict):
                text = data.get("text", "")
                if text:
                    texts[style] = text
            elif isinstance(data, str) and data.strip():
                texts[style] = data
    return texts


# ─────────────────────────────────────────────
# Scanner
# ─────────────────────────────────────────────

def scan_literature(
    root: Path,
    *,
    ranking: Optional[str] = None,
    edition: Optional[str] = None,
    level: Optional[str] = None,
    year_from: Optional[int] = None,
    year_to: Optional[int] = None,
    journal: Optional[str] = None,
    doi: Optional[str] = None,
    min_citations: Optional[int] = None,
    needs_review_flag: bool = False,
    missing: Optional[str] = None,
) -> Tuple[List[LiteratureMatch], List[str]]:
    """Scan wiki/ for scholarly Markdown files matching filters.

    Args:
        root: PKB root directory.
        ranking: Journal ranking scheme (CSSCI, PKU_CORE, AMI, CSCD, CUSTOM).
        edition: Ranking edition (e.g. "2025-2026").
        level: Ranking level (source, extended, core, authoritative, top, etc.).
        year_from: Minimum publication year (inclusive).
        year_to: Maximum publication year (inclusive).
        journal: Journal name substring match.
        doi: DOI substring match.
        min_citations: Minimum citation count.
        needs_review_flag: Only pages with metadata_match.needs_review.
        missing: Only pages missing this field (citation, metrics, rankings, scholarly).

    Returns:
        (matches, warnings) — matches sorted stably, warnings for parse errors.
    """
    wiki_dir = root / "wiki"
    matches: List[LiteratureMatch] = []
    warnings: List[str] = []

    if not wiki_dir.exists():
        return matches, [f"wiki/ directory not found at {wiki_dir}"]

    for fp in sorted(wiki_dir.rglob("*.md")):
        try:
            raw = fp.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            warnings.append(f"Encoding error: {fp}")
            continue
        except Exception as e:
            warnings.append(f"Read error: {fp} ({e})")
            continue

        try:
            fm, body = parse_frontmatter(raw)
        except Exception as e:
            warnings.append(f"Frontmatter parse error: {fp} ({e})")
            continue

        # ── Apply filters (AND logic) ──
        passes = True

        # Ranking filter
        if ranking:
            if not _has_ranking(fm, ranking, edition, level):
                passes = False

        # Year range filter
        file_year = _get_year(fm)
        if year_from is not None and (file_year is None or file_year < year_from):
            passes = False
        if year_to is not None and (file_year is None or file_year > year_to):
            passes = False

        # Journal filter (substring match)
        if journal:
            j = _get_journal(fm)
            if journal.lower() not in j.lower():
                passes = False

        # DOI filter (substring match)
        if doi:
            d = _get_doi(fm)
            if doi.lower() not in d.lower():
                passes = False

        # Citation count filter
        if min_citations is not None:
            if _get_citation_count(fm) < min_citations:
                passes = False

        # Needs review filter
        if needs_review_flag:
            if not _needs_review(fm):
                passes = False

        # Missing field filter
        if missing:
            if _has_field(fm, missing):
                passes = False

        # ── Implicit: only include pages with scholarly data or DOI ──
        has_scholarly = (
            bool(_get_doi(fm)) or
            _has_field(fm, "scholarly") or
            _has_field(fm, "citation") or
            _has_field(fm, "rankings") or
            (isinstance(fm.get("journal_rankings"), list) and len(fm.get("journal_rankings", [])) > 0)
        )
        if not has_scholarly:
            continue

        if not passes:
            continue

        # ── Build match record ──
        scholarly = fm.get("scholarly", {})
        if not isinstance(scholarly, dict):
            scholarly = {}

        title = str(scholarly.get("title", fm.get("title", "")))
        authors_raw = scholarly.get("authors", fm.get("authors", fm.get("author", [])))
        if isinstance(authors_raw, list):
            authors_str = "; ".join(str(a) for a in authors_raw)
        else:
            authors_str = str(authors_raw) if authors_raw else ""

        rankings = fm.get("journal_rankings", [])
        if not isinstance(rankings, list):
            rankings = []

        matches.append(LiteratureMatch(
            path=str(fp.relative_to(root)),
            title=title,
            doi=_get_doi(fm),
            journal=_get_journal(fm),
            year=str(file_year) if file_year else "",
            authors=authors_str,
            rankings=rankings,
            citations_count=_get_citation_count(fm),
            has_citation=_has_field(fm, "citation"),
            citation_texts=_extract_citation_texts(fm),
            needs_review=_needs_review(fm),
            locked=_is_locked(fm),
            scholarly_complete=(
                _has_field(fm, "scholarly") and
                _has_field(fm, "citation")
            ),
        ))

    # Stable sort: by year desc, then by title
    matches.sort(key=lambda m: (
        -(int(m.year) if m.year.isdigit() else 0),
        m.title.lower(),
    ))

    return matches, warnings


# ─────────────────────────────────────────────
# Output formatters
# ─────────────────────────────────────────────

def _format_table(matches: List[LiteratureMatch], max_width: int = 100):
    """Print matches as a formatted table."""
    if not matches:
        print("No matching literature found.")
        return

    # Auto-calculate column widths
    idx_w = 4
    title_w = min(40, max(len(m.title) for m in matches) + 2)
    journal_w = min(20, max(len(m.journal) for m in matches) + 2)
    year_w = 6
    doi_w = min(25, max(len(m.doi) for m in matches) + 2)

    # Headers
    header = (f"{'#':<{idx_w}} {'Title':<{title_w}} {'Journal':<{journal_w}} "
              f"{'Year':<{year_w}} {'Citations':>9} {'DOI':<{doi_w}}")
    sep = "-" * len(header)
    print(sep)
    print(header)
    print(sep)

    for i, m in enumerate(matches, 1):
        title = m.title[:title_w-2] if len(m.title) > title_w else m.title
        journal = m.journal[:journal_w-2] if len(m.journal) > journal_w else m.journal
        doi_s = m.doi[:doi_w-2] if len(m.doi) > doi_w else m.doi
        citations = str(m.citations_count)
        print(f"{i:<{idx_w}} {title:<{title_w}} {journal:<{journal_w}} "
              f"{m.year:<{year_w}} {citations:>9} {doi_s:<{doi_w}}")

    print(sep)
    print(f"{len(matches)} result(s)")
    if any(m.needs_review for m in matches):
        nr = sum(1 for m in matches if m.needs_review)
        print(f"{nr} need(s) review")
    if any(m.locked for m in matches):
        locked = sum(1 for m in matches if m.locked)
        print(f"{locked} locked")


def _format_json(matches: List[LiteratureMatch]):
    """Print matches as JSON array."""
    output = []
    for m in matches:
        output.append({
            "path": m.path,
            "title": m.title,
            "doi": m.doi,
            "journal": m.journal,
            "year": m.year,
            "authors": m.authors,
            "rankings": [
                {
                    "scheme": r.get("scheme", ""),
                    "edition": r.get("edition", ""),
                    "level": r.get("level", ""),
                }
                for r in m.rankings
            ],
            "citations_count": m.citations_count,
            "has_citation": m.has_citation,
            "needs_review": m.needs_review,
            "locked": m.locked,
            "scholarly_complete": m.scholarly_complete,
        })
    print(json.dumps(output, ensure_ascii=False, indent=2))


def _format_paths(matches: List[LiteratureMatch]):
    """Print one path per line, suitable for pipe to other tools."""
    for m in matches:
        print(m.path)


def _export_citations(matches: List[LiteratureMatch], style: str):
    """Export available citation texts in the requested style."""
    exported = 0
    for m in matches:
        text = m.citation_texts.get(style, "")
        if text:
            print(f"## {m.title or m.path}")
            print(text)
            print()
            exported += 1
    if exported == 0:
        print(f"No citations available in style '{style}'.")
    else:
        print(f"---\n{exported} citation(s) exported.")


# ─────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="PKB Structured Literature Filter",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python tools/filter_literature.py --ranking CSSCI
  python tools/filter_literature.py --ranking CSSCI --edition 2025-2026
  python tools/filter_literature.py --ranking AMI --level authoritative
  python tools/filter_literature.py --year-from 2020 --year-to 2026
  python tools/filter_literature.py --journal "新闻与传播研究"
  python tools/filter_literature.py --min-citations 10
  python tools/filter_literature.py --needs-review
  python tools/filter_literature.py --missing citation
  python tools/filter_literature.py --format table
  python tools/filter_literature.py --format json
  python tools/filter_literature.py --format paths
  python tools/filter_literature.py --export-citations gbt7714-numeric
        """,
    )

    # Filters
    parser.add_argument("--ranking", default="",
                        help="Journal ranking scheme (CSSCI, PKU_CORE, AMI, CSCD, CUSTOM)")
    parser.add_argument("--edition", default="",
                        help="Ranking edition (e.g. '2025-2026')")
    parser.add_argument("--level", default="",
                        help="Ranking level (source, extended, core, authoritative, top, etc.)")
    parser.add_argument("--year-from", type=int, default=None,
                        help="Minimum publication year (inclusive)")
    parser.add_argument("--year-to", type=int, default=None,
                        help="Maximum publication year (inclusive)")
    parser.add_argument("--journal", default="",
                        help="Journal name substring match")
    parser.add_argument("--doi", default="",
                        help="DOI substring match")
    parser.add_argument("--min-citations", type=int, default=None,
                        help="Minimum citation count")
    parser.add_argument("--needs-review", action="store_true",
                        help="Only pages with metadata_match.needs_review")
    parser.add_argument("--missing", default="",
                        choices=["", "citation", "metrics", "rankings", "scholarly"],
                        help="Only pages missing specified field")

    # Output
    parser.add_argument("--format", default="table",
                        choices=["table", "json", "paths"],
                        help="Output format (default: table)")
    parser.add_argument("--export-citations", default="",
                        help="Export citations in this style (e.g. gbt7714-numeric)")
    parser.add_argument("--root", default="",
                        help="PKB root directory (auto-detected if omitted)")

    args = parser.parse_args()

    # Determine PKB root
    if args.root:
        root = Path(args.root)
    else:
        root = Path(__file__).resolve().parent.parent

    # Validate
    if args.ranking and args.ranking.upper() not in ("CSSCI", "PKU_CORE", "AMI", "CSCD", "CUSTOM"):
        print(f"Warning: Unknown ranking scheme '{args.ranking}'. "
              f"Supported: CSSCI, PKU_CORE, AMI, CSCD, CUSTOM", file=sys.stderr)

    # Scan
    matches, warnings = scan_literature(
        root,
        ranking=args.ranking if args.ranking else None,
        edition=args.edition if args.edition else None,
        level=args.level if args.level else None,
        year_from=args.year_from,
        year_to=args.year_to,
        journal=args.journal if args.journal else None,
        doi=args.doi if args.doi else None,
        min_citations=args.min_citations,
        needs_review_flag=args.needs_review,
        missing=args.missing if args.missing else None,
    )

    # Print warnings to stderr
    for w in warnings:
        print(f"Warning: {w}", file=sys.stderr)

    # Output
    if args.export_citations:
        _export_citations(matches, args.export_citations)
    elif args.format == "json":
        _format_json(matches)
    elif args.format == "paths":
        _format_paths(matches)
    else:
        _format_table(matches)


if __name__ == "__main__":
    main()
