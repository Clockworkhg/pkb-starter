# AGENTS.md — PKB 个人知识库系统规则

> 这是 PKB 系统的"宪法"。所有 Agent 行为必须遵守此文件。
> 版本：1.3.2 | 最后更新：2026-06-20 (hooks v1.0 / install_skills v0.4.0 / scansci_bridge v1.0)
>
> 📄 快速参考见 [CLAUDE.md](CLAUDE.md) — 每次会话自动加载的精简版

---

## 一、三层架构

```
raw/          ← 第一层：原始资料（不可变，只增不删）
wiki/         ← 第二层：LLM 维护的结构化知识（Markdown）
skills/       ← 第三层：元规则 / Agent Skills（如何维护 wiki）
AGENTS.md     ← 第四层：Schema（本文件，定义规则）
```

### 1.1 Raw 层规则
- **raw/ 是只增不删的**。任何导入的原始文件永久保留。
- 子目录按类型分类：`webpacks/`, `clippings/`, `courses/`, `papers/`, `projects/`, `creation/`, `media/`, `personal/`, `assets/`
- 导入时自动生成 `manifest.json`，记录来源、原始路径、导入时间。
- **严禁**将敏感文件（含 API Key、Token、密码等）导入 raw/。

### 1.2 Wiki 层规则
- **wiki/ 由 LLM 维护**，人类可以手动编辑，但主要维护者是 Agent。
- 所有 wiki 页面使用 Markdown 格式，包含 YAML frontmatter。
- 每个页面必须有 `created`, `updated`, `tags` 字段。
- 页面之间通过 `[[wikilink]]` 互连。
- 目录结构：
  - `00_home/` — 首页和全局导航
  - `sources/` — 知识来源索引
  - `concepts/` — 概念笔记（原子化，一个概念一页）
  - `people/` — 人物笔记
  - `courses/` — 课程笔记
  - `papers/` — 论文笔记
  - `projects/` — 项目笔记
  - `questions/` — 问题笔记
  - `outputs/` — 产出（文章、报告等）
  - `tasks/` — 任务追踪
  - `meta/` — 元信息（标签索引、统计等）

### 1.3 Skills 层规则
- `skills/` 下每个子目录是一个 Skill，包含该 Skill 的 prompt 模板和规则。
- Skill 可以引用 tools/ 下的脚本。

---

## 二、自动路由规则

当用户输入 `/pkb <anything>` 时，Agent 必须按以下优先级自动判断：

### 2.1 文件路径（本地文件）
**触发条件**：输入是一个存在的本地文件路径，扩展名为：
`.py` `.ts` `.js` `.md` `.pdf` `.pptx` `.docx` `.xlsx` `.ipynb` `.txt` `.csv` `.json` `.yaml` `.yml` `.toml` `.html` `.css` `.jpg` `.png` `.gif` `.svg` `.webp` `.mp3` `.wav` `.mp4` `.mov` `.zip`

**动作**：执行 `tools/import_to_inbox.py <path>` → 文件复制到 `_INBOX/imported/`，生成 manifest。

### 2.2 文件夹路径
**触发条件**：输入是一个存在的本地目录路径。

**动作**：执行 `tools/import_to_inbox.py <path> --folder` → 整个目录复制到 `_INBOX/imported-folders/`，自动跳过 `.git`, `node_modules`, `.venv`, `__pycache__`, `dist`, `build`, `.tox`, `.mypy_cache`, `.pytest_cache`, `__MACOSX`。

### 2.3 HTTP/HTTPS 网页链接
**触发条件**：输入包含 `http://` 或 `https://` 开头的 URL。

**动作**：执行 `python tools/web_pack.py --topic "<主题>" --url "<url>"` (v3 z-web-pack aligned) → 采集网页内容到 `raw/webpacks/YYYY-MM-DD-主题名/`。
- 默认 `--mode full`（完整图片管线 + yt-dlp）
- GitHub tree 自动走 GitHub Collector v2 (API → git clone)
- 正文提取: readability-lxml → trafilatura → BeautifulSoup → Jina

如果用户未指定主题，Agent 应自动从网页标题提取或询问用户。

### 2.4 GitHub 仓库链接
**触发条件**：输入匹配 `github.com/<owner>/<repo>` 模式。

**动作**：
1. `git clone <url> raw/projects/<repo-name>`
2. 在 `wiki/projects/` 下创建项目索引页。

### 2.5 普通问题 / 关键词
**触发条件**：不匹配以上任何模式。

**动作**：搜索 `wiki/` 和 `raw/` 中的相关内容，返回结构化回答。如果无结果，建议采集相关网页。

---

## 三、文件路径自动导入规则

调用 `tools/import_to_inbox.py` 执行：

1. **默认复制**，绝不移动原始文件。
2. 生成 `manifest.json`：
   ```json
   {
     "source_path": "原始路径",
     "imported_at": "ISO 时间戳",
     "file_type": "扩展名",
     "original_name": "原始文件名",
     "imported_name": "导入后的文件名",
     "size_bytes": 文件大小,
     "sha256": "文件哈希（可选）"
   }
   ```
3. **自动重命名**：如果目标已存在同名文件，添加 `_1`, `_2` 后缀。
4. **跳过目录**：`.git`, `node_modules`, `.venv`, `__pycache__`, `dist`, `build`, `.tox`, `.mypy_cache`, `.pytest_cache`, `__MACOSX`, `.cache`
5. **敏感信息检测**：扫描文件内容，匹配以下模式时**拒绝导入并警告用户**：
   - 包含 `.env` 格式的 KEY=VALUE（含 `api_key`, `token`, `secret`, `password`, `private_key`, `credential`）
   - 文件名匹配 `.env`, `credentials.json`, `serviceAccount.json`, `id_rsa`, `*.pem`
   - 包含 `-----BEGIN RSA PRIVATE KEY-----` 或类似私钥头
6. 导入完成后输出清晰的报告：
   - 导入了多少文件
   - 跳过了多少文件（及原因）
   - 敏感信息警告

---

## 四、网页链接自动采集规则

调用 `tools/web_pack.py` 执行：

1. 从每个 URL 抓取正文（使用 readability 算法或 BeautifulSoup）
2. 下载正文中的图片到 `assets/` 子目录
3. 生成结构化的 webpack 目录（详见 tools/web_pack.py）
4. 在 `wiki/sources/` 下创建源索引页

---

## 五、/ask 与 /ask-pkb 查询规则

### 5.1 /ask — 项目内查询

当用户在当前 PKB 项目内使用 `/ask <问题>` 时：

1. 搜索 `wiki/` 目录中的 Markdown 文件（全文搜索或按 frontmatter tags 搜索）
2. 搜索 `raw/` 目录中的相关文件
3. 整合信息，返回结构化回答：
   - 直接回答（如有匹配的 wiki 页面）
   - 相关来源列表（链接到 raw/ 或 wiki/ 页面）
   - 知识缺口提示（如无相关内容）
4. 如果问题可以生成一个新概念笔记，建议用户保存到 `wiki/concepts/`

### 5.2 /ask-pkb — 全局跨项目查询

当用户在**任意项目**中使用 `/ask-pkb <问题>` 时（v0.6.11+）：

1. 按优先级确定 PKB 根路径：`PKB_ROOT` 环境变量 → 自动检测（向上查找 `pkb.ps1` + `CLAUDE.md` + `wiki/` + `raw/`） → `~/.pkb/config.json` → 提示用户设置
2. 先读 `<PKB_ROOT>/wiki/index.md`（知识库地图），再全文搜索 `wiki/`
3. 禁止「瞎猜模式」（不读 index 直接搜）、「假装有」（编造不存在的知识）
4. 返回结构化回答 + 知识缺口提示
5. 安装：`SKILL.md` 位于 `~/.claude/skills/ask-pkb/`（全局）或 PKB 项目的 `.claude/skills/ask-pkb/`

---

## 六、/output 保存规则

当用户使用 `/output` 时：

1. 将当前对话中产生的有价值内容保存到 `wiki/outputs/`
2. 文件命名：`YYYY-MM-DD-简短描述.md`
3. 包含 frontmatter：`created`, `tags`, `source_conversation`
4. 如果是研究结论，同时更新 `wiki/concepts/` 中的相关页面

---

## 七、/lint 健康检查规则

当用户使用 `/lint` 时，Agent 检查以下项目：

1. **Orphan pages**：wiki/ 中没有任何页面链接到它的孤立页面
2. **Broken wikilinks**：`[[target]]` 指向不存在的页面
3. **Stale content**：`updated` 日期超过 90 天且标记为 `#active` 的页面
4. **Missing frontmatter**：wiki/ 中缺少 `created`/`updated`/`tags` 的页面
5. **敏感信息泄露**：扫描 wiki/ 和 raw/ 中是否意外包含 API Key / Token
6. **空目录**：raw/ 和 wiki/ 下的空子目录
7. **大文件**：raw/ 中超过 50MB 的文件（提醒用户是否需要压缩或外置存储）

输出清晰的检查报告，包含通过/警告/失败的分类。

---

## 八、隐私和 API Key 安全规则

### 8.0 Web Pack 浏览器 Cookie 规则
- `--browser-cookies` **仅在 `--mode full` + 显式传参 + `--download-media` 时可用**
- Cookie 仅传给 yt-dlp 的 `--cookies-from-browser`，不用于 HTTP 网页请求
- Cookie **绝不写入任何文件**（不在 manifest.json、不在 markdown、不在日志）
- `/web` 命令**默认不使用 cookie**（`--mode full` 也需显式传参）

### 8.1 绝对禁止
- **禁止**将任何包含 API Key、Token、密码、私钥的内容写入 raw/ 或 wiki/
- **禁止**将 `.env` 文件或等效配置文件导入知识库
- **禁止**在 wiki 页面中硬编码任何凭据

### 8.2 检测规则
以下模式匹配时，Agent 必须**阻止操作**并警告用户：
- 文件名：`.env`, `.env.local`, `.env.production`, `credentials.json`, `serviceAccount.json`, `id_rsa`, `*.pem`, `*.p12`, `*.pfx`
- 内容匹配：`api_key=`, `apiKey:`, `"token":`, `"secret":`, `"password":`, `"private_key":`, `-----BEGIN RSA`, `-----BEGIN OPENSSH`
- 路径包含：`~/.ssh/`, `~/.aws/`, `~/.gcloud/`, `%APPDATA%`

### 8.3 .gitignore 保障
`.gitignore` 必须包含：
```
.env
.env.*
*credentials*
*serviceAccount*
*.pem
*.p12
*.pfx
id_rsa*
.claude/settings.local.json
```

---

## 九、Git 保存和回滚规则

### 9.1 自动保存 (/save)
- 每次完成重要操作后，Agent 应提醒用户可以 `/save` 提交更改。
- 用户也可以手动 `/save "提交信息"`。
- Commit 格式：`[PKB] YYYY-MM-DD: 简短描述`
- **不要**自动 push 到远程仓库（除非用户配置了 remote）。

### 9.2 回滚 (/rollback)
- `/rollback` — 查看最近的 commit 历史（最近 10 条）
- `/rollback <N>` — 回退 N 个 commit（默认 `git revert`，不删除历史）
- `/rollback --hard <N>` — 硬回退（需要用户二次确认）

### 9.3 初始化
- PKB 根目录是一个 Git 仓库
- `.gitignore` 已配置好排除敏感文件和临时文件
- `_INBOX/` 默认加入 `.gitignore`（待处理文件不入版本控制）

---

## 十、Agent 行为准则

1. **先判断后行动**：收到用户输入后，先按路由规则判断类型，再执行对应操作。
2. **默认安全**：遇到敏感信息，宁可不导入也要保护用户隐私。
3. **操作透明**：每次操作给出清晰的报告，包含做了什么、影响了什么文件。
4. **不做破坏性操作**：不移动原文件，不删除 raw/ 中的文件，不修改原始资料。
5. **维护 wiki 一致性**：导入新资料后，检查是否需要更新 wiki 索引页。

---

## 十一、Autopilot Policy（全自动模式）

### 11.1 触发条件
- **`/pkb <anything>` 默认即为全自动模式**（不需要 `--auto` flag）
- `/inbox` 默认全自动处理 _INBOX
- `--manual` flag 可切换到交互模式
- `--collect-only` flag 只采集不编译
- `--plan` flag 只生成计划不执行

### 11.2 自动完成的操作（不询问用户）
1. 扫描并识别所有输入类型（文件/文件夹/URL/GitHub/微信/webpack）
2. 对本地文件运行 `python tools/pkb_ingest.py <path> [--mode full|safe]`（导入 `_INBOX` + 预提取）
3. 对 URL 运行 `tools/web_pack.py` 生成素材包
4. 读取/使用预提取的文本内容进行 wiki 编译
   **4a. 本地文档预提取 (MarkItDown Phase 1.5, 仅 `--mode full`)**:
   - `pkb_ingest.py` 自动完成: `import_to_inbox` 复制 → `markitdown_convert` 预提取 → 缓存写入 `.pkb-cache/extractions/`
   - 支持格式: `.pdf` `.docx` `.pptx` `.xlsx` `.xls`
   - 默认处理路径: 文件 → `_INBOX` → MarkItDown → 缓存文件 (`.pkb-cache/extractions/<stem>-<sha256>.md`) → wiki 编译
   - **正文传递**: CLI JSON 不含完整正文 — 成功时返回 `extracted_path`，LLM 必须 `Read extracted_path` 获取正文
   - 提取成功时 frontmatter: `extraction_method: markitdown`, `fallback_required: false`
   - Fallback 路径: MarkItDown 失败 → Python 设 `fallback_required=true` (计划状态) → LLM Read _INBOX 副本 → LLM 记录 `fallback_attempted=true, fallback_used=true, fallback_succeeded=<bool>` → 仍失败 → `_PENDING_CONVERSION.md`
   - **Fallback 状态机**: Python 输出「计划状态」(required/attempted=False/used=False)，LLM 执行后写入 wiki 「实际状态」
   - **`.doc` 文件**: 返回 `legacy_doc_unsupported` + `fallback_required=true`。**禁止**将 `.doc` 重命名为 `.docx` 后强行读取。提示用户用 Word/LibreOffice 转换。
   - 依赖: `pip install -r tools/requirements-markitdown.txt`（可选，未安装时自动走 fallback）
   - 诊断: `python tools/pkb_ingest.py --check` 或 `python tools/markitdown_convert.py --check`
   - 版本: 动态读取 `importlib.metadata.version("markitdown")`，不硬编码
   - 缓存目录 `.pkb-cache/` 不进入 Git，正文缓存不是长期知识资产
   - 不支持: OCR、OpenAI/Azure 视觉模型、音频、YouTube、ZIP（Phase 2+）
   - `--mode safe` 不触发 MarkItDown，维持原有 LLM 直接读取行为
5. 按内容类型自动分类（学术论文/课程作业/项目/规范/不确定）
6. 创建 `wiki/sources/` source-note（带完整 frontmatter）
7. 创建/更新 `wiki/concepts/` concept pages
8. 创建/更新 `wiki/projects/` project pages（如适用）
9. 更新 `index.md`, `wiki/index.md`, `log.md`, `wiki/log.md`
10. 将已处理文件从 `_INBOX/imported/` 移动到 `raw/imported_processed/`
11. 自动修复所有 `source_path` frontmatter 为新路径
12. 运行健康检查（frontmatter, broken links, unindexed, stale paths）
13. 健康检查通过后执行 `git commit`

### 11.3 禁止输出的话术（默认全自动模式下）
- ❌ "下一步？"
- ❌ "你可以运行 /inbox --auto"
- ❌ "是否继续？"
- ❌ "是否需要我帮你编译？"
- ✅ 直接执行，最后给报告

### 11.4 仅在以下情况暂停询问用户
| 条件 | 操作 |
|------|------|
| 发现 API key / token / password / 私钥 / 身份证号 | 🛑 阻止操作，警告用户 |
| 需要删除文件 | 🛑 请求确认 |
| 文件无法解析（格式损坏或不支持） | 🛑 报告并生成 `_PENDING_CONVERSION.md` |
| 同名 wiki 页面冲突且无法自动合并 | 🛑 请求用户决策 |
| Git commit 前 secret scan 失败 | 🛑 阻止 commit，报告问题 |

### 11.4 自动处理策略
- **不删除有效资料**：所有原始文件保留在 `raw/imported_processed/`
- **不修改原始文件**：只读处理
- **不确定的内容类型**：创建 source-note 并在 frontmatter 标记 `review_needed: true`
- **微信文章采集失败**：生成 `_PENDING_MANUAL_CLIP.md`，不清空原 URL
- **旧版 .doc 无法提取**：创建基本 source-note，标记待转换为 .docx

### 11.5 每步操作后更新
- 根 `index.md` — 项目级导航（新概念链接）
- `wiki/index.md` — 知识级全量索引（新页面一行摘要）
- 根 `log.md` — 项目级事件日志
- `wiki/log.md` — 知识级 ingest 日志

### 11.6 健康检查标准
操作完成后必须运行健康检查。以下全部通过才执行 git commit：
- ✅ 所有 wiki 页面有完整 frontmatter（created/type/tags）
- ✅ 零破损双链
- ✅ 零未索引页面
- ✅ 无 stale `_INBOX` 引用（操作指示除外）
- ✅ source_path 全部指向正确路径

健康检查失败 → 列出问题清单，**不 commit**，让用户决定是否手动修复后提交。

---

## 十二、CNKI Skills 基础设施

### 12.1 先决条件

CNKI 相关 skills（`cnki-search`, `cnki-download` 等 10 个 + `/pkb-cnki`）依赖 Chrome DevTools MCP。

**一次性自动安装**（首次使用时运行）：
```bash
python tools/cnki_setup.py --fix      # 安装 MCP 包 + 启动 Chrome 调试模式
```

**日常启动**：
```powershell
powershell tools/launch_chrome.ps1    # 智能启动 Chrome（已跑则跳过）
```

### 12.2 自动化程度

| 步骤 | 方式 |
|------|------|
| Chrome 安装检测 | `cnki_setup.py` 自动探测常见路径 |
| chrome-devtools-mcp 安装 | `cnki_setup.py --fix` 自动 `npm install -g` |
| Chrome 调试模式启动 | `launch_chrome.ps1` 自动拉起（已跑则跳过） |
| MCP 连接验证 | `cnki_setup.py` 自动 `GET http://localhost:9222/json` |
| 知网登录 | ⚠️ **必须人工** — 账号密码/SSO/扫码 |
| 验证码 | ⚠️ **必须人工** — cnki skills 会暂停等待 |

### 12.3 MCP 生命周期

- `chrome-devtools` MCP server **仅在 Claude Code 启动时加载**
- compact 恢复的会话中，如果 MCP 是本次会话期间新配置的，工具名不会出现
- 解决方案：**重启 Claude Code**（`exit` 后重新 `claude` 进入项目）

### 12.4 预检流程（/pkb-cnki 执行前自动运行）

```
1. 检查当前会话有无 mcp__chrome-devtools__navigate_page 工具
   ├─ 有 → 继续
   └─ 无 → 输出诊断 + 停止（指导用户运行 setup 工具 + 重启 Claude Code）
2. 检查 http://localhost:9222/json 可达
   ├─ 可达 → 继续
   └─ 不可达 → 指导用户运行 tools/launch_chrome.ps1
```

---

## 十三、文档自动更新系统

### 13.1 概述

PKB 有 5 个项目级文档需要保持与代码库同步：
`index.md` / `COMMANDS.md` / `SKILL_LINKS.md` / `AGENTS.md` / `CLAUDE.md`

`tools/docs_update.py` 自动检测文档是否过期（tool 缺失、skill 缺失、命令缺失、commit 未记录、日期过期）。

### 13.2 触发方式

| 触发 | 行为 |
|------|------|
| `/save` | Step 2 自动运行 `docs_update.py --summary`，过期则自动修复后提交 |
| `/docs-update` | 独立运行诊断 + 修复，不 commit |
| `python tools/docs_update.py` | 命令行人类可读报告 |
| `python tools/docs_update.py --json` | 机器可读（供 Agent 消费） |

### 13.3 检测逻辑

| 文档 | 检测项 |
|------|--------|
| `index.md` | tools/\*.py 是否列出、wiki pages 引用率、日期是否为今天 |
| `COMMANDS.md` | `.claude/commands/*.md` 是否覆盖 ≥60%、CNKI 命令区 |
| `SKILL_LINKS.md` | `.claude/skills/*/` 是否覆盖 ≥50% |
| `AGENTS.md` | 关键章节是否完整（15 个 §）、版本号、日期 |
| `CLAUDE.md` | 文件是否存在、关键章节、工具列表、日期 |

### 13.4 约束

- 只更新项目级 md 文件，不碰 `wiki/` 知识内容
- wiki 页面用 `[[wikilink]]`，普通路径用 Markdown 链接
- 新增条目保持与周围风格一致
- 不重复已存在的条目

---

## 十四、CLAUDE.md 约定

### 14.1 分工

| 文件 | 角色 | 加载方式 |
|------|------|---------|
| **AGENTS.md** | 详细规则宪法（本文件） | Agent + 人类按需参考 |
| **CLAUDE.md** | 快速参考卡片 | Claude Code 每次会话自动注入 |

### 14.2 CLAUDE.md 内容要求

- **精简**：目标 ~80 行，只写每次会话都需要知道的
- **不重复**：详细规则引用 AGENTS.md，不复制粘贴
- **必须包含**：项目概述、三层架构图、关键路径、skill 路由提示、编码约定、工具速查、常见工作流
- **保持同步**：新增 tool/skill/command 后，`/save` 会自动检测 CLAUDE.md 是否过期

### 14.3 维护规则

- 新增 tool → CLAUDE.md 工具表可能需要更新
- 新增 skill 类别 → CLAUDE.md skill 路由可能需要更新
- 架构变更 → CLAUDE.md 架构图需要更新
- 每次 `/save` 自动检测，过期自动修复

---

## 十五、Hooks 系统

### 15.1 概述

PKB 使用 Claude Code harness hooks 将安全规则、健康检查、状态管理从 prompt 层提升到 harness 层。Hooks 注册在 `.claude/settings.json`，脚本存放在 `.claude/hooks/`。

**设计原则**：
- Hook 失败不阻塞工作流（安全违规除外）
- 幂等性：冷却窗口内不重复执行（状态缓存在 `_INBOX/.hook_state/`）
- 性能预算：全部 hooks 总计 < 65s
- Dry-run 模式：每个脚本支持 `--dry-run` 测试

### 15.2 Hook 清单

| # | Hook | 事件 | 匹配 | 行为 | 阻塞？ |
|---|------|------|------|------|--------|
| 1 | `01_session_start.py` | SessionStart | — | 环境验证 + 上下文卡片 + 文档新鲜度检测 | 否 |
| 2 | `02_pre_tool_use.py` | PreToolUse | 全部工具 | 拦截 secret commit / raw 删除 / 敏感文件写入 | **是** |
| 3 | `03_post_tool_use.py` | PostToolUse | Write\|Edit | wiki 文件快速 frontmatter 检查；commit 后全量健康检查 | 否 |
| 4 | `04_post_tool_use_failure.py` | PostToolUseFailure | — | 11 类错误模式匹配 + 恢复建议 | 否 |
| 5 | `05_stop.py` | Stop | — | 未提交提醒 + INBOX 过期预警 + 会话摘要 | 否 |
| 6 | `06_user_prompt_submit.py` | UserPromptSubmit | — | URL/路径/CNKI/论文 智能路由建议 | 否 |

### 15.3 共享库（hook_lib.py）

`hook_lib.py` 为所有 hook 脚本提供基础能力：

| 模块 | 功能 |
|------|------|
| `get_root()` | 从 `PKB_ROOT` 环境变量获取项目根目录 |
| `is_safe_to_run(name, cooldown)` | 幂等性守卫 — 冷却窗口内跳过重复执行 |
| `warn(msg)` / `block(msg)` | 分级输出 — warn 不阻塞，block 退出码 1 |
| `hook_timer(secs)` | 超时上下文管理器 — 超时自动终止 hook |
| `check_pkb_env()` | 验证 PKB_ROOT + 关键目录存在 |
| `scan_content_for_secrets()` | 11 种 secret 模式检测（API key / token / 私钥 / password） |
| `is_sensitive_filename()` | 敏感文件名检测（.env / credentials / .pem / .key） |
| `is_protected_write_path()` | 受保护路径检测（raw/ / .claude/） |
| `is_protected_delete_path()` | 禁止删除路径检测（raw/ / wiki/ / .claude/） |
| `git_staged_files()` | 获取 git 暂存区文件列表 |
| `git_uncommitted_files()` | 获取未提交变更文件列表 |
| `count_wiki_pages()` | 按类型统计 wiki 页面数 |
| `load_hook_config()` | 合并 settings.json + settings.local.json 配置 |
| `is_dry_run()` | 检测 `--dry-run` 标志 |

### 15.4 安全门控（PreToolUse）详细规则

| 触发条件 | 行为 | 说明 |
|---------|------|------|
| `Bash(git commit)` + staged 文件含 secret 模式 | 🛑 block | 检测 API key / token / password / 私钥 |
| `Bash(rm/del/rd)` + 路径含 `raw/` | 🛑 block | "不删除 raw/ 原始资料" |
| `Write/Edit` + 路径在 `raw/` 下 | 🛑 block | raw/ 仅追加，不能修改已有文件 |
| `Write/Edit` + 文件名匹配敏感模式 | 🛑 block | .env / credentials / .pem / .key / id_rsa |
| `Bash(git push)` | ⚠️ warn | push 不是默认行为 |

**注意**：不重复 `settings.json` 中已有的 `deny` 规则（`rm -rf`、`git push --force`、`curl`、`wget`）。

### 15.5 错误分类（PostToolUseFailure）覆盖

| 类别 | 触发模式 | 恢复建议 |
|------|---------|---------|
| network | ConnectionError / Timeout | 重试或 `--collect-only` |
| commit_blocked | git commit rejected | `/lint` 查看健康检查问题 |
| permission | Permission denied | 检查文件占用 |
| security | 敏感信息检测 | 移除 API key / token |
| encoding | GBK 编码错误 | `export PYTHONIOENCODING=utf-8` |
| auth | 401 / 403 / Jina fail | 用 raw URL 或手动采集 |
| not_found | 404 文件不存在 | 检查 URL/路径拼写 |
| invalid_url | 无效协议 | 本地文件用 `/pkb <path>` |
| server_error | 502/503/504 | 稍后重试 |
| dependency | ModuleNotFoundError | `pip install <pkg>` |
| tool_missing | yt-dlp/ffmpeg 缺失 | 安装对应工具 |

### 15.6 智能路由（UserPromptSubmit）规则

| 输入模式 | 建议 |
|---------|------|
| GitHub/Gist/微信 URL | `/pkb <url>` |
| 通用 URL | `/pkb <url>` or `/web <url>` |
| 文件路径 | `/pkb <path>` |
| 含"知网"/"CNKI" | `/pkb-cnki search ...` |
| 含"论文"/"paper"/"文献" | `/paper` or `/research` |
| 含"保存"/"commit" | `/save` |
| 含"检查"/"lint" | `/lint` |

> 路由仅建议，不重定向。30 秒冷却窗口避免噪声。

### 15.7 配置与覆盖

- **全局配置**：`.claude/settings.json` — 注册所有 6 个 hooks
- **用户覆盖**：`.claude/settings.local.json`（gitignored）— 可按 hook 禁用或调整参数
- **Hook 状态缓存**：`_INBOX/.hook_state/`（gitignored）— 存储冷却时间戳，丢失不影响功能

### 15.8 维护规则

- 新增 hook 脚本 → 更新 `.claude/settings.json` 注册 + 更新 CLAUDE.md hooks 速查表 + 更新本文 §15.2
- 修改 hook 行为 → 更新本文对应小节 + 同步 CLAUDE.md
- Hook 故障排查 → 检查 `_INBOX/.hook_state/` 缓存 + `--dry-run` 测试
- 每次 `/save` 自动检测 CLAUDE.md 是否包含 hooks 条目
