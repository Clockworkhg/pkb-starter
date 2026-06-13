# CNKI Workflow — 知网检索与论文下载

PKB v0.6.9 提供完整的知网（CNKI）文献检索、筛选和下载流程。

## 前提条件

- Google Chrome 或 Chromium
- Node.js（含 npx）
- 知网账号（需要机构订阅或付费）

## 快速开始

```powershell
# 一键启动 CNKI 工作流
.\pkb.ps1 cnki
```

这会自动：
1. 检查 Chrome 安装
2. 启动 Chrome 调试实例（PKB 专用 profile）
3. 检查 MCP 配置
4. 提示下一步操作

### 首次使用

1. **启动环境**：`.\pkb.ps1 cnki`
2. **登录知网**：在自动打开的 Chrome 窗口中登录 cnki.net
3. **启动 Claude Code**：`.\pkb.ps1 resume`
4. **执行检索**：在 Claude Code 中运行 `/pkb-cnki fill-gaps` 或 `/pkb-cnki search`

后续使用时，Chrome 登录态会保留在 `.pkb-local/chrome-profile/`，无需重复登录。

## 命令参考

### 统一启动器

| 命令 | 用途 |
|------|------|
| `.\pkb.ps1 cnki` | 启动 CNKI 工作流（Chrome + MCP 检查）|
| `.\pkb.ps1 resume` | 恢复 Claude Code 会话 + 加载 MCP |
| `.\pkb.ps1 doctor` | 完整诊断（18 项检查）|
| `.\pkb.ps1 status` | 环境状态摘要 |

### Claude Code 内命令

| 命令 | 用途 |
|------|------|
| `/pkb-cnki fill-gaps` | 补齐 manifest.json 中缺失的 PDF |
| `/pkb-cnki search <关键词>` | 搜索知网 → 创建 wiki 文献页 |
| `/pkb-cnki download <标题>` | 按标题下载论文 PDF |
| `/pkb-cnki download --doi <DOI>` | 按 DOI 精确下载 |
| `/pkb-cnki status` | 查看下载状态摘要 |

## 登录态管理

PKB 使用独立的 Chrome profile 保存知网登录状态：

```
.pkb-local/chrome-profile/   ← Chrome 用户数据目录
  ├── Default/
  │   ├── Cookies             ← 知网登录 Cookie
  │   ├── Local Storage/      ← 知网本地存储
  │   └── ...
  └── ...
```

- ✅ 登录态在会话之间保留
- ✅ 不影响用户日常 Chrome
- ✅ 不提交到 Git（`.gitignore` 已配置）
- ⚠️ Cookie 过期后需要重新登录

## Chrome 调试实例

### 检测当前状态

```powershell
# 快速检查
powershell tools/launch_chrome.ps1 -Check

# 完整诊断
.\pkb.ps1 doctor
```

Doctor 会区分：
- Chrome 未安装
- Chrome 未运行
- Chrome 已运行但无调试端口
- 调试端口可用但返回非 Chrome 响应
- 调试端口可用，完全正常

### 端口冲突

如果 9222 端口被占用：

```powershell
# 查看占用进程
netstat -ano | findstr :9222

# 使用自定义端口
$env:CHROME_DEBUG_PORT = "9223"
$env:CHROME_DEBUG_URL = "http://127.0.0.1:9223"
.\pkb.ps1 cnki
```

**注意**：如果端口被另一个 Chrome 调试实例占用，且该实例使用了不同的 user-data-dir，PKB 可以检测到这一情况并提示。

## 能力依赖

CNKI Skill 声明了以下必要能力：

| 能力 | 缺失时的行为 |
|------|-------------|
| `chrome-devtools` | 🛑 阻塞 — 标记 `pkb_task.py block` |
| `chrome-debug-port` | 🛑 阻塞 — 引导用户运行 `.\pkb.ps1 cnki` |
| `cnki-login` | 🛑 阻塞 — 提示用户登录 |

**诚实降级**：MCP 不可用时，不会用 WebSearch 冒充 CNKI 检索。替代方案会明确标注来源（如 Crossref/OpenAlex 公开元数据）。

## 故障排查

### 知网登录态失效

**症状**：CNKI 页面显示未登录或需要验证

**修复**：
1. 在 PKB Chrome 窗口中重新登录
2. 如遇到验证码，完成验证后恢复操作
3. 登录态会自动持久化

### MCP 工具不可用

**症状**：`mcp__chrome-devtools__*` 工具不在当前会话

**修复**：
```powershell
.\pkb.ps1 resume    # 重新启动 Claude Code + 加载 MCP
```

### 下载速度慢

**说明**：知网对下载频率有限制。PKB 的 fill-gaps 流程已内置 3-5 秒延迟。

### PDF 下载失败

**可能原因**：
- 知网无收录该论文
- 机构订阅不含该论文
- 验证码阻断
- 网络问题

PKB 会记录每篇失败论文的原因到 manifest.json。

## 更多

- [MCP Configuration](MCP.md) — MCP 设置
- [Session Continuity](SESSION_CONTINUITY.md) — 会话恢复
