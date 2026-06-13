# Session Continuity & Task State

PKB v0.6.9 引入会话连续性机制，解决跨 Claude Code 会话的长任务管理问题。

## 核心概念

### 问题

过去，Claude Code 会话之间是**完全隔离**的：
- 新会话不知道上一个会话做到了哪里
- 任务进度需要用户手动复述
- MCP 连接需要手动检查和重启
- 临时交接文件可能误入 Git

### 解决方案

PKB 现在维护一个**本地任务状态**，在会话之间传递上下文：

```
.pkb-local/                  ← Git 忽略，仅本地
├── state/
│   ├── active-task.json     ← 当前活动任务
│   └── task-history/        ← 已完成任务的归档
├── chrome-profile/          ← Chrome 专用配置 + 登录态
└── logs/                    ← 运行时日志
```

## 任务状态

### 结构

```json
{
  "schema_version": 1,
  "task_id": "political-communication-cnki",
  "title": "政治传播学知网文献检索",
  "status": "active",
  "goal": "检索、筛选并下载政治传播学中文核心文献",
  "completed": [
    "完成英文文献初步检索",
    "生成中文文献初步清单"
  ],
  "next_action": "连接 Chrome DevTools MCP 后进入知网检索",
  "blocked_by": [],
  "required_capabilities": [
    "chrome-devtools"
  ],
  "artifacts": [
    "wiki/sources/lit-political-communication.md"
  ],
  "notes": [],
  "created_at": "2026-06-13T10:00:00+08:00",
  "updated_at": "2026-06-13T12:30:00+08:00"
}
```

### 状态机

```
         ┌─────────┐
         │ active  │ ← 任务进行中
         └────┬────┘
              │
    ┌─────────┼─────────┐
    │         │         │
    ▼         ▼         ▼
┌─────────┐ ┌─────────┐ ┌──────────┐
│ blocked │ │completed│ │(manually │
│         │ │         │ │ cleared) │
└─────────┘ └────┬────┘ └──────────┘
                 │
                 ▼
          ┌──────────┐
          │ archived │ → 移入 task-history/
          └──────────┘
```

### 管理命令

```powershell
# 查看当前任务
python tools/pkb_task.py show

# 创建新任务
python tools/pkb_task.py start --title "任务标题" --goal "目标" --next "下一步"

# 更新任务
python tools/pkb_task.py update --status active --next "新的下一步"
python tools/pkb_task.py update --add-completed "完成了某步骤"

# 阻塞任务（能力缺失时）
python tools/pkb_task.py block "chrome-devtools MCP unavailable"

# 完成任务（自动归档到 history）
python tools/pkb_task.py complete

# 清除任务
python tools/pkb_task.py clear
```

### 自动更新节点

Claude 只应在以下时机更新任务状态：
- 开始新任务
- 明确完成一个阶段
- 遇到阻塞
- 生成关键产物
- 会话停止前（Stop hook 自动更新时间戳）
- 用户明确切换任务
- 任务完成

**不要**在每一句对话后都写状态。

## 会话恢复

### 推荐流程

```powershell
# 1. 启动环境
.\pkb.ps1 cnki          # 启动 Chrome + 检查 MCP

# 2. 登录知网（如需要）
#    在 PKB Chrome 窗口中手动登录

# 3. 恢复会话
.\pkb.ps1 resume        # claude --continue + --mcp-config .mcp.json
```

### `.\pkb.ps1 resume` 做了什么

1. 检查是否已在 Claude Code 会话中（防止递归）
2. 显示当前活动任务（如有）
3. 检查 `.mcp.json` 是否存在
4. 检查 Chrome 调试端口
5. 执行 `claude --continue --mcp-config .mcp.json`
   - `--continue`：恢复上一个会话的对话上下文
   - `--mcp-config .mcp.json`：显式加载项目 MCP 配置

### 手动恢复

如果自动恢复不适用：

```powershell
# 显示任务（手动描述给新会话）
python tools/pkb_task.py inject

# 输出示例：
# ┌────────────────────────────────────────────────────────────┐
# │ 📋 当前活动任务                                            │
# ├────────────────────────────────────────────────────────────┤
# │ 🟢 政治传播学知网文献检索                                  │
# ├────────────────────────────────────────────────────────────┤
# │ 已完成:                                                   │
# │   ✅ 英文文献初步检索                                      │
# │ 下一步: 连接 Chrome DevTools MCP 后进入知网检索            │
# │ 必要能力: chrome-devtools                                  │
# └────────────────────────────────────────────────────────────┘
```

## SessionStart 自动注入

新会话启动时，SessionStart hook 自动：

1. 读取 `.pkb-local/state/active-task.json`
2. 如果存在且非 `completed` 状态，注入简洁上下文
3. 不注入 Cookie、账号、绝对路径等敏感信息
4. 文件不存在时静默跳过
5. 文件损坏时提示一次并备份

## 隐私保证

- ✅ `.pkb-local/` 整个目录在 `.gitignore` 中
- ✅ 任务状态仅存本地，不提交到 Git
- ✅ SessionStart 注入不含敏感信息
- ✅ Chrome profile 独立于用户日常配置
- ✅ 示例文件在 `examples/active-task.example.json`（仅模板）

## 与其他机制的区别

| 机制 | 用途 | 持久化 |
|------|------|--------|
| **active-task.json** | 跨会话长任务状态 | `.pkb-local/`（仅本地）|
| **Claude auto memory** | 用户偏好和事实 | Claude Code 管理 |
| **Claude session resume** | 对话上下文恢复 | Claude Code 管理 |
| **Wiki pages** | 知识库内容 | Git 跟踪 |
| **handoff_*.md** | 已弃用 — 不再使用临时交结文件 | — |

## 故障排查

### active-task.json 损坏

**症状**：SessionStart 提示 "Task file corrupt"

**修复**：
```powershell
# 损坏文件已自动备份为 .bak
# 检查备份
ls .pkb-local/state/active-task.json.bak

# 清除损坏文件并重建
python tools/pkb_task.py clear
python tools/pkb_task.py start --title "..." --goal "..."
```

### `claude --continue` 找不到会话

**症状**：`No previous session found`

**说明**：`--continue` 依赖 Claude Code 的会话历史。如果历史已清除，需要手动启动新会话并告知任务进度。

**缓解**：`python tools/pkb_task.py inject` 输出任务上下文，可复制给新会话。

### 任务状态不更新

**说明**：任务状态更新是**可选**的。如果不需要跨会话跟踪，可以完全不用。PKB 核心功能不受影响。

## 更多

- [MCP Configuration](MCP.md) — MCP 设置和故障排查
- [CNKI Workflow](CNKI.md) — 知网检索完整流程
- [Updating from older versions](UPDATING.md) — 升级指南
