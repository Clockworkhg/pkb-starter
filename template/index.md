---
created: 2026-06-11
updated: 2026-06-13
tags: [home, index]
---

# PKB 个人知识库


> 🏠 **项目级首页** — PKB 系统的导航入口。知识内容目录请见 [[wiki/index]]。

基于 Karpathy LLM Wiki 模式的编译式个人知识库。三层架构：`raw/`（不可变原始资料） → `wiki/`（LLM 维护的结构化知识） → `skills/`（Agent 自动化规则）。

## 导航

### 📥 入口
- `/pkb <任何东西>` — 🚀 唯一入口，全自动入库
- `raw/webpacks/` — 网页素材包（6 个活跃包）
- `raw/imported_processed/` — 已处理归档（6 文件）
- `raw/papers/` — 论文 PDF（11 篇，16 MB）

### 🧠 核心概念（AI/Agent 技术栈）
- [[llm-wiki]] — Karpathy LLM Wiki 编译式知识库（PKB 理论基础）
- [[compiled-knowledge-base]] — 编译式 vs 检索式知识库
- [[deepseek-agent-ecosystem]] — DeepSeek Agent 生态（22+ 工具）
- [[agent-runtime]] — Agent 运行时概念（CLI/IDE/桌面/聊天）
- [[coding-agent-selection]] — Coding Agent 选择方法论
- [[claude-code-workflows]] — Claude Code 工作流与方法论（TDD/SDD/BDD + Agent Teams + 安全）
- [[ai-factory]] — AI Factory spec-driven 开发流水线
- [[skills-compatible-runtime]] — Skills 兼容运行时标准
- [[web-pack]] — 网页素材包概念
- [[pkb-web-pack]] — PKB web_pack.py v3 实现
- [[raw-layer]] — Raw 层概念
- [[design-md]] — DESIGN.md 纯文本设计系统（AGENTS.md 的视觉对应物）

### 🌐 学术文献地图（6 领域，~80 篇）
- [[lit-map-cyberspace-six-domains]] — 总图 + 交叉主题矩阵
  - [[lit-cyberspace-governance]] — 网络空间治理政策（16 篇）
  - [[lit-online-public-opinion]] — 网络舆情（12 篇）
  - [[lit-platform-governance]] — 平台治理（14 篇，含 DSA/DMA）
  - [[lit-group-polarization]] — 网络圈群极化（13 篇）
  - [[lit-youth-social-mentality]] — 青少年社会心态（13 篇）
  - [[lit-algorithmic-power]] — 算法权力（14 篇）
- 📄 PDF 已下载: 11/35（31%），见 `raw/papers/manifest.json`
- 🔌 CNKI 集成: `/pkb-cnki fill-gaps` 自动补齐缺失 PDF

### 📄 论文/文献（其他领域）
- [[feuerbach-thesis]] — 《费尔巴哈论》（马克思哲学）
  - [[materialism-dual-semantics]] — 唯物主义双重语义
  - [[engels-practice-four-dimensions]] — 恩格斯实践诠释四重维度
  - [[marx-engels-consistency]] — 马恩一致说 vs 对立说
- [[peach-blossom-fan]] — 《桃花扇》（文学/戏曲）
- [[bill-of-rights-comparison]] — 英美权利法案比较（法律）
- [[grassroots-governance]] — 基层治理（公共管理）

### 🗂️ 项目
- [[cnki-skills-integration]] — CNKI Skills + Chrome DevTools MCP 集成
- [[tjxj-z-skills]] — z-skills 仓库（外部 Skills 集成）
- [[elderly-care-hearing-project]] — 养老服务模拟听证会

### ⚙️ 系统
- [COMMANDS](COMMANDS.md) — 命令手册（35+ 命令）
- [AGENTS](AGENTS.md) — 系统规则（Agent 读，含 §15 Hooks 系统）
- [CLAUDE](CLAUDE.md) — 快速参考（每次会话自动加载）
- [log](log.md) — 项目级变更日志
- [[wiki/index]] — 知识级全量索引
- [[wiki/log]] — 知识级变更日志
- [SKILL_LINKS](SKILL_LINKS.md) — 外部 Skill 索引（39+ skills）
- [PKB 系统白皮书](docs/PKB-系统白皮书.md) — 完整架构、设计哲学与构建过程
- [PKB 教程指南](docs/PKB-教程指南.md) — 从零到一完全教程（入门文档）
- [PKB 手动搭建教程](docs/PKB-手动搭建教程.md) — 手把手从零搭建（含对话示例与原理溯源）
- `.claude/hooks/` — 6 个 harness hooks（安全门控 + 健康检查 + 路由 + 错误恢复）

### 🛠 工具
- `tools/web_pack.py` — 网页完整采集 v3.1（readability + Playwright DOM/Network + yt-dlp + GitHub Collector）
- `tools/content_quality.py` — 正文质量评分（静态采集与动态渲染触发判定）
- `tools/playwright_renderer.py` — Playwright DOM 渲染 fallback（Chromium 浏览器自动化）
- `tools/network_capture.py` — XHR/Fetch 网络响应捕获
- `tools/network_content.py` — 网络正文候选提取与去重
- `tools/selection_engine.py` — HTTP/Playwright DOM/Playwright Network 三方选择引擎
- `tools/pkb_auto.py` — 全自动入库 + 健康检查
- `tools/pkb_ingest.py` — 本地文件入库编排器（import→markitdown→cache→wiki）
- `tools/markitdown_convert.py` — 本地文档→MD 预提取引擎（PDF/DOCX/PPTX/XLSX/XLS）
- `tools/docs_update.py` — 项目文档自动更新
- `tools/cnki_setup.py` — CNKI 基础设施一键诊断 + 自动修复
- `tools/launch_chrome.ps1` — Chrome 远程调试智能启动器
- `tools/download_papers.py` — 批量论文下载协调器
- `tools/download_papers_r2.py` — R2 学术源论文下载
- `tools/download_papers_r3.py` — R3 学术源论文下载
- `tools/scihub_fetch.py` — Sci-Hub 论文获取
- `tools/import_to_inbox.py` — 文件导入 inbox
- `tools/sync_to_starter.py` — PKB → pkb-starter 系统同步（dev-only）

---

*由 PKB 系统维护。最后更新: 2026-06-13 (web_pack v3.1 / MarkItDown Phase 1.5)*
