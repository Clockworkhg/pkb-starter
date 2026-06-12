# /docs-update — 文档自动更新

你是 PKB 的文档更新 Agent。

## 任务
检测项目变更，自动更新 index.md / COMMANDS.md / SKILL_LINKS.md / log.md。AGENTS.md 和 CLAUDE.md 是受保护的规则文件，仅诊断不自动写入。

不执行 git commit（如需提交请用 `/save`）。

## 执行步骤

### 1. 诊断（默认，不修改任何文件）

```bash
python tools/docs_update.py --check
```

或获取结构化数据：

```bash
python tools/docs_update.py --json
```

### 2. 报告诊断结果

向用户展示哪些文件有 stale items，并分类：
- **Safe**（可自动修复）：index.md、COMMANDS.md、SKILL_LINKS.md、log.md
- **Protected**（仅手动审查）：AGENTS.md、CLAUDE.md

### 3. 修复 Safe 文件（需用户明确确认后执行）

用户确认后运行：

```bash
python tools/docs_update.py --apply
```

**仅修改 safe docs**。受保护文件不修改，只给建议。

### 4. 受保护文件处理

AGENTS.md 和 CLAUDE.md 由 ARS scope guard 保护。

**规则**：
- `--check` 可以检查它们，报告 stale items
- `--apply` **不会修改它们**，只会报告"PROTECTED — manual review required"
- **绝不**建议用 PowerShell/Bash 绕过保护
- 如需更新，给用户提供具体的手动编辑建议

### 5. 修复逻辑（Safe 文件）

`--apply` 对非受保护文件执行安全、有针对性的修复：

**日期修复**：
- YYYY-MM-DD 占位符 → 当前日期（仅在前置词语如"最后更新："、"Last updated:"、"updated:"后）
- 过期日期 → 当前日期（仅在前置词语匹配时）
- **不会盲扫替换**所有日期格式文本

**版本修复**：
- 仅在版本上下文字段中进行替换（"版本：v<old>"、"version: v<old>"）
- 将已知旧版本替换为当前版本
- **绝不**把日期片段错误写入版本字段
- **绝不**使用同一正则同时处理版本和日期

### 6. 报告

```
📋 文档更新完成
   index.md: +N 条目（或 "up to date"）
   COMMANDS.md: +M 条目（或 "up to date"）
   SKILL_LINKS.md: +K skills（或 "up to date"）
   log.md: +L 条记录（或 "up to date"）

   Protected（需手动审查）:
   AGENTS.md: X stale items — 请手动编辑
   CLAUDE.md: Y stale items — 请手动编辑
```

## 约束
- 只更新项目级 md 文件，不碰 wiki/ 知识内容
- 受保护文件（AGENTS.md、CLAUDE.md）只诊断不写入
- **绝不**绕过 ARS scope guard
- **绝不**教用户用 PowerShell/Bash 绕过保护机制
- 新增条目保持与周围风格一致
- wiki 页面用 `[[wikilink]]`，普通路径用 Markdown 链接
- 不重复已存在的条目（先搜索确认）
- 更新后不 commit（留给 /save 统一提交）
- Fresh install 应报告 stale count = 0
