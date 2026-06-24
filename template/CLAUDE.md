# CLAUDE.md — PKB 快速参考

> 每次 Claude Code 会话自动加载。详细规则见 [AGENTS.md](AGENTS.md)。

## 项目身份

**PKB** = 编译式个人知识库，遵循 Karpathy LLM Wiki 模式。
三层架构：`raw/`（不可变原始资料） → `wiki/`（LLM 维护的结构化知识） → `skills/`（Agent 自动化规则）。
**公开模板版本：`v0.6.14-starter`**（基于 PKB v0.6.14-alpha）| 内置：全局知识库查询 `/ask-pkb` + 对话捕获 `/pkb-capture`。上游项目：[PKB](https://github.com/Clockworkhg/pkb-starter)。

## 关键路径

```
.mcp.json            项目 MCP 配置（chrome-devtools，Claude Code 标准位置）
pkb.ps1              统一启动器（PKB 项目级，clone 完整 PKB 后可用）
raw/                 原始资料（不可变，只增不删）
wiki/                LLM 维护的结构化知识
.claude/skills/      Agent Skills（2 built-in：ask-pkb + pkb-capture，可扩展至 39+）
.claude/commands/    Slash Commands
.claude/hooks/       Harness Hooks（6 个自动化钩子）
tools/               Python 工具脚本
.pkb-cache/          文档转换缓存（MarkItDown 预提取）
.pkb-local/          本地运行时状态（不提交）
```

## 自动 Skill 检测规则

> ⚠️ **最高优先级**：收到用户输入后，必须先检查 Skill 路由表，匹配则立即调用对应 Skill。
> 不要直接回答问题 — 优先使用 Skill 工具。详细路由规则见 [AGENTS.md](AGENTS.md)。

## Skill 路由速查

### 核心（built-in 可用）
| 用户意图 | 调用 |
|---------|------|
| 全局知识库查询 | `/ask-pkb`（任意窗口可用） |
| 全局对话捕获 | `/pkb-capture`（任意窗口可用） |
| 丢任何东西入库 | `/pkb <anything>` |
| 网页采集 | `/web <url>` |
| 本地文件导入 | `/pkb <path>` |

### 学术研究（安装完整 PKB skill set 后可用）
| 用户意图 | 调用 |
|---------|------|
| 英文论文多源下载 | `python tools/scansci_bridge.py download <DOI>` |
| 学术研究（论文/综述/引用） | `/research` `/paper` `/literature-*` |
| 文献搜索/综述 | `/literature-search` `/literature-review` |
| 知网论文 | `/pkb-cnki`（需 Chrome MCP + 知网登录） |

### 工具与格式（安装后可用）
| 用户意图 | 调用 |
|---------|------|
| 文档格式转换 | `/doc` `/ocr` |
| 隐私清理 | `/sanitize` |
| 看板管理 | `/kanban` |
| 文档更新 | `/docs-update` |
| 保存/提交 | `/save` |

## 编码约定

- **Wiki 页面**: YAML frontmatter 必须含 `created`/`updated`/`tags`/`type`
- **双链**: wiki 内用 `[[wikilink]]`，跨层用 Markdown 链接
- **raw/ 不可变**: 只增不删，元数据在 manifest.json
- **Python 工具**: `encoding='utf-8', errors='replace'`（Windows 兼容）
- **PowerShell**: 用 cmdlet 不用 bash 语法；`shell=True` 跑外部命令
- **Git commit**: 格式 `[PKB] <domain>: <summary>`

## 工具速查

### 内置工具（模板自带）
| 工具 | 用途 |
|------|------|
| `tools/pkb_bridge.py` | 🆕 全局桥接引擎 v1.0（跨项目 capture/query/status/install） |
| `tools/pkb_auto.py` | 全自动入库 + 健康检查 |
| `tools/pkb_ingest.py` | 本地文件入库编排器（import→markitdown→cache→wiki） |
| `tools/markitdown_convert.py` | 本地文档→MD 预提取引擎（PDF/DOCX/PPTX/XLSX/XLS） |
| `tools/web_pack.py` | 网页完整采集 v3.1（readability + Playwright DOM + Network + yt-dlp） |
| `tools/scansci_bridge.py` | 🆕 scansci-pdf 桥接层（download/search/--check，多源赛马） |
| `tools/scihub_fetch.py` | 论文获取（scansci-pdf 13源并行 → Sci-Hub fallback） |
| `tools/pkb_retrieve.py` | 🆕 混合检索引擎（BM25 + 向量 RRF + Cross-encoder） |
| `tools/pkb_task.py` | 活动任务状态管理（show/start/update/block/complete/clear） |
| `tools/pkb_doctor.py` | 运行时诊断（18 项 PASS/WARN/FAIL/SKIP 检查） |
| `tools/docs_update.py` | 文档新鲜度检测 |
| `tools/scholarly_enrich.py` | 学术元数据增强 CLI（DOI 查询 + 批量扫描 + 写入） |
| `tools/filter_literature.py` | 结构化文献筛选器（按期刊等级/年份/被引/DOI 过滤） |
| `tools/import_journal_rankings.py` | 期刊目录导入（CSSCI/北大核心/AMI/CSCD/自定义） |
| `tools/import_to_inbox.py` | 文件导入 _INBOX |

### 可选扩展（安装完整 PKB 后可用）
| 工具 | 用途 |
|------|------|
| `tools/cnki_setup.py` | CNKI 基础设施一键诊断 + 修复 |
| `tools/batch_english_papers.py` | 批量英文论文元数据查询 |
| `tools/cnki_batch_download.py` | CNKI 批量下载协调器（MCP 驱动） |
| `tools/cnki_webvpn.py` | CNKI WebVPN 代理访问 |
| `tools/setup_beauty_stack.py` | 美化技术栈一键安装 |
| `tools/content_quality.py` | 正文质量评分 |
| `tools/playwright_renderer.py` | Playwright DOM 渲染 fallback |
| `tools/network_capture.py` | XHR/Fetch 网络响应捕获 |
| `tools/selection_engine.py` | HTTP / Playwright DOM / Playwright Network 三方选择 |

## Hooks 速查

| Hook | 触发 | 功能 |
|------|------|------|
| `01_session_start` | SessionStart | 环境验证 + 上下文卡片 + 文档新鲜度 |
| `02_pre_tool_use` | PreToolUse | 🛡️ 安全门控（拦截 secret commit / raw 删除 / 敏感文件写入） |
| `03_post_tool_use` | PostToolUse (Write\|Edit) | wiki frontmatter 检查 + 检索索引自动重建（30s冷却） + commit 后全量健康检查 |
| `04_post_tool_use_failure` | PostToolUseFailure | 错误分类（11 类）+ 恢复建议 |
| `05_stop` | Stop | 未提交提醒 + INBOX 过期预警 + 会话摘要 |
| `06_user_prompt_submit` | UserPromptSubmit | 智能路由建议（URL/路径/CNKI/论文） |

> Hooks 由 harness 级事件驱动，不在 `/pkb` 指令中执行。配置见 `.claude/settings.json`。
> 共享库 `hook_lib.py` 提供幂等性（冷却窗口）、超时、安全扫描等基础能力。

## 常用工作流

### 自动入库（最常用）
```
/pkb <文件/URL/任何东西>
```
全自动：采集 → 编译 wiki → 归档 → 健康检查 → commit。不询问。

### 保存
```
/save "提交信息"
```
自动更新文档 → 健康检查 → commit。省略消息则自动生成。

### 文档更新
```
/docs-update
```
诊断 + 修复项目文档，不 commit。`/save` 内含此步骤。

### 英文论文下载（🆕 scansci-pdf 多源管线）
```
python tools/scansci_bridge.py download 10.1038/s41586-020-2649-2
python tools/scansci_bridge.py search "machine learning" --limit 5
python tools/scansci_bridge.py --check          # 源健康诊断
python tools/scihub_fetch.py                    # 兼容旧接口（自动走多源）
```
**架构**: scansci-pdf 13源并行赛马 → Sci-Hub 直接抓取 fallback
**策略**: `fastest`（默认）| `oa_first` | `scihub_only` | `legal_only`
**健康**: 6/6 源可达（EuropePMC/Unpaywall/SemanticScholar/OpenAlex/Crossref，CORE 偶超时）


## 行为准则

1. **默认全自动** — `/pkb` 不停顿、不询问"下一步"
2. **安全优先** — 检测到 API key/token/password/私钥 → 阻止并警告
3. **操作透明** — 每次操作给出清晰变更报告
4. **不破坏原始资料** — 不移动/删除 raw/ 中文件
5. **维护一致性** — 导入新资料后自动更新索引和日志

## 暂停条件

仅在以下情况暂停询问用户：
- 发现敏感信息（API key / token / password / 私钥 / 身份证号）
- 需要删除文件
- 文件无法解析（格式损坏或不支持）
- 同名 wiki 页面冲突且无法自动合并
- Git commit 前 secret scan 失败

---

*与 [AGENTS.md](AGENTS.md) 保持同步。最后更新: 2026-06-24 (v0.6.14-starter / pkb_bridge v1.0 / scansci_bridge v1.0)*
