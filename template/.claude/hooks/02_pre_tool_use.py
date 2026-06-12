#!/usr/bin/env python3
"""
PreToolUse Safety Hook for PKB.

Blocks dangerous operations at the harness level (before tool execution):
  - git commit with secret patterns in staged files
  - rm/del/rd on protected paths (raw/, wiki/, .claude/)
  - Write/Edit to raw/ (append-only) or sensitive file names
  - Warns on git push (not default PKB behavior)

Does NOT duplicate settings.json `deny` rules:
  - rm -rf (already denied)
  - git push --force (already denied)
  - curl, wget (already denied)

Environment:
  CLAUDE_TOOL_NAME  — e.g. "Bash", "Write", "Edit"
  CLAUDE_TOOL_INPUT — JSON: {"tool_name": "...", "tool_input": {...}}
  PKB_ROOT          — set in settings.json env block

Usage:
  python .claude/hooks/02_pre_tool_use.py            # normal mode
  python .claude/hooks/02_pre_tool_use.py --dry-run  # print what would be blocked
"""

import os
import sys
import json

# Add parent to path for hook_lib import
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hook_lib import (
    warn, block, info, ok, is_dry_run,
    parse_tool_input, git_staged_files,
    scan_content_for_secrets, is_sensitive_filename,
    is_protected_write_path, is_protected_delete_path,
    get_root,
)


def handle_bash(tool_name: str, tool_input: dict) -> int:
    """Handle Bash tool calls. Returns 0 if allowed, 1 to block."""
    command = tool_input.get("command", "")
    command_lower = command.lower().strip()

    # ── git commit — scan staged files for secrets ──
    if command_lower.startswith("git commit") or "git commit" in command_lower:
        staged = git_staged_files()
        if not staged:
            return 0  # Nothing to commit
        root = get_root()
        for f in staged:
            fpath = root / f
            # Check filename first
            is_sens, reason = is_sensitive_filename(f)
            if is_sens:
                block(
                    f"git commit blocked: staged file '{f}' is sensitive ({reason}).\n"
                    f"  Remove it from staging: git reset -- {f}\n"
                    f"  Or add it to .gitignore if it should never be committed."
                )
            # Scan content if it's a text file
            if fpath.exists() and fpath.suffix in (
                ".py", ".md", ".txt", ".json", ".yml", ".yaml",
                ".toml", ".sh", ".ps1", ".js", ".ts", ".env",
                ".cfg", ".ini", ".xml", ".html", ".css", ""
            ):
                try:
                    content = fpath.read_text(encoding="utf-8", errors="ignore")
                    findings = scan_content_for_secrets(content)
                    if findings:
                        patterns = ", ".join(d for _, d in findings)
                        block(
                            f"git commit blocked: staged file '{f}' contains secret patterns.\n"
                            f"  Detected: {patterns}\n"
                            f"  Remove it: git reset -- {f}\n"
                            f"  If this is a false positive, use: git commit --no-verify"
                        )
                except Exception:
                    pass  # Binary file, skip content scan

    # ── rm / del / rd — check for protected paths ──
    if any(cmd in command_lower for cmd in ["rm ", "rmdir ", "del ", "rd ", "remove-item"]):
        # Extract paths from command
        import re
        paths = re.findall(r'(?:["\'])([^"\']+)(?:["\'])', command)
        paths += re.findall(r'(?:\s)([^\s"\']+\.?\w*)(?:\s|$)', command)
        for p in paths:
            is_prot, reason = is_protected_delete_path(p)
            if is_prot:
                block(f"Deletion blocked: {reason}\n  Command: {command[:120]}")

    # ── git push — warn (not default behavior) ──
    if command_lower.startswith("git push") or "git push" in command_lower:
        warn(
            "git push detected. PKB default policy is no auto-push.\n"
            "  If this is intentional, proceed. Otherwise use git commit without push."
        )

    return 0


def handle_write(tool_name: str, tool_input: dict) -> int:
    """Handle Write/Edit tool calls. Returns 0 if allowed, 1 to block."""
    filepath = tool_input.get("file_path", "")
    if not filepath:
        return 0

    # ── Check for protected write paths ──
    is_prot, reason = is_protected_write_path(filepath)
    if is_prot:
        block(f"Write blocked: {reason}\n  File: {filepath}")

    # ── Check for sensitive filenames ──
    is_sens, reason = is_sensitive_filename(filepath)
    if is_sens:
        block(f"Write blocked: {reason}\n  File: {filepath}\n  Sensitive files should not be stored in PKB.")

    # ── Check Write content for secrets ──
    content = tool_input.get("content", "")
    if content:
        findings = scan_content_for_secrets(content)
        if findings:
            patterns = ", ".join(d for _, d in findings)
            block(
                f"Write blocked: content contains secret patterns.\n"
                f"  File: {filepath}\n"
                f"  Detected: {patterns}\n"
                f"  Remove the secret from the content before writing."
            )

    return 0


def main():
    tool_info = parse_tool_input()
    tool_name = tool_info["tool_name"]

    if not tool_name:
        # No tool context — this can happen if hook fires outside a tool call
        return 0

    dry = is_dry_run()
    if dry:
        info(f"[DRY RUN] PreToolUse check for: {tool_name}")
        if tool_info.get("ok"):
            ti = tool_info.get("tool_input", {})
            cmd = ti.get("command", ti.get("file_path", str(ti)))[:120]
            info(f"  Tool input: {cmd}")
        return 0

    # Dispatch by tool type
    if tool_name == "Bash":
        return handle_bash(tool_name, tool_info.get("tool_input", {}))
    elif tool_name in ("Write", "Edit"):
        return handle_write(tool_name, tool_info.get("tool_input", {}))

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception as e:
        warn(f"PreToolUse hook error: {e}")
        sys.exit(0)  # Never block on unexpected errors
