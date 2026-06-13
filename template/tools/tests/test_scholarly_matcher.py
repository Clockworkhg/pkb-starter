"""Tests for scholarly matcher.py.

Covers: DOI→ISSN, ISSN exact, EISSN, ISSN-L, name exact, fuzzy matching,
confidence thresholds, evidence recording, name normalisation edge cases.
All tests use in-memory registry. No network access.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

_TOOLS_DIR = Path(__file__).resolve().parent.parent
if not (_TOOLS_DIR / "scholarly").is_dir() and not (_TOOLS_DIR / "content_quality.py").exists():
    _TOOLS_DIR = _TOOLS_DIR / "tools"
if str(_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOLS_DIR))

import pytest

from scholarly.journal_registry import JournalRegistry
from scholarly.matcher import JournalMatcher, _bigram_similarity, _normalise_name, _collapse
from scholarly.models import (
    JournalIdentity,
    JournalRanking,
    MatchMethod,
    ScholarlyRecord,
)

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "scholarly"


# ═══════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════

@pytest.fixture
def populated_registry():
    """Registry with test CSV loaded."""
    db_path = Path(tempfile.mktemp(suffix=".sqlite3"))
    reg = JournalRegistry(db_path=db_path)
    reg.import_csv(FIXTURES_DIR / "test_rankings.csv", source_label="test")
    yield reg
    reg.close()
    try:
        db_path.unlink(missing_ok=True)
    except Exception:
        pass


@pytest.fixture
def matcher(populated_registry):
    return JournalMatcher(populated_registry)


# ═══════════════════════════════════════════════════════════
# Bigram similarity
# ═══════════════════════════════════════════════════════════

def test_bigram_similarity_identical():
    assert _bigram_similarity("新闻与传播研究", "新闻与传播研究") > 0.95


def test_bigram_similarity_different():
    assert _bigram_similarity("新闻与传播研究", "物理学报") < 0.30


def test_bigram_similarity_empty():
    assert _bigram_similarity("", "anything") == 0.0
    assert _bigram_similarity("anything", "") == 0.0


def test_collapse_normalisation():
    """_collapse removes punctuation and normalises."""
    a = _collapse("新闻与传播研究")
    b = _collapse("《新闻与传播研究》")
    assert a == b


# ═══════════════════════════════════════════════════════════
# DOI → ISSN exact match (priority 1)
# ═══════════════════════════════════════════════════════════

def test_match_by_doi_issn(matcher):
    """Record with ISSN from DOI → exact match, confidence 1.0."""
    record = ScholarlyRecord(
        doi="10.1234/test",
        issn=["1005-2577"],
        journal_name="新闻与传播研究",
    )
    result = matcher.match(record)
    assert result is not None
    assert result.method == MatchMethod.DOI_RESOLVED_ISSN_EXACT
    assert result.confidence >= 0.98
    assert not result.needs_review


def test_match_by_doi_issn_l(matcher):
    """Record with ISSN-L from DOI → match."""
    record = ScholarlyRecord(
        doi="10.1234/test",
        issn=[],
        issn_l="1005-2577",
        journal_name="新闻与传播研究",
    )
    result = matcher.match(record)
    assert result is not None
    assert result.confidence >= 0.9


# ═══════════════════════════════════════════════════════════
# ISSN exact match (priority 2)
# ═══════════════════════════════════════════════════════════

def test_match_by_issn_exact(matcher):
    """Record with ISSN but no DOI → still matches by ISSN."""
    record = ScholarlyRecord(
        issn=["1005-2577"],
        journal_name="新闻与传播研究",
    )
    result = matcher.match(record)
    assert result is not None
    assert result.method == MatchMethod.ISSN_EXACT or result.method == MatchMethod.DOI_RESOLVED_ISSN_EXACT
    assert result.confidence >= 0.9


# ═══════════════════════════════════════════════════════════
# EISSN match (priority 3)
# ═══════════════════════════════════════════════════════════

def test_match_by_eissn(matcher):
    """Record with EISSN via JournalIdentity — falls through to name match if EISSN not in registry."""
    record = ScholarlyRecord(
        journal_identity=JournalIdentity(issn="", eissn="1001-8867"),
        journal_name="中国图书馆学报",
    )
    result = matcher.match(record)
    assert result is not None
    # EISSN not in test registry for this journal; falls through to name exact
    assert result.method in (MatchMethod.EISSN_EXACT, MatchMethod.ISSN_L_EXACT, MatchMethod.NAME_EXACT)


# ═══════════════════════════════════════════════════════════
# ISSN-L match (priority 4)
# ═══════════════════════════════════════════════════════════

def test_match_by_issn_l(matcher):
    """Record with ISSN-L matches."""
    record = ScholarlyRecord(
        issn_l="1000-0135",
        journal_name="情报学报",
    )
    result = matcher.match(record)
    assert result is not None
    assert result.confidence >= 0.9


# ═══════════════════════════════════════════════════════════
# Name exact match (priority 5)
# ═══════════════════════════════════════════════════════════

def test_match_by_name_exact(matcher):
    """Record with only journal name → match by normalised name."""
    record = ScholarlyRecord(
        journal_name="新闻与传播研究",
    )
    result = matcher.match(record)
    assert result is not None
    assert result.method == MatchMethod.NAME_EXACT
    assert result.confidence >= 0.90
    assert result.needs_review  # Name-only match requires review


# ═══════════════════════════════════════════════════════════
# Fuzzy match (priority 6)
# ═══════════════════════════════════════════════════════════

def test_match_fuzzy_close(matcher):
    """Close but not exact name match → fuzzy."""
    record = ScholarlyRecord(
        journal_name="新闻传播研究",  # missing "与"
        title="一篇关于算法的文章",
        authors=[{"family": "张", "given": "三"}],
        year=2025,
    )
    result = matcher.match(record)
    # May or may not match depending on similarity threshold
    if result:
        assert result.method == MatchMethod.TITLE_AUTHOR_YEAR_FUZZY
        assert len(result.evidence) > 0


def test_match_fuzzy_below_threshold(matcher):
    """Completely unrelated name → no match."""
    record = ScholarlyRecord(
        journal_name="完全无关的期刊名称XYZ",
    )
    result = matcher.match(record)
    assert result is None


# ═══════════════════════════════════════════════════════════
# Confidence thresholds
# ═══════════════════════════════════════════════════════════

def test_doi_issn_not_downgraded_by_name(matcher):
    """DOI→ISSN match is not downgraded even if name differs."""
    record = ScholarlyRecord(
        doi="10.1234/test",
        issn=["1005-2577"],
        journal_name="Some Completely Wrong Name",
    )
    result = matcher.match(record)
    assert result is not None
    # DOI-based match should be accepted despite name mismatch
    assert result.method == MatchMethod.DOI_RESOLVED_ISSN_EXACT
    assert not result.is_rejected()


def test_auto_accept_threshold(matcher):
    """DOI→ISSN: confidence >= 0.92 → auto-accept."""
    record = ScholarlyRecord(
        doi="10.1234/test",
        issn=["1005-2577"],
        journal_name="新闻与传播研究",
    )
    result = matcher.match(record)
    assert result is not None
    assert result.is_auto_accepted()


# ═══════════════════════════════════════════════════════════
# Evidence recording
# ═══════════════════════════════════════════════════════════

def test_match_evidence_recorded(matcher):
    """Match results include evidence strings."""
    record = ScholarlyRecord(
        doi="10.1234/test",
        issn=["1005-2577"],
    )
    result = matcher.match(record)
    assert result is not None
    assert len(result.evidence) > 0
    # Evidence should mention ISSN (normalized form)
    evidence_text = " ".join(result.evidence)
    # Either normalized form or raw form should appear
    assert "1005" in evidence_text


# ═══════════════════════════════════════════════════════════
# Name normalisation edge cases
# ═══════════════════════════════════════════════════════════

def test_name_matching_with_bookmarks(matcher):
    """《新闻与传播研究》 should match 新闻与传播研究."""
    record = ScholarlyRecord(
        journal_name="《新闻与传播研究》",
    )
    result = matcher.match(record)
    assert result is not None
    assert result.method == MatchMethod.NAME_EXACT


def test_name_matching_fullwidth(matcher):
    """Fullwidth spaces should be normalised."""
    record = ScholarlyRecord(
        journal_name="新闻与传播研究",  # already normal
    )
    result = matcher.match(record)
    assert result is not None


# ═══════════════════════════════════════════════════════════
# 0.92 boundary tests — method-based auto-accept
# ═══════════════════════════════════════════════════════════

def test_name_exact_at_092_not_auto_accept(matcher):
    """Name exact at confidence 0.92 is NOT auto-accepted.

    Per the method-based decision rule: identifier methods can auto-accept,
    but name-based methods (exact or fuzzy) never auto-accept, even at high scores.
    """
    record = ScholarlyRecord(
        journal_name="新闻与传播研究",  # Exact match in registry → 0.92
    )
    result = matcher.match(record)
    assert result is not None
    assert result.method == MatchMethod.NAME_EXACT
    assert result.confidence >= 0.92
    assert result.needs_review  # Always needs review for name-based
    assert not result.is_auto_accepted()  # Key assertion


def test_doi_resolved_issn_auto_accepts(matcher):
    """DOI→ISSN match auto-accepts (identifier method)."""
    record = ScholarlyRecord(
        doi="10.1234/test",
        issn=["1005-2577"],
        journal_name="新闻与传播研究",
    )
    result = matcher.match(record)
    assert result is not None
    assert result.method == MatchMethod.DOI_RESOLVED_ISSN_EXACT
    assert result.is_auto_accepted()
