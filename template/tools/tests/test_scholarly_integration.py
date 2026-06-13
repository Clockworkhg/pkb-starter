"""Tests for scholarly integration layer (tools/scholarly/integration.py).

Tests: frontmatter parsing/serialization, idempotency, locked page detection,
ScholarlyIntegrationConfig defaults, atomic write safety, fail-open behavior.
Mock network — no real API calls.
"""

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

_TOOLS_DIR = Path(__file__).resolve().parent.parent / "tools"
if str(_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOLS_DIR))

from scholarly.integration import (
    ScholarlyIntegrationConfig,
    ScholarlyIntegrationResult,
    parse_frontmatter,
    _serialise_simple_yaml,
    _is_idempotent,
    _is_locked,
    _build_scholarly_frontmatter,
    enrich_wiki_page_if_scholarly,
    scholarly_report_summary,
)
from scholarly.models import (
    CitationData,
    CitationStyle,
    EnrichmentResult,
    ScholarlyRecord,
    SourceStatus,
)
from scholarly.detector import ScholarlyDetectionResult


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def _make_page(content: str) -> Path:
    """Write a temp Markdown page and return its path."""
    tmp = tempfile.NamedTemporaryFile(
        mode='w', suffix='.md', delete=False, encoding='utf-8'
    )
    tmp.write(content)
    tmp.close()
    return Path(tmp.name)


# ─────────────────────────────────────────────
# Config tests
# ─────────────────────────────────────────────

class TestScholarlyIntegrationConfig:

    def test_defaults(self):
        """Default config has safe values."""
        c = ScholarlyIntegrationConfig()
        assert c.enabled is True
        assert c.auto_enrich_on_pkb is True
        assert c.detection_threshold == 0.90
        assert c.citation_engine == "auto"
        assert c.fail_open is True

    def test_from_empty_dict(self):
        """Empty dict → defaults."""
        c = ScholarlyIntegrationConfig.from_config_dict({})
        assert c.enabled is True

    def test_from_none(self):
        """None → defaults."""
        c = ScholarlyIntegrationConfig.from_config_dict(None)
        assert c.enabled is True

    def test_from_config_dict_overrides(self):
        """Known keys are overridden."""
        c = ScholarlyIntegrationConfig.from_config_dict({
            "enabled": False,
            "detection_threshold": 0.85,
            "citation_engine": "citeproc",
        })
        assert c.enabled is False
        assert c.detection_threshold == 0.85
        assert c.citation_engine == "citeproc"

    def test_unknown_keys_ignored(self):
        """Unknown keys don't cause errors."""
        c = ScholarlyIntegrationConfig.from_config_dict({
            "unknown_field": "value",
            "another": 123,
        })
        assert c.enabled is True  # default preserved

    def test_api_key_not_in_config(self):
        """API keys are NOT stored in config."""
        c = ScholarlyIntegrationConfig()
        assert not hasattr(c, "openalex_api_key")


# ─────────────────────────────────────────────
# Frontmatter parsing tests
# ─────────────────────────────────────────────

class TestFrontmatterParsing:

    def test_parse_simple(self):
        fm, body, raw = parse_frontmatter("---\ntitle: Test\ntags: [a, b]\n---\n\nBody text.")
        assert fm["title"] == "Test"
        assert fm["tags"] == ["a", "b"]
        assert body == "Body text."

    def test_parse_no_frontmatter(self):
        fm, body, raw = parse_frontmatter("Just body text.")
        assert fm == {}
        assert body == "Just body text."

    def test_parse_nested_dict(self):
        content = "---\nscholarly:\n  detected: true\n  doi: 10.xxx/yyy\n---\n\nBody."
        fm, body, raw = parse_frontmatter(content)
        assert isinstance(fm["scholarly"], dict)
        assert fm["scholarly"]["detected"] == "true"
        assert fm["scholarly"]["doi"] == "10.xxx/yyy"

    def test_serialise_nested(self):
        fm = {
            "title": "Test",
            "scholarly": {
                "detected": "true",
                "doi": "10.xxx/yyy",
            },
        }
        yaml_str = _serialise_simple_yaml(fm)
        assert "scholarly:" in yaml_str
        assert "  detected: true" in yaml_str
        assert "  doi: 10.xxx/yyy" in yaml_str

    def test_roundtrip_simple(self):
        original = "---\ntitle: Test Paper\ntags: [a, b]\n---\n\nBody."
        fm, body, raw = parse_frontmatter(original)
        yaml_str = _serialise_simple_yaml(fm)
        reconstructed = f"---\n{yaml_str}\n---\n\n{body}"
        fm2, body2, raw2 = parse_frontmatter(reconstructed)
        assert fm2.get("title") == "Test Paper"
        assert body2 == "Body."

    def test_serialise_boolean(self):
        fm = {"needs_review": True}
        yaml_str = _serialise_simple_yaml(fm)
        assert "needs_review: true" in yaml_str


# ─────────────────────────────────────────────
# Locked page detection
# ─────────────────────────────────────────────

class TestLockedDetection:

    def test_locked_true(self):
        fm = {"scholarly": {"locked": True, "doi": "10.xxx/yyy"}}
        assert _is_locked(fm) is True

    def test_locked_false(self):
        fm = {"scholarly": {"locked": False, "doi": "10.xxx/yyy"}}
        assert _is_locked(fm) is False

    def test_locked_not_set(self):
        fm = {"scholarly": {"doi": "10.xxx/yyy"}}
        assert _is_locked(fm) is False

    def test_no_scholarly_block(self):
        fm = {"title": "Test"}
        assert _is_locked(fm) is False


# ─────────────────────────────────────────────
# Idempotency tests
# ─────────────────────────────────────────────

class TestIdempotency:

    def test_identical_fm_no_change(self):
        fm = {"scholarly": {"detected": True, "doi": "10.xxx/yyy"}}
        new_data = {"scholarly": {"detected": True, "doi": "10.xxx/yyy"}}
        assert _is_idempotent(fm, new_data) is True

    def test_different_fm_needs_change(self):
        fm = {"scholarly": {"detected": True}}
        new_data = {"scholarly": {"detected": True, "doi": "10.xxx/new"}}
        assert _is_idempotent(fm, new_data) is False

    def test_new_fields_needs_change(self):
        fm = {}
        new_data = {"scholarly": {"detected": True}}
        assert _is_idempotent(fm, new_data) is False


# ─────────────────────────────────────────────
# Integration result tests
# ─────────────────────────────────────────────

class TestScholarlyIntegrationResult:

    def test_default_result(self):
        r = ScholarlyIntegrationResult()
        assert r.detected is False
        assert r.attempted is False
        assert r.changed is False
        assert r.locked is False

    def test_locked_skip(self):
        r = ScholarlyIntegrationResult(locked=True,
                                        skipped_reason="scholarly.locked is true")
        assert r.locked is True
        assert r.attempted is False


# ─────────────────────────────────────────────
# Report summary tests
# ─────────────────────────────────────────────

class TestReportSummary:

    def test_not_detected_empty(self):
        r = ScholarlyIntegrationResult(detected=False)
        assert scholarly_report_summary(r) == ""

    def test_detected_no_enrichment(self):
        r = ScholarlyIntegrationResult(
            detected=True,
            detection_result=ScholarlyDetectionResult(
                is_scholarly=True, confidence=0.95,
                identifiers={"doi": "10.xxx/test"},
                strong_signals=["doi_identified"],
            ),
            skipped_reason="no DOI available for enrichment",
        )
        summary = scholarly_report_summary(r)
        assert "10.xxx/test" in summary

    def test_enriched_with_journal(self):
        r = ScholarlyIntegrationResult(
            detected=True,
            attempted=True,
            changed=True,
            detection_result=ScholarlyDetectionResult(
                is_scholarly=True, confidence=0.95,
                identifiers={"doi": "10.xxx/test"},
                strong_signals=["doi_identified"],
            ),
            enrichment_result=EnrichmentResult(
                record=ScholarlyRecord(
                    doi="10.xxx/test",
                    journal_name="Journal of Testing",
                    crossref_status=SourceStatus.AVAILABLE,
                ),
            ),
        )
        summary = scholarly_report_summary(r)
        assert "10.xxx/test" in summary
        assert "Journal of Testing" in summary

    def test_locked_page_summary(self):
        r = ScholarlyIntegrationResult(
            detected=True, locked=True,
            skipped_reason="scholarly.locked is true",
        )
        summary = scholarly_report_summary(r)
        assert "Locked by user" in summary


# ─────────────────────────────────────────────
# enrich_wiki_page_if_scholarly integration tests
# ─────────────────────────────────────────────

class TestEnrichWikiPage:

    def test_disabled_config(self):
        """When scholarly.enabled=False, skip immediately."""
        page = _make_page("---\ntitle: Test\ndoi: 10.xxx/test\n---\n\nBody.")
        try:
            config = ScholarlyIntegrationConfig(enabled=False)
            result = enrich_wiki_page_if_scholarly(page, config=config)
            assert result.detected is False
            assert result.skipped_reason == "scholarly disabled in config"
        finally:
            os.unlink(page)

    def test_locked_page_skip(self):
        """Locked pages are skipped."""
        page = _make_page(
            "---\ntitle: Test\ndoi: 10.xxx/test\nscholarly:\n  locked: true\n---\n\nBody."
        )
        try:
            result = enrich_wiki_page_if_scholarly(page)
            assert result.locked is True
            assert result.skipped_reason == "scholarly.locked is true"
            assert result.attempted is False
        finally:
            os.unlink(page)

    def test_non_scholarly_page_skip(self):
        """Non-scholarly page is detected and skipped."""
        page = _make_page("---\ntitle: Random Note\n---\n\nSome random thoughts.")
        try:
            result = enrich_wiki_page_if_scholarly(page)
            assert result.detected is False
            assert "not scholarly" in result.skipped_reason
        finally:
            os.unlink(page)

    def test_no_doi_skip(self):
        """Page without DOI cannot be enriched."""
        page = _make_page(
            "---\ntitle: A Study\nauthor: Zhang San\nyear: 2023\n"
            "journal: J Testing\nissn: 1000-0001\ntype: literature\n---\n\n"
            "摘要：本文研究了...\n关键词：测试\n参考文献"
        )
        try:
            result = enrich_wiki_page_if_scholarly(page)
            assert result.detected is True
            assert "no doi" in result.skipped_reason.lower()
        finally:
            os.unlink(page)

    def test_encoding_error_graceful(self):
        """Invalid UTF-8 returns error, doesn't crash."""
        page = _make_page("---\ntitle: Test\n---\n\nBody.")
        try:
            # Corrupt the file
            with open(page, 'wb') as f:
                f.write(b'\xff\xfe\x00\x00 invalid')
            result = enrich_wiki_page_if_scholarly(page)
            assert len(result.errors) > 0
        finally:
            os.unlink(page)

    def test_idempotent_second_run_no_change(self):
        """Running enrichment twice on same page produces no diff."""
        content = (
            "---\ntitle: Test Paper\ndoi: 10.xxx/test\n"
            "scholarly:\n  detected: true\n  doi: 10.xxx/test\n"
            "  title: Test Paper\ncitation:\n  gbt7714-numeric:\n"
            "    text: '[1] Author. Test Paper. 2023.'\n"
            "    engine_used: fallback\n    strict: true\n"
            "---\n\n# Test Paper\n\nBody."
        )
        page = _make_page(content)
        try:
            # First run: should detect scholarly data already present
            result = enrich_wiki_page_if_scholarly(page)
            # Should be idempotent (same data already there)
            assert result.changed is False
        finally:
            os.unlink(page)

    def test_locked_bypass_with_force(self):
        """Force flag bypasses locked check."""
        page = _make_page(
            "---\ntitle: Test\ndoi: 10.xxx/test\nscholarly:\n  locked: true\n---\n\nBody."
        )
        try:
            result = enrich_wiki_page_if_scholarly(page, force=True)
            # Locked check is bypassed with force
            assert result.locked is False  # force bypasses
        finally:
            os.unlink(page)


# ─────────────────────────────────────────────
# End-to-end /pkb pipeline integration tests (Phase 1B.1)
# ─────────────────────────────────────────────

class TestPkbPipelineIntegration:
    """Tests that verify the scholarly enrichment integrates correctly
    into the /pkb workflow: before commit, only new pages, fail-open, no background tasks."""

    @pytest.fixture
    def pkb_root(self):
        """Create a temp PKB root with wiki/ directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            wiki_dir = root / "wiki" / "sources"
            wiki_dir.mkdir(parents=True)
            yield root

    def _make_wiki_page(self, root: Path, name: str, content: str) -> Path:
        """Create a wiki page and return its path."""
        page = root / "wiki" / "sources" / name
        page.parent.mkdir(parents=True, exist_ok=True)
        page.write_text(content, encoding='utf-8')
        return page

    def test_scholarly_before_commit_call_order(self, pkb_root):
        """Scholarly enrichment runs BEFORE commit in the /pkb pipeline."""
        from scholarly.integration import scholarly_enrich_pages

        # Create a scholarly page with DOI
        self._make_wiki_page(pkb_root, "paper1.md",
            "---\ntitle: Test Paper\ndoi: 10.1234/test.2025\n---\n\nBody.")

        # Create a non-scholarly page
        self._make_wiki_page(pkb_root, "note1.md",
            "---\ntitle: Random Note\n---\n\nJust notes.")

        commit_recorder = []

        # Simulate /pkb flow: Step 4 (scholarly) before Step 10 (commit)
        batch = scholarly_enrich_pages(
            [pkb_root / "wiki" / "sources" / "paper1.md",
             pkb_root / "wiki" / "sources" / "note1.md"],
            root=pkb_root,
            commit_recorder=commit_recorder,
        )

        # Enrichment completed
        assert batch.enriched_before_commit is True

        # Record commit AFTER enrichment
        commit_recorder.append("git_commit")

        # Verify call order: scholarly_start → scholarly_end → git_commit
        assert commit_recorder == [
            "scholarly_enrich_start",
            "scholarly_enrich_end",
            "git_commit",
        ], f"Call order wrong: {commit_recorder}"

    def test_only_specified_pages_processed(self, pkb_root):
        """Only the pages passed to scholarly_enrich_pages are processed.
        No unconditional wiki scan."""
        from scholarly.integration import scholarly_enrich_pages

        # Create 3 pages, only pass 2
        self._make_wiki_page(pkb_root, "paper1.md",
            "---\ntitle: Paper One\ndoi: 10.1234/one.2025\n---\n\nBody.")
        self._make_wiki_page(pkb_root, "paper2.md",
            "---\ntitle: Paper Two\ndoi: 10.1234/two.2025\n---\n\nBody.")
        self._make_wiki_page(pkb_root, "paper3.md",
            "---\ntitle: Paper Three\ndoi: 10.1234/three.2025\n---\n\nBody.")

        only = {str(pkb_root / "wiki" / "sources" / "paper1.md"),
                str(pkb_root / "wiki" / "sources" / "paper2.md")}

        batch = scholarly_enrich_pages(
            [pkb_root / "wiki" / "sources" / "paper1.md",
             pkb_root / "wiki" / "sources" / "paper2.md",
             pkb_root / "wiki" / "sources" / "paper3.md"],
            root=pkb_root,
            only_paths=only,
        )

        # Only 2 pages should be processed
        assert batch.pages_processed == 2

    def test_non_scholarly_no_enrichment_api_call(self, pkb_root):
        """Non-scholarly pages do not trigger Crossref/OpenAlex API calls."""
        from scholarly.integration import scholarly_enrich_pages
        from scholarly.integration import ScholarlyIntegrationConfig

        # Create a non-scholarly page
        self._make_wiki_page(pkb_root, "note1.md",
            "---\ntitle: Shopping List\n---\n\nMilk, eggs, bread.")

        config = ScholarlyIntegrationConfig(enabled=True)

        # Mock the enricher to detect any API call
        with patch('scholarly.integration.ScholarlyEnricher') as mock_enricher_class:
            mock_enricher = MagicMock()
            mock_enricher_class.return_value = mock_enricher

            batch = scholarly_enrich_pages(
                [pkb_root / "wiki" / "sources" / "note1.md"],
                root=pkb_root,
                config=config,
            )

            # The enricher should never be instantiated for non-scholarly pages
            mock_enricher_class.assert_not_called()

            result = batch.results.get(str(pkb_root / "wiki" / "sources" / "note1.md"))
            assert result is not None
            assert result.detected is False
            assert result.attempted is False

    def test_fail_open_page_still_committable(self, pkb_root):
        """When enrichment fails, the page is still saved and can be committed."""
        from scholarly.integration import scholarly_enrich_pages
        from scholarly.integration import ScholarlyIntegrationConfig

        # Create a scholarly page with DOI
        page = self._make_wiki_page(pkb_root, "paper1.md",
            "---\ntitle: Test Paper\ndoi: 10.1234/failopen.2025\n---\n\nBody.")

        config = ScholarlyIntegrationConfig(enabled=True, fail_open=True)

        # Mock enrich_by_doi to raise an exception
        with patch('scholarly.integration.ScholarlyEnricher') as mock_enricher_class:
            mock_enricher = MagicMock()
            mock_enricher.enrich_by_doi.side_effect = RuntimeError("Crossref timeout")
            mock_enricher_class.return_value = mock_enricher

            batch = scholarly_enrich_pages(
                [page], root=pkb_root, config=config
            )

        # Page was still processed (not crashed)
        result = batch.results.get(str(page))
        assert result is not None
        # Enrichment was attempted but failed
        assert result.attempted is True
        assert len(result.errors) > 0 or len(result.warnings) > 0
        # File still exists (wasn't corrupted)
        assert page.exists()
        content = page.read_text(encoding='utf-8')
        assert "Test Paper" in content

    def test_no_background_tasks(self, pkb_root):
        """scholarly_enrich_pages is fully synchronous — no background tasks."""
        import time
        from scholarly.integration import scholarly_enrich_pages

        self._make_wiki_page(pkb_root, "paper1.md",
            "---\ntitle: Sync Test\ndoi: 10.1234/sync.2025\n---\n\nBody.")

        start = time.time()
        batch = scholarly_enrich_pages(
            [pkb_root / "wiki" / "sources" / "paper1.md"],
            root=pkb_root,
        )
        elapsed = time.time() - start

        # Must complete quickly (synchronous, no background threads)
        assert elapsed < 10.0, f"Took {elapsed:.1f}s — should be synchronous"

    def test_enriched_content_present_for_commit(self, pkb_root):
        """When enrichment succeeds, the file on disk has scholarly frontmatter
        BEFORE commit would happen."""
        from scholarly.integration import scholarly_enrich_pages, ScholarlyIntegrationConfig
        from scholarly.enrichment import ScholarlyEnricher, EnrichmentConfig
        from scholarly.models import (
            ScholarlyRecord, EnrichmentResult, SourceStatus, CitationData, CitationStyle
        )

        # Create a scholarly page with DOI
        page = self._make_wiki_page(pkb_root, "paper1.md",
            "---\ntitle: Platform Governance\ndoi: 10.1234/commit.2025\n---\n\n# Abstract\n\nBody text.")

        config = ScholarlyIntegrationConfig(enabled=True, write_metrics=True, write_citations=True)

        # Mock the enrichment to return controlled data
        mock_record = ScholarlyRecord(
            doi="10.1234/commit.2025",
            title="Platform Governance in Digital Markets",
            authors=[{"family": "Zhang", "given": "San"}],
            year=2025,
            journal_name="Journal of Digital Governance",
            issn=["2000-5555"],
            crossref_status=SourceStatus.AVAILABLE,
            openalex_status=SourceStatus.AVAILABLE,
        )
        mock_enrichment = EnrichmentResult(
            record=mock_record,
            citations=[
                CitationData(
                    style=CitationStyle.GBT7714_NUMERIC,
                    formatted="[1] Zhang S. Platform Governance in Digital Markets[J]. Journal of Digital Governance, 2025.",
                    engine_used="fallback",
                    strict=True,
                ),
            ],
        )

        with patch('scholarly.integration.ScholarlyEnricher') as mock_enricher_class:
            mock_enricher = MagicMock()
            mock_enricher.enrich_by_doi.return_value = mock_enrichment
            mock_enricher_class.return_value = mock_enricher

            batch = scholarly_enrich_pages(
                [page], root=pkb_root, config=config
            )

        # Enrichment should have changed the file
        result = batch.results.get(str(page))
        assert result is not None
        assert result.changed is True

        # File on disk should now contain scholarly frontmatter
        content = page.read_text(encoding='utf-8')
        assert "scholarly:" in content
        assert "Journal of Digital Governance" in content
        assert "gbt7714-numeric" in content
        assert "Platform Governance" in content
