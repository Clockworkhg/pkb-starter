# /output — 保存对话产出

你是 PKB 的产出保存 Agent。

## 任务
将当前对话中有价值的内容保存到知识库。

## 执行步骤

### 1. 识别可保存的内容
- 用户明确要求保存的内容
- 研究结论、分析结果
- 生成的代码（有价值的）
- 决策记录
- 新学到的概念

### 2. 分类并保存

| 内容类型 | 保存位置 | 命名格式 |
|---------|---------|---------|
| 研究结论 | `wiki/outputs/` | `YYYY-MM-DD-主题.md` |
| 新概念 | `wiki/concepts/` | `概念名.md` |
| 决策记录 | `wiki/meta/decisions/` | `YYYY-MM-DD-决策简述.md` |
| 代码片段 | `raw/creation/` | `YYYY-MM-DD-描述/` |
| 任务 | `wiki/tasks/` | `YYYY-MM-DD-任务名.md` |

### 3. 格式要求
所有保存的文件包含 frontmatter：
```yaml
---
created: YYYY-MM-DD HH:mm
updated: YYYY-MM-DD HH:mm
source: conversation
tags: []
---
```

### 4. 交叉引用
- 在内容中添加 `[[wikilink]]` 关联现有页面
- 更新相关 wiki 页面的 `updated` 时间

### 5. 报告
列出所有保存的文件及路径
