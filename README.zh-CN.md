# PKB Starter

> **一个命令管理你的知识。** `/pkb <任何东西>` — 丢入 URL、文件或想法，LLM 自动整理一切。

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
- **本地优先**: 一切都在你的机器上，不上传任何内容
- **自愈能力**: 健康检查发现断链、过期内容、孤立页面
- **Git 原生**: 每次变更即一次 commit，完整回滚支持

## 快速安装

```bash
git clone https://github.com/pkb-starter/pkb-starter.git
cd pkb-starter
python scripts/install.py "D:\我的知识库"
cd "D:\我的知识库"
pip install -r requirements.txt
claude
```

中文用户推荐：
```bash
python scripts/install.py "D:\我的知识库" --lang zh-CN
```

在 Claude Code 中（项目模式）：
```
/project:help                        # 查看所有命令
/project:pkb https://example.com     # 开始采集
```

> **注意**: 命令使用 `/project:<名称>` 格式。裸 `/pkb` 仅在安装为 Claude Code 插件时可用。如果命令找不到，参见 [TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)。

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

## 可选技能

PKB Starter 出厂零外部依赖。通过 **可选技能包** 扩展功能，目录包含 43 个条目，覆盖 9 个外部仓库（另含 z-skills 作为用户授权本地安装）：

```bash
# 安装时选择
python scripts/install.py "D:\我的知识库" --profile student    # 8 个技能 — 学术必备
python scripts/install.py "D:\我的知识库" --profile developer  # 7 个技能 — 文档 + 项目
python scripts/install.py "D:\我的知识库" --profile research   # 12 个技能 — 完整流程
python scripts/install.py "D:\我的知识库" --interactive-skills # 从 42 个条目中选择

# 安装后随时添加
python scripts/skill_manager.py --target "D:\我的知识库" --list
python scripts/skill_manager.py --target "D:\我的知识库" --install-profile student
python scripts/skill_manager.py --target "D:\我的知识库" --install deep-research-skills
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

查看完整目录: `python scripts/skill_manager.py --target "D:\我的知识库" --list`

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

PKB Starter 在 `pkb.config.json` 中跟踪版本。更新已安装知识库的系统文件：

```
/project:update                  # 完整检查和更新
/project:update --dry-run        # 预览变更
/project:update --backup-only    # 仅创建备份
```

或手动操作：
```bash
cd D:\pkb-starter
git pull
python scripts/update_pkb.py "D:\我的知识库" --dry-run
python scripts/update_pkb.py "D:\我的知识库"
```

每次更新都会在 `.pkb_backup/` 中创建带时间戳的备份。用户数据 (`raw/`, `wiki/`, `_INBOX/`) **绝不** 被触碰。

[更新指南 ->](docs/zh-CN/UPDATING.md)

## 安全

- 默认不上传任何内容
- 敏感信息检测（API key、token、个人身份信息）
- `.gitignore` 包含全面的安全规则
- 安全/完整采集模式
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

**v0.6.1-alpha** — 完整的中文支持、中文文档、运行时中文输出。

---

*基于"知识管理应 1% 靠人力，99% 靠 AI 组织"的理念构建。*
