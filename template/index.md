---
created: 2026-06-11
updated: 2026-06-24
tags: [home, index]
---

# PKB 个人知识库

> 🏠 **项目级首页** — PKB 系统的导航入口。知识内容目录请见 [[wiki/index]]。

基于 Karpathy LLM Wiki 模式的编译式个人知识库。三层架构：`raw/`（不可变原始资料） → `wiki/`（LLM 维护的结构化知识） → `skills/`（Agent 自动化规则）。

## 导航

### 📥 入口
- `/pkb <任何东西>` — 🚀 唯一入口，全自动入库
- `raw/webpacks/` — 网页素材包
- `raw/papers/` — 论文 PDF
- `raw/imported_processed/` — 已处理归档

### 🧠 核心概念（AI/Agent 技术栈）
- [[llm-wiki]] — Karpathy LLM Wiki 编译式知识库（PKB 理论基础）
- [[compiled-knowledge-base]] — 编译式 vs 检索式知识库
- [[deepseek-agent-ecosystem]] — DeepSeek Agent 生态
- [[agent-runtime]] — Agent 运行时概念（CLI/IDE/桌面/聊天）
- [[coding-agent-selection]] — Coding Agent 选择方法论
- [[claude-code-workflows]] — Claude Code 工作流与方法论
- [[ai-factory]] — AI Factory spec-driven 开发流水线
- [[skills-compatible-runtime]] — Skills 兼容运行时标准
- [[web-pack]] — 网页素材包概念
- [[pkb-web-pack]] — PKB web_pack.py v3 实现
- [[raw-layer]] — Raw 层概念

### ⚙️ 系统
- [COMMANDS](COMMANDS.md) — 命令手册（35+ 命令，含全局 `/ask-pkb`）
- [AGENTS](AGENTS.md) — 系统规则（Agent 读，含 Hooks 系统）
- [CLAUDE](CLAUDE.md) — 快速参考（每次会话自动加载）
- [log](log.md) — 项目级变更日志
- [[wiki/index]] — 知识级全量索引
- [[wiki/log]] — 知识级变更日志
- `.claude/hooks/` — 6 个 harness hooks（安全门控 + 健康检查 + 路由 + 错误恢复）

### 🛠 核心工具
- `tools/web_pack.py` — 网页完整采集 v3.1（readability + Playwright DOM/Network + yt-dlp + GitHub Collector）
- `tools/content_quality.py` — 正文质量评分
- `tools/playwright_renderer.py` — Playwright DOM 渲染 fallback
- `tools/network_capture.py` — XHR/Fetch 网络响应捕获
- `tools/network_content.py` — 网络正文候选提取与去重
- `tools/selection_engine.py` — HTTP/Playwright DOM/Playwright Network 三方选择引擎
- `tools/pkb_auto.py` — 全自动入库 + 健康检查
- `tools/pkb_ingest.py` — 本地文件入库编排器（import→markitdown→cache→wiki）
- `tools/markitdown_convert.py` — 本地文档→MD 预提取引擎（PDF/DOCX/PPTX/XLSX/XLS）
- `tools/docs_update.py` — 项目文档自动更新
- `tools/cnki_setup.py` — CNKI 基础设施一键诊断 + 自动修复（安装完整 PKB 后可用）
- `tools/launch_chrome.ps1` — Chrome 远程调试智能启动器
- `tools/scihub_fetch.py` — 论文获取（scansci-pdf 多源并行 → Sci-Hub fallback）
- `tools/scansci_bridge.py` — 🆕 scansci-pdf 桥接层（多源赛马下载/搜索/健康检查）
- `tools/setup_beauty_stack.py` — 美化技术栈一键安装（安装完整 PKB 后可用）
- `tools/import_to_inbox.py` — 文件导入 inbox
- `tools/scholarly_enrich.py` — 学术元数据增强 CLI
- `tools/filter_literature.py` — 结构化文献筛选器
- `tools/import_journal_rankings.py` — 期刊目录导入（CSSCI/北大核心/AMI/CSCD）
- `tools/pkb_doctor.py` — 运行时诊断（18 项检查）
- `tools/pkb_task.py` — 活动任务状态管理
- `tools/check_collectors.py` — 采集器健康检查
- `tools/zskill_bridge.py` — Z-Skills 兼容桥接层

### 🚀 扩展工具（`/install` 可选安装）
- `tools/pkb_retrieve.py` — 🆕 混合检索引擎（BM25 + 向量 RRF + Cross-encoder）
- `tools/cnki_batch_download.py` — CNKI 批量下载协调器（MCP 驱动）
- `tools/cnki_webvpn.py` — CNKI WebVPN 代理访问
- `tools/batch_english_papers.py` — 批量英文论文元数据查询

---

*由 PKB 系统维护。最后更新: 2026-06-24 (v0.6.14 / web_pack v3.1 / scansci_bridge v1.0)*
