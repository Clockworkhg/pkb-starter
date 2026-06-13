"""Scholarly metadata enrichment — main entry point.

Orchestrates: DOI → Crossref → OpenAlex → cache → match → citations.
All modules are called through this interface; no direct client dependency
in CLI or external code.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from .cache import (
    MemoryCache,
    ScholarlyCache,
    TTL_DYNAMIC,
    TTL_STATIC,
    NS_CROSSREF,
    NS_OPENALEX_WORK,
    NS_OPENALEX_SOURCE,
)
from .citation_formatter import CitationFormatter
from .models import CitationEngine
from .clients.crossref import CrossrefClient, is_doi_like, normalise_doi
from .clients.openalex import OpenAlexClient
from .journal_registry import JournalRegistry
from .matcher import JournalMatcher
from .models import (
    CacheStatus,
    CitationData,
    CitationStyle,
    EnrichmentResult,
    JournalRanking,
    MatchResult,
    MetricSnapshot,
    ScholarlyRecord,
    SourceStatus,
)

# Sentinel: cache explicitly disabled (distinct from None = not-yet-initialised)
_NO_CACHE = object()


# ─────────────────────────────────────────────
# Enrichment configuration
# ─────────────────────────────────────────────

class EnrichmentConfig:
    """Configuration for the enrichment pipeline."""

    def __init__(self,
                 crossref_email: str = "",
                 openalex_api_key: str = "",
                 cache_only: bool = False,
                 offline: bool = False,
                 skip_openalex: bool = False,
                 skip_rankings: bool = False,
                 skip_citations: bool = False,
                 citation_engine: str = "auto"):
        self.crossref_email = crossref_email
        self.openalex_api_key = openalex_api_key
        self.cache_only = cache_only          # Only use cache, no network
        self.offline = offline                # No network, no cache fallback
        self.skip_openalex = skip_openalex    # Skip OpenAlex metrics
        self.skip_rankings = skip_rankings    # Skip journal ranking lookup
        self.skip_citations = skip_citations  # Skip citation formatting
        self.citation_engine = citation_engine  # "auto" | "fallback" | "citeproc"


# ─────────────────────────────────────────────
# Main enrichment function
# ─────────────────────────────────────────────

class ScholarlyEnricher:
    """Orchestrate the full enrichment pipeline.

    Usage:
        enricher = ScholarlyEnricher()
        result = enricher.enrich_by_doi("10.1234/example")
        # result.record, result.journal_rankings, result.citations, result.match_result
    """

    def __init__(self, config: Optional[EnrichmentConfig] = None,
                 cache: Optional[ScholarlyCache] = None,
                 registry: Optional[JournalRegistry] = None):
        self.config = config or EnrichmentConfig()
        self._cache = cache
        self._registry = registry

    @property
    def cache(self):
        """Return ScholarlyCache instance or None if explicitly disabled."""
        if self._cache is _NO_CACHE:
            return None
        if self._cache is None:
            self._cache = ScholarlyCache()
        return self._cache

    def _has_cache(self) -> bool:
        """Whether a cache object is available (not explicitly disabled)."""
        return self._cache is not _NO_CACHE

    @property
    def registry(self) -> JournalRegistry:
        if self._registry is None:
            self._registry = JournalRegistry()
        return self._registry

    def enrich_by_doi(self, doi: str) -> EnrichmentResult:
        """Full enrichment by DOI.

        Pipeline:
          1. Validate DOI
          2. Check cache
          3. Query Crossref (unless offline)
          4. Query OpenAlex (unless offline/skipped)
          5. Match journal rankings
          6. Generate citations
        """
        doi_norm = normalise_doi(doi)
        errors: List[str] = []
        warnings: List[str] = []

        if not doi_norm or not is_doi_like(doi_norm):
            return EnrichmentResult(
                record=ScholarlyRecord(doi=doi_norm),
                errors=[f"Invalid DOI: {doi!r}"],
            )

        # ── Step 1: Check cache ──
        cache_obj = self.cache  # None if explicitly disabled
        cache_queried = cache_obj is not None
        cache_hit = False
        cached_payload = None
        if cache_queried:
            cache_hit, cached_payload = cache_obj.get(NS_CROSSREF, doi_norm)

        if cache_hit and cached_payload:
            record = self._record_from_cache(cached_payload)
        elif self.config.offline:
            # Offline: cache WAS queried if available; MISS if queried but no entry
            return EnrichmentResult(
                record=ScholarlyRecord(
                    doi=doi_norm,
                    crossref_status=SourceStatus.UNAVAILABLE,
                    crossref_cache_status=(
                        CacheStatus.MISS if cache_queried
                        else CacheStatus.NOT_ATTEMPTED
                    ),
                ),
                warnings=["Offline mode: no cache entry for this DOI"],
            )
        elif self.config.cache_only:
            # Cache-only: always queried cache; MISS when no entry found
            return EnrichmentResult(
                record=ScholarlyRecord(
                    doi=doi_norm,
                    crossref_status=SourceStatus.UNAVAILABLE,
                    crossref_cache_status=CacheStatus.MISS,
                ),
                warnings=["Cache-only mode: no entry found (cache miss)"],
            )
        else:
            # ── Step 2: Crossref lookup ──
            try:
                crossref = CrossrefClient(email=self.config.crossref_email)
                record = crossref.lookup_doi(doi_norm)
                # Cache the result
                self.cache.set(NS_CROSSREF, doi_norm,
                               self._record_to_cache_payload(record),
                               ttl=TTL_STATIC)
            except Exception as e:
                errors.append(f"Crossref error: {e}")
                record = ScholarlyRecord(
                    doi=doi_norm,
                    crossref_status=SourceStatus.ERROR,
                )

        # ── Step 3: OpenAlex lookup ──
        if not self.config.skip_openalex and not self.config.offline and not self.config.cache_only:
            oa_cache_key = f"work:{doi_norm}"
            oa_hit, oa_payload = self.cache.get(NS_OPENALEX_WORK, oa_cache_key)
            if oa_hit and oa_payload:
                record = self._merge_openalex_cache(record, oa_payload)
            else:
                try:
                    oa = OpenAlexClient(api_key=self.config.openalex_api_key)
                    oa_record = oa.lookup_work_by_doi(doi_norm)
                    # Merge only the OpenAlex-specific fields
                    record = ScholarlyRecord(
                        doi=record.doi or oa_record.doi,
                        title=record.title or oa_record.title,
                        authors=record.authors or oa_record.authors,
                        journal_name=record.journal_name or oa_record.journal_name,
                        journal_identity=record.journal_identity,
                        issn=record.issn or oa_record.issn,
                        issn_l=record.issn_l or oa_record.issn_l,
                        year=record.year or oa_record.year,
                        volume=record.volume or oa_record.volume,
                        issue=record.issue or oa_record.issue,
                        page=record.page or oa_record.page,
                        publisher=record.publisher or oa_record.publisher,
                        pub_type=record.pub_type or oa_record.pub_type,
                        crossref_status=record.crossref_status,
                        crossref_cache_status=record.crossref_cache_status,
                        openalex_status=oa_record.openalex_status,
                        openalex_cache_status=oa_record.openalex_cache_status,
                        openalex_id=oa_record.openalex_id,
                        metrics=oa_record.metrics,
                        retrieved_at=datetime.now(timezone.utc).isoformat(),
                    )
                    try:
                        self.cache.set(NS_OPENALEX_WORK, oa_cache_key,
                                       {"metrics": [self._metric_to_dict(m) for m in oa_record.metrics],
                                        "openalex_id": oa_record.openalex_id},
                                       ttl=TTL_DYNAMIC)
                    except Exception:
                        pass  # Cache failure is non-fatal
                except Exception as e:
                    warnings.append(f"OpenAlex error: {e}")
                    record = ScholarlyRecord(
                        doi=record.doi,
                        title=record.title,
                        authors=record.authors,
                        journal_name=record.journal_name,
                        journal_identity=record.journal_identity,
                        issn=record.issn,
                        issn_l=record.issn_l,
                        year=record.year,
                        volume=record.volume,
                        issue=record.issue,
                        page=record.page,
                        publisher=record.publisher,
                        pub_type=record.pub_type,
                        crossref_status=record.crossref_status,
                        crossref_cache_status=record.crossref_cache_status,
                        openalex_status=SourceStatus.ERROR,
                        openalex_cache_status=CacheStatus.NOT_ATTEMPTED,
                        retrieved_at=datetime.now(timezone.utc).isoformat(),
                    )

        # ── Step 4: Journal ranking matching ──
        journal_rankings: List[JournalRanking] = []
        match_result: Optional[MatchResult] = None
        if not self.config.skip_rankings and self.registry.count() > 0:
            try:
                matcher = JournalMatcher(self.registry)
                match_result = matcher.match(record)
                if match_result and not match_result.is_rejected():
                    # Find all ranking entries from all schemes for this ISSN
                    for issn in record.issn:
                        rankings = self.registry.query_by_issn(issn)
                        journal_rankings.extend(rankings)
                    if record.issn_l:
                        rankings = self.registry.query_by_issn_l(record.issn_l)
                        for r in rankings:
                            if r not in journal_rankings:
                                journal_rankings.append(r)
                    # Deduplicate by match_key
                    seen = set()
                    deduped = []
                    for r in journal_rankings:
                        mk = r.match_key()
                        if mk not in seen:
                            seen.add(mk)
                            deduped.append(r)
                    journal_rankings = deduped
            except Exception as e:
                warnings.append(f"Journal matching error: {e}")

        # ── Step 5: Citation formatting ──
        citations: List[CitationData] = []
        if not self.config.skip_citations:
            try:
                engine = CitationEngine(self.config.citation_engine)
                formatter = CitationFormatter(engine=engine)
                citations = formatter.format_all(record)
            except Exception as e:
                warnings.append(f"Citation formatting error: {e}")

        return EnrichmentResult(
            record=record,
            journal_rankings=journal_rankings,
            citations=citations,
            match_result=match_result,
            errors=errors,
            warnings=warnings,
        )

    # ── Cache serialisation ──

    def _record_to_cache_payload(self, record: ScholarlyRecord) -> Dict[str, Any]:
        return {
            "doi": record.doi,
            "title": record.title,
            "authors": record.authors,
            "journal_name": record.journal_name,
            "issn": record.issn,
            "issn_l": record.issn_l,
            "year": record.year,
            "volume": record.volume,
            "issue": record.issue,
            "page": record.page,
            "article_number": record.article_number,
            "publisher": record.publisher,
            "pub_type": record.pub_type,
            "crossref_status": record.crossref_status.value,
            "crossref_cache_status": record.crossref_cache_status.value,
            "retrieved_at": record.retrieved_at,
        }

    def _record_from_cache(self, payload: Dict[str, Any]) -> ScholarlyRecord:
        return ScholarlyRecord(
            doi=payload.get("doi", ""),
            title=payload.get("title", ""),
            authors=payload.get("authors", []),
            journal_name=payload.get("journal_name", ""),
            issn=payload.get("issn", []),
            issn_l=payload.get("issn_l", ""),
            year=payload.get("year", 0),
            volume=payload.get("volume", ""),
            issue=payload.get("issue", ""),
            page=payload.get("page", ""),
            article_number=payload.get("article_number", ""),
            publisher=payload.get("publisher", ""),
            pub_type=payload.get("pub_type", "article-journal"),
            crossref_status=SourceStatus.AVAILABLE,
            crossref_cache_status=CacheStatus.HIT,
            retrieved_at=payload.get("retrieved_at", ""),
        )

    def _merge_openalex_cache(self, record: ScholarlyRecord, payload: Dict[str, Any]) -> ScholarlyRecord:
        metrics_raw = payload.get("metrics", [])
        metrics = [
            MetricSnapshot(
                source=m.get("source", "openalex"),
                metric_name=m.get("metric_name", ""),
                value=m.get("value"),
                unit=m.get("unit", ""),
                retrieved_at=m.get("retrieved_at", ""),
            )
            for m in metrics_raw
        ]
        return ScholarlyRecord(
            doi=record.doi,
            title=record.title,
            authors=record.authors,
            journal_name=record.journal_name,
            journal_identity=record.journal_identity,
            issn=record.issn,
            issn_l=record.issn_l,
            year=record.year,
            volume=record.volume,
            issue=record.issue,
            page=record.page,
            article_number=record.article_number,
            publisher=record.publisher,
            pub_type=record.pub_type,
            crossref_status=record.crossref_status,
            crossref_cache_status=record.crossref_cache_status,
            openalex_status=SourceStatus.AVAILABLE,
            openalex_cache_status=CacheStatus.HIT,
            openalex_id=payload.get("openalex_id", ""),
            metrics=metrics,
            retrieved_at=datetime.now(timezone.utc).isoformat(),
        )

    @staticmethod
    def _metric_to_dict(m: MetricSnapshot) -> Dict[str, Any]:
        return {
            "source": m.source,
            "metric_name": m.metric_name,
            "value": m.value,
            "unit": m.unit,
            "retrieved_at": m.retrieved_at,
        }


# ─────────────────────────────────────────────
# Module-level convenience
# ─────────────────────────────────────────────

def enrich_scholarly_record(
    doi: str = "",
    title: str = "",
    authors: Optional[List[Dict[str, str]]] = None,
    year: int = 0,
    journal: str = "",
    cache_only: bool = False,
    offline: bool = False,
    cache: Any = None,  # ScholarlyCache, None (auto-create), or False (disable)
) -> EnrichmentResult:
    """Convenience function for enrichment. Phase 1A: DOI is the primary key.

    Args:
        cache: ScholarlyCache instance, None (auto-create), or False (disable cache).
    """
    config = EnrichmentConfig(cache_only=cache_only, offline=offline)
    enricher = ScholarlyEnricher(config=config)
    if cache is False:
        enricher._cache = _NO_CACHE  # disable cache entirely

    if doi:
        return enricher.enrich_by_doi(doi)

    # Without DOI, create a minimal record
    record = ScholarlyRecord(
        title=title,
        authors=authors or [],
        journal_name=journal,
        year=year,
    )
    return EnrichmentResult(
        record=record,
        warnings=["No DOI provided — only local journal ranking match available"],
    )
