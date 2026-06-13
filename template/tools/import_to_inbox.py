#!/usr/bin/env python3
"""
PKB import_to_inbox — 文件/文件夹导入工具

用法:
    python import_to_inbox.py <路径>            # 导入单个文件
    python import_to_inbox.py <路径> --folder   # 导入整个文件夹
    python import_to_inbox.py <路径> --move     # 移动而非复制（默认复制）

功能:
    - 复制文件/文件夹到 _INBOX
    - 生成 manifest.json 记录来源信息
    - 自动重命名避免冲突
    - 跳过缓存目录和敏感文件
    - 检测敏感信息并警告
"""

import os
import sys
import json
import shutil
import hashlib
import argparse
from pathlib import Path
from datetime import datetime, timezone

# --- 配置 ---
PKB_ROOT = Path(os.environ.get("PKB_ROOT", r"D:\PKB_个人知识库"))
INBOX_FILES = PKB_ROOT / "_INBOX" / "imported"
INBOX_FOLDERS = PKB_ROOT / "_INBOX" / "imported-folders"

# 跳过的目录名
SKIP_DIRS = {
    ".git", "node_modules", ".venv", "venv", ".tox",
    "__pycache__", ".mypy_cache", ".pytest_cache",
    "dist", "build", ".cache", "__MACOSX",
    ".idea", ".vscode", ".vs",  # IDE 目录
}

# 敏感文件名模式
SENSITIVE_FILE_NAMES = {
    ".env", ".env.local", ".env.production", ".env.development",
    "credentials.json", "credentials.yaml", "credentials.yml",
    "serviceAccount.json", "service_account.json",
    "id_rsa", "id_rsa.pub", "id_ed25519", "id_ecdsa",
    "known_hosts", "authorized_keys",
}

# 敏感文件扩展名
SENSITIVE_EXTENSIONS = {".pem", ".p12", ".pfx", ".key", ".keystore", ".jks"}

# 敏感内容模式（正则）
import re
SENSITIVE_CONTENT_PATTERNS = [
    re.compile(rb'(?:api[_-]?key|apikey|api_secret|secret_key)\s*[=:]\s*["\']?[\w\-]{20,}["\']?', re.IGNORECASE),
    re.compile(rb'(?:token|access_token|auth_token|bearer)\s*[=:]\s*["\']?[\w\-\.]{20,}["\']?', re.IGNORECASE),
    re.compile(rb'(?:password|passwd|pwd)\s*[=:]\s*["\'][^"\']{3,}["\']', re.IGNORECASE),
    re.compile(rb'(?:private[_-]?key|secret)\s*[=:]\s*["\']?[\w\-+/=]{20,}["\']?', re.IGNORECASE),
    re.compile(rb'-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----', re.IGNORECASE),
    re.compile(rb'-----BEGIN PGP PRIVATE KEY BLOCK-----', re.IGNORECASE),
    re.compile(rb'(?:credential|cred)s?\s*[=:]\s*["\']?[\w\-]{10,}["\']?', re.IGNORECASE),
]


def get_safe_name(dest_dir: Path, name: str) -> str:
    """如果同名文件已存在，添加序号后缀。"""
    stem, ext = os.path.splitext(name)
    candidate = name
    counter = 1
    while (dest_dir / candidate).exists():
        candidate = f"{stem}_{counter}{ext}"
        counter += 1
    return candidate


def get_file_hash(filepath: Path, algorithm: str = "sha256") -> str:
    """计算文件哈希。"""
    h = hashlib.new(algorithm)
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def scan_sensitive_content(filepath: Path) -> list[str]:
    """扫描文件中的敏感内容。返回发现的模式描述列表。"""
    warnings = []
    try:
        # 只扫描文本文件（限制大小 10MB）
        if filepath.stat().st_size > 10 * 1024 * 1024:
            return warnings
        with open(filepath, "rb") as f:
            content = f.read(1024 * 100)  # 只扫描前 100KB
        for pattern in SENSITIVE_CONTENT_PATTERNS:
            if pattern.search(content):
                warnings.append(f"疑似敏感内容匹配: {pattern.pattern.decode()[:60]}...")
    except (IOError, UnicodeDecodeError):
        pass  # 二进制文件跳过
    return warnings


def import_file(src_path: Path, dest_dir: Path, move: bool = False) -> dict | None:
    """
    导入单个文件。
    返回 manifest 条目，如果跳过则返回 None。
    """
    # 检查文件名
    if src_path.name.lower() in {n.lower() for n in SENSITIVE_FILE_NAMES}:
        return {
            "status": "rejected",
            "reason": f"敏感文件名: {src_path.name}",
            "source_path": str(src_path),
        }

    # 检查扩展名
    if src_path.suffix.lower() in SENSITIVE_EXTENSIONS:
        return {
            "status": "rejected",
            "reason": f"敏感文件扩展名: {src_path.suffix}",
            "source_path": str(src_path),
        }

    # 检查内容
    content_warnings = scan_sensitive_content(src_path)
    if content_warnings:
        return {
            "status": "rejected",
            "reason": f"敏感内容: {'; '.join(content_warnings)}",
            "source_path": str(src_path),
        }

    # 复制文件
    safe_name = get_safe_name(dest_dir, src_path.name)
    dest_path = dest_dir / safe_name

    try:
        if move:
            shutil.move(str(src_path), str(dest_path))
        else:
            shutil.copy2(str(src_path), str(dest_path))
    except (IOError, OSError) as e:
        return {
            "status": "error",
            "reason": str(e),
            "source_path": str(src_path),
        }

    return {
        "status": "imported",
        "source_path": str(src_path),
        "imported_name": safe_name,
        "original_name": src_path.name,
        "size_bytes": src_path.stat().st_size,
        "imported_at": datetime.now(timezone.utc).isoformat(),
    }


def import_folder(src_path: Path, move: bool = False) -> list[dict]:
    """
    递归导入文件夹。
    跳过长列表中的缓存/IDE/依赖目录。
    """
    manifest_entries = []
    folder_dest = INBOX_FOLDERS / src_path.name

    # 确保目标目录唯一
    if folder_dest.exists():
        counter = 1
        while (INBOX_FOLDERS / f"{src_path.name}_{counter}").exists():
            counter += 1
        folder_dest = INBOX_FOLDERS / f"{src_path.name}_{counter}"

    folder_dest.mkdir(parents=True, exist_ok=True)

    skipped_dirs = []
    skipped_files = 0
    imported_files = 0

    for root, dirs, files in os.walk(str(src_path)):
        # 过滤要跳过的目录（原地修改 dirs 列表）
        dirs_to_skip = [d for d in dirs if d in SKIP_DIRS or d.startswith(".") and d in SKIP_DIRS]
        for d in dirs_to_skip:
            dirs.remove(d)
            skipped_dirs.append(os.path.join(root, d))

        # 计算相对路径
        rel_root = os.path.relpath(root, str(src_path))
        if rel_root == ".":
            dest_root = folder_dest
        else:
            dest_root = folder_dest / rel_root

        dest_root.mkdir(parents=True, exist_ok=True)

        for filename in files:
            file_src = Path(root) / filename
            entry = import_file(file_src, dest_root, move=move)
            if entry:
                if entry.get("status") == "imported":
                    imported_files += 1
                else:
                    skipped_files += 1
                manifest_entries.append(entry)

    # 写入 manifest.json
    manifest_path = folder_dest / "manifest.json"
    manifest = {
        "source_path": str(src_path),
        "imported_at": datetime.now(timezone.utc).isoformat(),
        "total_imported": imported_files,
        "total_skipped": skipped_files,
        "skipped_dirs": skipped_dirs,
        "entries": manifest_entries,
    }
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    return manifest_entries


def print_report(entries: list[dict], source_path: str, is_folder: bool = False):
    """打印清晰的导入报告。"""
    imported = [e for e in entries if e.get("status") == "imported"]
    rejected = [e for e in entries if e.get("status") == "rejected"]
    errors = [e for e in entries if e.get("status") == "error"]

    total_size = sum(e.get("size_bytes", 0) for e in imported)

    print()
    print("=" * 60)
    print(f"📥 PKB 导入报告")
    print("=" * 60)
    print(f"   来源: {source_path}")
    print(f"   类型: {'文件夹' if is_folder else '文件'}")

    if imported:
        print(f"   ✅ 成功导入: {len(imported)} 个文件")
        if total_size > 1024 * 1024:
            print(f"      总大小: {total_size / (1024*1024):.1f} MB")
        elif total_size > 1024:
            print(f"      总大小: {total_size / 1024:.1f} KB")
        else:
            print(f"      总大小: {total_size} B")

    if rejected:
        print(f"   🔴 已阻止 (敏感信息): {len(rejected)} 个文件")
        for r in rejected:
            print(f"      - {r.get('source_path')}: {r.get('reason')}")

    if errors:
        print(f"   ❌ 错误: {len(errors)} 个文件")
        for e in errors:
            print(f"      - {e.get('source_path')}: {e.get('reason')}")

    if not imported and not rejected and not errors:
        print("   ⚠️  没有文件被导入")

    print("=" * 60)

    # 输出 JSON 供 Agent 解析
    report = {
        "source": source_path,
        "is_folder": is_folder,
        "imported_count": len(imported),
        "rejected_count": len(rejected),
        "error_count": len(errors),
        "total_size_bytes": total_size,
        "rejected": [{"path": r["source_path"], "reason": r["reason"]} for r in rejected],
    }
    print()
    print("--- JSON REPORT ---")
    print(json.dumps(report, ensure_ascii=False, indent=2))


def main():
    global PKB_ROOT, INBOX_FILES, INBOX_FOLDERS
    parser = argparse.ArgumentParser(
        description="PKB 导入工具 — 将文件/文件夹导入知识库收件箱",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
    python import_to_inbox.py paper.pdf
    python import_to_inbox.py ~/Downloads/article.pdf
    python import_to_inbox.py ~/project/ --folder
    python import_to_inbox.py ~/project/ --folder --move
        """,
    )
    parser.add_argument("path", help="要导入的文件或文件夹路径")
    parser.add_argument("--folder", action="store_true", help="导入整个文件夹（默认是单文件）")
    parser.add_argument("--move", action="store_true", help="移动而非复制（默认复制）")
    parser.add_argument("--root", default=None, help=f"PKB 根目录（默认: {PKB_ROOT}）")

    args = parser.parse_args()

    if args.root:
        PKB_ROOT = Path(args.root)
        INBOX_FILES = PKB_ROOT / "_INBOX" / "imported"
        INBOX_FOLDERS = PKB_ROOT / "_INBOX" / "imported-folders"

    src_path = Path(args.path).resolve()

    if not src_path.exists():
        print(f"❌ 路径不存在: {src_path}")
        sys.exit(1)

    # 确保收件箱目录存在
    INBOX_FILES.mkdir(parents=True, exist_ok=True)
    INBOX_FOLDERS.mkdir(parents=True, exist_ok=True)

    if args.folder or src_path.is_dir():
        if not src_path.is_dir():
            print(f"❌ 不是目录: {src_path}（去掉 --folder 以导入单文件）")
            sys.exit(1)
        entries = import_folder(src_path, move=args.move)
        print_report(entries, str(src_path), is_folder=True)
    else:
        entry = import_file(src_path, INBOX_FILES, move=args.move)
        if entry is None:
            print("⚠️  文件被跳过（未知原因）")
            sys.exit(1)
        print_report([entry], str(src_path), is_folder=False)


if __name__ == "__main__":
    main()
