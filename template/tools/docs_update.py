#!/usr/bin/env python3
"""PKB documentation freshness checker and safe applier.

Detects drift between the filesystem and the 6 project docs:
  index.md, COMMANDS.md, SKILL_LINKS.md, AGENTS.md, CLAUDE.md, log.md

Also tracks: tools/ scripts, .claude/skills/, .claude/commands/, .claude/hooks/, wiki/ pages.

Usage:
    python tools/docs_update.py --check      # detect staleness, no modifications (default)
    python tools/docs_update.py --apply      # safely apply fixes (requires explicit flag)
    python tools/docs_update.py --json       # machine-readable (detection only)
    python tools/docs_update.py --summary    # one-line summary for /save integration

--check (default): Reports stale items. Does NOT modify any files.
--apply: Applies safe, targeted fixes to non-protected documentation.
         Protected files (CLAUDE.md, AGENTS.md) are reported for manual review only.
         Always lists which files will be modified before writing.
"""

import os, sys, json, re, subprocess
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parent.parent

# ── Configuration ─────────────────────────────────────────────────
CURRENT_VERSION = "v0.6.3-alpha"
TODAY = datetime.now().strftime("%Y-%m-%d")

# Docs that are safe to auto-fix with --apply
SAFE_DOCS = ["index.md", "COMMANDS.md", "SKILL_LINKS.md", "log.md"]

# Docs that are protected — only checked, never auto-modified
PROTECTED_DOCS = ["AGENTS.md", "CLAUDE.md"]

# ── What we track ─────────────────────────────────────────────────
TRACKED_DOCS = SAFE_DOCS + PROTECTED_DOCS

TOOLS_DIR = ROOT / "tools"
SKILLS_DIR = ROOT / ".claude" / "skills"
COMMANDS_DIR = ROOT / ".claude" / "commands"
HOOKS_DIR = ROOT / ".claude" / "hooks"
WIKI_DIR = ROOT / "wiki"


# ──────────────────────────────────────────────────────────────────
#  FS inventory helpers
# ──────────────────────────────────────────────────────────────────

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


def get_hooks():
    """List all hook scripts in .claude/hooks/ (excluding shared lib and pycache)."""
    if not HOOKS_DIR.is_dir():
        return []
    return sorted([
        p.name
        for p in HOOKS_DIR.glob("*.py")
        if not p.name.startswith("_")
        and not p.name.startswith(".")
        and p.name not in ("hook_lib.py", "test_hooks.py")
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


# ──────────────────────────────────────────────────────────────────
#  Staleness detection
# ──────────────────────────────────────────────────────────────────

def check_doc_freshness(doc_name):
    """Check if a doc file references all current tools/skills/etc."""
    doc_path = ROOT / doc_name
    if not doc_path.exists():
        return {"missing": True, "stale_items": [f"File {doc_name} does not exist"]}

    content = doc_path.read_text(encoding="utf-8")
    stale = []

    if doc_name == "index.md":
        for tool in get_tools():
            tool_name = Path(tool).name
            if tool_name not in content:
                stale.append(f"tool/{tool_name}")

        if "SKILL_LINKS" not in content:
            stale.append("skills: SKILL_LINKS.md cross-ref missing")

        wiki = get_wiki_pages()
        total_wiki = sum(len(v) for v in wiki.values())
        mentioned_wiki = sum(
            1 for cat in wiki.values() for p in cat
            if p in content
        )
        if total_wiki > 0 and mentioned_wiki < total_wiki * 0.3:
            stale.append(f"wiki pages: {mentioned_wiki}/{total_wiki} referenced")

        # Date check: only flag YYYY-MM-DD in frontmatter/Last-updated lines, not in body format examples
        if re.search(r'(created|updated):\s*YYYY-MM-DD', content) or \
           re.search(r'(最后更新[：:]|Last updated:)\s*YYYY-MM-DD', content):
            stale.append("date: placeholder YYYY-MM-DD in date field (should be actual date)")
        elif f"最后更新: {TODAY}" not in content and f"最后更新：{TODAY}" not in content \
                and f"Last updated: {TODAY}" not in content:
            stale.append(f"date: not {TODAY} in footer")

        # Hook reference check
        if ".claude/hooks/" not in content and "hooks" not in content.lower():
            stale.append("hooks: .claude/hooks/ not referenced in system section")

        # Version check — detect old/placeholder versions
        if "v0.5.0-alpha" in content:
            stale.append("version: v0.5.0-alpha found (should be v0.6.3-alpha)")

    elif doc_name == "COMMANDS.md":
        cmds = get_commands()
        mentioned = sum(1 for c in cmds if f"/{c}" in content or c in content)
        if len(cmds) > 0 and mentioned < len(cmds) * 0.6:
            missing_cmds = [c for c in cmds if f"/{c}" not in content and c not in content]
            stale.append(f"commands: {mentioned}/{len(cmds)} mentioned, missing: {missing_cmds[:5]}")

        # Check for docs-update command reference
        if "docs-update" in cmds and "/docs-update" not in content:
            stale.append("command: /docs-update not documented in COMMANDS.md")

    elif doc_name == "SKILL_LINKS.md":
        skills = get_skills()
        mentioned = sum(1 for s in skills if s in content)
        if len(skills) > 0 and mentioned < len(skills) * 0.5:
            missing = [s for s in skills if s not in content]
            stale.append(f"skills: {mentioned}/{len(skills)} mentioned, missing: {missing[:10]}")

    elif doc_name == "log.md":
        commits = get_recent_git_log(5)
        mentioned = 0
        for commit_hash, subject in commits:
            if commit_hash and commit_hash in content:
                mentioned += 1
            elif subject[:30] in content:
                mentioned += 1
        if len(commits) > 0 and mentioned < len(commits) * 0.5:
            stale.append(f"git log: {mentioned}/{len(commits)} recent commits mentioned")

        # Date check: only flag YYYY-MM-DD in frontmatter/Last-updated lines
        if re.search(r'(created|updated):\s*YYYY-MM-DD', content) or \
           re.search(r'(最后更新[：:]|Last updated:)\s*YYYY-MM-DD', content):
            stale.append("date: placeholder YYYY-MM-DD in date field (should be actual date)")
        elif f"最后更新：{TODAY}" not in content and f"最后更新: {TODAY}" not in content \
                and f"Last updated: {TODAY}" not in content:
            stale.append(f"date: not {TODAY} in footer")

    elif doc_name == "AGENTS.md":
        # Detect language: Chinese AGENTS uses "## 一、", English uses "## I."
        if re.search(r'##\s+[一二三四五六七八九十]+、', content):
            # Chinese format
            section_numbers = set()
            for m in re.finditer(r'##\s+([一二三四五六七八九十]+)、', content):
                num_str = m.group(1)
                chinese_to_int = {
                    '一': 1, '二': 2, '三': 3, '四': 4, '五': 5,
                    '六': 6, '七': 7, '八': 8, '九': 9, '十': 10,
                    '十一': 11, '十二': 12, '十三': 13, '十四': 14, '十五': 15,
                }
                section_numbers.add(chinese_to_int.get(num_str, 0))
        else:
            # English/Roman numeral format
            roman_to_int = {
                'I': 1, 'II': 2, 'III': 3, 'IV': 4, 'V': 5,
                'VI': 6, 'VII': 7, 'VIII': 8, 'IX': 9, 'X': 10,
                'XI': 11, 'XII': 12, 'XIII': 13, 'XIV': 14, 'XV': 15,
            }
            section_numbers = set()
            for m in re.finditer(r'##\s+([IVX]+)\.\s', content):
                num_str = m.group(1)
                section_numbers.add(roman_to_int.get(num_str, 0))

        expected_sections = set(range(1, 16))
        missing_sections = expected_sections - section_numbers
        if missing_sections:
            stale.append(f"sections missing: {sorted(missing_sections)}")

        # Date check: only flag YYYY-MM-DD in frontmatter/Last-updated lines, not in body format examples
        if re.search(r'(created|updated):\s*YYYY-MM-DD', content) or \
           re.search(r'(最后更新[：:]|Last updated:)\s*YYYY-MM-DD', content):
            stale.append("date: placeholder YYYY-MM-DD in date field (should be actual date)")
        elif f"最后更新：{TODAY}" not in content and f"最后更新: {TODAY}" not in content \
                and f"Last updated: {TODAY}" not in content:
            stale.append(f"date: not {TODAY} in footer")

        if "CLAUDE.md" not in content:
            stale.append("cross-ref: CLAUDE.md not mentioned")

        if "十五、Hooks" not in content and "Hooks 系统" not in content and "XV. Hooks" not in content:
            stale.append("section missing: Hooks 系统 / XV. Hooks")

        hooks = get_hooks()
        hooks_mentioned = sum(1 for h in hooks if h in content or h.replace(".py", "") in content)
        if len(hooks) > 0 and hooks_mentioned < len(hooks) * 0.5:
            missing = [h for h in hooks if h not in content and h.replace(".py", "") not in content]
            stale.append(f"hooks: {hooks_mentioned}/{len(hooks)} scripts mentioned, missing: {missing}")

    elif doc_name == "CLAUDE.md":
        # CLAUDE.md uses English section headers
        required_sections = [
            "Project Identity", "Key Paths", "Skill Routing",
            "Coding Conventions", "Tools Reference", "Common Workflows",
            "Code of Conduct", "Hooks"
        ]
        for section in required_sections:
            if section not in content:
                stale.append(f"section missing: {section}")

        for tool in get_tools():
            tool_name = Path(tool).name
            if tool_name not in content:
                stale.append(f"tool/{tool_name} not mentioned")

        for hook in get_hooks():
            hook_stem = hook.replace(".py", "")
            if hook not in content and hook_stem not in content:
                stale.append(f"hook/{hook} not mentioned")

        # Date check
        if "YYYY-MM-DD" in content:
            stale.append("date: placeholder YYYY-MM-DD found (should be actual date)")
        elif f"最后更新: {TODAY}" not in content and f"最后更新：{TODAY}" not in content \
                and f"Last updated: {TODAY}" not in content:
            stale.append(f"date: not {TODAY}")

    return {"missing": False, "stale_items": stale, "path": str(doc_path)}


# ──────────────────────────────────────────────────────────────────
#  Safe apply helpers
# ──────────────────────────────────────────────────────────────────

def safe_apply_doc(doc_name, stale_items):
    """Attempt safe fixes for a non-protected doc. Returns list of actions taken."""
    doc_path = ROOT / doc_name
    if not doc_path.exists():
        return [f"SKIP {doc_name}: file missing, cannot apply"]
    if doc_name in PROTECTED_DOCS:
        return [f"PROTECTED {doc_name}: manual review required — not auto-modified"]

    content = doc_path.read_text(encoding="utf-8")
    original = content
    actions = []

    for item in stale_items:
        prefix = item.split(":")[0].strip() if ":" in item else ""

        # ── Date fixes ──────────────────────────────────────────
        if prefix == "date":
            if "placeholder YYYY-MM-DD" in item:
                # Replace YYYY-MM-DD placeholders in frontmatter and "Last updated" lines
                content = re.sub(
                    r'(created|updated):\s*YYYY-MM-DD',
                    rf'\1: {TODAY}',
                    content
                )
                content = re.sub(
                    r'(最后更新[：:]\s*)YYYY-MM-DD',
                    rf'\1{TODAY}',
                    content
                )
                content = re.sub(
                    r'(Last updated:\s*)YYYY-MM-DD',
                    rf'\1{TODAY}',
                    content
                )
                actions.append(f"FIXED {doc_name}: replaced YYYY-MM-DD placeholder → {TODAY}")
            elif f"not {TODAY}" in item:
                # Update date in "最后更新" and "Last updated" footers
                content = re.sub(
                    r'(最后更新[：:]\s*)\d{4}-\d{2}-\d{2}',
                    rf'\1{TODAY}',
                    content
                )
                content = re.sub(
                    r'(Last updated:\s*)\d{4}-\d{2}-\d{2}',
                    rf'\1{TODAY}',
                    content
                )
                actions.append(f"FIXED {doc_name}: updated footer date → {TODAY}")

        # ── Version fixes ─────────────────────────────────────────
        elif prefix == "version":
            # Only replace explicit old version strings in version-context fields
            # Pattern: "版本：v<old>" or "version: v<old>" — must be field-anchored
            old_versions = re.findall(r'v\d+\.\d+\.\d+-alpha', item)
            for ov in old_versions:
                if ov != CURRENT_VERSION:
                    # Replace only in version-field context (anchored to a field label)
                    content = re.sub(
                        rf'(版本[：:]\s*){re.escape(ov)}',
                        rf'\1{CURRENT_VERSION}',
                        content
                    )
                    content = re.sub(
                        rf'(version[：:\s]*){re.escape(ov)}',
                        rf'\1{CURRENT_VERSION}',
                        content,
                        flags=re.IGNORECASE
                    )
                    actions.append(f"FIXED {doc_name}: version {ov} → {CURRENT_VERSION}")

    if content != original:
        doc_path.write_text(content, encoding="utf-8")
        if not actions:
            actions.append(f"APPLIED {doc_name}: structural fixes applied")

    if not actions:
        actions.append(f"OK {doc_name}: no changes needed")

    return actions


def safe_apply_protected(doc_name, stale_items):
    """Report staleness for a protected doc without modifying it."""
    actions = []
    actions.append(f"PROTECTED {doc_name}: manual review required — not auto-modified")
    for item in stale_items:
        actions.append(f"  → {item}")
    return actions


# ──────────────────────────────────────────────────────────────────
#  Main
# ──────────────────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="PKB documentation freshness checker and safe applier"
    )
    parser.add_argument("--json", action="store_true", help="Machine-readable output")
    parser.add_argument("--summary", action="store_true", help="One-line summary for /save")
    parser.add_argument("--check", action="store_true", help="Check only — report staleness, no modifications (default)")
    parser.add_argument("--apply", action="store_true", help="Apply safe fixes to non-protected documentation files")
    args = parser.parse_args()

    # Run detection
    report = {}
    total_stale = 0

    for doc in TRACKED_DOCS:
        result = check_doc_freshness(doc)
        if result["missing"] or result["stale_items"]:
            total_stale += len(result["stale_items"])
        report[doc] = result

    ctx = {
        "tools": get_tools(),
        "skills": get_skills(),
        "commands": get_commands(),
        "hooks": get_hooks(),
        "wiki_pages": get_wiki_pages(),
        "recent_commits": [f"{h} {s}" for h, s in get_recent_git_log(5)],
        "total_stale": total_stale,
        "protected_docs": PROTECTED_DOCS,
        "safe_docs": SAFE_DOCS,
        "current_version": CURRENT_VERSION,
        "check_date": TODAY,
    }
    report["_context"] = ctx

    # ── --json mode (detection only) ──────────────────────────
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0 if total_stale == 0 else 1

    # ── --summary mode ────────────────────────────────────────
    if args.summary:
        if total_stale == 0:
            print("[OK] Docs up to date.")
        else:
            stale_docs = [d for d, r in report.items() if not d.startswith("_") and r.get("stale_items")]
            print(f"[docs_update] {total_stale} stale entries across {len(stale_docs)} docs: " +
                  ", ".join(f"{d}({len(report[d]['stale_items'])})" for d in stale_docs))
        return 0 if total_stale == 0 else 1

    # ── --apply mode ───────────────────────────────────────────
    if args.apply:
        print("=" * 60)
        print("  PKB Documentation Update — APPLY MODE")
        print("=" * 60)
        print()
        print(f"  Version: {CURRENT_VERSION}")
        print(f"  Date:    {TODAY}")
        print(f"  Protected (manual review only): {', '.join(PROTECTED_DOCS)}")
        print(f"  Safe to modify: {', '.join(SAFE_DOCS)}")
        print()

        # List plan
        files_to_modify = []
        for doc in SAFE_DOCS:
            r = report[doc]
            if r.get("stale_items"):
                files_to_modify.append(doc)

        if files_to_modify:
            print("  Files to modify:")
            for f in files_to_modify:
                print(f"    - {f} ({len(report[f].get('stale_items', []))} stale items)")

        protected_stale = [d for d in PROTECTED_DOCS if report[d].get("stale_items")]
        if protected_stale:
            print()
            print("  Protected files needing manual review:")
            for d in protected_stale:
                print(f"    - {d} ({len(report[d].get('stale_items', []))} stale items)")

        if not files_to_modify and not protected_stale:
            print("  All docs up to date. Nothing to do.")
            print("=" * 60)
            return 0

        if not files_to_modify:
            print()
            print("  No safe files to auto-modify.")
            if protected_stale:
                print("  Consider manually reviewing protected files listed above.")
            print("=" * 60)
            return 0 if not protected_stale else 1

        print()
        print("  Applying fixes...")
        print()

        all_actions = []
        for doc in SAFE_DOCS:
            r = report[doc]
            if r.get("stale_items") or r.get("missing"):
                actions = safe_apply_doc(doc, r.get("stale_items", []))
                all_actions.extend(actions)
                for a in actions:
                    print(f"  {a}")

        for doc in PROTECTED_DOCS:
            r = report[doc]
            if r.get("stale_items"):
                actions = safe_apply_protected(doc, r.get("stale_items", []))
                all_actions.extend(actions)
                for a in actions:
                    print(f"  {a}")

        print()
        print("=" * 60)
        print(f"  Done. {len([a for a in all_actions if a.startswith('FIXED') or a.startswith('APPLIED')])} fixes applied.")
        if protected_stale:
            print(f"  {len(protected_stale)} protected file(s) require manual review.")
        print("=" * 60)
        return 0 if total_stale == 0 else 0  # --apply always returns 0 (non-fatal)

    # ── --check mode (default) ─────────────────────────────────
    print("=" * 60)
    print("  PKB Documentation Freshness Check")
    print("=" * 60)

    for doc in TRACKED_DOCS:
        r = report[doc]
        is_protected = doc in PROTECTED_DOCS
        marker = " [PROTECTED]" if is_protected else ""
        if r["missing"]:
            print(f"  [MISSING] {doc}: FILE MISSING")
        elif r["stale_items"]:
            print(f"  [STALE]  {doc}{marker}: {len(r['stale_items'])} stale items")
            for item in r["stale_items"]:
                print(f"           - {item}")
        else:
            print(f"  [OK]     {doc}: up to date")

    print("=" * 60)
    ctx = report["_context"]
    print(f"  Tools: {len(ctx['tools'])} | Skills: {len(ctx['skills'])} | Commands: {len(ctx['commands'])} | Hooks: {len(ctx['hooks'])}")
    wiki_total = sum(len(v) for v in ctx["wiki_pages"].values())
    print(f"  Wiki pages: {wiki_total} (c:{len(ctx['wiki_pages']['concepts'])} s:{len(ctx['wiki_pages']['sources'])} p:{len(ctx['wiki_pages']['projects'])})")
    print(f"  Version: {CURRENT_VERSION} | Date: {TODAY}")
    print("=" * 60)

    if total_stale > 0:
        print()
        print(f"  {total_stale} stale items detected.")
        protected_stale = [d for d in PROTECTED_DOCS if report[d].get("stale_items")]
        safe_stale = [d for d in SAFE_DOCS if report[d].get("stale_items")]
        if safe_stale:
            print(f"  Safe to auto-fix: {', '.join(safe_stale)}")
            print(f"  Run: python tools/docs_update.py --apply")
        if protected_stale:
            print(f"  Protected — manual review required: {', '.join(protected_stale)}")
            print(f"  Do NOT use --apply on protected files. Edit them manually.")
    else:
        print()
        print("  Docs are up to date.")

    return 0 if total_stale == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
