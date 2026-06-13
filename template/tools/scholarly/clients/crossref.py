"""Crossref API client for scholarly metadata retrieval.

Crossref REST API: https://api.crossref.org/

Design:
  - DOI lookup only (Phase 1A).
  - Converts all responses to ScholarlyRecord.
  - User-Agent and contact email are configurable.
  - Exponential backoff on 429 + 5xx. No retry on 4xx (except 429).
  - All tests use mock — no real network access.
"""

from __future__ import annotations

import os
import re
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote

import requests

from ..models import (
    APIError,
    JournalIdentity,
    NetworkError,
    NonRetryableError,
    RetryableError,
    ScholarlyRecord,
    SourceStatus,
)


# ─────────────────────────────────────────────
# DOI helpers
# ─────────────────────────────────────────────

_DOI_PREFIX_RE = re.compile(r'^https?://(?:dx\.)?doi\.org/', re.IGNORECASE)
_DOI_SCHEME_RE = re.compile(r'^doi:\s*', re.IGNORECASE)


def normalise_doi(raw: str) -> str:
    """Normalise a DOI string.

    Handles:
      - https://doi.org/10.1234/foo → 10.1234/foo
      - doi:10.1234/foo → 10.1234/foo
      - Leading/trailing whitespace
      - Case normalisation (DOIs are case-insensitive but lowercase is canonical)
    """
    if not raw:
        return ""
    s = raw.strip()
    s = _DOI_PREFIX_RE.sub('', s)
    s = _DOI_SCHEME_RE.sub('', s)
    s = s.strip()
    # Lowercase the prefix part (before first /), keep suffix as-is
    if '/' in s:
        prefix, suffix = s.split('/', 1)
        s = f"{prefix.lower()}/{suffix}"
    else:
        s = s.lower()
    return s


def is_doi_like(s: str) -> bool:
    """Quick check if a string looks like a DOI."""
    if not s:
        return False
    n = normalise_doi(s)
    return bool(re.match(r'^10\.\d{4,}/.+', n))


# ─────────────────────────────────────────────
# Crossref client
# ─────────────────────────────────────────────

CROSSREF_API_BASE = "https://api.crossref.org"
CROSSREF_USER_AGENT = "PKB-ScholarlyMetadata/0.1 (mailto:{email})"
DEFAULT_TIMEOUT = (10, 30)   # (connect, read)


class CrossrefClient:
    """Crossref REST API client for DOI metadata lookup."""

    def __init__(self, email: Optional[str] = None, timeout: Tuple[float, float] = DEFAULT_TIMEOUT,
                 session: Optional[requests.Session] = None):
        """
        Args:
            email: Contact email for Crossref's User-Agent policy.
                   Read from CROSSREF_EMAIL env var if not provided.
            timeout: (connect_timeout, read_timeout) in seconds.
            session: Optional requests.Session (useful for testing with mock).
        """
        self.email = email or os.environ.get("CROSSREF_EMAIL", "")
        self.timeout = timeout
        self._session = session

    @property
    def session(self) -> requests.Session:
        if self._session is None:
            s = requests.Session()
            ua = CROSSREF_USER_AGENT.format(email=self.email or "unknown")
            s.headers.update({
                "User-Agent": ua,
                "Accept": "application/json",
            })
            self._session = s
        return self._session

    # ── Public API ──

    def lookup_doi(self, doi: str) -> ScholarlyRecord:
        """Look up a DOI in Crossref and return a ScholarlyRecord.

        Raises:
            DOIParseError: If the DOI is malformed.
            APIError: For HTTP errors (subclass indicates retryable vs not).
            NetworkError: For connection/timeout errors.
        """
        from ..models import DOIParseError

        doi_norm = normalise_doi(doi)
        if not doi_norm or not is_doi_like(doi_norm):
            raise DOIParseError(f"Invalid DOI: {doi!r}")

        url = f"{CROSSREF_API_BASE}/works/{quote(doi_norm, safe='')}"
        resp_data = self._request_with_retry("GET", url)
        return self._parse_work(resp_data, doi_norm)

    # ── HTTP layer ──

    def _request_with_retry(self, method: str, url: str,
                            max_retries: int = 3) -> Dict[str, Any]:
        """Perform an HTTP request with exponential backoff on retryable errors."""
        last_exc: Optional[Exception] = None

        for attempt in range(max_retries + 1):
            try:
                resp = self.session.request(method, url, timeout=self.timeout)

                if resp.status_code == 200:
                    return resp.json()

                if resp.status_code == 404:
                    raise NonRetryableError(404, f"DOI not found in Crossref: {url}")

                if resp.status_code == 429:
                    # Rate limited — retry with backoff
                    if attempt < max_retries:
                        delay = self._backoff_delay(attempt, resp)
                        time.sleep(delay)
                        continue
                    raise RetryableError(429, "Crossref rate limit exceeded after retries")

                if resp.status_code in (500, 502, 503, 504):
                    if attempt < max_retries:
                        delay = self._backoff_delay(attempt, resp)
                        time.sleep(delay)
                        continue
                    raise RetryableError(resp.status_code,
                                         f"Crossref server error {resp.status_code} after retries")

                if 400 <= resp.status_code < 500:
                    raise NonRetryableError(resp.status_code,
                                            f"Crossref client error {resp.status_code}")

                # Unknown status — treat as error
                raise APIError(resp.status_code, f"Unexpected Crossref response: {resp.status_code}")

            except (requests.ConnectionError, requests.Timeout) as e:
                last_exc = e
                if attempt < max_retries:
                    delay = 2 ** attempt
                    time.sleep(delay)
                    continue
                raise NetworkError(f"Crossref network error: {e}") from e

            except (NonRetryableError, RetryableError, APIError):
                raise

        if last_exc:
            raise NetworkError(f"Crossref request failed after retries: {last_exc}")
        raise APIError(0, "Crossref request failed without specific error")

    @staticmethod
    def _backoff_delay(attempt: int, resp) -> float:
        """Compute backoff delay from attempt number and optional Retry-After header."""
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
        """Parse Crossref work response into ScholarlyRecord."""
        msg = data.get("message", {})
        if not msg:
            # DOI exists but no data
            return ScholarlyRecord(
                doi=doi,
                crossref_status=SourceStatus.NOT_FOUND,
                retrieved_at=self._now_iso(),
            )

        # Authors
        authors: List[Dict[str, str]] = []
        for a in msg.get("author", []) or []:
            family = a.get("family", "")
            given = a.get("given", "")
            if family or given:
                authors.append({"family": family, "given": given})

        # Title
        title_list = msg.get("title", []) or []
        title = title_list[0] if title_list else ""

        # Container (journal)
        container = msg.get("container-title", []) or []
        journal_name = container[0] if container else ""

        # ISSN
        issn_list: List[str] = []
        issn_type = msg.get("issn-type", []) or []
        issn_l = ""
        for entry in issn_type:
            itype = entry.get("type", "")
            ival = entry.get("value", "")
            if ival:
                issn_list.append(ival)
                if itype == "electronic":
                    pass  # eissn
                if itype == "print":
                    pass
        # Legacy flat ISSN array
        flat_issn = msg.get("ISSN", []) or []
        for v in flat_issn:
            if v and v not in issn_list:
                issn_list.append(v)

        # ISSN-L from message
        issn_l = msg.get("ISSN-L", "")

        # Publication details
        issued = msg.get("issued", {}) or {}
        date_parts = issued.get("date-parts", [[0]]) or [[0]]
        year = date_parts[0][0] if date_parts and date_parts[0] else 0

        volume = msg.get("volume", "") or ""
        issue = msg.get("issue", "") or ""
        page = msg.get("page", "") or ""
        article_number = msg.get("article-number", "") or ""

        # Publisher
        publisher = msg.get("publisher", "") or ""

        # Type
        pub_type = msg.get("type", "journal-article") or "journal-article"

        # Journal identity
        journal_identity = None
        print_issn = ""
        eissn = ""
        for entry in issn_type:
            if entry.get("type") == "print":
                print_issn = entry.get("value", "")
            elif entry.get("type") == "electronic":
                eissn = entry.get("value", "")

        if print_issn or issn_l:
            journal_identity = JournalIdentity(
                issn=print_issn, eissn=eissn, issn_l=issn_l,
                journal_name=journal_name, publisher=publisher,
            )

        return ScholarlyRecord(
            doi=doi,
            title=title,
            authors=authors,
            journal_name=journal_name,
            journal_identity=journal_identity,
            issn=issn_list,
            issn_l=issn_l,
            year=int(year) if year else 0,
            volume=str(volume),
            issue=str(issue),
            page=str(page),
            article_number=str(article_number) if article_number else "",
            publisher=publisher,
            pub_type=pub_type,
            crossref_status=SourceStatus.AVAILABLE,
            retrieved_at=self._now_iso(),
        )

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()
