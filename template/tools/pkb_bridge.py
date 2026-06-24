#!/usr/bin/env python3
"""PKB Global Bridge — 全局桥接引擎 v1.0

Called by global Skills (/pkb-capture, /ask-pkb) from any project window.
Provides: capture (ingest conversations), query (search KB), status (stats), install (setup).

Usage:
  python tools/pkb_bridge.py status --json
  python tools/pkb_bridge.py query "search term" --limit 5 --format json
  python tools/pkb_bridge.py capture --mode summary --stdin
  python tools/pkb_bridge.py install --all
"""

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


# ═══════════════════════════════════════════════════════════════════════════
# Sensitive Content Detection Patterns
# ═══════════════════════════════════════════════════════════════════════════

# Block-level patterns (match = reject write)
BLOCK_PATTERNS = [
    (re.compile(r'sk-[a-zA-Z0-9_-]{32,}', re.IGNORECASE), "api_key", "Anthropic/OpenAI API key (sk-...)"),
    (re.compile(r'AKIA[0-9A-Z]{16}'), "api_key", "AWS Access Key ID"),
    (re.compile(r'ghp_[a-zA-Z0-9]{36}'), "api_key", "GitHub Personal Access Token"),
    (re.compile(r'gho_[a-zA-Z0-9]{36}'), "api_key", "GitHub OAuth Token"),
    (re.compile(r'ghu_[a-zA-Z0-9]{36}'), "api_key", "GitHub User Token"),
    (re.compile(r'-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----'), "private_key", "Private key (PEM)"),
    (re.compile(r'eyJ[A-Za-z0-9_-]{50,}\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+'), "jwt_token", "JWT/Token string"),
    (re.compile(r'(?:TOKEN|SECRET|PASSWORD|API[_-]?KEY)\s*[=:]\s*["\']?\S{8,}', re.IGNORECASE), "credential_assignment", "Credential in assignment"),
    (re.compile(r'://[^@\s]{1,64}:[^@\s]{1,64}@'), "url_password", "URL with embedded password"),
]

# Warning-level patterns (match = write but warn)
WARN_PATTERNS = [
    (re.compile(r'\b\d{17}[\dXx]\b'), "pii_id", "Possible Chinese ID number"),
    (re.compile(r'\b1[3-9]\d{9}\b'), "pii_phone", "Possible Chinese mobile number"),
    (re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'), "pii_email", "Email address"),
    (re.compile(r'\b(?:10\.\d{1,3}\.\d{1,3}\.\d{1,3}|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3}):\d+\b'), "pii_internal_ip", "Internal IP with port"),
]


# ═══════════════════════════════════════════════════════════════════════════
# Skill Templates (global install targets)
# ═══════════════════════════════════════════════════════════════════════════

CAPTURE_SKILL_TEMPLATE = """---
name: pkb-capture
description: Capture the current conversation into PKB knowledge base from any project window. Use when the user says /pkb-capture, wants to save conversation insights, mark key fragments, or export transcripts into their personal knowledge base.
---

# PKB Capture — 全局对话捕获

将任意项目窗口的对话内容摄入 PKB 知识库。

## 触发条件

用户输入 /pkb-capture [mode] [topic]

## 模式路由

| 用户输入 | 模式 | 行为 |
|---------|------|------|
| /pkb-capture | summary (默认) | 自动总结对话核心，生成结构化笔记 |
| /pkb-capture summary | summary | 同上 |
| /pkb-capture summary "主题" | summary | 按指定主题总结 |
| /pkb-capture transcript | transcript | 导出完整对话记录 |
| /pkb-capture mark "片段文本" | fragment | 标记一个关键片段 |
| /pkb-capture status | status | 查看 PKB 当前统计 |

## 执行步骤

### Step 0: 找到 PKB 根路径

使用 4 层策略（与 /ask-pkb 相同）：
1. 环境变量 PKB_ROOT
2. 自动检测（向上找 pkb.ps1 + CLAUDE.md + wiki/ + raw/）
3. ~/.pkb/config.json 中 pkb_root 字段
4. 都不行 → 提示用户运行 `python <PKB_ROOT>/tools/pkb_bridge.py install`

### Step 1: 按模式执行

#### 模式 A: summary（默认）

1. **回顾对话**：梳理当前对话的全部内容
2. **按模板总结**：

```markdown
## 对话摘要：[一句话概括]

### 用户意图
- 问题 1：...
- 问题 2：...

### 核心结论
- 结论 1：...
- 结论 2：...

### 关键决策
- 决策 1：...（原因：...）

### 产出文件
- `path/to/file` — 说明

### 引用资料
- URL/文献：...

### 待办
- [ ] 待办 1
```

3. **组装 JSON**：

```json
{
  "title": "对话主题",
  "content": "<上面模板的完整 Markdown>",
  "tags": ["tag1", "tag2"],
  "source_project": "<当前工作目录文件夹名>",
  "source_window": "claude-code",
  "captured_at": "<ISO 时间戳>",
  "key_insights": ["发现1"],
  "decisions": ["决策1"],
  "todo_items": ["待办1"],
  "related_urls": [],
  "related_files": []
}
```

🔴 CHECKPOINT · 🛑 写入前确认：在 pipe JSON 到 bridge 之前，先在对话中展示总结摘要给用户看一眼。用户确认后再 pipe。如果用户说"不对"，重新总结。

4. **调 bridge**：

```
python <PKB_ROOT>/tools/pkb_bridge.py capture --mode summary --stdin
```

把 JSON pipe 进去。

#### 模式 B: transcript

1. 将当前对话整理为结构化 Markdown transcript
2. 写入临时文件
3. 调用：

```
python <PKB_ROOT>/tools/pkb_bridge.py capture --mode transcript --file <path>
```

#### 模式 C: fragment

1. 把用户标记的片段 + 上下文提取
2. 组装 JSON：

```json
{
  "fragments": [
    {"text": "关键内容...", "tag": "design-decision|reference|insight|todo", "context": "上下文"}
  ],
  "source_project": "<当前项目>",
  "source_window": "claude-code"
}
```

3. 调用：

```
python <PKB_ROOT>/tools/pkb_bridge.py capture --mode fragment --stdin
```

### Step 2: 处理返回值

- `ok: true` → 报告：创建了哪些 wiki 页面，commit hash
- `ok: false, blocked: true` → 🔴 CHECKPOINT · 🛑 停下来展示阻断原因（具体敏感内容）。不要自动重试，不要跳过写入。
- `ok: false` → 按 fallback 表处理

## 异常处理（三段式 fallback）

| 触发条件 | 一线修复 | 仍失败兜底 |
|---------|---------|-----------|
| PKB_ROOT 找不到 | 提示设 PKB_ROOT 或运行 `python tools/pkb_bridge.py install` | 让用户手动输入路径 |
| bridge 脚本不存在 | 提示在 PKB 项目内 `git pull` | 降级：手动写 md 到 `$PKB_ROOT/_INBOX/imported/`，标注 `capture_method: manual_fallback` |
| bridge 返回 blocked | 展示阻断原因 + 敏感内容，等用户修改 | 建议用 transcript 模式仅归档 |
| python 不可用 | 依次尝试 `python3`、`py` | 报错退出 |

## 🚫 反例黑名单

| # | 反模式 | 正确做法 |
|---|--------|---------|
| 1 | 总结中含 API Key/Token/密码/私钥 | 主动排除，bridge 做第二道硬检测 |
| 2 | 编造对话中没有的结论或决策 | 只提取对话中实际出现的内容 |
| 3 | 跳过 bridge 直接写文件 | 必须走 bridge，保证管线一致 |
| 4 | PKB_ROOT 未确认就开始总结 | 先找到根路径再操作 |
| 5 | blocked 后自动重试不告知用户 | 停下来展示阻断原因 |
| 6 | summary 只写一句话草草了事 | 严格按结构模板填写 |
| 7 | 把整个对话原文当"总结" | 提取关键信息，去除冗余 |
"""

ASK_PKB_STEP4_ENHANCED = """
### Step 4：全文搜索 + Bridge 搜索（双重，bridge 优先）

1. 先跑 bridge 搜索（通常更快更全）：
   ```
   python <PKB_ROOT>/tools/pkb_bridge.py query "用户问题" --limit 5 --format json
   ```
   → 成功: 用返回的 results + knowledge_gaps
   → 失败（脚本不存在/python不可用等）:
      → 降级到 Grep <PKB_ROOT>/wiki/ 搜关键词
      → 降级后在回答末尾标注 "⚠️ bridge 不可用，搜索可能不完整"

2. 再用 Grep <PKB_ROOT>/wiki/ 搜关键词做交叉补漏

3. 合并去重两组结果。Bridge 的 knowledge_gaps 用于 Step 6 回答

**bridge 降级策略**：

| 触发条件 | 行为 |
|---------|------|
| bridge 脚本不存在 | 降级到纯 Grep 搜索，回答末尾标注 ⚠️ |
| bridge 返回 `ok: false` | 降级到纯 Grep 搜索，不阻塞 |
| bridge 超时（> 15s） | 终止 bridge 等待，降级到 Grep |
| bridge 返回空 results | 用 Grep 补搜，结合 knowledge_gaps 给完整回答 |
"""


# ═══════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════

def slugify(text: str, max_len: int = 60) -> str:
    """Convert text to filename-safe slug."""
    slug = re.sub(r'[^\w\s-]', '', text.lower())
    slug = re.sub(r'[-\s]+', '-', slug).strip('-')
    return slug[:max_len]


def make_error(code: str, message: str, hint: str = "", recoverable: bool = True) -> dict:
    """Build unified error response."""
    return {
        "ok": False,
        "error": code,
        "message": message,
        "hint": hint,
        "recoverable": recoverable,
    }


def make_ok(**kwargs) -> dict:
    """Build unified success response."""
    return {"ok": True, **kwargs}


def get_skills_dir() -> Path:
    """Get global Claude Code skills directory."""
    return Path.home() / ".claude" / "skills"


def find_pkb_root() -> Path | None:
    """Discover PKB root directory. Returns Path or None.

    Priority:
    1. PKB_ROOT environment variable
    2. Auto-detect: walk up from cwd looking for pkb.ps1 + CLAUDE.md + wiki/ + raw/
    3. ~/.pkb/config.json → pkb_root field
    """
    # Layer 1: Environment variable
    env_root = os.environ.get("PKB_ROOT")
    if env_root:
        p = Path(env_root)
        if p.is_dir():
            return p.resolve()

    # Layer 2: Auto-detect (walk up from cwd)
    cwd = Path.cwd()
    for parent in [cwd, *cwd.parents]:
        if (
            (parent / "pkb.ps1").exists()
            and (parent / "CLAUDE.md").exists()
            and (parent / "wiki").is_dir()
            and (parent / "raw").is_dir()
        ):
            # Verify it's actually PKB
            claude_md = parent / "CLAUDE.md"
            try:
                if "PKB" in claude_md.read_text(encoding="utf-8", errors="replace"):
                    return parent.resolve()
            except Exception:
                continue

    # Layer 3: ~/.pkb/config.json
    config_path = Path.home() / ".pkb" / "config.json"
    if config_path.exists():
        try:
            config = json.loads(config_path.read_text(encoding="utf-8"))
            pkb_root = config.get("pkb_root")
            if pkb_root:
                p = Path(pkb_root)
                if p.is_dir():
                    return p.resolve()
        except (json.JSONDecodeError, KeyError, OSError):
            pass

    return None


# ═══════════════════════════════════════════════════════════════════════════
# Sensitive Content Detection
# ═══════════════════════════════════════════════════════════════════════════

def scan_capture_content(content: str) -> dict:
    """Scan capture content for sensitive material.

    Returns dict with:
      - blocked: bool — True if content must be rejected
      - block_findings: list of {type, pattern_description, match_snippet}
      - warnings: list of {type, pattern_description}
    """
    block_findings = []
    warnings = []

    for pattern, ptype, desc in BLOCK_PATTERNS:
        m = pattern.search(content)
        if m:
            snippet = content[max(0, m.start() - 10):m.end() + 10]
            block_findings.append({
                "type": ptype,
                "pattern": desc,
                "match_snippet": snippet,
            })

    for pattern, ptype, desc in WARN_PATTERNS:
        if pattern.search(content):
            warnings.append({
                "type": ptype,
                "pattern": desc,
            })

    # Also try hook_lib's scan if available
    root = find_pkb_root()
    if root:
        try:
            hook_dir = str(root / ".claude" / "hooks")
            if hook_dir not in sys.path:
                sys.path.insert(0, hook_dir)
            from hook_lib import scan_content_for_secrets
            hook_findings = scan_content_for_secrets(content)
            for pat, desc in hook_findings:
                # Avoid duplicates
                if not any(f["pattern"] == desc for f in block_findings):
                    block_findings.append({
                        "type": "hook_lib_match",
                        "pattern": desc,
                        "match_snippet": "",
                    })
        except ImportError:
            pass  # hook_lib not available — use our own patterns

    return {
        "blocked": len(block_findings) > 0,
        "block_findings": block_findings,
        "warnings": warnings,
    }


# ═══════════════════════════════════════════════════════════════════════════
# Command: status
# ═══════════════════════════════════════════════════════════════════════════

def cmd_status(args) -> dict:
    """Return PKB statistics."""
    root = find_pkb_root()
    if not root:
        return make_error(
            "PKB_ROOT_NOT_FOUND",
            "Cannot locate PKB knowledge base",
            "Set PKB_ROOT environment variable or run: python tools/pkb_bridge.py install --config",
        )

    # Count wiki pages by type
    wiki_dir = root / "wiki"
    concepts = len(list((wiki_dir / "concepts").glob("*.md"))) if (wiki_dir / "concepts").is_dir() else 0
    sources = len(list((wiki_dir / "sources").glob("*.md"))) if (wiki_dir / "sources").is_dir() else 0
    projects = len(list((wiki_dir / "projects").glob("*.md"))) if (wiki_dir / "projects").is_dir() else 0
    outputs = len(list((wiki_dir / "outputs").glob("*.md"))) if (wiki_dir / "outputs").is_dir() else 0
    total_wiki = sum(1 for _ in wiki_dir.rglob("*.md")) if wiki_dir.is_dir() else 0

    # Count INBOX pending
    inbox_dir = root / "_INBOX" / "imported"
    inbox_pending = sum(1 for _ in inbox_dir.glob("*")) if inbox_dir.is_dir() else 0

    # Last commit
    last_commit = ""
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%aI"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            cwd=str(root), timeout=5,
        )
        if result.returncode == 0:
            last_commit = result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass

    # Version from CLAUDE.md
    version = "unknown"
    claude_md = root / "CLAUDE.md"
    if claude_md.exists():
        try:
            text = claude_md.read_text(encoding="utf-8", errors="replace")
            m = re.search(r"v(\d+\.\d+\.\d+[\w.-]*)", text)
            if m:
                version = f"v{m.group(1)}"
        except Exception:
            pass

    return make_ok(
        wiki_pages=total_wiki,
        concepts=concepts,
        sources=sources,
        projects=projects,
        outputs=outputs,
        inbox_pending=inbox_pending,
        last_commit=last_commit,
        pkb_version=version,
    )


# ═══════════════════════════════════════════════════════════════════════════
# Command: query
# ═══════════════════════════════════════════════════════════════════════════

def cmd_query(args) -> dict:
    """Search PKB knowledge base and return JSON results."""
    root = find_pkb_root()
    if not root:
        return make_error(
            "PKB_ROOT_NOT_FOUND",
            "Cannot locate PKB knowledge base",
            "Set PKB_ROOT env var or run: python tools/pkb_bridge.py install --config",
        )

    query_text = args.query_text
    limit = args.limit
    results = []

    wiki_dir = root / "wiki"
    if not wiki_dir.is_dir():
        return make_ok(query=query_text, results=[], knowledge_gaps=["wiki/ directory not found"])

    # Step 1: Read wiki/index.md for candidate pages
    index_md = wiki_dir / "index.md"
    candidates = set()
    if index_md.exists():
        try:
            index_content = index_md.read_text(encoding="utf-8", errors="replace")
            for line in index_content.split("\n"):
                for m in re.finditer(r'\[\[([^\]|]+)(?:\|[^\]]+)?\]\]', line):
                    page = m.group(1).strip()
                    candidates.add(page)
        except Exception:
            pass

    # Step 2: Full-text search wiki/ for query keywords
    keywords = query_text.lower().split()
    scored = []  # (path, score, snippet, ptype, title, tags, updated)

    for md_file in wiki_dir.rglob("*.md"):
        try:
            content = md_file.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue

        score = 0
        content_lower = content.lower()
        for kw in keywords:
            score += content_lower.count(kw)

        if score > 0:
            # Extract snippet: first 200 chars around first keyword match
            first_match = content_lower.find(keywords[0])
            if first_match == -1:
                first_match = 0
            start = max(0, first_match - 50)
            snippet = content[start:start + 200].replace("\n", " ").strip()

            rel_path = str(md_file.relative_to(root))

            # Determine type from path
            if "/concepts/" in rel_path:
                ptype = "concept"
            elif "/sources/" in rel_path:
                ptype = "source"
            elif "/projects/" in rel_path:
                ptype = "project"
            elif "/outputs/" in rel_path:
                ptype = "output"
            else:
                ptype = "wiki"

            # Extract title from frontmatter or first heading
            title = md_file.stem
            for line in content.split("\n")[:20]:
                if line.startswith("title:") or line.startswith("# "):
                    title = line.split(":", 1)[-1].strip() if ":" in line else line.lstrip("# ").strip()
                    break

            # Extract tags from frontmatter
            tags = []
            in_frontmatter = False
            for line in content.split("\n")[:30]:
                if line.strip() == "---":
                    if not in_frontmatter:
                        in_frontmatter = True
                        continue
                    else:
                        break
                if in_frontmatter and line.startswith("tags:"):
                    tag_str = line.split(":", 1)[1].strip()
                    tags = [t.strip().strip("[]'\"") for t in tag_str.split(",") if t.strip()]

            # Extract updated date
            updated = ""
            in_frontmatter = False
            for line in content.split("\n")[:30]:
                if line.strip() == "---":
                    if not in_frontmatter:
                        in_frontmatter = True
                        continue
                    else:
                        break
                if in_frontmatter and line.startswith("updated:"):
                    updated = line.split(":", 1)[1].strip()

            scored.append((rel_path, score, snippet, ptype, title, tags, updated))

    # Sort by score descending
    scored.sort(key=lambda x: x[1], reverse=True)

    # Normalize scores to 0.0-1.0 relevance
    max_score = scored[0][1] if scored else 1
    for item in scored[:limit]:
        rel_path, score, snippet, ptype, title, tags, updated = item
        relevance = round(score / max_score, 2) if max_score > 0 else 0.0
        results.append({
            "type": ptype,
            "path": rel_path,
            "title": title,
            "snippet": snippet[:200],
            "relevance": relevance,
            "tags": tags,
            "updated": updated,
        })

    # Step 3: Check raw/ for related materials
    raw_dir = root / "raw"
    raw_matches = []
    if raw_dir.is_dir():
        for manifest in raw_dir.rglob("manifest.json"):
            try:
                mf = json.loads(manifest.read_text(encoding="utf-8", errors="replace"))
                if isinstance(mf, dict):
                    mf_text = json.dumps(mf).lower()
                    if any(kw in mf_text for kw in keywords):
                        raw_matches.append(str(manifest.relative_to(root)))
            except (json.JSONDecodeError, UnicodeDecodeError, OSError):
                pass

    # Step 4: Detect knowledge gaps
    knowledge_gaps = []
    if not results:
        knowledge_gaps.append(f"知识库中未找到与「{query_text}」相关的内容")

    return make_ok(
        query=query_text,
        results=results,
        raw_matches=raw_matches[:limit],
        knowledge_gaps=knowledge_gaps,
    )


# ═══════════════════════════════════════════════════════════════════════════
# Command: capture
# ═══════════════════════════════════════════════════════════════════════════

def write_capture_file(root: Path, content: str, frontmatter: dict) -> Path:
    """Write captured content as markdown file in _INBOX/imported/.

    Returns the Path to the written file.
    """
    inbox_dir = root / "_INBOX" / "imported"
    inbox_dir.mkdir(parents=True, exist_ok=True)

    date_str = datetime.now().strftime("%Y-%m-%d")
    title_slug = slugify(frontmatter.get("title", "capture"))
    filename = f"{date_str}-{title_slug}.md"

    # Avoid overwrites
    filepath = inbox_dir / filename
    counter = 1
    while filepath.exists():
        filepath = inbox_dir / f"{date_str}-{title_slug}-{counter}.md"
        counter += 1

    # Build markdown with YAML frontmatter
    fm = frontmatter.copy()
    fm.setdefault("created", datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
    fm.setdefault("type", "capture")

    lines = ["---"]
    for key, value in fm.items():
        if isinstance(value, list):
            lines.append(f"{key}: [{', '.join(repr(v) for v in value)}]")
        elif isinstance(value, str) and ("\n" in value or ":" in value):
            lines.append(f'{key}: "{value}"')
        else:
            lines.append(f"{key}: {value}")
    lines.append("---")
    lines.append("")
    lines.append(content)

    filepath.write_text("\n".join(lines), encoding="utf-8")
    return filepath


def cmd_capture(args) -> dict:
    """Capture conversation content into PKB."""
    root = find_pkb_root()
    if not root:
        return make_error(
            "PKB_ROOT_NOT_FOUND",
            "Cannot locate PKB knowledge base",
            "Set PKB_ROOT env var or run: python tools/pkb_bridge.py install --config",
        )

    mode = args.mode

    # ── Parse input ──
    if args.stdin:
        try:
            raw = sys.stdin.read()
            capture_data = json.loads(raw)
        except json.JSONDecodeError as e:
            return make_error(
                "STDIN_PARSE_ERROR",
                f"Failed to parse stdin JSON: {e}",
                "Check JSON structure and retry, or use --file <path> for a JSON file",
            )
    elif args.file:
        try:
            raw = Path(args.file).read_text(encoding="utf-8", errors="replace")
            capture_data = json.loads(raw)
        except (json.JSONDecodeError, FileNotFoundError) as e:
            return make_error(
                "FILE_PARSE_ERROR",
                f"Failed to read/parse file: {e}",
                "Check file path and JSON structure",
            )
    else:
        return make_error(
            "NO_INPUT",
            "No input provided",
            "Use --stdin to pipe JSON or --file <path> for a JSON file",
        )

    # ── Assemble content and frontmatter per mode ──
    if mode == "summary":
        title = capture_data.get("title", "Untitled Capture")
        content = capture_data.get("content", "")
        tags = capture_data.get("tags", [])
        source_project = capture_data.get("source_project", "")
        source_window = capture_data.get("source_window", "claude-code")
        captured_at = capture_data.get("captured_at", datetime.now(timezone.utc).isoformat())

        frontmatter = {
            "title": title,
            "tags": tags + ["capture", "summary"],
            "source_project": source_project,
            "source_window": source_window,
            "captured_at": captured_at,
        }

        # Add optional fields
        for field in ["key_insights", "decisions", "todo_items", "related_urls", "related_files"]:
            if field in capture_data and capture_data[field]:
                frontmatter[field] = capture_data[field]

        full_content = content

    elif mode == "transcript":
        title = capture_data.get("title", "Conversation Transcript")
        content = capture_data.get("content", "")
        source_project = capture_data.get("source_project", "")

        frontmatter = {
            "title": title,
            "tags": ["capture", "transcript"],
            "source_project": source_project,
            "captured_at": datetime.now(timezone.utc).isoformat(),
        }
        full_content = content

    elif mode == "fragment":
        fragments = capture_data.get("fragments", [])
        if not fragments:
            return make_error(
                "NO_FRAGMENTS",
                "Fragment mode but no fragments provided",
                "Each fragment needs 'text' and 'tag' fields",
            )

        title = capture_data.get("title", "Fragments")
        source_project = capture_data.get("source_project", "")

        # Build content from fragments
        frag_lines = ["# Marked Fragments\n"]
        for i, frag in enumerate(fragments, 1):
            tag = frag.get("tag", "untagged")
            text = frag.get("text", "")
            ctx = frag.get("context", "")
            frag_lines.append(f"## Fragment {i}: {tag}")
            if ctx:
                frag_lines.append(f"> Context: {ctx}\n")
            frag_lines.append(text)
            frag_lines.append("")

        frontmatter = {
            "title": title,
            "tags": ["capture", "fragment"],
            "source_project": source_project,
            "captured_at": datetime.now(timezone.utc).isoformat(),
        }
        full_content = "\n".join(frag_lines)

    else:
        return make_error("UNKNOWN_MODE", f"Unknown capture mode: {mode}")

    # ── Sensitive content scan ──
    scan = scan_capture_content(full_content)
    if scan["blocked"]:
        return {
            "ok": False,
            "blocked": True,
            "found": scan["block_findings"],
            "hint": "Remove credentials from the capture content and retry",
        }

    # ── Write to _INBOX ──
    try:
        filepath = write_capture_file(root, full_content, frontmatter)
    except OSError as e:
        return make_error(
            "INBOX_WRITE_FAILED",
            f"Failed to write capture file: {e}",
            "Check disk space and permissions for _INBOX/imported/",
        )

    # ── Pipeline: ingest → docs_update → git commit ──
    wiki_pages = []
    concepts_updated = []
    commit_hash = ""
    warnings = scan["warnings"].copy()

    # Step A: Run pkb_ingest.py on the captured file
    inbox_abs = str(filepath)
    try:
        ingest_result = subprocess.run(
            [sys.executable, str(root / "tools" / "pkb_ingest.py"), inbox_abs, "--mode", "full", "--json"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            cwd=str(root), timeout=120,
        )
        if ingest_result.returncode == 0 and ingest_result.stdout and ingest_result.stdout.strip():
            try:
                # Parse the last JSON line from ingest output
                lines_out = ingest_result.stdout.strip().split("\n")
                ingest_json = json.loads(lines_out[-1])
                if ingest_json.get("extracted_path"):
                    wiki_pages.append(ingest_json["extracted_path"])
                if ingest_json.get("wiki_pages"):
                    wiki_pages.extend(ingest_json["wiki_pages"])
            except (json.JSONDecodeError, IndexError):
                pass
        elif ingest_result.returncode != 0:
            warnings.append({"type": "ingest_failed", "pattern": (ingest_result.stderr or "")[:200]})
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        warnings.append({"type": "ingest_failed", "pattern": str(e)})

    # Step B: Run docs_update.py consistency check
    try:
        update_result = subprocess.run(
            [sys.executable, str(root / "tools" / "docs_update.py"), "--json"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            cwd=str(root), timeout=30,
        )
        if update_result.returncode != 0:
            warnings.append({"type": "docs_update_warning", "pattern": "docs_update returned non-zero"})
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass  # Non-blocking

    # Step C: Git add + commit (with file lock)
    lockfile = root / "_INBOX" / ".bridge_lock"
    lockfile.parent.mkdir(parents=True, exist_ok=True)

    try:
        # Simple file-based mutex for cross-platform compatibility
        with open(lockfile, "w") as lf:
            try:
                import msvcrt
                msvcrt.locking(lf.fileno(), msvcrt.LK_NBLCK, 1)
            except (OSError, ImportError):
                # Could not acquire lock — another bridge process running
                warnings.append({"type": "lock_busy", "pattern": "Another bridge process is running, skipping commit"})
            else:
                # Stage all changes
                subprocess.run(
                    ["git", "add", "-A"],
                    capture_output=True, text=True, encoding="utf-8", errors="replace",
                    cwd=str(root), timeout=10,
                )
                # Commit
                title = frontmatter.get("title", "Untitled Capture")
                commit_msg = f"[PKB] capture: {title}"
                commit_result = subprocess.run(
                    ["git", "commit", "-m", commit_msg],
                    capture_output=True, text=True, encoding="utf-8", errors="replace",
                    cwd=str(root), timeout=15,
                )
                if commit_result.returncode == 0:
                    # Extract commit hash
                    hash_result = subprocess.run(
                        ["git", "rev-parse", "--short", "HEAD"],
                        capture_output=True, text=True, encoding="utf-8", errors="replace",
                        cwd=str(root), timeout=5,
                    )
                    commit_hash = hash_result.stdout.strip()
                else:
                    if "nothing to commit" in commit_result.stdout + commit_result.stderr:
                        pass  # No changes to commit — not an error
                    else:
                        warnings.append({"type": "commit_failed", "pattern": commit_result.stderr.strip()[:200]})
    except OSError as e:
        warnings.append({"type": "commit_error", "pattern": str(e)})

    if warnings and not any(w.get("type") == "sanitization_needed" for w in warnings):
        pass  # warnings already populated from scan

    return make_ok(
        raw_path=str(filepath.relative_to(root)),
        wiki_pages=list(set(wiki_pages)),
        concepts_updated=concepts_updated,
        commit=commit_hash,
        warnings=warnings,
    )


# ═══════════════════════════════════════════════════════════════════════════
# Command: install
# ═══════════════════════════════════════════════════════════════════════════

def cmd_install(args) -> dict:
    """Install global Skills and config."""
    root = find_pkb_root()
    if not root:
        return make_error(
            "PKB_ROOT_NOT_FOUND",
            "Cannot locate PKB. Run this command from within the PKB project directory.",
            "cd to your PKB project and retry",
        )

    skills_dir = get_skills_dir()
    results = []

    # ── Install pkb-capture skill ──
    if args.all or args.skill == "capture":
        capture_dir = skills_dir / "pkb-capture"
        capture_dir.mkdir(parents=True, exist_ok=True)
        skill_file = capture_dir / "SKILL.md"
        skill_file.write_text(CAPTURE_SKILL_TEMPLATE, encoding="utf-8")
        results.append(f"[OK] pkb-capture skill installed -> {skill_file}")

    # ── Update ask-pkb skill ──
    if args.all or args.skill == "ask-pkb":
        ask_pkb_dir = skills_dir / "ask-pkb"
        ask_pkb_file = ask_pkb_dir / "SKILL.md"

        if ask_pkb_file.exists():
            # Read existing and check if already enhanced
            existing = ask_pkb_file.read_text(encoding="utf-8", errors="replace")
            if "Bridge 搜索" in existing:
                results.append(f"[OK] ask-pkb skill already enhanced -> {ask_pkb_file}")
            else:
                # Find the Step 4 section and replace it
                # Try multiple possible markers
                step4_markers = [
                    "### Step 4：全文搜索补漏",
                    "### Step 4: 全文搜索补漏",
                    "### Step 4：Grep",
                    "### Step 4",
                ]
                replaced = False
                for old_step4 in step4_markers:
                    if old_step4 in existing:
                        parts = existing.split(old_step4, 1)
                        before = parts[0]
                        after_parts = parts[1].split("### Step 5", 1)
                        after = "### Step 5" + after_parts[1] if len(after_parts) > 1 else ""

                        new_content = before + ASK_PKB_STEP4_ENHANCED + "\n" + after
                        ask_pkb_file.write_text(new_content, encoding="utf-8")
                        results.append(f"[OK] ask-pkb skill updated (Step 4 enhanced) -> {ask_pkb_file}")
                        replaced = True
                        break

                if not replaced:
                    results.append(f"[WARN] ask-pkb SKILL.md found but Step 4 marker not recognized -> {ask_pkb_file}")
        else:
            results.append(f"[WARN] ask-pkb skill not found at {ask_pkb_file}, skipping update")

    # ── Write ~/.pkb/config.json ──
    if args.all or args.config:
        pkb_config_dir = Path.home() / ".pkb"
        pkb_config_dir.mkdir(parents=True, exist_ok=True)
        config_file = pkb_config_dir / "config.json"
        config_data = {"pkb_root": str(root.resolve())}
        config_file.write_text(
            json.dumps(config_data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        results.append(f"[OK] Config written -> {config_file}")

    return make_ok(installed=[r for r in results])


# ═══════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="PKB Global Bridge — 全局桥接引擎 v1.0",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # status
    p_status = sub.add_parser("status", help="Show PKB statistics")
    p_status.add_argument("--json", action="store_true", help="Output as JSON")

    # query
    p_query = sub.add_parser("query", help="Search PKB knowledge base")
    p_query.add_argument("query_text", type=str, help="Search query")
    p_query.add_argument("--limit", type=int, default=5, help="Max results")
    p_query.add_argument("--format", choices=["json", "text"], default="json")

    # capture
    p_capture = sub.add_parser("capture", help="Capture conversation into PKB")
    p_capture.add_argument("--mode", choices=["summary", "transcript", "fragment"], default="summary")
    p_capture.add_argument("--stdin", action="store_true", help="Read JSON from stdin")
    p_capture.add_argument("--file", type=str, help="Read from file (transcript mode or JSON fallback)")

    # install
    p_install = sub.add_parser("install", help="Install global Skills and config")
    p_install.add_argument("--all", action="store_true", help="Install everything (skills + config)")
    p_install.add_argument("--skill", choices=["capture", "ask-pkb"], help="Install specific skill")
    p_install.add_argument("--config", action="store_true", help="Write ~/.pkb/config.json only")

    args = parser.parse_args()

    # ── Dispatch ──
    if args.command == "status":
        result = cmd_status(args)
    elif args.command == "query":
        result = cmd_query(args)
    elif args.command == "capture":
        result = cmd_capture(args)
    elif args.command == "install":
        result = cmd_install(args)
    else:
        result = make_error("UNKNOWN_COMMAND", f"Unknown: {args.command}")

    # ── Output ──
    if args.command == "install":
        # install outputs human-readable text
        if result.get("ok"):
            for line in result.get("installed", []):
                print(line)
        else:
            print(f"[ERROR] {result.get('message', 'Unknown error')}")
            if result.get("hint"):
                print(f"   Hint: {result['hint']}")
        sys.exit(0 if result.get("ok") else 1)

    # Determine JSON mode for other commands
    if args.command == "status":
        json_mode = getattr(args, 'json', False)
    elif args.command in ("query", "capture"):
        json_mode = getattr(args, 'format', 'text') == 'json'
    else:
        json_mode = False

    if json_mode:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    elif args.command == "status":
        # Human-readable status output
        if result.get("ok"):
            print(f"PKB Status")
            print(f"  Version:    {result.get('pkb_version', '?')}")
            print(f"  Wiki pages: {result.get('wiki_pages', '?')}")
            print(f"  Concepts:   {result.get('concepts', '?')}")
            print(f"  Sources:    {result.get('sources', '?')}")
            print(f"  Projects:   {result.get('projects', '?')}")
            print(f"  Outputs:    {result.get('outputs', '?')}")
            print(f"  INBOX:      {result.get('inbox_pending', '?')} pending")
            print(f"  Last commit:{result.get('last_commit', 'N/A')}")
        else:
            print(f"Error: {result.get('message', 'Unknown')}")
    else:
        # Default: print JSON
        print(json.dumps(result, indent=2, ensure_ascii=False))

    sys.exit(0 if result.get("ok", True) else 1)


if __name__ == "__main__":
    main()
