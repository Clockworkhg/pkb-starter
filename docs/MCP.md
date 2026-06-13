# MCP Configuration & Troubleshooting

PKB 使用 [Claude Code MCP (Model Context Protocol)](https://docs.anthropic.com/en/docs/claude-code/mcp) 连接外部服务。
当前主要用途是 **Chrome DevTools MCP**，用于知网（CNKI）浏览器自动化。

## 配置文件位置

Claude Code 按以下优先级发现 MCP 配置：

1. `--mcp-config <file>` 命令行参数（最高优先级）
2. `.mcp.json`（项目根目录）— **PKB 标准位置**
3. `~/.claude.json`（用户全局配置）

PKB 将公开的 MCP 配置放在项目根目录 `.mcp.json`：

```json
{
  "mcpServers": {
    "chrome-devtools": {
      "command": "npx",
      "args": [
        "-y",
        "chrome-devtools-mcp@latest",
        "--browserUrl",
        "${CHROME_DEBUG_URL:-http://127.0.0.1:9222}"
      ]
    }
  }
}
```

### 环境变量覆盖

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `CHROME_DEBUG_URL` | `http://127.0.0.1:9222` | Chrome 调试地址（含端口） |
| `CHROME_DEBUG_HOST` | `127.0.0.1` | 调试主机（仅 host） |
| `CHROME_DEBUG_PORT` | `9222` | 调试端口（仅 port） |

## 快速诊断

```powershell
# 完整诊断（18 项检查）
.\pkb.ps1 doctor

# 或 Python 版本
python tools/pkb_doctor.py

# 仅机器可读 JSON
python tools/pkb_doctor.py --json
```

## Chrome DevTools MCP

### 启动流程

```powershell
# 一键启动（推荐）
.\pkb.ps1 cnki

# 或分步操作：
.\pkb.ps1 doctor          # 诊断
.\pkb.ps1 resume          # 恢复会话 + MCP
```

### 手动启动 Chrome 调试

```powershell
# 使用 PKB 专用 profile（保存登录态）
powershell tools/launch_chrome.ps1

# 仅检查状态
powershell tools/launch_chrome.ps1 -Check

# 静默模式（无提示）
powershell tools/launch_chrome.ps1 -Silent
```

### 工作原理

1. Chrome 以 `--remote-debugging-port=9222` 启动
2. 使用独立 profile `.pkb-local/chrome-profile/`（不影响日常 Chrome）
3. Claude Code 通过 MCP Server 连接调试端口
4. 知网登录状态保存在独立 profile 中（不提交到 Git）

## 故障排查

### `.mcp.json` 未被识别

**症状**：`claude mcp list` 中看不到 `chrome-devtools`

**检查**：
```powershell
# 确认 .mcp.json 在项目根目录
ls .mcp.json

# 确认 JSON 格式正确
python -c "import json; json.load(open('.mcp.json'))"
```

**修复**：
```powershell
# 重启 Claude Code 并显式加载 MCP 配置
claude --mcp-config .mcp.json
```

### MCP 显示 "Pending approval"

**症状**：`claude mcp list` 显示 `chrome-devtools` 状态为 `pending`

**修复**：在 Claude Code 中运行：
```
/mcp
```
选择 `chrome-devtools` → 批准（Approve）。

或者运行 `.\pkb.ps1 doctor` 查看诊断建议。

### Chrome 端口失败

**症状**：`http://127.0.0.1:9222/json` 无法访问

**可能原因**：
1. Chrome 未启动调试模式
2. 端口被其他程序占用
3. 防火墙阻止

**诊断**：
```powershell
# 检查端口占用
netstat -ano | findstr :9222

# 检查 Chrome 进程
tasklist | findstr chrome

# 完整诊断
.\pkb.ps1 doctor
```

### Chrome 已运行但端口不匹配

**症状**：Chrome 在运行但 9222 端口无响应

**说明**：用户日常 Chrome 没有 `--remote-debugging-port` 参数。
PKB 会启动**独立的 Chrome 实例**，使用专用 profile，不影响日常 Chrome。

### 端口冲突

**症状**：`端口 9222 被其他程序占用`

**修复**：
```powershell
# 方案 1: 使用不同端口
$env:CHROME_DEBUG_PORT = "9223"
# 同时更新 .mcp.json 或设置 CHROME_DEBUG_URL=http://127.0.0.1:9223

# 方案 2: 关闭占用进程
netstat -ano | findstr :9222
taskkill /PID <PID> /F
```

### npx 不存在

**症状**：`npx: not found`

**修复**：安装 Node.js（包含 npx）
```powershell
# 下载安装 Node.js LTS
# https://nodejs.org/
```

### 从旧版 `.claude/mcp.json` 迁移

PKB v0.6.9 使用标准 `.mcp.json`。已有 `.claude/mcp.json` 的用户：

1. **系统自动兼容**：PKB 工具会同时检查两个位置
2. **建议迁移**：将 Chrome DevTools 配置复制到 `.mcp.json`
3. **不删除旧文件**：`.claude/mcp.json` 可以保留（不会冲突）

```powershell
# 手动迁移（如有需要）
copy .claude\mcp.json .mcp.json
# 然后编辑 .mcp.json，移除本地特定配置
```

## 本地配置（不进入 Git）

如需添加私人 MCP 配置（Zotero 密钥等），使用：
- `.claude/settings.local.json`（Claude Code 本地设置）
- `.mcp.local.json`（如需要，手动创建，已在 `.gitignore`）

这些文件不会提交到 Git。

## 更多

- [Session Continuity](SESSION_CONTINUITY.md) — 会话恢复与任务连续性
- [CNKI Workflow](CNKI.md) — 知网检索完整流程
- [Updating from older versions](UPDATING.md) — 升级指南
