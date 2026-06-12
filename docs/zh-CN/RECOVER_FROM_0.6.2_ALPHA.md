# 从 v0.6.2-alpha 文档新鲜度问题中恢复

> 如果你安装了 v0.6.2-alpha 并看到过期文档警告，本指南适合你。

语言：[English](../RECOVER_FROM_0.6.2_ALPHA.md) | [简体中文](RECOVER_FROM_0.6.2_ALPHA.md)

---

## 1. 发生了什么

v0.6.2-alpha 发布时存在几个影响新安装的文档问题：

- **新装即提示过期**：新知识库立即报告文档过期（最多 22 项），因为模板文件包含占位符日期（`YYYY-MM-DD`）和过期版本引用（`v0.5.0-alpha`）。
- **版本号写入错误**：`/docs-update` 命令可能错误改写版本号（例如 `v0.5.0-alpha` → `v06-12`），将日期片段与版本号混淆。
- **试图覆写受保护文件**：`/docs-update` 可能试图修改受 ARS scope guard 保护的 `CLAUDE.md` 和 `AGENTS.md`。

**这不影响你的用户数据。** `raw/`、`wiki/`、`_INBOX/`、`skills/_vendor/` 和 `.pkb_local/` 目录是安全的。

## 2. 受影响的对象

- 安装了 **v0.6.2-alpha** 的用户。
- 特别是在安装后立即运行 `/docs-update` 的用户。

使用较旧版本（v0.5.0-alpha 及更早版本）并更新到 v0.6.2-alpha 的用户同样受影响。

## 3. 千万不要做的事

- ❌ **不要删除知识库**。你的数据是安全的。
- ❌ **不要手动随意编辑系统文件**，除非你确切知道改了什么。
- ❌ **不要 force-reset**，如果你已经添加了个人笔记。
- ❌ **不要覆盖已有知识库重装**——这可能覆盖你的数据。
- ❌ **不要在 v0.6.2-alpha 上运行 `/docs-update`**——等到更新到 v0.6.3-alpha 后再运行。

## 4. 安全更新到 v0.6.3-alpha

v0.6.3-alpha 修复了所有这些问题。使用内置更新客户端：

```bash
cd "<你的知识库路径>"

# 第 1 步：预览将要更改的内容（安全，不修改任何文件）
python tools/pkb_update_client.py --checkout v0.6.3-alpha

# 第 2 步：查看报告
# 打开 update_client_report.md 检查：
#   - 计划更改中没有 raw/ 文件
#   - 计划更改中没有 wiki/ 文件
#   - 计划更改中没有 _INBOX/ 文件

# 第 3 步：应用更新
python tools/pkb_update_client.py --checkout v0.6.3-alpha --apply
```

**更新后验证：**

```bash
python tools/docs_update.py --check
```

预期输出：
- `stale count = 0`
- 当前版本不是 `v0.5.0-alpha`
- 无 `YYYY-MM-DD` 占位符
- 无格式错误的 `v06-12` 版本号
- 所有追踪文档显示 `[OK]`

## 5. 如果在 v0.6.2-alpha 上已运行 /docs-update

如果你在 v0.6.2-alpha 上运行了 `/docs-update`，文档可能包含错误的版本号或日期值。

**恢复步骤：**

1. **先 dry-run：**
   ```bash
   python tools/pkb_update_client.py --checkout v0.6.3-alpha
   ```

2. **检查更新报告：**
   - 如果 `update_client_report.md` 列出核心文档冲突，接受 v0.6.3-alpha 模板版本（除非你故意自定义了它们）。
   - 如果你在计划更改中看到个人 wiki 笔记或 raw 文件，**立即停止**并寻求帮助。

3. **应用更新：**
   ```bash
   python tools/pkb_update_client.py --checkout v0.6.3-alpha --apply
   ```

4. **验证：**
   ```bash
   python tools/docs_update.py --check
   ```

## 6. 如果更新客户端缺失或损坏

如果 `tools/pkb_update_client.py` 缺失（v0.6.2-alpha 之前安装的）或损坏：

**方案 A：使用本地 pkb-starter 克隆**

```bash
cd "<你的知识库路径>"
python tools/pkb_update_client.py --starter-path "D:\pkb-starter" --checkout v0.6.3-alpha
python tools/pkb_update_client.py --starter-path "D:\pkb-starter" --checkout v0.6.3-alpha --apply
```

**方案 B：全新安装用于对比，然后手动更新**

```bash
# 将全新 v0.6.3-alpha 安装到临时目录用于对比
git clone https://github.com/pkb-starter/pkb-starter.git D:\pkb-starter-temp
cd D:\pkb-starter-temp
git checkout v0.6.3-alpha
python scripts/install.py E:\pkb-fresh-063 --force

# 对比新安装和你的知识库之间的系统文件
# 仅手动复制需要更新的系统模板文件
```

## 7. 更新后验证

运行所有检查：

```bash
cd "<你的知识库路径>"

# 文档新鲜度
python tools/docs_update.py --check
# 预期：stale count = 0

# 检查配置中的版本
python -c "import json; c=json.load(open('pkb.config.json', encoding='utf-8')); print(c.get('starter_version'))"
# 预期：v0.6.3-alpha

# 检查文档中没有格式错误的版本
python -c "import re, pathlib; [print(f'{f.name}: v06-12') for f in pathlib.Path('.').glob('*.md') if 'v06-12' in f.read_text(encoding='utf-8')]"
# 预期：无输出
```

## 8. 何时寻求帮助

如遇以下情况，请联系 pkb-starter 维护者：

- 更新报告列出**你未自定义的核心文件冲突**
- **用户数据**（raw/、wiki/）出现在计划更改中
- `git status` 显示**意外的删除**
- 更新后无法解决冲突

---

*本指南适用于 v0.6.2-alpha → v0.6.3-alpha 迁移。如需一般更新信息，请参见 [UPDATING.md](../UPDATING.md)。*
