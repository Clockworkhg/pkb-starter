#!/usr/bin/env python3
"""
PKB MarkItDown 文档预提取器 — Phase 1.5 硬化。

将本地文档（PDF/DOCX/PPTX/XLSX/XLS）转为 Markdown，
作为 PKB 知识库管线的可选中预处理步骤。

用法:
    python tools/markitdown_convert.py <文件路径>
    python tools/markitdown_convert.py --json <文件路径>   # JSON（不含完整正文）
    python tools/markitdown_convert.py --check              # 依赖预检

Python 调用:
    from tools.markitdown_convert import convert_with_markitdown, ExtractionResult
    result = convert_with_markitdown(Path("document.pdf"))
    if result.success:
        print(result.preview)          # 短预览
        print(result.extracted_path)   # 缓存文件路径

依赖 (Phase 1.5):
    pip install "markitdown[pdf,docx,pptx,xlsx,xls]==0.1.6"

不支持 (Phase 1.5):
    - 旧版 .doc (OLE 格式) — 返回 legacy_doc_unsupported
    - OCR / OpenAI / Azure / 音频 / YouTube / ZIP
    - 非本地文件路径
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import tempfile
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# ── 编码: Windows 兼容 ──
sys.stdout.reconfigure(encoding='utf-8', errors='replace')  # type: ignore[attr-defined]

# ── 项目根 ──
_PKB_ROOT = Path(__file__).resolve().parent.parent

# ── 缓存目录 ──
CACHE_DIR = _PKB_ROOT / ".pkb-cache" / "extractions"

# ── 预览最大字符数 ──
PREVIEW_MAX_CHARS = 500

# ───────────────────────────────────────────────────────────────
# 依赖检测
# ───────────────────────────────────────────────────────────────

HAS_MARKITDOWN = False
_IS_PYTHON_310_PLUS = sys.version_info >= (3, 10)

try:
    from markitdown import MarkItDown  # noqa: F401
    HAS_MARKITDOWN = True
except ImportError:
    pass

# Python 版本保护: markitdown 0.1.6 需要 >= 3.10
if HAS_MARKITDOWN and not _IS_PYTHON_310_PLUS:
    HAS_MARKITDOWN = False


def get_markitdown_version() -> Optional[str]:
    """通过 importlib.metadata 读取实际安装的 markitdown 版本。

    Returns:
        版本字符串，例如 "0.1.6"；未安装时返回 None。
        绝不抛出异常。
    """
    try:
        from importlib.metadata import version as _pkg_version, PackageNotFoundError
        return _pkg_version("markitdown")
    except Exception:
        return None


# ───────────────────────────────────────────────────────────────
# ExtractionResult
# ───────────────────────────────────────────────────────────────

@dataclass
class ExtractionResult:
    """结构化提取结果。

    完整正文保存在 .pkb-cache/extractions/ 缓存文件中。
    text 字段仅在内存中用于管线内部传递，CLI 序列化时排除。
    """

    text: str                              # 提取的 Markdown 文本（内存使用，失败时为空）
    method: str                            # 提取方法标识，如 "markitdown"
    source_path: str                       # 源文件绝对路径
    source_type: str                       # 小写扩展名: pdf / docx / pptx / xlsx / xls
    success: bool                          # quality_passed 且无致命错误
    extracted_path: Optional[str] = None   # 缓存文件路径（成功时填充）
    character_count: int = 0               # 完整转换结果字符数
    preview: str = ""                      # 短预览（最多 500 可见字符）
    source_sha256: Optional[str] = None    # 源文件 SHA256 前 12 位
    warnings: list[str] = field(default_factory=list)
    error_code: Optional[str] = None       # None=成功, 否则为错误码
    metadata: dict = field(default_factory=dict)


# ───────────────────────────────────────────────────────────────
# 格式映射
# ───────────────────────────────────────────────────────────────

SUPPORTED_EXTENSIONS: dict[str, str] = {
    ".pdf":  "pdf",
    ".docx": "docx",
    ".pptx": "pptx",
    ".xlsx": "xlsx",
    ".xls":  "xls",
}

LEGACY_DOC_EXTENSIONS = frozenset({".doc"})

# 最大单文件大小
MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB


# ───────────────────────────────────────────────────────────────
# 缓存工具函数
# ───────────────────────────────────────────────────────────────

def _compute_file_sha256(path: Path) -> Optional[str]:
    """计算文件内容的 SHA256 哈希。

    Returns:
        十六进制摘要字符串；读取失败时返回 None。
    """
    try:
        sha = hashlib.sha256()
        with open(path, 'rb') as f:
            while True:
                chunk = f.read(65536)  # 64 KiB chunks
                if not chunk:
                    break
                sha.update(chunk)
        return sha.hexdigest()
    except Exception:
        return None


def _sanitize_stem(name: str, max_len: int = 80) -> str:
    """清理文件名 stem，保留安全字符。

    替换非 [\\w\\-_.] 字符为 '_'，限制长度。
    """
    # 去掉扩展名（如果包含）
    stem = Path(name).stem or name
    # 替换不安全字符
    safe = re.sub(r'[^\w\-_.]', '_', stem, flags=re.UNICODE)
    # 移除连续下划线
    safe = re.sub(r'_+', '_', safe)
    # 去掉首尾下划线
    safe = safe.strip('_')
    # 限制长度
    if len(safe) > max_len:
        safe = safe[:max_len].rstrip('_')
    # 空 stem 回退
    if not safe:
        safe = "extracted"
    return safe


def _write_extraction_cache(
    text: str,
    source_path: Path,
    cache_dir: Optional[Path] = None,
) -> Optional[Path]:
    """将提取文本写入缓存文件。

    文件名: <safe_stem>-<sha256_前12位>.md
    使用临时文件 + 原子替换，避免半写入文件残留。

    Args:
        text: 待写入的 Markdown 文本。
        source_path: 源文件路径（用于计算 SHA256 和生成文件名）。
        cache_dir: 缓存目录，默认为 CACHE_DIR。

    Returns:
        写入成功返回 Path；失败返回 None。
    """
    if cache_dir is None:
        cache_dir = CACHE_DIR

    try:
        # 确保目录存在
        cache_dir.mkdir(parents=True, exist_ok=True)

        # 计算源文件 SHA256
        file_sha = _compute_file_sha256(source_path)
        if file_sha is None:
            return None

        sha_prefix = file_sha[:12]
        safe_stem = _sanitize_stem(source_path.name, max_len=80)

        filename = f"{safe_stem}-{sha_prefix}.md"
        target_path = cache_dir / filename

        # 安全检查: 确保输出路径在缓存目录内
        resolved = target_path.resolve()
        cache_resolved = cache_dir.resolve()
        if not str(resolved).startswith(str(cache_resolved)):
            return None

        # 原子写入: 临时文件 + os.replace
        fd, tmp_path = tempfile.mkstemp(
            suffix=".md",
            prefix=".extract_",
            dir=str(cache_dir),
        )
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                f.write(text)
            os.replace(tmp_path, str(resolved))
        except Exception:
            # 清理临时文件
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

        return resolved

    except Exception:
        return None


# ───────────────────────────────────────────────────────────────
# 质量检查配置（集中管理，按 source_type 区分阈值）
# ───────────────────────────────────────────────────────────────

QUALITY_CONFIG: dict = {
    "default": {
        "min_stripped_chars": 50,
        "min_paragraphs": 1,
        "min_visible_text_ratio": 0.3,
    },
    "xlsx": {
        "min_stripped_chars": 10,
        "min_paragraphs": 0,
        "min_visible_text_ratio": 0.1,
        "min_sheet_indicators": 1,
    },
    "xls": {
        "min_stripped_chars": 10,
        "min_paragraphs": 0,
        "min_visible_text_ratio": 0.1,
        "min_sheet_indicators": 1,
    },
    "pptx": {
        "min_stripped_chars": 30,
        "min_paragraphs": 0,
        "min_visible_text_ratio": 0.3,
    },
}

CONVERSION_ERROR_MARKERS: list[str] = [
    "enable javascript",
    "javascript is not available",
    "this browser is no longer supported",
    "something went wrong",
    "please enable cookies",
    "access denied",
    "checking your browser",
    "just a moment",
    "performing security verification",
    "requiring captcha",
    "verify you are human",
    "log in to",
    "sign up now",
    "[unable to render",
    "conversion failed",
]


# ───────────────────────────────────────────────────────────────
# 质量检查函数
# ───────────────────────────────────────────────────────────────

def _get_quality_threshold(source_type: str) -> dict:
    """获取指定 source_type 的质量阈值，回退到 default。"""
    return QUALITY_CONFIG.get(source_type, QUALITY_CONFIG["default"])


def _is_header_only(text: str, min_chars: int) -> bool:
    """检测文本是否仅包含 Markdown 标题而无正文。"""
    body = re.sub(r'^#{1,6}\s+[^\n]*$', '', text, flags=re.MULTILINE)
    stripped = re.sub(r'\s+', '', body)
    return len(stripped) < min_chars


def _table_has_meaningful_content(text: str) -> bool:
    """检测表格提取结果是否至少包含工作表名/字段名/有效单元格。"""
    sheet_indicators = re.findall(
        r'(?i)sheet\s*\d|工作表\d|字段|field|column|row\s*\d|table|表格',
        text,
    )
    cell_lines = [
        line for line in text.split('\n')
        if line.strip() and not line.strip().startswith('#') and not line.strip().startswith('|--')
    ]
    return len(sheet_indicators) > 0 or len(cell_lines) > 1


def _validate_is_normal_text(text: str, source_type: str) -> tuple[bool, list[str]]:
    """
    判断提取文本是否为有效内容。

    Returns:
        (is_valid, warnings): 是否通过质量检查 + 警告列表
    """
    warnings: list[str] = []
    cfg = _get_quality_threshold(source_type)

    # 1. 空文本检查
    if not text or not text.strip():
        return False, ["提取文本为空"]

    # 2. 去除空白后的可见字符数
    stripped = re.sub(r'\s+', '', text)
    min_chars = cfg.get("min_stripped_chars", 50)
    if len(stripped) < min_chars:
        warnings.append(f"可见字符数 {len(stripped)} < 阈值 {min_chars}")

    # 3. 仅标题无正文检测
    if _is_header_only(text, min_chars):
        warnings.append("文本仅包含标题，无正文内容")

    # 4. 段落数量
    min_para = cfg.get("min_paragraphs", 1)
    if min_para > 0:
        paragraphs = re.split(r'\n\s*\n', text)
        meaningful_paras = [p for p in paragraphs if len(re.sub(r'\s+', '', p)) >= 20]
        if len(meaningful_paras) < min_para:
            warnings.append(f"有效段落数 {len(meaningful_paras)} < 阈值 {min_para}")

    # 5. 可见文本比例
    body = re.sub(r'https?://\S+', '', text)
    body = re.sub(r'!\[[^\]]*\]\([^)]*\)', '', body)
    body = re.sub(r'\[[^\]]*\]\([^)]*\)', '', body)
    visible = re.sub(r'\s+', '', body)
    total = max(len(stripped), 1)
    ratio = len(visible) / total
    min_ratio = cfg.get("min_visible_text_ratio", 0.3)
    if ratio < min_ratio:
        warnings.append(f"可见文本比例 {ratio:.2f} < 阈值 {min_ratio}")

    # 6. 转换异常标记
    lowered = text.lower()
    for marker in CONVERSION_ERROR_MARKERS:
        if marker in lowered:
            warnings.append(f"检测到转换异常标记: '{marker}'")
            break

    # 7. 表格型特殊检查
    if source_type in ("xlsx", "xls"):
        min_sheet = cfg.get("min_sheet_indicators", 1)
        if min_sheet > 0 and not _table_has_meaningful_content(text):
            warnings.append(f"表格内容指示器不足（阈值 {min_sheet}）")

    is_valid = len(warnings) == 0
    return is_valid, warnings


def _quality_check(result: ExtractionResult) -> ExtractionResult:
    """
    对 ExtractionResult 执行质量检查。
    修改 result.success, result.warnings, result.metadata["quality_passed"]。
    """
    if not result.text or not result.text.strip():
        result.success = False
        result.warnings.append("提取文本为空")
        result.metadata["quality_passed"] = False
        return result

    is_valid, warnings = _validate_is_normal_text(result.text, result.source_type)

    result.warnings.extend(warnings)
    result.metadata["quality_passed"] = is_valid
    result.metadata["char_count_stripped"] = len(re.sub(r'\s+', '', result.text))
    result.metadata["paragraph_count"] = len(re.split(r'\n\s*\n', result.text))

    if not is_valid:
        result.success = False

    return result


# ───────────────────────────────────────────────────────────────
# 主转换函数
# ───────────────────────────────────────────────────────────────

def convert_with_markitdown(
    input_path: Path,
) -> ExtractionResult:
    """
    使用 MarkItDown 将本地文档转换为 Markdown。

    成功时将完整正文写入 .pkb-cache/extractions/ 缓存文件，
    并在结果中返回 extracted_path、preview、character_count。

    Args:
        input_path: 源文件的绝对或相对路径。

    Returns:
        ExtractionResult — 绝不抛出异常；所有错误转为结构化结果。

    支持的扩展名: .pdf, .docx, .pptx, .xlsx, .xls
    .doc 显式返回 error_code="legacy_doc_unsupported"
    """
    # 标准化路径
    try:
        input_path = input_path.resolve()
    except Exception:
        input_path = Path(str(input_path))

    source_path_str = str(input_path)
    ext = input_path.suffix.lower()
    if ext == ".xlsm":
        ext = ".xls"

    # 动态版本
    installed_ver = get_markitdown_version()

    # ── 基本信息 ──
    base_result = ExtractionResult(
        text="",
        method="markitdown",
        source_path=source_path_str,
        source_type="",
        success=False,
        metadata={
            "extractor_version": installed_ver or "not_installed",
            "fallback_used": False,
            "quality_passed": False,
        },
    )

    # ── 格式检测 ──
    if ext in LEGACY_DOC_EXTENSIONS:
        base_result.source_type = "doc"
        base_result.error_code = "legacy_doc_unsupported"
        base_result.warnings.append(
            "旧版 .doc (OLE 格式) 不受 MarkItDown 支持。"
            "请先用 Microsoft Word 或 LibreOffice 将文件另存为 .docx 格式。"
        )
        base_result.metadata["source_format"] = "doc"
        return base_result

    if ext not in SUPPORTED_EXTENSIONS:
        base_result.source_type = ext.lstrip(".")
        base_result.error_code = "unsupported_format"
        base_result.warnings.append(
            f"不支持的文件格式: '{ext}'。"
            f"Phase 1.5 支持: {', '.join(SUPPORTED_EXTENSIONS.keys())}"
        )
        base_result.metadata["source_format"] = ext.lstrip(".")
        return base_result

    source_type = SUPPORTED_EXTENSIONS[ext]
    base_result.source_type = source_type
    base_result.metadata["source_format"] = source_type

    # ── 依赖检查 ──
    if not HAS_MARKITDOWN:
        base_result.error_code = "import_error"
        base_result.warnings.append(
            "markitdown 未安装。请运行: "
            'pip install "markitdown[pdf,docx,pptx,xlsx,xls]==0.1.6"'
        )
        return base_result

    # ── 文件可读性检查 ──
    try:
        if not input_path.exists():
            base_result.error_code = "exception"
            base_result.warnings.append(f"文件不存在: {source_path_str}")
            return base_result
        if not input_path.is_file():
            base_result.error_code = "exception"
            base_result.warnings.append(f"路径不是文件: {source_path_str}")
            return base_result

        file_size = input_path.stat().st_size
        if file_size == 0:
            base_result.error_code = "corrupt_file"
            base_result.warnings.append("文件为空 (0 bytes)")
            return base_result
        if file_size > MAX_FILE_SIZE_BYTES:
            base_result.error_code = "file_too_large"
            base_result.warnings.append(
                f"文件过大 ({file_size / 1024 / 1024:.1f} MB > {MAX_FILE_SIZE_BYTES / 1024 / 1024:.0f} MB)"
            )
            return base_result
    except OSError as e:
        base_result.error_code = "exception"
        base_result.warnings.append(f"文件读取失败: {e}")
        return base_result

    # ── MarkItDown 转换 ──
    try:
        md = MarkItDown()
        result = md.convert(str(input_path))
        text_content = result.text_content
    except Exception as e:
        base_result.error_code = "exception"
        base_result.warnings.append(f"MarkItDown 转换异常: {type(e).__name__}: {e}")
        tb = traceback.format_exc()
        base_result.metadata["_debug_traceback"] = tb[:2000]
        if any(kw in str(e).lower() for kw in ("corrupt", "not a valid", "invalid", "bad zip", "truncated")):
            base_result.error_code = "corrupt_file"
        return base_result

    # ── 填充文本 ──
    if text_content is None:
        text_content = ""
    base_result.text = text_content.strip() if text_content else ""

    # ── 质量检查 ──
    base_result = _quality_check(base_result)

    # 空输出特殊处理
    if not base_result.text:
        base_result.error_code = "empty_output"
        base_result.warnings.append("MarkItDown 返回空文本")
        return base_result

    # ── 缓存写入 (仅质量检查通过时) ──
    if base_result.metadata.get("quality_passed"):
        # 计算源文件哈希
        file_sha = _compute_file_sha256(input_path)
        sha_prefix = file_sha[:12] if file_sha else None
        base_result.source_sha256 = sha_prefix

        # 写入缓存
        cache_path = _write_extraction_cache(base_result.text, input_path)

        if cache_path is not None:
            base_result.extracted_path = str(cache_path)
            base_result.metadata["extracted_path"] = str(cache_path)
        else:
            # 缓存写入失败 — 视为提取失败
            base_result.success = False
            base_result.error_code = "cache_write_failed"
            base_result.warnings.append("缓存文件写入失败")
            base_result.metadata["quality_passed"] = False
            return base_result

        # 预览
        preview_text = re.sub(r'\s+', ' ', base_result.text).strip()
        base_result.preview = preview_text[:PREVIEW_MAX_CHARS]
        base_result.character_count = len(base_result.text)
        base_result.metadata["character_count"] = base_result.character_count

    # ── 最终成功判定 ──
    if base_result.metadata.get("quality_passed") and base_result.error_code is None:
        base_result.success = True

    return base_result


# ───────────────────────────────────────────────────────────────
# Fallback 结果构造
# ───────────────────────────────────────────────────────────────

def make_fallback_result(
    primary_result: ExtractionResult,
    fallback_method: str,
    fallback_text: str,
    fallback_success: bool,
) -> ExtractionResult:
    """
    构造包含 fallback 链信息的提取结果。
    当 MarkItDown 失败后，调用方使用此函数包装后续提取器的结果。
    """
    result = ExtractionResult(
        text=fallback_text,
        method=fallback_method,
        source_path=primary_result.source_path,
        source_type=primary_result.source_type,
        success=fallback_success,
        warnings=list(primary_result.warnings),
        metadata={
            **primary_result.metadata,
            "fallback_used": True,
            "primary_extractor": "markitdown",
            "fallback_extractor": fallback_method,
            "fallback_reason": primary_result.error_code or "quality_failure",
            "quality_passed": fallback_success,
        },
    )
    # 如果 fallback 成功且 extractor_version 已设置，沿用
    if "extractor_version" not in result.metadata:
        result.metadata["extractor_version"] = get_markitdown_version() or "not_installed"
    return result


# ───────────────────────────────────────────────────────────────
# CLI
# ───────────────────────────────────────────────────────────────

def _cli_main() -> None:
    """CLI 入口 (python tools/markitdown_convert.py <文件>)。"""
    import argparse

    parser = argparse.ArgumentParser(
        description="PKB MarkItDown 文档预提取器 (Phase 1.5)",
    )
    parser.add_argument(
        "input",
        type=str,
        nargs="?",
        help="源文件路径",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="仅输出 JSON（不含完整正文）",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="依赖预检 (不需要文件参数)",
    )
    args = parser.parse_args()

    # ── 依赖预检 ──
    if args.check:
        real_ver = get_markitdown_version()
        checks = {
            "markitdown_installed": HAS_MARKITDOWN,
            "markitdown_version": real_ver or "not_installed",
            "pdf_support": HAS_MARKITDOWN,
            "docx_support": HAS_MARKITDOWN,
            "pptx_support": HAS_MARKITDOWN,
            "xlsx_support": HAS_MARKITDOWN,
            "xls_support": HAS_MARKITDOWN,
            "ocr_support": False,
            "install_hint": "",
        }
        # OCR 检测
        try:
            import markitdown_ocr  # noqa: F401
            checks["ocr_support"] = True
        except ImportError:
            pass

        if not HAS_MARKITDOWN:
            checks["install_hint"] = (
                'pip install -r tools/requirements-markitdown.txt'
            )

        if args.json:
            print(json.dumps(checks, indent=2, ensure_ascii=False))
        else:
            print("\n🔍 MarkItDown 依赖预检 (Phase 1.5)")
            print("=" * 40)
            for key, val in checks.items():
                if key == "install_hint":
                    continue
                icon = "✅" if val else "❌"
                label = key.replace("_", " ").title()
                display = val
                if key == "markitdown_version":
                    display = val if val else "N/A"
                print(f"  {icon} {label}: {display}")
            if checks["install_hint"]:
                print(f"\n  💡 安装: {checks['install_hint']}")
            print()
        sys.exit(0 if checks["markitdown_installed"] else 1)

    if not args.input:
        parser.error("需要文件路径参数 (或使用 --check 进行预检)")

    input_path = Path(args.input)
    result = convert_with_markitdown(input_path)

    if args.json:
        # JSON 输出：排除完整正文
        output = {
            "source_path": result.source_path,
            "source_type": result.source_type,
            "method": result.method,
            "success": result.success,
            "extracted_path": result.extracted_path,
            "character_count": result.character_count,
            "preview": result.preview,
            "source_sha256": result.source_sha256,
            "warnings": result.warnings,
            "error_code": result.error_code,
            "metadata": result.metadata,
        }
        print(json.dumps(output, indent=2, ensure_ascii=False))
    else:
        status_icon = "✅" if result.success else "❌"
        print(f"\n{status_icon} MarkItDown 转换: {result.source_path}")
        print(f"   格式: {result.source_type}")
        print(f"   成功: {result.success}")
        print(f"   错误码: {result.error_code or '无'}")
        if result.extracted_path:
            print(f"   缓存: {result.extracted_path}")
            print(f"   字符数: {result.character_count}")
        if result.warnings:
            print(f"   警告 ({len(result.warnings)}):")
            for w in result.warnings:
                print(f"     - {w}")
        print(f"   元数据: {json.dumps(result.metadata, indent=2, ensure_ascii=False)}")
        if result.preview:
            print(f"\n── 预览（前 {PREVIEW_MAX_CHARS} 字符）──")
            print(result.preview)
            if result.character_count > PREVIEW_MAX_CHARS:
                print(f"... (共 {result.character_count} 字符)")
            print("── 结束 ──")
        print()

    sys.exit(0 if result.success else 1)


if __name__ == "__main__":
    _cli_main()
