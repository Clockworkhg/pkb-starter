---
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
| 4 | PKB_ROOT 未确认就开始总结 | 先找到根路径再操��� |
| 5 | blocked 后自动重试不告知用户 | 停下来展示阻断原因 |
| 6 | summary 只写一句话草草了事 | 严格按结构模板填写 |
| 7 | 把整个对话原文当"总结" | 提取关键信息，去除冗余 |
