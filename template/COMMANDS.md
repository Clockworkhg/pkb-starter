# COMMANDS.md — PKB 懒人命令手册

> 你不需要记住任何命令。你只需要记住一个命令。

---

## 🚀 唯一入口：`/pkb`

```
/pkb <任何东西>
```

把任何东西丢给 `/pkb`，Agent 会自动判断该做什么：

| 你丢进去的 | Agent 自动做的 |
|-----------|--------------|
| `/pkb C:\Users\me\paper.pdf` | 📥 导入文件到 _INBOX |
| `/pkb C:\Users\me\project\` | 📥 导入整个文件夹 |
| `/pkb https://arxiv.org/abs/2301.12345` | 🌐 Raw 层采集 → raw/webpacks |
| `/pkb https://github.com/author/repo` | 🌐 GitHub 特殊采集 → raw/webpacks |
| `/pkb transformer attention 原理` | 🔍 搜索 wiki 并回答 |
| `/pkb 保存` | 💾 Git commit 当前状态 |
| `/pkb 检查` | 🩺 运行健康检查 |

### /pkb 路由逻辑

| 输入类型 | 执行命令 | 说明 |
|---------|---------|------|
| 单篇普通网页 | `/clip` | 快速剪藏到 raw/clippings |
| GitHub 链接 | `/web` | GitHub README/raw 优先抓取 |
| 多个链接 | `/web` | 生成素材包 |
| 论文链接 | `/web` | 展开引用 |
| 文档/教程 | `/web` | 展开关联页面 |
| `/pkb transformer attention 原理` | 🔍 搜索 wiki 并回答 |
| `/pkb 保存` | 💾 Git commit 当前状态 |
| `/pkb 检查` | 🩺 运行健康检查 |

---

## 📋 独立命令（可选，更精确的控制）

### 核心命令
| 命令 | 作用 |
|------|------|
| `/add <路径>` | 导入文件/文件夹到 _INBOX |
| `/inbox` | 查看待处理的文件 |
| `/web <URL>` | 🌐 Raw 层素材包采集 → raw/webpacks |
| `/clip` | 采集剪贴板内容 |
| `/ask <问题>` | 搜索知识库回答 |
| `/output` | 保存当前对话产出 |
| `/lint` | 知识库健康检查 |
| `/docs-update` | 📋 自动检测+更新项目文档 |
| `/save "消息"` | Git 提交（含自动文档更新） |
| `/rollback` | 查看/回滚 Git 历史 |
| `/help` | 显示此帮助 |

### 🔌 CNKI 知网命令
| 命令 | 作用 |
|------|------|
| `/pkb-cnki fill-gaps` | 🎯 自动补齐缺失的论文 PDF（从 manifest.json 读取） |
| `/pkb-cnki fill-gaps <领域>` | 只补齐指定领域的 PDF |
| `/pkb-cnki search <关键词>` | 搜索知网 → 自动创建 wiki 文献页 |
| `/pkb-cnki download <标题>` | 单篇论文搜到即下，存入 raw/papers/ |
| `/pkb-cnki status` | 查看 PDF 下载状态摘要 |
| `python tools/cnki_setup.py --fix` | 一键安装 MCP + 诊断 Chrome |
| `powershell tools/launch_chrome.ps1` | 启动 Chrome 远程调试模式 |

> CNKI 命令需 Chrome DevTools MCP 连接 + 用户登录知网。详见 [[cnki-skills-integration]]。

### 📚 学术研究命令
| 命令 | 作用 |
|------|------|
| `/research <主题>` | 深度调研（多源搜索+综合报告） |
| `/paper <路径>` | 论文分析/写作 |
| `/literature-search <查询>` | 学术文献多源搜索 (Semantic Scholar/arXiv/OpenAlex) |
| `/literature-review <主题>` | 多视角对话式文献综述 |
| `/paper-writing-section` | 论文章节撰写 |
| `/related-work-writing` | 相关工作章节撰写 |
| `/idea-generation <主题>` | 研究想法生成+新颖性检查 |
| `/citation-management` | 引用收集/验证/格式化 (GB/T 7714/APA/IEEE) |
| `/self-review` | 论文投稿前自查 |
| `/paper-revision` | 根据审稿意见修订 |
| `/rebuttal-writing` | 审稿回复信撰写 |
| `/algorithm-design` | 算法设计（伪代码+复杂度分析） |
| `/math-reasoning` | 数学推理（定理证明/公式推导） |
| `/experiment-design` | 实验方案设计 |
| `/experiment-code` | 实验代码生成（7段式结构） |
| `/data-analysis <数据>` | 统计分析（4轮代码审查） |
| `/figure-generation` | 学术图表生成 (matplotlib/seaborn) |
| `/table-generation` | 学术表格生成 (LaTeX/CSV/Markdown) |
| `/zotero <key>` | Zotero 文献库查询 |

### 🛠️ 工具命令
| 命令 | 作用 |
|------|------|
| `/z-excel-editor <文件>` | Excel 创建/编辑/格式化 |
| `/z-md-excel <文件>` | Markdown 表格 → Excel 批量转换 |
| `/doc <文件>` | 文档格式转换 (Phase 3) |
| `/ocr <文件>` | 图片/扫描PDF OCR (Phase 3) |
| `/search <关键词>` | 全文搜索 (Phase 2: qmd) |
| `/sanitize <文件>` | 隐私清理 (Phase 2) |

### 🎨 创作命令 (Phase 3)
| 命令 | 作用 |
|------|------|
| `/prompt` | AI 提示词库管理 |
| `/song` | 歌词/Suno 风格版本管理 |
| `/script` | 剧本拆分/分镜生成 |

### ⚙️ 元命令 (Phase 3)
| 命令 | 作用 |
|------|------|
| `/kanban` | Markdown 看板管理 (Phase 2) |
| `/make-skill <描述>` | 创建新 Skill |
| `/skill-lint` | Skill 健康检查 |

---

## 💡 最懒的日常用法

```
# 丢进去就完事了（默认全自动）
/pkb "文件路径或链接"

# 批量处理 _INBOX（默认全自动）
/inbox

# 查询
/ask 问题

# 手动控制（如需审阅）
/pkb --manual "文件路径"
/pkb --collect-only "https://..."
/pkb --plan "文件1" "文件2"
```

**`/pkb` 默认全自动**：导入 → 分类 → 编译 wiki → 归档 → 健康检查 → git commit。
用户只需要看最终报告。不是"需要加 --auto"，是"本就该这样"。

### /web — Web Pack v3 (z-web-pack aligned)

采集器已以 [z-web-pack](https://github.com/tjxj/z-skills/tree/main/z-web-pack) 为功能标准完全重构。

```bash
# 默认 full 模式（完整图片管线 + GitHub Collector v2）
python tools/web_pack.py --topic "主题" --url "https://..."

# safe 模式（无 cookie/视频/登录态）
python tools/web_pack.py --topic "主题" --url "https://..." --mode safe

# 视频采集
python tools/web_pack.py --topic "主题" --url "https://..." --videos all --download-media

# 关键参数
--mode full|safe         # 模式 (默认 full)
--videos off|direct|all  # 视频 (默认 direct)
--download-media         # 完整媒体下载
--browser-cookies chrome # yt-dlp cookie (仅 full)
--max-image-mb 20        # 图片上限
--max-video-mb 300       # 视频上限
--same-domain-only       # 仅同域
--no-jina               # 禁用 Jina
```

输出: `raw/webpacks/YYYY-MM-DD-主题/` (README, 5 inventories, manifest.json, MAIN/LINKED pages, assets)
正文提取管线: readability-lxml → trafilatura → BeautifulSoup → Jina
图片能力: srcset, magic bytes, SHA256 去重, tracking 过滤, Referer 防盗链, 共 16 项
视频能力: yt-dlp 平台视频, 字幕, 封面, 1080p 封顶

---

## 🔌 已安装的外部 Skill 命令

### Academic Research Skills (ars)
| 命令 | 作用 |
|------|------|
| `/ars-full` | 完整学术研究管线 |
| `/ars-plan` | 论文章节规划 |
| `/ars-outline` | 详细大纲 + 证据地图 |
| `/ars-abstract` | 双语摘要 + 关键词 |
| `/ars-lit-review` | 带注释的文献综述 |
| `/ars-citation-check` | 引用错误报告 |
| `/ars-format-convert` | LaTeX/DOCX/PDF/Markdown 转换 |
| `/ars-reviewer` | 模拟同行评审 |
| `/ars-revision` | 修订稿 + R&R 回复 |
| `/ars-disclosure` | AI 使用声明 |

### Obsidian Skills
自动激活：Markdown 编辑、双链、Canvas、Bases、Web Clipper

---

## 🤖 后台自动化（无需手动触发）

以下 6 个 harness hooks 在后台自动运行，无需用户调用：

| Hook | 何时触发 | 做什么 |
|------|---------|--------|
| SessionStart | 会话启动 | 打印 PKB 上下文卡片 + 环境检测 |
| PreToolUse | 每次工具调用前 | 拦截 secret commit / raw 删除 / 敏感写入 |
| PostToolUse | 文件写入后 | wiki 快速健康检查 + commit 后全量检查 |
| PostToolUseFailure | 工具失败时 | 错误分类（11 类）+ 恢复建议 |
| Stop | 会话退出前 | 未提交提醒 + 会话摘要 |
| UserPromptSubmit | 用户输入时 | 智能路由建议（URL→/pkb, CNKI→/pkb-cnki） |

> 配置：`.claude/settings.json` | 脚本：`.claude/hooks/` | 用户覆盖：`.claude/settings.local.json`

---

## 📦 待安装 Skill（已审核）

| Skill | 推荐度 | 安装方式 |
|-------|--------|---------|
| deep-research | ⭐⭐⭐ | 复制到 `.claude/skills/` |
| literature-search | ⭐⭐⭐ | 复制到 `.claude/skills/` |
| paper-writing-section | ⭐⭐ | 复制到 `.claude/skills/` |
| 更多... | | 见 `SKILL_LINKS.md` |
