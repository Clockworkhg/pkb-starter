#!/usr/bin/env python3
"""
PostToolUse Validation Hook for PKB.

Enhanced replacement for the single-matcher Write→pkb_auto.py --check hook.
Routes to the appropriate check based on tool and target:

  - Write/Edit on wiki/*.md  → fast frontmatter-only check (lightweight)
  - Write/Edit on other files → skip (not in PKB scope)
  - Bash(git commit)         → full health check via pkb_auto.py --check
                               (NOTE: requires separate Bash matcher in settings.json
                               to be reachable; current matcher is only Write|Edit)

Always returns 0 — failures are warnings, not blocks.
The PreToolUse hook handles blocking for safety violations.

Environment:
  CLAUDE_TOOL_NAME  — e.g. "Bash", "Write", "Edit"
  CLAUDE_TOOL_INPUT — JSON: {"tool_name": "...", "tool_input": {...}}
  PKB_ROOT          — set in settings.json env block

Usage:
  python .claude/hooks/03_post_tool_use.py            # normal mode
  python .claude/hooks/03_post_tool_use.py --dry-run  # print what would be checked
"""

import os
import re
import sys
import time
import json
import subprocess
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hook_lib import (
    warn, info, ok, is_dry_run, parse_tool_input, get_root, is_safe_to_run,
)


def check_frontmatter(filepath: str) -> dict:
    """Quick frontmatter check on a single wiki file. Returns {ok: bool, issues: [str]}."""
    try:
        p = Path(filepath)
        if not p.exists():
            return {"ok": True, "issues": []}
        content = p.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return {"ok": True, "issues": []}

    # Strip UTF-8 BOM if present (Windows Notepad adds ﻿)
    if content.startswith("﻿"):
        content = content[1:]

    issues = []
    # Check for frontmatter delimiters
    if not content.startswith("---"):
        issues.append("Missing opening frontmatter (---)")
    else:
        # Find closing ---
        end = content.find("---", 3)
        if end == -1:
            issues.append("Unclosed frontmatter (missing closing ---)")
        else:
            fm = content[3:end].strip()
            # Check required keys (per CLAUDE.md: created/updated/tags/type)
            for key in ["created", "updated", "tags", "type"]:
                if f"{key}:" not in fm:
                    issues.append(f"Missing frontmatter key: {key}")

    return {"ok": len(issues) == 0, "issues": issues, "file": str(p.name)}


def run_full_health_check() -> dict:
    """Run pkb_auto.py --check and return structured result."""
    root = get_root()
    script = root / "tools" / "pkb_auto.py"
    if not script.exists():
        return {"ok": True, "issues": ["pkb_auto.py not found"], "skipped": True}
    try:
        result = subprocess.run(
            [sys.executable, str(script), "--check"],
            capture_output=True, text=True, cwd=str(root), timeout=25,
        )
        output = result.stdout + result.stderr
        passed = "HEALTH CHECK: PASSED" in output
        return {
            "ok": passed,
            "output": output.strip(),
            "exit_code": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"ok": True, "issues": ["Health check timed out"], "skipped": True}
    except Exception as e:
        return {"ok": True, "issues": [str(e)], "skipped": True}


def _rebuild_index() -> None:
    """Auto-rebuild retrieval index after wiki changes (BM25 + embeddings + reranker).

    Uses a 30-second cooldown to avoid thrashing when multiple wiki pages
    are written in quick succession.
    """
    if not is_safe_to_run("pkb_retrieve_rebuild", cooldown_secs=30):
        return  # within cooldown, skip

    root = get_root()
    script = root / "tools" / "pkb_retrieve.py"
    if not script.exists():
        return

    dry = is_dry_run()
    if dry:
        info("[DRY RUN] Would rebuild retrieval index via pkb_retrieve.py --build")
        return

    try:
        result = subprocess.run(
            [sys.executable, str(script), "--build", "--json"],
            capture_output=True, text=True, cwd=str(root), timeout=30,
        )
        if result.returncode == 0:
            # Parse JSON to get doc count for the message
            try:
                data = json.loads(result.stdout.strip())
                doc_count = data.get("bm25", {}).get("doc_count", "?")
                ok(f"Retrieval index auto-updated ({doc_count} docs)")
            except Exception:
                ok("Retrieval index auto-updated")
        else:
            warn(f"Index rebuild failed (exit {result.returncode})")
    except subprocess.TimeoutExpired:
        warn("Index rebuild timed out (30s) — skipped")
    except Exception as e:
        warn(f"Index rebuild error: {e}")


# ── File-based write counter for subdomain index rebuild ──
# Persisted to _INBOX/.hook_state/ to survive across subprocess invocations.
# (Contrast with _rebuild_index which uses time-based cooldown.)

def _get_write_count(root: Path) -> int:
    """Read persisted wiki write count from hook state."""
    state_file = root / "_INBOX" / ".hook_state" / "wiki_write_count.json"
    try:
        if state_file.exists():
            data = json.loads(state_file.read_text(encoding="utf-8"))
            return data.get("count", 0)
    except Exception:
        pass
    return 0


def _increment_write_count(root: Path) -> int:
    """Increment and persist wiki write count. Returns new count."""
    count = _get_write_count(root) + 1
    state_file = root / "_INBOX" / ".hook_state" / "wiki_write_count.json"
    try:
        state_file.parent.mkdir(parents=True, exist_ok=True)
        state_file.write_text(
            json.dumps({"count": count, "last_write": time.time()}),
            encoding="utf-8",
        )
    except Exception:
        pass  # Non-fatal — counter lapse is acceptable
    return count


def _maybe_rebuild_subdomain_indexes() -> None:
    """Every 10th wiki write, rebuild relevant subdomain _index.md.

    Counter is file-persisted so it survives across subprocess invocations.
    At 10 writes: rebuild concepts, sources, projects _index.md.
    At 50 writes: also suggest full /lint.
    """
    root = get_root()
    count = _increment_write_count(root)

    # Lint suggestion at 50-write milestones (do NOT return — still rebuild)
    if count % 50 == 0:
        info(
            f"📊 {count} wiki writes — consider running /lint "
            f"for full health check"
        )

    # Rebuild every 10 writes
    if count % 10 != 0:
        return

    info(f"📝 Rebuilding subdomain indexes (write #{count})…")

    for subdir_name in ("concepts", "sources", "projects"):
        subdir = root / "wiki" / subdir_name
        if subdir.exists():
            _rebuild_single_subdomain_index(subdir, subdir_name)


def _rebuild_single_subdomain_index(subdir: Path, name: str) -> None:
    """Rebuild one subdomain _index.md — update '最近更新' section with 5 most recent pages."""
    index_path = subdir / "_index.md"
    if not index_path.exists():
        return

    try:
        md_files = sorted(
            [f for f in subdir.glob("*.md") if f.name != "_index.md"],
            key=lambda f: f.stat().st_mtime, reverse=True,
        )
    except Exception:
        return

    existing = index_path.read_text(encoding="utf-8", errors="replace")
    recent = md_files[:5]
    recent_links = "\n".join(f"- [[{f.stem}]]" for f in recent)

    # Use \r?\n for Windows CRLF compatibility
    new_content = re.sub(
        r"## 最近更新\r?\n(?:<!--.*?-->\r?\n)?(?:- \[\[.*?\]\]\r?\n)*",
        f"## 最近更新\n{recent_links}\n",
        existing,
        count=1,
    )

    if new_content != existing:
        # Atomic write: tmp → rename (avoids truncated file on crash)
        tmp = index_path.with_suffix(".md.tmp")
        tmp.write_text(new_content, encoding="utf-8", errors="replace")
        tmp.replace(index_path)
        ok(f"{name}/_index.md updated ({len(md_files)} pages)")
    else:
        ok(f"{name}/_index.md unchanged")


def handle_write(tool_input: dict) -> int:
    """Fast-path: check only the written file if it's a wiki page."""
    filepath = tool_input.get("file_path", "")
    if not filepath:
        return 0

    rel = filepath.replace("\\", "/")
    # Only validate wiki markdown files
    if "wiki/" in rel and rel.endswith(".md"):
        result = check_frontmatter(filepath)
        if not result["ok"]:
            for issue in result["issues"]:
                warn(f"{result['file']}: {issue}")
        else:
            ok()  # Silent pass
        # Phase 3: Auto-rebuild retrieval index (30s cooldown)
        _rebuild_index()
        # Phase 4: Periodic subdomain index rebuild (every 10 writes)
        _maybe_rebuild_subdomain_indexes()
    # Non-wiki files (index.md, log.md, CLAUDE.md, etc.) — skip fast path
    return 0


def handle_git_commit() -> int:
    """Full-path: run complete health check after git commit."""
    dry = is_dry_run()
    if dry:
        info("[DRY RUN] Would run full health check via pkb_auto.py --check")
        return 0

    result = run_full_health_check()
    if result.get("skipped"):
        return 0

    if not result["ok"]:
        warn(
            "Health check found issues after git commit.\n"
            "  Run /lint to see details and fix before the next commit."
        )
        # Print the check output so the LLM can see the issues
        output = result.get("output", "")
        if output:
            print(output, file=sys.stderr)
    else:
        ok("Health check passed after git commit.")
    return 0


def main():
    tool_info = parse_tool_input()
    tool_name = tool_info["tool_name"]
    tool_input = tool_info.get("tool_input", {})

    if not tool_name:
        return 0

    dry = is_dry_run()
    if dry:
        info(f"[DRY RUN] PostToolUse check for: {tool_name}")
        cmd_or_file = tool_input.get("command", tool_input.get("file_path", ""))
        if cmd_or_file:
            info(f"  Target: {cmd_or_file[:120]}")
        return 0

    # Route by tool type + context
    if tool_name in ("Write", "Edit"):
        return handle_write(tool_input)
    elif tool_name == "Bash":
        command = tool_input.get("command", "")
        if "git commit" in command.lower():
            return handle_git_commit()
    # Other tools — no post-validation needed

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception as e:
        warn(f"PostToolUse hook error: {e}")
        sys.exit(0)
