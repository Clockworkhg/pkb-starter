#!/usr/bin/env python3
"""
UserPromptSubmit Hook for PKB — analyzes user input and suggests optimal commands.

Suggest-only, never redirects. Silent for most inputs.
Cooldown: 30 seconds between suggestions.

Routing table:
  - GitHub/Gist URL     → /pkb <url>
  - WeChat article URL  → /pkb <url>
  - Generic URL         → /pkb <url> or /web <url>
  - File path           → /pkb <path>
  - CNKI/知网 terms     → /pkb-cnki search <query>
  - Paper/literature    → /paper or /research
  - Save/commit         → /save

Usage:
  python .claude/hooks/06_user_prompt_submit.py            # normal mode
  python .claude/hooks/06_user_prompt_submit.py --dry-run  # print routing table
"""

import os
import sys
import re

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hook_lib import info, is_dry_run, is_safe_to_run

ROUTING_PATTERNS = [
    (r'^https?://github\.com/[^/\s]+/[^/\s]+', '/pkb <url>', 'GitHub repository'),
    (r'^https?://gist\.github\.com/', '/pkb <url>', 'GitHub Gist'),
    (r'^https?://mp\.weixin\.qq\.com/', '/pkb <url>', 'WeChat article'),
    (r'^https?://', '/pkb <url> or /web <url>', 'URL'),
    (r'^[A-Za-z]:[\\/]', '/pkb <path>', 'Windows path'),
    (r'^~/[a-zA-Z]', '/pkb <path>', 'Unix path'),
    (r'知网|cnki|CNKI', '/pkb-cnki search ...', 'CNKI/知网'),
    (r'论文|paper|文献综述|literature\s*review', '/paper or /research', 'Academic'),
    (r'保存|commit|提交', '/save "message"', 'Save/commit'),
    (r'检查|lint|健康检查|health\s*check', '/lint', 'Health check'),
    (r'收集|采集|collect|ingest|入库', '/pkb or /inbox --auto', 'Collection'),
    (r'搜索|search|查找|find', '/search <query>', 'Search'),
]


def analyze_input(user_input: str) -> list:
    """Analyze user input and return list of (command, description) suggestions."""
    if not user_input or len(user_input.strip()) < 3:
        return []
    suggestions = []
    for pattern, command, desc in ROUTING_PATTERNS:
        if re.search(pattern, user_input):
            suggestions.append((command, desc))
            if len(suggestions) >= 2:
                break
    return suggestions


def main():
    if not is_safe_to_run("user_prompt_submit", cooldown_secs=30):
        return 0

    dry = is_dry_run()
    if dry:
        info("[DRY RUN] UserPromptSubmit routing table:")
        for _, cmd, desc in sorted(ROUTING_PATTERNS, key=lambda x: x[2]):
            info(f"  {desc}: {cmd}")
        return 0

    user_input = os.environ.get("CLAUDE_USER_PROMPT", "")
    if not user_input:
        return 0

    suggestions = analyze_input(user_input)
    for cmd, desc in suggestions:
        info(f"{desc} → try: {cmd}")

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception:
        sys.exit(0)
