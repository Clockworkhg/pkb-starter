# COMMANDS.md -- PKB 命令手册

> 你只需要记住一个命令。

---

## 唯一入口: `/pkb`

```
/pkb <任何东西>
```

把任何东西丢给 `/pkb`，Agent 自动判断该做什么:

| 你丢入 | Agent 自动处理 |
|--------|---------------|
| `/pkb C:\Users\me\paper.pdf` | 导入文件到 _INBOX |
| `/pkb C:\Users\me\project\` | 导入整个文件夹 |
| `/pkb https://example.com/article` | 网页采集到 raw/webpacks |
| `/pkb https://github.com/author/repo` | GitHub 专项采集到 raw/webpacks |
| `/pkb transformer attention concept` | 搜索 wiki 并回答 |
| `/pkb save` | Git 提交当前状态 |
| `/pkb check` | 运行健康检查 |

### /pkb 路由逻辑

| 输入类型 | 执行 | 说明 |
|---------|------|------|
| 单个网页 | `/clip` | 快速剪藏到 raw/clippings |
| GitHub 链接 | `/web` | 优先使用 GitHub README/raw |
| 多个链接 | `/web` | 生成 webpack |
| 论文链接 | `/web` | 展开参考文献 |
| 文档/教程 | `/web` | 展开相关页面 |
| 问题/关键词 | 搜索 wiki | 从知识库回答 |
| "save" | `/save` | Git 提交 |
| "check" | `/lint` | 健康检查 |

---

## 全部项目命令

> 注意: 命令在项目模式下使用 `/project:<名称>` 格式。裸命令（如 `/pkb`）仅在安装为 Claude Code 插件时可用。

### 核心命令

| 命令 | 功能 |
|------|------|
| `/project:pkb <任何东西>` | 智能入口，自动识别类型并处理 |
| `/project:web <URL>` | 采集网页内容到 raw/webpacks |
| `/project:inbox` | 处理待入库文件 |
| `/project:ask <问题>` | 搜索知识库 |
| `/project:lint` | 健康检查 |
| `/project:save` | Git 提交并自动更新文档 |
| `/project:rollback` | 查看/回滚 Git 历史 |
| `/project:sanitize` | 隐私扫描 |
| `/project:skills` | 管理可选技能包 |
| `/project:update` | 从 pkb-starter 更新系统文件 |

### /project:skills -- 技能管理

| 用法 | 功能 |
|------|------|
| `/project:skills` | 查看已安装技能、启用状态和可用配置 |
| `/project:skills --list` | 列出全部 43 个目录条目及说明和风险等级 |
| `/project:skills --describe <id>` | 查看技能详情（功能、风险、安装方法） |
| `/project:skills --install <id>` | 安装单个技能（先显示说明和风险） |
| `/project:skills --install-profile <profile>` | 安装配置中的所有技能（core/student/research/...） |
| `/project:skills --audit` | 审计已安装技能：许可证、适配器、.git、问题 |
| `/project:skills --enabled` | 显示当前启用的技能和适配器 |
| `/project:skills --enable <id>` | 启用一个已审计的技能（激活其适配器） |
| `/project:skills --disable <id>` | 禁用一个技能（不删除源代码） |
| `/project:skills --update-catalog` | 刷新本地目录版本 |
| `/project:skills --install z-skills` | 安装 z-skills 到本地（需明确同意） |
| `/project:skills --enable z-web-pack-local` | 启用 z-web-pack 作为替代采集后端 |

### 研究命令 (需要 academic-research-skills 插件)

| 命令 | 功能 |
|------|------|
| `/project:research <主题>` | 深度研究（多源搜索 + 报告） |
| `/project:paper <路径>` | 论文分析/写作 |
| `/project:literature-search <查询>` | 多源学术搜索 |
| `/project:literature-review <主题>` | 文献综述，多视角对话 |

### 工具命令

| 命令 | 功能 |
|------|------|
| `/project:sanitize <文件>` | 隐私清理 |
| `/project:search <关键词>` | 全文搜索 |
| `/project:doc <文件>` | 文档格式转换 |
| `/project:ocr <文件>` | 图片/PDF OCR 文字提取 |
| `/project:kanban` | 看板管理 |

---

## 日常用法速查

```
# 丢进去即可（默认全自动）
/pkb "文件路径或URL"

# 批量处理 _INBOX（默认全自动）
/inbox

# 查询
/ask 问题

# 手动控制（如需审查）
/pkb --manual "文件路径"
/pkb --collect-only "https://..."
/pkb --plan "文件1" "文件2"
```

`/pkb` 默认全自动: 导入 -> 分类 -> 编译 wiki -> 归档 -> 健康检查 -> git 提交。
你只需要看最终报告。

---

## /project:web -- 网页采集

```bash
# 默认完整模式（完整图片管线 + GitHub Collector）
python tools/web_pack.py --topic "主题" --url "https://..."

# 安全模式（无 cookie/视频/登录状态）
python tools/web_pack.py --topic "主题" --url "https://..." --mode safe

# 视频采集
python tools/web_pack.py --topic "主题" --url "https://..." --videos all --download-media

# 关键参数
--mode full|safe         # 模式（默认 full）
--videos off|direct|all  # 视频模式（默认 direct）
--download-media         # 完整媒体下载
--browser-cookies chrome # yt-dlp cookie（仅 full 模式）
--max-image-mb 20        # 单张图片上限
--max-video-mb 300       # 单个视频上限
--same-domain-only       # 仅同域名
```

输出: `raw/webpacks/YYYY-MM-DD-topic/`
内容提取: readability-lxml -> trafilatura -> BeautifulSoup -> Jina
图片能力: srcset, magic bytes, SHA256 去重, 追踪过滤, Referer 防盗链（16 项功能）
视频能力: yt-dlp 平台视频, 字幕, 缩略图, 1080p 上限

---

## 语言设置

如果 `pkb.config.json` 中 `language` 设置为 `zh-CN`，所有命令输出将自动切换为中文。

```json
{
  "language": "zh-CN"
}
```

---

*属于 PKB Starter。详细规则见 AGENTS.md。*
