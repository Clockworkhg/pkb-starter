# PKB 升级指南

## v0.6.9 → v0.6.11 迁移

### 新特性

- **`/ask-pkb` 全局知识库查询**：在任意项目中查询 PKB wiki，无需切换窗口
  - 路径检测：`PKB_ROOT` 环境变量 → 自动检测 → `~/.pkb/config.json`
  - 安装：`SKILL.md` 已内置在 `.claude/skills/ask-pkb/`，使用符号链接或复制到 `~/.claude/skills/` 即可全局使用
  - 与 `pkb.ps1` 共用 `PKB_ROOT` 环境变量约定

### 手动步骤

1. **设置环境变量**（推荐）：
   ```powershell
   # PowerShell — 添加到 $PROFILE
   $env:PKB_ROOT = "D:\你的PKB路径"
   ```
2. **或创建配置文件**：`~/.pkb/config.json` → `{"pkb_root": "D:\\你的PKB路径"}`
3. **验证**：在任意项目里 `/ask-pkb "知识库有哪些概念"`

## v0.6.7 → v0.6.9 迁移

### 新特性

- 统一启动器 `.\pkb.ps1`（`start`/`status`/`cnki`/`doctor`/`resume`）
- MCP 配置标准化到 `.mcp.json`（项目根目录）
- 活动任务状态系统（`.pkb-local/state/active-task.json`）
- 会话恢复支持（`claude --continue` + MCP 自动加载）

### 自动变更

以下变更由更新器自动处理：

| 变更 | 方式 |
|------|------|
| `.mcp.json` 创建 | NEW — 如果不存在则创建 |
| `.claude/mcp.json` | MERGE — 保留不动，工具兼容两处 |
| `.gitignore` 更新 | MERGE — 新增 `.pkb-local/` 等条目 |
| `pkb.ps1` | NEW — 统一启动器 |
| `tools/pkb_task.py` | NEW — 任务状态管理 |
| `tools/pkb_doctor.py` | NEW — 诊断工具 |
| `tools/launch_chrome.ps1` | MERGE — 更新为 PKB 专用 profile |
| Hooks 更新 | MERGE — 新增任务注入 |
| 文档 | NEW — `docs/MCP.md` 等 |

### 手动检查

更新后建议运行：

```powershell
.\pkb.ps1 doctor     # 诊断环境
.\pkb.ps1 status     # 查看状态
```

### 不兼容变更

**无**。v0.6.9 完全向后兼容。

## 系统更新时用户数据保护

PKB 更新不会覆盖以下用户数据目录：

### 受保护的目录

| 目录 | 内容 | 保护方式 |
|------|------|---------|
| `.pkb_local/scholarly/cache.sqlite3` | 学术元数据缓存 | `.gitignore` + 更新器跳过 |
| `.pkb_local/scholarly/rankings/*.csv` | 导入的期刊等级 CSV | `.gitignore` + 更新器跳过 |
| `.pkb_local/scholarly/jobs/` | 批量任务断点状态 | `.gitignore` + 更新器跳过 |
| `.pkb_local/scholarly/styles/*.csl` | 自定义引用样式 | `.gitignore` + 更新器跳过 |
| `pkb.config.json` | 用户配置（含 scholarly 配置） | 不会被覆盖 |
| `.claude/settings.local.json` | Claude Code 本地设置 | `.gitignore` |
| `wiki/` | 知识库内容 | 不含在系统更新中 |
| `raw/` | 原始资料 | 不含在系统更新中 |
| `_INBOX/` | 待处理文件 | `.gitignore` |

### 数据安全原则

1. **系统工具和用户数据分离**：`tools/` 和 `.claude/` 是系统文件，`.pkb_local/`、`wiki/`、`raw/` 是用户数据
2. **SHA-256 校验**：升级前后所有用户配置文件 SHA-256 保持不变
3. **不自动删除**：系统更新不会删除 `.pkb_local/` 下的任何用户文件

### 更新后验证

```bash
# 检查用户数据完整性
python tools/pkb_auto.py --check

# 验证学术元数据缓存
python tools/scholarly_enrich.py --cache-only --scan wiki/ --dry-run
```

## 期刊目录迁移

升级时已导入的期刊目录（`.pkb_local/scholarly/rankings/`）自动保留。

重新导入不会重复已有数据：

```bash
python tools/import_journal_rankings.py import new-data.csv  # 增量导入
python tools/import_journal_rankings.py list                  # 查看当前
```

## 故障排查

### 升级后 scholarly 模块报错

1. 确认 Python 依赖已安装：
   ```bash
   pip install -r tools/requirements-scholarly.txt
   ```

2. 检查配置：
   ```bash
   python -c "import json; c=json.load(open('pkb.config.json')); print(c.get('scholarly', {}))"
   ```

3. 运行诊断：
   ```bash
   python -m pytest tests/test_scholarly_integration.py -v
   ```

### Bun / claude-mem 故障

若 SessionStart Hook 报错 bun 或 claude-mem：
- 这些是可选的 MCP 服务，不影响核心功能
- 在 `.claude/settings.local.json` 中禁用相关 MCP 服务

### 当前不支持

- 网络首发论文（无正式卷期页码）的引用格式可能不完整
- 非期刊类型（图书、会议论文、学位论文）的 GB/T 7714 fallback 尚未金样验证
- JCR / Scopus / 中科院分区（Phase 1C 规划中）
