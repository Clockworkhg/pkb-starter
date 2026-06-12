#!/usr/bin/env python3
"""
SessionStart Hook for PKB — runs at the start of every Claude Code session.

Actions:
  1. Verify PKB environment (PKB_ROOT, essential directories)
  2. Run docs_update.py --summary (quick staleness check)
  3. Print session context card (wiki stats, recent commits, INBOX status)
  4. Re-print after compaction recovery (helps Agent restore context)

Cooldown: 5 minutes between context card prints.
Always returns 0 — never blocks session start.
"""

import os
import sys
import subprocess
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hook_lib import (
    warn, info, ok, is_dry_run, get_root,
    check_pkb_env, count_wiki_pages, git_recent_commits,
    is_safe_to_run,
)


def check_mcp_availability() -> dict:
    """Quick check if Chrome DevTools MCP server is reachable."""
    import urllib.request
    result = {"chrome_devtools": False}
    try:
        req = urllib.request.Request("http://localhost:9222/json", method="HEAD")
        urllib.request.urlopen(req, timeout=3)
        result["chrome_devtools"] = True
    except Exception:
        pass
    return result


def check_docs_freshness() -> dict:
    """Run docs_update.py --summary for quick staleness check."""
    root = get_root()
    script = root / "tools" / "docs_update.py"
    if not script.exists():
        return {"ok": True, "stale": False, "summary": "docs_update.py not found"}
    try:
        result = subprocess.run(
            [sys.executable, str(script), "--summary"],
            capture_output=True, text=True, cwd=str(root), timeout=15,
        )
        output = result.stdout.strip()
        stale = result.returncode != 0
        return {"ok": not stale, "stale": stale, "summary": output}
    except subprocess.TimeoutExpired:
        return {"ok": True, "stale": False, "summary": "Docs check timed out"}
    except Exception as e:
        return {"ok": True, "stale": False, "summary": f"Docs check error: {e}"}


def check_stale_inbox_count() -> int:
    """Count files in _INBOX/imported/."""
    root = get_root()
    inbox = root / "_INBOX" / "imported"
    if not inbox.exists():
        return 0
    try:
        return len([f for f in inbox.iterdir() if f.is_file()])
    except Exception:
        return 0


def print_context_card(docs_status: dict):
    """Print the PKB session context card."""
    wiki = count_wiki_pages()
    commits = git_recent_commits(5)

    # Count today's commits
    today_count = 0
    try:
        r = subprocess.run(
            ["git", "log", "--since=midnight", "--format=%h"],
            capture_output=True, text=True, cwd=str(get_root()), timeout=10,
        )
        if r.returncode == 0:
            today_count = len(r.stdout.strip().splitlines()) if r.stdout.strip() else 0
    except Exception:
        pass

    # Docs status
    docs_icon = "OK" if docs_status.get("ok", True) else "STALE"
    docs_line = f"Docs: {docs_icon}"
    if docs_status.get("stale"):
        docs_line += f" ({docs_status.get('summary', '')[:60]})"

    # MCP status
    mcp = check_mcp_availability()
    mcp_line = "MCP: chrome-devtools " + ("ON" if mcp["chrome_devtools"] else "OFF")

    # INBOX
    inbox_count = check_stale_inbox_count()
    inbox_line = f"INBOX: {inbox_count} pending" if inbox_count else "INBOX: empty"

    print()
    print("┌" + "─" * 55 + "┐")
    print(f"│ PKB Session Ready".ljust(56) + "│")
    print("├" + "─" * 55 + "┤")
    print(f"│ Wiki: {wiki['total']} pages ({wiki['concepts']} concepts, {wiki['sources']} sources, {wiki['projects']} projects)".ljust(56) + "│")
    print(f"│ Commits: {today_count} today, {len(commits)} in history".ljust(56) + "│")
    print(f"│ {docs_line}".ljust(56) + "│")
    print(f"│ {mcp_line}".ljust(56) + "│")
    print(f"│ {inbox_line}".ljust(56) + "│")
    print("├" + "─" * 55 + "┤")
    print(f"│ Tip: /pkb <anything> to ingest  |  /save to commit".ljust(56) + "│")
    print("└" + "─" * 55 + "┘")
    print()


def main():
    # Cooldown: only print context card once per 5 minutes
    show_card = is_safe_to_run("session_start_context", cooldown_secs=300)

    dry = is_dry_run()
    if dry:
        info("[DRY RUN] SessionStart — would verify env and print context card")
        env = check_pkb_env()
        info(f"  PKB env: {'OK' if env['ok'] else 'ISSUES'}")
        print_context_card({"ok": True, "stale": False, "summary": "[dry run]"})
        return 0

    # Verify environment (always, fast)
    env = check_pkb_env()
    if not env["ok"]:
        warn(f"PKB environment issues: {env['issues']}")

    # Docs freshness (cooldown: 10 min)
    docs_status = {"ok": True, "stale": False, "summary": ""}
    if is_safe_to_run("session_start_docs", cooldown_secs=600):
        docs_status = check_docs_freshness()
        if docs_status.get("stale"):
            warn(f"Project docs may be stale: {docs_status.get('summary', '')}")
            info("  Run /docs-update to auto-fix.")

    # Context card
    if show_card:
        print_context_card(docs_status)

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception as e:
        print(f"[PKB Hook ⚠️] SessionStart hook error: {e}", file=sys.stderr)
        sys.exit(0)
