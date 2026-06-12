#!/usr/bin/env python3
"""
PostToolUseFailure Hook for PKB — runs when a tool invocation fails.

Classifies the error and suggests recovery actions.
Always returns 0 — informational only, never blocks.

Error categories (11 total):
  network, commit_blocked, permission, security, encoding,
  auth, not_found, invalid_url, server_error, dependency, tool_missing

Usage:
  python .claude/hooks/04_post_tool_use_failure.py            # normal mode
  python .claude/hooks/04_post_tool_use_failure.py --dry-run  # print error patterns
"""

import os
import sys
import re

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hook_lib import warn, info, is_dry_run, parse_tool_input

ERROR_PATTERNS = [
    (r"Connection(?:Reset|Refused|Error|Aborted)|timed\s*out|Timeout|Remote end closed",
     "network",
     "Network connection issue. Retry in a few minutes, or use --collect-only to skip web fetching."),
    (r"git commit.*rejected|pre-commit hook.*failed",
     "commit_blocked",
     "Git commit rejected. Run /lint to see health check issues, fix them, then re-commit."),
    (r"Permission\s*[Dd]enied|Access\s*[Dd]enied",
     "permission",
     "Permission denied. Check if the file is locked by another program or has read-only flag."),
    (r"secret|sensitive|blocked.*security|api[_-]?key.*found",
     "security",
     "Operation blocked — sensitive content detected. Remove API keys/tokens/passwords from the content."),
    (r"UnicodeEncodeError.*gbk|gbk.*codec.*encode",
     "encoding",
     "GBK encoding error on Windows. Set: export PYTHONIOENCODING=utf-8 && python <script>"),
    (r"401.*Unauthorized|403.*Forbidden|Jina.*Reader.*fail",
     "auth",
     "Authentication denied by remote server. For GitHub, try raw.githubusercontent.com URL."),
    (r"404.*Not\s*Found|No such file|FileNotFoundError",
     "not_found",
     "File or URL not found. Check the path/URL for typos."),
    (r"No connection adapters|Invalid\s*URL|Invalid\s*schema",
     "invalid_url",
     "Invalid URL or unsupported protocol. For local files use /pkb <path>, for web use https:// prefix."),
    (r"502|503|504|Bad\s*Gateway|Service\s*Unavailable",
     "server_error",
     "Remote server error (5xx). The server is temporarily down. Retry in a few minutes."),
    (r"ModuleNotFoundError|ImportError|No module named",
     "dependency",
     "Missing Python dependency. Install: pip install <package>"),
    (r"yt-dlp|ffmpeg|not installed|not found.*command",
     "tool_missing",
     "Required external tool missing. Install yt-dlp: pip install yt-dlp"),
]

TOOL_SPECIFIC = {
    "web_pack.py": "Tips: try --mode safe (no media), --max-depth 0 (single page), or clone GitHub repos locally first.",
    "pkb_auto.py": "Tips: --check validates wiki health, --scan finds unprocessed _INBOX items.",
    "import_to_inbox.py": "Tips: sensitive files are auto-rejected. Use --folder for directories.",
}


def classify_error(stderr_text: str, tool_name: str = "") -> list:
    """Classify error text against known patterns. Returns list of (category, suggestion)."""
    findings = []
    for pattern, category, suggestion in ERROR_PATTERNS:
        if re.search(pattern, stderr_text, re.IGNORECASE):
            if not any(f[0] == category for f in findings):
                findings.append((category, suggestion))

    for tool_key, tip in TOOL_SPECIFIC.items():
        if tool_key in tool_name.lower() or tool_key in stderr_text.lower():
            findings.append(("tool_specific", tip))
            break

    return findings


def main():
    dry = is_dry_run()
    if dry:
        info("[DRY RUN] PostToolUseFailure — known error categories:")
        for _, cat, tip in ERROR_PATTERNS:
            info(f"  [{cat}] {tip[:80]}")
        return 0

    tool_info = parse_tool_input()
    tool_name = tool_info.get("tool_name", "unknown")

    stderr_text = os.environ.get("CLAUDE_TOOL_ERROR", "")
    error_file = os.environ.get("CLAUDE_TOOL_ERROR_FILE", "")
    if not stderr_text and error_file and os.path.exists(error_file):
        try:
            with open(error_file, "r", encoding="utf-8", errors="ignore") as f:
                stderr_text = f.read()
        except Exception:
            pass

    if not stderr_text:
        return 0

    findings = classify_error(stderr_text, tool_name)
    if findings:
        info(f"Tool '{tool_name}' failed — suggestions:")
        for category, suggestion in findings:
            print(f"  [{category}] {suggestion}")
    else:
        info(f"Tool '{tool_name}' failed. Check the error above for details.")

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception as e:
        print(f"[PKB Hook ⚠️] PostToolUseFailure error: {e}", file=sys.stderr)
        sys.exit(0)
