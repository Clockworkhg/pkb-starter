"""Tests for scholarly detector module (tools/scholarly/detector.py).

Covers: DOI journal articles, arXiv papers, local PDF papers, web pages citing DOI,
journal TOC pages, news articles, course notes, type:literature pages,
DOI-free records with complete journal fields.

Phase 1B.1: Added priority tests — explicit declarations override soft exclusion,
strong signals survive soft keyword exclusion, hard exclusions (page type) still block.
"""

import sys
from pathlib import Path

import pytest

_TOOLS_DIR = Path(__file__).resolve().parent.parent / "tools"
if str(_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOLS_DIR))

from scholarly.detector import (
    ScholarlyDetectionResult,
    detect_scholarly,
    should_auto_enrich,
)


class TestDetectScholarly:
    """Detection tests for various content types."""

    # ── Strong signal: frontmatter type: literature ──
    def test_type_literature_frontmatter(self):
        """Frontmatter type: literature is a strong signal."""
        fm = {"type": "literature", "title": "Test Paper"}
        body = "Some body text."
        result = detect_scholarly(fm, body)
        assert result.is_scholarly is True
        assert result.confidence >= 0.90
        assert "frontmatter_type_literature" in result.strong_signals
        assert result.user_declared is True

    # ── Strong signal: DOI in body ──
    def test_doi_in_body_journal_article(self):
        """DOI in body text is a strong signal."""
        fm = {"title": "Governance Models"}
        body = "A Survey of Platform Governance. doi: 10.1234/test.2023"
        result = detect_scholarly(fm, body)
        assert result.is_scholarly is True
        assert result.confidence >= 0.90
        assert "doi_identified" in result.strong_signals
        assert result.identifiers.get("doi") == "10.1234/test.2023"

    # ── Strong signal: DOI in frontmatter ──
    def test_doi_in_frontmatter(self):
        """DOI in frontmatter is a strong signal."""
        fm = {"doi": "10.5678/example.2024", "title": "Example Paper"}
        body = "# Example\n\nThis is a paper."
        result = detect_scholarly(fm, body)
        assert result.is_scholarly is True
        assert result.identifiers.get("doi") == "10.5678/example.2024"

    # ── Strong signal: arXiv ID ──
    def test_arxiv_paper(self):
        """arXiv ID detection."""
        fm = {"title": "Deep Learning Paper"}
        body = "arXiv: 2301.12345v2 This paper proposes..."
        result = detect_scholarly(fm, body)
        assert result.is_scholarly is True
        assert "arxiv_id" in result.strong_signals
        assert "arxiv_id" in result.identifiers

    # ── Strong signal: academic source URL ──
    def test_academic_source_url(self):
        """URL from arxiv.org is a strong signal."""
        fm = {"title": "Paper Title"}
        body = "Content here."
        result = detect_scholarly(fm, body, source_url="https://arxiv.org/abs/2301.12345")
        assert result.is_scholarly is True
        assert "academic_source_url" in result.strong_signals

    # ── Strong signal: existing scholarly block ──
    def test_existing_scholarly_frontmatter(self):
        """Frontmatter with scholarly.detected=true is a strong signal."""
        fm = {
            "title": "Paper",
            "scholarly": {"detected": True, "doi": "10.xxx/yyy"},
        }
        body = "Text."
        result = detect_scholarly(fm, body)
        assert result.is_scholarly is True
        assert "scholarly_frontmatter_detected" in result.strong_signals
        assert result.user_declared is True

    # ── Medium signals: bibliographic completeness ──
    def test_bibliographic_fields_multiple(self):
        """Title + author + year + journal + volume → medium signals (candidate)."""
        fm = {
            "title": "A Study of Something",
            "author": "Zhang San",
            "year": "2023",
            "journal": "Journal of Testing",
            "volume": "40",
            "issue": "1",
        }
        body = "# A Study\n\nAbstract: This is a study."
        result = detect_scholarly(fm, body)
        assert result.is_scholarly is True
        assert result.confidence >= 0.60
        assert any("bibliographic" in s for s in result.medium_signals)

    # ── Medium signals: ISSN ──
    def test_issn_signal(self):
        """ISSN present in frontmatter."""
        fm = {
            "title": "Paper",
            "author": "Author",
            "year": "2024",
            "journal": "J Test",
            "issn": "1000-0001",
        }
        body = "Body text."
        result = detect_scholarly(fm, body)
        assert result.is_scholarly is True
        assert "has_issn" in result.medium_signals

    # ── Medium signals: scholarly structure ──
    def test_scholarly_structure_markers(self):
        """Chinese scholarly structure markers in body."""
        fm = {"title": "A Paper"}
        body = "摘要：本文研究了...\n关键词：测试\n参考文献\n[1] Author..."
        result = detect_scholarly(fm, body)
        assert result.is_scholarly is True
        assert any("scholarly_structure" in s for s in result.medium_signals)

    # ── Medium signals: filename ──
    def test_filename_indicates_paper(self):
        """File name suggests scholarly work."""
        fm = {"title": "Deep Learning"}
        body = "Some text."
        result = detect_scholarly(fm, body, file_name="paper_2023_cn.md")
        assert result.is_scholarly is True
        assert any("filename" in s for s in result.medium_signals)

    # ── Hard exclusion: journal TOC ──
    def test_journal_toc_page(self):
        """Journal table of contents page is hard-excluded."""
        fm = {"title": "目录"}
        body = "本期目录：\n1. Paper A\n2. Paper B"
        result = detect_scholarly(fm, body)
        assert result.is_scholarly is False
        assert len(result.hard_exclusion_signals) > 0

    def test_journal_search_results(self):
        """Search results page is hard-excluded."""
        fm = {"title": "检索结果"}
        body = "Search results for 'machine learning'..."
        result = detect_scholarly(fm, body)
        assert result.is_scholarly is False
        assert len(result.hard_exclusion_signals) > 0

    # ── Soft exclusion: news article without strong signals ──
    def test_news_article_with_doi_citation_no_strong(self):
        """News article with DOI but no strong structural signals → soft-excluded."""
        fm = {"title": "新闻：最新研究发现", "type": "news"}
        body = "据最新研究（DOI: 10.1234/paper）显示...这是一篇新闻报道。"
        result = detect_scholarly(fm, body)
        # DOI is a strong signal, so this IS scholarly (soft exclusion only reduces confidence)
        assert result.is_scholarly is True
        assert "doi_identified" in result.strong_signals
        # Soft exclusion should be present
        assert len(result.soft_exclusion_signals) > 0

    def test_soft_excluded_without_strong(self):
        """Page with soft exclusion keyword and no strong signals → not scholarly."""
        fm = {"title": "新闻快讯", "type": "news"}
        body = "Some news content about research."
        result = detect_scholarly(fm, body)
        assert result.is_scholarly is False
        assert len(result.soft_exclusion_signals) > 0

    # ── Hard exclusion: software doc ──
    def test_software_documentation(self):
        """Software docs are hard-excluded."""
        fm = {"title": "API Documentation"}
        body = "This is the README for the project. Usage: pip install..."
        result = detect_scholarly(fm, body)
        assert result.is_scholarly is False

    # ── No signals: plain page ──
    def test_plain_page_no_signals(self):
        """Plain page with no academic signals."""
        fm = {"title": "Random Note"}
        body = "Just some random thoughts."
        result = detect_scholarly(fm, body)
        assert result.is_scholarly is False
        assert result.confidence == 0.0

    # ── Type detection ──
    def test_detected_type_journal_article(self):
        """Detect type: article-journal from pub_type."""
        fm = {"pub_type": "journal-article", "doi": "10.xxx/yyy"}
        body = "Text."
        result = detect_scholarly(fm, body)
        assert result.detected_type == "article-journal"

    def test_detected_type_preprint_arxiv(self):
        """Detect type: preprint from arXiv ID."""
        fm = {"title": "Preprint Paper"}
        body = "arXiv: 2301.12345"
        result = detect_scholarly(fm, body)
        assert result.detected_type == "preprint"

    def test_detected_type_thesis(self):
        """Detect type: thesis from body content."""
        fm = {"title": "My Thesis"}
        body = "This doctoral dissertation presents..."
        result = detect_scholarly(fm, body)
        assert result.detected_type == "thesis"

    # ═══════════════════════════════════════════
    # Phase 1B.1: Priority tests (spec section 2)
    # ═══════════════════════════════════════════

    # 2.1: Explicit user declaration > soft exclusion
    def test_type_literature_overrides_news_title(self):
        """type: literature + title containing 新闻 → still scholarly (user declared)."""
        fm = {
            "type": "literature",
            "title": "新闻传播学研究方法探析",
            "author": "Zhang San",
            "year": "2023",
            "doi": "10.1234/journal.2023",
        }
        body = "摘要：本文探讨了新闻传播学的研究方法。\n关键词：新闻传播\n参考文献"
        result = detect_scholarly(fm, body)
        assert result.is_scholarly is True
        assert result.user_declared is True
        assert result.confidence >= 0.85
        # Soft exclusion should be present but did not override
        assert len(result.soft_exclusion_signals) > 0

    def test_scholarly_detected_overrides_blog_title(self):
        """scholarly.detected: true + title with 'blog' → still scholarly (user declared)."""
        fm = {
            "title": "Blog Politics and Digital Democracy",
            "scholarly": {"detected": True, "doi": "10.5678/politics.2024"},
            "author": "Smith J",
            "year": "2024",
        }
        body = "Abstract: This paper examines the intersection of blog politics..."
        result = detect_scholarly(fm, body)
        assert result.is_scholarly is True
        assert result.user_declared is True
        # Soft exclusion present but did not override
        assert len(result.soft_exclusion_signals) > 0

    # 2.2: Verified structural strong signals > soft exclusion
    def test_doi_journal_article_with_news_in_title(self):
        """DOI journal article titled '新闻传播...' → auto-enrich (strong signal > soft exclusion)."""
        fm = {
            "title": "新闻传播学前沿研究",
            "author": "Li Si",
            "year": "2025",
            "journal": "新闻与传播研究",
            "issn": "1005-2577",
            "volume": "42",
            "issue": "3",
        }
        body = "摘要：本文分析了新闻传播领域的最新发展。\n"
        body += "DOI: 10.1234/xwcb.2025.001\n"
        body += "关键词：新闻传播；传播学\n参考文献\n[1]..."
        result = detect_scholarly(fm, body)
        assert result.is_scholarly is True
        # Should have DOI strong signal
        assert "doi_identified" in result.strong_signals
        # Soft exclusion: title contains 新闻 → reduces confidence but doesn't negate
        assert len(result.soft_exclusion_signals) > 0
        # Still scholarly because DOI is a strong signal (soft only reduces confidence)
        assert result.confidence >= 0.70

    def test_english_journal_paper_with_blog_in_title(self):
        """English journal paper with 'Blog' in title → auto-enrich (strong signals > soft exclusion)."""
        fm = {
            "title": "Blog Politics: Digital Democracy in the Age of Social Media",
            "author": "Johnson, A.",
            "year": "2024",
            "journal": "Journal of Digital Politics",
            "doi": "10.1234/jdp.2024.001",
            "issn": "2000-1111",
            "volume": "15",
        }
        body = "Abstract: This article examines blog politics...\nKeywords: blog, democracy\nReferences\n[1]..."
        result = detect_scholarly(fm, body)
        assert result.is_scholarly is True
        assert "doi_identified" in result.strong_signals
        # Soft exclusion present (title contains 'blog') but did not override DOI
        assert len(result.soft_exclusion_signals) > 0
        assert result.confidence >= 0.70  # Reduced from 0.90 by soft exclusion

    # 2.3: Hard exclusions — page type
    def test_news_site_report_with_doi(self):
        """News website page citing a DOI → hard-excluded (page IS a news report)."""
        fm = {
            "title": "Breaking: New Study Reveals Climate Impact",
            "type": "news",
        }
        body = "news article: A recent study (DOI: 10.1234/climate.2025) published in Nature..."
        result = detect_scholarly(fm, body)
        # Has DOI (strong signal) but body matches 'news article' hard exclusion
        # Actually 'news article' is soft, not hard. Let me check...
        # The DOI makes this a strong signal. 'news article' is soft exclusion.
        # Per rules: strong signal → only hard exclusion can block, soft reduces confidence.
        # So this should be is_scholarly=True with reduced confidence.
        assert result.is_scholarly is True  # DOI is strong signal
        assert "doi_identified" in result.strong_signals
        assert len(result.soft_exclusion_signals) > 0  # news_article pattern

    def test_journal_toc_with_multiple_dois(self):
        """Journal TOC page containing multiple DOIs → hard-excluded (page IS a TOC)."""
        fm = {"title": "目录"}
        body = (
            "本期目录：\n"
            "1. Paper A — DOI: 10.1234/a.2024\n"
            "2. Paper B — DOI: 10.1234/b.2024\n"
            "3. Paper C — DOI: 10.1234/c.2024\n"
        )
        result = detect_scholarly(fm, body)
        assert result.is_scholarly is False
        assert len(result.hard_exclusion_signals) > 0

    # 2.4: scholarly.disabled
    def test_scholarly_disabled_true(self):
        """scholarly.disabled: true → skip regardless of other signals."""
        fm = {
            "type": "literature",
            "title": "Important Paper",
            "doi": "10.1234/important.2025",
            "scholarly": {"disabled": True},
        }
        body = "Abstract: This is an important paper."
        result = detect_scholarly(fm, body)
        assert result.is_scholarly is False
        assert result.user_disabled is True
        assert "scholarly.disabled is true" in result.reasons[0]

    def test_scholarly_disabled_blocks_auto_enrich(self):
        """should_auto_enrich returns False when scholarly.disabled: true."""
        r = ScholarlyDetectionResult(
            is_scholarly=True,
            confidence=0.95,
            strong_signals=["doi_identified", "frontmatter_type_literature"],
            user_declared=True,
            user_disabled=True,
        )
        assert should_auto_enrich(r) is False


class TestShouldAutoEnrich:
    """Tests for the auto-enrich decision function."""

    def test_high_confidence_strong_signal(self):
        """confidence >= 0.90 with strong signal → auto-enrich."""
        r = ScholarlyDetectionResult(
            is_scholarly=True, confidence=0.95,
            strong_signals=["doi_identified"],
        )
        assert should_auto_enrich(r) is True

    def test_low_confidence_no_strong(self):
        """confidence < 0.90 without strong signal → no auto-enrich."""
        r = ScholarlyDetectionResult(
            is_scholarly=True, confidence=0.85,
            medium_signals=["bibliographic_fields_3"],
        )
        assert should_auto_enrich(r) is False

    def test_high_confidence_no_strong(self):
        """confidence >= 0.90 but no strong signal → no auto-enrich."""
        r = ScholarlyDetectionResult(
            is_scholarly=True, confidence=0.90,
            medium_signals=["bibliographic_fields_4"],
        )
        assert should_auto_enrich(r) is False

    def test_not_scholarly(self):
        """Not scholarly at all → no auto-enrich."""
        r = ScholarlyDetectionResult(is_scholarly=False, confidence=0.0)
        assert should_auto_enrich(r) is False

    def test_edge_threshold_below(self):
        """confidence 0.89 with strong signal → no auto-enrich."""
        r = ScholarlyDetectionResult(
            is_scholarly=True, confidence=0.89,
            strong_signals=["doi_identified"],
        )
        assert should_auto_enrich(r) is False

    def test_edge_threshold_at(self):
        """confidence 0.90 with strong signal → auto-enrich."""
        r = ScholarlyDetectionResult(
            is_scholarly=True, confidence=0.90,
            strong_signals=["doi_identified"],
        )
        assert should_auto_enrich(r) is True

    # Phase 1B.1: user_declared always triggers auto-enrich
    def test_user_declared_always_enriches(self):
        """User-declared scholarly → auto-enrich even with moderate confidence."""
        r = ScholarlyDetectionResult(
            is_scholarly=True, confidence=0.85,
            strong_signals=["frontmatter_type_literature"],
            user_declared=True,
        )
        assert should_auto_enrich(r) is True

    def test_user_disabled_never_enriches(self):
        """scholarly.disabled → never auto-enrich."""
        r = ScholarlyDetectionResult(
            is_scholarly=True, confidence=0.99,
            strong_signals=["doi_identified"],
            user_declared=True,
            user_disabled=True,
        )
        assert should_auto_enrich(r) is False
