# PKB — 个人知识库系统

> 基于 Obsidian + LLM Wiki + Agent Skills 的本地个人知识库。
> 不是普通 RAG，是"编译式知识库"。
> **当前版本：v0.6.11-alpha** | 组件：web_pack v3.1 | 🆕 全局知识库查询：`/ask-pkb` | 公开模板：[pkb-starter](https://github.com/Clockworkhg/pkb-starter)

## 架构

```
raw/          ← 原始资料（不可变，只增不删）
wiki/         ← LLM 维护的结构化知识
skills/       ← Agent 技能定义
AGENTS.md     ← 系统规则（Agent 读）
COMMANDS.md   ← 命令手册（人读）
```

## 快速开始

### 丢进去就完事了（默认全自动）

```
/pkb "文件路径或链接"
/inbox
```

把任何东西丢给 `/pkb`，自动完成：导入 → 分类 → 编译 wiki → 归档 → 健康检查 → git commit。
**不询问、不暂停、不废话。** 仅安全风险/无法解析/命名冲突时停下。

### 手动控制（如需）

| 命令 | 行为 |
|------|------|
| `/pkb --manual <...>` | 采集后询问下一步 |
| `/pkb --collect-only <...>` | 只采集到 raw，不编译 wiki |
| `/pkb --plan <...>` | 只生成处理计划 |

## 常用命令

| 命令 | 作用 |
|------|------|
| `/pkb <anything>` | 🚀 全自动入库（默认） |
| `/inbox` | 📥 查看或自动处理 _INBOX |
| `/web <url>` | 🌐 底层采集命令（只到 raw/webpacks） |
| `/ask <问题>` | 🔍 项目内查询知识库 |
| `/ask-pkb <问题>` | 🌐 全局知识库查询（任意窗口可用） |
| `/lint` | 🩺 健康检查 |
| `/save` | 💾 Git 保存 |

> `/web` 是底层采集命令，只生成 raw/webpacks。`/pkb` 是完整入口，包含采集 + 编译 + 归档 + commit。
> 日常只需要用 `/pkb`。

完整命令列表：`/help`

## /web 网页采集 (v3.1 — Playwright 动态渲染)

`/web` 是 Raw 层采集命令，使用 **PKB web_pack v3.1**，已对齐 [z-web-pack](https://github.com/tjxj/z-skills/tree/main/z-web-pack) 功能标准。

```bash
# 默认 full 模式（完整图片管线 + GitHub Collector v2）
python tools/web_pack.py --topic "主题" --url "https://..."

# safe 模式（无 cookie/视频/登录态）
python tools/web_pack.py --topic "主题" --url "https://..." --mode safe

# Playwright 动态渲染（仅在普通采集不完整时启用）
python tools/web_pack.py --topic "主题" --url "https://..." --render
python tools/web_pack.py --topic "主题" --url "https://..." --render --headed
python tools/web_pack.py --topic "主题" --url "https://..." --render --debug-network

# 关键参数
--mode full|safe --videos off|direct|all --download-media
--render --headed --debug-network
--browser-cookies chrome --max-image-mb 20 --max-video-mb 300
```

**能力**:
- 正文: readability-lxml → trafilatura → BeautifulSoup → Jina
- 动态页面: Playwright Chromium DOM 渲染（可选，`--render`）
- 网络捕获: XHR/Fetch 响应正文提取（`--render`）
- 正文选择: HTTP / Playwright DOM / Playwright Network 三方质量评分
- 图片: 16 项（srcset, magic bytes, SHA256 去重, tracking 过滤...）
- 视频: yt-dlp 平台视频 + 字幕/封面
- GitHub: API → git clone --depth 1 (v2 Collector)

**Playwright 可选依赖**:
```bash
pip install -r requirements-playwright.txt
playwright install chromium
```

输出结构：
```
raw/webpacks/YYYY-MM-DD-主题/
├── README.md, 00–04 inventory, manifest.json
├── MAIN-xx-*.md / LINKED-xx-*.md
└── assets/
```

完成后用 `/inbox` 编译进 wiki。

## 学术元数据增强 (Phase 1B.1)

`/pkb` 采集学术文献时**自动**检测并补全元数据：

- **自动检测**：识别 DOI/arXiv/PMID/ISSN + 作者 + 年份 + 期刊 等学术信号
- **自动增强**：通过 Crossref/OpenAlex 补全标题、作者、期刊、被引次数
- **期刊等级匹配**：支持 CSSCI/北大核心/AMI/CSCD 等本地导入的期刊目录
- **引用生成**：GB/T 7714 顺序编码制 & 著者-出版年、APA 7、BibTeX、RIS
- **Fail-open**：Crossref/OpenAlex 不可用时不影响 `/pkb` 正常流程

### 配置

```json
// pkb.config.json
{"scholarly": {"enabled": true, "auto_enrich_on_pkb": true}}
```

关闭自动增强：`{"scholarly": {"enabled": false}}`

### 批量工具

```bash
# 批量增强已有文献
python tools/scholarly_enrich.py --scan wiki/ --write
python tools/scholarly_enrich.py --scan wiki/ --write --only-missing
python tools/scholarly_enrich.py --scan wiki/ --write --resume

# 文献筛选
python tools/filter_literature.py --ranking CSSCI
python tools/filter_literature.py --ranking CSSCI --year-from 2023 --min-citations 5

# 导入期刊目录（用户自行获取合法来源）
python tools/import_journal_rankings.py import rankings.csv
```

### 外部网络请求说明

学术增强默认会向 **Crossref** 和 **OpenAlex** 发起网络请求（均为免费公开 API）。

- **Crossref**：查询 DOI 文献元数据（无需密钥，建议配置邮箱 `CROSSREF_EMAIL`）
- **OpenAlex**：查询被引次数与指标（无需密钥，建议配置 API Key `OPENALEX_API_KEY` 提升限额）
- 本地 PDF/文档中的 DOI 可能被发送到上述服务进行解析
- 缓存位置：`.pkb_local/scholarly/cache.sqlite3`（不进入 Git）
- 使用 `--cache-only` 或 `--offline` 可跳过网络请求

> 详细文档：`docs/SCHOLARLY_METADATA.md`

## 外部 Skills 安装状态

| Skill | 状态 | 安装方式 |
|-------|------|---------|
| **obsidian-skills** | ✅ 已安装 | Plugin Marketplace (user scope) |
| **academic-research-skills** | ✅ 已安装 | Plugin Marketplace (user scope) |
| **deep-research-skills** | 🔍 已审核 | 见 `skills/_vendor/` — 待用户决定 |
| **agent-research-skills** | 🔍 已审核 | 见 `skills/_vendor/` — 推荐 Tier 1 安装 |

详细 Skill 索引：`SKILL_LINKS.md`

## 新增可用命令（来自已安装 Skills）

### Obsidian Skills
Obsidian Markdown 编辑、Canvas 白板、Bases 数据库、Web Clipper

### Academic Research Skills (14 个命令)
`/ars-full` `/ars-plan` `/ars-outline` `/ars-abstract` `/ars-lit-review` `/ars-citation-check` `/ars-format-convert` `/ars-reviewer` `/ars-revision` `/ars-revision-coach` `/ars-disclosure` `/ars-mark-read` `/ars-unmark-read` `/ars-cache-invalidate`

## 依赖

- [Obsidian](https://obsidian.md/) — Markdown 知识库编辑器
- [Claude Code](https://claude.ai/code) — LLM Agent
- Python 3 — 运行辅助工具（`tools/`）
  - `pip install requests beautifulsoup4 markdownify`

## 目录结构

参见 `AGENTS.md` 或运行 `/help`。
