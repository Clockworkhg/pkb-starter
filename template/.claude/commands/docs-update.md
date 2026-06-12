# /docs-update — 文档自动更新

你是 PKB 的文档更新 Agent。

## 任务
检测项目变更，自动更新 index.md / COMMANDS.md / SKILL_LINKS.md / AGENTS.md / CLAUDE.md / log.md。
不执行 git commit（如需提交请用 `/save`）。

## 执行步骤

### 1. 诊断
```bash
python tools/docs_update.py --json
```

### 2. 自动修复
根据 JSON 中的 `stale_items`，对每个过时文档执行编辑：

**index.md**:
- tool 缺失 → 在 `### 🛠 工具` 章节添加条目
- wiki page 缺失 → 在对应分类章节添加 `[[page-name]] — 一句话描述`
- skill 缺失 → 在对应区域添加
- 日期过期 → 更新 `最后更新: YYYY-MM-DD`

**COMMANDS.md**:
- 命令缺失 → 在对应分类表格添加 `| /xxx | 描述 |`

**SKILL_LINKS.md**:
- skill 缺失 → 添加完整条目（来源/用途/状态/安全等级）

**log.md**:
- commit 缺失 → 在顶部补录 `## YYYY-MM-DD — <摘要>` 条目

### 3. 报告
```
📋 文档更新完成
   index.md: +N 条目
   COMMANDS.md: +M 命令
   SKILL_LINKS.md: +K skills
   log.md: +L 条记录
```

## 约束
- 只更新项目级 md 文件，不碰 wiki/ 知识内容
- 新增条目保持与周围风格一致
- wiki 页面用 `[[wikilink]]`，普通路径用 Markdown 链接
- 不重复已存在的条目（先搜索确认）
- 更新后不 commit（留给 /save 统一提交）
