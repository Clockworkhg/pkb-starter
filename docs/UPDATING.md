# PKB Starter — Updating

How pkb-starter itself updates, and how installed PKB users update their system files.

## Table of Contents

1. [For pkb-starter Maintainers](#for-pkb-starter-maintainers)
2. [For Installed PKB Users](#for-installed-pkb-users)
3. [What Gets Updated](#what-gets-updated)
4. [What Is Never Overwritten](#what-is-never-overwritten)
5. [Backup and Rollback](#backup-and-rollback)
6. [Private PKB -> pkb-starter Sync](#private-pkb---pkb-starter-sync)
7. [Why Not Copy the Whole PKB?](#why-not-copy-the-whole-pkb)

---

## For pkb-starter Maintainers

### Syncing from Private PKB

The private PKB repository contains the canonical implementations. Changes flow **one-way**: PKB -> pkb-starter.

```
Private PKB (canonical)          pkb-starter (public template)
=======================          =============================
AGENTS.md          ----sync----> template/AGENTS.md
COMMANDS.md        ----sync----> template/COMMANDS.md
.claude/commands/* ----sync----> template/.claude/commands/*
tools/*.py         ----sync----> template/tools/*
```

**How to sync:**

```bash
# In private PKB:
python tools/sync_to_starter.py --target "D:\pkb-starter" --dry-run
python tools/sync_to_starter.py --target "D:\pkb-starter" --diff
python tools/sync_to_starter.py --target "D:\pkb-starter"

# Review sync_report.md before committing
git -C "D:\pkb-starter" diff
git -C "D:\pkb-starter" commit -am "sync from private PKB: <what changed>"
```

**Safety**: The sync tool (`starter_sync_manifest.json`) defines exactly what CAN sync. Everything else is blocked. Personal paths, emails, and sensitive patterns are sanitized automatically.

### Version Bump Checklist

1. Update `CURRENT_VERSION` in `scripts/update_pkb.py`.
2. Create new migration script in `migrations/`.
3. Update `docs/UPDATING.md` (this file).
4. Update `README.md` version references.
5. Sync from private PKB if system files changed.
6. Test: `python scripts/update_pkb.py "<test-install>" --dry-run`.
7. Tag and release.

### Migration Script Requirements

Migration scripts in `migrations/` must:
- Implement `can_migrate(target)` -> bool
- Implement `upgrade(target)` -> list of changes
- Implement `dry_run(target)` -> prints what would change
- NEVER touch `raw/`, `wiki/`, `_INBOX/`
- Be idempotent (safe to run multiple times)
- Use ASCII output for GBK compatibility

---

## For Installed PKB Users

### Checking Your Version

```bash
cat pkb.config.json | grep starter_version
```

Or use the command:

```
/project:update --dry-run
```

### Updating

```
/project:update
```

This will:
1. Detect your current version.
2. Create a backup in `.pkb_backup/`.
3. Run any pending migrations.
4. Update system files.
5. Generate `update_report.md`.

### Preview Before Updating

```
/project:update --dry-run
```

Shows exactly what would change without making any changes.

### Manual Update

If you prefer to update manually:

```bash
cd D:\pkb-starter
git pull
python scripts/update_pkb.py "D:\MyKB" --dry-run
python scripts/update_pkb.py "D:\MyKB"
```

---

## What Gets Updated

| Path | Description | Updated? |
|------|-------------|----------|
| `tools/` | Python helper scripts | **Yes** |
| `.claude/commands/` | Slash command definitions | **Yes** |
| `skill_adapters/` | Compatibility adapter files | **Yes** |
| `skills_registry/` | Skill catalog and profiles | **Yes** |
| `COMMANDS.md` | Command reference | **Yes** |
| `AGENTS.md` | System rules (partial) | **Conditional** |
| `pkb.config.json` | Version/time fields only | **Version fields only** |
| `CLAUDE.md` | Quick reference | **No** (yours is project-local) |

---

## What Is Never Overwritten

These directories and files are **completely off-limits** to the update process:

- `raw/` — Your raw materials (web collections, PDFs, files)
- `wiki/` — Your knowledge pages (concepts, sources, projects)
- `_INBOX/` — Your pending imports
- `skills/_vendor/` — Your installed skill source code
- `.pkb_local/` — Your local configuration
- `pkb.config.json` user settings — Your preferences, profiles, enabled skills
- Any file not explicitly listed as a system file

---

## Backup and Rollback

### Automatic Backup

Every update creates a timestamped backup:

```
.pkb_backup/
  20260612_143052/
    tools/
    .claude/commands/
    skill_adapters/
    skills_registry/
    COMMANDS.md
    AGENTS.md
    pkb.config.json
```

### Manual Backup

```
/project:update --backup-only
```

### Rollback

If an update causes issues:

```bash
# Find the latest backup
ls .pkb_backup/

# Restore system files
cp -r .pkb_backup/20260612_143052/* .

# Verify
/project:lint
```

### Git-Based Rollback

If your PKB uses git (recommended):

```bash
git diff  # Review changes
git checkout -- tools/ .claude/commands/  # Revert specific paths
# Or full rollback:
git reset --hard HEAD~1
```

---

## Private PKB -> pkb-starter Sync

The maintainer's private PKB is the canonical source for system files. Changes flow through a controlled, sanitized pipeline:

```
Private PKB                    Sync Tool                     pkb-starter
=======================        =========                     =============
                               1. Read manifest
AGENTS.md                      2. Check never_sync           template/AGENTS.md
COMMANDS.md                    3. Sanitize (paths, email)    template/COMMANDS.md
.claude/commands/pkb.md        4. Scan sensitive keywords    template/.claude/commands/pkb.md
tools/pkb_auto.py              5. License check              template/tools/pkb_auto.py
                               6. Write (if safe)
                               7. Generate report
```

### Manifest Control

`starter_sync_manifest.json` in the private PKB defines:
- **mappings**: Exact file-to-file mappings (only these sync)
- **never_sync**: Paths hard-blocked even if in mappings
- **sanitize_patterns**: Personal info -> placeholder replacements
- **license_sensitive_paths**: Paths requiring extra license checks

### Sanitization

Before any file reaches pkb-starter:
1. Personal paths are replaced (`D:\PKB_个人知识库` -> `<PKB_ROOT>`)
2. Email addresses are replaced (`user@example.com` -> `<USER_EMAIL>`)
3. User name variants are replaced (`Hershel` -> `<USER_NAME>`)
4. Remaining generic emails are caught and replaced
5. Sensitive keywords (token, password, api_key) are flagged

### What Cannot Sync

The sync manifest blocks:
- All of `raw/` (immutable raw materials)
- All of `wiki/` (personal knowledge pages)
- All of `_INBOX/` (pending imports)
- `skills/_vendor/` (third-party skill code)
- `pkb.config.json` (personal configuration)
- `.env`, `.pkb_local/` (local secrets and settings)
- `.claude/settings.json` (personal Claude Code settings)
- Test directories and temporary files

---

## Why Not Copy the Whole PKB?

You might wonder: "Why not just copy the entire private PKB to pkb-starter?"

1. **Privacy**: The private PKB contains your actual knowledge, source notes, project pages, and personal materials. These should never be exposed.

2. **Security**: API keys, tokens, and credentials may exist in configuration files. The sync pipeline catches these; a bulk copy would not.

3. **License Compliance**: The private PKB may contain third-party skills and vendor code. License checks prevent accidental redistribution.

4. **Version Control**: pkb-starter is a template, not a knowledge base. It should be clean, minimal, and ready for new users to install.

5. **Maintenance**: Selective sync means pkb-starter only receives polished, reviewed system files — not works-in-progress.

6. **Separation of Concerns**: The private PKB is a living knowledge base. pkb-starter is a stable distribution point. Different repositories, different purposes.
