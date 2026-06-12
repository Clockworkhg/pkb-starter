# PKB Starter — Quick Start

> 5 minutes to your own LLM-powered personal knowledge base.

## Prerequisites

- **Claude Code** installed (`claude` command available)
- **Python 3.9+** (`python --version`)
- **Git** (`git --version`)
- Optional: **Obsidian** (for visual browsing of your wiki)

## Step 1: Clone

```bash
git clone https://github.com/pkb-starter/pkb-starter.git
cd pkb-starter
```

## Step 2: Install

```bash
python scripts/install.py "D:\MyKnowledgeBase"
```

This creates:
- Full directory structure (`raw/`, `wiki/`, `_INBOX/`)
- 11 project commands in `.claude/commands/`
- Python tools: `web_pack.py`, `pkb_auto.py`, `sanitize.py`, `import_to_inbox.py`, `docs_update.py`
- `.gitignore` with security rules
- Git repository initialized

> **Note**: The `skills/` directory is created empty. Skills are part of the pkb-starter **plugin repository**, not the project template. When you install pkb-starter as a Claude Code plugin, skills become available globally. When using the project template alone (this install), you use `tools/` Python scripts directly.

## Step 3: Install Python Dependencies

```bash
cd "D:\MyKnowledgeBase"
pip install -r requirements.txt
```

## Step 4: Launch

```bash
cd "D:\MyKnowledgeBase"
claude
```

In Claude Code (project mode):
```
/project:help                          # See all commands
/project:pkb https://example.com       # Collect a web page
/project:pkb ~/Downloads/paper.pdf     # Import a file
/project:ask transformer concept       # Search your knowledge base
```

> **v0.1.0 uses project commands**. Commands are invoked as `/project:<name>` when you `cd` into your PKB directory and run `claude`. Bare `/pkb` is only available if pkb-starter is installed as a Claude Code plugin.

## Optional: Install Skill Packs

Extend PKB with domain-specific skills from a catalog of 42 entries:

```bash
# List all available skills
python scripts/install_skills.py --list

# Install a skill profile (from pkb-starter directory)
python scripts/install_skills.py --target "D:\MyKnowledgeBase" --profile student

# Preview what would be installed
python scripts/install_skills.py --target "D:\MyKnowledgeBase" --profile research --dry-run

# Or from Claude Code
/project:skills --install student
/project:skills --list
```

Profiles: `core` (built-in only) | `student` (8 skills) | `research` (12) | `developer` (7) | `creator` (7) | `output` (7) | `security` (3) | `full` (24) | `custom`

[Full skill catalog and ecosystem →](OPTIONAL_SKILLS.md)

## Step 5: Add Your First Knowledge

```
/project:pkb https://karpathy.bearblog.dev/llm-wiki/
```

Wait ~30 seconds. The agent will:
1. Collect the web page content + images
2. Extract the main text
3. Create a wiki source-note and concept page
4. Update indices and logs
5. Health check
6. Git commit

Open `wiki/concepts/` in Obsidian to see the result.

## Daily Workflow

```
/project:pkb <anything>     # Throw anything in — auto-processed
/project:ask <question>     # Query your knowledge
/project:lint               # Health check
/project:save "message"     # Git commit with auto doc update
```

That's it! You now have a living, growing personal knowledge base maintained by LLM.

---

## Need Help?
- [DESIGN.md](DESIGN.md) — Architecture deep dive
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) — Common issues
- [SECURITY.md](SECURITY.md) — Privacy & security guide
