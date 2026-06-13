"""Unified data models for the PKB Scholarly Metadata Enrichment system.

All external API responses MUST be converted into these internal models first.
Other modules MUST NOT depend on raw Crossref or OpenAlex JSON field names.

Design rules:
  - SourceStatus tracks what the external source returned (available/not_found/unavailable/…).
  - CacheStatus tracks whether the local cache was hit/missed/not-attempted (orthogonal axis).
  - Never use empty string or None to represent all failure states.
  - All dataclasses are frozen for immutability.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


# ─────────────────────────────────────────────
# Status enums
# ─────────────────────────────────────────────

class SourceStatus(str, Enum):
    """Data source retrieval status — what the external source returned.

    Covers only source-side outcomes. Cache hit/miss is tracked separately
    via CacheStatus on ScholarlyRecord.
    """
    AVAILABLE = "available"
    NOT_FOUND = "not_found"
    UNAVAILABLE = "unavailable"       # e.g. no API key configured
    INVALID = "invalid"               # e.g. malformed DOI
    ERROR = "error"                   # network or parse error


class CacheStatus(str, Enum):
    """Cache lookup outcome, orthogonal to source retrieval status."""
    HIT = "cache_hit"
    MISS = "cache_miss"
    NOT_ATTEMPTED = "cache_not_attempted"


class CitationStyle(str, Enum):
    """Supported citation output styles."""
    GBT7714_NUMERIC = "gbt7714-numeric"
    GBT7714_AUTHOR_DATE = "gbt7714-author-date"
    APA7 = "apa7"
    BIBTEX = "bibtex"
    RIS = "ris"


class JournalLevel(str, Enum):
    """Normalised journal ranking levels across schemes."""
    SOURCE = "source"                 # CSSCI 来源期刊 / PKU core
    EXTENDED = "extended"             # CSSCI 扩展版
    CORE = "core"                     # 北大核心
    AUTHORITATIVE = "authoritative"   # AMI 权威
    TOP = "top"                       # AMI 顶级
    TIER_A = "tier_a"
    TIER_B = "tier_b"
    TIER_C = "tier_c"
    CUSTOM = "custom"


class MatchMethod(str, Enum):
    """How a journal match was achieved — named by what was matched."""
    DOI_RESOLVED_ISSN_EXACT = "doi_resolved_issn_exact"
    ISSN_EXACT = "issn_exact"
    EISSN_EXACT = "eissn_exact"
    ISSN_L_EXACT = "issn_l_exact"
    NAME_EXACT = "name_exact"
    TITLE_AUTHOR_YEAR_FUZZY = "title_author_year_fuzzy"


class CitationEngine(str, Enum):
    """Which rendering engine to use for citation formatting."""
    AUTO = "auto"            # Let the formatter decide per style
    FALLBACK = "fallback"    # Force fallback formatter
    CITEPROC = "citeproc"    # Force citeproc-py (fail on error, no silent fallback)


# ─────────────────────────────────────────────
# Core data models
# ─────────────────────────────────────────────

@dataclass(frozen=True)
class JournalIdentity:
    """Canonical journal identity keyed by ISSN."""
    issn: str                          # Normalised: XXXX-XXXX
    eissn: str = ""
    issn_l: str = ""
    journal_name: str = ""             # Official name from Crossref / ISSN portal
    publisher: str = ""
    status: SourceStatus = SourceStatus.AVAILABLE

    def has_issn(self) -> bool:
        return bool(self.issn)

    def has_issn_l(self) -> bool:
        return bool(self.issn_l)


@dataclass(frozen=True)
class JournalRanking:
    """A single ranking entry from one evaluation system."""
    scheme: str                        # CSSCI / PKU_CORE / AMI / CSCD / CUSTOM
    edition: str                       # e.g. "2025-2026", "2023"
    journal_name: str                  # Original name from the ranking list
    normalized_name: str               # Normalised for matching
    issn: str = ""                     # Normalised XXXX-XXXX, may be ""
    eissn: str = ""
    issn_l: str = ""
    level: str = ""                    # source / extended / core / authoritative / …
    category: str = ""                 # e.g. "新闻学与传播学"
    source_label: str = ""             # Human-readable data provenance
    source_url: str = ""
    verified_at: str = ""              # ISO date of import / verification

    def match_key(self) -> str:
        """Stable key for dedup: scheme-edition-issn-normalized_name."""
        return f"{self.scheme}|{self.edition}|{self.issn}|{self.normalized_name}"


@dataclass(frozen=True)
class MetricSnapshot:
    """One datapoint from a metrics source."""
    source: str                        # openalex / jcr / scopus / custom
    metric_name: str                   # e.g. "2yr_mean_citedness"
    value: Optional[float] = None
    unit: str = ""                     # e.g. "citations per article"
    retrieved_at: str = ""
    status: SourceStatus = SourceStatus.AVAILABLE

    def display_label(self) -> str:
        """Human-readable label preserving source identity."""
        return f"{self.source} {self.metric_name}"


@dataclass(frozen=True)
class CitationData:
    """Citation strings in multiple formats, generated from unified model."""
    style: CitationStyle
    formatted: str                     # The actual citation text
    csl_json: Dict[str, Any] = field(default_factory=dict)
    status: SourceStatus = SourceStatus.AVAILABLE
    engine_used: str = ""              # "fallback" | "citeproc" | "direct" | ""
    style_requested: str = ""          # Value of the requested CitationStyle
    strict: bool = True                # False when engine output is unverified against golden tests
    warnings: List[str] = field(default_factory=list)  # Engine-specific warnings

    def is_empty(self) -> bool:
        return not self.formatted.strip()


@dataclass(frozen=True)
class MatchResult:
    """Outcome of a journal matching attempt."""
    method: MatchMethod
    confidence: float                  # 0.0 – 1.0
    matched_id: str = ""               # stable key of matched JournalRanking
    evidence: List[str] = field(default_factory=list)
    needs_review: bool = False

    # Recommended thresholds:
    #   confidence >= 0.92 → auto-accept
    #   0.80 <= confidence < 0.92 → needs_review
    #   confidence < 0.80 → do not use
    CONFIDENCE_AUTO_ACCEPT = 0.92
    CONFIDENCE_NEEDS_REVIEW = 0.80

    def is_auto_accepted(self) -> bool:
        """Auto-accept only for identifier-based exact matches.

        Name-exact and fuzzy matches never auto-accept regardless of score,
        because journal names can be ambiguous even at high bigram similarity.
        """
        if self.confidence < self.CONFIDENCE_AUTO_ACCEPT:
            return False
        ID_METHODS = {
            MatchMethod.DOI_RESOLVED_ISSN_EXACT,
            MatchMethod.ISSN_EXACT,
            MatchMethod.EISSN_EXACT,
            MatchMethod.ISSN_L_EXACT,
        }
        return self.method in ID_METHODS

    def is_rejected(self) -> bool:
        return self.confidence < self.CONFIDENCE_NEEDS_REVIEW


@dataclass(frozen=True)
class ScholarlyRecord:
    """Unified metadata for a single scholarly work."""
    # Source identification
    doi: str = ""
    title: str = ""
    authors: List[Dict[str, str]] = field(default_factory=list)
    #  Each author dict: {"family": "张", "given": "三"}

    # Journal
    journal_name: str = ""
    journal_identity: Optional[JournalIdentity] = None
    issn: List[str] = field(default_factory=list)   # All ISSNs found
    issn_l: str = ""

    # Publication details
    year: int = 0
    volume: str = ""
    issue: str = ""
    page: str = ""
    article_number: str = ""
    publisher: str = ""

    # Type
    pub_type: str = "journal-article"   # CSL type

    # Status for each data source
    crossref_status: SourceStatus = SourceStatus.UNAVAILABLE
    openalex_status: SourceStatus = SourceStatus.UNAVAILABLE
    # Cache lookup outcome (orthogonal to source_status)
    crossref_cache_status: CacheStatus = CacheStatus.NOT_ATTEMPTED
    openalex_cache_status: CacheStatus = CacheStatus.NOT_ATTEMPTED
    retrieved_at: str = ""

    # Metrics
    metrics: List[MetricSnapshot] = field(default_factory=list)
    openalex_id: str = ""

    def as_author_list(self) -> str:
        """Simple concatenation for display."""
        names = []
        for a in self.authors:
            family = a.get("family", "")
            given = a.get("given", "")
            if family and given:
                names.append(f"{family}, {given}")
            elif family:
                names.append(family)
        return "; ".join(names)


@dataclass(frozen=True)
class EnrichmentResult:
    """Complete enrichment output for one scholarly work."""
    record: ScholarlyRecord
    journal_rankings: List[JournalRanking] = field(default_factory=list)
    citations: List[CitationData] = field(default_factory=list)
    match_result: Optional[MatchResult] = None
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def has_journal_rankings(self) -> bool:
        return len(self.journal_rankings) > 0

    def has_citations(self) -> bool:
        return any(not c.is_empty() for c in self.citations)


# ─────────────────────────────────────────────
# Cache helpers
# ─────────────────────────────────────────────

@dataclass(frozen=True)
class CacheEntry:
    """One row in the SQLite cache."""
    namespace: str                     # e.g. "crossref", "openalex"
    cache_key: str                     # lookup key (DOI, ISSN, etc.)
    payload_json: str                  # JSON-serialised payload
    created_at: str                    # ISO timestamp
    expires_at: str                    # ISO timestamp


# ─────────────────────────────────────────────
# Custom exception hierarchy
# ─────────────────────────────────────────────

class ScholarlyError(Exception):
    """Base exception for scholarly module."""


class DOIParseError(ScholarlyError):
    """Invalid or unparseable DOI."""


class ISSNFormatError(ScholarlyError):
    """Invalid ISSN format or checksum."""


class NetworkError(ScholarlyError):
    """Network-level error (timeout, connection refused)."""


class APIError(ScholarlyError):
    """API returned an error response."""

    def __init__(self, status_code: int, message: str = ""):
        self.status_code = status_code
        super().__init__(f"HTTP {status_code}: {message}")


class RetryableError(APIError):
    """5xx or 429 — worth retrying with backoff."""


class NonRetryableError(APIError):
    """4xx (except 429) — do not retry."""


class ConfigError(ScholarlyError):
    """Misconfiguration (e.g. missing required API key)."""
