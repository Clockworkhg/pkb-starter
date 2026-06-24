---
name: ask-pkb
description: Query the PKB personal knowledge base from any project. Use when the user wants to search, recall, or consult knowledge stored in the PKB wiki — concepts, sources, literature maps, project notes, or raw materials. This skill bridges any working directory to the PKB knowledge base. Supports PKB_ROOT env var, auto-detection, and pkb.config.json.
---

# Ask PKB — 全局知识库查询

## PKB 根路径（按优先级尝试，找到就停）

PKB 根路径按以下顺序确定：

1. **环境变量**: `PKB_ROOT` 已设置 → 直接用
2. **自动检测**: 从当前目录向上走，找包含 `pkb.ps1` + `CLAUDE.md`（含 "PKB" 标记）+ `wiki/` + `raw/` 目录的路径
3. **配置文件**: 读 `~/.pkb/config.json` 中的 `pkb_root` 字段
4. **都不行**: 告诉用户设置 `PKB_ROOT` 环境变量，或在 `~/.pkb/config.json` 中配置

确定后用 `Grep "PKB" <path>/CLAUDE.md` 快速验证该路径确实是 PKB 安装。

## 执行步骤（严格顺序，不过不许往下走）

### Step 1：确定 PKB 根路径

用上面的 4 层策略找到根路径。找到后存为变量，后面所有路径都拼它。

### Step 2：先读地图，再上路

```
Read <PKB_ROOT>/wiki/index.md
```

不要跳过这一步直接去搜。index.md 是知识库的结构图——看了它你才知道哪些页面存在、关键词对应哪个文件。跳过这一步直接 grep 就叫"瞎猜模式"。

### Step 3：锁定目标文件

从 index.md 的表格中匹配用户问题的关键词，确定候选页面列表（最多锁定 5 个）。

如果 index.md 里找不到匹配的页面，告诉用户"知识库里还没有相关内容"，同时给三个建议：
1. 换个关键词试试
2. `/pkb <相关URL>` 先把资料收进来（需在 PKB 项目内执行）
3. 告诉我你大概要查什么方向的

### Step 4：全文搜索补漏

```
Grep <PKB_ROOT>/wiki/ 搜索关键词
```

index.md 可能没有覆盖到所有细节内容。Grep 查出 index 漏掉的文件。

### Step 4b：BM25 检索增强（结果不足时触发）

如果 Step 4 的 grep + Step 3 的 index 候选加起来少于 3 个页面，运行：

```
Bash python tools/pkb_retrieve.py "从用户问题提取的关键词" --mode hybrid --top-k 10 --json --no-snippet
```

从返回的 JSON 中提取 `results[].file`，合并到候选页面列表去重。BM25 检索和 grep/logic 走不同匹配策略——grep 查字面关键词，BM25 按 IDF 加权找语义相关页面。两者互补。

> **不需要每次都跑**：只在候选页面不足时才触发。索引由 SessionStart hook 自动维护，首次使用前如果过期会自动 rebuild。
>
> **混合模式**：`--mode hybrid` 通过 RRF 融合 BM25 关键词 + 向量语义两路召回，再经 cross-encoder 重排序（三阶段 pipeline）。向量不可用时自动降级纯 BM25。首次 `--build` 约需 10 秒（下载 24MB embedding + 568MB reranker + encode 151 篇文档），后续约 3 秒。
>
> **禁用重排序**：`--no-rerank` 跳过 cross-encoder，仅用 RRF/BM25 分数。重排序模型：`BAAI/bge-reranker-v2-m3`（多语言）。
>
> **索引自动维护**：PostToolUse hook 在 wiki 页面写入后自动重建索引（30 秒冷却，防止频繁重建）。

### Step 5：读取命中文件

Read 每个候选文件的 frontmatter 区域（前 30 行）+ 搜索命中的上下文段落。不要整篇读——只读相关部分。

### Step 6：结构化回答

```
## 🔍 查询结果

> [一句话直接回答，或者"知识库里暂时没有直接答案"]

**相关页面**
- [[page-1]] — 为什么相关
- [[page-2]] — 为什么相关

**关键原文**（如果找到了）
> 在这里摘录最相关的段落

**知识缺口**（如果有）
- 缺少 XX 方向的内容，建议用 /pkb <URL> 补充
```

## 反例：这些行为一律禁止

### 🚫 瞎猜模式
问"有没有费尔巴哈的东西"，不去读 wiki/index.md，凭对话记忆说"好像有"。**禁止。** 必须先去读 index。

### 🚫 跳步骤
"index 里好像没有，就不读了"。**禁止。** index 可能没覆盖，Step 4 的 grep 和 Step 4b 的 BM25 都可能命中。

### 🚫 候选太少也不补检索
grep 只找到 1 个页面，index 也只锁定了 1 个，总共 2 个——但就是不去跑 BM25。**禁止。** 候选不足 3 个时必须执行 Step 4b。

### 🚫 全篇默写
把整篇 concept page 复制粘贴给用户。**禁止。** 提取相关段落 + 给页面的 wikilink 让用户自己读完整版。

### 🚫 假装有
问的东西知识库里没有，硬编一个回答。**禁止。** 没有就说没有，告诉用户怎么补。

## 用户体验

- **不需要切窗口**：在任何项目里直接 `/ask-pkb "xxx"`
- **不需要记文件名**：说概念就能找到对应页面
- **不需要手动拼路径**：环境变量 `PKB_ROOT` 或自动检测

## 失败模式记录（遇到新失败时追加）

### v1.4 (2026-06-23)
- Phase 3 检索增强：Cross-encoder 二阶段重排序。
- Reranker 模型：`BAAI/bge-reranker-v2-m3`（568MB，多语言），sentence-transformers 可选。
- 三阶段 pipeline：BM25 + 向量 → RRF 融合 → Cross-encoder 重排。
- `--no-rerank` flag 禁用重排序；`--reranker-model` 覆盖默认模型。
- PostToolUse hook 自动维护索引：wiki 写入后自动 `--build`（30s 冷却）。

### v1.3 (2026-06-23)
- Step 4b 升级为 `--mode hybrid`：BM25 + 向量 RRF 融合检索。
- 向量引擎：`BAAI/bge-small-zh-v1.5`（24MB, 512d），sentence-transformers 可选安装。
- 支持跨语言语义匹配、模糊概念搜索。

### v1.2 (2026-06-23)
- 新增 Step 4b：BM25 检索增强。当 index + grep 候选不足 3 个页面时触发。

*(v1.1 之前无失败记录)*
