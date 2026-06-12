# PKB Starter -- 可选技能

> 完整的技能生态：43 个目录条目、9 个配置预设、9 个外部仓库追踪、另含 z-skills 作为用户授权本地安装。全部不捆绑——你选择安装什么。

语言：[English](../OPTIONAL_SKILLS.md) | [简体中文](OPTIONAL_SKILLS.md)

## 设计理念

PKB Starter 是一个**核心框架**，零外部技能即可开箱使用。可选技能添加领域专用能力：学术研究、文档处理、语义搜索、项目管理、安全加固。

我们不捆绑第三方代码，原因如下：
1. **许可证清晰** — 每个技能有自己的 LICENSE。捆绑会混合许可证。
2. **用户选择** — 你决定哪些第三方代码在你的机器上运行。
3. **更新独立** — 技能按自己的时间表从各自仓库更新。
4. **安全** — 你审计你安装的内容，而非我们预装的内容。

## 生态一览

| 指标 | 数量 |
|------|------|
| 目录条目总数 | 43 |
| 追踪的外部 GitHub 仓库 | 9 |
| PKB 自建技能（捆绑） | 12 |
| Claude Code 插件市场 | 2 |
| MCP 服务器 | 2 |
| 仅供参考 | 0 |
| 仅适配器（需先安装父技能） | 1 |
| 用户授权本地安装（z-skills） | 1 |
| 核心内置工具 | 5 |

## 配置预设

9 个预设配置适用于不同用例：

| 配置预设 | 技能数 | 最适合 |
|---------|--------|--------|
| **Core** | 0 外部（10 内置） | 极简主义者 — 纯 PKB 工作流 |
| **Student** | 8 | 本科生、课程作业、论文写作 |
| **Research** | 12 | 研究生、学术人员、深度研究 |
| **Developer** | 7 | 软件工程师、项目文档 |
| **Creator** | 7 | 写作者、音乐人、影视制作人、内容创作者 |
| **Output** | 7 | 文档/报告/演示文稿生产者 |
| **Security** | 3 | 隐私审计、发布前加固 |
| **Full** | 24 | 高级用户 — 完整生态 |
| **Custom** | 交互选择 | 高级 — 从 43 个条目中手选 |

### Core 配置预设（始终存在）

以下技能内置于 PKB 模板：
- `web-pack` — 网页内容采集器（requests + BeautifulSoup + markdownify）
- `pkb-auto` — 全自动入库流程
- `import-to-inbox` — 文件导入与密钥检测
- `sanitize-tool` — 隐私扫描器（正则模式）
- `docs-update` — 文档新鲜度检查器
- `git-versioning` — 增强 Git 保存/回滚 + 密钥扫描
- `secret-scan` — 提交前敏感数据检测
- `document-converter` — DOCX/PDF/PPTX 与 Markdown 互转
- `skill-creator` — 新建技能创建向导
- `skill-lint` — 技能健康检查

## 安装

技能可以在初始 PKB 设置时安装，也可以之后随时安装。运行时技能管理器（`skill_manager.py` 和 `/project:skills`）在实时 PKB 安装上工作。

### 初始设置时（使用 install.py）
```bash
python scripts/install.py "D:\MyKB" --profile student
python scripts/install.py "D:\MyKB" --profile student --dry-run   # 仅预览
python scripts/install.py "D:\MyKB" --interactive-skills          # 逐个选择
python scripts/install.py "D:\MyKB" --skip-skills                 # 仅核心，之后添加
```

### 安装后随时（使用 skill_manager.py）
```bash
# 浏览和探索
python scripts/skill_manager.py --target "D:\MyKB" --list
python scripts/skill_manager.py --target "D:\MyKB" --describe deep-research-skills
python scripts/skill_manager.py --target "D:\MyKB" --enabled

# 安装
python scripts/skill_manager.py --target "D:\MyKB" --install deep-research-skills
python scripts/skill_manager.py --target "D:\MyKB" --install-profile research --dry-run
python scripts/skill_manager.py --target "D:\MyKB" --install-profile student

# 管理
python scripts/skill_manager.py --target "D:\MyKB" --audit
python scripts/skill_manager.py --target "D:\MyKB" --enable kanban-skill
python scripts/skill_manager.py --target "D:\MyKB" --disable kanban-skill
python scripts/skill_manager.py --target "D:\MyKB" --update-catalog
```

### 使用 install_skills.py（旧版，仅设置时）
```bash
python scripts/install_skills.py --list
python scripts/install_skills.py --list-profiles
python scripts/install_skills.py --target "D:\MyKB" --profile research --dry-run
python scripts/install_skills.py --target "D:\MyKB" --profile custom
python scripts/install_skills.py --target "D:\MyKB" --audit-only
```

### 从 Claude Code（随时）
```
/project:skills                       # 状态概览
/project:skills --list                # 浏览目录
/project:skills --describe <id>       # 完整详情
/project:skills --install <id>        # 单个技能
/project:skills --install-profile student
/project:skills --audit               # 健康检查
/project:skills --enabled             # 已激活列表
/project:skills --enable <id>         # 激活
/project:skills --disable <id>        # 停用
/project:skills --update-catalog      # 刷新
```

## 运行时技能管理

PKB 的技能系统设计为渐进式采用。无需在设置时决定一切：

1. **从 Core 开始** — 纯 PKB，零外部技能。所有内置工具可用。
2. **按需添加** — `/project:skills --list` 浏览，`--describe` 了解，`--install` 添加。
3. **启用前审计** — `--audit` 检查 LICENSE、.git、适配器。然后 `--enable` 激活。
4. **停用而非删除** — `--disable` 停用但不删除源代码。
5. **始终可逆** — 删除 `skills/_vendor/<id>/` 完全移除。从配置中清除。

### 技能生命周期

```
目录条目  --install-->  skills/_vendor/<id>/  （已下载，未激活）
                             |
                             +--audit-->  审查 LICENSE、代码、适配器
                             |
                             +--enable-->  适配器激活，技能可用
                             |
                             +--disable-->  适配器停用，代码保留
                             |
                             +--删除目录-->  完全移除
```

### 状态模型（在 pkb.config.json 中）

```json
"skills": {
  "catalog_version": "0.5.0",
  "installed_profiles": ["student"],
  "installed_skills": ["deep-research-skills", "kanban-skill"],
  "enabled_skills": ["kanban-skill"],
  "disabled_skills": ["deep-research-skills"],
  "vendor_downloads": ["deep-research-skills", "kanban-skill"],
  "enabled_adapters": ["kanban_adapter.md"],
  "pending_audit": []
}
```

### 每个技能安装前展示

- **简短说明** — 一句话摘要
- **详细说明** — 2-4 句关于用例的描述
- **适用场景** — 典型使用情况
- **不适用场景** — 应避免的情况
- **风险说明** — 通俗语言的风险描述
- **环境要求** — API key、MCP、外部运行时

## 风险等级

技能按风险分类，帮助你做出明智决策：

| 等级 | 策略 | 数量 | 示例 |
|------|------|------|------|
| `low` | 自动安装。无外部依赖。 | 28 | obsidian-skills、kanban-skill、prompt-library、article-extractor |
| `medium` | 安装时警告。检查依赖/token 用量。 | 10 | academic-research-skills、deep-research-skills、qmd、data-analysis |
| `high` | 需要明确确认。MCP 或外部运行时。 | 5 | cnki-skills、zotero-mcp、z-skills、z-web-pack-local |
| `reference_only` | 永不安装。仅设计参考。 | 0 | （无 — z-skills 现为用户授权本地安装） |

## 来源类型

| 类型 | 含义 | 安装方式 |
|------|------|---------|
| `built_in` | PKB 核心模板工具 | 始终存在 |
| `local_template` | PKB 自建技能 | 捆绑在模板中 |
| `external_repo` | 第三方 GitHub 仓库 | `git clone --depth 1` |
| `plugin_marketplace` | Claude Code 插件市场 | `/plugin marketplace add` + `/plugin install` |
| `mcp_server` | MCP 服务器 | 手动配置 `.claude/mcp.json` |
| `reference_only` | 设计参考 | 绝不安装 |
| `adapter_only` | 需要先安装父技能的适配器 | 需要父技能已安装 + 已审计 |
| `user_approved_clone` | 第三方仓库，需明确同意 | 用户输入 'INSTALL' 后 git clone |

## 技能目录（v0.3.0）

### 知识采集（6 个条目）

| ID | 来源 | 风险 | 子技能 | 备注 |
|----|------|------|--------|------|
| web-pack | built_in | low | — | 核心网页采集器，始终启用 |
| pkb-auto | built_in | low | — | 自动入库流程 |
| import-to-inbox | built_in | low | — | 文件导入 + 密钥检测 |
| article-extractor | tapestry-skills (MIT) | low | — | 单篇文章快速提取 |
| ocr-helper | local_template (MIT) | medium | — | 通过 Windows API/Tesseract 进行 OCR |
| web-clipper-helper | local_template (MIT) | low | — | 浏览器剪藏助手 |

### 学术研究（10 个条目）

| ID | 来源 | 风险 | 子技能 | 备注 |
|----|------|------|--------|------|
| academic-research-skills | plugin marketplace | medium | 14 (ars-*) | 完整 ARS 流程 |
| deep-research-skills | Weizhena (MIT) | medium | 5 | 结构化多轮研究 |
| agent-research-skills | lingzhi227 (NO LICENSE) | medium | 31 | 全面的 agent 驱动研究流程 |
| literature-search | agent-research (Tier 1) | low | — | 多源文献搜索 |
| literature-review | agent-research (Tier 1) | low | — | 对话式文献综述 |
| paper-writing-section | agent-research (Tier 1) | low | — | 学术论文撰写 |
| citation-management | agent-research (Tier 2) | low | — | GB/T 7714、APA、IEEE |
| data-analysis | agent-research (Tier 2) | medium | — | 四轮审查的统计分析 |
| cnki-skills | cookjohn (check LICENSE) | high | 10 | 知网数据库（需要 MCP + 登录） |
| zotero-mcp | 54yyyu (check LICENSE) | high | — | MCP 服务器（需要 Zotero 运行中） |
| zotero-mcp-skill | kerim (check LICENSE) | high | — | zotero-mcp 的配套技能 |

### 文档处理（2 个条目）

| ID | 来源 | 风险 | 子技能 | 备注 |
|----|------|------|--------|------|
| anthropic-skills | anthropics (Apache 2.0) | medium | 17 | 官方文档处理技能 |
| document-converter | local_template (MIT) | low | — | DOCX/PDF/PPTX 与 MD 互转 |

### 知识管理（3 个条目）

| ID | 来源 | 风险 | 子技能 | 备注 |
|----|------|------|--------|------|
| obsidian-skills | plugin marketplace | low | 4 | Obsidian vault 管理 |
| qmd | tobi (MIT) | medium | — | 语义搜索（BM25+向量+LLM） |
| kanban-skill | mattjoyce (Apache 2.0) | low | — | 基于 Markdown 文件的看板 |

### 安全与隐私（2 个条目）

| ID | 来源 | 风险 | 子技能 | 备注 |
|----|------|------|--------|------|
| sanitize-tool | built_in | low | — | 核心隐私扫描器 |
| sanitize-skill | wan-huiyan (MIT) | low | — | 增强匿名化器 |

### 创作与产出（4 个条目）

| ID | 来源 | 风险 | 子技能 | 备注 |
|----|------|------|--------|------|
| prompt-library | local_template (MIT) | low | — | AI prompt 库管理 |
| song-archive | local_template (MIT) | low | — | 歌词/Suno 风格版本 |
| script-breakdown | local_template (MIT) | low | — | 剧本 -> 分镜 -> prompts |
| tapestry-skills | michalparkola (MIT) | low | 7 | 创意 + 工具集合 |

### 元工具（3 个条目）

| ID | 来源 | 风险 | 子技能 | 备注 |
|----|------|------|--------|------|
| git-versioning | local_template (MIT) | low | — | 增强 Git + 密钥扫描 |
| skill-creator | local_template (MIT) | low | — | 新建技能创建向导 |
| skill-lint | local_template (MIT) | low | — | 技能健康检查 |

### 开发（2 个条目）

| ID | 来源 | 风险 | 子技能 | 备注 |
|----|------|------|--------|------|
| code-debugging | agent-research (Tier 3) | medium | — | 系统性调试工作流 |
| github-research | agent-research (Tier 3) | medium | — | GitHub 仓库分析 |

### 知识采集 — 外部（2 个条目）

| ID | 来源 | 风险 | 子技能 | 备注 |
|----|------|------|--------|------|
| youtube-transcript | tapestry-skills (MIT) | low | — | 基于 yt-dlp，无需 API key |
| youtube-skills | ZeroPointRepo (MIT) | medium | 12 | 部分需要 TranscriptAPI key |

### 仅供参考（0 个条目）

所有 43 个目录条目均可安装。没有 reference_only 条目。两个条目需要特殊的用户选择加入：

| ID | 来源 | 风险 | 备注 |
|----|------|------|------|
| z-skills | tjxj（需审计） | high | 用户授权本地安装。PKB 不分发。 |
| z-web-pack-local | adapter_only | high | 需要先安装并审计 z-skills。 |

### Z-Skills 兼容模块

PKB Starter v0.4.1 包含一个用于 [z-skills](https://github.com/tjxj/z-skills) 的兼容模块，作为可选的、用户授权的本地安装：

- **不捆绑**：PKB Starter 不包含、不复制、不二次分发 z-skills 代码。
- **用户选择加入**：用户必须明确运行 `/project:skills --install z-skills` 并输入 'INSTALL' 确认。
- **需要审计**：z-skills 安装后进入 `pending_audit`。必须通过审计才能启用。
- **仅适配器**：PKB 适配器（`z_skills_adapter.md`）仅路由输出 — 不修改代码。
- **不默认打补丁**：不修改 z-skills 源代码。兼容性通过包装器/配置实现。
- **本地补丁（万不得已）**：仅在明确 `--allow-local-patch` 时。存储在 `.pkb_local/patches/`（已被 gitignore）。
- **默认采集器不变**：PKB 内置的基础 web_pack 保持默认。z-web-pack 是替代选项。

```bash
# 安装 z-skills（需明确同意）
python scripts/skill_manager.py --target . --install z-skills

# 审计 z-skills
python tools/zskill_bridge.py audit

# 启用 z-web-pack 作为采集后端
python scripts/skill_manager.py --target . --enable z-web-pack-local

# 作为采集器使用
python tools/zskill_bridge.py run --skill z-web-pack --url <url> --topic <topic>
python tools/zskill_bridge.py import-output --path <output-dir>
```

## 适配器如何工作

每个外部技能都有一个**适配器** — 一个 markdown 文档，告诉 Claude Code 将技能输出路由到 PKB 内的何处：

```
外部技能输出              适配器路由到
----------------------    -------------------------
研究报告            --->     wiki/outputs/research/
论文分析            --->     wiki/sources/
文献来源            --->     wiki/sources/
提取的概念          --->     wiki/concepts/
项目任务            --->     wiki/tasks/
搜索结果            --->     （只读，不持久化）
文档转换            --->     wiki/outputs/（+ raw/imported_processed/）
网页采集            --->     raw/webpacks/
学术论文            --->     raw/papers/ + wiki/sources/
YouTube 转录        --->     raw/media/transcripts/
看板                --->     wiki/tasks/
```

适配器不是可执行代码。它们是 LLM 在将技能输出集成到知识库时遵循的参考文档。适配器位于 `template/skill_adapters/`，在技能安装时复制到你的 PKB。

## 追踪的外部仓库

| 仓库 | 技能数 | 许可证 | 风险 |
|------|--------|--------|------|
| kepano/obsidian-skills | 4 | 检查仓库 | low |
| Imbad0202/academic-research-skills | 14 | 检查仓库 | medium |
| Weizhena/Deep-Research-skills | 5 | MIT | medium |
| lingzhi227/agent-research-skills | 31 | NO LICENSE | medium |
| anthropics/skills | 17 | Apache 2.0 / source-available | medium |
| tobi/qmd | 1 (CLI+MCP) | MIT | medium |
| mattjoyce/kanban-skill | 1 | Apache 2.0 | low |
| wan-huiyan/skill-anonymizer | 1 | MIT | low |
| michalparkola/tapestry-skills | 7 | MIT | low |
| ZeroPointRepo/youtube-skills | 12 | MIT | medium |
| cookjohn/cnki-skills | 10 | 检查仓库 | high |
| 54yyyu/zotero-mcp | 1 (MCP) | 检查仓库 | high |
| kerim/zotero-mcp-skill | 1 | 检查仓库 | high |
| tjxj/z-skills | 5（用户选择加入） | 需审计 | high（用户授权本地安装） |
| VoltAgent/awesome-agent-skills | 索引 | 检查仓库 | reference |
| ComposioHQ/awesome-claude-skills | 索引 | 检查仓库 | reference |

## 添加新技能

1. 按照 schema 在 `skills_registry/skill_catalog.json` 中添加条目
2. 如果技能产生输出，在 `template/skill_adapters/<adapter>.md` 中创建适配器
3. 在 `skills_registry/profiles.json` 中添加到相关配置预设
4. 更新本文档的统计数据和表格
5. 测试：`python scripts/install_skills.py --target . --profile custom --dry-run`

## 移除技能

```bash
# 从命令行
python scripts/install_skills.py --target "D:\MyKB" --audit-only  # 检查已安装内容

# 从 Claude Code
/project:skills --remove <skill-id>  # 交互式确认

# 手动
rm -rf skills/_vendor/<skill-id>/
# 然后更新 SKILL_LINKS.md 和 pkb.config.json
```

## 安全

- 技能克隆到 `skills/_vendor/`（默认被 gitignore）。
- 不自动执行任何技能代码 — 安装 = `git clone --depth 1`。
- 需要 MCP 的技能需手动配置 `.claude/mcp.json`。
- PKB 绝不读取或存储第三方技能的 API key。
- 使用前审查每个技能的 LICENSE（检查克隆仓库中的 LICENSE 文件）。
- 高风险技能（CNKI、Zotero）需要明确的 `--enable-risky` 选择加入。
- 仅供参考的技能绝不下载 — 仅目录条目。
- Z-skills（z-skills、z-web-pack-local）需要明确的用户选择加入（"INSTALL"）、审计和启用后才能使用。
- Z-skills 代码不由 pkb-starter 分发。用户直接从 tjxj/z-skills 克隆。
- Z-skills 补丁存入 `.pkb_local/patches/`（已被 gitignore），绝不提交或分发。
- 删除技能只需删除其 `skills/_vendor/<id>/` 目录。

---
*PKB Starter v0.4.1。更新日期：2026-06-12。*
