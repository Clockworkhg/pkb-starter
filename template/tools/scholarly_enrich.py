#!/usr/bin/env python3
"""PKB Scholarly Metadata Enrichment CLI.

Usage:
    python tools/scholarly_enrich.py --doi "10.xxxx/xxxx"
    python tools/scholarly_enrich.py wiki/some-paper.md
    python tools/scholarly_enrich.py --scan wiki/
    python tools/scholarly_enrich.py --cache-only --doi "10.xxxx/xxxx"
    python tools/scholarly_enrich.py --offline wiki/some-paper.md
    python tools/scholarly_enrich.py --json --doi "10.xxxx/xxxx"
    python tools/scholarly_enrich.py --write wiki/some-paper.md

--write modifies the Markdown file in place with enrichment data.
Without --write, only a preview is displayed.

Phase 1A: no /pkb integration, no PostToolUse hook changes.
"""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Ensure tools/ is on path
_TOOLS_DIR = Path(__file__).resolve().parent
if str(_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOLS_DIR))

from scholarly.enrichment import ScholarlyEnricher, EnrichmentConfig
from scholarly.citation_formatter import CitationFormatter
from scholarly.models import (
    CitationStyle,
    EnrichmentResult,
    JournalRanking,
    MatchResult,
    MetricSnapshot,
)


# ─────────────────────────────────────────────
# Markdown frontmatter handling
# ─────────────────────────────────────────────

def parse_frontmatter(content: str) -> Tuple[Dict[str, Any], str, str]:
    """Parse YAML frontmatter from Markdown content.

    Returns (frontmatter_dict, body, raw_frontmatter_string).
    """
    if not content.startswith("---"):
        return {}, content, ""
    end = content.find("---", 3)
    if end == -1:
        return {}, content, ""
    fm_raw = content[3:end].strip()
    body = content[end + 3:].strip()
    # Simple key: value parser (not full YAML — avoids pyyaml dependency)
    fm = _parse_simple_yaml(fm_raw)
    return fm, body, fm_raw


def _parse_simple_yaml(raw: str) -> Dict[str, Any]:
    """Parse a simple flat YAML frontmatter. No nested parsing needed.

    Only processes non-indented lines (top-level keys). Indented lines
    (nested values) are skipped to avoid overwriting top-level keys.
    """
    result: Dict[str, Any] = {}
    in_nested = False
    for line in raw.split("\n"):
        # Skip indented lines (nested blocks)
        if line and line[0] in (" ", "\t"):
            in_nested = True
            continue
        in_nested = False
        line_clean = line.strip()
        if not line_clean or line_clean.startswith("#"):
            continue
        if ":" in line_clean:
            key, _, value = line_clean.partition(":")
            key = key.strip()
            value = value.strip()
            # Handle list values: [a, b, c]
            if value.startswith("[") and value.endswith("]"):
                inner = value[1:-1]
                result[key] = [v.strip().strip("'\"") for v in inner.split(",") if v.strip()]
            else:
                result[key] = value.strip("'\"")
    return result


def _serialise_simple_yaml(fm: Dict[str, Any]) -> str:
    """Serialise a flat dict back to simple YAML lines."""
    lines = []
    for key, value in fm.items():
        if isinstance(value, list):
            items = ", ".join(f"'{v}'" if " " in str(v) else str(v) for v in value)
            lines.append(f"{key}: [{items}]")
        elif isinstance(value, dict):
            # Nested dicts: indent with 2 spaces
            lines.append(f"{key}:")
            for k, v in value.items():
                if isinstance(v, dict):
                    lines.append(f"  {k}:")
                    for k2, v2 in v.items():
                        lines.append(f"    {k2}: {v2}")
                else:
                    lines.append(f"  {k}: {v}")
        elif isinstance(value, bool):
            lines.append(f"{key}: {'true' if value else 'false'}")
        else:
            lines.append(f"{key}: {value}")
    return "\n".join(lines)


def _merge_frontmatter(fm: Dict[str, Any], result: EnrichmentResult) -> Dict[str, Any]:
    """Merge enrichment result into frontmatter dict.

    Updates: scholarly, journal_rankings, metrics, citation, metadata_match.
    Preserves all unknown fields.
    """
    new_fm = dict(fm)

    # ── scholarly namespace ──
    rec = result.record
    scholarly: Dict[str, Any] = {}
    if rec.title:
        scholarly["title"] = rec.title
    if rec.authors:
        scholarly["authors"] = [f"{a.get('family','')}{a.get('given','')}" for a in rec.authors]
    if rec.year:
        scholarly["year"] = str(rec.year)
    if rec.doi:
        scholarly["doi"] = rec.doi
    if rec.journal_name:
        scholarly["journal"] = rec.journal_name
    if rec.issn:
        scholarly["issn"] = rec.issn
    if rec.issn_l:
        scholarly["issn_l"] = rec.issn_l
    if rec.pub_type:
        scholarly["type"] = rec.pub_type
    new_fm["scholarly"] = scholarly

    # ── journal_rankings ──
    if result.journal_rankings:
        rankings: Dict[str, Any] = {}
        for r in result.journal_rankings:
            scheme = r.scheme.lower()
            if scheme not in rankings:
                rankings[scheme] = {
                    "edition": r.edition,
                    "level": r.level,
                }
        new_fm["journal_rankings"] = rankings

    # ── metrics ──
    if rec.metrics:
        metrics: Dict[str, Any] = {}
        for m in rec.metrics:
            source = m.source
            if source not in metrics:
                metrics[source] = {}
            if m.value is not None:
                metrics[source][m.metric_name] = m.value
            elif m.unit:
                metrics[source][m.metric_name] = m.unit
        if rec.retrieved_at:
            metrics["retrieved_at"] = rec.retrieved_at
        new_fm["metrics"] = metrics

    # ── citations ──
    if result.citations:
        citations: Dict[str, str] = {}
        for c in result.citations:
            if not c.is_empty() and c.style != CitationStyle.BIBTEX and c.style != CitationStyle.RIS:
                citations[c.style.value] = c.formatted
        if citations:
            new_fm["citation"] = citations

    # ── metadata_match ──
    if result.match_result:
        mr = result.match_result
        new_fm["metadata_match"] = {
            "method": mr.method.value,
            "confidence": str(round(mr.confidence, 2)),
        }
        if mr.needs_review:
            new_fm["metadata_match"]["needs_review"] = "true"

    return new_fm


def _detect_bom(filepath: Path) -> bool:
    """Check if file starts with UTF-8 BOM (EF BB BF)."""
    try:
        with open(filepath, 'rb') as f:
            return f.read(3) == b'\xef\xbb\xbf'
    except Exception:
        return False


def _detect_crlf(filepath: Path) -> bool:
    """Check if file uses CRLF line endings (by reading raw bytes)."""
    try:
        with open(filepath, 'rb') as f:
            raw = f.read(4096)
            return b'\r\n' in raw.split(b'\n')[0] if b'\n' in raw else b'\r\n' in raw
    except Exception:
        return False


def _read_markdown(filepath: Path) -> Tuple[str, bool, bool]:
    """Read Markdown content with BOM and line-ending detection.

    Returns (content, has_bom, uses_crlf).
    Raises UnicodeDecodeError on invalid encoding (no silent corruption).
    """
    has_bom = _detect_bom(filepath)
    uses_crlf = _detect_crlf(filepath)
    encoding = "utf-8-sig" if has_bom else "utf-8"
    # Read in binary mode first to preserve line endings
    with open(filepath, 'rb') as f:
        raw = f.read()
    if has_bom:
        raw = raw[3:]  # Strip BOM before decoding
    content = raw.decode('utf-8')
    return content, has_bom, uses_crlf


def update_markdown_file(filepath: Path, result: EnrichmentResult) -> bool:
    """Atomically update a Markdown file with enrichment data.

    Encoding: reads with strict UTF-8, writes UTF-8 without BOM (or UTF-8-sig
              if the original file had a BOM). Preserves original line endings.

    Atomic write: writes to a temp file in the same directory, flushes + fsyncs,
                  then calls os.replace() (atomic on same filesystem).

    On failure: original file is preserved, temp file is cleaned up,
                a clear error is returned.

    Returns True on success.
    """
    try:
        original, has_bom, uses_crlf = _read_markdown(filepath)
    except UnicodeDecodeError as e:
        print(f"ERROR: Encoding error in {filepath}: {e}", file=sys.stderr)
        print("  The file is not valid UTF-8. Please re-save as UTF-8.", file=sys.stderr)
        return False
    except Exception as e:
        print(f"ERROR: Cannot read {filepath}: {e}", file=sys.stderr)
        return False

    fm, body, _ = parse_frontmatter(original)
    new_fm = _merge_frontmatter(fm, result)

    # Build new content
    new_fm_yaml = _serialise_simple_yaml(new_fm)
    new_content = f"---\n{new_fm_yaml}\n---\n\n{body}"

    # Preserve original line endings
    if uses_crlf:
        new_content = new_content.replace('\n', '\r\n')

    # Determine write encoding
    write_encoding = "utf-8-sig" if has_bom else "utf-8"

    # Write to temp file in same directory
    tmp_path = filepath.parent / (filepath.name + ".tmp")
    try:
        tmp_path.write_text(new_content, encoding=write_encoding)

        # Flush + fsync for durability
        try:
            with open(tmp_path, 'r+b') as f:
                os.fsync(f.fileno())
        except (OSError, IOError):
            pass  # fsync may not be available on all filesystems

        # Preserve original file permissions
        try:
            original_stat = filepath.stat()
            os.chmod(tmp_path, original_stat.st_mode)
        except Exception:
            pass  # Permissions preservation is best-effort

        # Atomic replace on same filesystem
        os.replace(tmp_path, filepath)
        return True
    except Exception as e:
        print(f"ERROR: Write failed for {filepath}: {e}", file=sys.stderr)
        # Clean up temp file if it exists
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except Exception:
                pass
        return False


# ─────────────────────────────────────────────
# Display helpers
# ─────────────────────────────────────────────

def _display_result(result: EnrichmentResult):
    """Print a human-readable enrichment result."""
    rec = result.record
    print()
    print("=" * 60)
    print("  Scholarly Metadata Enrichment")
    print("=" * 60)

    # Title
    if rec.title:
        print(f"\n  Title: {rec.title}")

    # Authors
    if rec.authors:
        authors_str = ", ".join(
            f"{a.get('family','')}{a.get('given','')}" for a in rec.authors
        )
        print(f"  Authors: {authors_str}")

    # Journal
    if rec.journal_name:
        print(f"  Journal: {rec.journal_name}")
    if rec.year:
        print(f"  Year: {rec.year}")
    if rec.volume:
        vol_info = rec.volume
        if rec.issue:
            vol_info += f"({rec.issue})"
        if rec.page:
            vol_info += f": {rec.page}"
        print(f"  Volume/Issue/Page: {vol_info}")
    if rec.doi:
        print(f"  DOI: {rec.doi}")

    # Source status
    print(f"\n  Crossref: {rec.crossref_status.value}")
    print(f"  OpenAlex: {rec.openalex_status.value}")

    # Journal rankings
    if result.journal_rankings:
        print(f"\n  --- Journal Rankings ---")
        for r in result.journal_rankings:
            print(f"  [{r.scheme}] {r.edition}: {r.level} — {r.journal_name}")
            if r.category:
                print(f"    Category: {r.category}")

    # Match info
    if result.match_result:
        mr = result.match_result
        print(f"\n  Match: {mr.method.value} (confidence: {mr.confidence:.2f})")
        if mr.needs_review:
            print(f"  [WARN] NEEDS REVIEW")
        for e in mr.evidence:
            print(f"    • {e}")

    # Metrics
    if rec.metrics:
        print(f"\n  --- Metrics ---")
        for m in rec.metrics:
            if m.value is not None:
                print(f"  {m.source} {m.metric_name}: {m.value} {m.unit}")
            else:
                print(f"  {m.source} {m.metric_name}: {m.unit}")

    # Citations
    if result.citations:
        print(f"\n  --- Citations ---")
        for c in result.citations:
            if not c.is_empty():
                label = c.style.value.upper()
                print(f"\n  [{label}]")
                print(f"  {c.formatted[:200]}")
                if len(c.formatted) > 200:
                    print(f"  ...")

    # Warnings and errors
    if result.warnings:
        print(f"\n  --- Warnings ---")
        for w in result.warnings:
            print(f"  [WARN] {w}")
    if result.errors:
        print(f"\n  --- Errors ---")
        for e in result.errors:
            print(f"  [ERROR] {e}")

    print("\n" + "=" * 60)


def _display_json(result: EnrichmentResult):
    """Print JSON-serialisable enrichment result."""
    rec = result.record
    output: Dict[str, Any] = {
        "record": {
            "doi": rec.doi,
            "title": rec.title,
            "authors": [{"family": a.get("family", ""), "given": a.get("given", "")} for a in rec.authors],
            "journal_name": rec.journal_name,
            "issn": rec.issn,
            "issn_l": rec.issn_l,
            "year": rec.year,
            "volume": rec.volume,
            "issue": rec.issue,
            "page": rec.page,
            "crossref_status": rec.crossref_status.value,
            "openalex_status": rec.openalex_status.value,
        },
        "journal_rankings": [
            {
                "scheme": r.scheme,
                "edition": r.edition,
                "journal_name": r.journal_name,
                "issn": r.issn,
                "level": r.level,
                "category": r.category,
            }
            for r in result.journal_rankings
        ],
        "citations": [
            {
                "style_requested": c.style_requested or c.style.value,
                "style": c.style.value,
                "engine_used": c.engine_used,
                "strict": c.strict,
                "warnings": c.warnings,
                "text": c.formatted,
            }
            for c in result.citations if not c.is_empty()
        ],
        "match": {
            "method": result.match_result.method.value,
            "confidence": result.match_result.confidence,
            "needs_review": result.match_result.needs_review,
        } if result.match_result else None,
        "metrics": [
            {
                "source": m.source,
                "name": m.metric_name,
                "value": m.value,
                "unit": m.unit,
            }
            for m in rec.metrics
        ],
        "warnings": result.warnings,
        "errors": result.errors,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))


# ─────────────────────────────────────────────
# Job state management (for batch --resume)
# ─────────────────────────────────────────────

def _jobs_dir(root: Path) -> Path:
    """Return .pkb_local/scholarly/jobs/ directory, creating if needed."""
    d = root / ".pkb_local" / "scholarly" / "jobs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _save_job_state(job: Dict[str, Any], root: Path):
    """Save job state to .pkb_local/scholarly/jobs/<job_id>.json."""
    jd = _jobs_dir(root)
    job_file = jd / f"{job['job_id']}.json"
    job_file.write_text(
        json.dumps(job, ensure_ascii=False, indent=2),
        encoding='utf-8',
    )


def _load_job_state(job_id: str, root: Path) -> Optional[Dict[str, Any]]:
    """Load a job state file. Returns None if missing or corrupt."""
    job_file = _jobs_dir(root) / f"{job_id}.json"
    if not job_file.exists():
        return None
    try:
        return json.loads(job_file.read_text(encoding='utf-8'))
    except (json.JSONDecodeError, OSError):
        return None


def _list_incomplete_jobs(root: Path) -> List[Dict[str, Any]]:
    """List all job states that are not yet 'completed'."""
    jd = _jobs_dir(root)
    jobs = []
    for f in sorted(jd.glob("*.json")):
        job = _load_job_state(f.stem, root)
        if job and job.get("status") != "completed":
            jobs.append(job)
    return jobs


def _create_job(options: Dict[str, Any], root: Path) -> Dict[str, Any]:
    """Create a new job state entry."""
    job_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    job = {
        "job_id": job_id,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "status": "running",
        "options": options,
        "pending": [],
        "succeeded": [],
        "skipped": [],
        "failed": [],
        "last_processed": "",
        "errors": [],
    }
    _save_job_state(job, root)
    return job


# ─────────────────────────────────────────────
# Scan helpers
# ─────────────────────────────────────────────

def _find_md_files(base: Path) -> List[Path]:
    """Find all Markdown files under a directory."""
    if base.is_file():
        return [base] if base.suffix == ".md" else []
    return sorted(base.rglob("*.md"))


def _extract_doi_from_md(filepath: Path) -> Optional[str]:
    """Extract DOI from a Markdown file's frontmatter."""
    try:
        content, _, _ = _read_markdown(filepath)
    except Exception:
        return None
    fm, _, _ = parse_frontmatter(content)
    doi = fm.get("doi", "")
    if doi:
        return str(doi)
    # Also check scholarly namespace
    scholarly = fm.get("scholarly", {})
    if isinstance(scholarly, dict):
        return str(scholarly.get("doi", ""))
    return None


def _has_scholarly_data(fm: Dict[str, Any]) -> bool:
    """Check if frontmatter already has scholarly enrichment data."""
    scholarly = fm.get("scholarly", {})
    if isinstance(scholarly, dict) and scholarly.get("detected"):
        return True
    return False


def _scholarly_is_complete(fm: Dict[str, Any],
                           required_sections: Optional[List[str]] = None) -> bool:
    """Check if scholarly data is complete (has citation + metrics + rankings).

    Args:
        fm: Parsed frontmatter dict.
        required_sections: List of section keys to check (e.g. ["citation", "metrics"]).
                          If None, checks citation only.
    """
    if required_sections is None:
        required_sections = ["citation"]
    for section in required_sections:
        val = fm.get(section)
        if not val or (isinstance(val, dict) and len(val) == 0):
            return False
    return True


def _is_locked(fm: Dict[str, Any]) -> bool:
    """Check if scholarly.locked is true."""
    scholarly = fm.get("scholarly", {})
    if isinstance(scholarly, dict):
        return bool(scholarly.get("locked", False))
    return False


# ─────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="PKB Scholarly Metadata Enrichment CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python tools/scholarly_enrich.py --doi '10.1234/example'
  python tools/scholarly_enrich.py --doi '10.1234/example' --json
  python tools/scholarly_enrich.py wiki/paper.md --write
  python tools/scholarly_enrich.py --scan wiki/
  python tools/scholarly_enrich.py --scan wiki/ --write
  python tools/scholarly_enrich.py --scan wiki/ --write --only-missing
  python tools/scholarly_enrich.py --scan wiki/ --write --resume
  python tools/scholarly_enrich.py --scan wiki/ --dry-run
  python tools/scholarly_enrich.py --scan wiki/ --jsonl
  python tools/scholarly_enrich.py --scan wiki/ --force
        """,
    )
    parser.add_argument("target", nargs="?", help="DOI, Markdown file, or directory")
    parser.add_argument("--doi", default="", help="DOI to look up")
    parser.add_argument("--scan", default="", help="Scan directory for Markdown files")
    parser.add_argument("--cache-only", action="store_true", help="Only use cache, no network")
    parser.add_argument("--offline", action="store_true", help="No network, no cache fallback")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--jsonl", action="store_true", help="Output each file result as one JSON line")
    parser.add_argument("--write", action="store_true", help="Write enrichment data to file")
    parser.add_argument("--dry-run", action="store_true", help="Preview what would be written (no changes)")
    parser.add_argument("--only-missing", action="store_true",
                        help="Only process pages without complete scholarly data")
    parser.add_argument("--resume", action="store_true",
                        help="Resume the most recent incomplete job")
    parser.add_argument("--force", action="store_true",
                        help="Force enrichment even for locked pages or low confidence")
    parser.add_argument("--crossref-email", default="", help="Crossref contact email")
    parser.add_argument("--openalex-key", default="", help="OpenAlex API key")
    parser.add_argument("--citation-engine", default="auto",
                        choices=["auto", "fallback", "citeproc"],
                        help="Citation rendering engine (default: auto)")
    parser.add_argument("--root", default="",
                        help="PKB root directory (auto-detected if omitted)")

    args = parser.parse_args()

    # Determine PKB root
    if args.root:
        root = Path(args.root)
    else:
        root = Path(__file__).resolve().parent.parent

    # Resolve DOI
    doi = args.doi
    if not doi and args.target:
        target = args.target.strip()
        if target.startswith("10.") and "/" in target:
            doi = target
        elif target.startswith("doi:"):
            doi = target
        elif target.startswith("http"):
            doi = target

    # Config
    config = EnrichmentConfig(
        crossref_email=args.crossref_email or os.environ.get("CROSSREF_EMAIL", ""),
        openalex_api_key=args.openalex_key or os.environ.get("OPENALEX_API_KEY", ""),
        cache_only=args.cache_only,
        offline=args.offline,
        citation_engine=args.citation_engine,
    )

    # ── DOI mode ──
    if doi:
        enricher = ScholarlyEnricher(config=config)
        result = enricher.enrich_by_doi(doi)
        if args.json or args.jsonl:
            _display_json(result)
        else:
            _display_result(result)
        return

    # ── Scan mode ──
    if args.scan:
        scan_dir = Path(args.scan)
        if not scan_dir.is_absolute():
            scan_dir = root / scan_dir
        files = _find_md_files(scan_dir)
        if not files:
            print(f"No Markdown files found in {scan_dir}")
            return

        # ── dry-run takes precedence over write ──
        actually_write = args.write and not args.dry_run
        is_dry = args.dry_run or (not args.write and not args.jsonl and not args.json)

        # ── Resume handling ──
        job: Optional[Dict[str, Any]] = None
        if args.resume:
            incomplete = _list_incomplete_jobs(root)
            if not incomplete:
                print("No incomplete jobs to resume.")
                return
            # Find most recent compatible job
            for j in reversed(incomplete):
                j_opts = j.get("options", {})
                if (j_opts.get("scan") == str(scan_dir) and
                    j_opts.get("citation_engine") == args.citation_engine):
                    job = j
                    break
            if job is None:
                print("No compatible incomplete job found.")
                print(f"  Available jobs: {[j['job_id'] for j in incomplete]}")
                return
            # Load succeeded set
            succeeded_set = set(job.get("succeeded", []))
            failed_set = set(job.get("failed", []))
            print(f"Resuming job {job['job_id']} "
                  f"({len(succeeded_set)} succeeded, {len(failed_set)} failed, "
                  f"{len(files)} total files)")
        else:
            job = _create_job({
                "scan": str(scan_dir),
                "citation_engine": args.citation_engine,
                "write": actually_write,
                "dry_run": is_dry,
                "only_missing": args.only_missing,
                "force": args.force,
            }, root)
            succeeded_set = set()
            failed_set = set()

        enricher = ScholarlyEnricher(config=config)
        total = len(files)
        enriched = 0
        skipped = 0
        warned = 0
        written = 0

        for idx, fp in enumerate(files, 1):
            fp_str = str(fp)

            # Skip already succeeded/failed in resume mode
            if args.resume:
                if fp_str in succeeded_set:
                    continue
                if fp_str in failed_set:
                    skipped += 1
                    continue

            # Read frontmatter
            try:
                content, has_bom, uses_crlf = _read_markdown(fp)
            except Exception as e:
                if args.jsonl:
                    print(json.dumps({"file": fp_str, "status": "error",
                                      "error": f"Read error: {e}"},
                                     ensure_ascii=False))
                else:
                    print(f"[{idx}/{total}] error     {fp} (read error: {e})")
                warned += 1
                continue

            fm, body, _ = parse_frontmatter(content)

            # ── only-missing skip ──
            if args.only_missing and _has_scholarly_data(fm):
                # Check if complete
                if _scholarly_is_complete(fm, ["citation"]):
                    if not args.jsonl:
                        print(f"[{idx}/{total}] skip      {fp} (already complete)")
                    skipped += 1
                    continue

            # ── locked check ──
            if _is_locked(fm) and not args.force:
                if not args.jsonl:
                    print(f"[{idx}/{total}] locked    {fp} (scholarly.locked)")
                skipped += 1
                if job:
                    job.setdefault("skipped", []).append(fp_str)
                    job["last_processed"] = fp_str
                    _save_job_state(job, root)
                continue

            # ── Non-Markdown skip ──
            if fp.suffix != ".md":
                skipped += 1
                continue

            # Extract DOI
            file_doi = _extract_doi_from_md(fp)
            if not file_doi:
                if not args.jsonl:
                    print(f"[{idx}/{total}] skip      {fp} (no DOI)")
                skipped += 1
                continue

            # ── Enrich ──
            try:
                result = enricher.enrich_by_doi(file_doi)
            except Exception as e:
                if args.jsonl:
                    print(json.dumps({"file": fp_str, "status": "error",
                                      "error": f"Enrichment error: {e}"},
                                     ensure_ascii=False))
                else:
                    print(f"[{idx}/{total}] error     {fp} ({e})")
                warned += 1
                if job:
                    job.setdefault("failed", []).append(fp_str)
                    job.setdefault("errors", []).append(f"{fp_str}: {e}")
                    job["last_processed"] = fp_str
                    _save_job_state(job, root)
                continue

            # ── JSONL output ──
            if args.jsonl:
                rec = result.record
                jl = {
                    "file": fp_str,
                    "status": "enriched",
                    "doi": rec.doi,
                    "title": rec.title,
                    "journal": rec.journal_name,
                    "crossref": rec.crossref_status.value,
                    "openalex": rec.openalex_status.value,
                    "rankings": [
                        {"scheme": r.scheme, "edition": r.edition, "level": r.level}
                        for r in result.journal_rankings
                    ],
                    "citations": {
                        c.style.value: c.engine_used
                        for c in result.citations if not c.is_empty()
                    },
                    "warnings": result.warnings,
                }
                print(json.dumps(jl, ensure_ascii=False))

            # ── Write ──
            if actually_write:
                if result.record.crossref_status not in (
                    SourceStatus.AVAILABLE, SourceStatus.NOT_FOUND
                ) and result.record.openalex_status not in (
                    SourceStatus.AVAILABLE,
                ):
                    if result.warnings:
                        print(f"[{idx}/{total}] warning   {fp} ({result.warnings[0][:60]})")
                    warned += 1
                    continue

                if update_markdown_file(fp, result):
                    if not args.jsonl:
                        print(f"[{idx}/{total}] enriched  {fp}")
                    enriched += 1
                    written += 1
                    if job:
                        job.setdefault("succeeded", []).append(fp_str)
                else:
                    if not args.jsonl:
                        print(f"[{idx}/{total}] error     {fp} (write failed)")
                    warned += 1
            elif is_dry:
                if not args.jsonl:
                    status_label = "would enrich" if result.record.crossref_status in (
                        SourceStatus.AVAILABLE, SourceStatus.NOT_FOUND,
                    ) else "no data"
                    print(f"[{idx}/{total}] {status_label:<10} {fp}")
                enriched += 1  # Count as would-enrich
            else:
                # Preview mode
                enriched += 1

            # Update job state
            if job:
                job["last_processed"] = fp_str
                _save_job_state(job, root)

        # ── Final summary ──
        if job:
            job["status"] = "completed" if warned == 0 else "completed_with_warnings"
            job["completed_at"] = datetime.now(timezone.utc).isoformat()
            _save_job_state(job, root)

        if not args.jsonl:
            print(f"\n{'='*50}")
            print(f"  Scan complete: {total} files")
            print(f"  Enriched: {enriched}  |  Skipped: {skipped}  |  Warnings: {warned}")
            if actually_write:
                print(f"  Written: {written}")
            elif is_dry:
                print(f"  (dry-run — no files modified)")
            print(f"{'='*50}")

        return

    # ── Single file mode ──
    if args.target:
        fp = Path(args.target)
        if not fp.is_absolute():
            fp = root / fp
        if fp.exists() and fp.suffix == ".md":
            # Check locked
            try:
                content, has_bom, uses_crlf = _read_markdown(fp)
            except Exception as e:
                print(f"ERROR: Cannot read {fp}: {e}", file=sys.stderr)
                sys.exit(1)
            fm, body, _ = parse_frontmatter(content)

            if _is_locked(fm) and not args.force:
                print(f"Skipped: {fp} (scholarly.locked is true)")
                if args.json or args.jsonl:
                    print(json.dumps({"file": str(fp), "status": "locked",
                                      "skipped_reason": "scholarly.locked is true"},
                                     ensure_ascii=False))
                return

            file_doi = _extract_doi_from_md(fp)
            if not file_doi:
                print(f"No DOI found in {fp}")
                sys.exit(1)

            enricher = ScholarlyEnricher(config=config)
            result = enricher.enrich_by_doi(file_doi)

            # dry-run takes precedence
            if args.dry_run:
                print(f"[DRY RUN] Would enrich: {fp}")
                print(f"  DOI: {file_doi}")
                print(f"  Crossref: {result.record.crossref_status.value}")
                print(f"  OpenAlex: {result.record.openalex_status.value}")
                return

            if args.write:
                if update_markdown_file(fp, result):
                    print(f"Updated: {fp}")
                else:
                    sys.exit(1)
            elif args.json or args.jsonl:
                _display_json(result)
            else:
                _display_result(result)
            return

    # ── No valid input ──
    parser.print_help()


if __name__ == "__main__":
    main()
