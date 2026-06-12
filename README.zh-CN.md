# PKB Starter ![version](https://img.shields.io/badge/version-v0.6.6--alpha-blue)

> **一个命令管理你的知识。** `/pkb <任何东西>` — 丢入 URL、文件或想法，LLM 自动整理一切。
>
> **当前版本**：v0.6.6-alpha

语言：[English](README.md) | [简体中文](README.zh-CN.md)

PKB Starter 是一个 **Claude Code 插件 + 项目模板**，让你在几分钟内拥有一个本地的、LLM 维护的个人知识库。基于 Karpathy 的 [LLM Wiki](https://karpathy.bearblog.dev/llm-wiki/) 理念。

## 它能做什么

```
你: /project:pkb https://example.com/article
PKB: [自动采集 -> 提取 -> 分类 -> 创建 wiki 页面 -> 关联概念 -> git 提交]
     完成。已创建 2 个 wiki 页面。健康状态: [正常]
```

## 特性

- **一条命令**: `/pkb <任何东西>` — 全自动入库，无需人工干预
- **LLM 整理**: AI 自动分类、链接、维护你的知识
- **丰富采集**: 网页、PDF、DOCX、PPTX、GitHub 仓库、视频
- **Obsidian 兼容**: `[[wikilink]]` 知识图谱，打开 wiki/ 即 vault
- **本地文件优先、无云同步、无遥测**；使用 Claude Code 整理时，进入模型上下文的内容按模型服务商规则处理
- **自愈能力**: 健康检查发现断链、过期内容、孤立页面
- **Git 原生**: 每次变更即一次 commit，完整回滚支持

## 快速安装

```bash
git clone https://github.com/Clockworkhg/pkb-starter.git
cd pkb-starter
python scripts/install.py "D:\MyKB"
cd "D:\MyKB"
pip install -r requirements.txt
claude
```

> **路径由你决定**：`D:\MyKB` 只是示例。你可以安装到任何路径——`E:\KnowledgeBase`、`C:\Users\...\Documents\PKB`、`F:\ResearchKB` 等。`install.py` 的第一个位置参数就是目标安装路径，无默认强制路径。也可以使用交互模式：`python scripts/install.py --interactive`

中文用户推荐：
```bash
python scripts/install.py "D:\MyKB" --lang zh-CN
```

在 Claude Code 中（项目模式）：
```
/project:help                        # 查看所有命令
/project:pkb https://example.com     # 开始采集
```

> **注意**: 命令使用 `/project:<名称>` 格式。裸 `/pkb` 仅在安装为 Claude Code 插件时可用。如果命令找不到，参见 [TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)。

> **关于路径**: Windows 支持中文路径，但为了减少 Python、Git、Shell、第三方工具和跨平台兼容问题，建议优先使用英文路径，例如 `D:\MyKB`。如果用户坚持使用中文路径，也可以尝试，但遇到编码或工具兼容问题时，建议迁移到英文路径。

[完整快速入门 ->](docs/zh-CN/QUICKSTART.md)

## 架构

```
raw/          不可变原始资料（网页采集、PDF、文件）
wiki/         LLM 维护的结构化知识（Markdown + [[wikilinks]]）
skills/       Agent 自动化规则（7 个技能）
tools/        Python 辅助脚本（web_pack、import、sanitize 等）
```

[设计深入 ->](docs/zh-CN/DESIGN.md)

## 命令

| 命令 | 功能 |
|------|------|
| `/project:pkb <任何东西>` | 智能入口 — 自动识别类型并处理 |
| `/project:web <url>` | 采集网页内容到 raw/webpacks |
| `/project:inbox` | 处理待入库文件 |
| `/project:ask <问题>` | 搜索知识库 |
| `/project:lint` | 健康检查 |
| `/project:save` | Git 提交并自动更新文档 |
| `/project:rollback` | 查看/回滚 Git 历史 |
| `/project:sanitize` | 隐私扫描 |
| `/project:skills` | 管理可选技能包 |
| `/project:update` | 从 pkb-starter 更新系统文件 |

## 配合 Obsidian 使用

PKB 的 `wiki/` 目录是一个标准的 [Obsidian](https://obsidian.md/zh) 仓库——直接将其作为你的 vault 文件夹打开即可。所有 wiki 页面使用 `[[wikilinks]]` 交叉引用，开箱即用，提供丰富的知识图谱。

### 快速开始

1. [下载 Obsidian](https://obsidian.md/zh)（免费，支持 Windows/Mac/Linux）
2. 打开 Obsidian → "打开文件夹作为仓库" → 选择你的 PKB 的 `wiki/` 目录
3. 图谱视图将自动展示你的知识连接

### 示例场景

**研究者 — 文献综述**

```bash
# 采集论文和网页资源
/project:pkb https://arxiv.org/abs/1706.03762   # "Attention Is All You Need"
/project:pkb ~/Downloads/transformer-survey.pdf
/project:pkb https://karpathy.bearblog.dev/llm-wiki/
```

然后在 Obsidian 中：
- 打开图谱视图（`Ctrl+G`）—— 看到论文、概念、来源自动关联
- 点击任意节点跳转到对应 wiki 页面
- 输入 `[[` 使用自动补全，边写边链接新想法
- 使用 `Ctrl+Shift+F` 搜索全部知识

**学生 — 课程笔记**

```bash
/project:pkb ~/Notes/CS229-lecture01.pdf        # 课件
/project:pkb https://ocw.mit.edu/course/notes    # 课程页面
/project:pkb ~/Downloads/assignment-solution.pdf  # 你的作业
```

然后在 Obsidian 中：
- 每节课成为一个 wiki 页面，与核心概念链接
- 局部图谱（`Ctrl+G` → "局部图谱"）只显示该课程相关的连接
- 在 wiki frontmatter 中使用标签（`#cs229`、`#考试`）按主题组织
- 画布（`Ctrl+P` → "新建画布"）将概念按空间排列

**开发者 — 项目文档**

```bash
/project:pkb https://github.com/oven-sh/bun       # 仓库调研
/project:pkb ~/Projects/设计文档.md               # 你的工作
/project:pkb https://docs.python.org/zh-cn/3/      # 参考资料
```

然后在 Obsidian 中：
- 项目笔记与引用的文档并排展示
- `[[wikilinks]]` 将你的设计决策与来源关联
- 日记插件 → 记录开发进度，链接到 wiki 页面
- Dataview 插件 → 查询所有标记为 `#project-x` 或 `#决策` 的页面

**写作者 — 主题研究**

```bash
/project:pkb https://zh.wikipedia.org/wiki/知识图谱
/project:pkb https://blog.research.google/2023/05/
/project:pkb ~/Downloads/采访笔记.md
```

然后在 Obsidian 中：
- 使用大纲面板查看长文 wiki 页面的结构
- 分屏（`Ctrl+点击`）—— 一边看资料，一边起草
- 书签插件 → 固定常用的概念参考页
- 图谱展示空白区域：连接稀少的聚类 = 需要深入研究的方向

### 推荐插件

以下 Obsidian 社区插件与 PKB 自动生成的 wiki 搭配良好：

| 插件 | 用途 |
|------|------|
| **Dataview** | 按标签、日期或元数据查询 wiki 页面 |
| **Calendar** | 查看与 wiki 概念关联的日记 |
| **Excalidraw** | 在概念页面旁手绘草图 |
| **Omnisearch** | 更快的全文本搜索 |
| **Tag Wrangler** | 批量重命名/合并所有 wiki 页面的标签 |

> **提示**: PKB 自动提交每一次变更。如果你在 Claude Code 运行时通过 Obsidian 编辑 wiki 页面，保存文件——PKB 的 `/save` 或自动提交 hook 会在下一个周期检测到你的更改。

[Obsidian →](https://obsidian.md/zh)

## 可选技能

PKB Starter 出厂零外部依赖。通过 **可选技能包** 扩展功能，目录包含 43 个条目，覆盖 9 个外部仓库（另含 z-skills 作为用户授权本地安装）：

```bash
# 安装时选择
python scripts/install.py "D:\MyKB" --profile student    # 8 个技能 — 学术必备
python scripts/install.py "D:\MyKB" --profile developer  # 7 个技能 — 文档 + 项目
python scripts/install.py "D:\MyKB" --profile research   # 12 个技能 — 完整流程
python scripts/install.py "D:\MyKB" --interactive-skills # 从 42 个条目中选择

# 安装后随时添加
python scripts/skill_manager.py --target "D:\MyKB" --list
python scripts/skill_manager.py --target "D:\MyKB" --install-profile student
python scripts/skill_manager.py --target "D:\MyKB" --install deep-research-skills
```

或在 Claude Code 中：
```
/project:skills                       # 查看状态
/project:skills --list                # 浏览目录
/project:skills --describe <id>       # 了解技能详情
/project:skills --install-profile student
/project:skills --audit
```

配置预设：**Core** (0 外部) | **Student** (8) | **Research** (12) | **Developer** (7) | **Creator** (7) | **Output** (7) | **Security** (3) | **Full** (24) | **Custom** (交互选择)

每个技能在安装前都会展示说明、风险等级和依赖要求。第三方技能克隆到 `skills/_vendor/` — 永不自启，永不自动配置。从 Core 开始，按需添加。

查看完整目录: `python scripts/skill_manager.py --target "D:\MyKB" --list`

[可选技能指南 ->](docs/zh-CN/OPTIONAL_SKILLS.md)

## 适合谁

- **研究者**: 采集论文、构建文献地图、自动生成引用
- **开发者**: 记录项目、收集代码参考、维护设计决策
- **写作者**: 研究主题、整理来源、构建概念地图
- **学生**: 课程笔记、论文分析、考试复习
- **任何人** 想要一个"自我维护的第二大脑"

## PKB 不是什么

- **不是云服务** — 一切都是你磁盘上的本地文件
- **不是笔记应用** — 用 Obsidian 做笔记；PKB 是自动整理器
- **不是搜索引擎** — 它搜索你的知识，不是互联网
- **不是备份工具** — 请使用正规备份；PKB 用 git 做版本管理

## 网页采集器

PKB Starter v0.1.0 内置了**基础网页采集器** (`tools/web_pack.py`)，支持：
- 公开网页抓取 (requests + BeautifulSoup)
- 内容提取（标题、正文、链接、图片）
- Markdown 转换 (markdownify)
- GitHub blob/raw URL 处理
- 标准输出结构（README、manifest、inventories）

**Z-Web-Pack（可选本地安装）**: 用户可选择安装 [z-web-pack](https://github.com/tjxj/z-skills/tree/main/z-web-pack) 作为替代采集后端。PKB Starter 不分发 z-skills 或 z-web-pack 代码。用户必须：
1. 明确选择加入: `/project:skills --install z-skills`
2. 审计许可证: `/project:skills --audit z-skills`
3. 启用适配器: `/project:skills --enable z-web-pack-local`
4. 使用: `/project:web --collector z-web-pack <url>`

参见 [Z_WEB_PACK_PARITY.md](docs/zh-CN/Z_WEB_PACK_PARITY.md) 了解功能对比和 z-skills 兼容模块。

## 更新

当你从 GitHub 更新 pkb-starter 后，已安装的知识库无需重装即可升级系统文件。

**推荐方式 — 使用知识库自带的更新客户端：**

```bash
cd "D:\MyKB"
python tools/pkb_update_client.py              # 预览变更（默认 dry-run）
python tools/pkb_update_client.py --apply      # 执行更新
```

或在 Claude Code 中：
```
/project:update                  # 默认预览（安全）
/project:update --apply          # 确认后执行
```

**备选 — 本地已有 pkb-starter 仓库：**

```bash
python tools/pkb_update_client.py --starter-path "D:\pkb-starter"
```

**高级 — 直接运行 update_pkb.py：**

```bash
python scripts/update_pkb.py "D:\MyKB" --dry-run
```

每次更新都会在 `.pkb_backup/` 中创建带时间戳的备份。用户数据 (`raw/`、`wiki/`、`_INBOX/`、`skills/_vendor/`、`.pkb_local/`) **绝不** 被触碰。配置字段（`language`、`install_path`、`starter_repo_url`）**始终保留**。

[更新指南 ->](docs/zh-CN/UPDATING.md)

## 隐私

- **本地文件优先、无云同步、无遥测** — 文件留在你的机器上
- 使用 Claude Code 整理时，进入模型上下文的内容按模型服务商规则处理
- 敏感信息检测（API key、token、个人身份信息）
- `.gitignore` 包含全面的安全规则
- [安全指南 ->](docs/zh-CN/SECURITY.md)

## 环境要求

- **Claude Code**（需 Claude API 访问权限）
- **Python 3.9+**
- **Git**
- 可选: Obsidian（可视化浏览）

## 文档

| 文档 | 内容 |
|------|------|
| [QUICKSTART.md](docs/zh-CN/QUICKSTART.md) | 5 分钟快速设置 |
| [DESIGN.md](docs/zh-CN/DESIGN.md) | 架构深入 |
| [SECURITY.md](docs/zh-CN/SECURITY.md) | 隐私与安全 |
| [Z_WEB_PACK_PARITY.md](docs/zh-CN/Z_WEB_PACK_PARITY.md) | web_pack 能力说明 |
| [TROUBLESHOOTING.md](docs/zh-CN/TROUBLESHOOTING.md) | 常见问题 |
| [OPTIONAL_SKILLS.md](docs/zh-CN/OPTIONAL_SKILLS.md) | 可选技能包 |
| [UPDATING.md](docs/zh-CN/UPDATING.md) | 更新与迁移指南 |
| [EXAMPLES.md](docs/zh-CN/EXAMPLES.md) | 使用示例 |

## 参与贡献

欢迎贡献！以下方向最需要帮助：
- 更多内容类型分类器
- 更多源格式支持
- 平台特定安装脚本
- 文档改进

## 许可证

MIT — 参见 [LICENSE](LICENSE)

## 当前版本

**v0.6.6-alpha** — 修复更新客户端版本发现与缓存安全问题。`/update` 现在正确检测远端 tag、每次都刷新缓存、支持 `--doctor` 诊断、自动修复 hook 路径污染。

**v0.6.5-alpha** — 新增可选 z-web-pack 兼容层，采集器健康检查，bridge 执行支持。

**v0.6.4-alpha** — 修复默认更新源占位符，新装使用官方仓库地址。

---

*基于"知识管理应 1% 靠人力，99% 靠 AI 组织"的理念构建。*
