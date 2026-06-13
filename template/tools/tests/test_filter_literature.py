"""Tests for filter_literature.py — structured literature filter.

Covers: CSSCI/AMI filtering, edition, level, year range, citations,
needs_review, missing field, AND logic, table/json/paths output,
citation export, damaged frontmatter, stable sort, no network, no writes.
"""

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

_TOOLS_DIR = Path(__file__).resolve().parent.parent / "tools"
if str(_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOLS_DIR))


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def _make_wiki(root: Path, files: dict):
    """Create a wiki/ directory structure from {relpath: content} dict."""
    wiki_dir = root / "wiki"
    wiki_dir.mkdir(parents=True, exist_ok=True)
    for relpath, content in files.items():
        fp = wiki_dir / relpath
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(content, encoding='utf-8')


SAMPLE_SCHOLARLY_PAGE = """---
title: A Study of Platform Governance
doi: 10.1234/test.2023
scholarly:
  detected: true
  detected_type: article-journal
  doi: 10.1234/test.2023
  title: A Study of Platform Governance
  authors: ['Zhang San', 'Li Si']
  year: 2023
  journal: Journal of Communication Research
  issn: ['1000-0001']
  enriched_at: 2026-06-13T00:00:00Z
  sources: ['crossref', 'openalex']
journal_rankings:
  - scheme: CSSCI
    edition: 2025-2026
    level: source
    matched_by: issn
    confidence: 0.98
metrics:
  openalex:
    cited_by_count: 16
    two_year_mean_citedness: 3.82
  retrieved_at: 2026-06-13T00:00:00Z
citation:
  gbt7714-numeric:
    text: '[1] Zhang S, Li S. A Study of Platform Governance[J]. Journal of Communication Research, 2023, 40(1): 1-25.'
    engine_used: fallback
    strict: true
  apa7:
    text: 'Zhang, S., & Li, S. (2023). A Study of Platform Governance. Journal of Communication Research, 40(1), 1-25.'
    engine_used: citeproc
    strict: true
metadata_match:
  method: doi_resolved_issn_exact
  confidence: 1.0
---
# A Study of Platform Governance

Abstract text...
"""

SAMPLE_NON_SCHOLARLY_PAGE = """---
title: Random Note
type: note
---
Just some random notes.
"""

SAMPLE_AMI_PAGE = """---
title: Communication Theory Paper
doi: 10.5678/comm.2024
scholarly:
  detected: true
  detected_type: article-journal
  doi: 10.5678/comm.2024
  title: Communication Theory Paper
  authors: ['Wang Wu']
  year: 2024
  journal: Communication Theory
journal_rankings:
  - scheme: AMI
    edition: 2025-2026
    level: authoritative
    matched_by: issn
metrics:
  openalex:
    cited_by_count: 42
citation:
  gbt7714-numeric:
    text: '[1] Wang W. Communication Theory Paper[J]. Communication Theory, 2024, 35(2): 100-120.'
    engine_used: fallback
    strict: true
metadata_match:
  method: issn_exact
  confidence: 0.95
  needs_review: true
---
# Communication Theory Paper

Abstract...
"""

SAMPLE_NEEDS_REVIEW_PAGE = """---
title: Needs Review Paper
doi: 10.9999/review.2025
scholarly:
  detected: true
  doi: 10.9999/review.2025
  title: Needs Review Paper
  year: 2025
  journal: Some Journal
metadata_match:
  method: name_exact
  confidence: 0.85
  needs_review: true
---
# Needs Review Paper

Body.
"""

SAMPLE_NO_CITATION_PAGE = """---
title: No Citation Paper
doi: 10.8888/nocite.2023
scholarly:
  detected: true
  doi: 10.8888/nocite.2023
  title: No Citation Paper
  year: 2023
  journal: Journal Without Citations
---
# No Citation Paper

Body text without citation block.
"""


# ─────────────────────────────────────────────
# Tests
# ─────────────────────────────────────────────

class TestFilterLiterature:

    @pytest.fixture
    def wiki_root(self):
        """Create a temp PKB root with sample wiki pages."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _make_wiki(root, {
                "sources/scholarly_paper.md": SAMPLE_SCHOLARLY_PAGE,
                "sources/ami_paper.md": SAMPLE_AMI_PAGE,
                "sources/needs_review.md": SAMPLE_NEEDS_REVIEW_PAGE,
                "sources/no_citation.md": SAMPLE_NO_CITATION_PAGE,
                "concepts/random_note.md": SAMPLE_NON_SCHOLARLY_PAGE,
            })
            yield root

    def _scan(self, root, **kwargs):
        """Helper: run scan_literature with given filters."""
        from filter_literature import scan_literature
        return scan_literature(root, **kwargs)

    # ── Ranking filter ──
    def test_filter_cssci(self, wiki_root):
        matches, warnings = self._scan(wiki_root, ranking="CSSCI")
        assert len(matches) == 1
        assert matches[0].journal == "Journal of Communication Research"

    def test_filter_ami(self, wiki_root):
        matches, warnings = self._scan(wiki_root, ranking="AMI")
        assert len(matches) == 1
        assert matches[0].journal == "Communication Theory"

    def test_filter_cssci_with_edition(self, wiki_root):
        matches, warnings = self._scan(wiki_root, ranking="CSSCI", edition="2025-2026")
        assert len(matches) == 1

    def test_filter_cssci_wrong_edition(self, wiki_root):
        matches, warnings = self._scan(wiki_root, ranking="CSSCI", edition="2023-2024")
        assert len(matches) == 0

    def test_filter_ami_level(self, wiki_root):
        matches, warnings = self._scan(wiki_root, ranking="AMI", level="authoritative")
        assert len(matches) == 1

    def test_filter_ami_wrong_level(self, wiki_root):
        matches, warnings = self._scan(wiki_root, ranking="AMI", level="top")
        assert len(matches) == 0

    def test_filter_nonexistent_ranking(self, wiki_root):
        matches, warnings = self._scan(wiki_root, ranking="JCR")
        assert len(matches) == 0

    # ── Year filter ──
    def test_filter_year_from(self, wiki_root):
        matches, warnings = self._scan(wiki_root, year_from=2024)
        assert len(matches) == 2  # 2024 AMI + 2025 review
        assert all(int(m.year) >= 2024 for m in matches if m.year.isdigit())

    def test_filter_year_to(self, wiki_root):
        matches, warnings = self._scan(wiki_root, year_to=2023)
        assert len(matches) == 2  # 2023 CSSCI + 2023 no_citation

    def test_filter_year_range(self, wiki_root):
        matches, warnings = self._scan(wiki_root, year_from=2024, year_to=2025)
        assert len(matches) == 2
        years = [int(m.year) for m in matches if m.year.isdigit()]
        assert all(2024 <= y <= 2025 for y in years)

    # ── Journal filter ──
    def test_filter_journal_substring(self, wiki_root):
        matches, warnings = self._scan(wiki_root, journal="Communication")
        assert len(matches) == 2  # Both papers have "Communication" in journal name

    def test_filter_journal_exact(self, wiki_root):
        matches, warnings = self._scan(wiki_root, journal="Communication Theory")
        assert len(matches) == 1

    # ── DOI filter ──
    def test_filter_doi_substring(self, wiki_root):
        matches, warnings = self._scan(wiki_root, doi="10.1234")
        assert len(matches) == 1

    # ── Citations filter ──
    def test_filter_min_citations(self, wiki_root):
        matches, warnings = self._scan(wiki_root, min_citations=20)
        assert len(matches) == 1
        assert matches[0].citations_count >= 20

    def test_filter_min_citations_none_match(self, wiki_root):
        matches, warnings = self._scan(wiki_root, min_citations=100)
        assert len(matches) == 0

    # ── Needs review filter ──
    def test_filter_needs_review(self, wiki_root):
        matches, warnings = self._scan(wiki_root, needs_review_flag=True)
        # Both AMI paper and Needs Review Paper have needs_review: true
        assert len(matches) == 2
        assert all(m.needs_review for m in matches)

    # ── Missing field filter ──
    def test_filter_missing_citation(self, wiki_root):
        matches, warnings = self._scan(wiki_root, missing="citation")
        # Needs Review Paper and No Citation Paper both lack citations
        assert len(matches) == 2
        assert all(not m.has_citation for m in matches)

    # ── AND logic ──
    def test_and_cssci_and_year(self, wiki_root):
        matches, warnings = self._scan(
            wiki_root, ranking="CSSCI", year_from=2023, year_to=2023
        )
        assert len(matches) == 1

    def test_and_ranking_and_min_citations(self, wiki_root):
        matches, warnings = self._scan(
            wiki_root, ranking="AMI", min_citations=30
        )
        assert len(matches) == 1

    def test_and_no_results(self, wiki_root):
        matches, warnings = self._scan(
            wiki_root, ranking="CSSCI", year_from=2025
        )
        assert len(matches) == 0

    # ── Stable sort ──
    def test_stable_sort_by_year_desc(self, wiki_root):
        matches, warnings = self._scan(wiki_root)
        years = [int(m.year) for m in matches if m.year.isdigit()]
        assert years == sorted(years, reverse=True)

    # ── Non-scholarly pages not in results ──
    def test_non_scholarly_excluded(self, wiki_root):
        matches, warnings = self._scan(wiki_root)
        titles = [m.title for m in matches]
        assert "Random Note" not in titles

    # ── Citation texts extracted ──
    def test_citation_texts_extracted(self, wiki_root):
        matches, warnings = self._scan(wiki_root, ranking="CSSCI")
        assert len(matches) == 1
        assert "gbt7714-numeric" in matches[0].citation_texts
        assert matches[0].has_citation is True

    # ── Empty wiki ──
    def test_empty_wiki(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            wiki = root / "wiki"
            wiki.mkdir()
            matches, warnings = self._scan(root)
            assert len(matches) == 0


class TestFilterOutputFormats:

    @pytest.fixture
    def wiki_root(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _make_wiki(root, {
                "sources/scholarly_paper.md": SAMPLE_SCHOLARLY_PAGE,
                "sources/ami_paper.md": SAMPLE_AMI_PAGE,
            })
            yield root

    def test_format_paths(self, capsys, wiki_root):
        """--format paths outputs one path per line."""
        from filter_literature import _format_paths
        from filter_literature import scan_literature
        matches, _ = scan_literature(wiki_root)
        _format_paths(matches)
        captured = capsys.readouterr()
        lines = [l for l in captured.out.strip().split("\n") if l.strip()]
        assert len(lines) >= 2  # At least 2 scholarly pages
        # All lines should be valid paths containing .md
        assert all(".md" in l for l in lines)

    def test_format_json(self, capsys, wiki_root):
        """--format json outputs valid JSON."""
        from filter_literature import _format_json
        from filter_literature import scan_literature
        matches, _ = scan_literature(wiki_root)
        _format_json(matches)
        captured = capsys.readouterr()
        data = json.loads(captured.out.strip())
        assert isinstance(data, list)
        assert len(data) == 2

    def test_export_citations(self, capsys, wiki_root):
        """--export-citations outputs citation texts."""
        from filter_literature import _export_citations
        from filter_literature import scan_literature
        matches, _ = scan_literature(wiki_root)
        _export_citations(matches, "gbt7714-numeric")
        captured = capsys.readouterr()
        assert "Zhang S" in captured.out or "Wang W" in captured.out

    def test_export_citations_none_available(self, capsys, wiki_root):
        """Export non-existent style shows message."""
        from filter_literature import _export_citations
        from filter_literature import scan_literature
        matches, _ = scan_literature(wiki_root)
        _export_citations(matches, "ris")
        captured = capsys.readouterr()
        assert "No citations available" in captured.out


class TestFilterEdgeCases:

    @pytest.fixture
    def wiki_root(self):
        """Create a temp PKB root with sample wiki pages."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            yield root

    def test_damaged_frontmatter(self):
        """Damaged frontmatter records warning, continues scan."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _make_wiki(root, {
                "sources/broken.md": "---\ntitle: Broken\nunclosed: [\n---\n\nBody.",
                "sources/good.md": SAMPLE_SCHOLARLY_PAGE,
            })
            from filter_literature import scan_literature
            matches, warnings = scan_literature(root)
            # The good page should still be found
            assert len(matches) >= 1

    def test_encoding_error(self):
        """Non-UTF-8 file records warning, continues scan."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            wiki = root / "wiki" / "sources"
            wiki.mkdir(parents=True)
            (wiki / "bad_encoding.md").write_bytes(b'\xff\xfe\x00\x00 invalid')
            (wiki / "good.md").write_text(SAMPLE_SCHOLARLY_PAGE, encoding='utf-8')
            from filter_literature import scan_literature
            matches, warnings = scan_literature(root)
            assert len(warnings) >= 1
            assert len(matches) >= 1  # Good page still found

    def test_no_wiki_dir(self):
        """No wiki/ directory returns empty with warning."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            from filter_literature import scan_literature
            matches, warnings = scan_literature(root)
            assert len(matches) == 0
            assert len(warnings) >= 1

    def test_no_file_writes(self, wiki_root):
        """Filter tool does not write any files."""
        from filter_literature import scan_literature
        # Check file modification times before
        files_before = {}
        for fp in sorted((wiki_root / "wiki").rglob("*.md")):
            files_before[str(fp)] = fp.stat().st_mtime
        matches, _ = scan_literature(wiki_root, ranking="CSSCI")
        # Check no files were modified
        for fp_str, mtime in files_before.items():
            assert Path(fp_str).stat().st_mtime == mtime

    def test_no_network_calls(self, wiki_root):
        """Filter tool makes no network calls."""
        import requests
        _make_wiki(wiki_root, {
            "sources/scholarly_paper.md": SAMPLE_SCHOLARLY_PAGE,
        })
        from filter_literature import scan_literature
        with patch.object(requests.Session, 'request',
                          side_effect=RuntimeError("Network blocked")):
            matches, _ = scan_literature(wiki_root)
            assert len(matches) >= 1  # Should work entirely offline
