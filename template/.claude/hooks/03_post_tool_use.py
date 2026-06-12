#!/usr/bin/env python3
"""
PostToolUse Validation Hook for PKB.

Enhanced replacement for the single-matcher Write→pkb_auto.py --check hook.
Routes to the appropriate check based on tool and target:

  - Write/Edit on wiki/*.md  → fast frontmatter-only check (lightweight)
  - Write/Edit on other files → skip (not in PKB scope)
  - Bash(git commit)         → full health check via pkb_auto.py --check

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
import sys
import subprocess
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hook_lib import (
    warn, info, ok, is_dry_run, parse_tool_input, get_root,
)


def check_frontmatter(filepath: str) -> dict:
    """Quick frontmatter check on a single wiki file. Returns {ok: bool, issues: [str]}."""
    try:
        p = Path(filepath)
        if not p.exists():
            return {"ok": True, "issues": []}
        content = p.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return {"ok": True, "issues": []}

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
            # Check required keys
            for key in ["created", "type"]:
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
