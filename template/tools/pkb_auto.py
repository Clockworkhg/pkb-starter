#!/usr/bin/env python3
"""
PKB Auto Ingest Orchestrator (pkb_auto.py)

Scans _INBOX and raw/webpacks, identifies processed/unprocessed items,
generates auto_ingest_plan.json, auto_ingest_report.md, and processed manifest.
Does NOT write wiki content — that's Claude Code's job per AGENTS.md.

Usage:
    python tools/pkb_auto.py --scan           # Scan and generate plan
    python tools/pkb_auto.py --check          # Health check only
    python tools/pkb_auto.py --report         # Generate auto_ingest_report.md
    python tools/pkb_auto.py --manifest       # Generate processed manifest
    python tools/pkb_auto.py --full           # Scan + check + report (default)
"""

import os, sys, json, glob, hashlib, re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
PKG_ROOT = Path(__file__).resolve().parent.parent
INBOX_FILES = PKG_ROOT / "_INBOX" / "imported"
INBOX_FOLDERS = PKG_ROOT / "_INBOX" / "imported-folders"
PROCESSED_DIR = PKG_ROOT / "raw" / "imported_processed"
WEBPACKS_DIR = PKG_ROOT / "raw" / "webpacks"
WIKI_DIR = PKG_ROOT / "wiki"
WIKI_INDEX = WIKI_DIR / "index.md"

# Content type classification rules
CONTENT_RULES = {
    "academic_paper": {
        "extensions": [".pdf", ".docx"],
        "keywords": ["学报", "大学", "哲学", "法律", "历史", "文学", "政治", "经济",
                     "社会", "马克思", "恩格斯", "费尔巴哈", "唯物", "实践", "权利",
                     "journal", "university", "research", "analysis"],
    },
    "coursework": {
        "extensions": [".docx", ".pptx", ".pdf"],
        "keywords": ["作业", "考试", "课程", "小组", "汇报", "实验", "报告", "答辩"],
    },
    "school_policy": {
        "extensions": [".doc", ".docx"],
        "keywords": ["规则", "规范", "写作", "论文", "学位", "格式", "要求"],
    },
    "project_ppt": {
        "extensions": [".pptx"],
        "keywords": ["项目", "方案", "听证会", "模拟", "提案", "策划", "计划"],
    },
    "github_source": {
        "source_type": "github",
        "keywords": [],
    },
    "methodology": {
        "extensions": [".md"],
        "keywords": ["模式", "框架", "方法", "理念", "架构", "设计", "pattern"],
    },
}

SENSITIVE_PATTERNS = [
    (r'(?:api[_-]?key|apikey)\s*[=:]\s*["\']?\w{20,}', "API Key"),
    (r'(?:token|secret)\s*[=:]\s*["\']?\w{20,}', "Token/Secret"),
    (r'(?:password|passwd)\s*[=:]\s*["\']\S+', "Password"),
    (r'-----BEGIN\s+(?:RSA\s+)?PRIVATE\s+KEY-----', "Private Key"),
    (r'\b\d{15,18}\b', "ID Card Number (possible)"),
]

SAFE_EXTENSIONS = {
    ".py", ".ts", ".js", ".md", ".pdf", ".pptx", ".docx", ".xlsx",
    ".ipynb", ".txt", ".csv", ".json", ".yaml", ".yml", ".toml",
    ".html", ".css", ".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp",
    ".mp3", ".wav", ".mp4", ".mov", ".zip", ".doc",
}


# ---------------------------------------------------------------------------
# Scanning
# ---------------------------------------------------------------------------
def scan_inbox() -> List[Dict]:
    """Scan _INBOX/imported for unprocessed files."""
    items = []
    if not INBOX_FILES.exists():
        return items
    for f in INBOX_FILES.iterdir():
        if f.is_file() and not f.name.startswith("."):
            items.append({
                "path": str(f),
                "name": f.name,
                "size_bytes": f.stat().st_size,
                "ext": f.suffix.lower(),
                "source": "inbox_imported",
            })
    return items


def scan_inbox_folders() -> List[Dict]:
    """Scan _INBOX/imported-folders."""
    items = []
    if not INBOX_FOLDERS.exists():
        return items
    for d in INBOX_FOLDERS.iterdir():
        if d.is_dir() and not d.name.startswith("."):
            items.append({
                "path": str(d),
                "name": d.name,
                "source": "inbox_folder",
            })
    return items


def scan_webpacks() -> List[Dict]:
    """Scan raw/webpacks for unprocessed packs."""
    items = []
    if not WEBPACKS_DIR.exists():
        return items
    for d in sorted(WEBPACKS_DIR.iterdir()):
        if not d.is_dir():
            continue
        manifest = d / "manifest.json"
        has_manifest = manifest.exists()
        # Check if already has wiki source-note
        pack_slug = d.name
        wiki_created = False
        wiki_source_file = None
        for src_dir in ["sources", "source"]:
            sources_path = WIKI_DIR / src_dir
            if sources_path.exists():
                for mf in sources_path.glob("*.md"):
                    try:
                        content = mf.read_text(encoding="utf-8")
                        if pack_slug in content or d.name in content:
                            wiki_created = True
                            wiki_source_file = str(mf.relative_to(PKG_ROOT))
                            break
                    except:
                        pass
            if wiki_created:
                break

        # Count files
        file_count = sum(1 for _ in d.rglob("*") if _.is_file())
        items.append({
            "path": str(d),
            "name": d.name,
            "has_manifest": has_manifest,
            "file_count": file_count,
            "wiki_created": wiki_created,
            "wiki_source_file": wiki_source_file,
            "source": "webpack",
            "processed": wiki_created,
        })
    return items


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------
def classify_content(name: str, ext: str, text_sample: str = "") -> str:
    """Auto-classify content type."""
    name_lower = name.lower()
    text_lower = text_sample.lower()

    for ctype, rules in CONTENT_RULES.items():
        if "source_type" in rules:
            continue  # GitHub sources handled separately
        exts = rules.get("extensions", [])
        keywords = rules.get("keywords", [])
        ext_match = ext.lower() in exts if exts else True
        kw_matches = sum(1 for kw in keywords if kw.lower() in name_lower or kw.lower() in text_lower)
        if ext_match and kw_matches >= 1:
            return ctype

    return "unknown"


def classify_url(url: str) -> str:
    """Classify URL type."""
    if "github.com" in url or "gist.github.com" in url:
        return "github"
    if "mp.weixin.qq.com" in url:
        return "wechat"
    if "arxiv.org" in url:
        return "academic"
    return "webpage"


# ---------------------------------------------------------------------------
# Sensitive info scan
# ---------------------------------------------------------------------------
def scan_sensitive(filepath: str) -> List[str]:
    """Scan file for sensitive information. Returns list of found patterns."""
    warnings = []
    try:
        if not os.path.isfile(filepath):
            return warnings
        size = os.path.getsize(filepath)
        if size > 10 * 1024 * 1024:  # Skip files > 10MB
            return warnings
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read(50000)  # First 50KB
        for pattern, label in SENSITIVE_PATTERNS:
            if re.search(pattern, content, re.IGNORECASE):
                warnings.append(label)
    except:
        pass
    return warnings


# ---------------------------------------------------------------------------
# Path fixing
# ---------------------------------------------------------------------------
def find_stale_inbox_refs() -> List[Tuple[str, str]]:
    """Find stale _INBOX references in wiki body text (not frontmatter)."""
    stale = []
    if not WIKI_DIR.exists():
        return stale
    for mf in WIKI_DIR.rglob("*.md"):
        try:
            content = mf.read_text(encoding="utf-8")
            # Skip frontmatter
            parts = content.split("---", 2)
            body = parts[2] if len(parts) >= 3 else content
            if "_INBOX/imported" in body or "_INBOX" in body:
                # Check if it's an intentional instruction vs stale path
                for line in body.split("\n"):
                    if "_INBOX" in line and "→" in line:
                        continue  # Instructional text
                    if "_INBOX/imported" in line:
                        stale.append((str(mf.relative_to(PKG_ROOT)), line.strip()[:120]))
        except:
            pass
    return stale


def check_source_paths() -> Dict:
    """Check source_path frontmatter consistency."""
    issues = []
    correct = 0
    total = 0
    if not WIKI_DIR.exists():
        return {"total": 0, "correct": 0, "issues": []}

    for mf in WIKI_DIR.rglob("*.md"):
        try:
            content = mf.read_text(encoding="utf-8")
            if not content.startswith("---"):
                continue
            end = content.find("---", 3)
            if end < 0:
                continue
            fm_text = content[3:end].strip()
            total += 1
            if "source_path:" not in fm_text:
                continue
            # Extract source_path value
            for line in fm_text.split("\n"):
                if line.strip().startswith("source_path:"):
                    sp = line.split(":", 1)[1].strip()
                    if sp.startswith("_INBOX"):
                        issues.append({
                            "file": str(mf.relative_to(PKG_ROOT)),
                            "current": sp,
                            "expected": sp.replace("_INBOX/imported/", "raw/imported_processed/"),
                        })
                    else:
                        correct += 1
        except:
            pass
    return {"total": total, "correct": correct, "issues": issues, "stale_count": len(issues)}


# ---------------------------------------------------------------------------
# Health checks
# ---------------------------------------------------------------------------
def check_frontmatter() -> List[Dict]:
    """Check all wiki pages for complete frontmatter."""
    issues = []
    required = {"created", "type", "tags"}
    if not WIKI_DIR.exists():
        return issues
    for mf in sorted(WIKI_DIR.rglob("*.md")):
        try:
            content = mf.read_text(encoding="utf-8")
            if not content.startswith("---"):
                issues.append({"file": str(mf.relative_to(PKG_ROOT)), "issue": "MISSING frontmatter"})
                continue
            end = content.find("---", 3)
            if end < 0:
                issues.append({"file": str(mf.relative_to(PKG_ROOT)), "issue": "MALFORMED frontmatter"})
                continue
            fm_text = content[3:end].strip()
            missing = []
            for key in required:
                if f"\n{key}:" not in fm_text and not fm_text.startswith(f"{key}:"):
                    missing.append(key)
            if missing:
                issues.append({"file": str(mf.relative_to(PKG_ROOT)), "issue": f"missing: {', '.join(missing)}"})
        except:
            pass
    return issues


def check_broken_links() -> List[Dict]:
    """Check for broken [[wikilinks]] in wiki pages."""
    import yaml
    all_pages = {}
    for mf in WIKI_DIR.rglob("*.md"):
        all_pages[mf.stem] = str(mf.relative_to(PKG_ROOT))

    broken = []
    link_pat = re.compile(r'\[\[([^\]|#]+)(?:[|#][^\]]+)?\]\]')
    code_pat = re.compile(r'`[^`]*`')  # inline code spans
    for mf in WIKI_DIR.rglob("*.md"):
        try:
            content = mf.read_text(encoding="utf-8")
            # Strip inline code spans before checking links
            clean = code_pat.sub('', content)
            for match in link_pat.finditer(clean):
                target = match.group(1)
                if target not in all_pages and "/" not in target:
                    broken.append({
                        "file": str(mf.relative_to(PKG_ROOT)),
                        "link": target,
                    })
        except:
            pass
    return broken


def check_unindexed() -> List[str]:
    """Check for wiki pages not in wiki/index.md."""
    if not WIKI_INDEX.exists():
        return ["wiki/index.md not found"]
    index_content = WIKI_INDEX.read_text(encoding="utf-8")
    link_pat = re.compile(r'\[\[([^\]|#]+)')
    indexed = set(link_pat.findall(index_content))

    unindexed = []
    for mf in WIKI_DIR.rglob("*.md"):
        rel = str(mf.relative_to(WIKI_DIR)).replace("\\", "/")
        if rel in ["index.md", "log.md"]:
            continue
        if mf.stem not in indexed:
            unindexed.append(str(mf.relative_to(PKG_ROOT)))
    return unindexed


def check_webpack_quality() -> List[Dict]:
    """Check webpack quality markings."""
    issues = []
    if not WEBPACKS_DIR.exists():
        return issues
    for d in sorted(WEBPACKS_DIR.iterdir()):
        if not d.is_dir():
            continue
        readme = d / "README.md"
        if not readme.exists():
            issues.append({"webpack": d.name, "issue": "missing README.md"})
            continue
        content = readme.read_text(encoding="utf-8")
        if "v1" in d.name.lower() or "测试" in d.name:
            if "⚠️" not in content:
                issues.append({"webpack": d.name, "issue": "v1 pack missing quality warning"})
    return issues


# ---------------------------------------------------------------------------
# Plan generation
# ---------------------------------------------------------------------------
def generate_plan() -> Dict:
    """Generate auto_ingest_plan.json."""
    inbox_files = scan_inbox()
    inbox_folders = scan_inbox_folders()
    webpacks = scan_webpacks()

    # Classify each item
    plan_items = []
    for item in inbox_files:
        ctype = classify_content(item["name"], item["ext"])
        item["content_type"] = ctype
        item["action"] = "ingest_inbox"
        item["wiki_targets"] = _get_wiki_targets(ctype)
        plan_items.append(item)

    for item in inbox_folders:
        item["content_type"] = "unknown"
        item["action"] = "ingest_folder"
        item["wiki_targets"] = ["wiki/sources/"]
        plan_items.append(item)

    for item in webpacks:
        if item.get("processed"):
            item["action"] = "skip"
        else:
            item["action"] = "ingest_webpack"
            item["wiki_targets"] = _get_webpack_wiki_targets(item["name"])
        plan_items.append(item)

    pending = [i for i in plan_items if i.get("action") not in ("skip",)]
    processed = [i for i in plan_items if i.get("action") == "skip"]

    plan = {
        "generated_at": datetime.now().isoformat(),
        "summary": {
            "total_items": len(plan_items),
            "pending": len(pending),
            "already_processed": len(processed),
            "inbox_files": len(inbox_files),
            "inbox_folders": len(inbox_folders),
            "webpacks": len(webpacks),
        },
        "pending": pending,
        "already_processed": processed,
    }
    return plan


def _get_wiki_targets(ctype: str) -> List[str]:
    """Get wiki page types to create based on content type."""
    targets = {
        "academic_paper": ["wiki/sources/", "wiki/concepts/"],
        "coursework": ["wiki/sources/", "wiki/outputs/"],
        "school_policy": ["wiki/sources/", "wiki/concepts/"],
        "project_ppt": ["wiki/sources/", "wiki/projects/"],
        "methodology": ["wiki/concepts/", "wiki/projects/PKB个人知识库/"],
        "unknown": ["wiki/sources/"],
    }
    return targets.get(ctype, ["wiki/sources/"])


def _get_webpack_wiki_targets(name: str) -> List[str]:
    """Get wiki targets based on webpack name."""
    name_lower = name.lower()
    if "github" in name_lower or "skill" in name_lower:
        return ["wiki/sources/", "wiki/concepts/", "wiki/projects/"]
    if "article" in name_lower or "wx" in name_lower:
        return ["wiki/sources/"]
    return ["wiki/sources/", "wiki/concepts/"]


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------
def generate_report(plan: Dict) -> str:
    """Generate auto_ingest_report.md."""
    s = plan["summary"]
    pending = plan["pending"]

    lines = [
        f"# PKB Auto Ingest Report",
        f"",
        f"> 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"",
        f"## 概览",
        f"",
        f"| 指标 | 数量 |",
        f"|------|------|",
        f"| 待处理项 | {s['pending']} |",
        f"| 已处理项 | {s['already_processed']} |",
        f"| INBOX 文件 | {s['inbox_files']} |",
        f"| INBOX 文件夹 | {s['inbox_folders']} |",
        f"| Webpacks | {s['webpacks']} |",
    ]

    if pending:
        lines.append("")
        lines.append("## 待处理项")
        lines.append("")
        lines.append("| # | 来源 | 名称 | 类型 | 建议操作 |")
        lines.append("|---|------|------|------|---------|")
        for i, item in enumerate(pending, 1):
            name = item.get("name", "")[:50]
            source = item.get("source", "?")
            ctype = item.get("content_type", "unknown")
            action = item.get("action", "?")
            lines.append(f"| {i} | {source} | {name} | {ctype} | {action} |")

    # Health summary
    fm_issues = check_frontmatter()
    broken = check_broken_links()
    unindexed = check_unindexed()
    webpack_issues = check_webpack_quality()
    stale = find_stale_inbox_refs()
    source_paths = check_source_paths()

    lines.append("")
    lines.append("## 健康检查")
    lines.append("")
    lines.append(f"| 检查项 | 状态 |")
    lines.append(f"|--------|------|")
    lines.append(f"| Frontmatter 完整 | {'✅' if not fm_issues else f'⚠️ {len(fm_issues)} issues'} |")
    lines.append(f"| 破损双链 | {'✅' if not broken else f'❌ {len(broken)} broken'} |")
    lines.append(f"| 未索引页面 | {'✅' if not unindexed else f'⚠️ {len(unindexed)} unindexed'} |")
    lines.append(f"| Stale _INBOX 引用 | {'✅' if not stale else f'⚠️ {len(stale)} stale'} |")
    sp_stale = source_paths.get('stale_count', 0)
    lines.append(f"| source_path 一致性 | {'✅' if sp_stale == 0 else '⚠️ ' + str(sp_stale) + ' stale'} |")
    lines.append(f"| Webpack 质量 | {'✅' if not webpack_issues else f'⚠️ {len(webpack_issues)} issues'} |")

    if fm_issues:
        lines.append("")
        lines.append("### Frontmatter Issues")
        for iss in fm_issues[:20]:
            lines.append(f"- {iss['file']}: {iss['issue']}")

    if broken:
        lines.append("")
        lines.append("### Broken Links")
        for b in broken[:20]:
            lines.append(f"- {b['file']} → [[{b['link']}]]")

    if unindexed:
        lines.append("")
        lines.append("### Unindexed Pages")
        for u in unindexed[:20]:
            lines.append(f"- {u}")

    return "\n".join(lines)


def generate_processed_manifest() -> Dict:
    """Generate manifest for raw/imported_processed/."""
    manifest_path = PROCESSED_DIR / "manifest.json"
    existing = {}
    if manifest_path.exists():
        try:
            existing = json.loads(manifest_path.read_text(encoding="utf-8"))
        except:
            pass

    files = []
    if PROCESSED_DIR.exists():
        for f in PROCESSED_DIR.iterdir():
            if f.is_file() and not f.name.startswith(".") and not f.name.startswith("_"):
                files.append({
                    "filename": f.name,
                    "size_kb": round(f.stat().st_size / 1024, 1),
                    "processed_at": datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
                })

    manifest = {
        "updated_at": datetime.now().isoformat(),
        "total_files": len(files),
        "files": files,
    }
    return manifest


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    import argparse
    parser = argparse.ArgumentParser(description="PKB Auto Ingest Orchestrator")
    parser.add_argument("--scan", action="store_true", help="Scan and print plan JSON")
    parser.add_argument("--check", action="store_true", help="Run health checks only")
    parser.add_argument("--report", action="store_true", help="Generate auto_ingest_report.md")
    parser.add_argument("--manifest", action="store_true", help="Generate processed manifest JSON")
    parser.add_argument("--full", action="store_true", help="Full scan + check + report (default)")
    parser.add_argument("--plan-file", default=None, help="Path to auto_ingest_plan.json output")
    parser.add_argument("--report-file", default=None, help="Path to auto_ingest_report.md output")

    args = parser.parse_args()
    if not any([args.scan, args.check, args.report, args.manifest, args.full]):
        args.full = True

    if args.scan or args.full:
        plan = generate_plan()
        plan_json = json.dumps(plan, ensure_ascii=False, indent=2)
        print(plan_json)
        if args.plan_file:
            Path(args.plan_file).write_text(plan_json, encoding="utf-8")
        else:
            plan_path = PKG_ROOT / "auto_ingest_plan.json"
            plan_path.write_text(plan_json, encoding="utf-8")

    if args.check or args.full:
        print("\n=== HEALTH CHECK ===", flush=True)
        fm = check_frontmatter()
        broken = check_broken_links()
        unindexed = check_unindexed()
        webpack_q = check_webpack_quality()
        stale = find_stale_inbox_refs()
        sp = check_source_paths()

        print(f"Frontmatter: {'✅ OK' if not fm else f'⚠️ {len(fm)} issues'}", flush=True)
        for f in fm[:10]:
            print(f"  - {f['file']}: {f['issue']}", flush=True)

        print(f"Broken links: {'✅ 0' if not broken else f'❌ {len(broken)}'}", flush=True)
        for b in broken[:10]:
            print(f"  - {b['file']} → [[{b['link']}]]", flush=True)

        print(f"Unindexed: {'✅ 0' if not unindexed else f'⚠️ {len(unindexed)}'}", flush=True)
        for u in unindexed[:10]:
            print(f"  - {u}", flush=True)

        print(f"Stale _INBOX refs: {'✅ 0' if not stale else f'⚠️ {len(stale)}'}", flush=True)
        for s in stale[:10]:
            print(f"  - {s[0]}: {s[1]}", flush=True)

        sp_sc = sp.get('stale_count', 0)
        print(f"source_path: {'✅ OK' if sp_sc == 0 else '⚠️ ' + str(sp_sc) + ' stale'}", flush=True)
        for iss in sp['issues'][:10]:
            print(f"  - {iss['file']}: {iss['current']} → {iss['expected']}", flush=True)

        print(f"Webpack quality: {'✅ OK' if not webpack_q else f'⚠️ {len(webpack_q)} issues'}", flush=True)
        for w in webpack_q[:10]:
            print(f"  - {w['webpack']}: {w['issue']}", flush=True)

        all_ok = not (fm or broken or unindexed or sp['issues'])
        if all_ok:
            print("\n🏁 HEALTH CHECK: PASSED", flush=True)
        else:
            print(f"\n🏁 HEALTH CHECK: {len(fm or [])} fm + {len(broken)} broken + {len(unindexed)} unindexed + {sp['stale_count']} path issues", flush=True)

    if args.report or args.full:
        plan = generate_plan()
        report = generate_report(plan)
        report_path = args.report_file or str(PKG_ROOT / "auto_ingest_report.md")
        Path(report_path).write_text(report, encoding="utf-8")
        print(f"\nReport: {report_path}", flush=True)

    if args.manifest or args.full:
        manifest = generate_processed_manifest()
        PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
        manifest_path = PROCESSED_DIR / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Manifest: {manifest_path} ({manifest['total_files']} files)", flush=True)


if __name__ == "__main__":
    main()
