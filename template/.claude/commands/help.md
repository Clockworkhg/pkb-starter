# /help — PKB 帮助

你是 PKB 的帮助 Agent。

## 任务
展示 PKB 系统的命令列表和使用说明。

## 快速开始

```
/pkb <任何东西>    ← 唯一需要记住的命令
```

## 命令列表

| 命令 | 作用 | 示例 |
|------|------|------|
| `/pkb <anything>` | 🚀 智能入口 | `/pkb paper.pdf` |
| `/add <path>` | 📥 导入文件/文件夹 | `/add ~/Downloads/paper.pdf` |
| `/inbox` | 📬 查看待处理 | `/inbox` |
| `/web <url>` | 🌐 采集网页 | `/web https://example.com` |
| `/clip` | 📋 采集剪贴板 | `/clip` |
| `/ask <问题>` | 🔍 查询知识库 | `/ask transformer 原理` |
| `/ask-pkb <问题>` | 🌐 全局知识库查询 | `/ask-pkb 费尔巴哈` |
| `/research <主题>` | 🔬 深度研究 | `/research LLM 推理优化` |
| `/paper <path\|url>` | 📄 分析论文 | `/paper https://arxiv.org/abs/...` |
| `/zotero <key>` | 📚 Zotero 导入 | `/zotero` |
| `/output` | 💾 保存产出 | `/output` |
| `/lint` | 🩺 健康检查 | `/lint` |
| `/save "msg"` | 💾 Git 提交 | `/save "导入新论文"` |
| `/rollback [N]` | ⏪ 查看/回滚 | `/rollback` |
| `/help` | ❓ 显示帮助 | `/help` |

## 知识库结构

```
D:\PKB_个人知识库\
├─ _INBOX/         待处理（不入 Git）
├─ raw/            原始资料（只增不删）
├─ wiki/           LLM 维护的结构化知识
├─ skills/         Agent 技能定义
├─ templates/      模板文件
├─ tools/          辅助脚本
├─ AGENTS.md       系统规则（AGENTS 读）
├─ COMMANDS.md     命令手册（人读）
└─ README.md       项目说明
```

## 更多信息
- 详细规则：阅读 `AGENTS.md`
- 项目说明：阅读 `README.md`
