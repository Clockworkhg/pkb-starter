#!/usr/bin/env python3
"""PKB documentation freshness checker.

Detects drift between the filesystem and the 5 project docs:
  index.md, COMMANDS.md, SKILL_LINKS.md, AGENTS.md, CLAUDE.md, log.md

Usage:
    python tools/docs_update.py            # human-readable report
    python tools/docs_update.py --json     # machine-readable (for hooks/LLM consumption)
    python tools/docs_update.py --summary  # one-line summary for /save integration

The script detects WHAT is stale — the LLM does the actual editing.
"""

import os, sys, json, subprocess
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parent.parent

# ── What we track ─────────────────────────────────────────────
TRACKED_DOCS = ["index.md", "COMMANDS.md", "SKILL_LINKS.md", "AGENTS.md", "CLAUDE.md", "log.md"]

# Check: tools/ Python scripts
TOOLS_DIR = ROOT / "tools"

# Check: .claude/skills/ subdirectories
SKILLS_DIR = ROOT / ".claude" / "skills"

# Check: .claude/commands/ markdown files
COMMANDS_DIR = ROOT / ".claude" / "commands"

# Check: wiki/ pages
WIKI_DIR = ROOT / "wiki"


def get_tools():
    """List all Python scripts in tools/ (excluding __init__)."""
    if not TOOLS_DIR.is_dir():
        return []
    return sorted([
        f"tools/{p.name}"
        for p in TOOLS_DIR.glob("*.py")
        if not p.name.startswith("_") and not p.name.startswith(".")
    ])


def get_skills():
    """List all skill directories in .claude/skills/."""
    if not SKILLS_DIR.is_dir():
        return []
    return sorted([
        d.name
        for d in SKILLS_DIR.iterdir()
        if d.is_dir() and not d.name.startswith("_") and not d.name.startswith(".")
    ])


def get_commands():
    """List all slash commands in .claude/commands/."""
    if not COMMANDS_DIR.is_dir():
        return []
    return sorted([
        p.stem
        for p in COMMANDS_DIR.glob("*.md")
        if not p.name.startswith("_")
    ])


def get_wiki_pages():
    """List all wiki pages (concepts + sources + projects)."""
    if not WIKI_DIR.is_dir():
        return {}
    pages = {"concepts": [], "sources": [], "projects": []}
    for sub in ["concepts", "sources", "projects"]:
        subdir = WIKI_DIR / sub
        if subdir.is_dir():
            pages[sub] = sorted([
                p.stem
                for p in subdir.glob("*.md")
                if not p.name.startswith("_") and p.name != "index"
            ])
    return pages


def get_recent_git_log(n=5):
    """Get last N commit short hashes and subjects as tuples (hash, subject)."""
    try:
        result = subprocess.run(
            ["git", "log", f"-{n}", "--format=%h %s"],
            capture_output=True, text=True, timeout=5,
            cwd=str(ROOT), encoding='utf-8', errors='replace'
        )
        entries = []
        for line in result.stdout.strip().split("\n"):
            if not line.strip():
                continue
            parts = line.split(" ", 1)
            if len(parts) == 2:
                entries.append((parts[0], parts[1]))
            else:
                entries.append(("", parts[0]))
        return entries
    except Exception:
        return []


def check_doc_freshness(doc_name):
    """Check if a doc file references all current tools/skills/etc."""
    doc_path = ROOT / doc_name
    if not doc_path.exists():
        return {"missing": True, "stale_items": [f"File {doc_name} does not exist"]}

    content = doc_path.read_text(encoding="utf-8")
    stale = []

    if doc_name == "index.md":
        # Check tools mentioned
        for tool in get_tools():
            tool_name = Path(tool).name
            if tool_name not in content:
                stale.append(f"tool/{tool_name}")

        # Check skills referenced (index.md links to SKILL_LINKS.md for full catalog)
        # Only flag if SKILL_LINKS link itself is missing
        if "SKILL_LINKS" not in content:
            stale.append("skills: SKILL_LINKS.md cross-ref missing")

        # Check wiki pages mentioned
        wiki = get_wiki_pages()
        total_wiki = sum(len(v) for v in wiki.values())
        mentioned_wiki = sum(
            1 for cat in wiki.values() for p in cat
            if p in content
        )
        if total_wiki > 0 and mentioned_wiki < total_wiki * 0.3:
            stale.append(f"wiki pages: {mentioned_wiki}/{total_wiki} referenced")

        # Check date freshness
        today = datetime.now().strftime("%Y-%m-%d")
        if f"最后更新: {today}" not in content and f"最后更新：{today}" not in content:
            stale.append("date: not today")

    elif doc_name == "COMMANDS.md":
        # Check commands mentioned
        cmds = get_commands()
        mentioned = sum(1 for c in cmds if f"/{c}" in content or c in content)
        if len(cmds) > 0 and mentioned < len(cmds) * 0.6:
            missing_cmds = [c for c in cmds if f"/{c}" not in content and c not in content]
            stale.append(f"commands: {mentioned}/{len(cmds)} mentioned, missing: {missing_cmds[:5]}")

    elif doc_name == "SKILL_LINKS.md":
        skills = get_skills()
        mentioned = sum(1 for s in skills if s in content)
        if len(skills) > 0 and mentioned < len(skills) * 0.5:
            missing = [s for s in skills if s not in content]
            stale.append(f"skills: {mentioned}/{len(skills)} mentioned, missing: {missing[:10]}")

    elif doc_name == "log.md":
        # Check if recent commit hashes appear in the log
        commits = get_recent_git_log(5)
        mentioned = 0
        for commit_hash, subject in commits:
            if commit_hash and commit_hash in content:
                mentioned += 1
            elif subject[:30] in content:
                mentioned += 1
        if len(commits) > 0 and mentioned < len(commits) * 0.5:
            stale.append(f"git log: {mentioned}/{len(commits)} recent commits mentioned")

    elif doc_name == "AGENTS.md":
        # Check key sections exist (one-* through fourteen-*)
        import re
        section_numbers = set()
        for m in re.finditer(r'##\s+([一二三四五六七八九十]+)、', content):
            num_str = m.group(1)
            # Convert Chinese numeral to integer
            chinese_to_int = {
                '一': 1, '二': 2, '三': 3, '四': 4, '五': 5,
                '六': 6, '七': 7, '八': 8, '九': 9, '十': 10,
                '十一': 11, '十二': 12, '十三': 13, '十四': 14,
            }
            section_numbers.add(chinese_to_int.get(num_str, 0))

        expected_sections = set(range(1, 15))  # §1–§14
        missing_sections = expected_sections - section_numbers
        if missing_sections:
            stale.append(f"sections missing: {sorted(missing_sections)}")

        # Check version/date (uses "最后更新：" with full-width colon)
        today = datetime.now().strftime("%Y-%m-%d")
        if f"最后更新：{today}" not in content:
            stale.append("date: not today")

        # Check that CLAUDE.md is cross-referenced
        if "CLAUDE.md" not in content:
            stale.append("cross-ref: CLAUDE.md not mentioned")

    elif doc_name == "CLAUDE.md":
        # Check file exists (already handled by outer check)
        # Check key sections
        required_sections = [
            "项目身份", "关键路径", "Skill 路由速查", "编码约定",
            "工具速查", "常用工作流", "行为准则"
        ]
        for section in required_sections:
            if section not in content:
                stale.append(f"section missing: {section}")

        # Check tools mentioned
        for tool in get_tools():
            tool_name = Path(tool).name
            if tool_name not in content:
                stale.append(f"tool/{tool_name} not mentioned")

        # Check date freshness
        today = datetime.now().strftime("%Y-%m-%d")
        if f"最后更新: {today}" not in content and f"最后更新：{today}" not in content:
            stale.append("date: not today")

    return {"missing": False, "stale_items": stale, "path": str(doc_path)}


def main():
    import argparse
    parser = argparse.ArgumentParser(description="PKB documentation freshness checker")
    parser.add_argument("--json", action="store_true", help="Machine-readable output")
    parser.add_argument("--summary", action="store_true", help="One-line summary for /save")
    args = parser.parse_args()

    report = {}
    total_stale = 0

    for doc in TRACKED_DOCS:
        result = check_doc_freshness(doc)
        if result["missing"] or result["stale_items"]:
            total_stale += len(result["stale_items"])
        report[doc] = result

    # Add context
    report["_context"] = {
        "tools": get_tools(),
        "skills": get_skills(),
        "commands": get_commands(),
        "wiki_pages": get_wiki_pages(),
        "recent_commits": [f"{h} {s}" for h, s in get_recent_git_log(5)],
        "total_stale": total_stale,
    }

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0 if total_stale == 0 else 1

    if args.summary:
        if total_stale == 0:
            print("[OK] Docs up to date.")
        else:
            stale_docs = [d for d, r in report.items() if not d.startswith("_") and r.get("stale_items")]
            print(f"[docs_update] {total_stale} stale entries across {len(stale_docs)} docs: " +
                  ", ".join(f"{d}({len(report[d]['stale_items'])})" for d in stale_docs))
        return 0 if total_stale == 0 else 1

    # Human-readable
    print("=" * 60)
    print("  PKB Documentation Freshness Check")
    print("=" * 60)

    for doc in TRACKED_DOCS:
        r = report[doc]
        if r["missing"]:
            print(f"  [MISSING] {doc}: FILE MISSING")
        elif r["stale_items"]:
            print(f"  [STALE]  {doc}: {len(r['stale_items'])} stale items")
            for item in r["stale_items"]:
                print(f"           - {item}")
        else:
            print(f"  [OK]     {doc}: up to date")

    print("=" * 60)
    ctx = report["_context"]
    print(f"  Tools: {len(ctx['tools'])} | Skills: {len(ctx['skills'])} | Commands: {len(ctx['commands'])}")
    wiki_total = sum(len(v) for v in ctx["wiki_pages"].values())
    print(f"  Wiki pages: {wiki_total} (c:{len(ctx['wiki_pages']['concepts'])} s:{len(ctx['wiki_pages']['sources'])} p:{len(ctx['wiki_pages']['projects'])})")
    print("=" * 60)

    if total_stale > 0:
        print(f"\n  Run /save to auto-fix -- the LLM will update docs before committing.")
    return 0 if total_stale == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
