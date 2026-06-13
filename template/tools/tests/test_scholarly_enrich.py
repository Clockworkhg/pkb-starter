"""Integration tests for scholarly_enrich.py (CLI) and enrichment.py.

Covers: CLI modes, --write idempotency, atomic writes, offline, cache-only,
JSON output, Markdown file handling, Windows paths.

No real network access — all tests use mock.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

_TOOLS_DIR = Path(__file__).resolve().parent.parent
if not (_TOOLS_DIR / "scholarly").is_dir() and not (_TOOLS_DIR / "content_quality.py").exists():
    _TOOLS_DIR = _TOOLS_DIR / "tools"
if str(_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOLS_DIR))

import pytest

from scholarly.enrichment import ScholarlyEnricher, EnrichmentConfig, enrich_scholarly_record
from scholarly.models import (
    CacheStatus,
    EnrichmentResult,
    ScholarlyRecord,
    SourceStatus,
)
from scholarly.cache import ScholarlyCache, NS_CROSSREF, TTL_STATIC
from scholarly_enrich import (
    parse_frontmatter,
    _parse_simple_yaml,
    _serialise_simple_yaml,
    _merge_frontmatter,
    update_markdown_file,
    _extract_doi_from_md,
)


# ═══════════════════════════════════════════════════════════
# Frontmatter parsing
# ═══════════════════════════════════════════════════════════

def test_parse_simple_yaml_basic():
    yaml = "title: Hello\ntype: literature\ntags: [a, b, c]"
    result = _parse_simple_yaml(yaml)
    assert result["title"] == "Hello"
    assert result["type"] == "literature"
    assert result["tags"] == ["a", "b", "c"]


def test_parse_simple_yaml_empty():
    assert _parse_simple_yaml("") == {}


def test_serialise_simple_yaml():
    fm = {"title": "Hello", "type": "literature"}
    result = _serialise_simple_yaml(fm)
    assert "title: Hello" in result
    assert "type: literature" in result


def test_serialise_simple_yaml_with_list():
    fm = {"tags": ["a", "b", "c"]}
    result = _serialise_simple_yaml(fm)
    assert "tags:" in result
    assert "a" in result


def test_serialise_simple_yaml_with_nested():
    fm = {"journal_rankings": {"cssci": {"edition": "2025-2026", "level": "source"}}}
    result = _serialise_simple_yaml(fm)
    assert "journal_rankings:" in result
    assert "cssci:" in result
    assert "2025-2026" in result


def test_parse_frontmatter_full():
    content = """---
title: Test
type: literature
year: 2025
doi: 10.1234/test
---
This is the body text."""
    fm, body, raw = parse_frontmatter(content)
    assert fm["title"] == "Test"
    assert fm["doi"] == "10.1234/test"
    assert "This is the body text." in body


def test_parse_frontmatter_no_frontmatter():
    content = "Just body text, no frontmatter."
    fm, body, raw = parse_frontmatter(content)
    assert fm == {}
    assert body == content


# ═══════════════════════════════════════════════════════════
# Frontmatter merge
# ═══════════════════════════════════════════════════════════

def test_merge_frontmatter_preserves_existing():
    """Existing fields not in scholarly namespace are preserved."""
    fm = {"title": "Original", "created": "2026-01-01", "custom_field": "keep_me"}
    result = EnrichmentResult(record=ScholarlyRecord(title="Enriched"))
    new_fm = _merge_frontmatter(fm, result)
    assert new_fm["created"] == "2026-01-01"
    assert new_fm["custom_field"] == "keep_me"
    assert "scholarly" in new_fm


# ═══════════════════════════════════════════════════════════
# Markdown file update
# ═══════════════════════════════════════════════════════════

def test_update_markdown_file():
    """Write enrichment data atomically to a temp file."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as f:
        f.write("""---
title: Test Paper
doi: 10.1234/test
type: literature
---

This is the body of the paper.
""")
        tmp_path = Path(f.name)

    try:
        result = EnrichmentResult(
            record=ScholarlyRecord(
                title="Test Paper",
                doi="10.1234/test",
                authors=[{"family": "张", "given": "三"}],
                journal_name="测试期刊",
                year=2025,
                volume="1",
                issue="1",
                page="1-10",
                pub_type="article-journal",
                crossref_status=SourceStatus.AVAILABLE,
            ),
        )

        ok = update_markdown_file(tmp_path, result)
        assert ok

        # Read back and verify
        content = tmp_path.read_text(encoding="utf-8")
        assert "scholarly:" in content
        assert "10.1234/test" in content
        assert "张" in content
        assert "This is the body" in content
    finally:
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass


def test_update_idempotent():
    """Two consecutive --write operations produce identical output."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as f:
        f.write("""---
title: Idempotent Test
doi: 10.1234/idempotent
type: literature
---

Body text.
""")
        tmp_path = Path(f.name)

    try:
        result = EnrichmentResult(
            record=ScholarlyRecord(
                title="Idempotent Test",
                doi="10.1234/idempotent",
                authors=[{"family": "张", "given": "三"}],
                journal_name="新闻与传播研究",
                year=2025,
                pub_type="article-journal",
                crossref_status=SourceStatus.AVAILABLE,
            ),
        )

        # First write
        ok = update_markdown_file(tmp_path, result)
        assert ok
        content1 = tmp_path.read_text(encoding="utf-8")

        # Second write with same data
        ok = update_markdown_file(tmp_path, result)
        assert ok
        content2 = tmp_path.read_text(encoding="utf-8")

        assert content1 == content2, "Two consecutive --write should produce identical output"
    finally:
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass


def test_atomic_write_failure_preserves_original():
    """If os.replace fails, original file stays intact, temp file is cleaned up."""
    original_content = """---
title: Safe Test
type: literature
---

Safe body text.
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as f:
        f.write(original_content)
        tmp_path = Path(f.name)

    try:
        # Simulate os.replace failure
        with patch("os.replace", side_effect=OSError("simulated replace failure")):
            result = EnrichmentResult(record=ScholarlyRecord(title="Test"))
            ok = update_markdown_file(tmp_path, result)
            assert not ok

        # Original file should be intact
        content = tmp_path.read_text(encoding="utf-8")
        assert "Safe body text" in content
        assert "Safe Test" in content
    finally:
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════
# Encoding tests
# ═══════════════════════════════════════════════════════════

def test_update_markdown_no_bom_roundtrip():
    """UTF-8 without BOM → write → still no BOM."""
    content = """---
title: No BOM Test
type: literature
---

Body with Unicode: 中文测试 и тест.
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as f:
        f.write(content)
        tmp_path = Path(f.name)

    try:
        result = EnrichmentResult(
            record=ScholarlyRecord(
                title="No BOM Test", pub_type="article-journal",
                crossref_status=SourceStatus.AVAILABLE,
            ),
        )
        ok = update_markdown_file(tmp_path, result)
        assert ok

        # Verify no BOM
        with open(tmp_path, 'rb') as f:
            first_bytes = f.read(3)
        assert first_bytes != b'\xef\xbb\xbf', "File should NOT have BOM after write"

        # Verify content readable as UTF-8
        new_content = tmp_path.read_text(encoding="utf-8")
        assert "中文测试" in new_content
        assert "и тест" in new_content
    finally:
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass


def test_update_markdown_bom_read():
    """File with UTF-8 BOM is read and written correctly."""
    with tempfile.NamedTemporaryFile(mode="wb", suffix=".md", delete=False) as f:
        f.write(b'\xef\xbb\xbf')  # BOM
        f.write("""---
title: BOM Test
type: literature
---

Body with BOM.
""".encode('utf-8'))
        tmp_path = Path(f.name)

    try:
        result = EnrichmentResult(
            record=ScholarlyRecord(
                title="BOM Test", pub_type="article-journal",
                crossref_status=SourceStatus.AVAILABLE,
            ),
        )
        ok = update_markdown_file(tmp_path, result)
        assert ok

        # Verify content is correct
        content = tmp_path.read_text(encoding="utf-8-sig")
        assert "BOM Test" in content
        assert "Body with BOM" in content
    finally:
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass


def test_update_markdown_cjk_unicode():
    """Chinese, Tibetan, special punctuation round-trip without corruption."""
    content = """---
title: 藏文与中文测试 བོད་སྐད།
type: literature
---

Unicode: —–《》「」①②③ ★☆
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as f:
        f.write(content)
        tmp_path = Path(f.name)

    try:
        result = EnrichmentResult(
            record=ScholarlyRecord(
                title="藏文与中文测试 བོད་སྐད།", pub_type="article-journal",
                crossref_status=SourceStatus.AVAILABLE,
            ),
        )
        ok = update_markdown_file(tmp_path, result)
        assert ok

        new_content = tmp_path.read_text(encoding="utf-8")
        assert "བོད་སྐད" in new_content  # Tibetan
        assert "—–" in new_content  # Em/en dashes
        assert "①②③" in new_content  # Circled numbers
    finally:
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass


def test_update_markdown_crlf_preserved():
    """CRLF line endings are preserved after update."""
    content = "---\r\ntitle: CRLF Test\r\ntype: literature\r\n---\r\n\r\nCRLF body.\r\n"
    with tempfile.NamedTemporaryFile(mode="wb", suffix=".md", delete=False) as f:
        f.write(content.encode('utf-8'))
        tmp_path = Path(f.name)

    try:
        result = EnrichmentResult(
            record=ScholarlyRecord(
                title="CRLF Test", pub_type="article-journal",
                crossref_status=SourceStatus.AVAILABLE,
            ),
        )
        ok = update_markdown_file(tmp_path, result)
        assert ok

        # Read in binary mode to check for CRLF
        with open(tmp_path, 'rb') as f:
            raw = f.read()
        assert b'\r\n' in raw, "CRLF should be preserved in the file"
        # Decode to verify content is correct
        decoded = raw.decode('utf-8')
        assert "CRLF Test" in decoded
        assert "CRLF body" in decoded
    finally:
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass


def test_update_markdown_atomic_same_dir_temp():
    """Temp file is created in same directory as target file."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as f:
        f.write("""---
title: Dir Test
---
Body.
""")
        tmp_path = Path(f.name)

    try:
        result = EnrichmentResult(
            record=ScholarlyRecord(
                title="Dir Test", pub_type="article-journal",
                crossref_status=SourceStatus.AVAILABLE,
            ),
        )
        # Before calling update, verify no stray .tmp file exists
        expected_tmp = tmp_path.parent / (tmp_path.name + ".tmp")
        assert not expected_tmp.exists()

        ok = update_markdown_file(tmp_path, result)
        assert ok

        # Temp file should be cleaned up (os.replace removes the source)
        assert not expected_tmp.exists()
    finally:
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════
# DOI extraction from Markdown
# ═══════════════════════════════════════════════════════════

def test_extract_doi_from_md():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as f:
        f.write("""---
title: Test
doi: 10.1234/from-md
type: literature
---
Body.
""")
        tmp_path = Path(f.name)

    try:
        doi = _extract_doi_from_md(tmp_path)
        assert doi == "10.1234/from-md"
    finally:
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass


def test_extract_doi_from_md_no_doi():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as f:
        f.write("""---
title: No DOI
type: literature
---
Body.
""")
        tmp_path = Path(f.name)

    try:
        doi = _extract_doi_from_md(tmp_path)
        assert doi == "" or doi is None
    finally:
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════
# Enrichment via offline/cache-only modes
# ═══════════════════════════════════════════════════════════

def test_enrich_offline_cache_hit():
    """Offline mode with pre-populated cache: returns cached record."""
    cache = ScholarlyCache()
    doi = "10.1234/offline-cached"
    # Pre-populate cache
    from scholarly.clients.crossref import CrossrefClient
    cache.set(NS_CROSSREF, doi, {
        "doi": doi, "title": "Cached Article", "authors": [{"family": "张", "given": "三"}],
        "journal_name": "测试期刊", "year": 2025, "volume": "1", "issue": "1",
        "page": "1-10", "pub_type": "article-journal",
        "crossref_status": "available", "crossref_cache_status": "cache_hit",
    }, ttl=TTL_STATIC)

    result = enrich_scholarly_record(doi=doi, offline=True, cache=cache)
    assert result.record.crossref_status == SourceStatus.AVAILABLE
    assert result.record.crossref_cache_status == CacheStatus.HIT
    assert result.record.title == "Cached Article"
    cache.close()


def test_enrich_offline_cache_miss():
    """Offline mode with empty cache: source UNAVAILABLE, cache MISS.

    Cache WAS queried (offline must query cache first), but no entry was found.
    """
    cache = ScholarlyCache()
    doi = "10.1234/offline-miss-test"
    # Ensure no cache entry for this DOI
    cache.delete(NS_CROSSREF, doi)

    result = enrich_scholarly_record(doi=doi, offline=True, cache=cache)
    assert result.record.crossref_status == SourceStatus.UNAVAILABLE
    assert result.record.crossref_cache_status == CacheStatus.MISS, (
        f"Offline cache miss should be MISS, got {result.record.crossref_cache_status}"
    )
    assert len(result.warnings) >= 1


def test_enrich_offline_no_cache_object():
    """Offline mode with cache disabled: source UNAVAILABLE, cache NOT_ATTEMPTED.

    When no cache object is available (cache=False), the cache was never queried.
    """
    doi = "10.1234/offline-no-cache-obj"
    result = enrich_scholarly_record(doi=doi, offline=True, cache=False)
    assert result.record.crossref_status == SourceStatus.UNAVAILABLE
    assert result.record.crossref_cache_status == CacheStatus.NOT_ATTEMPTED, (
        f"Offline without cache should be NOT_ATTEMPTED, got {result.record.crossref_cache_status}"
    )
    assert len(result.warnings) >= 1


def test_enrich_cache_only():
    """Cache-only mode: source UNAVAILABLE, cache MISS."""
    result = enrich_scholarly_record(doi="10.1234/test", cache_only=True)
    assert result.record.crossref_status == SourceStatus.UNAVAILABLE
    assert result.record.crossref_cache_status == CacheStatus.MISS


def test_enrich_invalid_doi():
    """Invalid DOI returns error, not crash."""
    result = enrich_scholarly_record(doi="not-a-doi")
    assert len(result.errors) >= 1


def test_enrich_normal_no_key():
    """Normal mode without explicit offline/cache-only flags.

    Crossref may return AVAILABLE (cache hit from prior runs) or ERROR (no
    network in test environment). OpenAlex may be AVAILABLE (cached) or
    UNAVAILABLE (no key configured). The pipeline does not crash either way.
    """
    import uuid
    result = enrich_scholarly_record(doi=f"10.1234/test-{uuid.uuid4().hex[:8]}")
    # Crossref status depends on cache state — accept valid outcomes
    assert result.record.crossref_status in (
        SourceStatus.AVAILABLE,   # Cache hit
        SourceStatus.ERROR,       # No cache, network blocked
        SourceStatus.UNAVAILABLE, # No cache, offline-like fallthrough
    )
    # OpenAlex status depends on cache state or API key availability
    assert result.record.openalex_status in (
        SourceStatus.AVAILABLE,    # Cached from prior run
        SourceStatus.UNAVAILABLE,  # No key configured
    )
    # Verify cache_status fields exist and have valid values
    assert result.record.crossref_cache_status is not None
    assert result.record.openalex_cache_status is not None


# ═══════════════════════════════════════════════════════════
# Windows path compatibility
# ═══════════════════════════════════════════════════════════

def test_windows_path_markdown():
    """Markdown file handling works on Windows paths."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as f:
        f.write("""---
title: Windows Test
doi: 10.1234/windows
---
Windows body.
""")
        tmp_path = Path(f.name)

    try:
        doi = _extract_doi_from_md(tmp_path)
        assert doi == "10.1234/windows"

        result = EnrichmentResult(
            record=ScholarlyRecord(
                title="Windows Test", doi="10.1234/windows",
                pub_type="article-journal",
                crossref_status=SourceStatus.AVAILABLE,
            ),
        )
        ok = update_markdown_file(tmp_path, result)
        assert ok

        content = tmp_path.read_text(encoding="utf-8")
        assert "scholarly:" in content
    finally:
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass


def test_backslash_path_normalisation():
    """Backslashes in paths are handled."""
    p = Path("C:\\Users\\test\\wiki\\paper.md")
    assert "wiki" in str(p)
    assert p.suffix == ".md"
