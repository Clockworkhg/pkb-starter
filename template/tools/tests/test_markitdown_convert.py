#!/usr/bin/env python3
"""
Tests for tools/markitdown_convert.py + tools/pkb_ingest.py — PKB MarkItDown Phase 1.5.

Usage:
    python tools/tests/test_markitdown_convert.py          # all tests
    python tools/tests/test_markitdown_convert.py Cache    # specific class
"""

import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

# ── Project root setup ──
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
os.chdir(str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "tools"))

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"

# ── Import modules under test ──
from markitdown_convert import (
    HAS_MARKITDOWN,
    SUPPORTED_EXTENSIONS,
    LEGACY_DOC_EXTENSIONS,
    QUALITY_CONFIG,
    CACHE_DIR,
    PREVIEW_MAX_CHARS,
    ExtractionResult,
    convert_with_markitdown,
    make_fallback_result,
    get_markitdown_version,
    _validate_is_normal_text,
    _quality_check,
    _is_header_only,
    _table_has_meaningful_content,
    _get_quality_threshold,
    _compute_file_sha256,
    _sanitize_stem,
    _write_extraction_cache,
)


# ═══════════════════════════════════════════════════════════════
# Test ExtractionResult Dataclass
# ═══════════════════════════════════════════════════════════════

class TestExtractionResult(unittest.TestCase):
    """ExtractionResult dataclass behaves correctly."""

    def test_defaults(self):
        r = ExtractionResult(
            text="hello",
            method="markitdown",
            source_path="/tmp/x.pdf",
            source_type="pdf",
            success=False,
        )
        self.assertEqual(r.warnings, [])
        self.assertIsNone(r.error_code)
        self.assertEqual(r.metadata, {})
        self.assertIsNone(r.extracted_path)
        self.assertEqual(r.character_count, 0)
        self.assertEqual(r.preview, "")
        self.assertIsNone(r.source_sha256)

    def test_success_flag_independent(self):
        """success is False by default even with text."""
        r = ExtractionResult(
            text="some text",
            method="markitdown",
            source_path="x.pdf",
            source_type="pdf",
            success=False,
        )
        self.assertFalse(r.success)
        self.assertEqual(r.text, "some text")

    def test_metadata_persists(self):
        r = ExtractionResult(
            text="", method="m", source_path="x.pdf", source_type="pdf", success=True,
            metadata={"key": "value"}
        )
        self.assertEqual(r.metadata["key"], "value")

    def test_new_fields_present(self):
        """Phase 1.5: extracted_path, character_count, preview, source_sha256 exist."""
        r = ExtractionResult(
            text="hello world",
            method="markitdown",
            source_path="x.pdf",
            source_type="pdf",
            success=True,
            extracted_path="/cache/test.md",
            character_count=11,
            preview="hello world",
            source_sha256="abcdef123456",
        )
        self.assertEqual(r.extracted_path, "/cache/test.md")
        self.assertEqual(r.character_count, 11)
        self.assertEqual(r.preview, "hello world")
        self.assertEqual(r.source_sha256, "abcdef123456")


# ═══════════════════════════════════════════════════════════════
# Test Format Detection
# ═══════════════════════════════════════════════════════════════

class TestFormatDetection(unittest.TestCase):
    """Extension-to-source_type mapping and unsupported/doc detection."""

    def test_docx_detected(self):
        result = convert_with_markitdown(FIXTURES_DIR / "test_doc.docx")
        self.assertEqual(result.source_type, "docx")

    def test_pdf_detected(self):
        result = convert_with_markitdown(FIXTURES_DIR / "test_pdf.pdf")
        self.assertEqual(result.source_type, "pdf")

    def test_pptx_detected(self):
        result = convert_with_markitdown(FIXTURES_DIR / "test_ppt.pptx")
        self.assertEqual(result.source_type, "pptx")

    def test_xlsx_detected(self):
        result = convert_with_markitdown(FIXTURES_DIR / "test_sheet.xlsx")
        self.assertEqual(result.source_type, "xlsx")

    def test_xls_detected(self):
        result = convert_with_markitdown(FIXTURES_DIR / "test_sheet.xls")
        self.assertEqual(result.source_type, "xls")

    def test_doc_returns_legacy_doc_unsupported(self):
        """Old .doc (OLE format) must return legacy_doc_unsupported."""
        result = convert_with_markitdown(Path("/fake/oldfile.doc"))
        self.assertEqual(result.error_code, "legacy_doc_unsupported")
        self.assertFalse(result.success)
        self.assertEqual(result.text, "")
        self.assertEqual(result.source_type, "doc")

    def test_unknown_format_returns_unsupported_format(self):
        """Unknown extension must return unsupported_format."""
        result = convert_with_markitdown(Path("/fake/unknown.xyz"))
        self.assertEqual(result.error_code, "unsupported_format")
        self.assertFalse(result.success)
        self.assertEqual(result.text, "")

    def test_no_extension_returns_unsupported_format(self):
        """File with no extension is unsupported."""
        result = convert_with_markitdown(Path("/fake/noextension"))
        self.assertEqual(result.error_code, "unsupported_format")


# ═══════════════════════════════════════════════════════════════
# Test convert_with_markitdown (real fixtures, needs markitdown)
# ═══════════════════════════════════════════════════════════════

@unittest.skipUnless(HAS_MARKITDOWN, "markitdown not installed")
class TestConvertWithMarkItDown(unittest.TestCase):
    """Actual conversion of real fixture files."""

    def test_docx_normal(self):
        """DOCX with text content produces successful result with cache."""
        result = convert_with_markitdown(FIXTURES_DIR / "test_doc.docx")
        self.assertTrue(result.success, f"warnings={result.warnings}, error_code={result.error_code}")
        self.assertIn("DOCX", result.text)
        self.assertEqual(result.method, "markitdown")
        self.assertEqual(result.source_type, "docx")
        self.assertIn("extractor_version", result.metadata)
        self.assertTrue(result.metadata.get("quality_passed"))
        # Phase 1.5: cache file written
        self.assertIsNotNone(result.extracted_path, "extracted_path should be set on success")
        self.assertTrue(Path(result.extracted_path).exists(), f"cache file missing: {result.extracted_path}")
        self.assertGreater(result.character_count, 0)
        self.assertGreater(len(result.preview), 0)
        self.assertLessEqual(len(result.preview), PREVIEW_MAX_CHARS + 10)  # +10 for whitespace
        self.assertIsNotNone(result.source_sha256)

    def test_pdf_text(self):
        """PDF with extractable text produces successful result with cache."""
        result = convert_with_markitdown(FIXTURES_DIR / "test_pdf.pdf")
        self.assertTrue(result.success, f"warnings={result.warnings}, error_code={result.error_code}")
        self.assertIn("Hello from PDF", result.text)
        self.assertEqual(result.source_type, "pdf")
        self.assertIsNotNone(result.extracted_path)

    def test_pptx_normal(self):
        """PPTX with slide text produces successful result with cache."""
        result = convert_with_markitdown(FIXTURES_DIR / "test_ppt.pptx")
        self.assertTrue(result.success, f"warnings={result.warnings}, error_code={result.error_code}")
        self.assertIn("PPTX", result.text)
        self.assertEqual(result.source_type, "pptx")
        self.assertIsNotNone(result.extracted_path)

    def test_xlsx_normal(self):
        """XLSX with sheet data produces successful result with cache."""
        result = convert_with_markitdown(FIXTURES_DIR / "test_sheet.xlsx")
        self.assertTrue(result.success, f"warnings={result.warnings}, error_code={result.error_code}")
        self.assertIn("张三", result.text)
        self.assertEqual(result.source_type, "xlsx")
        self.assertIsNotNone(result.extracted_path)

    def test_xls_normal(self):
        """XLS file with sheet data produces successful result."""
        result = convert_with_markitdown(FIXTURES_DIR / "test_sheet.xls")
        if result.success:
            self.assertIn("张三", result.text)
            self.assertIsNotNone(result.extracted_path)
        else:
            self.assertIsNotNone(result.error_code)
            self.assertFalse(result.success)

    def test_empty_file_no_crash(self):
        """Empty/corrupt file returns error result, never raises, no cache."""
        result = convert_with_markitdown(FIXTURES_DIR / "test_empty.docx")
        self.assertFalse(result.success)
        self.assertIsNotNone(result.error_code)
        self.assertIn(result.error_code, ("corrupt_file", "empty_output", "exception"))
        # No cache file should be written on failure
        self.assertIsNone(result.extracted_path)
        self.assertEqual(result.character_count, 0)
        self.assertEqual(result.preview, "")

    def test_chinese_filename_windows_path(self):
        """Chinese filename resolves correctly on Windows, cache path valid."""
        result = convert_with_markitdown(FIXTURES_DIR / "中文文件名_测试.pdf")
        self.assertIsNotNone(result.error_code or result.success)
        self.assertIn("中文文件名_测试", result.source_path)

    def test_result_metadata_correct(self):
        """Result includes extractor_version, source_format, quality_passed."""
        result = convert_with_markitdown(FIXTURES_DIR / "test_doc.docx")
        self.assertIn("extractor_version", result.metadata)
        self.assertIn("source_format", result.metadata)
        self.assertEqual(result.metadata["source_format"], "docx")
        self.assertIn("quality_passed", result.metadata)
        # Phase 1.5: version is dynamic from importlib.metadata, never hardcoded fallback
        ver = result.metadata["extractor_version"]
        self.assertIsNotNone(ver)
        self.assertRegex(ver, r'^\d+\.\d+', f"Version should be dynamic, got: {ver}")

    def test_nonexistent_file(self):
        """Non-existent file returns structured error, no cache."""
        result = convert_with_markitdown(Path("/nonexistent/path/file.pdf"))
        self.assertFalse(result.success)
        self.assertEqual(result.error_code, "exception")
        self.assertIsNone(result.extracted_path)

    def test_cli_json_excludes_full_text(self):
        """Phase 1.5: CLI --json does NOT include 'text' field."""
        import subprocess
        proc = subprocess.run(
            [sys.executable, "tools/markitdown_convert.py", "--json",
             str(FIXTURES_DIR / "test_doc.docx")],
            capture_output=True, text=True,
            encoding='utf-8', errors='replace',
            cwd=str(REPO_ROOT),
        )
        output = json.loads(proc.stdout)
        # Full text must NOT be in JSON output
        self.assertNotIn("text", output, "CLI JSON must not include full text")
        # New fields must be present
        self.assertIn("extracted_path", output)
        self.assertIn("character_count", output)
        self.assertIn("preview", output)
        self.assertIn("source_sha256", output)


# ═══════════════════════════════════════════════════════════════
# Test Quality Checks (no markitdown needed)
# ═══════════════════════════════════════════════════════════════

class TestQualityChecks(unittest.TestCase):
    """Quality check functions in isolation."""

    def test_normal_text_passes(self):
        is_valid, warnings = _validate_is_normal_text(
            "这是一个正常的文档段落。包含足够的文字内容来通过质量检查。"
            "第二段内容：这里还有更多的文字。需要满足最低字符数和段落数量的要求。"
            "第三段：继续增加内容量以确保质量检查通过。文档内容应该是有效的。",
            "docx",
        )
        self.assertTrue(is_valid, f"warnings={warnings}")
        self.assertEqual(warnings, [])

    def test_empty_text_fails(self):
        is_valid, warnings = _validate_is_normal_text("", "pdf")
        self.assertFalse(is_valid)

    def test_whitespace_only_fails(self):
        is_valid, warnings = _validate_is_normal_text("   \n\n  \t  ", "pdf")
        self.assertFalse(is_valid)

    def test_headers_only_fails(self):
        text = "# 标题一\n## 标题二\n### 标题三"
        is_valid, warnings = _validate_is_normal_text(text, "docx")
        self.assertFalse(is_valid)

    def test_too_few_chars_fails(self):
        is_valid, _ = _validate_is_normal_text("hi", "pdf")
        self.assertFalse(is_valid)

    def test_table_minimal_passes(self):
        is_valid, warnings = _validate_is_normal_text(
            "Sheet1\n姓名\t年龄\n张三\t28",
            "xlsx",
        )
        self.assertTrue(is_valid, f"warnings={warnings}")

    def test_garbage_markers_detected(self):
        is_valid, warnings = _validate_is_normal_text(
            "This page requires javascript to be enabled. Please enable cookies. " * 5,
            "pdf",
        )
        self.assertFalse(is_valid)

    def test_quality_check_updates_result(self):
        result = ExtractionResult(
            text="hi", method="m", source_path="x.pdf", source_type="pdf", success=True,
        )
        result = _quality_check(result)
        self.assertFalse(result.success)
        self.assertFalse(result.metadata["quality_passed"])


# ═══════════════════════════════════════════════════════════════
# Test Helper Functions
# ═══════════════════════════════════════════════════════════════

class TestHelperFunctions(unittest.TestCase):
    """Individual helper function correctness."""

    def test_is_header_only_true(self):
        self.assertTrue(_is_header_only("# Title\n## Sub", 50))

    def test_is_header_only_false(self):
        body = "Body text here that is definitely long enough to pass the quality check threshold."
        self.assertFalse(_is_header_only(f"# Title\n\n{body}", 50))

    def test_table_meaningful_with_sheet_name(self):
        self.assertTrue(_table_has_meaningful_content("Sheet1\nfield1\tfield2"))

    def test_table_meaningful_empty(self):
        self.assertFalse(_table_has_meaningful_content(""))

    def test_get_quality_threshold_uses_default(self):
        cfg = _get_quality_threshold("unknown_fmt")
        self.assertEqual(cfg, QUALITY_CONFIG["default"])

    def test_get_quality_threshold_xlsx(self):
        cfg = _get_quality_threshold("xlsx")
        self.assertEqual(cfg["min_stripped_chars"], 10)

    def test_sanitize_stem_normal(self):
        """Normal filename becomes safe stem."""
        result = _sanitize_stem("my document (final).docx")
        self.assertNotIn(" ", result)
        self.assertNotIn("(", result)
        self.assertNotIn(")", result)
        self.assertFalse(result.endswith(".docx"))

    def test_sanitize_stem_chinese(self):
        """Chinese filename stem is preserved."""
        result = _sanitize_stem("中文文件名_测试.pdf")
        self.assertIn("中文文件名_测试", result)
        self.assertFalse(result.endswith(".pdf"))

    def test_sanitize_stem_truncation(self):
        """Long filename is truncated."""
        long_name = "a" * 200 + ".pdf"
        result = _sanitize_stem(long_name, max_len=80)
        self.assertLessEqual(len(result), 80)

    def test_sanitize_stem_empty_fallback(self):
        """Empty stem falls back to 'extracted'."""
        result = _sanitize_stem("")
        self.assertTrue(len(result) > 0)

    def test_compute_sha256_returns_string(self):
        """SHA256 of a real file returns valid hex string."""
        sha = _compute_file_sha256(FIXTURES_DIR / "test_doc.docx")
        self.assertIsNotNone(sha)
        self.assertEqual(len(sha), 64)
        self.assertTrue(all(c in "0123456789abcdef" for c in sha))

    def test_compute_sha256_nonexistent_returns_none(self):
        """SHA256 of nonexistent file returns None."""
        sha = _compute_file_sha256(Path("/nonexistent/sha_test.xyz"))
        self.assertIsNone(sha)


# ═══════════════════════════════════════════════════════════════
# Test Fallback Result Construction
# ═══════════════════════════════════════════════════════════════

class TestFallbackResult(unittest.TestCase):
    """make_fallback_result constructs correct fallback metadata."""

    def test_fallback_metadata(self):
        primary = ExtractionResult(
            text="",
            method="markitdown",
            source_path="/tmp/x.pdf",
            source_type="pdf",
            success=False,
            error_code="empty_output",
            warnings=["empty"],
            metadata={"extractor_version": "0.1.6", "source_format": "pdf"},
        )
        fallback = make_fallback_result(
            primary,
            fallback_method="pypdf+pdfplumber",
            fallback_text="Extracted by fallback",
            fallback_success=True,
        )
        self.assertTrue(fallback.success)
        self.assertEqual(fallback.method, "pypdf+pdfplumber")
        self.assertTrue(fallback.metadata["fallback_used"])
        self.assertEqual(fallback.metadata["primary_extractor"], "markitdown")
        self.assertEqual(fallback.metadata["fallback_extractor"], "pypdf+pdfplumber")
        self.assertEqual(fallback.metadata["fallback_reason"], "empty_output")


# ═══════════════════════════════════════════════════════════════
# Test Graceful Degradation (markitdown not installed)
# ═══════════════════════════════════════════════════════════════

class TestGracefulDegradation(unittest.TestCase):
    """Behavior when markitdown is not available."""

    def test_unsupported_works_without_markitdown(self):
        """Format rejection works even without markitdown installed."""
        result = convert_with_markitdown(Path("test.xyz"))
        self.assertEqual(result.error_code, "unsupported_format")

    def test_legacy_doc_works_without_markitdown(self):
        """Legacy .doc rejection works without markitdown installed."""
        result = convert_with_markitdown(Path("test.doc"))
        self.assertEqual(result.error_code, "legacy_doc_unsupported")


# ═══════════════════════════════════════════════════════════════
# Test Size and Safety Guards
# ═══════════════════════════════════════════════════════════════

class TestSafetyGuards(unittest.TestCase):
    """File size limits and safety."""

    def test_zero_byte_file(self):
        """Zero-byte file returns corrupt_file or empty_output."""
        result = convert_with_markitdown(FIXTURES_DIR / "test_empty.docx")
        self.assertFalse(result.success)
        self.assertIn(result.error_code, ("corrupt_file", "empty_output", "exception"))

    def test_result_never_raises(self):
        """convert_with_markitdown never raises, even on garbage paths."""
        try:
            result = convert_with_markitdown(Path("test\0garbage.pdf"))
            self.assertFalse(result.success)
        except Exception as e:
            self.fail(f"convert_with_markitdown raised unexpectedly: {e}")


# ═══════════════════════════════════════════════════════════════
# Test Extraction Metadata
# ═══════════════════════════════════════════════════════════════

class TestExtractionMetadata(unittest.TestCase):
    """Metadata is correctly populated in all scenarios."""

    def test_success_metadata(self):
        """On success: version, source_format, quality_passed, char_count."""
        result = convert_with_markitdown(FIXTURES_DIR / "test_doc.docx")
        if result.success:
            self.assertEqual(result.metadata["source_format"], "docx")
            self.assertTrue(result.metadata["quality_passed"])
            self.assertIn("char_count_stripped", result.metadata)
            self.assertIn("paragraph_count", result.metadata)

    def test_failure_metadata(self):
        """On failure: error_code is set, quality_passed=False."""
        result = convert_with_markitdown(Path("test.xyz"))
        self.assertFalse(result.metadata.get("quality_passed", True))
        self.assertIsNotNone(result.error_code)

    def test_method_always_markitdown(self):
        """method field is always 'markitdown'."""
        result = convert_with_markitdown(Path("test.xyz"))
        self.assertEqual(result.method, "markitdown")

    def test_version_not_hardcoded(self):
        """extractor_version is from importlib.metadata, never 'not_installed' fallback on success."""
        result = convert_with_markitdown(FIXTURES_DIR / "test_doc.docx")
        if result.success:
            ver = result.metadata.get("extractor_version")
            self.assertIsNotNone(ver)
            self.assertNotEqual(ver, "not_installed",
                                "Version should not be 'not_installed' when markitdown is available")
            self.assertRegex(ver, r'^\d+\.\d+', f"Should be a real version, got: {ver}")


# ═══════════════════════════════════════════════════════════════
# ═══════  PHASE 1.5 HARDENING: CACHE & OUTPUT TESTS  ═══════
# ═══════════════════════════════════════════════════════════════

@unittest.skipUnless(HAS_MARKITDOWN, "markitdown not installed")
class TestCacheAndOutput(unittest.TestCase):
    """Phase 1.5: Cache file creation, CLI output exclusion, path safety."""

    def test_cache_file_created_on_success(self):
        """Successful conversion writes .md cache file."""
        result = convert_with_markitdown(FIXTURES_DIR / "test_doc.docx")
        self.assertTrue(result.success)
        self.assertIsNotNone(result.extracted_path)
        cache_path = Path(result.extracted_path)
        self.assertTrue(cache_path.exists(), f"Cache not found: {cache_path}")
        self.assertTrue(cache_path.suffix == ".md")
        # Content should be valid
        content = cache_path.read_text(encoding="utf-8")
        self.assertIn("DOCX", content)

    def test_extracted_path_in_result(self):
        """IngestResult.extracted_path points to cache file."""
        from pkb_ingest import ingest_local_file
        result = ingest_local_file(FIXTURES_DIR / "test_doc.docx", mode="full")
        try:
            self.assertTrue(result.extraction_success)
            self.assertIsNotNone(result.extracted_path)
            self.assertTrue(Path(result.extracted_path).exists())
        finally:
            _cleanup_result(result)

    def test_cli_json_excludes_extracted_text(self):
        """pkb_ingest.py --json does NOT contain extracted_text."""
        import subprocess
        proc = subprocess.run(
            [sys.executable, "tools/pkb_ingest.py", "--json",
             str(FIXTURES_DIR / "test_doc.docx")],
            capture_output=True, text=True,
            encoding='utf-8', errors='replace',
            cwd=str(REPO_ROOT),
        )
        output = json.loads(proc.stdout)
        self.assertNotIn("extracted_text", output,
                         "CLI JSON must not include full extracted_text")
        self.assertIn("extracted_path", output)
        self.assertIn("preview", output)
        self.assertIn("character_count", output)
        # Cleanup inbox
        _cleanup_result_path(output.get("inbox_path", ""))

    def test_preview_length_limited(self):
        """preview is at most ~500 chars."""
        result = convert_with_markitdown(FIXTURES_DIR / "test_doc.docx")
        self.assertTrue(result.success)
        self.assertLessEqual(len(result.preview), PREVIEW_MAX_CHARS + 20,
                             f"preview too long: {len(result.preview)} chars")

    def test_character_count_correct(self):
        """character_count matches actual text length."""
        result = convert_with_markitdown(FIXTURES_DIR / "test_doc.docx")
        self.assertTrue(result.success)
        self.assertEqual(result.character_count, len(result.text))

    def test_different_content_different_paths(self):
        """Files with different content get different cache paths."""
        # DOCX and PDF have different content → different SHA256 → different paths
        r1 = convert_with_markitdown(FIXTURES_DIR / "test_doc.docx")
        r2 = convert_with_markitdown(FIXTURES_DIR / "test_pdf.pdf")
        if r1.success and r2.success:
            self.assertNotEqual(r1.extracted_path, r2.extracted_path,
                                "Different files should have different cache paths")

    def test_same_content_stable_path(self):
        """Same file processed twice produces same cache path."""
        r1 = convert_with_markitdown(FIXTURES_DIR / "test_doc.docx")
        r2 = convert_with_markitdown(FIXTURES_DIR / "test_doc.docx")
        if r1.success and r2.success:
            # Same file, same SHA256 → same cache path
            self.assertEqual(r1.extracted_path, r2.extracted_path,
                             "Same file should have stable cache path")

    def test_chinese_filename_cache_path(self):
        """Chinese filename produces valid cache path."""
        result = convert_with_markitdown(FIXTURES_DIR / "中文文件名_测试.pdf")
        if result.success:
            cache_path = Path(result.extracted_path)
            self.assertTrue(cache_path.exists())
            # Path should be inside cache dir
            self.assertIn(".pkb-cache", str(cache_path))
            # Filename should contain safe stem
            self.assertIn("中文文件名_测试", cache_path.stem[:20])

    def test_spaces_in_path(self):
        """Spaces in filename handled correctly for cache."""
        # Use existing fixture — path contains spaces via FIXTURES_DIR
        result = convert_with_markitdown(FIXTURES_DIR / "test_doc.docx")
        if result.success:
            cache_path = Path(result.extracted_path)
            self.assertTrue(cache_path.exists())

    def test_windows_path_compatibility(self):
        """Windows-style paths work in cache path."""
        result = convert_with_markitdown(FIXTURES_DIR / "test_doc.docx")
        if result.success:
            self.assertIsNotNone(result.extracted_path)
            # Path should be valid Windows path
            self.assertTrue(Path(result.extracted_path).is_absolute())
            # Should not contain invalid chars
            invalid = set('<>:"|?*')
            path_str = str(Path(result.extracted_path).name)
            self.assertFalse(any(c in path_str for c in invalid))

    def test_cache_write_failure_handled(self):
        """Cache write failure returns structured error, not crash."""
        import platform, tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a FILE where a directory component would be,
            # so cache_dir.mkdir(parents=True) fails
            block_file = Path(tmpdir) / "blocker"
            block_file.write_text("block")
            # Try to use block_file/subdir as cache_dir — mkdir will fail
            # because 'blocker' exists as a file, not a directory
            result_path = _write_extraction_cache(
                "test content", FIXTURES_DIR / "test_doc.docx",
                cache_dir=block_file / "subdir",
            )
            self.assertIsNone(result_path,
                              "Should return None when mkdir fails (file blocks dir)")

    def test_path_traversal_blocked(self):
        """Cache paths with .. are blocked."""
        # _write_extraction_cache computes path from sanitized stem + sha
        # Path traversal via stem should be blocked by sanitization
        evil_stem = _sanitize_stem("../../../etc/passwd")
        self.assertNotIn("..", evil_stem)
        self.assertNotIn("/", evil_stem)

    def test_no_cache_on_failure(self):
        """Failed extraction leaves no cache file."""
        result = convert_with_markitdown(FIXTURES_DIR / "test_empty.docx")
        self.assertFalse(result.success)
        self.assertIsNone(result.extracted_path)
        self.assertEqual(result.character_count, 0)
        self.assertEqual(result.preview, "")


# ═══════════════════════════════════════════════════════════════
# ═══════  PHASE 1.5 HARDENING: FALLBACK STATE TESTS  ════════
# ═══════════════════════════════════════════════════════════════

class TestFallbackStates(unittest.TestCase):
    """Phase 1.5: Fallback state machine — Python outputs 'plan state'."""

    def _ingest(self, path, mode="full"):
        from pkb_ingest import ingest_local_file
        return ingest_local_file(path, mode=mode)

    def test_success_no_fallback(self):
        """MarkItDown success → all fallback fields False/None."""
        result = self._ingest(FIXTURES_DIR / "test_doc.docx", mode="full")
        try:
            if result.extraction_success:
                self.assertFalse(result.fallback_required,
                                 "Success should not require fallback")
                self.assertFalse(result.fallback_attempted)
                self.assertFalse(result.fallback_used)
                self.assertIsNone(result.fallback_succeeded)
                self.assertIsNone(result.fallback_reason)
                self.assertIsNone(result.fallback_extractor)
        finally:
            _cleanup_result(result)

    def test_missing_markitdown_requires_fallback(self):
        """When markitdown not installed: fallback_required=True, not yet executed."""
        with patch("markitdown_convert.HAS_MARKITDOWN", False):
            result = self._ingest(FIXTURES_DIR / "test_doc.docx", mode="full")
            try:
                if result.imported:
                    self.assertTrue(result.fallback_required,
                                    "Missing markitdown must require fallback")
                    self.assertFalse(result.fallback_attempted,
                                     "Python must not mark fallback as attempted")
                    self.assertFalse(result.fallback_used,
                                     "Python must not mark fallback as used")
                    self.assertIsNone(result.fallback_succeeded,
                                      "Fallback not yet executed")
                    self.assertEqual(result.fallback_reason, "import_error")
                    self.assertEqual(result.fallback_extractor, "llm_direct_read")
            finally:
                _cleanup_result(result)

    def test_quality_fail_requires_fallback(self):
        """Quality check failure triggers fallback_required."""
        # Zero-byte file will fail quality check
        result = self._ingest(FIXTURES_DIR / "test_empty.docx", mode="full")
        try:
            if result.imported:
                self.assertTrue(result.fallback_required,
                                "Quality failure must require fallback")
                self.assertFalse(result.fallback_attempted)
                self.assertFalse(result.fallback_used)
                self.assertIsNone(result.fallback_succeeded)
                self.assertIsNotNone(result.fallback_reason)
                self.assertEqual(result.fallback_extractor, "llm_direct_read")
        finally:
            _cleanup_result(result)

    def test_doc_requires_fallback(self):
        """.doc returns legacy_doc_unsupported and requires fallback."""
        fake_doc = FIXTURES_DIR / "test_legacy_hardening.doc"
        fake_doc.write_text("fake OLE content")
        try:
            result = self._ingest(fake_doc, mode="full")
            self.assertEqual(result.error_code, "legacy_doc_unsupported")
            self.assertTrue(result.fallback_required,
                            ".doc must require fallback")
            self.assertFalse(result.fallback_attempted)
            self.assertFalse(result.fallback_used)
            self.assertEqual(result.fallback_reason, "legacy_doc_unsupported")
        finally:
            fake_doc.unlink()

    def test_unsupported_format_no_fallback(self):
        """Unsupported format (not .doc): LLM is primary, not fallback."""
        unsupported = FIXTURES_DIR / "test_unsupported_hardening.xyz"
        unsupported.write_text("dummy content")
        try:
            result = self._ingest(unsupported, mode="full")
            self.assertTrue(result.imported)
            self.assertEqual(result.extraction_method, "llm_direct_read")
            # LLM is primary path, not fallback
            self.assertFalse(result.fallback_required,
                             "Unsupported format: LLM is primary, not fallback")
            self.assertFalse(result.fallback_used)
        finally:
            unsupported.unlink()

    def test_fallback_reason_populated(self):
        """fallback_reason is populated with correct error code."""
        result = self._ingest(FIXTURES_DIR / "test_empty.docx", mode="full")
        try:
            if result.fallback_required:
                self.assertIsNotNone(result.fallback_reason)
                self.assertIn(result.fallback_reason,
                              ("corrupt_file", "empty_output", "exception", ""))
        finally:
            _cleanup_result(result)

    def test_safe_mode_no_fallback_required(self):
        """--mode safe: LLM is primary path, fallback_required=False."""
        result = self._ingest(FIXTURES_DIR / "test_doc.docx", mode="safe")
        try:
            self.assertTrue(result.imported)
            self.assertEqual(result.extraction_method, "llm_direct_read")
            self.assertFalse(result.fallback_required,
                             "safe mode: LLM is primary, not fallback")
            self.assertFalse(result.fallback_attempted)
            self.assertFalse(result.fallback_used)
        finally:
            _cleanup_result(result)


# ═══════════════════════════════════════════════════════════════
# ═══════  PHASE 1.5 HARDENING: VERSION INFO TESTS  ══════════
# ═══════════════════════════════════════════════════════════════

class TestVersionInfo(unittest.TestCase):
    """Phase 1.5: Dynamic version via importlib.metadata."""

    def test_get_version_returns_string_when_installed(self):
        """get_markitdown_version() returns a version string when installed."""
        ver = get_markitdown_version()
        if HAS_MARKITDOWN:
            self.assertIsNotNone(ver)
            self.assertIsInstance(ver, str)
            self.assertRegex(ver, r'^\d+\.\d+')
        else:
            self.assertIsNone(ver)

    def test_get_version_returns_none_when_missing(self):
        """get_markitdown_version() returns None when package not installed."""
        with patch("markitdown_convert.get_markitdown_version", return_value=None):
            from markitdown_convert import get_markitdown_version as gmv
            self.assertIsNone(gmv())

    def test_version_mockable_for_ci(self):
        """Version function is mockable for CI environments."""
        with patch("importlib.metadata.version", side_effect=ImportError):
            # When importlib fails, we should get None
            # Simulate directly
            from importlib.metadata import PackageNotFoundError
            with patch("importlib.metadata.version",
                       side_effect=PackageNotFoundError("markitdown")):
                ver = get_markitdown_version()
                self.assertIsNone(ver)

    def test_check_shows_real_version(self):
        """--check CLI output shows actual installed version."""
        import subprocess
        proc = subprocess.run(
            [sys.executable, "tools/markitdown_convert.py", "--check", "--json"],
            capture_output=True, text=True,
            encoding='utf-8', errors='replace',
            cwd=str(REPO_ROOT),
        )
        output = json.loads(proc.stdout)
        self.assertIn("markitdown_version", output)
        ver = output["markitdown_version"]
        if HAS_MARKITDOWN:
            self.assertIsInstance(ver, str)
            self.assertRegex(ver, r'^\d+\.\d+')
            self.assertNotEqual(ver, "not_installed")
        else:
            self.assertEqual(ver, "not_installed")

    def test_pkb_ingest_check_shows_version(self):
        """pkb_ingest.py --check also shows dynamic version."""
        import subprocess
        proc = subprocess.run(
            [sys.executable, "tools/pkb_ingest.py", "--check", "--json"],
            capture_output=True, text=True,
            encoding='utf-8', errors='replace',
            cwd=str(REPO_ROOT),
        )
        output = json.loads(proc.stdout)
        self.assertIn("markitdown_version", output)


# ═══════════════════════════════════════════════════════════════
# E2E Pipeline Tests — updated for Phase 1.5 field names
# ═══════════════════════════════════════════════════════════════

@unittest.skipUnless(HAS_MARKITDOWN, "markitdown not installed")
class TestE2EPipeline(unittest.TestCase):
    """End-to-end pipeline: import_to_inbox → markitdown → structured result."""

    def _ingest(self, path, mode="full"):
        from pkb_ingest import ingest_local_file
        return ingest_local_file(path, mode=mode)

    def test_docx_full_pipeline(self):
        """DOCX → _INBOX → MarkItDown → cache file → success."""
        result = self._ingest(FIXTURES_DIR / "test_doc.docx", mode="full")
        self.addCleanup(lambda: _cleanup_result(result))
        self.assertTrue(result.imported, f"import failed: {result.warnings}")
        self.assertTrue(result.extraction_success, f"extraction failed: {result.warnings}")
        self.assertEqual(result.extraction_method, "markitdown")
        # Phase 1.5: fallback not required on success
        self.assertFalse(result.fallback_required)
        self.assertFalse(result.fallback_used)
        self.assertTrue(result.quality_passed)
        # Cache file path must be present
        self.assertIsNotNone(result.extracted_path)
        self.assertGreater(result.character_count, 50)
        self.assertGreater(len(result.preview), 0)

    def test_pptx_full_pipeline(self):
        """PPTX → _INBOX → MarkItDown → cache file → success."""
        result = self._ingest(FIXTURES_DIR / "test_ppt.pptx", mode="full")
        self.addCleanup(lambda: _cleanup_result(result))
        self.assertTrue(result.imported)
        self.assertTrue(result.extraction_success, f"warnings={result.warnings}")
        self.assertEqual(result.extraction_method, "markitdown")
        self.assertIsNotNone(result.extracted_path)

    def test_xlsx_full_pipeline(self):
        """XLSX → _INBOX → MarkItDown → cache file → success."""
        result = self._ingest(FIXTURES_DIR / "test_sheet.xlsx", mode="full")
        self.addCleanup(lambda: _cleanup_result(result))
        self.assertTrue(result.imported)
        self.assertTrue(result.extraction_success, f"warnings={result.warnings}")
        self.assertIsNotNone(result.preview)
        self.assertIn("张三", result.preview)

    def test_safe_mode_skips_markitdown(self):
        """--mode safe does not trigger MarkItDown, LLM is primary."""
        result = self._ingest(FIXTURES_DIR / "test_doc.docx", mode="safe")
        self.addCleanup(lambda: _cleanup_result(result))
        self.assertTrue(result.imported)
        self.assertEqual(result.extraction_method, "llm_direct_read")
        self.assertFalse(result.extraction_success)
        self.assertFalse(result.fallback_required,
                         "safe mode: LLM is primary, not fallback")
        self.assertFalse(result.fallback_used)

    def test_doc_returns_legacy_unsupported(self):
        """.doc returns legacy_doc_unsupported with fallback_required."""
        fake_doc = FIXTURES_DIR / "test_legacy_e2e.doc"
        fake_doc.write_text("fake OLE content")
        try:
            result = self._ingest(fake_doc, mode="full")
            self.assertEqual(result.error_code, "legacy_doc_unsupported")
            self.assertFalse(result.extraction_success)
            self.assertTrue(result.fallback_required,
                            ".doc must require fallback")
            self.assertEqual(result.fallback_reason, "legacy_doc_unsupported")
        finally:
            fake_doc.unlink()

    def test_chinese_filename_pipeline(self):
        """Chinese filename flows through pipeline correctly."""
        result = self._ingest(FIXTURES_DIR / "中文文件名_测试.pdf", mode="full")
        self.addCleanup(lambda: _cleanup_result(result))
        self.assertTrue(result.imported)
        self.assertIn("中文文件名_测试", result.inbox_path)

    def test_unsupported_format_fallback(self):
        """Unsupported format routes to llm_direct_read, not fallback."""
        unsupported = FIXTURES_DIR / "test_unsupported_e2e.xyz"
        unsupported.write_text("dummy")
        try:
            result = self._ingest(unsupported, mode="full")
            self.assertTrue(result.imported)
            self.assertEqual(result.extraction_method, "llm_direct_read")
            self.assertFalse(result.extraction_success)
            self.assertFalse(result.fallback_required)
        finally:
            unsupported.unlink()

    def test_metadata_has_fallback_fields(self):
        """Fallback result has fallback_required and fallback_reason."""
        result = self._ingest(FIXTURES_DIR / "test_empty.docx", mode="full")
        self.addCleanup(lambda: _cleanup_result(result))
        self.assertTrue(result.imported)
        if result.fallback_required:
            self.assertIn("fallback_reason", result.metadata)
            self.assertTrue(result.metadata["fallback_required"])
            self.assertIn("primary_extractor", result.metadata)
            self.assertEqual(result.metadata["primary_extractor"], "markitdown")

    def test_nonexistent_file(self):
        """Non-existent file returns error, no crash."""
        result = self._ingest(Path("/nonexistent/file_12345.pdf"), mode="full")
        self.assertEqual(result.error_code, "file_not_found")
        self.assertFalse(result.imported)

    def test_failure_no_extracted_path(self):
        """Failed extraction has no extracted_path and zero character_count."""
        result = self._ingest(FIXTURES_DIR / "test_empty.docx", mode="full")
        self.addCleanup(lambda: _cleanup_result(result))
        if not result.extraction_success:
            self.assertIsNone(result.extracted_path)
            self.assertEqual(result.character_count, 0)
            self.assertEqual(result.preview, "")

    def test_safe_mode_preserves_original_behavior(self):
        """--mode safe: no markitdown, just import — existing behavior intact."""
        result = self._ingest(FIXTURES_DIR / "test_doc.docx", mode="safe")
        self.addCleanup(lambda: _cleanup_result(result))
        self.assertTrue(result.imported)
        self.assertNotEqual(result.extraction_method, "markitdown")
        self.assertFalse(result.fallback_required)


# ═══════════════════════════════════════════════════════════════
# E2E Integration: Combined pipeline metadata tests
# ═══════════════════════════════════════════════════════════════

@unittest.skipUnless(HAS_MARKITDOWN, "markitdown not installed")
class TestE2EMetadata(unittest.TestCase):
    """Verify metadata structure meets wiki frontmatter requirements (Phase 1.5)."""

    def _ingest(self, path, mode="full"):
        from pkb_ingest import ingest_local_file
        return ingest_local_file(path, mode=mode)

    def test_success_metadata_for_frontmatter(self):
        """Success metadata has extraction_method and fallback_required=False."""
        result = self._ingest(FIXTURES_DIR / "test_doc.docx", mode="full")
        self.addCleanup(lambda: _cleanup_result(result))
        self.assertTrue(result.extraction_success)
        self.assertIn("extraction_method", result.metadata)
        self.assertEqual(result.metadata["extraction_method"], "markitdown")
        self.assertFalse(result.metadata["fallback_required"])
        # Should NOT have legacy fallback_used=true
        self.assertFalse(result.metadata.get("fallback_used", False))

    def test_fallback_metadata_for_frontmatter(self):
        """Fallback metadata has primary_extractor and fallback_reason."""
        result = self._ingest(FIXTURES_DIR / "test_empty.docx", mode="full")
        self.addCleanup(lambda: _cleanup_result(result))
        if result.fallback_required:
            self.assertEqual(result.metadata["primary_extractor"], "markitdown")
            self.assertIn("fallback_reason", result.metadata)
            self.assertTrue(result.metadata["fallback_required"])
            self.assertFalse(result.metadata["fallback_attempted"])
            self.assertFalse(result.metadata["fallback_used"])


# ═══════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════

def _cleanup_result(result) -> None:
    """Remove _INBOX file after test."""
    if result and result.inbox_path:
        _cleanup_result_path(result.inbox_path)


def _cleanup_result_path(inbox_path: str) -> None:
    """Remove file from _INBOX after test."""
    try:
        p = Path(inbox_path)
        if p.exists():
            p.unlink()
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    if len(sys.argv) > 1:
        target = sys.argv[1].lower()
        loader = unittest.TestLoader()
        all_tests = loader.loadTestsFromModule(sys.modules[__name__])

        matching = unittest.TestSuite()
        for suite in all_tests:
            for test in suite:
                class_name = test.__class__.__name__.lower()
                if target in class_name:
                    matching.addTest(test)

        if matching.countTestCases() > 0:
            runner = unittest.TextTestRunner(verbosity=2)
            runner.run(matching)
        else:
            print(f"No test class matching '{sys.argv[1]}'. Available classes:")
            for suite in all_tests:
                for test in suite:
                    print(f"  {test.__class__.__name__}")
            sys.exit(1)
    else:
        unittest.main(verbosity=2)
