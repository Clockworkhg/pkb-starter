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
    # === URL patterns (ordered: specific before generic) ===
    (r'^https?://github\.com/[^/\s]+/[^/\s]+', '/pkb <url>', 'GitHub repository'),
    (r'^https?://gist\.github\.com/', '/pkb <url>', 'GitHub Gist'),
    (r'^https?://mp\.weixin\.qq\.com/', '/pkb <url>', 'WeChat article'),
    (r'bilibili\.com/video|youtube\.com/watch|youtu\.be|\.m3u8', 'z-video-downloader', 'Video URL'),
    (r'^https?://', '/pkb <url> or /web <url>', 'URL'),
    # === File path patterns ===
    (r'^[A-Za-z]:[\\/]', '/pkb <path>', 'Windows path'),
    (r'^~/[a-zA-Z]', '/pkb <path>', 'Unix path'),
    # === CNKI / Academic ===
    (r'知网|cnki|CNKI', '/pkb-cnki search ...', 'CNKI/知网'),
    (r'论文|paper|文献综述|literature\s*review', '/paper or /research', 'Academic'),
    # === Video / Transcript ===
    (r'下载.*视频|视频.*下载|帮我下.*视频|下载这个[视频影片]|把.*视频.*下.*来|视频.*下.*来', 'z-video-downloader', 'Download video'),
    (r'字幕|转录|transcript|字幕下载|文字稿|获取.*字幕', 'youtube-transcript', 'Transcript'),
    # === System operations ===
    (r'保存|commit|提交', '/save "message"', 'Save/commit'),
    (r'检查|lint|健康检查|health\s*check', '/lint', 'Health check'),
    (r'收集|采集|collect|ingest|入库', '/pkb or /inbox --auto', 'Collection'),
    (r'搜索|search|查找|find', '/search <query>', 'Search'),
    # === Tools & formats ===
    (r'清理|脱敏|sanitize|匿名化|去敏|隐私.*清|去隐私', '/sanitize', 'Sanitize'),
    (r'看板|kanban|任务卡|任务管理|卡片.*管理', '/kanban', 'Kanban'),
    (r'Excel|excel|xlsx|电子表格|表格.*编辑|编辑.*表格', '/z-excel-editor or /z-md-excel', 'Excel'),
    (r'转换.*(docx|pptx|pdf)|(docx|pptx|pdf).*转换|doc.*转|ocr|图片.*文字|文字.*识别', '/doc or /ocr', 'Document convert'),
    # === Knowledge base query ===
    (r'知识库.*有|查.*笔记|PKB.*里|wiki.*有|帮我查.*知识|问.*知识库', '/ask-pkb', 'Query PKB'),
    # === Code & development ===
    (r'代码审查|code.?review|审查.*代码|review.*code', '/code-review or /simplify', 'Code review'),
    (r'调试|debug|bug|排查|为什么.*错|怎么.*出错|帮我.*看.*bug', 'systematic-debugging', 'Debug'),
    (r'头脑风暴|brainstorm|想.*方案|出.*主意|发散|思路', 'brainstorming', 'Brainstorm'),
    # === Content & docs ===
    (r'提取.*文章|文章.*提取|article.*extract|提取.*正文|正文.*提取', '/article-extract', 'Article extract'),
    (r'文档.*更新|刷新.*索引|docs.?update|文档.*过期', '/docs-update', 'Docs update'),
    (r'美化|UI.*框架|tailwind|shadcn|前端.*装|装.*UI', '/setup-beauty-stack', 'UI setup'),
]


def analyze_input(user_input: str) -> list:
    """Analyze user input and return list of (command, description) suggestions."""
    if not user_input or len(user_input.strip()) < 3:
        return []
    suggestions = []
    for pattern, command, desc in ROUTING_PATTERNS:
        if re.search(pattern, user_input):
            suggestions.append((command, desc))
    # No limit — return all matches for complete coverage
    # Fallback: when no pattern matches, suggest /help
    if not suggestions and len(user_input.strip()) >= 3:
        suggestions.append(('/help', 'No specific match — see all available commands'))
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
