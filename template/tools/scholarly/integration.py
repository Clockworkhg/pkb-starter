"""Scholarly enrichment integration layer for /pkb workflow.

Connects scholarly enrichment to the PKB ingest pipeline with:
  - Synchronous enrichment before commit
  - Fail-open semantics (enrichment failure never blocks /pkb)
  - Idempotent writes (no duplicate fields, no spurious diffs)
  - Locked-page protection (scholarly.locked: true → skip)
  - Source tracking for every enriched field

Phase 1B: production integration. No background tasks, no PostToolUse hooks.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Ensure tools/ is on path
_TOOLS_DIR = Path(__file__).resolve().parent.parent
if str(_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOLS_DIR))

from scholarly.detector import (
    ScholarlyDetectionResult,
    detect_scholarly,
    should_auto_enrich,
)
from scholarly.enrichment import ScholarlyEnricher, EnrichmentConfig
from scholarly.models import (
    CitationData,
    CitationStyle,
    EnrichmentResult,
    SourceStatus,
)


# ─────────────────────────────────────────────
# Integration configuration
# ─────────────────────────────────────────────

@dataclass
class ScholarlyIntegrationConfig:
    """Configuration for scholarly enrichment within /pkb flow.

    All fields have safe defaults. API keys read from environment only.
    """
    enabled: bool = True
    auto_enrich_on_pkb: bool = True
    detection_threshold: float = 0.90
    citation_engine: str = "auto"
    citation_styles: List[str] = field(default_factory=lambda: ["gbt7714-numeric", "apa7"])
    use_crossref: bool = True
    use_openalex: bool = True
    cache_only: bool = False
    offline: bool = False
    write_metrics: bool = True
    write_citations: bool = True
    fail_open: bool = True

    @classmethod
    def from_config_dict(cls, d: Optional[Dict[str, Any]] = None) -> "ScholarlyIntegrationConfig":
        """Create from a config dict (e.g. pkb.config.json scholarly section).

        Unknown or missing keys fall back to safe defaults.
        """
        if not d or not isinstance(d, dict):
            return cls()
        return cls(
            enabled=bool(d.get("enabled", True)),
            auto_enrich_on_pkb=bool(d.get("auto_enrich_on_pkb", True)),
            detection_threshold=float(d.get("detection_threshold", 0.90)),
            citation_engine=str(d.get("citation_engine", "auto")),
            citation_styles=list(d.get("citation_styles", ["gbt7714-numeric", "apa7"])),
            use_crossref=bool(d.get("use_crossref", True)),
            use_openalex=bool(d.get("use_openalex", True)),
            cache_only=bool(d.get("cache_only", False)),
            offline=bool(d.get("offline", False)),
            write_metrics=bool(d.get("write_metrics", True)),
            write_citations=bool(d.get("write_citations", True)),
            fail_open=bool(d.get("fail_open", True)),
        )


# ─────────────────────────────────────────────
# Integration result
# ─────────────────────────────────────────────

@dataclass
class ScholarlyIntegrationResult:
    """Result of scholarly enrichment integration into /pkb flow.

    Tracks what happened for final report and diagnostics.
    """
    detected: bool = False
    attempted: bool = False
    changed: bool = False
    confidence: float = 0.0
    source_statuses: Dict[str, str] = field(default_factory=dict)
    cache_statuses: Dict[str, str] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    match_result: Optional[Dict[str, Any]] = None
    citation_engines: Dict[str, str] = field(default_factory=dict)
    detection_result: Optional[ScholarlyDetectionResult] = None
    enrichment_result: Optional[EnrichmentResult] = None
    skipped_reason: str = ""
    locked: bool = False


# ─────────────────────────────────────────────
# Frontmatter parsing utilities
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
    fm = _parse_simple_yaml(fm_raw)
    return fm, body, fm_raw


def _parse_simple_yaml(raw: str) -> Dict[str, Any]:
    """Parse simple flat YAML frontmatter with nested dict support."""
    result: Dict[str, Any] = {}
    current_nested: Optional[str] = None
    current_sub: Optional[str] = None
    current_list: Optional[str] = None
    current_list_item: Optional[Dict[str, Any]] = None
    for line in raw.split("\n"):
        if not line.strip() or line.strip().startswith("#"):
            continue

        # Indentation tracking
        indent = len(line) - len(line.lstrip())
        stripped = line.strip()

        # List item at indent 2 (e.g. "- scheme: CSSCI")
        if stripped.startswith("- ") and indent == 2:
            item_content = stripped[2:].strip()
            if ":" in item_content:
                k, _, v = item_content.partition(":")
                k = k.strip()
                v = v.strip()
                entry = {k: v.strip("'\"")}
                # Check if we're inside a nested block that expects a list
                if current_nested and isinstance(result.get(current_nested), dict):
                    current_list = current_nested
                    if not isinstance(result[current_nested], list):
                        # First list item — convert from dict to list
                        existing = result[current_nested]
                        result[current_nested] = []
                        if existing:
                            result[current_nested].append(existing)
                    current_list_item = entry
                    result[current_nested].append(entry)
                else:
                    # Top-level list item
                    if current_list is None:
                        result[current_nested or "__list__"] = []
                        current_list = current_nested or "__list__"
                    current_list_item = entry
                    result[current_list].append(entry)
            continue

        # Sub-field of list item at indent 4 (e.g. "    edition: 2025-2026")
        if ":" in stripped and indent == 4 and current_list_item is not None:
            key, _, value = stripped.partition(":")
            key = key.strip()
            value = value.strip()
            current_list_item[key] = value.strip("'\"")
            continue

        if ":" in stripped:
            key, _, value = stripped.partition(":")
            key = key.strip()
            value = value.strip()

            if indent == 0:
                current_nested = None
                current_sub = None
                current_list = None
                current_list_item = None
                if value == "":
                    # Nested dict starting
                    current_nested = key
                    result[key] = {}
                elif value.startswith("[") and value.endswith("]"):
                    inner = value[1:-1]
                    result[key] = [v.strip().strip("'\"") for v in inner.split(",") if v.strip()]
                else:
                    result[key] = value.strip("'\"")
            elif indent == 2 and current_nested is not None and isinstance(result.get(current_nested), dict):
                if value == "":
                    current_sub = key
                    result[current_nested][key] = {}
                elif value.startswith("[") and value.endswith("]"):
                    # List value at indent 2
                    inner = value[1:-1]
                    result[current_nested][key] = [v.strip().strip("'\"") for v in inner.split(",") if v.strip()]
                else:
                    result[current_nested][key] = value.strip("'\"")
            elif indent == 4 and current_nested is not None and current_sub is not None:
                result[current_nested][current_sub][key] = value.strip("'\"")
    return result


def _serialise_simple_yaml(fm: Dict[str, Any]) -> str:
    """Serialise a nested dict back to YAML with proper indentation."""
    def _format_value(v: Any) -> str:
        """Format a scalar value, quoting if needed for YAML safety."""
        s = str(v)
        # Quote if value contains ':' followed by space (YAML key-value ambiguity)
        if isinstance(v, str) and (': ' in s or s.startswith('[') or s.startswith('{')):
            return f"'{s}'"
        return s

    lines = []
    for key, value in fm.items():
        if isinstance(value, dict):
            if not value:
                continue  # skip empty dicts
            lines.append(f"{key}:")
            for k, v in value.items():
                if isinstance(v, dict):
                    if not v:
                        continue
                    lines.append(f"  {k}:")
                    for k2, v2 in v.items():
                        if isinstance(v2, list):
                            items = ", ".join(
                                f"'{x}'" if " " in str(x) else str(x) for x in v2
                            )
                            lines.append(f"    {k2}: [{items}]")
                        elif isinstance(v2, bool):
                            lines.append(f"    {k2}: {'true' if v2 else 'false'}")
                        else:
                            lines.append(f"    {k2}: {_format_value(v2)}")
                elif isinstance(v, list):
                    items = ", ".join(
                        f"'{x}'" if " " in str(x) else str(x) for x in v
                    )
                    lines.append(f"  {k}: [{items}]")
                elif isinstance(v, bool):
                    lines.append(f"  {k}: {'true' if v else 'false'}")
                else:
                    lines.append(f"  {k}: {_format_value(v)}")
        elif isinstance(value, list):
            if not value:
                continue  # skip empty lists
            items = ", ".join(f"'{v}'" if " " in str(v) else str(v) for v in value)
            lines.append(f"{key}: [{items}]")
        elif isinstance(value, bool):
            lines.append(f"{key}: {'true' if value else 'false'}")
        else:
            lines.append(f"{key}: {_format_value(value)}")
    return "\n".join(lines)


# ─────────────────────────────────────────────
# File I/O with encoding safety
# ─────────────────────────────────────────────

def _detect_bom(filepath: Path) -> bool:
    try:
        with open(filepath, 'rb') as f:
            return f.read(3) == b'\xef\xbb\xbf'
    except Exception:
        return False


def _detect_crlf(filepath: Path) -> bool:
    try:
        with open(filepath, 'rb') as f:
            raw = f.read(4096)
            return b'\r\n' in raw
    except Exception:
        return False


def _read_markdown(filepath: Path) -> Tuple[str, bool, bool]:
    """Read Markdown with BOM and line-ending detection. UTF-8 strict."""
    has_bom = _detect_bom(filepath)
    uses_crlf = _detect_crlf(filepath)
    with open(filepath, 'rb') as f:
        raw = f.read()
    if has_bom:
        raw = raw[3:]
    content = raw.decode('utf-8')  # strict — raises UnicodeDecodeError on invalid
    return content, has_bom, uses_crlf


def _atomic_write(filepath: Path, content: str, has_bom: bool, uses_crlf: bool) -> bool:
    """Atomic write to a Markdown file, preserving encoding and line endings."""
    if uses_crlf:
        content = content.replace('\n', '\r\n')
    encoding = "utf-8-sig" if has_bom else "utf-8"

    tmp_path = filepath.parent / (filepath.name + ".tmp")
    try:
        tmp_path.write_text(content, encoding=encoding)
        try:
            with open(tmp_path, 'r+b') as f:
                os.fsync(f.fileno())
        except (OSError, IOError):
            pass
        try:
            os.chmod(tmp_path, filepath.stat().st_mode)
        except Exception:
            pass
        os.replace(tmp_path, filepath)
        return True
    except Exception:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except Exception:
                pass
        return False


# ─────────────────────────────────────────────
# Frontmatter merge — controlled namespace
# ─────────────────────────────────────────────

# Fields that the scholarly module is allowed to modify
_CONTROLLED_TOP_KEYS = {
    "scholarly", "journal_rankings", "metrics", "citation",
    "metadata_match", "doi", "issn", "issn_l",
}

_CONTROLLED_PREFIXES = ("scholarly.", "journal_ranking", "metrics.", "citation.", "metadata_match.")


def _is_locked(fm: Dict[str, Any]) -> bool:
    """Check if the page's scholarly section is user-locked."""
    scholarly = fm.get("scholarly", {})
    if isinstance(scholarly, dict):
        return bool(scholarly.get("locked", False))
    return False


def _format_author_display(family: str, given: str) -> str:
    """Format a single author name for display in frontmatter.

    - CJK names: family + given, no space (e.g. 张三)
    - Non-CJK names: family + ' ' + given (e.g. Doe John)
    """
    import re as _re
    family = family.strip()
    given = given.strip()
    if not family and not given:
        return ""
    if not family:
        return given
    if not given:
        return family
    has_cjk = bool(_re.search(r'[一-鿿㐀-䶿豈-﫿]', family + given))
    if has_cjk:
        return f"{family}{given}"
    return f"{family} {given}"


def _build_scholarly_frontmatter(
    result: EnrichmentResult,
    detection: ScholarlyDetectionResult,
    existing_fm: Dict[str, Any],
    config: ScholarlyIntegrationConfig,
) -> Dict[str, Any]:
    """Build the scholarly frontmatter block from enrichment result.

    Returns a dict ready to merge into the page frontmatter.
    All fields include source tracking.
    """
    now_ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    rec = result.record

    # Preserve existing enriched_at for idempotency
    existing_scholarly = existing_fm.get("scholarly", {})
    if isinstance(existing_scholarly, dict) and existing_scholarly.get("enriched_at"):
        existing_enriched = existing_scholarly["enriched_at"]
        # Only preserve if it looks like a valid timestamp (not from a newer run)
        if isinstance(existing_enriched, str) and existing_enriched.startswith("20"):
            now_ts = existing_enriched

    # ── scholarly namespace ──
    scholarly: Dict[str, Any] = {
        "detected": True,
        "detected_type": detection.detected_type,
        "enriched_at": now_ts,
        "sources": [],
    }
    if rec.doi:
        scholarly["doi"] = rec.doi
        scholarly["sources"].append("crossref")
    if rec.title:
        scholarly["title"] = rec.title
    if rec.authors:
        scholarly["authors"] = [
            _format_author_display(a.get('family', ''), a.get('given', ''))
            for a in rec.authors
        ]
    if rec.year:
        scholarly["year"] = str(rec.year)
    if rec.journal_name:
        scholarly["journal"] = rec.journal_name
    if rec.issn:
        scholarly["issn"] = rec.issn
    if rec.issn_l:
        scholarly["issn_l"] = rec.issn_l
    if rec.volume:
        scholarly["volume"] = rec.volume
    if rec.issue:
        scholarly["issue"] = rec.issue
    if rec.pages if hasattr(rec, 'pages') else rec.page:
        scholarly["pages"] = rec.pages if hasattr(rec, 'pages') and rec.pages else rec.page
    if rec.pub_type:
        scholarly["pub_type"] = rec.pub_type

    # Track available sources
    if rec.crossref_status == SourceStatus.AVAILABLE:
        if "crossref" not in scholarly["sources"]:
            scholarly["sources"].append("crossref")
    if rec.openalex_status == SourceStatus.AVAILABLE:
        scholarly["sources"].append("openalex")
    scholarly["sources"] = list(set(scholarly["sources"]))

    # Preserve locked state if it was set
    existing_scholarly = existing_fm.get("scholarly", {})
    if isinstance(existing_scholarly, dict) and existing_scholarly.get("locked"):
        scholarly["locked"] = True

    # ── journal_rankings ──
    journal_rankings: List[Dict[str, Any]] = []
    if result.journal_rankings and config.write_metrics:
        for r in result.journal_rankings:
            entry = {
                "scheme": r.scheme,
                "edition": r.edition,
                "level": r.level,
                "source_label": r.source_label if r.source_label else "auto_matched",
            }
            if r.category:
                entry["category"] = r.category
            if result.match_result:
                entry["matched_by"] = result.match_result.method.value
                entry["confidence"] = round(result.match_result.confidence, 2)
            journal_rankings.append(entry)

    # ── metrics ──
    metrics: Dict[str, Any] = {}
    if rec.metrics and config.write_metrics:
        for m in rec.metrics:
            if m.status != SourceStatus.AVAILABLE:
                continue  # Don't write unavailable/error metrics
            if m.source not in metrics:
                metrics[m.source] = {}
            if m.value is not None:
                metrics[m.source][m.metric_name] = m.value
        if rec.retrieved_at:
            metrics["retrieved_at"] = rec.retrieved_at

    # ── citations ──
    citation: Dict[str, Any] = {}
    if result.citations and config.write_citations:
        for c in result.citations:
            if c.is_empty():
                continue
            if c.style in (CitationStyle.BIBTEX, CitationStyle.RIS):
                continue  # BibTeX/RIS too long for frontmatter
            entry: Dict[str, Any] = {
                "text": c.formatted,
                "engine_used": c.engine_used,
                "strict": c.strict,
            }
            if c.warnings:
                entry["warnings"] = c.warnings
            citation[c.style.value] = entry

    # ── metadata_match ──
    result_dict = {
        "scholarly": scholarly,
    }
    if journal_rankings:
        result_dict["journal_rankings"] = journal_rankings
    if metrics:
        result_dict["metrics"] = metrics
    if citation:
        result_dict["citation"] = citation
    if result.match_result:
        mr = result.match_result
        result_dict["metadata_match"] = {
            "method": mr.method.value,
            "confidence": round(mr.confidence, 2),
        }
        if mr.needs_review:
            result_dict["metadata_match"]["needs_review"] = True
    return result_dict


def _is_idempotent(
    existing_fm: Dict[str, Any],
    new_scholarly: Dict[str, Any],
) -> bool:
    """Check if the new scholarly data is identical to existing.

    Returns True if no changes needed (idempotent — skip write).
    """
    for key in ("scholarly", "journal_rankings", "metrics", "citation", "metadata_match"):
        existing = existing_fm.get(key)
        new_val = new_scholarly.get(key)
        if _normalize_for_comparison(existing) != _normalize_for_comparison(new_val):
            return False
    return True


def _normalize_for_comparison(value: Any) -> Any:
    """Normalize values for comparison (sort lists, strip strings, bool↔str equivalence)."""
    if isinstance(value, dict):
        return {k: _normalize_for_comparison(v) for k, v in sorted(value.items())}
    if isinstance(value, list):
        return sorted(str(_normalize_for_comparison(v)) for v in value)
    if isinstance(value, str):
        s = value.strip()
        # Normalize YAML boolean strings to actual bools for comparison
        if s.lower() in ("true", "false"):
            return s.lower() == "true"
        return s
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return str(value)
    return str(value)


# ─────────────────────────────────────────────
# Main integration entry point
# ─────────────────────────────────────────────

def enrich_wiki_page_if_scholarly(
    page_path: Path,
    *,
    root: Optional[Path] = None,
    config: Optional[ScholarlyIntegrationConfig] = None,
    force: bool = False,
) -> ScholarlyIntegrationResult:
    """Detect if a wiki page is scholarly and enrich if appropriate.

    This is the main entry point for /pkb integration. Called after wiki page
    generation and before health check + commit.

    Args:
        page_path: Path to the wiki Markdown file.
        root: PKB root directory (auto-detected if None).
        config: Integration config (defaults if None).
        force: If True, bypass locked check and detection threshold.

    Returns:
        ScholarlyIntegrationResult with full status.
    """
    if root is None:
        root = page_path.parent.parent
    if config is None:
        config = ScholarlyIntegrationConfig()

    result = ScholarlyIntegrationResult()

    # ── 0. Quick guard: skip if scholarly disabled ──
    if not config.enabled:
        result.skipped_reason = "scholarly disabled in config"
        return result

    # ── 1. Read the file ──
    try:
        content, has_bom, uses_crlf = _read_markdown(page_path)
    except UnicodeDecodeError as e:
        result.errors.append(f"Encoding error: {e}")
        return result
    except Exception as e:
        result.errors.append(f"Read error: {e}")
        return result

    fm, body, fm_raw = parse_frontmatter(content)

    # ── 2. Check locked ──
    if _is_locked(fm) and not force:
        result.locked = True
        result.skipped_reason = "scholarly.locked is true"
        return result

    # ── 3. Detect ──
    detection = detect_scholarly(
        frontmatter=fm,
        body=body,
        source_url=str(fm.get("source_url", fm.get("url", ""))),
        file_name=page_path.name,
    )
    result.detection_result = detection
    result.detected = detection.is_scholarly
    result.confidence = detection.confidence

    if not detection.is_scholarly:
        result.skipped_reason = f"not scholarly (confidence: {detection.confidence})"
        return result

    # ── 4. Check if should enrich ──
    if not force and not should_auto_enrich(detection, threshold=config.detection_threshold):
        result.skipped_reason = (
            f"confidence {detection.confidence} below threshold {config.detection_threshold}"
        )
        return result

    # ── 5. Extract DOI ──
    doi = detection.identifiers.get("doi", "")
    if not doi:
        doi = str(fm.get("doi", ""))
    if not doi and isinstance(fm.get("scholarly"), dict):
        doi = str(fm["scholarly"].get("doi", ""))

    if not doi:
        result.warnings.append("No DOI found; enrichment limited")
        # Without DOI, we can still try to match journal rankings from frontmatter
        result.skipped_reason = "no DOI available for enrichment"
        return result

    # ── 6. Run enrichment ──
    result.attempted = True
    try:
        enrich_config = EnrichmentConfig(
            crossref_email=os.environ.get("CROSSREF_EMAIL", ""),
            openalex_api_key=os.environ.get("OPENALEX_API_KEY", ""),
            cache_only=config.cache_only,
            offline=config.offline,
            skip_openalex=not config.use_openalex,
            skip_citations=not config.write_citations,
            citation_engine=config.citation_engine,
        )
        enricher = ScholarlyEnricher(config=enrich_config)
        enrich_result = enricher.enrich_by_doi(doi)
        result.enrichment_result = enrich_result

        # Track source statuses
        result.source_statuses["crossref"] = enrich_result.record.crossref_status.value
        result.source_statuses["openalex"] = enrich_result.record.openalex_status.value

        # Track warnings and errors from enrichment
        result.warnings.extend(enrich_result.warnings)
        result.errors.extend(enrich_result.errors)

        # Track citation engines
        for c in enrich_result.citations:
            if not c.is_empty():
                result.citation_engines[c.style.value] = c.engine_used

        # Track match
        if enrich_result.match_result:
            result.match_result = {
                "method": enrich_result.match_result.method.value,
                "confidence": enrich_result.match_result.confidence,
            }

    except Exception as e:
        result.errors.append(f"Enrichment error: {e}")
        if not config.fail_open:
            return result
        # fail-open: continue with whatever we have
        result.warnings.append(
            f"Enrichment failed ({e}); page saved without enrichment. "
            f"Retry: python tools/scholarly_enrich.py \"{page_path}\" --write"
        )
        return result

    # ── 7. Build scholarly frontmatter ──
    if enrich_result is None or (
        enrich_result.record.crossref_status not in (
            SourceStatus.AVAILABLE,
        ) and enrich_result.record.openalex_status not in (
            SourceStatus.AVAILABLE,
        )
    ):
        result.warnings.append("No data available from any source; page saved without enrichment")
        return result

    new_scholarly = _build_scholarly_frontmatter(
        enrich_result, detection, fm, config
    )

    # ── 8. Idempotency check ──
    if _is_idempotent(fm, new_scholarly):
        result.changed = False
        return result

    # ── 9. Merge into frontmatter ──
    new_fm = dict(fm)
    # Overwrite or remove controlled keys
    for key in _CONTROLLED_TOP_KEYS:
        if key in new_scholarly:
            new_fm[key] = new_scholarly[key]
        elif key in new_fm:
            del new_fm[key]  # Remove old controlled key no longer present

    # ── 10. Write back ──
    new_fm_yaml = _serialise_simple_yaml(new_fm)
    new_content = f"---\n{new_fm_yaml}\n---\n\n{body}"

    if new_content == content:
        result.changed = False
        return result

    success = _atomic_write(page_path, new_content, has_bom, uses_crlf)
    if success:
        result.changed = True
    else:
        result.errors.append("Atomic write failed; original file preserved")

    return result


# ─────────────────────────────────────────────
# Batch orchestration for /pkb pipeline
# ─────────────────────────────────────────────

@dataclass
class ScholarlyBatchResult:
    """Aggregate result from batch scholarly enrichment of wiki pages.

    Tracks: which pages were processed, what changed, call order proof.
    """
    pages_processed: int = 0
    pages_enriched: int = 0
    pages_skipped: int = 0
    pages_locked: int = 0
    errors: List[str] = field(default_factory=list)
    results: Dict[str, ScholarlyIntegrationResult] = field(default_factory=dict)
    call_order: List[str] = field(default_factory=list)
    enriched_before_commit: bool = False


def scholarly_enrich_pages(
    page_paths: List[Path],
    *,
    root: Optional[Path] = None,
    config: Optional[ScholarlyIntegrationConfig] = None,
    commit_recorder: Optional[List[str]] = None,
    only_paths: Optional[set] = None,
) -> ScholarlyBatchResult:
    """Orchestrate scholarly enrichment for a batch of wiki pages.

    This is the synchronous orchestrator called by /pkb Step 4.
    It processes only the given pages (no unconditional wiki scan),
    runs before commit, and is fully testable.

    Args:
        page_paths: List of wiki page paths to check/enrich.
        root: PKB root directory.
        config: Integration config.
        commit_recorder: Optional list to record call sequence for testing.
        only_paths: If set, only process pages whose path is in this set
                    (used to ensure only new/updated pages are processed).

    Returns:
        ScholarlyBatchResult with aggregate statistics and per-page results.
    """
    if config is None:
        config = ScholarlyIntegrationConfig()

    batch = ScholarlyBatchResult()

    # Record: enrichment starts BEFORE commit
    if commit_recorder is not None:
        commit_recorder.append("scholarly_enrich_start")
        batch.call_order.append("scholarly_enrich_start")

    for page_path in page_paths:
        if not page_path.exists():
            batch.errors.append(f"Missing: {page_path}")
            continue
        if not page_path.suffix == ".md":
            continue
        if only_paths is not None and str(page_path) not in only_paths:
            continue

        batch.pages_processed += 1
        try:
            result = enrich_wiki_page_if_scholarly(
                page_path, root=root, config=config
            )
            batch.results[str(page_path)] = result

            if result.changed:
                batch.pages_enriched += 1
            elif result.locked:
                batch.pages_locked += 1
            elif result.skipped_reason:
                batch.pages_skipped += 1

            if result.errors:
                batch.errors.extend(result.errors)

        except Exception as e:
            batch.errors.append(f"{page_path}: {e}")

    # Record: enrichment complete BEFORE commit
    if commit_recorder is not None:
        commit_recorder.append("scholarly_enrich_end")
        batch.call_order.append("scholarly_enrich_end")

    batch.enriched_before_commit = True
    return batch


# ─────────────────────────────────────────────
# Report generation for /pkb output
# ─────────────────────────────────────────────

def scholarly_report_summary(result: ScholarlyIntegrationResult) -> str:
    """Generate a concise summary for /pkb final report.

    Only called when scholarly processing occurred.
    """
    if not result.detected:
        return ""

    lines = ["Scholarly metadata:"]

    det = result.detection_result
    if det and det.identifiers.get("doi"):
        lines.append(f"- DOI: {det.identifiers['doi']}")

    enr = result.enrichment_result
    if enr:
        rec = enr.record
        if rec.journal_name:
            lines.append(f"- Journal: {rec.journal_name}")
        if enr.journal_rankings:
            for r in enr.journal_rankings[:3]:
                lines.append(f"- Rankings: {r.scheme} {r.edition} ({r.level})")
        if rec.metrics:
            for m in rec.metrics:
                if m.metric_name == "cited_by_count" and m.value:
                    lines.append(f"- OpenAlex citations: {int(m.value)}")
        for c in enr.citations:
            if not c.is_empty() and c.engine_used and c.style not in (CitationStyle.BIBTEX, CitationStyle.RIS):
                lines.append(f"- Citation: {c.style.value.upper()} ({c.engine_used})")

    if result.errors:
        # Show one clean error message, not the full stack
        lines.append(f"- Enrichment issue: {result.errors[0][:100]}")

    if result.locked:
        lines.append("- Locked by user; skipped")

    if result.skipped_reason and not result.attempted:
        lines.append(f"- {result.skipped_reason}")

    return "\n".join(lines)
