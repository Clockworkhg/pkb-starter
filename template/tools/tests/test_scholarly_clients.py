"""Tests for Crossref and OpenAlex API clients.

ALL TESTS USE MOCK. No real network access.
Covers: DOI normalisation, API parsing, error handling, retry logic, OpenAlex no-key.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

_TOOLS_DIR = Path(__file__).resolve().parent.parent / "tools"
if str(_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOLS_DIR))

import pytest
import requests

from scholarly.clients.crossref import (
    CrossrefClient,
    is_doi_like,
    normalise_doi,
)
from scholarly.clients.openalex import OpenAlexClient
from scholarly.models import (
    APIError,
    DOIParseError,
    NetworkError,
    NonRetryableError,
    RetryableError,
    SourceStatus,
)


# ═══════════════════════════════════════════════════════════
# DOI normalisation
# ═══════════════════════════════════════════════════════════

def test_normalise_doi_simple():
    assert normalise_doi("10.1234/example") == "10.1234/example"


def test_normalise_doi_with_prefix():
    assert normalise_doi("https://doi.org/10.1234/example") == "10.1234/example"


def test_normalise_doi_with_doi_scheme():
    assert normalise_doi("doi:10.1234/example") == "10.1234/example"


def test_normalise_doi_lowercase_prefix():
    assert normalise_doi("10.ABCD/Example") == "10.abcd/Example"


def test_normalise_doi_whitespace():
    assert normalise_doi("  10.1234/test  ") == "10.1234/test"


def test_normalise_doi_empty():
    assert normalise_doi("") == ""


def test_is_doi_like_valid():
    assert is_doi_like("10.1234/example")
    assert is_doi_like("10.12345/some.path/here")


def test_is_doi_like_invalid():
    assert not is_doi_like("")
    assert not is_doi_like("not-a-doi")
    assert not is_doi_like("11.1234/test")  # wrong prefix


# ═══════════════════════════════════════════════════════════
# Crossref client tests (all mocked)
# ═══════════════════════════════════════════════════════════

CROSSREF_RESPONSE = {
    "message": {
        "title": ["Platform Governance in the Age of Algorithms"],
        "author": [
            {"family": "Zhang", "given": "San"},
            {"family": "Li", "given": "Si"},
        ],
        "container-title": ["Journal of Communication Research"],
        "issn-type": [
            {"type": "print", "value": "1005-2577"},
            {"type": "electronic", "value": "1005-2578"},
        ],
        "ISSN": ["1005-2577"],
        "ISSN-L": "1005-2577",
        "issued": {"date-parts": [[2025]]},
        "volume": "32",
        "issue": "4",
        "page": "15-28",
        "publisher": "Communication Press",
        "type": "journal-article",
        "DOI": "10.1234/example",
    }
}


class TestCrossrefClient:
    """All tests use mock responses."""

    @pytest.fixture
    def mock_session(self):
        session = MagicMock()
        return session

    @pytest.fixture
    def client(self, mock_session):
        return CrossrefClient(session=mock_session)

    def test_lookup_doi_success(self, client, mock_session):
        """Successful DOI lookup returns populated ScholarlyRecord."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = CROSSREF_RESPONSE
        mock_session.request.return_value = mock_resp

        record = client.lookup_doi("10.1234/example")

        assert record.title == "Platform Governance in the Age of Algorithms"
        assert len(record.authors) == 2
        assert record.authors[0]["family"] == "Zhang"
        assert record.journal_name == "Journal of Communication Research"
        assert record.year == 2025
        assert record.volume == "32"
        assert record.issue == "4"
        assert record.page == "15-28"
        assert record.doi == "10.1234/example"
        assert "1005-2577" in record.issn
        assert record.crossref_status == SourceStatus.AVAILABLE

    def test_lookup_doi_invalid(self, client):
        """Invalid DOI raises DOIParseError."""
        with pytest.raises(DOIParseError):
            client.lookup_doi("not-a-doi")

    def test_lookup_doi_not_found(self, client, mock_session):
        """404 returns NonRetryableError."""
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_session.request.return_value = mock_resp

        with pytest.raises(NonRetryableError) as exc_info:
            client.lookup_doi("10.1234/nonexistent")
        assert exc_info.value.status_code == 404

    def test_lookup_doi_429_retry(self, client, mock_session):
        """429 should trigger retry and eventually succeed."""
        rate_limited = MagicMock(spec=requests.Response)
        rate_limited.status_code = 429

        success = MagicMock(spec=requests.Response)
        success.status_code = 200
        success.json.return_value = CROSSREF_RESPONSE

        # First call → 429, second call → 200
        mock_session.request.side_effect = [rate_limited, success]

        record = client.lookup_doi("10.1234/example")
        assert record.title  # Should succeed after retry

    def test_lookup_doi_500_retry_fail(self, client, mock_session):
        """500 after max retries should raise RetryableError."""
        error_resp = MagicMock(spec=requests.Response)
        error_resp.status_code = 500

        mock_session.request.return_value = error_resp

        with pytest.raises(RetryableError):
            client.lookup_doi("10.1234/example")

    def test_lookup_doi_400_no_retry(self, client, mock_session):
        """400 should NOT trigger retry (instant NonRetryableError)."""
        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_session.request.return_value = mock_resp

        with pytest.raises(NonRetryableError):
            client.lookup_doi("10.1234/example")

        # Should only have been called once (no retry)
        assert mock_session.request.call_count == 1

    def test_lookup_doi_timeout(self, client, mock_session):
        """Connection timeout should raise NetworkError after retries."""
        mock_session.request.side_effect = requests.ConnectionError("timeout")

        with pytest.raises(NetworkError):
            client.lookup_doi("10.1234/example")

    def test_lookup_doi_minimal_fields(self, client, mock_session):
        """Minimal Crossref response should not crash."""
        minimal = {
            "message": {
                "title": ["Test"],
                "DOI": "10.1234/minimal",
            }
        }
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = minimal
        mock_session.request.return_value = mock_resp

        record = client.lookup_doi("10.1234/minimal")
        assert record.title == "Test"
        assert record.authors == []
        assert record.year == 0
        assert record.issn == []


# ═══════════════════════════════════════════════════════════
# OpenAlex client tests (all mocked)
# ═══════════════════════════════════════════════════════════

OPENALEX_WORK_RESPONSE = {
    "id": "https://openalex.org/W123456",
    "doi": "https://doi.org/10.1234/example",
    "title": "Platform Governance in the Age of Algorithms",
    "publication_date": "2025-03-15",
    "type": "article",
    "cited_by_count": 16,
    "authorships": [
        {
            "author": {"display_name": "Zhang, San"},
        },
        {
            "author": {"display_name": "Li, Si"},
        },
    ],
    "primary_location": {
        "source": {
            "display_name": "Journal of Communication Research",
            "issn": ["1005-2577", "1005-2578"],
            "issn_l": "1005-2577",
        }
    },
    "biblio": {
        "volume": "32",
        "issue": "4",
        "first_page": "15",
        "last_page": "28",
    },
    "open_access": {
        "oa_status": "gold",
    },
    "summary_stats": {},
}


OPENALEX_SOURCE_RESPONSE = {
    "id": "https://openalex.org/S12345",
    "display_name": "Journal of Communication Research",
    "issn": ["1005-2577", "1005-2578"],
    "issn_l": "1005-2577",
    "publisher": "Communication Press",
    "works_count": 2500,
    "cited_by_count": 12000,
    "summary_stats": {
        "2yr_mean_citedness": 3.82,
        "h_index": 45,
    },
    "is_in_doaj": True,
}


class TestOpenAlexClient:
    """All tests use mock responses."""

    @pytest.fixture
    def mock_session(self):
        session = MagicMock()
        return session

    @pytest.fixture
    def client(self, mock_session):
        return OpenAlexClient(api_key="test-key", session=mock_session)

    def test_lookup_work_success(self, client, mock_session):
        """Successful work lookup returns ScholarlyRecord with metrics."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = OPENALEX_WORK_RESPONSE
        mock_session.request.return_value = mock_resp

        record = client.lookup_work_by_doi("10.1234/example")

        assert record.title == "Platform Governance in the Age of Algorithms"
        assert record.openalex_status == SourceStatus.AVAILABLE
        assert record.openalex_id == "https://openalex.org/W123456"
        assert record.year == 2025
        assert record.volume == "32"
        assert record.issue == "4"
        assert record.page == "15-28"

        # Metrics
        assert len(record.metrics) >= 1
        cited_by = [m for m in record.metrics if m.metric_name == "cited_by_count"]
        assert len(cited_by) == 1
        assert cited_by[0].value == 16.0

    def test_lookup_source_success(self, client, mock_session):
        """Source lookup returns JournalIdentity."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = OPENALEX_SOURCE_RESPONSE
        mock_session.request.return_value = mock_resp

        identity = client.lookup_source_by_issn("1005-2577")
        assert identity is not None
        assert identity.journal_name == "Journal of Communication Research"
        assert identity.issn == "1005-2577"

    def test_lookup_source_not_found(self, client, mock_session):
        """404 on source returns None without raising."""
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_session.request.return_value = mock_resp

        identity = client.lookup_source_by_issn("9999-9999")
        assert identity is None

    def test_lookup_source_with_metrics(self, client, mock_session):
        """Source with metrics returns both identity and metrics."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = OPENALEX_SOURCE_RESPONSE
        mock_session.request.return_value = mock_resp

        identity, metrics = client.lookup_source_with_metrics("1005-2577")
        assert identity is not None
        # Check that we have metrics
        metric_names = {m.metric_name for m in metrics}
        assert "2yr_mean_citedness" in metric_names
        assert "h_index" in metric_names
        assert "works_count" in metric_names

        # 2yr_mean_citedness is NOT called "影响因子"
        two_yr = [m for m in metrics if m.metric_name == "2yr_mean_citedness"][0]
        assert two_yr.value == 3.82
        assert "openalex" in two_yr.display_label().lower()
        assert "impact" not in two_yr.display_label().lower()
        assert "影响" not in two_yr.display_label()

    def test_no_api_key(self, mock_session):
        """Client without API key returns UNAVAILABLE immediately — no request made."""
        client = OpenAlexClient(api_key="", session=mock_session)
        assert not client.has_api_key

        record = client.lookup_work_by_doi("10.1234/example")
        # Without API key, returns UNAVAILABLE immediately
        assert record.openalex_status == SourceStatus.UNAVAILABLE
        # No HTTP request was made
        assert mock_session.request.call_count == 0

    def test_no_api_key_source_returns_none(self, mock_session):
        """Source lookup without API key returns None immediately."""
        client = OpenAlexClient(api_key="", session=mock_session)
        result = client.lookup_source_by_issn("1005-2577")
        assert result is None
        assert mock_session.request.call_count == 0

    def test_429_retry(self, client, mock_session):
        """429 should retry then succeed."""
        rate_limited = MagicMock(spec=requests.Response)
        rate_limited.status_code = 429

        success = MagicMock(spec=requests.Response)
        success.status_code = 200
        success.json.return_value = OPENALEX_WORK_RESPONSE

        mock_session.request.side_effect = [rate_limited, success]
        record = client.lookup_work_by_doi("10.1234/example")
        assert record.openalex_status == SourceStatus.AVAILABLE
        assert mock_session.request.call_count >= 2

    def test_404_no_retry(self, client, mock_session):
        """404 on work should raise without retry."""
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_session.request.return_value = mock_resp

        with pytest.raises(NonRetryableError):
            client.lookup_work_by_doi("10.1234/nonexistent")
        assert mock_session.request.call_count == 1

    def test_timeout_raises_network_error(self, client, mock_session):
        """Connection timeout → NetworkError after retries."""
        mock_session.request.side_effect = requests.Timeout("timed out")

        with pytest.raises(NetworkError):
            client.lookup_work_by_doi("10.1234/example")

    def test_diagnostics_captured(self, client, mock_session):
        """Rate limit headers are captured in diagnostics."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = OPENALEX_WORK_RESPONSE
        mock_resp.headers = {
            "x-rate-limit": "100",
            "x-rate-limit-remaining": "95",
        }
        mock_session.request.return_value = mock_resp

        client.lookup_work_by_doi("10.1234/example")
        diag = client.diagnostics
        assert diag["status_code"] == 200
        assert diag.get("x-rate-limit-remaining") == "95"
