#!/usr/bin/env python3
"""
PKB 本地文件入库编排器 (pkb_ingest.py)

将本地文档接入 PKB 全自动入库管线：
  import_to_inbox → markitdown_convert (full mode) → 结构化结果

这是 /pkb --mode full <本地文档> 的真实 Python 执行入口。
不处理 URL — URL 仍由 web_pack.py 负责。

用法:
    python tools/pkb_ingest.py <文件路径>                  # 默认 full 模式
    python tools/pkb_ingest.py <文件路径> --mode safe      # safe 模式 (不走 markitdown)
    python tools/pkb_ingest.py <文件路径> --json           # JSON（不含完整正文）
    python tools/pkb_ingest.py --check                     # 依赖预检

返回 IngestResult: 包含 extracted_path（缓存文件路径）、preview、fallback 状态等。
LLM 收到结果后：若 extraction_success=True，Read extracted_path 获取正文编译 wiki；
若 fallback_required=True，Read _INBOX 副本执行 fallback。
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ── 编码: Windows 兼容 ──
sys.stdout.reconfigure(encoding='utf-8', errors='replace')  # type: ignore[attr-defined]

# ── 项目根 ──
_PKB_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PKB_ROOT / "tools"))

# ── 内部依赖 ──
from import_to_inbox import import_file, INBOX_FILES as _INBOX_DIR, PKB_ROOT
from markitdown_convert import (
    HAS_MARKITDOWN,
    SUPPORTED_EXTENSIONS,
    ExtractionResult,
    convert_with_markitdown,
    make_fallback_result,
    get_markitdown_version,
)

# ───────────────────────────────────────────────────────────────
# IngestResult — 入库编排结果
# ───────────────────────────────────────────────────────────────

@dataclass
class IngestResult:
    """本地文件入库编排的完整结果。

    成功时 extracted_path 指向 .pkb-cache/extractions/ 缓存文件，
    CLI JSON 不包含完整正文 —— LLM 通过 Read 工具读取 extracted_path。

    fallback 字段为「计划状态」：Python 管线标记 fallback_required=True
    表示需要 LLM 执行 fallback，但 fallback_attempted/used/succeeded
    由 LLM 在实际执行后记录到 wiki frontmatter。
    """

    # 文件信息
    source_path: str                       # 原始文件路径
    inbox_path: str                        # _INBOX 中的副本路径
    original_name: str                     # 原始文件名
    source_type: str                       # 扩展名: pdf / docx / pptx / xlsx / xls

    # 提取结果（不包含完整正文 — 正文在 extracted_path 指向的缓存文件中）
    extracted_path: Optional[str] = None   # 缓存文件路径（成功时填充）
    preview: str = ""                      # 短预览（最多 500 可见字符）
    character_count: int = 0               # 完整转换结果字符数
    source_sha256: Optional[str] = None    # 源文件 SHA256 前 12 位
    extraction_method: str = ""            # "markitdown" 或 "llm_direct_read"
    extraction_success: bool = False       # 提取是否成功
    quality_passed: bool = False           # 质量检查是否通过

    # Fallback 状态机（Python 输出「计划状态」，LLM 记录「实际执行状态」）
    fallback_required: bool = False        # MarkItDown 失败，需要 LLM fallback
    fallback_attempted: bool = False       # LLM 已尝试 fallback（Python 始终为 False）
    fallback_used: bool = False            # LLM 已执行 fallback（Python 始终为 False）
    fallback_succeeded: Optional[bool] = None  # None=未尝试, True=成功, False=失败
    fallback_reason: Optional[str] = None  # 触发 fallback 的原因（错误码）
    fallback_extractor: Optional[str] = None   # fallback 方法，如 "llm_direct_read"

    # 错误信息
    error_code: Optional[str] = None       # 错误码 (成功时为 None)
    warnings: list[str] = field(default_factory=list)

    # 元数据 (用于 wiki frontmatter)
    metadata: dict = field(default_factory=dict)

    # 入库状态
    imported: bool = False                 # 是否已复制到 _INBOX
    ingest_time: str = ""                  # ISO 时间戳


# ───────────────────────────────────────────────────────────────
# 核心编排函数
# ───────────────────────────────────────────────────────────────

def ingest_local_file(
    file_path: Path,
    mode: str = "full",
    *,
    _markitdown_result: Optional[ExtractionResult] = None,  # 测试注入点
) -> IngestResult:
    """
    编排本地文档的完整入库流程。

    1. 复制到 _INBOX/imported/
    2. full 模式: 对支持格式调用 markitdown_convert
       - 成功: 写入缓存文件，返回 extracted_path
       - 失败: 设置 fallback_required=True，由 LLM 执行 fallback
    3. safe 模式: 跳过 MarkItDown，由 LLM 直接读取

    Args:
        file_path: 源文件路径
        mode: "full" (启用 markitdown) 或 "safe" (跳过 markitdown)

    Returns:
        IngestResult — 包含提取路径、预览和 fallback 计划状态
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    ext = file_path.suffix.lower()

    # ── 初始化结果 ──
    result = IngestResult(
        source_path=str(file_path.resolve()),
        inbox_path="",
        original_name=file_path.name,
        source_type=ext.lstrip("."),
        extraction_method="",
        extraction_success=False,
        quality_passed=False,
        ingest_time=now_iso,
    )

    # ── 校验 ──
    if not file_path.exists():
        result.error_code = "file_not_found"
        result.warnings.append(f"文件不存在: {file_path}")
        return result

    if not file_path.is_file():
        result.error_code = "not_a_file"
        result.warnings.append(f"路径不是文件: {file_path}")
        return result

    # ── Step 1: 复制到 _INBOX ──
    try:
        inbox_entry = import_file(file_path, _INBOX_DIR, move=False)
        if inbox_entry is None or inbox_entry.get("status") != "imported":
            result.error_code = "import_failed"
            result.warnings.append(
                f"导入 _INBOX 失败: {inbox_entry.get('reason', '未知') if inbox_entry else '无结果'}"
            )
            return result
        result.imported = True
        result.inbox_path = str(_INBOX_DIR / inbox_entry["imported_name"])
    except Exception as e:
        result.error_code = "import_exception"
        result.warnings.append(f"导入 _INBOX 异常: {e}")
        return result

    # ── Step 2: 文档预提取 (仅 full 模式 + 支持格式) ──
    if mode != "full":
        # safe 模式: 跳过 markitdown, LLM 为 primary path（不是 fallback）
        result.extraction_method = "llm_direct_read"
        result.warnings.append("safe 模式: 跳过 MarkItDown 预提取, 由 LLM 直接读取")
        result.metadata["mode"] = "safe"
        # safe 模式下 LLM 是主路径，不是 fallback
        result.fallback_required = False
        return result

    # 不支持格式路由
    if ext not in SUPPORTED_EXTENSIONS:
        if ext == ".doc":
            # .doc: 明确不支持，需要 fallback
            result.error_code = "legacy_doc_unsupported"
            result.warnings.append(
                "旧版 .doc (OLE 格式) 不受支持。请用 Word 或 LibreOffice 转为 .docx。"
            )
            result.metadata["extraction_method"] = "none"
            result.fallback_required = True
            result.fallback_reason = "legacy_doc_unsupported"
            result.fallback_extractor = "llm_direct_read"
            return result
        # 其他格式: LLM 为 primary path，不做 markitdown fallback
        result.extraction_method = "llm_direct_read"
        result.warnings.append(
            f"格式 '{ext}' 不在 MarkItDown Phase 1.5 支持范围, 由 LLM 直接读取"
        )
        result.metadata["mode"] = "full"
        result.fallback_required = False
        return result

    # ── 支持格式: 调用 MarkItDown ──
    try:
        mk_result = _markitdown_result or convert_with_markitdown(Path(result.inbox_path))
    except Exception as e:
        # convert_with_markitdown 不应抛出, 但防御性捕获
        mk_result = ExtractionResult(
            text="",
            method="markitdown",
            source_path=result.inbox_path,
            source_type=SUPPORTED_EXTENSIONS.get(ext, ext.lstrip(".")),
            success=False,
            error_code="exception",
            warnings=[f"convert_with_markitdown 异常: {e}"],
        )

    # ── 处理 MarkItDown 结果 ──
    if mk_result.success:
        # ✅ MarkItDown 成功 — 正文已写入 extracted_path 缓存文件
        result.extracted_path = mk_result.extracted_path
        result.preview = mk_result.preview
        result.character_count = mk_result.character_count
        result.source_sha256 = mk_result.source_sha256
        result.extraction_method = "markitdown"
        result.extraction_success = True
        result.quality_passed = True
        # Fallback: 不需要、未尝试、未使用
        result.fallback_required = False
        result.fallback_attempted = False
        result.fallback_used = False
        result.fallback_succeeded = None
        result.fallback_reason = None
        result.fallback_extractor = None
        result.metadata = {
            **mk_result.metadata,
            "extraction_method": "markitdown",
            "fallback_required": False,
            "ingest_mode": mode,
            "ingest_time": now_iso,
        }
        return result

    # ── MarkItDown 失败 → 标记需要 fallback ──
    result.warnings.append(
        f"MarkItDown 提取失败 (error_code={mk_result.error_code}), 需要 LLM fallback"
    )
    result.warnings.extend(mk_result.warnings)

    # Fallback 计划状态：Python 仅标记「需要执行」，LLM 在收到结果后实际执行
    result.extraction_method = "llm_direct_read"
    result.extraction_success = False
    result.quality_passed = False
    result.error_code = mk_result.error_code

    result.fallback_required = True
    result.fallback_attempted = False       # LLM 尚未执行
    result.fallback_used = False            # LLM 尚未使用
    result.fallback_succeeded = None        # 待定
    result.fallback_reason = mk_result.error_code or "quality_failure"
    result.fallback_extractor = "llm_direct_read"

    result.metadata = {
        **mk_result.metadata,
        "extraction_method": "llm_direct_read",
        "fallback_required": True,
        "fallback_attempted": False,
        "fallback_used": False,
        "fallback_succeeded": None,
        "fallback_reason": result.fallback_reason,
        "fallback_extractor": "llm_direct_read",
        "primary_extractor": "markitdown",
        "quality_passed": False,
        "ingest_mode": mode,
        "ingest_time": now_iso,
    }

    return result


# ───────────────────────────────────────────────────────────────
# 依赖预检
# ───────────────────────────────────────────────────────────────

def check_dependencies() -> dict:
    """
    检查 MarkItDown 依赖状态。

    Returns:
        包含所有检查项状态的 dict。
    """
    installed_ver = get_markitdown_version()

    checks = {
        "markitdown_installed": HAS_MARKITDOWN,
        "markitdown_version": installed_ver or "not_installed",
        "pdf_support": HAS_MARKITDOWN,
        "docx_support": HAS_MARKITDOWN,
        "pptx_support": HAS_MARKITDOWN,
        "xlsx_support": HAS_MARKITDOWN,
        "xls_support": HAS_MARKITDOWN,
        "ocr_support": False,
        "missing_deps": [],
        "install_hint": "",
    }

    if HAS_MARKITDOWN and installed_ver:
        checks["markitdown_version"] = installed_ver
        # OCR 检查
        try:
            import markitdown_ocr  # noqa: F401
            checks["ocr_support"] = True
        except ImportError:
            checks["ocr_support"] = False
            checks["missing_deps"].append("markitdown-ocr (OCR, 默认未启用)")
    else:
        checks["missing_deps"] = [
            "markitdown[pdf,docx,pptx,xlsx,xls]==0.1.6"
        ]
        checks["install_hint"] = (
            'pip install -r tools/requirements-markitdown.txt'
        )

    return checks


# ───────────────────────────────────────────────────────────────
# CLI
# ───────────────────────────────────────────────────────────────

def _cli_main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="PKB 本地文件入库编排器 — Phase 1.5 真实执行入口",
    )
    parser.add_argument(
        "input",
        type=str,
        nargs="?",
        help="源文件路径",
    )
    parser.add_argument(
        "--mode",
        choices=["full", "safe"],
        default="full",
        help="采集模式 (默认: full)",
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
        checks = check_dependencies()
        if args.json:
            print(json.dumps(checks, indent=2, ensure_ascii=False))
        else:
            print("\n🔍 MarkItDown 依赖预检 (PKB Phase 1.5)")
            print("=" * 50)
            for key, val in checks.items():
                if key in ("missing_deps", "install_hint"):
                    continue
                icon = "✅" if val else "❌"
                label = key.replace("_", " ").title()
                display = val if val is not None else "N/A"
                print(f"  {icon} {label}: {display}")
            if checks["missing_deps"]:
                print(f"\n  ⚠️  缺失依赖: {', '.join(checks['missing_deps'])}")
            if checks["install_hint"]:
                print(f"  💡 安装: {checks['install_hint']}")
            print()
        sys.exit(0 if checks["markitdown_installed"] else 1)

    # ── 文件入库 ──
    if not args.input:
        parser.error("需要文件路径参数 (或使用 --check 进行预检)")

    file_path = Path(args.input)
    result = ingest_local_file(file_path, mode=args.mode)

    if args.json:
        # JSON 输出：不包含完整正文
        output = {
            "source_path": result.source_path,
            "inbox_path": result.inbox_path,
            "original_name": result.original_name,
            "source_type": result.source_type,
            "extracted_path": result.extracted_path,
            "preview": result.preview,
            "character_count": result.character_count,
            "source_sha256": result.source_sha256,
            "extraction_method": result.extraction_method,
            "extraction_success": result.extraction_success,
            "quality_passed": result.quality_passed,
            "fallback_required": result.fallback_required,
            "fallback_attempted": result.fallback_attempted,
            "fallback_used": result.fallback_used,
            "fallback_succeeded": result.fallback_succeeded,
            "fallback_reason": result.fallback_reason,
            "fallback_extractor": result.fallback_extractor,
            "error_code": result.error_code,
            "warnings": result.warnings,
            "metadata": result.metadata,
            "imported": result.imported,
            "ingest_time": result.ingest_time,
        }
        print(json.dumps(output, indent=2, ensure_ascii=False))
    else:
        status = "✅" if result.extraction_success else ("⚠️" if result.imported else "❌")
        print(f"\n{status} PKB 入库: {result.original_name}")
        print(f"   源路径: {result.source_path}")
        print(f"   _INBOX: {result.inbox_path or '导入失败'}")
        print(f"   格式: {result.source_type}")
        print(f"   提取方法: {result.extraction_method}")
        print(f"   提取成功: {result.extraction_success}")
        print(f"   质量通过: {result.quality_passed}")
        if result.extracted_path:
            print(f"   缓存路径: {result.extracted_path}")
            print(f"   字符数: {result.character_count}")
        print(f"   Fallback 需要: {result.fallback_required}")
        if result.fallback_required:
            print(f"   Fallback 原因: {result.fallback_reason}")
            print(f"   Fallback 方法: {result.fallback_extractor}")
        if result.error_code:
            print(f"   错误码: {result.error_code}")
        if result.warnings:
            print(f"   警告 ({len(result.warnings)}):")
            for w in result.warnings:
                print(f"     - {w}")
        if result.preview:
            print(f"\n── 预览 ──\n{result.preview}")
            if result.character_count > len(result.preview):
                print(f"... (共 {result.character_count} 字符)")
            print("── 结束 ──")
        print()

    sys.exit(0 if result.imported else 1)


if __name__ == "__main__":
    _cli_main()
