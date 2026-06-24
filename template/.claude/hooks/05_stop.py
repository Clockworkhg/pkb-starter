#!/usr/bin/env python3
"""
Stop Hook for PKB — runs before Claude Code exits the session.

Actions:
  1. Detect uncommitted changes (git status)
  2. Warn if critical files are modified (settings.json, AGENTS.md, CLAUDE.md)
  3. Check for stale files in _INBOX/imported/ (> 24h old)
  4. Print session summary (files changed, wiki pages, recent commits)
  5. Update active task state timestamp if task exists

Always returns 0 — never blocks exit.
Bun/claude-mem failures are silently ignored (these are optional MCP services).

Usage:
  python .claude/hooks/05_stop.py            # normal mode
  python .claude/hooks/05_stop.py --dry-run  # print what would be reported
"""

import os
import re
import sys
import time
import json
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hook_lib import (
    warn, info, ok, is_dry_run,
    get_root, git_uncommitted_files, git_recent_commits,
    count_wiki_pages, is_safe_to_run,
)

# Files that deserve a strong reminder if modified
CRITICAL_FILES = [
    ".claude/settings.json",
    ".claude/settings.local.json",
    "AGENTS.md",
    "CLAUDE.md",
    ".gitignore",
    ".mcp.json",
]


def check_uncommitted() -> list:
    """Return list of uncommitted files."""
    return git_uncommitted_files()


def check_critical_modifications(uncommitted: list) -> list:
    """Return list of critical files among uncommitted."""
    critical = []
    for f in uncommitted:
        f_norm = f.replace("\\", "/")
        for cf in CRITICAL_FILES:
            if f_norm == cf or f_norm.endswith("/" + cf):
                critical.append(f)
                break
    return critical


def check_stale_inbox(hours: int = 24) -> list:
    """Return list of stale files in _INBOX/imported/ that are older than `hours`."""
    root = get_root()
    inbox = root / "_INBOX" / "imported"
    if not inbox.exists():
        return []
    stale = []
    cutoff = time.time() - (hours * 3600)
    try:
        for f in inbox.iterdir():
            if f.is_file():
                mtime = f.stat().st_mtime
                if mtime < cutoff:
                    age_hours = (time.time() - mtime) / 3600
                    stale.append((f.name, age_hours))
    except Exception:
        pass
    return stale


def refresh_hot_md():
    """Refresh wiki/hot.md with session summary.

    Lists recently modified wiki pages, updates the recent operations section.
    Controls size to ~500 words / ~3000 chars. Non-fatal.
    """
    root = get_root()
    hot_path = root / "wiki" / "hot.md"
    if not hot_path.exists():
        return

    dry = is_dry_run()
    if dry:
        info("[DRY RUN] Would refresh wiki/hot.md")
        return

    try:
        from datetime import datetime, timezone

        content = hot_path.read_text(encoding="utf-8", errors="replace")

        # Preserve existing "当前活跃主题" section if present
        active_topics_match = re.search(
            r"## 当前活跃主题\r?\n(.*?)(?=\r?\n## |\Z)", content, re.DOTALL
        )
        active_topics_section = ""
        if active_topics_match:
            active_body = active_topics_match.group(1).strip()
            if active_body and active_body != "（见上方最近操作）":
                active_topics_section = f"## 当前活跃主题\n{active_body}"
            else:
                active_topics_section = "## 当前活跃主题\n<!-- 由 Agent 手动维护 -->\n（见上方最近操作）"

        # Get recently modified wiki pages (top 10, exclude self + _prefix files)
        wiki_root = root / "wiki"
        wiki_files = []
        try:
            for f in sorted(
                wiki_root.rglob("*.md"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            ):
                if f.name.startswith("_") or f.name == "hot.md":
                    continue
                rel = f.relative_to(wiki_root)
                wiki_files.append(str(rel).replace("\\", "/"))
                if len(wiki_files) >= 10:
                    break
        except Exception:
            pass

        # Prune recent ops to last 4 + add session stamp
        # Use \r?\n for Windows CRLF compatibility
        recent_match = re.search(
            r"## 最近操作\r?\n(.*?)(?=\r?\n## |\Z)", content, re.DOTALL
        )
        ops_lines = []
        if recent_match:
            ops_lines = [l for l in recent_match.group(1).split("\n") if l.strip().startswith("-")]
        ops_lines = ops_lines[:4]

        today = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d")
        session_stamp = f"- {today}: Session completed — see [[log|操作日志]] for details"
        ops_lines.insert(0, session_stamp)

        # Build the hot.md content
        recent_files = "\n".join(f"- `{f}`" for f in wiki_files[:10])

        new_hot = f"""---
created: {today}
updated: {today}
tags: [meta, cache, auto-generated]
type: system
---

# Hot Cache

> 最近上下文摘要。每次会话开始先读此文件（~500 tok）。
> 会话结束自动刷新。

## 最近操作
{chr(10).join(ops_lines)}

{active_topics_section}

## 最近变更的文件
{recent_files}

---

> 自动生成。控制在 ~500 words 以内。
"""

        if new_hot.strip() != content.strip():
            # Atomic write: tmp → rename to avoid truncated file on timeout/crash
            tmp = hot_path.with_suffix(".md.tmp")
            tmp.write_text(new_hot, encoding="utf-8", errors="replace")
            tmp.replace(hot_path)
            ok("wiki/hot.md auto-refreshed")
    except Exception:
        pass  # Non-fatal — never block exit


def touch_active_task():
    """Update the active task's updated_at timestamp if it exists. Non-fatal."""
    root = get_root()
    task_file = root / ".pkb-local" / "state" / "active-task.json"
    if not task_file.exists():
        return
    try:
        from datetime import datetime, timezone
        data = json.loads(task_file.read_text(encoding="utf-8"))
        data["updated_at"] = datetime.now(timezone.utc).astimezone().isoformat()
        # Atomic write via tmp
        tmp = task_file.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        tmp.replace(task_file)
    except Exception:
        pass  # Never fail the stop hook


def print_session_summary():
    """Print a brief session summary card."""
    wiki = count_wiki_pages()
    commits = git_recent_commits(5)
    uncommitted = check_uncommitted()

    # Count today's commits
    import subprocess
    today_commits = 0
    try:
        result = subprocess.run(
            ["git", "log", "--since=midnight", "--format=%h"],
            capture_output=True, text=True, cwd=str(get_root()), timeout=10,
        )
        if result.returncode == 0:
            today_commits = len(result.stdout.strip().splitlines())
    except Exception:
        pass

    print()
    print("┌" + "─" * 50 + "┐")
    print(f"│ PKB Session Summary".ljust(51) + "│")
    print("├" + "─" * 50 + "┤")
    print(f"│ Wiki: {wiki['total']} pages ({wiki['concepts']} concepts, {wiki['sources']} sources, {wiki['projects']} projects)".ljust(51) + "│")
    print(f"│ Commits: {today_commits} today, {len(commits)} recent".ljust(51) + "│")

    # Uncommitted status
    if uncommitted:
        n = len(uncommitted)
        critical = check_critical_modifications(uncommitted)
        if critical:
            print(f"│ ⚠️  {n} uncommitted files (incl. critical config!)".ljust(51) + "│")
        else:
            print(f"│ 📝 {n} uncommitted files".ljust(51) + "│")
    else:
        print(f"│ ✅ Working tree clean".ljust(51) + "│")

    # Stale inbox
    stale = check_stale_inbox()
    if stale:
        print(f"│ 📥 INBOX: {len(stale)} stale files (>24h)".ljust(51) + "│")

    print("└" + "─" * 50 + "┘")

    # Recommendations
    if uncommitted:
        critical = check_critical_modifications(uncommitted)
        if critical:
            warn(
                f"Critical files modified and uncommitted: {', '.join(critical)}\n"
                f"  Consider running /save to commit your changes."
            )
        else:
            info(f"Tip: /save to commit {len(uncommitted)} uncommitted file(s)")

    if stale:
        names = ", ".join(f"{n} ({h:.0f}h)" for n, h in stale[:3])
        if len(stale) > 3:
            names += f" +{len(stale)-3} more"
        info(f"Stale INBOX files: {names}\n  Run /inbox to process pending imports.")


def main():
    # Idempotency: only run once per session (cooldown = 1 hour)
    if not is_safe_to_run("stop", cooldown_secs=3600):
        return 0

    dry = is_dry_run()
    if dry:
        info("[DRY RUN] Stop hook — would print session summary")
        uncommitted = check_uncommitted()
        stale = check_stale_inbox()
        info(f"  Uncommitted: {len(uncommitted)} files")
        info(f"  Stale inbox: {len(stale)} files")
        return 0

    # Touch active task timestamp (non-fatal)
    touch_active_task()

    # Refresh hot.md cache (non-fatal)
    refresh_hot_md()

    print_session_summary()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception as e:
        # Silently handle all errors — Stop hook must never block exit.
        # This includes Bun/claude-mem unavailability (optional MCP services).
        print(f"[PKB Hook ⚠️] Stop hook error: {e}", file=sys.stderr)
        sys.exit(0)
