# PKB Starter -- 使用示例

语言：[English](../EXAMPLES.md) | [简体中文](EXAMPLES.md)

## 示例 1：采集并入库一篇博客文章

```
用户: /project:pkb https://karpathy.bearblog.dev/llm-wiki/

Agent:
  [1/10] 解析：URL -> 网页采集
  [2/10] 运行：python tools/web_pack.py --topic "llm-wiki" --url "https://karpathy.bearblog.dev/llm-wiki/"
  [3/10] 已采集：1 个页面、3 张图片、12 个链接 -> raw/webpacks/2026-06-12-llm-wiki/
  [4/10] 入库中：llm-wiki -> wiki/sources/llm-wiki-karpathy.md + wiki/concepts/llm-wiki.md
  [5/10] 索引中：已更新 wiki/index.md（+1 条目）
  [6/10] 归档中：已处理 1 个 webpack
  [7/10] 日志中：已更新 wiki/log.md + log.md
  [8/10] 健康检查：通过
  [9/10] Git 提交：f3a21bc — [PKB] auto ingest: 2026-06-12 — llm-wiki blog post
  [10/10] 报告：
    已创建 1 个新 wiki 页面
    已更新 1 个概念页面
    健康状态：通过
    提交：f3a21bc
```

## 示例 2：导入并分析 PDF 论文

```
用户: /project:pkb ~/Downloads/attention-is-all-you-need.pdf

Agent:
  [1/10] 解析：本地文件 — attention-is-all-you-need.pdf
  [2/10] 导入中：~/Downloads/attention-is-all-you-need.pdf -> _INBOX/imported/
  [3/10] 入库中：检测到学术论文
           -> wiki/sources/attention-is-all-you-need.md
           -> wiki/concepts/transformer-architecture.md
  [4/10] 索引中：已更新 wiki/index.md
  [5/10] 归档中：_INBOX -> raw/imported_processed/attention-is-all-you-need.pdf
  [6/10] 日志中：完成
  [7/10] 健康检查：通过
  [8/10] Git 提交：a4b56cd — [PKB] auto ingest: 2026-06-12 — attention is all you need
  [9/10] 报告：
    已创建 2 个新 wiki 页面
    PDF：12 页、2.3 MB
    健康状态：通过
    提交：a4b56cd
```

## 示例 3：搜索你的知识库

```
用户: /project:ask transformer attention mechanism

Agent: 正在搜索 wiki/ 和 raw/ 中关于 "transformer attention mechanism" 的内容...

## 查询结果

### 直接答案
来自 [[transformer-architecture]]：
Transformer 使用多头自注意力机制，其中 Query、Key、Value
矩阵计算注意力分数：Attention(Q,K,V) = softmax(QK^T/sqrt(dk))V。

### 相关 Wiki 页面
- [[transformer-architecture]] — 完整架构描述
- [[attention-is-all-you-need]] — 原始论文来源笔记
- [[llm-wiki]] — LLM Wiki 知识库概念

### 相关原始资料
- `raw/papers/attention-is-all-you-need.pdf` — 原始论文

### 知识空白
- 没有关于 Flash Attention 或高效注意力变体的内容
  -> 运行 /project:web https://arxiv.org/abs/2205.14135 进行采集
```

## 示例 4：GitHub 仓库采集

```
用户: /project:pkb https://github.com/squidfunk/mkdocs-material

Agent:
  [1/10] 解析：GitHub URL — squidfunk/mkdocs-material
  [2/10] 运行：GitHub Collector 模式
           -> GitHub raw：README.md、CONTRIBUTING.md
  [3/10] 已采集：3 个页面、5 个代码文件 -> raw/webpacks/2026-06-12-mkdocs-material/
  [4/10] 入库中：mkdocs-material 工具 -> wiki/sources/mkdocs-material.md + wiki/concepts/static-site-generator.md
  ...
  [10/10] 报告：2 个 wiki 页面，健康状态：通过
```

## 示例 5：每日健康检查

```
用户: /project:lint

Agent:
PKB 健康检查报告
================

通过（5 项）
  - 所有 frontmatter 完整（42 页）
  - 无断链 wikilink（已检查 156 个）
  - 未检测到敏感信息
  - 所有 source_path 引用有效
  - 索引一致性：42/42 页已索引

警告（2 项）
  - wiki/concepts/old-methodology.md — 上次更新于 120 天前
  - wiki/sources/archived-project.md — 孤立页面（无入链）

统计
  - Wiki 页面：42
  - 概念：18 | 来源：15 | 项目：5 | 产出：4
  - 原始文件：87
  - 总大小：156 MB
```

## 示例 6：使用中文模式

```
# 安装时选择中文
python scripts/install.py "D:\我的知识库" --lang zh-CN

# 日常使用
/project:pkb https://example.com/article
# Agent 自动以中文生成 wiki 页面和报告

/project:ask 什么是 Transformer 架构
# Agent 以中文搜索并回答

/project:lint
# 健康检查报告以中文显示
```

## 示例 7：管理可选技能

```
# 浏览技能目录
python scripts/skill_manager.py --target "D:\我的知识库" --list

# 查看某个技能的详细信息
python scripts/skill_manager.py --target "D:\我的知识库" --describe deep-research-skills

# 安装学生配置预设
python scripts/skill_manager.py --target "D:\我的知识库" --install-profile student

# 审计已安装技能
python scripts/skill_manager.py --target "D:\我的知识库" --audit

# 启用一个技能
python scripts/skill_manager.py --target "D:\我的知识库" --enable kanban-skill
```

## 示例 8：更新知识库系统文件

```
# 预览更新
/project:update --dry-run

# 执行更新
/project:update

# 仅创建备份
/project:update --backup-only
```

---

*欢迎社区贡献更多使用示例。*
