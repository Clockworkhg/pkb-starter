# PKB Starter — Quick Start

> 5 minutes to your own LLM-powered personal knowledge base.
>
> **Version**: v0.6.2-alpha

Languages: [English](QUICKSTART.md) | [简体中文](zh-CN/QUICKSTART.md)

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
python scripts/install.py "D:\MyKB"
```

> **Path is up to you**: `D:\MyKB` is an example. You may use any path — `E:\KnowledgeBase`, `C:\Users\YourName\Documents\PKB`, `F:\ResearchKB`, etc. The first positional argument to `install.py` is your chosen target. ASCII paths are recommended. For interactive guided setup: `python scripts/install.py --interactive`

This creates:
- Full directory structure (`raw/`, `wiki/`, `_INBOX/`)
- 11 project commands in `.claude/commands/`
- Python tools: `web_pack.py`, `pkb_auto.py`, `sanitize.py`, `import_to_inbox.py`, `docs_update.py`, `pkb_update_client.py`
- `.gitignore` with security rules
- Git repository initialized

> **Note**: The `skills/` directory is created empty. Skills are part of the pkb-starter **plugin repository**, not the project template. When you install pkb-starter as a Claude Code plugin, skills become available globally. When using the project template alone (this install), you use `tools/` Python scripts directly.

## Step 3: Install Python Dependencies

```bash
cd "D:\MyKB"
pip install -r requirements.txt
```

## Step 4: Launch

```bash
cd "D:\MyKB"
claude
```

In Claude Code (project mode):
```
/project:help                          # See all commands
/project:pkb https://example.com       # Collect a web page
/project:pkb Downloads\paper.pdf       # Import a file
/project:ask transformer concept       # Search your knowledge base
```

> **Project commands**: Commands are invoked as `/project:<name>` when you `cd` into your PKB directory and run `claude`. Bare `/pkb` is only available if pkb-starter is installed as a Claude Code plugin.

## Optional: Install Skill Packs

Extend PKB with domain-specific skills from a catalog of 43 entries. You can install skills during setup or anytime later:

```bash
# During installation: choose a profile
python scripts/install.py "D:\MyKB" --profile student
python scripts/install.py "D:\MyKB" --interactive-skills   # pick individually
python scripts/install.py "D:\MyKB" --skip-skills           # core only, add later

# Anytime after installation: manage skills
python scripts/skill_manager.py --target "D:\MyKB" --list
python scripts/skill_manager.py --target "D:\MyKB" --describe deep-research-skills
python scripts/skill_manager.py --target "D:\MyKB" --install deep-research-skills
python scripts/skill_manager.py --target "D:\MyKB" --install-profile student --dry-run
python scripts/skill_manager.py --target "D:\MyKB" --audit

# Or from Claude Code
/project:skills                       # See status and available profiles
/project:skills --list                # Browse all 43 entries
/project:skills --describe <id>       # Full details for one skill
/project:skills --install <id>        # Install a single skill
/project:skills --install-profile student
/project:skills --audit               # Check installed skills
/project:skills --enable <id>         # Activate after audit
/project:skills --disable <id>        # Deactivate without deleting
```

Profiles: `core` (built-in only) | `student` (8 skills) | `research` (12) | `developer` (7) | `creator` (7) | `output` (7) | `security` (3) | `full` (24) | `custom`

Each skill shows its description, risk level, and requirements before installation.
Third-party skills are cloned to `skills/_vendor/` and never auto-executed.
Start with Core and add skills as you need them — no need to decide everything upfront.

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

## Staying Updated

When pkb-starter releases a new version on GitHub, upgrade your installed KB without reinstalling:

```bash
cd "D:\MyKB"
python tools/pkb_update_client.py              # Preview (dry-run by default)
python tools/pkb_update_client.py --apply      # Apply the update
```

Or in Claude Code: `/project:update` (dry-run by default), `/project:update --apply` to apply.

Your data (`raw/`, `wiki/`, `_INBOX/`, `skills/_vendor/`) is never touched. All config settings are preserved.

[Full Update Guide →](UPDATING.md)

---

## Need Help?
- [DESIGN.md](DESIGN.md) — Architecture deep dive
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) — Common issues
- [SECURITY.md](SECURITY.md) — Privacy & security guide
