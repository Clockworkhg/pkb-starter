# /help — PKB Help

You are the PKB help agent.

## Task
Display PKB system command list and usage guide.

## Quick Start

```
/pkb <anything>    ← The only command you need to remember
```

## Command List

| Command | Purpose | Example |
|---------|---------|---------|
| `/pkb <anything>` | 🚀 Smart entry | `/pkb paper.pdf` |
| `/add <path>` | 📥 Import file/folder | `/add ~/Downloads/paper.pdf` |
| `/inbox` | 📬 View pending | `/inbox` |
| `/web <url>` | 🌐 Collect webpage | `/web https://example.com` |
| `/clip` | 📋 Collect clipboard | `/clip` |
| `/ask <question>` | 🔍 Query knowledge base | `/ask transformer concept` |
| `/output` | 💾 Save output | `/output` |
| `/lint` | 🩺 Health check | `/lint` |
| `/save "msg"` | 💾 Git commit | `/save "imported new paper"` |
| `/rollback [N]` | ⏪ View/rollback | `/rollback` |
| `/help` | ❓ Show help | `/help` |

## Knowledge Base Structure

```
PKB/
├─ _INBOX/         Pending (not in git)
├─ raw/            Raw materials (append-only)
├─ wiki/           LLM-maintained structured knowledge
├─ skills/         Agent skill definitions
├─ templates/      Template files
├─ tools/          Helper scripts
├─ AGENTS.md       System rules (for agents)
├─ COMMANDS.md     Command reference (for humans)
├─ CLAUDE.md       Quick reference (auto-loaded)
└─ README.md       Project overview
```

## More Info
- Detailed rules: `AGENTS.md`
- Project overview: `README.md`
