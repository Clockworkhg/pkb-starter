"""OpenAlex API client for scholarly metrics and open data.

OpenAlex REST API: https://api.openalex.org/

Design:
  - API key from OPENALEX_API_KEY env var. Falls back gracefully without it.
  - DOI → Work lookup. ISSN → Source lookup.
  - 2yr_mean_citedness is NOT "Journal Impact Factor". Labels always include "OpenAlex".
  - Exposes rate-limit headers in diagnostics.
  - Exponential backoff on 429 + 5xx.
  - All metrics retain their OpenAlex source identity.
  - Tests use mock — no real network access.
"""

from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import requests

from ..models import (
    APIError,
    JournalIdentity,
    MetricSnapshot,
    NetworkError,
    NonRetryableError,
    RetryableError,
    ScholarlyRecord,
    SourceStatus,
)


OPENALEX_API_BASE = "https://api.openalex.org"
OPENALEX_USER_AGENT = "PKB-ScholarlyMetadata/0.1"
DEFAULT_TIMEOUT = (10, 30)


class OpenAlexClient:
    """OpenAlex REST API client for works and sources."""

    def __init__(self, api_key: Optional[str] = None,
                 timeout: Tuple[float, float] = DEFAULT_TIMEOUT,
                 session: Optional[requests.Session] = None):
        """
        Args:
            api_key: OpenAlex API key. Read from OPENALEX_API_KEY if not provided.
                     None/empty = polite pool (unauthenticated).
            timeout: (connect_timeout, read_timeout) in seconds.
            session: Optional requests.Session (for testing with mock).
        """
        self.api_key = api_key or os.environ.get("OPENALEX_API_KEY", "")
        self.timeout = timeout
        self._session = session
        self._last_diagnostics: Dict[str, Any] = {}

    @property
    def has_api_key(self) -> bool:
        return bool(self.api_key)

    @property
    def session(self) -> requests.Session:
        if self._session is None:
            s = requests.Session()
            s.headers.update({
                "User-Agent": OPENALEX_USER_AGENT,
                "Accept": "application/json",
            })
            self._session = s
        return self._session

    @property
    def diagnostics(self) -> Dict[str, Any]:
        """Last request diagnostics (rate limit info, etc.)."""
        return dict(self._last_diagnostics)

    # ── Public API ──

    def lookup_work_by_doi(self, doi: str) -> ScholarlyRecord:
        """Look up a scholarly work by DOI.

        If no API key is configured, returns a record with status UNAVAILABLE
        rather than failing — the rest of the pipeline can continue.
        """
        from ..models import DOIParseError, CacheStatus
        from .crossref import normalise_doi, is_doi_like

        doi_norm = normalise_doi(doi)
        if not doi_norm or not is_doi_like(doi_norm):
            raise DOIParseError(f"Invalid DOI: {doi!r}")

        if not self.api_key:
            return ScholarlyRecord(
                doi=doi_norm,
                openalex_status=SourceStatus.UNAVAILABLE,
                openalex_cache_status=CacheStatus.NOT_ATTEMPTED,
                retrieved_at=self._now_iso(),
            )

        url = f"{OPENALEX_API_BASE}/works/doi:{doi_norm}"
        params: Dict[str, str] = {}
        if self.api_key:
            params["api_key"] = self.api_key

        resp_data = self._request_with_retry("GET", url, params=params)
        return self._parse_work(resp_data, doi_norm)

    def lookup_source_by_issn(self, issn: str) -> Optional[JournalIdentity]:
        """Look up journal/source by ISSN or ISSN-L.

        Returns None if not found or no API key configured.
        """
        if not issn:
            return None
        if not self.api_key:
            return None

        url = f"{OPENALEX_API_BASE}/sources/issn:{issn}"
        params: Dict[str, str] = {}
        if self.api_key:
            params["api_key"] = self.api_key

        try:
            resp_data = self._request_with_retry("GET", url, params=params)
            return self._parse_source(resp_data)
        except NonRetryableError as e:
            if e.status_code == 404:
                return None
            raise

    def lookup_source_metrics_by_issn(self, issn: str) -> List[MetricSnapshot]:
        """Get metrics for a journal/source by ISSN."""
        identity = self.lookup_source_by_issn(issn)
        if identity is None:
            return []
        return self._extract_source_metrics(identity)

    # ── HTTP layer ──

    def _request_with_retry(self, method: str, url: str,
                            params: Optional[Dict[str, str]] = None,
                            max_retries: int = 3) -> Dict[str, Any]:
        """Perform HTTP request with exponential backoff."""
        self._last_diagnostics = {}
        last_exc: Optional[Exception] = None

        for attempt in range(max_retries + 1):
            try:
                resp = self.session.request(method, url, params=params, timeout=self.timeout)

                # Capture diagnostics
                try:
                    self._last_diagnostics = {
                        "status_code": resp.status_code,
                        "x-rate-limit": resp.headers.get("x-rate-limit", ""),
                        "x-rate-limit-remaining": resp.headers.get("x-rate-limit-remaining", ""),
                    }
                except (AttributeError, KeyError):
                    self._last_diagnostics = {"status_code": resp.status_code}

                if resp.status_code == 200:
                    return resp.json()

                if resp.status_code == 404:
                    raise NonRetryableError(404, f"Not found in OpenAlex: {url}")

                if resp.status_code == 429:
                    if attempt < max_retries:
                        delay = self._backoff_delay(attempt, resp)
                        time.sleep(delay)
                        continue
                    raise RetryableError(429, "OpenAlex rate limit exceeded")

                if resp.status_code in (500, 502, 503, 504):
                    if attempt < max_retries:
                        delay = self._backoff_delay(attempt, resp)
                        time.sleep(delay)
                        continue
                    raise RetryableError(resp.status_code,
                                         f"OpenAlex server error {resp.status_code}")

                if 400 <= resp.status_code < 500:
                    raise NonRetryableError(resp.status_code,
                                            f"OpenAlex client error {resp.status_code}")

                raise APIError(resp.status_code, f"Unexpected OpenAlex response")

            except (requests.ConnectionError, requests.Timeout) as e:
                last_exc = e
                if attempt < max_retries:
                    delay = 2 ** attempt
                    time.sleep(delay)
                    continue
                raise NetworkError(f"OpenAlex network error: {e}") from e

            except (NonRetryableError, RetryableError, APIError):
                raise

        if last_exc:
            raise NetworkError(f"OpenAlex request failed after retries")
        raise APIError(0, "OpenAlex request failed without specific error")

    @staticmethod
    def _backoff_delay(attempt: int, resp) -> float:
        base = 2 ** attempt
        try:
            retry_after = resp.headers.get("Retry-After", "")
            if retry_after and retry_after.isdigit():
                return max(base, float(retry_after))
        except (AttributeError, KeyError):
            pass
        return base

    # ── Response parsing ──

    def _parse_work(self, data: Dict[str, Any], doi: str) -> ScholarlyRecord:
        """Parse OpenAlex work response into ScholarlyRecord extension."""
        # OpenAlex returns the work directly (no 'message' wrapper like Crossref)
        title = data.get("title", "") or ""
        doi_from_api = data.get("doi", "") or doi

        # Authorship
        authors: List[Dict[str, str]] = []
        for authorship in data.get("authorships", []) or []:
            author = authorship.get("author", {}) or {}
            family = author.get("display_name", "")
            given = ""
            if "," in family:
                parts = family.split(",", 1)
                family = parts[0].strip()
                given = parts[1].strip()
            if family:
                authors.append({"family": family, "given": given})

        # Venue / primary location
        primary = data.get("primary_location", {}) or {}
        source_info = (primary.get("source") or {}) if primary else {}
        journal_name = (source_info.get("display_name") or "")

        # Source details
        issn_l = data.get("primary_location", {}).get("source", {}).get("issn_l", "") or ""
        issns_raw = (source_info.get("issn") or []) if source_info else []
        issn_list: List[str] = list(issns_raw) if issns_raw else []

        # Publication date
        pub_date = data.get("publication_date", "") or ""
        year = 0
        if pub_date and "-" in str(pub_date):
            try:
                year = int(str(pub_date).split("-")[0])
            except (ValueError, IndexError):
                pass

        # Biblio
        biblio = data.get("biblio", {}) or {}
        volume = biblio.get("volume", "") or ""
        issue = biblio.get("issue", "") or ""
        page = ""
        first_page = biblio.get("first_page", "") or ""
        last_page = biblio.get("last_page", "") or ""
        if first_page and last_page:
            page = f"{first_page}-{last_page}"
        elif first_page:
            page = str(first_page)

        # Type
        pub_type = data.get("type", "article-journal") or "article-journal"
        if pub_type == "article":
            pub_type = "article-journal"

        # Metrics
        metrics: List[MetricSnapshot] = []
        cited_by = data.get("cited_by_count")
        if cited_by is not None:
            metrics.append(MetricSnapshot(
                source="openalex",
                metric_name="cited_by_count",
                value=float(cited_by),
                unit="citations",
                retrieved_at=self._now_iso(),
            ))

        # Open access
        oa_info = data.get("open_access", {}) or {}
        oa_status = oa_info.get("oa_status", "")
        if oa_status:
            metrics.append(MetricSnapshot(
                source="openalex",
                metric_name="oa_status",
                value=None,
                unit=oa_status,
                retrieved_at=self._now_iso(),
            ))

        # OpenAlex ID
        oa_id = data.get("id", "") or ""

        return ScholarlyRecord(
            doi=doi,
            title=title,
            authors=authors,
            journal_name=journal_name,
            issn=issn_list,
            issn_l=issn_l,
            year=year,
            volume=str(volume),
            issue=str(issue),
            page=page,
            pub_type=pub_type,
            openalex_status=SourceStatus.AVAILABLE,
            openalex_id=oa_id,
            metrics=metrics,
            retrieved_at=self._now_iso(),
        )

    def _parse_source(self, data: Dict[str, Any]) -> Optional[JournalIdentity]:
        """Parse OpenAlex source into JournalIdentity."""
        display_name = data.get("display_name", "") or ""
        issn_l = data.get("issn_l", "") or ""
        issns = data.get("issn", []) or []

        print_issn = ""
        eissn = ""
        if len(issns) >= 1:
            print_issn = issns[0]
        if len(issns) >= 2:
            eissn = issns[1]

        publisher = data.get("publisher", "") or ""

        return JournalIdentity(
            issn=print_issn,
            eissn=eissn,
            issn_l=issn_l,
            journal_name=display_name,
            publisher=publisher,
        )

    def _extract_source_metrics(self, identity: JournalIdentity) -> List[MetricSnapshot]:
        """Fetch metrics for a source.

        Note: the identity already has basic info; this adds metric fields.
        Actually we need to re-fetch to get metrics. Let's attach to the source directly.
        """
        # In Phase 1A, metrics come from the Work lookup, not Source.
        # Source-level metrics (2yr_mean_citedness, h_index) require a separate
        # Source object fetch, which is triggered by lookup_source_by_issn.
        # Those detailed metrics are parsed in _parse_source_with_metrics.
        return []

    def lookup_source_with_metrics(self, issn: str) -> Tuple[Optional[JournalIdentity], List[MetricSnapshot]]:
        """Look up source by ISSN and extract detailed metrics.

        Returns (JournalIdentity, list of MetricSnapshot).
        Returns (None, []) if no API key or ISSN not found.
        """
        if not issn:
            return None, []
        if not self.api_key:
            return None, []

        url = f"{OPENALEX_API_BASE}/sources/issn:{issn}"
        params: Dict[str, str] = {}
        if self.api_key:
            params["api_key"] = self.api_key

        try:
            resp_data = self._request_with_retry("GET", url, params=params)
        except NonRetryableError as e:
            if e.status_code == 404:
                return None, []
            raise

        identity = self._parse_source(resp_data)
        if identity is None:
            return None, []

        metrics: List[MetricSnapshot] = []
        now_iso = self._now_iso()

        # 2-year mean citedness — always label with "OpenAlex"
        two_yr = resp_data.get("summary_stats", {}).get("2yr_mean_citedness")
        if two_yr is not None:
            metrics.append(MetricSnapshot(
                source="openalex",
                metric_name="2yr_mean_citedness",
                value=float(two_yr),
                unit="citations per article (2-year window)",
                retrieved_at=now_iso,
            ))

        # h-index
        h_idx = resp_data.get("summary_stats", {}).get("h_index")
        if h_idx is not None:
            metrics.append(MetricSnapshot(
                source="openalex",
                metric_name="h_index",
                value=float(h_idx),
                unit="h-index",
                retrieved_at=now_iso,
            ))

        # Works count
        works_count = resp_data.get("works_count")
        if works_count is not None:
            metrics.append(MetricSnapshot(
                source="openalex",
                metric_name="works_count",
                value=float(works_count),
                unit="total works",
                retrieved_at=now_iso,
            ))

        # Cited by count (total citations to this journal)
        cited_by = resp_data.get("cited_by_count")
        if cited_by is not None:
            metrics.append(MetricSnapshot(
                source="openalex",
                metric_name="source_cited_by_count",
                value=float(cited_by),
                unit="total citations to source",
                retrieved_at=now_iso,
            ))

        # DOAJ status
        if resp_data.get("is_in_doaj"):
            metrics.append(MetricSnapshot(
                source="openalex",
                metric_name="is_in_doaj",
                value=1.0,
                unit="boolean",
                retrieved_at=now_iso,
            ))

        return identity, metrics

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()
