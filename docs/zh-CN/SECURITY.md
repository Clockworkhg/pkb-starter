# PKB Starter -- 安全说明

语言：[English](../SECURITY.md) | [简体中文](SECURITY.md)

## PKB 不上传什么

PKB 是一个**本地优先**的系统。默认情况下：
- **一切都在你的机器上** — 无云同步、无遥测、无分析
- **不自动推送**到远程 Git 仓库
- **无外部 API 调用**，除非你明确请求网页采集（`/web`）
- **所有知识保存在 `raw/` 和 `wiki/`** 中，位于你的本地磁盘

## 不应该放入 PKB 的内容

### 绝对不要添加：
- API key、token、密码、密钥
- 私钥（SSH、PGP、SSL 证书）
- `.env` 文件或等效文件
- OAuth 客户端密钥
- 数据库连接字符串
- 信用卡号、银行账户
- 身份证号、护照扫描件
- 医疗记录
- 认证 cookie

### 谨慎处理：
- wiki 页面中的个人邮箱地址（使用 `redacted@example.com` 或通用占位符）
- 电话号码
- 家庭地址
- 雇佣合同
- 工作中的专有代码
- 机密文档

### 可以安全添加：
- 公开网页文章
- 学术论文（已发表）
- 开源代码
- 个人笔记和摘要
- 项目文档
- 学习资料

## Cookie / 完整模式安全

`web_pack.py` 有两种模式：

### `--mode safe`（推荐用于敏感浏览）
- 不读取 cookie
- 不下载视频
- 不处理登录状态
- 仅基础图片采集

### `--mode full`（选择加入，功能更强）
- `--browser-cookies` 标志仅在同时使用 `--download-media` 时可用
- Cookie 仅传递给 yt-dlp 用于视频平台访问
- Cookie 绝不用于 HTTP 页面请求
- Cookie 绝不写入任何文件（不写入 manifest.json、不写入 markdown、不写入日志）
- Cookie 绝不包含在 git 提交中

## Git 安全

### `.gitignore` 保护：
```
.env、.env.*
*credentials*、*serviceAccount*
*.pem、*.p12、*.pfx、*.key
id_rsa*、*_rsa
.claude/settings.local.json
raw/personal/*id_card*、*passport*、*bank*、*medical*
```

### `/save` 提交前检查：
每次 git 提交前，`/save` 运行密钥扫描：
1. 检查所有暂存文件中的 API key / token / password 模式
2. 发现关键模式时阻止提交
3. 对潜在的个人身份信息（邮箱、电话）发出警告

## 分享知识库之前

如果你打算公开你的知识库（例如发布到 GitHub）：

1. **运行 sanitize**：`/sanitize wiki/` 扫描并报告敏感模式
2. **删除 raw/personal/**：此目录专门存放你永远不想公开的内容
3. **审查 wiki/**：检查是否意外包含个人信息
4. **检查 git 历史**：`git log -p` 确认提交历史中没有敏感数据
5. **必要时压缩历史**：如果敏感数据曾被提交，使用 `git filter-branch` 或类似工具

## 安全分享特定页面

仅分享某个 wiki 页面：
```
/sanitize wiki/concepts/my-concept.md --fix
# 审查脱敏后的版本
# 仅分享脱敏副本
```

原始文件保持不变。Sanitize 创建包含脱敏处理的副本。

## 隐私级别

PKB 支持为内容标记隐私级别：

```yaml
---
privacy: internal   # 不在 /ask 输出中引用
privacy: public     # 可以安全分享
---
```

在 frontmatter 中设置。`/ask` 技能遵循此设置，不会在回答中暴露 `internal` 内容。

## 可选技能安全

PKB 的可选技能系统（43 个目录条目，9 个独立外部仓库）使用以下安全措施：

1. **不自动执行**：技能仅通过 `git clone --depth 1` 安装。无安装脚本、无克隆后钩子、无 npm/pip install。
2. **隔离存放**：技能位于 `skills/_vendor/`（已被 gitignore）。不会修改 PKB 核心文件。
3. **适配器路由**：所有技能输出通过 PKB 适配器，强制放置到 `raw/`/`wiki/`。技能不能在项目根目录散落文件。
4. **不自动配置 MCP**：需要 MCP 服务器的技能需手动配置 `.claude/mcp.json`。PKB 绝不触碰 MCP 配置。
5. **不存储 API key**：PKB 绝不读取、存储或传递第三方技能的 API key。
6. **风险分类**：
   - 28 个低风险（自动安装）
   - 10 个中风险（安装前警告）
   - 5 个高风险（需要明确确认）
   - 0 个仅供参考（z-skills 现为用户授权本地安装）
7. **LICENSE 审查**：每个技能条目记录其许可证状态。无 LICENSE 的技能被标记。z-skills 需要完整审计后才能启用。
8. **z-skills 安全**：
   - **不二次分发代码** — PKB Starter 不包含、不复制、不捆绑 z-skills 源代码。
   - **用户明确选择加入** — 安装 z-skills 需要阅读风险说明后输入 'INSTALL'。
   - **审计后启用** — z-skills 克隆后进入 `pending_audit`。必须通过审计才能启用 `z-web-pack-local`。
   - **不自动执行** — zskill_bridge.py 不自动执行 z-skills 脚本。
   - **不默认打补丁** — 不修改 z-skills 源代码。不兼容问题通过包装器、配置或输出重定位解决。
   - **仅限本地补丁（万不得已时）** — 需要 `--allow-local-patch`。存储在 `.pkb_local/patches/`（已被 gitignore）。
   - **输出隔离** — z-web-pack 输出到 `raw/webpacks/`（与内置采集器相同）。
   - **默认采集器不变** — 基本 web_pack 保持默认，z-web-pack 为选择加入。
9. **插件市场**：2 个技能只能通过 Claude Code 官方插件市场安装，不能通过 git clone。
10. **删除即删目录**：删除技能只需删除 `skills/_vendor/<skill-id>/`。不留残余状态。
11. **审计追踪**：`skill_manager.py --audit` 和 `/project:skills --audit` 报告所有已安装技能，包含风险等级、许可证状态、.git 验证、适配器状态和 INSTALL_NOTE.md 状态。

### 运行时安全

技能可以随时安装——安装时或数月之后。同样的安全规则始终适用：

- **每个技能在安装前都展示说明和风险**——CLI 和 Claude Code 中均如此。
- **安装不等于激活**——技能需经过审计后才能启用。
- **启用是明确的**——`--enable <id>` 是审计后的独立步骤。
- **停用不删除**——`--disable <id>` 停用适配器但保留源代码。
- **从小开始**——Core 配置预设（零外部技能）是最安全的默认选择。按需逐步添加。
- **Full 配置预设警告**——Full 配置预设列出全部 24 个推荐技能，但不自动启用高风险技能。

## 报告安全问题

发现 PKB Starter 的安全问题？请通过 pkb-starter 仓库的 GitHub Issues 报告。不要在 issue 中包含敏感数据。
