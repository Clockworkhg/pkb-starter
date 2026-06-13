# CLAUDE.md — PKB 快速参考

> 每次 Claude Code 会话自动加载。详细规则见 [AGENTS.md](AGENTS.md)。

## 项目身份

**PKB** = 编译式个人知识库，遵循 Karpathy LLM Wiki 模式。
三层架构：`raw/`（不可变原始资料） → `wiki/`（LLM 维护的结构化知识） → `skills/`（Agent 自动化规则）。
项目版本：`v0.6.8-alpha` | 组件：`web_pack v3.1`。公开模板：[pkb-starter](https://github.com/Clockworkhg/pkb-starter)。

## 关键路径

```
raw/webpacks/        网页素材包（web_pack.py v3.1 产出，Playwright 动态渲染）
raw/papers/          论文 PDF + manifest.json
.pkb-cache/          文档转换缓存（MarkItDown 预提取）
wiki/concepts/       原子化概念笔记
wiki/sources/        知识来源索引（含文献地图）
wiki/projects/       项目笔记
.claude/skills/      Agent Skills（39+）
.claude/commands/    Slash Commands（35+）
.claude/hooks/       Harness Hooks（6 个自动化钩子）
tools/               Python 工具脚本（10+）
```

## Skill 路由速查

| 用户意图 | 调用 |
|---------|------|
| 丢任何东西入库 | `/pkb <anything>` |
| 知网论文搜索/下载 | `/pkb-cnki search\|fill-gaps\|download` |
| 学术研究（论文/综述/引用） | `/research` `/paper` `/literature-*` |
| 文档格式转换 | `/doc` `/ocr` |
| Excel/Markdown 表格 | `/z-excel-editor` `/z-md-excel` |
| 隐私清理 | `/sanitize` |
| 看板管理 | `/kanban` |
| 代码审查/简化 | `/simplify` |
| 创建新 Skill | `/make-skill` |

## 编码约定

- **Wiki 页面**: YAML frontmatter 必须含 `created`/`updated`/`tags`/`type`
- **双链**: wiki 内用 `[[wikilink]]`，跨层用 Markdown 链接
- **raw/ 不可变**: 只增不删，元数据在 manifest.json
- **Python 工具**: `encoding='utf-8', errors='replace'`（Windows 兼容）
- **PowerShell**: 用 cmdlet 不用 bash 语法；`shell=True` 跑外部命令
- **Git commit**: 格式 `[PKB] <domain>: <summary>`

## 工具速查

| 工具 | 用途 |
|------|------|
| `tools/web_pack.py` | 网页完整采集 v3.1（readability + Playwright DOM + Network + yt-dlp + GitHub Collector） |
| `tools/content_quality.py` | 正文质量评分（Playwright 动态渲染触发判定） |
| `tools/playwright_renderer.py` | Playwright DOM 渲染 fallback（Chromium 浏览器自动化） |
| `tools/network_capture.py` | XHR/Fetch 网络响应捕获 |
| `tools/network_content.py` | 网络正文候选提取 + 去重 |
| `tools/selection_engine.py` | HTTP / Playwright DOM / Playwright Network 三方选择 |
| `tools/pkb_auto.py` | 全自动入库 + 健康检查 |
| `tools/pkb_ingest.py` | 本地文件入库编排器（import→markitdown→cache→wiki，正文在 .pkb-cache/）（Phase 1.5） |
| `tools/markitdown_convert.py` | 本地文档→MD 预提取引擎（PDF/DOCX/PPTX/XLSX/XLS，动态版本）（Phase 1.5） |
| `tools/docs_update.py` | 文档新鲜度检测（`--json`/`--summary`） |
| `tools/cnki_setup.py` | CNKI 基础设施一键诊断 + 修复 |
| `tools/download_papers.py` | 批量论文下载协调器 |
| `tools/download_papers_r2.py` | R2 学术源论文下载 |
| `tools/download_papers_r3.py` | R3 学术源论文下载 |
| `tools/scihub_fetch.py` | Sci-Hub 论文获取 |
| `tools/scholarly_enrich.py` | 学术元数据增强 CLI（DOI 查询 + 批量扫描 + 写入）（Phase 1B） |
| `tools/filter_literature.py` | 结构化文献筛选器（按期刊等级/年份/被引/DOI 过滤）（Phase 1B） |
| `tools/import_journal_rankings.py` | 期刊目录导入（CSSCI/北大核心/AMI/CSCD/自定义） |
| `tools/import_to_inbox.py` | 文件导入 _INBOX |
| `tools/sync_to_starter.py` | PKB → pkb-starter 系统同步（dev-only） |

## Hooks 速查

| Hook | 触发 | 功能 |
|------|------|------|
| `01_session_start` | SessionStart | 环境验证 + 上下文卡片 + 文档新鲜度 |
| `02_pre_tool_use` | PreToolUse | 🛡️ 安全门控（拦截 secret commit / raw 删除 / 敏感文件写入） |
| `03_post_tool_use` | PostToolUse (Write\|Edit) | wiki 快速 frontmatter 检查 + commit 后全量健康检查 |
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

### CNKI 论文
```
python tools/cnki_setup.py --fix     # 一次性安装
powershell tools/launch_chrome.ps1   # 启动 Chrome 调试
/pkb-cnki fill-gaps                  # 补齐缺失 PDF
```
⚠️ 需 Chrome DevTools MCP 连接 + 知网登录。MCP 仅会话启动时加载。

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

*与 [AGENTS.md](AGENTS.md) 保持同步。最后更新: 2026-06-13 (web_pack v3.1 / Scholarly Phase 1B.2)*
