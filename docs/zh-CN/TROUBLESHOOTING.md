# PKB Starter -- 常见问题

语言：[English](../TROUBLESHOOTING.md) | [简体中文](TROUBLESHOOTING.md)

## 关于路径

Windows 支持中文路径，但为了减少 Python、Git、Shell、第三方工具和跨平台兼容问题，建议优先使用英文路径，例如 `D:\MyKB`。如果用户坚持使用中文路径，也可以尝试，但遇到编码或工具兼容问题时，建议迁移到英文路径。

## 常见问题与解决方案

### `/pkb` 提示 "unknown command"

**原因**：`.claude/commands/` 中的命令是**项目命令**，并非全局 slash 命令。必须使用 `/project:` 前缀调用。

**解决方法**：使用项目命令格式：
```
/project:pkb <任何东西>
/project:inbox
/project:web <url>
/project:ask <问题>
/project:lint
```

**工作原理**：当你 `cd` 到 PKB 目录并运行 `claude` 时，Claude Code 检测项目根目录中的 `.claude/commands/`。这些命令之后以 `/project:<名称>` 格式可用。除非安装为 Claude Code 插件，否则不能使用裸 `/pkb`。

### `.doc` 文件解析失败

**原因**：旧格式 `.doc` 文件（非 `.docx`）需要不同的解析方式。

**解决方法**：
1. 先转换为 `.docx`（在 Word/LibreOffice 中打开，另存为 `.docx`）
2. 或使用转换器：`libreoffice --headless --convert-to docx file.doc`
3. 重新导入：`/pkb file.docx`

### "python: command not found" / "python 不是可识别的命令"

**原因**：Python 不在 PATH 中，或 Windows 上使用 `python` vs `python3` 的问题。

**解决方法**：
- Windows：使用 `python`（不是 `python3`）。如果找不到，将 Python 添加到 PATH。
- macOS/Linux：尝试 `python3` 或安装：`brew install python` / `apt install python3`
- 验证：`python --version` 应显示 3.9+

### GitHub 采集返回错误内容

**原因**：GitHub 速率限制、私有仓库或 Jina 回退抓取了导航栏。

**解决方法**：
1. 对于公开仓库，PKB 使用 GitHub API -> git clone -> Jina（按顺序）
2. 对于私有仓库，确保 git 已认证（`git config --global credential.helper`）
3. 如果 Jina 抓取了导航栏而非内容：添加 `--no-jina` 标志
4. 增加请求间隔：`--delay 0.5`

### 微信公众号文章无法采集

**原因**：微信文章需要特定的 cookie/会话处理。

**解决方法**：
1. PKB web_pack 尝试使用特殊微信处理（max-depth 0）
2. 如果自动采集失败，手动变通方案：
   - 在微信桌面版中打开文章
   - 手动复制内容
   - 保存到剪贴板
   - 运行 `/clip`
3. Agent 会自动检测失败并建议手动剪贴

### "Bun not found" 错误

**原因**：此消息来自外部 Claude Code hooks 或本机用户全局 hook 配置。PKB Starter 不使用也不依赖 Bun。

**解决方法**：
- PKB Starter 是 Python 项目——所有脚本和 hooks 均为 Python 3.9+。
- "Bun not found" 消息是非阻塞的，不影响 PKB 操作。
- 如果看到此消息，请检查全局 Claude Code hook 设置（`~/.claude/settings.json` 或 `%USERPROFILE%\.claude\settings.json`），查找可能引用 Bun 的 hooks。
- 如果启用了自定义 hooks，请确保安装了所需的运行时，或禁用使用 Bun 的 hooks。
- 验证 Python 依赖：`pip install -r requirements.txt`

### 健康检查报告大量断链

**原因**：重命名或删除的 wiki 页面留下了悬空的 `[[wikilink]]` 引用。

**解决方法**：
1. 运行 `/lint` 查看所有断链
2. 手动修复：找到断开的 `[[link]]` 并更新为正确的页面名称
3. 或对源材料重新运行 `/pkb` 以重新生成链接

### `git commit` 提交前密钥扫描失败

**原因**：在暂存文件中检测到敏感模式。

**解决方法**：
1. 阅读扫描报告查看哪些文件/模式被标记
2. 运行 `/sanitize <file>` 进行脱敏
3. 如有需要，审查并手动清理
4. 重新运行 `/save`

### 大型网页采集占用过多磁盘空间

**原因**：图片和视频在 `--mode full` 下可能迅速累积。

**解决方法**：
1. 使用 `--max-image-mb 5` 限制图片大小
2. 使用 `--max-video-mb 100` 限制视频大小
3. 使用 `--mode safe` 进行快速纯文本采集
4. 定期检查 `raw/webpacks/` 并删除不需要的 webpack

### Windows 上 "Permission denied"

**原因**：文件被其他程序锁定，或路径过长。

**解决方法**：
1. 如果 Obsidian 打开了 wiki/ vault，先关闭 Obsidian
2. 关闭其他可能锁定 PKB 目录文件的程序
3. 对于长路径问题，使用更短的根路径（例如 `D:\PKB\` 代替 `D:\a-very-long-path-name\PKB\`）

### Obsidian 不显示 wiki 页面

**原因**：Obsidian vault 指向了错误的目录。

**解决方法**：
- 打开 Obsidian -> "Open folder as vault" -> 选择 `wiki/` 目录
- 或打开 PKB 根目录作为 vault（wiki 链接通过路径仍然有效）

### 技能安装失败，"git clone" 错误

**原因**：网络问题、仓库 URL 变更或仓库是私有的/已删除。

**解决方法**：
1. 检查 `skills_registry/skill_catalog.json` 中的仓库 URL
2. 确认你能在浏览器中访问该仓库
3. 对于私有仓库，确保 git 已认证
4. 尝试逐个安装技能：`python scripts/install_skills.py --target . --profile custom`
5. 先查看完整目录：`python scripts/install_skills.py --list`

### 高风险技能无法安装

**原因**：`risk_level: high` 或 `reference_only` 的技能默认被阻止（目录中有 5 个高风险）。

**解决方法**：使用 `--enable-risky` 安装大多数高风险技能：
```
python scripts/install_skills.py --target "D:\MyKB" --profile full --enable-risky
```
z-skills 使用不同的流程：使用 `/project:skills --install z-skills`（需要明确同意）。

### Z-Skills 无法安装

**原因**：z-skills 使用 `install_method: user_approved_clone` 并需要明确同意。

**解决方法**：
1. 运行：`python scripts/skill_manager.py --target "D:\MyKB" --install z-skills`
2. 阅读显示的风险说明
3. 输入 'INSTALL'（不是 'y' 或 'yes'）以确认
4. z-skills 将克隆到 `skills/_vendor/z-skills/`，状态为 pending_audit

### z-web-pack-local 无法启用

**原因**：z-web-pack-local 要求先安装并审计 z-skills。

**解决方法**：
1. 安装 z-skills：`/project:skills --install z-skills`
2. 审计：`/project:skills --audit`（如果已安装 z-skills，会自动审计）
3. 然后启用：`/project:skills --enable z-web-pack-local`

### Z-skills 审计报告缺失

**原因**：尚未运行审计，或 zskill_bridge.py 不在目标 PKB 中。

**解决方法**：
1. 运行：`python scripts/skill_manager.py --target "D:\MyKB" --audit`
2. 或直接：`python tools/zskill_bridge.py audit`
3. 如果找不到桥接脚本：从 pkb-starter 复制 `template/tools/zskill_bridge.py` 到你的 PKB 的 `tools/` 目录。

### Z-web-pack 采集器提示 "adapter is not enabled"

**原因**：使用了 `--collector z-web-pack` 但 z-web-pack-local 未启用。

**解决方法**：
```
/project:skills --install z-skills          # 安装（明确同意）
/project:skills --audit                     # 审计许可证 + 结构
/project:skills --enable z-web-pack-local   # 启用适配器
```
然后重试：`/project:web --collector z-web-pack <url>`

### 插件市场技能无法安装

**原因**：`install_method: plugin_marketplace` 的技能（obsidian-skills、academic-research-skills）无法通过 git clone 安装。

**解决方法**：通过 Claude Code 手动安装：
```
/plugin marketplace add kepano/obsidian-skills
/plugin install obsidian@obsidian-skills
```
这些技能在目录中仅供参考。install_skills.py 会跳过它们并显示手动安装说明。

### 技能适配器不工作

**原因**：适配器未复制到目标 PKB，或技能输出进入了错误的目录。

**解决方法**：
1. 确认适配器存在：`ls template/skill_adapters/`
2. 重新安装技能以复制其适配器
3. 检查 `SKILL_LINKS.md` 中的适配器映射
4. 手动将适配器复制到你的 PKB 的 `templates/skill_adapters/`

### /project:skills 提示 "unknown command"

**原因**：`.claude/commands/skills.md` 文件未复制到目标 PKB。

**解决方法**：
1. 确认 `.claude/commands/skills.md` 在你的 PKB 目录中存在
2. 重新安装 PKB 模板：`python scripts/install.py "D:\MyKB" --force`
3. 或从 pkb-starter 模板手动创建命令文件

### 技能在目录中显示 NO LICENSE

**原因**：某些仓库（如 agent-research-skills、z-skills）缺少 LICENSE 文件。

**解决方法**：
1. 检查克隆仓库的根目录是否有任何许可证文件：`ls skills/_vendor/<skill-id>/LICENSE*`
2. 检查仓库的 GitHub 页面获取许可证信息
3. 如果没有找到许可证，视为"保留所有权利" — 仅供个人参考使用
4. 运行 `python scripts/skill_manager.py --target . --audit` 查看所有已安装技能的许可证状态

### 安装后找不到技能

**原因**：技能经过三个阶段：安装 -> 审计 -> 启用。新安装的技能尚未启用。

**解决方法**：
1. 运行 `/project:skills` 查看所有已安装技能及其状态
2. 标记为 [INSTALLED] 或 [PENDING AUDIT] 的技能已下载但未激活
3. 运行 `/project:skills --audit` 验证安装
4. 运行 `/project:skills --enable <id>` 激活
5. 重启 Claude Code 加载新启用的技能

### 初始设置后想添加技能

**原因**：你使用了 `--skip-skills` 安装，现在想添加技能。

**解决方法**：
```bash
# 浏览可用技能
python scripts/skill_manager.py --target "D:\MyKB" --list

# 或在 Claude Code 中
/project:skills --list
/project:skills --describe deep-research-skills
/project:skills --install-profile student
```
技能可以随时添加——无需重新安装 PKB。

### skill_manager.py 提示 "Target directory does not exist"

**原因**：--target 路径必须指向你的 PKB 安装目录，而非 pkb-starter 源代码目录。

**解决方法**：
```bash
# 指向你的 PKB 目录，不是 pkb-starter
python scripts/skill_manager.py --target "D:\MyKB" --list
# 不要：python scripts/skill_manager.py --target "D:\pkb-starter" --list
```

### Dry-run 显示了技能但实际未安装

**原因**：`--dry-run` 是预览模式。它展示将要发生什么，但不做实际修改。

**解决方法**：移除 `--dry-run` 以实际安装：
```bash
python scripts/skill_manager.py --target "D:\MyKB" --install-profile student
```

### 更新失败 "No pkb.config.json found"

**原因**：目标目录不是 PKB 安装目录，或配置文件被删除。

**解决方法**：
1. 确认你指向的是 PKB 安装目录，而非 pkb-starter 源代码
2. 在你的 PKB 目录中运行 `ls pkb.config.json`
3. 如果缺失，重新安装：`python scripts/install.py "D:\MyKB" --force`

### 更新提示 "Already up-to-date" 但我预期有变更

**原因**：你已安装的 `starter_version` 匹配或超过了当前版本。

**解决方法**：
1. 检查你的版本：`cat pkb.config.json | grep starter_version`
2. 检查 `scripts/update_pkb.py` 中的 pkb-starter 版本（CURRENT_VERSION）
3. 如果 pkb-starter 领先，拉取：`cd D:\pkb-starter && git pull`
4. 然后重新运行更新

### 更新覆写了我的 AGENTS.md

**原因**：`AGENTS.md` 在系统更新路径中，且使用了 `--force`。

**解决方法**：
1. 从备份恢复：`cp .pkb_backup/<最新>/AGENTS.md .`
2. 默认情况下，用户修改的 AGENTS.md 会被跳过。仅在有意时使用 `--force`。
3. 考虑将你的自定义规则添加到单独文件，并从 AGENTS.md 中引用。

### 迁移脚本失败

**原因**：某个迁移脚本在目标 PKB 中遇到了意外状态。

**解决方法**：
1. 检查错误输出 — 迁移脚本会报告哪个前置条件失败。
2. 从备份恢复：`cp -r .pkb_backup/<最新>/* .`
3. 报告问题，附上你的 pkb-starter 版本和目标 PKB 状态。

### 备份目录越来越大

**原因**：多次更新创建了多个带时间戳的备份目录。

**解决方法**：
1. 检查备份：`ls .pkb_backup/`
2. 保留最近 2-3 个备份
3. 删除旧备份：`rm -rf .pkb_backup/20250101_120000`
4. `.pkb_backup/` 在 `.gitignore` 中，不会被提交

### /project:update 提示 "unknown command"

**原因**：更新命令在 pkb-starter v0.5.0 中添加。旧版本安装中没有。

**解决方法**：
1. 先手动更新：`python scripts/update_pkb.py "D:\MyKB"`
2. 迁移后，`/project:update` 将可用
3. 后续更新可直接使用该命令

### 找不到 pkb_update_client.py

**原因**：你的知识库是在 v0.6.2-alpha 之前安装的。更新客户端在该版本中添加。

**解决方法**：
1. 手动更新一次：`python scripts/update_pkb.py "D:\MyKB"`（从 pkb-starter 目录运行）
2. 更新后，`tools/pkb_update_client.py` 即可用
3. 后续更新：`python tools/pkb_update_client.py`

### 更新客户端提示 "No valid starter_repo_url"

**原因**：`pkb.config.json` 中的 `starter_repo_url` 未设置或者是占位符。

**解决方法**：
1. 编辑 `pkb.config.json`，将 `starter_repo_url` 设置为你的 pkb-starter fork
2. 或使用 `--starter-path "D:\pkb-starter"` 指向本地克隆
3. 或使用 `--repo-url https://github.com/<your-fork>/pkb-starter.git`

### 安装失败 "Target directory not empty"

**原因**：目标安装路径中已有文件。

**解决方法**：
1. 使用空目录：`python scripts/install.py "D:\MyKB"`
2. 或使用 `--force` 覆盖：`python scripts/install.py "D:\MyKB" --force`
3. 或使用交互模式确认：`python scripts/install.py --interactive`

### 未提供安装目标路径

**原因**：`install.py` 需要第一个位置参数指定目标路径。

**解决方法**：
```bash
# 提供目标路径
python scripts/install.py "D:\MyKB"

# 或使用交互模式
python scripts/install.py --interactive
```

路径可以是任意目录——`E:\KnowledgeBase`、`C:\Users\...\Documents\PKB` 等，无默认强制路径。

---

## 仍然卡住了？

1. 运行 `python scripts/check_env.py` 验证环境
2. 查看 [DESIGN.md](DESIGN.md) 理解架构
3. 在 pkb-starter GitHub 仓库提交 issue
