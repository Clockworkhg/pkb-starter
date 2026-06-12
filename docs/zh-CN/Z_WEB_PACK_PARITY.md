# PKB web_pack -- Z-Web-Pack 功能对比

> PKB 内置 web_pack 采集器与 z-web-pack（tjxj/z-skills）的功能对比，以及 z-skills 兼容模块文档。

语言：[English](../Z_WEB_PACK_PARITY.md) | [简体中文](Z_WEB_PACK_PARITY.md)

## 两种采集器

PKB 提供两种网页采集后端：

| | PKB 基础 web_pack | Z-Web-Pack（通过 z-skills） |
|---|---|---|
| **状态** | 内置，始终可用 | 可选，用户本地安装 |
| **分发** | 捆绑在 PKB Starter 中（MIT） | PKB 不分发 |
| **安装** | 包含在模板中 | 用户从 tjxj/z-skills 克隆 |
| **许可证** | MIT（PKB 项目） | 按目录分别授权，需审计 |
| **默认** | 是 | 否（明确选择加入） |
| **激活** | 始终激活 | 安装 -> 审计 -> 启用 |

## v0.1.0 状态：基础采集器（PKB 内置）

v0.1.0 版本内置了基础网页采集器，覆盖：

| 功能 | 状态 |
|------|------|
| 单个 URL 采集 | [OK] |
| 多个 URL 采集 | [OK] |
| 内容提取（requests + BS4） | [OK] |
| Markdown 转换（markdownify） | [OK] |
| 标题/正文/链接/图片提取 | [OK] |
| GitHub blob/raw URL 处理 | [OK] |
| 标准输出结构 | [OK] |
| README.md + manifest.json | [OK] |
| 01-link-inventory.md | [OK] |
| 02-image-inventory.md | [OK] |
| 03-reading-map.md | [OK] |
| 04-media-inventory.md | [OK] |

## 功能对比

| 功能 | PKB 基础 web_pack | z-web-pack |
|------|-------------------|------------|
| 公开网页采集 | 是 | 是 |
| Readability 内容提取 | 是（readability-lxml + trafilatura） | 是 |
| BeautifulSoup 回退 | 是 | 是 |
| Markdown 转换 | 是（markdownify） | 是 |
| 结构化 webpack 输出 | 是 | 是 |
| README + manifest | 是 | 是 |
| 链接清单 | 是 | 是 |
| 图片清单 | 基础 | 高级（srcset、magic bytes） |
| 阅读地图 | 是 | 是 |
| 媒体清单 | 基础 | 高级 |
| 图片下载 | 基础 | 高级（SHA256 去重、Referer） |
| 图片 srcset / picture 处理 | v0.2 计划 | 是 |
| Magic bytes 检测 | v0.2 计划 | 是 |
| 视频 / yt-dlp 集成 | 不计划 | 是 |
| 浏览器 cookie 支持 | 不包含 | 选择加入 |
| GitHub 采集 | 是（API + git clone） | 是 |
| 微信公众号文章处理 | 是（max-depth 0） | 未知 |
| 多层爬取 | 基础 | 高级 |
| Jina Reader 回退 | v0.2 计划 | 未知 |
| 跟踪像素/网站图标过滤 | v0.2 计划 | 是 |

## v0.2 路线图（PKB 内置）

1. 懒加载图片属性支持（data-src、data-original 等）
2. 下载资源去重
3. GitHub API + git clone depth-1 回退链
4. 内容质量启发式（弱内容检测）
5. 可选媒体下载（选择加入，不含 cookie 处理）

所有 v0.2 功能将独立实现，不参考 z-web-pack 代码。

## 输出结构兼容性

PKB web_pack 为基础采集生成与 z-web-pack 相同的输出文件结构：

```
raw/webpacks/<YYYY-MM-DD>-<topic>/
  README.md
  manifest.json
  01-link-inventory.md
  02-image-inventory.md
  03-reading-map.md
  04-media-inventory.md
  MAIN-<topic>.md
  snapshots/
    <page>.md
  assets/
```

这种结构兼容性意味着无论使用哪个采集器生成 webpack，wiki 入库脚本的工作方式完全相同。

---

## Z-Skills 兼容模块（v0.4.1）

### 它是什么

一个桥接模块，允许 PKB 用户可选地在本地安装 z-skills，并将 z-web-pack 作为替代采集后端使用。

### 它不是什么

- 不是对 z-skills 代码的二次分发
- 不是对 z-skills 源代码的修改
- 不是对 PKB 内置 web_pack 的替代
- 不是依赖或必要条件
- 不是默认启用的

### 架构

```
用户操作                          PKB / Z-Skills 状态
--------                          ------------------
/project:skills --install
  z-skills                ------> git clone tjxj/z-skills
                                   -> skills/_vendor/z-skills/
                                   -> 状态：pending_audit
                                   -> 不自动启用

/project:skills --audit   ------> zskill_bridge.py audit
                                   -> 检查 LICENSE 文件
                                   -> 生成 zskill_audit_report.md

/project:skills --enable
  z-web-pack-local        ------> 启用 z_skills_adapter.md
                                   -> z-web-pack 现在可选
                                   -> 不修改 z-skills 代码

/project:web --collector
  z-web-pack <url>        ------> zskill_bridge.py run
                                   -> 调用 z-web-pack
                                   -> import-output 到 raw/webpacks/
                                   -> 后续 wiki 流程相同
```

### 涉及的文件

| 文件 | 位置 | 用途 |
|------|------|------|
| `z_skills_adapter.md` | `template/skill_adapters/` | 适配器路由规则 |
| `zskill_bridge.py` | `template/tools/` | 桥接：定位、审计、运行、导入 |
| `skill_catalog.json` | `skills_registry/` | z-skills + z-web-pack-local 条目 |
| `skills.md` | `template/.claude/commands/` | /project:skills z-skills 流程 |
| `web.md` | `template/.claude/commands/` | --collector z-web-pack 选项 |
| `pkb.md` | `template/.claude/commands/` | --collector z-web-pack 选项 |
| `.gitignore` | `template/` | skills/_vendor/、.pkb_local/、报告文件 |

### 不含 Z-Skills 代码

PKB Starter 包含零行 z-skills 代码。桥接模块：

- 阅读 `SKILL.md` 以理解 z-web-pack 的接口（仅概念参考）
- 通过 Claude Code 技能调用（而非直接脚本执行）来调用 z-web-pack
- 将 z-web-pack 输出从其输出目录复制到 PKB 的 `raw/webpacks/`

### 安全规则

1. **不二次分发代码**：PKB Starter 不包含、不复制、不捆绑 z-skills 源代码。
2. **用户明确选择加入**：安装 z-skills 需要在阅读风险说明后输入 'INSTALL'。
3. **审计后启用**：z-skills 克隆后进入 `pending_audit`。必须通过审计才能启用 `z-web-pack-local`。
4. **不自动执行**：桥接模块不自动执行 z-skills 脚本。
5. **不默认打补丁**：不修改 z-skills 源代码。不兼容问题通过包装器、配置或输出重定位解决。
6. **仅限本地补丁（万不得已时）**：需要 `--allow-local-patch`。存储在 `.pkb_local/patches/`（已被 gitignore）。不提交、不分发。
7. **输出隔离**：z-web-pack 输出到 `raw/webpacks/`（与 PKB 内置采集器相同）。
8. **默认采集器不变**：基本 web_pack 保持默认。z-web-pack 为选择加入。

### 为什么不默认使用 Z-Web-Pack

1. **许可证**：z-skills 采用按目录许可。PKB Starter 不能假设有分发权限。
2. **用户选择**：用户应自行决定哪些第三方代码在自己的机器上运行。
3. **简洁性**：PKB 内置采集器零配置即可处理 90% 以上的常见用例。
4. **独立性**：PKB 采集器可以按自己的路线图演进，无需外部依赖。
5. **安全**：对第三方代码而言，先用后审是更安全的默认设置。

### 采集器选择指南

| 场景 | 推荐采集器 |
|------|-----------|
| 快速保存文章 | PKB 基础 web_pack |
| 研究论文采集 | PKB 基础 web_pack |
| GitHub README/文档 | PKB 基础 web_pack |
| 微信公众号文章 | PKB 基础 web_pack |
| 重度图片网站（需要 srcset） | z-web-pack |
| 视频页面归档 | z-web-pack |
| 多层深度爬取 | z-web-pack |
| 并排对比 | 两者都用 |

### 默认路径

**默认始终是 PKB 基础 web_pack**。它无需任何设置即可使用。z-web-pack 适用于需要其高级功能并愿意手动安装、审计和启用的用户。

---

## 法律说明

z-web-pack 是 tjxj 在 z-skills 仓库中的 Claude Code 技能。PKB Starter 不包含、不派生、不二次分发 z-web-pack 或 z-skills 代码。需要 z-web-pack 完整功能的用户应直接从 https://github.com/tjxj/z-skills 安装，并遵守其许可条款。

PKB 的 web_pack.py 是一个独立的清洁室实现，其功能设计受到 z-web-pack 已记录输出结构的启发。PKB 的实现未使用任何 z-web-pack 代码、常量、正则表达式、注释或脚本。

---

*PKB Starter v0.4.1。更新日期：2026-06-12。*
