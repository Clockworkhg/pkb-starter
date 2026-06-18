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
"index 里好像没有，就不读了"。**禁止。** index 可能没覆盖，Step 4 的 grep 可能命中。

### 🚫 全篇默写
把整篇 concept page 复制粘贴给用户。**禁止。** 提取相关段落 + 给页面的 wikilink 让用户自己读完整版。

### 🚫 假装有
问的东西知识库里没有，硬编一个回答。**禁止。** 没有就说没有，告诉用户怎么补。

## 用户体验

- **不需要切窗口**：在任何项目里直接 `/ask-pkb "xxx"`
- **不需要记文件名**：说概念就能找到对应页面
- **不需要手动拼路径**：环境变量 `PKB_ROOT` 或自动检测

## 失败模式记录（遇到新失败时追加）

*(目前是 v1.1，还没有失败记录。第一次翻车后，把原因写在这里。)*
