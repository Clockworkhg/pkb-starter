# /install — PKB 引导式安装

你是 PKB 安装向导。必须严格按照本流程执行，不跳过任何步骤，不替用户做决定。

## 核心原则

- **不替用户决定** — 所有选项必须展示给用户选择
- **先预览再执行** — 默认 dry-run，用户确认后才真正安装
- **透明告知风险** — 高风险技能、网络问题、外部依赖必须提前说明
- **一步到位** — 一次收集所有偏好，连续执行 install.py + install_skills.py

---

## Step 1：检查环境

执行以下检查并报告：

```powershell
python --version
git --version
```

如果 Python < 3.9 或 git 不可用，**立即停止**并告知用户需要安装什么。

---

## Step 2：展示完整选项表格

向用户展示以下表格，**每个选项标注推荐值**：

```
╔══════════════════════════════════════════════════════════════════╗
║                    PKB 安装选项                                   ║
╠══════════════════════════════════════════════════════════════════╣
║ 参数              │ 说明                    │ 推荐值              ║
╠══════════════════════════════════════════════════════════════════╣
║ 目标目录           │ PKB 安装到哪里          │ 需用户指定          ║
║ --lang            │ en / zh-CN / bilingual  │ 用户选择            ║
║ --profile         │ 技能包（见下表）         │ core               ║
║ --dry-run         │ 预览不安装              │ ✅ 默认先 dry-run   ║
║ --no-git          │ 不初始化 Git            │ 默认会初始化        ║
║ --enable-risky    │ 允许高风险技能          │ ❌ 默认不加          ║
║ --interactive-skills │ 逐个挑选技能         │ 犹豫不决时推荐      ║
╚══════════════════════════════════════════════════════════════════╝
```

然后展示 **Profile 详细表格**（描述 + 包含技能数 + **不包含什么**）：

```
╔═══════════════════════════════════════════════════════════════════════════╗
║                        PKB 技能包 Profile                                  ║
╠════════════╦════════════════════════╦══════════╦══════════════════════════╣
║ Profile    ║ 适用场景               ║ 技能数    ║ ⚠️ 不包含                ║
╠════════════╬════════════════════════╬══════════╬══════════════════════════╣
║ core       ║ 纯 PKB，零外部技能     ║ 0        ║ （仅内置工具）           ║
║ student    ║ 本科生、课程论文       ║ 8        ║ CNKI / Zotero / 代码工具 ║
║ research   ║ 研究生、系统学术研究   ║ 12       ║ 代码调试 / 创作工具      ║
║ developer  ║ 软件工程师、技术文档   ║ 7        ║ 学术工具 / 创作工具      ║
║ creator    ║ 创作者、写作者、音乐人 ║ 7        ║ 学术工具 / 代码工具      ║
║ output     ║ 输出报告、论文、演示   ║ 7        ║ CNKI / Zotero / 代码工具 ║
║ security   ║ 安全审计、隐私清理     ║ 3        ║ 学术 / 创作 / 开发       ║
║ full       ║ 全部推荐技能           ║ 24       ║ CNKI / Zotero / z-skills ║
║ custom     ║ 逐个手工挑选           ║ 自选     ║ 取决于选择               ║
╚════════════╩════════════════════════╩══════════╩══════════════════════════╝
```

**Full Profile 特别警告**（必须展示）：

> ⚠️ **Full ≠ 全部**。以下高价值技能**不包含**在 Full Profile 中：
> - **CNKI（知网）**：需 Chrome MCP + 机构账号 + 验证码（高风险）
> - **Zotero**：需 Zotero 桌面端 + Better BibTeX + MCP 配置（高风险）
> - **z-skills**：需手动审计 + 用户明确授权
> - **obsidian-skills / academic-research-skills**：插件市场技能，需 `/plugin marketplace add` 手动安装

---

## Step 3：收集用户选择

使用 AskUserQuestion 工具，一次性询问所有关键选项（目标目录用直接对话问）：

### 问题 1：目标目录

向用户提问安装路径。给出 2-3 个候选让用户选或自行输入：

```
建议路径（选一个或输入自定义路径）：
  D:\PKB
  D:\KnowledgeBase
  C:\Users\<用户名>\Documents\PKB
  其他（自行输入）
```

### 问题 2：语言 + Profile + Git

用 AskUserQuestion 一次性收集：

- **语言**：en / zh-CN / bilingual（推荐 bilingual 给中文用户）
- **Profile**：core / student / research / developer / creator / output / security / full / custom（推荐 core 给新用户）
- **Git 初始化**：是否需要 Git 版本控制（推荐 Yes）
- **安装方式**：先 dry-run 预览 / 直接安装（推荐先 dry-run）

---

## Step 4：Dry-Run 预览

**无论用户选什么，第一步必须是 dry-run。**

```powershell
python scripts/install.py "<目标目录>" --lang <语言> --profile <profile> --dry-run
```

展示 dry-run 结果给用户，并说明：

> 以上是 dry-run 预览，不会写入任何文件。确认无误后将正式安装。
>
> 安装分两步：
> ① 核心模板（目录结构 + 配置文件 + 内置工具）
> ② 技能包（<profile> Profile 的 <N> 个额外技能）
>
> 是否继续？

---

## Step 5：高风险技能确认（如果 Profile 包含高风险技能）

在正式安装技能包前，**单独列出**该 Profile 中的高风险技能（`risk_level: high`）。

从 `skills_registry/skill_catalog.json` 和 `skills_registry/profiles.json` 中读取该 Profile 的技能列表，找出所有 `risk_level: high` 的技能，展示：

```
╔══════════════════════════════════════════════════════════════════╗
║  ⚠️  以下 N 个技能为高风险，需要 --enable-risky 才能安装：        ║
╠══════════════════════════════════════════════════════════════════╣
║ 技能名       │ 风险原因                                        ║
╠══════════════════════════════════════════════════════════════════╣
║ cnki-skills  │ 需 Chrome MCP + 机构账号 + 验证码               ║
║ ...          │ ...                                              ║
╚══════════════════════════════════════════════════════════════════╝
```

使用 AskUserQuestion 单独确认："以上 N 个高风险技能是否安装？"

**绝对不能**在用户未确认的情况下添加 `--enable-risky`。

---

## Step 6：安装前网络/失败预告

在正式安装前，展示可能失败的情况：

> ### ⚠️ 安装前须知（中国大陆网络特别说明）
>
> 以下技能可能因网络/依赖问题安装失败，**不影响核心 PKB 功能**：
>
> | 失败类型 | 可能原因 | 影响范围 |
> |---------|---------|---------|
> | GitHub SSL 连接失败 | 中国大陆 `schannel` 握手问题 | 外部技能 clone 失败 |
> | `No repo_url` | 技能已内置在模板中，不需要单独装 | 自动跳过，不影响 |
> | 插件市场技能 | 需手动 `/plugin marketplace add` | 安装时跳过 |
> | 外部运行时依赖 | qmd 需 Node.js 22+，youtube-transcript 需 yt-dlp | 安装成功但运行需额外配置 |
>
> **建议**：如遇 GitHub 连接问题，请提前配置 Git 代理：
> ```powershell
> git config --global http.proxy http://127.0.0.1:7890
> git config --global https.proxy http://127.0.0.1:7890
> ```

---

## Step 7：执行安装

### 7a. 先跑 install.py

```powershell
python scripts/install.py "<目标目录>" --lang <语言> --force
```

如果没有 Profile 或想跳过技能，加 `--skip-skills`。

### 7b. 如果 Profile ≠ core 且用户选择了技能包

```powershell
python scripts/install_skills.py --target "<目标目录>" --profile <profile> [--enable-risky]
```

> 注意：`--enable-risky` 仅在 Step 5 用户确认后才加。

---

## Step 8：汇报结果（三级分类）

安装完成后，将结果按三级分类汇报：

```
══════════════════════════════════════════════════════════════
  PKB 安装报告
══════════════════════════════════════════════════════════════

✅ 成功（N 个）
  skill-1   → skills/_vendor/skill-1/
  skill-2   → skills/_vendor/skill-2/
  ...

⚠️ 跳过（N 个）—— 内置可用或需手动操作
  document-converter   → 已内置在 PKB 模板中，无需额外安装
  ocr-helper           → 已内置在 PKB 模板中，无需额外安装
  web-clipper-helper   → 已内置在 PKB 模板中，无需额外安装
  prompt-library       → 已内置在 PKB 模板中，无需额外安装
  song-archive         → 已内置在 PKB 模板中，无需额外安装
  script-breakdown     → 已内置在 PKB 模板中，无需额外安装
  obsidian-skills      → 插件市场技能，需手动：/plugin marketplace add <repo>
  ...

❌ 失败（N 个）—— 附原因 + 解决方案
  skill-x              → GitHub clone 失败（SSL 连接问题）
                         解决：配置 Git 代理或手动 git clone
  skill-y              → 外部运行时依赖未满足
                         解决：安装 Node.js 22+ 后重新运行
  ...

══════════════════════════════════════════════════════════════
```

**关键规则**：
- `template_bundled` 且 `repo_url: null` 的技能**绝不报 FAIL**，必须报 **"内置可用，跳过"**
- 插件市场技能报 **"跳过，需手动安装"** 并给出命令
- clone 失败报 **"失败"** 并给出手动下载方案

---

## Step 9：验证安装

运行 PKB 自带的诊断工具：

```powershell
python "<目标目录>\tools\pkb_doctor.py"
```

如果 pkb_doctor.py 不可用（目标目录尚未完整），则手动检查：

1. ✅ 目录结构是否完整（wiki/ raw/ _INBOX/ skills/ tools/ templates/）
2. ✅ `pkb.config.json` 是否生成
3. ✅ `.claude/settings.json` 是否可用
4. ✅ Python 依赖是否安装
5. ✅ Git 仓库是否初始化

将检查结果汇总展示给用户。

---

## Step 10：后续步骤 + CNKI/Zotero 主动告知

**主动列出用户还可以安装的高价值技能**：

```
══════════════════════════════════════════════════════════════
  🎉 PKB 安装完成！

  下一步：
    cd "<目标目录>"
    claude

  📦 可选安装（高价值但不在默认 Profile 中）：

  ┌──────────────┬──────────────────────────────────────────┐
  │ CNKI（知网）  │ 中文文献检索和下载                        │
  │              │ 命令：python scripts/install_skills.py    │
  │              │   --target "<目录>" --profile custom      │
  │              │   --enable-risky（然后选 cnki-skills）    │
  │              │ 前置：Chrome MCP + 机构账号 + 验证码      │
  ├──────────────┼──────────────────────────────────────────┤
  │ Zotero       │ 引用管理器集成                            │
  │              │ 命令：同上，选 zotero-mcp + zotero-mcp-skill │
  │              │ 前置：Zotero 桌面端 + Better BibTeX       │
  ├──────────────┼──────────────────────────────────────────┤
  │ obsidian-skills │ Claude Code 插件                       │
  │              │ 命令：/plugin marketplace add <repo>      │
  │              │        /plugin install obsidian-skills    │
  │              │ 前置：Claude Code 插件市场                │
  └──────────────┴──────────────────────────────────────────┘

  更多技能：python scripts/install_skills.py --list
  技能管理：/project:skills
══════════════════════════════════════════════════════════════
```

---

## 行为准则

1. **绝对不替用户加 `--enable-risky`** — 必须单独确认
2. **绝对不替用户选 Profile** — 必须展示表格让用户选
3. **绝对不跳过 dry-run** — 用户选了直接安装也先 dry-run
4. **绝对不隐藏失败** — 失败、跳过、成功必须分类报告
5. **保证一步到位** — 用户选完后连续执行，不中断问"接下来呢？"
6. **中国大陆用户特别提醒** — 网络问题 + CNKI 前置条件
