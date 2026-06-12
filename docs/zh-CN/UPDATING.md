# PKB Starter -- 更新指南

> 如何更新 pkb-starter 本身，以及已安装的 PKB 用户如何更新其系统文件。

语言：[English](../UPDATING.md) | [简体中文](UPDATING.md)

## 目录

1. [面向 pkb-starter 维护者](#面向-pkb-starter-维护者)
2. [面向已安装 PKB 用户](#面向已安装-pkb-用户)
3. [什么会被更新](#什么会被更新)
4. [什么永不覆写](#什么永不覆写)
5. [备份与回滚](#备份与回滚)
6. [私有 PKB -> pkb-starter 同步](#私有-pkb---pkb-starter-同步)
7. [为什么不复制整个 PKB？](#为什么不复制整个-pkb)

---

## 面向 pkb-starter 维护者

### 从私有 PKB 同步

私有 PKB 仓库包含规范实现。变更**单向**流动：PKB -> pkb-starter。

```
私有 PKB（规范）                pkb-starter（公共模板）
=======================        =============================
AGENTS.md          ----sync----> template/AGENTS.md
COMMANDS.md        ----sync----> template/COMMANDS.md
.claude/commands/* ----sync----> template/.claude/commands/*
tools/*.py         ----sync----> template/tools/*
```

**同步方法：**

```bash
# 在私有 PKB 中：
python tools/sync_to_starter.py --target "D:\pkb-starter" --dry-run
python tools/sync_to_starter.py --target "D:\pkb-starter" --diff
python tools/sync_to_starter.py --target "D:\pkb-starter"

# 提交前检查 sync_report.md
git -C "D:\pkb-starter" diff
git -C "D:\pkb-starter" commit -am "sync from private PKB: <变更说明>"
```

**安全性**：同步工具（`starter_sync_manifest.json`）精确定义了哪些内容可以同步。其余一切被阻止。个人路径、邮箱和敏感模式自动脱敏。

### 版本历史

- **v0.5.0-alpha**：当前。添加同步/更新/迁移工作流。基线为 v0.4.1-alpha。
- **v0.4.1-alpha**：Z-Skills 兼容模块（commit 9e8d33b）。引入 `tools/zskill_bridge.py`、`skill_adapters/z_skills_adapter.md`、`docs/Z_WEB_PACK_PARITY.md` 和 skills_registry。

### 语言模板

PKB Starter v0.6.0-alpha 增加了中文（zh-CN）本地化支持。用户可以使用 `--lang zh-CN` 或 `--lang bilingual` 安装。

更新期间：

- `update_pkb.py` **不覆写**用户自定义的 README、AGENTS 或 COMMANDS 文件，无论语言如何。
- `pkb.config.json` 中的 `language`、`wiki_language`、`output_language` 字段在更新期间被保留。
- 如果后续版本新增语言模板文件，`update_pkb.py` 仅补充缺失文件——绝不强制覆写用户修改过的文档。
- 双语安装保留英文（`*.md`）和中文（`*.zh-CN.md`）两份根文档。
- Wiki 内容语言由 `pkb.config.json` 中的 `wiki_language` 控制，而非安装时使用的模板。

### 版本升级清单

1. 更新 `scripts/update_pkb.py` 中的 `CURRENT_VERSION`。
2. 在 `migrations/` 中创建新的迁移脚本。
3. 更新 `docs/UPDATING.md`（本文件）。
4. 更新 `README.md` 中的版本引用。
5. 如果系统文件变更，从私有 PKB 同步。
6. 测试：`python scripts/update_pkb.py "<测试安装>" --dry-run`。
7. 打标签并发布。

### 迁移脚本要求

`migrations/` 中的迁移脚本必须：
- 实现 `can_migrate(target)` -> bool
- 实现 `upgrade(target)` -> 变更列表
- 实现 `dry_run(target)` -> 打印将要变更的内容
- **绝不触碰** `raw/`、`wiki/`、`_INBOX/`
- 幂等（多次运行安全）
- 使用 ASCII 输出以保证 GBK 兼容

---

## 面向已安装 PKB 用户

### 检查你的版本

```bash
cat pkb.config.json | grep starter_version
```

或使用命令：

```
/project:update --dry-run
```

### 更新

```
/project:update
```

这将：
1. 检测你的当前版本。
2. 在 `.pkb_backup/` 中创建备份。
3. 运行所有待处理的迁移。
4. 更新系统文件。
5. 生成 `update_report.md`。

### 更新前预览

```
/project:update --dry-run
```

展示将要变更的确切内容，不做任何实际修改。

### 手动更新

如果你偏好手动更新：

```bash
cd D:\pkb-starter
git pull
python scripts/update_pkb.py "D:\MyKB" --dry-run
python scripts/update_pkb.py "D:\MyKB"
```

---

## 什么会被更新

| 路径 | 说明 | 是否更新？ |
|------|------|-----------|
| `tools/` | Python 辅助脚本 | **是** |
| `.claude/commands/` | Slash 命令定义 | **是** |
| `skill_adapters/` | 兼容适配器文件 | **是** |
| `skills_registry/` | 技能目录和配置预设 | **是** |
| `COMMANDS.md` | 命令参考 | **是** |
| `AGENTS.md` | 系统规则（部分） | **有条件** |
| `pkb.config.json` | 仅版本/时间字段 | **仅版本字段** |
| `CLAUDE.md` | 快速参考 | **否**（你的文件是项目本地的） |

---

## 什么永不覆写

以下目录和文件对更新过程**完全不可触碰**：

- `raw/` — 你的原始资料（网页采集、PDF、文件）
- `wiki/` — 你的知识页面（概念、来源、项目）
- `_INBOX/` — 你的待处理导入
- `skills/_vendor/` — 你安装的技能源代码（包括 z-skills vendor 目录）
- `skills/_vendor/z-skills/` — Z-skills 本地克隆，更新绝不触碰
- `.pkb_local/` — 你的本地配置
- `.pkb_local/patches/` — 你的本地补丁，绝不覆写
- `zskill_audit_report.md` — Z-skills 审计报告，绝不覆写
- `skill_manager_report.md` — 技能管理器报告，绝不覆写
- `pkb.config.json` 用户设置 — 你的偏好、配置预设、已启用技能
- `pkb.config.json` 技能状态 — `installed_profiles`、`installed_skills`、`enabled_skills`、`disabled_skills`、`vendor_downloads`、`enabled_adapters`、`pending_audit` 被保留
- 任何未明确列为系统文件的文件

### Z-Skills 状态保留

如果你安装了 z-skills 并启用了 z-web-pack-local：
- `skills/_vendor/` 在更新期间**绝不**被触碰
- `pkb.config.json` 中的 `enabled_adapters` 被保留（你的 `z-web-pack-local` 保持启用）
- `vendor_downloads` 被保留（你的 z-skills 克隆路径保持）
- `zskill_audit_report.md` 绝不覆写
- `.pkb_local/patches/` 绝不覆写

更新仅触碰 PKB 系统文件 — 绝不更新第三方 vendor 代码。

---

## 备份与回滚

### 自动备份

每次更新创建带时间戳的备份：

```
.pkb_backup/
  20260612_143052/
    tools/
    .claude/commands/
    skill_adapters/
    skills_registry/
    COMMANDS.md
    AGENTS.md
    pkb.config.json
```

### 手动备份

```
/project:update --backup-only
```

### 回滚

如果更新导致问题：

```bash
# 找到最新备份
ls .pkb_backup/

# 恢复系统文件
cp -r .pkb_backup/20260612_143052/* .

# 验证
/project:lint
```

### 基于 Git 的回滚

如果你的 PKB 使用 git（推荐）：

```bash
git diff  # 审查变更
git checkout -- tools/ .claude/commands/  # 恢复特定路径
# 或完全回滚：
git reset --hard HEAD~1
```

---

## 私有 PKB -> pkb-starter 同步

维护者的私有 PKB 是系统文件的规范来源。变更通过受控、脱敏的管道流动：

```
私有 PKB                    同步工具                      pkb-starter
=======================     =========                     =============
                             1. 读取清单
AGENTS.md                    2. 检查 never_sync            template/AGENTS.md
COMMANDS.md                  3. 脱敏（路径、邮箱）         template/COMMANDS.md
.claude/commands/pkb.md      4. 扫描敏感关键字            template/.claude/commands/pkb.md
tools/pkb_auto.py            5. 许可证检查                 template/tools/pkb_auto.py
                             6. 写入（如果安全）
                             7. 生成报告
```

### 清单控制

私有 PKB 中的 `starter_sync_manifest.json` 定义了：
- **mappings**：精确的文件到文件映射（只有这些会同步）
- **never_sync**：即使在映射中也被硬阻止的路径
- **sanitize_patterns**：个人信息 -> 占位符替换
- **license_sensitive_paths**：需要额外许可证检查的路径

### 脱敏

在任何文件到达 pkb-starter 之前：
1. 个人路径被替换（`<PRIVATE_PKB_ROOT>` -> `<PKB_ROOT>`）
2. 邮箱地址被替换（`user@example.com` -> `<USER_EMAIL>`）
3. 用户名变体被替换（`JohnDoe` -> `<USER_NAME>`）
4. 剩余的通用邮箱被捕获并替换
5. 敏感关键字（token、password、api_key）被标记

> **占位符说明**：`<PRIVATE_PKB_ROOT>` 表示维护者自己的私有 PKB 目录。`<PKB_STARTER_ROOT>` 表示公开模板仓库。普通用户不需要运行私有 PKB → starter 同步流程 — 本节仅记录维护者流水线。

### 什么不能同步

同步清单阻止：
- 全部 `raw/`（不可变原始资料）
- 全部 `wiki/`（个人知识页面）
- 全部 `_INBOX/`（待处理导入）
- `skills/_vendor/`（第三方技能代码）
- `pkb.config.json`（个人配置）
- `.env`、`.pkb_local/`（本地密钥和设置）
- `.claude/settings.json`（个人 Claude Code 设置）
- 测试目录和临时文件

---

## 为什么不复制整个 PKB？

你可能想问："为什么不把整个私有 PKB 复制到 pkb-starter？"

1. **隐私**：私有 PKB 包含你的实际知识、来源笔记、项目页面和个人材料。这些绝不应暴露。

2. **安全**：API key、token 和凭证可能存在于配置文件中。同步管道会捕获这些；批量复制不会。

3. **许可证合规**：私有 PKB 可能包含第三方技能和 vendor 代码。许可证检查防止意外再分发。

4. **版本控制**：pkb-starter 是一个模板，不是知识库。它应该干净、最小化、为新用户随时可用。

5. **可维护性**：选择性同步意味着 pkb-starter 只接收经过打磨和审查的系统文件——而非进行中的工作。

6. **关注点分离**：私有 PKB 是一个活的知识库。pkb-starter 是一个稳定的分发点。不同的仓库，不同的目的。
