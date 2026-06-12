# pkb-init — Initialize a new PKB

## When to Use
- User says "create a knowledge base", "setup PKB", "init knowledge base"
- First time setup in a new directory
- Clone and customize the pkb-starter template

## Instructions

### 1. Confirm target directory
Ask user for the target path. Default: current working directory or user-specified path.

### 2. Run the install script
```bash
python scripts/install.py "<target_directory>"
```

### 3. What the script does
- Creates full directory structure: `raw/`, `wiki/`, `skills/`, `tools/`, `templates/`, `_INBOX/`
- Copies template files: `AGENTS.md`, `COMMANDS.md`, `CLAUDE.md`, `index.md`, `log.md`, `.gitignore`
- Copies `.claude/commands/` (10 slash commands)
- Copies `tools/` (web_pack.py, import_to_inbox.py, pkb_auto.py, docs_update.py, sanitize.py)
- Initializes git repository
- Generates `pkb.config.json` with metadata

### 4. Post-install
Guide user:
```
✅ PKB initialized at <path>

Next steps:
  1. cd <path>
  2. claude
  3. /pkb <anything> — start adding knowledge
  4. /help — see all commands
```

## Safety Notes
- Never overwrite existing files without confirmation
- Detect existing PKB and offer migration via `scripts/migrate_existing_pkb.py`
- Never copy user's personal data from other PKB instances
