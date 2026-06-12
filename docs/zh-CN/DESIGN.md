# PKB Starter -- 架构设计

语言：[English](../DESIGN.md) | [简体中文](DESIGN.md)

## 设计哲学

PKB 基于 Andrej Karpathy 的 **LLM Wiki** 概念：一个编译式知识库，由 LLM 承担组织、链接和维护知识的繁重工作。你负责丢入东西，系统负责结构化。

### 核心洞察

传统个人知识管理需要人类：
1. 决定文件存放位置
2. 撰写摘要和笔记
3. 创建概念之间的链接
4. 随时间推移维护一致性

PKB 颠覆了这一点：**人类提供原始材料**（文件、URL、笔记），**LLM 维护结构**。这使得知识采集几乎零成本。

## 三层架构

```
+----------------------------------------------+
|  第三层：skills/                              |
|  Agent 自动化规则                             |
|  "如何维护知识库"                             |
+----------------------------------------------+
|  第二层：wiki/                                |
|  LLM 维护的结构化知识                         |
|  Markdown + [[wikilink]] + frontmatter        |
+----------------------------------------------+
|  第一层：raw/                                 |
|  不可变原始资料                               |
|  只增不删，永不修改                           |
+----------------------------------------------+
```

### 第一层：`raw/` — 不可变档案

原始资料入库后**永不修改**。这保留了来源追溯性，并在 LLM 能力提升时支持重新处理。

| 子目录 | 内容 |
|--------|------|
| `webpacks/` | 结构化网页采集（页面 + 图片 + 元数据） |
| `papers/` | 学术论文（PDF） |
| `imported_processed/` | 从 `_INBOX` 转移的已处理文件 |
| `clippings/` | 剪贴板快速剪辑 |
| `personal/` | 私人笔记和参考资料 |

### 第二层：`wiki/` — 活知识

LLM 维护的 Markdown 页面，包含：
- **YAML frontmatter**：`created`、`updated`、`tags`、`type`、`source_path`
- **`[[wikilink]]`** 页面间连接
- **原子化概念**：一个概念一页
- **来源追溯**：每个概念都可追溯到原始资料

| 子目录 | 用途 |
|--------|------|
| `concepts/` | 原子化概念笔记 |
| `sources/` | 知识来源索引 |
| `projects/` | 项目专用页面 |
| `outputs/` | 生成的文章、报告 |

### 第三层：`skills/` — Agent 规则

自动化整个流程的 Claude Code 技能：
- **pkb-auto**：全自动入库
- **pkb-web-pack**：网页内容采集
- **pkb-inbox**：原始资料 -> Wiki 编译
- **pkb-ask**：知识库查询
- **pkb-sanitize**：隐私扫描
- **pkb-lint**：健康检查
- **pkb-init**：新建 PKB 设置

## 自动入库流程

```
用户: /pkb <任何东西>
         |
         +-- 文件？ --> 复制到 _INBOX
         +-- URL？ --> web_pack.py -> raw/webpacks/
         +-- 文本？ --> 搜索 wiki，返回答案
              |
    +---------+----------+
    |  自动入库           |
    |  - 提取内容         |
    |  - 分类类型         |
    |  - 创建 wiki        |
    |  - 更新索引         |
    +---------+----------+
              |
    +---------+----------+
    |  自动归档           |
    |  - INBOX -> raw/    |
    |  - 修正 source_path |
    +---------+----------+
              |
    +---------+----------+
    |  健康检查           |
    |  - 断链？           |
    |  - 缺少元数据？     |
    |  - 敏感信息？       |
    +---------+----------+
              |
         Git 提交
              |
         报告
```

## 关键设计决策

### 1. raw/ 只增不删
文件从不从 raw/ 删除。即使导入了错误的内容，它也会保留——在元数据中标记即可。这防止了意外数据丢失并保留了来源追溯。

### 2. LLM 作为主要维护者
人类可以编辑 wiki 页面，但 LLM 是主要作者。这意味着：
- 一致的格式和链接
- 自动交叉引用
- 新鲜度跟踪

### 3. 默认全自动
`/pkb <任何东西>` 从不询问"下一步？"——它执行完整流程并在最后报告。这是关键洞察：如果 LLM 是维护者，就不要在人类决策上阻塞。

### 4. Git 原生
每次变更即一次 git 提交。你可以使用标准 git 工作流进行回滚、分支和协作。知识库本身就是一个 git 仓库。

### 5. Obsidian 兼容
`wiki/` 目录结构和 `[[wikilink]]` 语法完全兼容 Obsidian。将 `wiki/` 作为 Obsidian vault 打开即可进行可视化图谱浏览。

### 6. 可选技能架构

PKB 的技能系统遵循 **注册表 + 适配器** 模式，编目整个 PKB 生态。技能可以在初始设置时或之后随时通过运行时技能管理器安装。

```
skills_registry/           pkb-starter（目录，不捆绑）
  skill_catalog.json       43 个目录条目，包含完整元数据
  profiles.json            9 个预设配置（core/student/.../custom）

scripts/
  install.py               一次性安装器（设置时）
  install_skills.py        技能安装器（设置时，旧版）
  skill_manager.py         运行时技能管理器（随时可用）[NEW v0.4.0]

skills/_vendor/            目标 PKB（按需安装）
  obsidian-skills/         通过 git 克隆，永不自启
  agent-research-skills/   31 个子技能，选择性激活
  deep-research-skills/    5 个子技能，纯 prompt（安全）
  ...

template/skill_adapters/   pkb-starter（路由规则）
  <adapter>.md             将技能输出映射到 raw/wiki 路径

template/.claude/commands/
  skills.md                /project:skills 命令（随时管理）
```

核心原则：
- **目录驱动**：43 个条目覆盖 9 个独立外部仓库。从真实 PKB 安装中提取。
- **不捆绑**：技能从各自仓库克隆，不从 pkb-starter 复制。
- **适配器模式**：每个技能有一个 markdown 适配器，告诉 LLM 将输出路由到何处。
- **风险分类**：low（自动安装，28 个技能）、medium（警告，10 个技能）、high（需要明确确认，5 个技能）、reference_only（永不安装，0 个技能）。
- **不自动执行**：安装 = `git clone --depth 1`。在你于 Claude Code 中调用技能之前，没有任何代码运行。
- **渐进式采用**：从 Core（0 外部）开始。随时通过 `/project:skills --install-profile <name>` 或 `skill_manager.py` 添加。
- **明确激活**：安装 -> 审计 -> 启用 是一个三步流程。仅安装不会激活技能。
- **来源多样性**：external_repo（24 个条目来自 9 个仓库）、local_template（10）、plugin_marketplace（2）、mcp_server（1）、adapter_only（1）、built_in（5）。
- **Z-skills 兼容**：用户授权本地安装，需明确同意。PKB 不分发 z-skills 代码。桥接（zskill_bridge.py）处理定位、审计、运行、导入输出和补丁。

### 6.1 运行时技能管理

技能管理器（`scripts/skill_manager.py` 和 `/project:skills`）在实时 PKB 安装上工作：

- **Status**：显示已安装、已启用、已禁用、待审计的技能
- **List**：包含说明和风险等级的完整目录
- **Describe**：任何技能的详细视图（是什么、为什么、风险、如何安装）
- **Install**：单个技能或整个配置预设，支持 dry-run
- **Audit**：LICENSE 检查、.git 验证、适配器状态
- **Enable/Disable**：切换状态而不删除源代码
- **Update catalog**：刷新本地目录版本

每个技能在安装前都展示其说明、风险解释、适用/不适用场景指导以及环境要求（API key、MCP、外部运行时）。高风险技能需要明确的用户确认。

### 6.2 Z-Skills 兼容模块

PKB Starter 包含一个用于可选 z-skills 集成的桥接模块：

- **不二次分发代码**：PKB 不捆绑、不复制、不二次分发 z-skills 源代码。
- **用户明确选择加入**：安装 z-skills 需要阅读风险后输入 'INSTALL'。
- **桥接架构**：`zskill_bridge.py` 处理定位、审计、状态、运行、导入输出和补丁。
- **三阶段生命周期**：安装（用户克隆）-> 审计（LICENSE 检查）-> 启用（激活适配器）。
- **默认采集器不变**：PKB 内置 web_pack 是默认。z-web-pack 为选择加入。
- **仅本地补丁**：补丁需要 `--allow-local-patch`，存储在 `.pkb_local/patches/`（已被 gitignore）。

详见 [Z_WEB_PACK_PARITY.md](Z_WEB_PACK_PARITY.md) 了解完整功能对比和架构。

## 工具

| 工具 | 用途 |
|------|------|
| `web_pack.py` | 带图片/媒体管道的结构化网页采集 |
| `import_to_inbox.py` | 带敏感数据检测的文件导入 |
| `pkb_auto.py` | 健康检查和自动流程编排 |
| `docs_update.py` | 项目文档新鲜度检查器 |
| `sanitize.py` | 带模式检测的隐私扫描 |
| `update_pkb.py` | 版本迁移和系统文件更新 |

## 版本管理与迁移

### 版本追踪

每个 PKB 安装通过 `pkb.config.json` 追踪其 pkb-starter 来源：

```json
{
  "starter_version": "0.5.0",
  "schema_version": "0.5.0",
  "created_at": "2026-06-12T00:00:00Z",
  "last_updated_at": "2026-06-12T12:00:00Z",
  "skills": { ... }
}
```

### 迁移架构

```
已安装 PKB（v0.3.0）            pkb-starter（当前）
========================        ====================
pkb.config.json                  scripts/update_pkb.py
  starter_version: 0.3.0 ------> 检测版本差距
                                  migrations/
                                    0.3.0_to_0.4.0.py
                                    0.4.0_to_0.5.0.py
                                    （增量运行两者）

                                  结果：
                                    pkb.config.json
                                      starter_version: 0.5.0
```

### 安全更新流程

1. **检测** 从 `pkb.config.json > starter_version` 读取已安装版本
2. **备份** 系统文件到 `.pkb_backup/YYYYMMDD_HHMMSS/`
3. **迁移** 运行增量迁移脚本
4. **更新** 从模板复制新系统文件
5. **合并** 更新配置文件中的版本字段（保留用户设置）
6. **报告** 写入 `update_report.md`

### 受保护数据

更新过程有严格边界：

| 受保护（永不触碰） | 更新（仅系统文件） |
|-------------------|-------------------|
| `raw/` | `tools/` |
| `wiki/` | `.claude/commands/` |
| `_INBOX/` | `skill_adapters/` |
| `skills/_vendor/` | `skills_registry/` |
| `pkb.config.json` 设置 | `pkb.config.json` 版本字段 |
| `.pkb_local/` | `COMMANDS.md` |

### 同步流程（维护者）

私有 PKB 通过受控管道将脱敏后的系统文件同步到 pkb-starter：

```
私有 PKB --[脱敏 + 许可证检查]--> pkb-starter/template/
```

只有 `starter_sync_manifest.json` 中列出的文件才有资格同步。个人路径、邮箱和敏感模式在文件到达公共仓库前被替换为占位符。

[完整更新文档 ->](UPDATING.md)
