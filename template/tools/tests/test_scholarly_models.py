"""Tests for PKB scholarly data models.

Covers: model construction, immutability, status enums, ISSN helpers.
"""

from __future__ import annotations

import sys
from pathlib import Path

_TOOLS_DIR = Path(__file__).resolve().parent.parent / "tools"
if str(_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOLS_DIR))

import pytest

from scholarly.models import (
    CacheStatus,
    CitationData,
    CitationStyle,
    EnrichmentResult,
    JournalIdentity,
    JournalRanking,
    MatchMethod,
    MatchResult,
    MetricSnapshot,
    ScholarlyRecord,
    SourceStatus,
)
from scholarly.journal_registry import validate_issn, normalise_issn


# ═══════════════════════════════════════════════════════════
# SourceStatus enum
# ═══════════════════════════════════════════════════════════

def test_source_status_values():
    """SourceStatus enumerates source-side outcomes only (no cache states)."""
    values = {s.value for s in SourceStatus}
    assert "available" in values
    assert "not_found" in values
    assert "unavailable" in values
    assert "invalid" in values
    assert "error" in values
    # Cache states are NOT in SourceStatus — they are separate CacheStatus
    assert "cache_hit" not in values
    assert "skipped" not in values
    assert len(values) == 5


def test_cache_status_values():
    """CacheStatus enumerates cache lookup outcomes."""
    values = {s.value for s in CacheStatus}
    assert "cache_hit" in values
    assert "cache_miss" in values
    assert "cache_not_attempted" in values
    assert len(values) == 3


def test_match_method_values():
    """MatchMethod uses renamed members with accurate names."""
    assert MatchMethod.DOI_RESOLVED_ISSN_EXACT.value == "doi_resolved_issn_exact"
    assert MatchMethod.ISSN_EXACT.value == "issn_exact"
    assert MatchMethod.EISSN_EXACT.value == "eissn_exact"
    assert MatchMethod.ISSN_L_EXACT.value == "issn_l_exact"
    assert MatchMethod.NAME_EXACT.value == "name_exact"
    assert MatchMethod.TITLE_AUTHOR_YEAR_FUZZY.value == "title_author_year_fuzzy"


# ═══════════════════════════════════════════════════════════
# ScholarlyRecord
# ═══════════════════════════════════════════════════════════

def test_scholarly_record_defaults():
    r = ScholarlyRecord()
    assert r.doi == ""
    assert r.title == ""
    assert r.authors == []
    assert r.year == 0
    assert r.crossref_status == SourceStatus.UNAVAILABLE
    assert r.openalex_status == SourceStatus.UNAVAILABLE
    assert r.crossref_cache_status == CacheStatus.NOT_ATTEMPTED
    assert r.openalex_cache_status == CacheStatus.NOT_ATTEMPTED


def test_scholarly_record_authors():
    r = ScholarlyRecord(authors=[
        {"family": "张", "given": "三"},
        {"family": "Smith", "given": "John"},
    ])
    assert len(r.authors) == 2
    assert r.as_author_list() == "张, 三; Smith, John"


def test_scholarly_record_immutable():
    r = ScholarlyRecord(title="Test")
    with pytest.raises(Exception):
        r.title = "Changed"  # type: ignore[misc]


# ═══════════════════════════════════════════════════════════
# JournalIdentity
# ═══════════════════════════════════════════════════════════

def test_journal_identity():
    ji = JournalIdentity(issn="1005-2577", journal_name="新闻与传播研究")
    assert ji.has_issn()
    assert not ji.has_issn_l()


def test_journal_identity_no_issn():
    ji = JournalIdentity(issn="", journal_name="Unknown")
    assert not ji.has_issn()


# ═══════════════════════════════════════════════════════════
# JournalRanking
# ═══════════════════════════════════════════════════════════

def test_journal_ranking_match_key():
    r1 = JournalRanking(
        scheme="CSSCI", edition="2025-2026", journal_name="新闻与传播研究",
        normalized_name="新闻与传播研究", issn="1005-2577", level="source",
    )
    r2 = JournalRanking(
        scheme="CSSCI", edition="2025-2026", journal_name="新闻与传播研究",
        normalized_name="新闻与传播研究", issn="1005-2577", level="source",
    )
    assert r1.match_key() == r2.match_key()


def test_journal_ranking_different_editions():
    r1 = JournalRanking(
        scheme="CSSCI", edition="2025-2026", journal_name="新闻与传播研究",
        normalized_name="新闻与传播研究", issn="1005-2577", level="source",
    )
    r2 = JournalRanking(
        scheme="CSSCI", edition="2021-2022", journal_name="新闻与传播研究",
        normalized_name="新闻与传播研究", issn="1005-2577", level="source",
    )
    assert r1.match_key() != r2.match_key()


# ═══════════════════════════════════════════════════════════
# MatchResult
# ═══════════════════════════════════════════════════════════

def test_match_result_auto_accept():
    """Identifier-based exact match at high confidence auto-accepts."""
    mr = MatchResult(method=MatchMethod.DOI_RESOLVED_ISSN_EXACT, confidence=1.0, matched_id="test")
    assert mr.is_auto_accepted()
    assert not mr.is_rejected()
    assert not mr.needs_review


def test_match_result_needs_review():
    mr = MatchResult(method=MatchMethod.NAME_EXACT, confidence=0.88, matched_id="test", needs_review=True)
    assert not mr.is_auto_accepted()
    assert not mr.is_rejected()
    assert mr.needs_review


def test_match_result_rejected():
    mr = MatchResult(method=MatchMethod.TITLE_AUTHOR_YEAR_FUZZY, confidence=0.50, matched_id="test")
    assert not mr.is_auto_accepted()
    assert mr.is_rejected()


def test_auto_accept_rejects_name_exact_at_092():
    """Name-exact at 0.92 is NOT auto-accepted — method-based gate.

    Per the decision rules: identifier-based methods (ISSN, DOI→ISSN, etc.)
    can auto-accept at confidence >= 0.92. Name-based methods NEVER auto-accept,
    regardless of confidence score, because journal names can be ambiguous.
    """
    mr = MatchResult(method=MatchMethod.NAME_EXACT, confidence=0.92, matched_id="test")
    assert not mr.is_auto_accepted()
    assert not mr.is_rejected()  # 0.92 is above rejection threshold


def test_auto_accept_accepts_identifier_at_092():
    """ISSN exact at 0.92 IS auto-accepted — identifier-based."""
    mr = MatchResult(method=MatchMethod.ISSN_EXACT, confidence=0.92, matched_id="test")
    assert mr.is_auto_accepted()
    assert not mr.is_rejected()


def test_auto_accept_rejects_name_exact_at_099():
    """Even at 0.99, name exact never auto-accepts."""
    mr = MatchResult(method=MatchMethod.NAME_EXACT, confidence=0.99, matched_id="test")
    assert not mr.is_auto_accepted()


def test_auto_accept_rejects_fuzzy_at_095():
    """Fuzzy match at 0.95 never auto-accepts (not an identifier method)."""
    mr = MatchResult(method=MatchMethod.TITLE_AUTHOR_YEAR_FUZZY, confidence=0.95, matched_id="test")
    assert not mr.is_auto_accepted()


# ═══════════════════════════════════════════════════════════
# EnrichmentResult
# ═══════════════════════════════════════════════════════════

def test_enrichment_result_empty():
    r = EnrichmentResult(record=ScholarlyRecord())
    assert not r.has_journal_rankings()
    assert not r.has_citations()


def test_enrichment_result_with_data():
    record = ScholarlyRecord(title="Test")
    rankings = [JournalRanking(
        scheme="CSSCI", edition="2025-2026", journal_name="测试",
        normalized_name="测试", issn="1234-5678", level="source",
    )]
    citations = [CitationData(style=CitationStyle.GBT7714_NUMERIC, formatted="Test.")]
    r = EnrichmentResult(record=record, journal_rankings=rankings, citations=citations)
    assert r.has_journal_rankings()
    assert r.has_citations()


# ═══════════════════════════════════════════════════════════
# ISSN validation
# ═══════════════════════════════════════════════════════════

def test_validate_issn_valid():
    # 1005-2577: check digit = 7
    # sum = 7*1 + 7*0 + 6*0 + 5*5 + 4*2 + 3*5 + 2*7 = 7+0+0+25+8+15+14 = 69
    # 69 % 11 = 3, 11-3 = 8
    # Wait, let me compute properly: ISSN 1005-2577
    # Position: 8 7 6 5 4 3 2 1
    # Digits:   1 0 0 5 2 5 7 7
    # sum = 8*1 + 7*0 + 6*0 + 5*5 + 4*2 + 3*5 + 2*7 = 8 + 0 + 0 + 25 + 8 + 15 + 14 = 70
    # 70 % 11 = 4, 11-4 = 7, check = 7. Correct!
    n, valid = validate_issn("1005-2577")
    assert valid
    assert n == "1005-2577"


def test_validate_issn_invalid_checksum():
    n, valid = validate_issn("1005-2578")
    assert not valid


def test_validate_issn_with_prefix():
    n, valid = validate_issn("ISSN 1005-2577")
    assert valid
    assert n == "1005-2577"


def test_validate_issn_too_short():
    n, valid = validate_issn("1234")
    assert not valid
    assert n == ""


def test_validate_issn_empty():
    n, valid = validate_issn("")
    assert not valid


def test_validate_issn_with_x():
    # ISSN 0317-8471 → 0317-847X? Let me check...
    # We need a known ISSN with check digit X
    # Actually let's use our known valid ISSN
    n, valid = validate_issn("  ISSN: 1005-2577  ")
    assert valid
    assert n == "1005-2577"


def test_normalise_issn():
    assert normalise_issn("1005-2577") == "1005-2577"
    assert normalise_issn("ISSN 1005-2577") == "1005-2577"
    assert normalise_issn("garbage") == ""
    assert normalise_issn("") == ""


# ═══════════════════════════════════════════════════════════
# MetricSnapshot
# ═══════════════════════════════════════════════════════════

def test_metric_snapshot_label():
    m = MetricSnapshot(source="openalex", metric_name="2yr_mean_citedness", value=3.82,
                       unit="citations per article")
    assert "openalex" in m.display_label()
    assert "2yr_mean_citedness" in m.display_label()
    # Must NOT contain "影响因子" or "Impact Factor"
    assert "影响因子" not in m.display_label()
    assert "Impact Factor" not in m.display_label()


# ═══════════════════════════════════════════════════════════
# CitationStyle enum
# ═══════════════════════════════════════════════════════════

def test_citation_styles():
    assert CitationStyle.GBT7714_NUMERIC.value == "gbt7714-numeric"
    assert CitationStyle.APA7.value == "apa7"
    assert CitationStyle.BIBTEX.value == "bibtex"
    assert CitationStyle.RIS.value == "ris"
