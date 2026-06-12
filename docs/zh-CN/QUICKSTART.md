# PKB Starter -- 快速开始

> 5 分钟搭建你自己的 LLM 驱动个人知识库。

语言：[English](../QUICKSTART.md) | [简体中文](QUICKSTART.md)

## 环境准备

- **Claude Code** 已安装（`claude` 命令可用）
- **Python 3.9+**（`python --version`）
- **Git**（`git --version`）
- 可选：**Obsidian**（可视化浏览知识库）

## 第一步：克隆

```bash
git clone https://github.com/pkb-starter/pkb-starter.git
cd pkb-starter
```

## 第二步：安装

```bash
python scripts/install.py "D:\MyKB"
```

> **路径由你决定**：`D:\MyKB` 只是示例。你可以安装到任何路径——`E:\KnowledgeBase`、`C:\Users\...\Documents\PKB`、`F:\ResearchKB` 等。`install.py` 的第一个位置参数就是目标安装路径，无默认强制路径。推荐使用 ASCII 路径。也可使用交互模式：`python scripts/install.py --interactive`

中文用户推荐使用中文模式安装：
```bash
python scripts/install.py "D:\MyKB" --lang zh-CN
```

此命令将创建：
- 完整目录结构（`raw/`、`wiki/`、`_INBOX/`）
- `.claude/commands/` 中的 11 个项目命令
- Python 工具：`web_pack.py`、`pkb_auto.py`、`sanitize.py`、`import_to_inbox.py`、`docs_update.py`、`pkb_update_client.py`
- 包含安全规则的 `.gitignore`
- 初始化的 Git 仓库

> **注意**：`skills/` 目录初始为空。技能属于 pkb-starter **插件仓库**的一部分，不属于项目模板。当 pkb-starter 安装为 Claude Code 插件时，技能全局可用。仅使用项目模板（本安装方式）时，你直接使用 `tools/` Python 脚本。

> **关于路径**：Windows 支持中文路径，但为了减少 Python、Git、Shell、第三方工具和跨平台兼容问题，建议优先使用英文路径，例如 `D:\MyKB`。如果用户坚持使用中文路径，也可以尝试，但遇到编码或工具兼容问题时，建议迁移到英文路径。

## 第三步：安装 Python 依赖

```bash
cd "D:\MyKB"
pip install -r requirements.txt
```

## 第四步：启动

```bash
cd "D:\MyKB"
claude
```

在 Claude Code 中（项目模式）：
```
/project:help                          # 查看所有命令
/project:pkb https://example.com       # 采集网页
/project:pkb Downloads\paper.pdf       # 导入文件
/project:ask transformer 概念          # 搜索知识库
```

> **项目命令**：当你 `cd` 到知识库目录并运行 `claude` 时，命令以 `/project:<名称>` 格式调用。裸 `/pkb` 仅在安装为 Claude Code 插件时可用。

## 可选：安装技能包

通过 43 个条目的技能目录为 PKB 扩展领域专用能力。可以在安装时或之后随时添加：

```bash
# 安装时：选择配置预设
python scripts/install.py "D:\MyKB" --profile student
python scripts/install.py "D:\MyKB" --interactive-skills   # 逐个选择
python scripts/install.py "D:\MyKB" --skip-skills           # 仅核心，之后添加

# 安装后随时管理技能
python scripts/skill_manager.py --target "D:\MyKB" --list
python scripts/skill_manager.py --target "D:\MyKB" --describe deep-research-skills
python scripts/skill_manager.py --target "D:\MyKB" --install deep-research-skills
python scripts/skill_manager.py --target "D:\MyKB" --install-profile student --dry-run
python scripts/skill_manager.py --target "D:\MyKB" --audit

# 或在 Claude Code 中
/project:skills                       # 查看状态和可用配置预设
/project:skills --list                # 浏览全部 43 个条目
/project:skills --describe <id>       # 查看技能完整详情
/project:skills --install <id>        # 安装单个技能
/project:skills --install-profile student
/project:skills --audit               # 检查已安装技能
/project:skills --enable <id>         # 审计后激活
/project:skills --disable <id>        # 停用但不删除
```

配置预设：`core`（仅内置）| `student`（8 个技能）| `research`（12 个）| `developer`（7 个）| `creator`（7 个）| `output`（7 个）| `security`（3 个）| `full`（24 个）| `custom`

每个技能在安装前都会展示说明、风险等级和依赖要求。第三方技能克隆到 `skills/_vendor/`，永不自启。从 Core 开始，按需添加——无需一开始就决定全部。

[完整技能目录和生态 ->](../OPTIONAL_SKILLS.md)

## 第五步：添加第一条知识

```
/project:pkb https://karpathy.bearblog.dev/llm-wiki/
```

等待约 30 秒。Agent 将：
1. 采集网页内容 + 图片
2. 提取正文
3. 创建 wiki 来源笔记和概念页面
4. 更新索引和日志
5. 健康检查
6. Git 提交

在 Obsidian 中打开 `wiki/concepts/` 查看结果。

## 日常工作流

```
/project:pkb <任何东西>     # 丢入任何东西——自动处理
/project:ask <问题>         # 查询你的知识
/project:lint               # 健康检查
/project:save "提交信息"     # Git 提交并自动更新文档
```

就是这样！你现在拥有了一个由 LLM 维护的、持续生长的个人知识库。

## 保持更新

当 pkb-starter 在 GitHub 上发布新版本时，无需重装即可升级系统文件：

```bash
cd "D:\MyKB"
python tools/pkb_update_client.py --dry-run    # 预览变更
python tools/pkb_update_client.py              # 执行更新
```

或在 Claude Code 中：`/project:update`（默认预览），`/project:update --apply` 确认执行。

你的数据（`raw/`、`wiki/`、`_INBOX/`、`skills/_vendor/`）永不被触碰。所有配置设置始终保留。

[完整更新指南 →](UPDATING.md)

---

## 需要帮助？
- [DESIGN.md](../DESIGN.md) — 架构深入
- [TROUBLESHOOTING.md](../TROUBLESHOOTING.md) — 常见问题
- [SECURITY.md](../SECURITY.md) — 隐私与安全指南
