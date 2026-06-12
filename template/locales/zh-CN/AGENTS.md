# AGENTS.md -- PKB 系统规则

> 这是 PKB 系统的"宪法"。所有 Agent 行为必须遵守此文件。
> 版本：1.0.0 | 最后更新：2026-06-12
>
> 快速参考见 [CLAUDE.md](CLAUDE.md) -- 每次会话自动加载的精简版

---

## 一、三层架构

```
raw/          ← 第一层：原始资料（不可变，只增不删）
wiki/         ← 第二层：LLM 维护的结构化知识（Markdown）
skills/       ← 第三层：元规则 / Agent Skills（如何维护 wiki）
AGENTS.md     ← 第四层：Schema（本文件，定义规则）
```

### 1.1 Raw 层规则
- **raw/ 是只增不删的**。导入的原始文件永久保留。
- 子目录按类型分类：`webpacks/`、`clippings/`、`courses/`、`papers/`、`projects/`、`creation/`、`media/`、`personal/`、`assets/`
- 导入时自动生成 `manifest.json`，记录来源、原始路径、导入时间。
- **严禁**将包含 API Key、Token、密码等敏感内容的文件导入 raw/。

### 1.2 Wiki 层规则
- **wiki/ 由 LLM 维护**。人类可以手动编辑，但主要维护者是 Agent。
- 所有 wiki 页面使用 Markdown 格式，必须包含 YAML frontmatter。
- 每个页面必须包含 `created`、`updated`、`tags`、`type` 字段。
- 页面之间通过 `[[wikilink]]` 互连。
- 目录结构：
  - `sources/` -- 知识来源索引
  - `concepts/` -- 概念笔记（原子化，一个概念一页）
  - `projects/` -- 项目笔记
  - `outputs/` -- 产出（文章、报告等）

### 1.3 Skills 层规则
- `skills/` 下每个子目录是一个 Skill，包含该 Skill 的 prompt 模板和规则。
- Skill 可以引用 `tools/` 下的脚本。

---

## 二、语言规则

### 2.1 语言检测

当 `pkb.config.json` 中设置 `language` 为 `zh-CN` 时，Agent 必须默认以简体中文生成以下内容：

| 内容类型 | 语言要求 |
|---------|---------|
| wiki 页面（concepts/、sources/、projects/ 等） | 简体中文 |
| 变更日志（log.md） | 简体中文 |
| 健康检查报告 | 简体中文 |
| 导入报告 | 简体中文 |
| frontmatter 中的描述性字段（description、summary） | 简体中文 |
| Agent 与用户的交互输出 | 简体中文 |

### 2.2 例外情况

以下内容保持原文语言，不强制翻译：

- **代码块和命令**：全部保持原样
- **技术术语**：YAML frontmatter、`[[wikilink]]`、`git commit` 等保持英文
- **文件路径**：保持实际路径（如 `D:\MyKB\wiki\concepts\`）
- **原始资料引用**：引用 raw/ 中内容时保留原文，可附加中文摘要
- **第三方工具输出**：不修改外部工具的原生输出
- **用户明确指定**：用户要求使用其他语言时，遵循用户指示

### 2.3 路径示例

本文档中的路径示例使用 Windows 风格路径：

```
D:\MyKB\raw\webpacks\
D:\MyKB\wiki\concepts\
D:\MyKB\raw\papers\
D:\MyKB\tools\web_pack.py
```

Agent 应根据实际运行环境自动适配路径分隔符（Windows `\` 或 POSIX `/`）。

### 2.4 文件名与 Slug 策略

中文模式下，页面标题和正文默认使用简体中文，但文件名、目录名和 slug 优先使用 ASCII-safe 英文命名：

- **Markdown 文件名**：使用英文 slug（如 `personal-knowledge-base.md`），页面 title（YAML frontmatter 或一级标题）使用中文。
- **目录名**：使用英文 slug（如 `wiki/concepts/`），不强制生成中文目录名。
- **source note 文件名**：使用英文 slug（如 `attention-is-all-you-need.md`）。
- **用户明确要求中文文件名时才使用中文文件名**。

这样更利于 Git 版本管理、脚本处理、跨平台同步和 Obsidian 兼容。

---

## 三、自动路由规则

当用户输入 `/pkb <anything>` 时，Agent 必须按以下优先级自动判断：

### 3.1 文件路径（本地文件）
**触发条件**：输入是一个存在的本地文件路径。
**动作**：执行 `python tools/import_to_inbox.py <path>` → 文件复制到 `_INBOX/imported/`，生成 manifest。

### 3.2 文件夹路径
**触发条件**：输入是一个存在的本地目录路径。
**动作**：执行 `python tools/import_to_inbox.py <path> --folder` → 整个目录复制，自动跳过 `.git`、`node_modules`、`.venv`、`__pycache__` 等。

### 3.3 HTTP/HTTPS 网页链接
**触发条件**：输入包含 `http://` 或 `https://`。
**动作**：执行 `python tools/web_pack.py --topic "<主题>" --url "<url>"` → 采集网页内容到 `raw/webpacks/YYYY-MM-DD-主题名/`。
- 默认 `--mode full`（完整图片管线 + yt-dlp）
- GitHub 仓库自动使用 GitHub Collector 模式（API → git clone）
- 正文提取链：readability-lxml → trafilatura → BeautifulSoup → Jina（逐级回退）

如果用户未指定主题，Agent 应自动从网页标题提取或询问用户。

### 3.4 普通问题 / 关键词
**触发条件**：不匹配以上任何模式。
**动作**：搜索 `wiki/` 和 `raw/` 中的相关内容，返回结构化回答。如果无结果，建议采集相关网页。

---

## 四、文件路径自动导入规则

调用 `python tools/import_to_inbox.py` 执行：

1. **默认复制**，绝不移动原始文件。
2. 生成 `manifest.json`，包含 source_path、imported_at、file_type、size_bytes 等字段。
3. **自动重命名**：如果目标已存在同名文件，添加 `_1`、`_2` 后缀。
4. **跳过目录**：`.git`、`node_modules`、`.venv`、`__pycache__`、`dist`、`build`、`.tox`、`.mypy_cache`、`.pytest_cache`、`__MACOSX`、`.cache`
5. **敏感信息检测**：扫描文件内容，匹配到 API Key、Token、密码、私钥等模式时**拒绝导入并警告用户**。
6. 导入完成后输出清晰报告：导入了多少文件、跳过了多少文件（及原因）、敏感信息警告。

---

## 五、网页链接自动采集规则

调用 `python tools/web_pack.py` 执行：

1. 从每个 URL 抓取正文（使用 readability 算法或 BeautifulSoup）
2. 下载正文中的图片到 `assets/` 子目录
3. 生成结构化的 webpack 目录
4. 在 `wiki/sources/` 下创建源索引页

---

## 六、查询规则

当用户使用 `/ask <问题>` 时：

1. 全文搜索 `wiki/` 目录中的 Markdown 文件（按 frontmatter tags 搜索）
2. 搜索 `raw/` 目录中的相关文件
3. 整合信息，返回结构化回答：
   - 直接回答（如有匹配的 wiki 页面）
   - 相关来源列表（链接到 raw/ 或 wiki/ 页面）
   - 知识缺口提示（如无相关内容）
4. 如果问题可以生成一个新概念笔记，建议保存到 `wiki/concepts/`

---

## 七、输出保存规则

当用户使用 `/output` 时：

1. 将当前对话中产生的有价值内容保存到 `wiki/outputs/`
2. 文件命名：`YYYY-MM-DD-简短描述.md`
3. 必须包含 frontmatter：`created`、`tags`、`source_conversation`
4. 如果是研究结论，同时更新 `wiki/concepts/` 中的相关页面

---

## 八、健康检查规则

当用户使用 `/lint` 时，Agent 检查以下项目：

1. **破损双链**：`[[target]]` 指向不存在的页面
2. **孤立页面**：wiki/ 中没有任何页面链接到它的页面
3. **过时内容**：`updated` 日期超过 90 天且标记为 `#active` 的页面
4. **缺失 frontmatter**：wiki/ 中缺少 `created`/`updated`/`tags`/`type` 的页面
5. **敏感信息泄露**：扫描 wiki/ 和 raw/ 中是否意外包含 API Key / Token
6. **空目录**：raw/ 和 wiki/ 下的空子目录
7. **大文件**：raw/ 中超过 50MB 的文件（提醒用户是否需要压缩或外置存储）

输出清晰的检查报告，包含通过/警告/失败的分类。

---

## 九、隐私和 API Key 安全规则

### 9.0 Web Pack 浏览器 Cookie 规则
- `--browser-cookies` 仅在 `--mode full` + 显式传参 + `--download-media` 时可用
- Cookie 仅传给 yt-dlp 的 `--cookies-from-browser`，不用于 HTTP 网页请求
- Cookie **绝不写入任何文件**（不在 manifest.json、不在 markdown、不在日志）

### 9.1 绝对禁止
- **禁止**将任何包含 API Key、Token、密码、私钥的内容写入 raw/ 或 wiki/
- **禁止**将 `.env` 文件或等效配置文件导入知识库
- **禁止**在 wiki 页面中硬编码任何凭据

### 9.2 检测规则
以下模式匹配时，Agent 必须**阻止操作**并警告用户：
- 文件名：`.env`、`.env.local`、`.env.production`、`credentials.json`、`serviceAccount.json`、`id_rsa`、`*.pem`、`*.p12`、`*.pfx`
- 内容匹配：`api_key=`、`apiKey:`、`"token":`、`"secret":`、`"password":`、`"private_key":`、`-----BEGIN RSA`、`-----BEGIN OPENSSH`
- 路径包含：`~/.ssh/`、`~/.aws/`、`~/.gcloud/`、`%APPDATA%`

### 9.3 .gitignore 保障
`.gitignore` 必须包含对敏感文件的排除规则（参见 `template/.gitignore`）。

---

## 十、Git 保存和回滚规则

### 10.1 自动保存
- 每次完成重要操作后，Agent 应提醒用户可以 `/save` 提交更改。
- 用户也可以手动 `/save "提交信息"`。
- Commit 格式：`[PKB] YYYY-MM-DD: 简短描述`
- **不要**自动 push 到远程仓库（除非用户配置了 remote）。

### 10.2 回滚
- `/rollback` -- 查看最近的 commit 历史（最近 10 条）
- `/rollback <N>` -- 回退 N 个 commit（默认 `git revert`，不删除历史）
- `/rollback --hard <N>` -- 硬回退（需要用户二次确认）

### 10.3 初始化
- PKB 根目录是一个 Git 仓库
- `.gitignore` 已配置好排除敏感文件和临时文件
- `_INBOX/` 默认加入 `.gitignore`（待处理文件不入版本控制）

---

## 十一、Agent 行为准则

1. **先判断后行动**：收到用户输入后，先按路由规则判断类型，再执行对应操作。
2. **默认安全**：遇到敏感信息，宁可不导入也要保护用户隐私。
3. **操作透明**：每次操作给出清晰的报告，包含做了什么、影响了什么文件。
4. **不做破坏性操作**：不移动原文件，不删除 raw/ 中的文件，不修改原始资料。
5. **维护 wiki 一致性**：导入新资料后，检查是否需要更新 wiki 索引页。

---

## 十二、Autopilot Policy（全自动模式）

### 12.1 触发条件
- **`/pkb <anything>` 默认即为全自动模式**（不需要 `--auto` flag）
- `--manual` flag 可切换到交互模式
- `--collect-only` flag 只采集不编译 wiki
- `--plan` flag 只生成计划不执行

### 12.2 自动完成的操作（不询问用户）
1. 扫描并识别所有输入类型（文件/文件夹/URL/GitHub/webpack）
2. 将文件复制到 `_INBOX/imported/`
3. 对 URL 运行 `python tools/web_pack.py` 生成素材包
4. 读取文件内容（PDF/DOCX/PPTX/MD），提取文本
5. 按内容类型自动分类
6. 创建 wiki source-note（带完整 frontmatter）
7. 创建/更新 wiki concept pages 和 project pages
8. 更新索引和日志文件
9. 将已处理文件归档
10. 自动修复所有 `source_path` frontmatter 引用
11. 运行健康检查
12. 健康检查通过后执行 `git commit`

### 12.3 禁止输出的话术（默认全自动模式下）
- [禁止] "下一步？"
- [禁止] "你可以运行 /inbox --auto"
- [禁止] "是否继续？"
- [禁止] "是否需要我帮你编译？"
- [允许] 直接执行，最后给报告

### 12.4 仅在以下情况暂停询问用户
| 条件 | 操作 |
|------|------|
| 发现 API key / token / password / 私钥 / 身份证号 | [阻止] 阻止操作，警告用户 |
| 需要删除文件 | [阻止] 请求确认 |
| 文件无法解析（格式损坏或不支持） | [阻止] 报告并生成 _PENDING_CONVERSION.md |
| 同名 wiki 页面冲突且无法自动合并 | [阻止] 请求用户决策 |
| Git commit 前 secret scan 失败 | [阻止] 阻止 commit，报告问题 |

---

## 十三、文档自动更新系统

`tools/docs_update.py` 自动检测文件系统与项目文档（`index.md`、`COMMANDS.md`、`AGENTS.md`、`CLAUDE.md`、`log.md`）之间的差异。

触发方式：`/save` 内置步骤（Step 2 自动运行）或独立的 `/docs-update` 命令。
仅编辑项目级 Markdown 文件 -- 绝不触碰 `wiki/` 知识内容。

---

## 十四、可选 Skill 集成

### 14.1 注册

所有第三方 skill 必须在使用前在 `SKILL_LINKS.md` 中登记。
这包括通过 `install_skills.py` 安装或手动放入 `skills/_vendor/` 的 skill。

### 14.2 输出路由

任何第三方 skill 的输出必须通过 PKB 适配器映射到 `raw/` 或 `wiki/` 中的正确位置：

| Skill 输出类型 | PKB 目标位置 |
|--------------|-------------|
| 学术研究结果 | `wiki/outputs/research/` 或 `wiki/papers/` |
| 文献来源和引用 | `wiki/sources/` |
| 提取的概念 | `wiki/concepts/` |
| 项目相关输出 | `wiki/projects/` |
| 搜索结果 | 不修改 wiki。通过 `/project:inbox` 或 `/project:output` 路由。 |
| 任务/看板数据 | `wiki/tasks/` |
| 文档转换 | `wiki/outputs/<名称>.md`，原始文件进入 `raw/imported_processed/` |

### 14.3 禁止的输出位置

第三方 skill 结果**绝对禁止**散落在项目根目录。
允许路径：`wiki/`、`raw/`、`templates/`、`skills/_vendor/`。
不允许：项目根目录下的 `*.md`、`output/`、`results/`、`data/`（除非用户明确创建）。

### 14.4 风险等级规则

| 风险等级 | 策略 |
|---------|------|
| `low` | 在用户配置中选定后自动安装。 |
| `medium` | 安装时显示警告。首次使用前检查适配器。 |
| `high` | 要求显式 `--enable-risky`。展示 MCP/运行时需求。绝不自动启用。 |
| `reference_only` | 永不安装。仅在目录中登记。 |

### 14.5 适配器协议

每个 skill 在 `templates/skill_adapters/<适配器名称>.md` 中有对应的适配器，定义：
- 何时使用该 skill
- 接受哪些输入类型
- 输出必须放置在 PKB 结构中的哪个位置
- 如何与 PKB 命令集成（`/project:inbox`、`/project:lint`、`/project:save`）

适配器在 skill 安装时复制到目标 PKB。它们是 LLM 的参考文档，不是可执行代码。

### 14.6 需要 MCP 的 Skill

需要 MCP 服务器的 skill（如 zotero-mcp）需要手动配置：
1. 单独安装 MCP 服务器（遵循其官方文档）。
2. 手动将服务器条目添加到 `.claude/mcp.json`。
3. PKB **绝不**自动配置 MCP 服务器。
4. PKB **绝不**读取或存储 MCP API Key。

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

---

*与 CLAUDE.md 保持同步。最后更新：2026-06-12*
