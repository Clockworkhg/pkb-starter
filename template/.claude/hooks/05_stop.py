#!/usr/bin/env python3
"""
Stop Hook for PKB — runs before Claude Code exits the session.

Actions:
  1. Detect uncommitted changes (git status)
  2. Warn if critical files are modified (settings.json, AGENTS.md, CLAUDE.md)
  3. Check for stale files in _INBOX/imported/ (> 24h old)
  4. Print session summary (files changed, wiki pages, recent commits)

Always returns 0 — never blocks exit.

Usage:
  python .claude/hooks/05_stop.py            # normal mode
  python .claude/hooks/05_stop.py --dry-run  # print what would be reported
"""

import os
import sys
import time
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

    print_session_summary()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception as e:
        print(f"[PKB Hook ⚠️] Stop hook error: {e}", file=sys.stderr)
        sys.exit(0)
