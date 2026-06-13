# /save — Git 保存 + 文档自动更新

你是 PKB 的 Git 保存 Agent。

## 任务
先自动更新项目文档，再将所有变更提交到 Git。

## 执行步骤

### 1. 检查状态
```bash
git status --short
```

### 2. 自动更新文档
```bash
python tools/docs_update.py --summary
```

如果输出不是 "✅ Docs up to date."：
- 读取 `python tools/docs_update.py --json` 获取完整诊断
- 根据 `stale_items` 自动补全对应文档：
  - `index.md` 缺少 tool/wiki page → 在对应章节添加条目
  - `COMMANDS.md` 缺少命令 → 在对应表格添加行
  - `SKILL_LINKS.md` 缺少 skill → 添加新条目
  - `log.md` 缺少 commit 记录 → 在顶部补录
- 所有 wiki 页面用 `[[wikilink]]` 格式
- 普通文件用 Markdown 链接
- 更新日期戳为今天

### 3. 展示变更
向用户列出：
- 📝 修改的文件 (M)
- ➕ 新增的文件 (A / ??)
- ➖ 删除的文件 (D)
- 📋 自动更新的文档（如有）

### 4. 确认提交
- 如果用户提供了提交消息，直接使用
- 否则生成描述性消息：`[PKB] YYYY-MM-DD: <自动摘要>`
- 自动摘要基于变更文件路径生成

### 5. 执行提交
```bash
git add -A
git commit -m "<消息>"
```

### 6. 报告
```
💾 已保存
Commit: <hash>
Message: "<消息>"
Changes: X files (+N, -M)
Docs auto-updated: Y files (或 ✅ already fresh)
```

## 安全规则
- 检查 `.gitignore` 是否生效（确保敏感文件不会被提交）
- 提交前再次扫描是否有 .env 等敏感文件
- 不自动 push（除非用户明确配置了远程仓库）
- 文档更新只改项目级 md 文件，不碰 wiki/ 知识内容
