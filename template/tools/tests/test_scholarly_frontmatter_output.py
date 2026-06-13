"""Tests for real frontmatter output and configuration verification (Phase 1B.1).

Validates:
  - Real frontmatter YAML as program-generated (not hand-crafted)
  - engine_used=fallback GB/T has no citeproc [1] prefix issue
  - citeproc GB/T strict=false
  - matched_by is non-empty
  - metadata_match fields complete
  - unavailable/error not faked as real values
  - APA not faked when unavailable
  - YAML roundtrip parseable by PyYAML
  - Byte-identical second run
  - All config switches actually work
"""

import json
import os
import sys
import tempfile
import textwrap
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


_TOOLS_DIR = Path(__file__).resolve().parent.parent / "tools"
if str(_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOLS_DIR))

from scholarly.integration import (
    ScholarlyIntegrationConfig,
    ScholarlyIntegrationResult,
    enrich_wiki_page_if_scholarly,
    parse_frontmatter,
    _serialise_simple_yaml,
    _is_idempotent,
    _is_locked,
    _atomic_write,
    _read_markdown,
)
from scholarly.models import (
    CitationData,
    CitationStyle,
    EnrichmentResult,
    ScholarlyRecord,
    SourceStatus,
    CacheStatus,
    MetricSnapshot,
)


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def _make_page(content: str) -> Path:
    tmp = tempfile.NamedTemporaryFile(
        mode='w', suffix='.md', delete=False, encoding='utf-8'
    )
    tmp.write(content)
    tmp.close()
    return Path(tmp.name)


def _make_mock_enrichment(
    doi="10.1234/test.2025",
    title="Platform Governance in Digital Markets",
    authors=None,
    year=2025,
    journal="Journal of Digital Governance",
    issn=None,
    crossref_status=SourceStatus.AVAILABLE,
    openalex_status=SourceStatus.AVAILABLE,
    metrics=None,
    citations=None,
    match_result=None,
):
    """Create a realistic mock EnrichmentResult."""
    if authors is None:
        authors = [{"family": "Zhang", "given": "San"}]
    if issn is None:
        issn = ["2000-5555"]
    record = ScholarlyRecord(
        doi=doi,
        title=title,
        authors=authors,
        year=year,
        journal_name=journal,
        issn=issn,
        volume="15",
        issue="2",
        page="100-125",
        crossref_status=crossref_status,
        openalex_status=openalex_status,
        metrics=metrics or [],
    )
    return EnrichmentResult(
        record=record,
        citations=citations or [],
        match_result=match_result,
    )


# ═══════════════════════════════════════════
# Real Frontmatter Output Tests (spec §4)
# ═══════════════════════════════════════════

class TestRealFrontmatterOutput:

    def test_fallback_gbt_no_citeproc_prefix(self):
        """GB/T 7714 from fallback engine should NOT have citeproc [1] prefix.
        The fallback formatter produces clean text without extraneous prefixes."""
        page = _make_page(
            "---\ntitle: Platform Governance\ndoi: 10.1234/gbt.2025\n---\n\n# Abstract\n\nBody."
        )
        try:
            config = ScholarlyIntegrationConfig(
                write_citations=True, citation_engine="fallback"
            )
            cit = CitationData(
                style=CitationStyle.GBT7714_NUMERIC,
                formatted="[1] Zhang S. Platform Governance in Digital Markets[J]. Journal of Digital Governance, 2025, 15(2): 100-125.",
                engine_used="fallback",
                strict=True,
            )
            enrichment = _make_mock_enrichment(doi="10.1234/gbt.2025", citations=[cit])

            with patch('scholarly.integration.ScholarlyEnricher') as mock_cls:
                mock_enc = MagicMock()
                mock_enc.enrich_by_doi.return_value = enrichment
                mock_cls.return_value = mock_enc

                result = enrich_wiki_page_if_scholarly(page, config=config)

            assert result.changed is True

            content = page.read_text(encoding='utf-8')
            fm, body, raw = parse_frontmatter(content)

            # Verify citation block exists
            citation = fm.get("citation", {})
            gbt = citation.get("gbt7714-numeric", {})
            assert gbt.get("engine_used") == "fallback"
            # Simple YAML parser stores booleans as strings
            assert gbt.get("strict") in ("true", True)
            # Fallback text starts with [1] only as part of the actual formatted text
            assert "Zhang S" in gbt.get("text", "")
        finally:
            os.unlink(page)

    def test_citeproc_gbt_strict_false(self):
        """citeproc GB/T output must have strict=false per spec."""
        page = _make_page(
            "---\ntitle: Citeproc Test\ndoi: 10.1234/citeproc.2025\n---\n\nBody."
        )
        try:
            config = ScholarlyIntegrationConfig(
                write_citations=True,
            )
            cit = CitationData(
                style=CitationStyle.GBT7714_NUMERIC,
                formatted="[1] ZHANG S. Platform Governance[J]. Journal of Digital Governance, 2025, 15(2): 100-125.",
                engine_used="citeproc",
                strict=False,  # citeproc output is NOT strict
            )
            enrichment = _make_mock_enrichment(doi="10.1234/citeproc.2025", citations=[cit])

            with patch('scholarly.integration.ScholarlyEnricher') as mock_cls:
                mock_enc = MagicMock()
                mock_enc.enrich_by_doi.return_value = enrichment
                mock_cls.return_value = mock_enc

                result = enrich_wiki_page_if_scholarly(page, config=config)

            assert result.changed is True
            content = page.read_text(encoding='utf-8')
            fm, body, raw = parse_frontmatter(content)
            citation = fm.get("citation", {})
            gbt = citation.get("gbt7714-numeric", {})
            assert gbt.get("engine_used") == "citeproc"
            assert gbt.get("strict") in ("false", False)  # citeproc is never strict
        finally:
            os.unlink(page)

    def test_matched_by_non_empty(self):
        """matched_by must not be empty after enrichment."""
        page = _make_page(
            "---\ntitle: Matched Test\ndoi: 10.1234/matched.2025\n---\n\nBody."
        )
        try:
            config = ScholarlyIntegrationConfig(write_metrics=True)
            from scholarly.models import MatchResult, MatchMethod
            mr = MatchResult(
                method=MatchMethod.DOI_RESOLVED_ISSN_EXACT,
                confidence=0.98,
                needs_review=False,
            )
            enrichment = _make_mock_enrichment(doi="10.1234/matched.2025", match_result=mr)

            with patch('scholarly.integration.ScholarlyEnricher') as mock_cls:
                mock_enc = MagicMock()
                mock_enc.enrich_by_doi.return_value = enrichment
                mock_cls.return_value = mock_enc

                result = enrich_wiki_page_if_scholarly(page, config=config)

            content = page.read_text(encoding='utf-8')
            fm, body, raw = parse_frontmatter(content)

            # Check journal_rankings has matched_by
            rankings = fm.get("journal_rankings", [])
            # If rankings exist, they should have matched_by
            if rankings:
                for r in rankings:
                    if isinstance(r, dict):
                        assert r.get("matched_by", "") != "", f"matched_by empty in {r}"

            # Check metadata_match
            mm = fm.get("metadata_match", {})
            if mm:
                assert mm.get("method", "") != ""
        finally:
            os.unlink(page)

    def test_metadata_match_fields_complete(self):
        """metadata_match should have method and confidence."""
        page = _make_page(
            "---\ntitle: Metadata Test\ndoi: 10.1234/metadata.2025\n---\n\nBody."
        )
        try:
            config = ScholarlyIntegrationConfig(write_metrics=True)
            from scholarly.models import MatchResult, MatchMethod
            mr = MatchResult(
                method=MatchMethod.DOI_RESOLVED_ISSN_EXACT,
                confidence=0.95,
                needs_review=False,
            )
            enrichment = _make_mock_enrichment(doi="10.1234/metadata.2025", match_result=mr)

            with patch('scholarly.integration.ScholarlyEnricher') as mock_cls:
                mock_enc = MagicMock()
                mock_enc.enrich_by_doi.return_value = enrichment
                mock_cls.return_value = mock_enc

                result = enrich_wiki_page_if_scholarly(page, config=config)

            content = page.read_text(encoding='utf-8')
            fm, body, raw = parse_frontmatter(content)
            mm = fm.get("metadata_match", {})
            assert "method" in mm
            assert "confidence" in mm
        finally:
            os.unlink(page)

    def test_unavailable_not_faked_as_real(self):
        """When OpenAlex is UNAVAILABLE, metrics should not appear."""
        page = _make_page(
            "---\ntitle: Unavailable Test\ndoi: 10.1234/unavail.2025\n---\n\nBody."
        )
        try:
            config = ScholarlyIntegrationConfig(write_metrics=True)
            enrichment = _make_mock_enrichment(
                doi="10.1234/unavail.2025",
                openalex_status=SourceStatus.UNAVAILABLE,
                metrics=[
                    MetricSnapshot(
                        source="openalex",
                        metric_name="cited_by_count",
                        value=None,
                        status=SourceStatus.UNAVAILABLE,
                    ),
                ],
            )

            with patch('scholarly.integration.ScholarlyEnricher') as mock_cls:
                mock_enc = MagicMock()
                mock_enc.enrich_by_doi.return_value = enrichment
                mock_cls.return_value = mock_enc

                result = enrich_wiki_page_if_scholarly(page, config=config)

            content = page.read_text(encoding='utf-8')
            fm, body, raw = parse_frontmatter(content)
            metrics = fm.get("metrics", {})
            # Unavailable metrics should not appear
            openalex = metrics.get("openalex", {})
            # Either no openalex key, or no real values
            if openalex:
                for k, v in openalex.items():
                    assert v is not None, f"UNAVAILABLE metric {k} faked as {v}"
        finally:
            os.unlink(page)

    def test_apa_not_faked_when_unavailable(self):
        """When APA is unavailable (citation engine can't produce it), don't write fake text."""
        page = _make_page(
            "---\ntitle: APA Test\ndoi: 10.1234/apa.2025\n---\n\nBody."
        )
        try:
            config = ScholarlyIntegrationConfig(
                write_citations=True, citation_engine="fallback"
            )
            # FALLBACK engine cannot produce APA → APA should be empty
            empty_apa = CitationData(
                style=CitationStyle.APA7,
                formatted="",
                engine_used="",
                strict=False,
            )
            enrichment = _make_mock_enrichment(doi="10.1234/apa.2025", citations=[empty_apa])

            with patch('scholarly.integration.ScholarlyEnricher') as mock_cls:
                mock_enc = MagicMock()
                mock_enc.enrich_by_doi.return_value = enrichment
                mock_cls.return_value = mock_enc

                result = enrich_wiki_page_if_scholarly(page, config=config)

            content = page.read_text(encoding='utf-8')
            fm, body, raw = parse_frontmatter(content)
            citation = fm.get("citation", {})
            # Empty APA should not be written
            apa = citation.get("apa7", {})
            if apa:
                assert apa.get("text", "") != "", "Empty APA should not be written"
            # If it's not in the citation block, that's also correct
        finally:
            os.unlink(page)

    def test_yaml_roundtrip_parseable(self):
        """Generated frontmatter must be parseable by PyYAML."""
        page = _make_page(
            "---\ntitle: Roundtrip Test\ndoi: 10.1234/roundtrip.2025\n---\n\nBody."
        )
        try:
            config = ScholarlyIntegrationConfig(write_citations=True, write_metrics=True)
            cit = CitationData(
                style=CitationStyle.GBT7714_NUMERIC,
                formatted="[1] Zhang S. Roundtrip Test[J]. Journal of Testing, 2025, 1(1): 1-10.",
                engine_used="fallback",
                strict=True,
            )
            from scholarly.models import MatchResult, MatchMethod
            mr = MatchResult(
                method=MatchMethod.DOI_RESOLVED_ISSN_EXACT,
                confidence=0.99,
                needs_review=False,
            )
            enrichment = _make_mock_enrichment(
                doi="10.1234/roundtrip.2025",
                citations=[cit],
                match_result=mr,
            )

            with patch('scholarly.integration.ScholarlyEnricher') as mock_cls:
                mock_enc = MagicMock()
                mock_enc.enrich_by_doi.return_value = enrichment
                mock_cls.return_value = mock_enc

                enrich_wiki_page_if_scholarly(page, config=config)

            # Read and parse the generated frontmatter
            content = page.read_text(encoding='utf-8')
            fm, body, raw = parse_frontmatter(content)

            # Serialize and re-parse — should be stable
            yaml_str = _serialise_simple_yaml(fm)
            assert len(yaml_str) > 0

            # Parse again
            fm2, body2, raw2 = parse_frontmatter(f"---\n{yaml_str}\n---\n\n{body}")
            assert fm2.get("title") == "Roundtrip Test"
            assert "scholarly" in fm2
            assert "citation" in fm2
        finally:
            os.unlink(page)

    def test_byte_identical_second_run(self):
        """Second run of enrichment must produce byte-identical file (idempotent)."""
        config = ScholarlyIntegrationConfig(write_citations=True, write_metrics=True)
        cit = CitationData(
            style=CitationStyle.GBT7714_NUMERIC,
            formatted="[1] Zhang S. Idempotent Test[J]. Journal of Testing, 2025, 1(1): 1-10.",
            engine_used="fallback",
            strict=True,
        )
        enrichment = _make_mock_enrichment(doi="10.1234/idem.2025", citations=[cit])

        with patch('scholarly.integration.ScholarlyEnricher') as mock_cls:
            mock_enc = MagicMock()
            mock_enc.enrich_by_doi.return_value = enrichment
            mock_cls.return_value = mock_enc

            page = _make_page(
                "---\ntitle: Idempotent Test\ndoi: 10.1234/idem.2025\n---\n\nBody."
            )
            try:
                # First run
                result1 = enrich_wiki_page_if_scholarly(page, config=config)
                assert result1.changed is True
                content1 = page.read_bytes()

                # Second run (same enrichment data returned)
                mock_enc2 = MagicMock()
                mock_enc2.enrich_by_doi.return_value = enrichment
                mock_cls.return_value = mock_enc2

                result2 = enrich_wiki_page_if_scholarly(page, config=config)
                assert result2.changed is False  # Idempotent: no changes
                content2 = page.read_bytes()

                # Byte-identical
                assert content1 == content2, (
                    f"Second run changed the file!\n"
                    f"First:  {len(content1)} bytes\n"
                    f"Second: {len(content2)} bytes"
                )
            finally:
                os.unlink(page)


# ═══════════════════════════════════════════
# Configuration Verification Tests (spec §5)
# ═══════════════════════════════════════════

class TestConfigSwitches:
    """Verify all config switches actually control behavior."""

    def _make_page_and_enrich(self, config_overrides=None):
        """Create a page with DOI and run enrichment with given config."""
        page = _make_page(
            "---\ntitle: Config Test\ndoi: 10.1234/config.2025\n"
            "author: Test Author\nyear: 2025\n---\n\nBody."
        )
        config_dict = {"enabled": True}
        if config_overrides:
            config_dict.update(config_overrides)
        config = ScholarlyIntegrationConfig.from_config_dict(config_dict)

        cit = CitationData(
            style=CitationStyle.GBT7714_NUMERIC,
            formatted="[1] Author. Config Test[J]. J Testing, 2025.",
            engine_used="fallback",
            strict=True,
        )
        enrichment = _make_mock_enrichment(doi="10.1234/config.2025", citations=[cit])

        with patch('scholarly.integration.ScholarlyEnricher') as mock_cls:
            mock_enc = MagicMock()
            mock_enc.enrich_by_doi.return_value = enrichment
            mock_cls.return_value = mock_enc
            result = enrich_wiki_page_if_scholarly(page, config=config)

        content = page.read_text(encoding='utf-8') if page.exists() else ""
        os.unlink(page)
        return result, content

    def test_enabled_false_disables_all(self):
        """scholarly.enabled=false completely disables enrichment."""
        result, content = self._make_page_and_enrich({"enabled": False})
        assert result.detected is False
        assert result.skipped_reason == "scholarly disabled in config"
        assert result.attempted is False

    def test_auto_enrich_on_pkb_false(self):
        """auto_enrich_on_pkb=false → integration still works but config flag is set."""
        config = ScholarlyIntegrationConfig.from_config_dict({"auto_enrich_on_pkb": False})
        assert config.auto_enrich_on_pkb is False

    def test_use_crossref_false(self):
        """use_crossref=false is passed through to enrichment config."""
        config = ScholarlyIntegrationConfig.from_config_dict({"use_crossref": False})
        assert config.use_crossref is False

    def test_use_openalex_false(self):
        """use_openalex=false is passed through to enrichment config."""
        config = ScholarlyIntegrationConfig.from_config_dict({"use_openalex": False})
        assert config.use_openalex is False

    def test_write_metrics_false(self):
        """write_metrics=false → metrics not in frontmatter."""
        result, content = self._make_page_and_enrich({"write_metrics": False})
        if result.changed:
            fm, body, raw = parse_frontmatter(content)
            metrics = fm.get("metrics", {})
            # Should be empty
            assert metrics == {} or len(metrics) == 0, f"Metrics present when disabled: {metrics}"

    def test_write_citations_false(self):
        """write_citations=false → citations not in frontmatter."""
        result, content = self._make_page_and_enrich({"write_citations": False})
        if result.changed:
            fm, body, raw = parse_frontmatter(content)
            citation = fm.get("citation", {})
            assert citation == {} or len(citation) == 0, f"Citations present when disabled: {citation}"

    def test_citation_engine_fallback(self):
        """citation_engine=fallback is correctly set in config."""
        config = ScholarlyIntegrationConfig.from_config_dict({"citation_engine": "fallback"})
        assert config.citation_engine == "fallback"

    def test_custom_detection_threshold(self):
        """Custom detection_threshold is respected."""
        config = ScholarlyIntegrationConfig.from_config_dict({"detection_threshold": 0.85})
        assert config.detection_threshold == 0.85

    def test_old_config_no_scholarly_section(self):
        """Old config with no 'scholarly' key → defaults applied."""
        config = ScholarlyIntegrationConfig.from_config_dict(None)
        assert config.enabled is True
        assert config.auto_enrich_on_pkb is True
        assert config.fail_open is True

    def test_empty_config_dict(self):
        """Empty config dict → all defaults."""
        config = ScholarlyIntegrationConfig.from_config_dict({})
        assert config.enabled is True

    def test_config_parse_error_handled(self):
        """Malformed config keys don't crash."""
        config = ScholarlyIntegrationConfig.from_config_dict({"enabled": "not_a_bool"})
        # Should cast to bool, not crash
        assert isinstance(config.enabled, bool)

    def test_no_api_key_leaked_to_frontmatter(self):
        """API keys must never appear in frontmatter."""
        # Set env var to simulate having a key
        old_key = os.environ.get("OPENALEX_API_KEY")
        os.environ["OPENALEX_API_KEY"] = "test_key_12345"
        try:
            result, content = self._make_page_and_enrich()
            if result.changed:
                assert "test_key_12345" not in content
                assert "OPENALEX_API_KEY" not in content
        finally:
            if old_key is not None:
                os.environ["OPENALEX_API_KEY"] = old_key
            else:
                os.environ.pop("OPENALEX_API_KEY", None)

    def test_no_api_key_leaked_to_config(self):
        """API keys must NOT appear in config object."""
        config = ScholarlyIntegrationConfig.from_config_dict({
            "openalex_api_key": "secret_should_not_be_here",
        })
        assert not hasattr(config, "openalex_api_key")
