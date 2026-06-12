# PKB Starter — Updating

Languages: [English](UPDATING.md) | [简体中文](zh-CN/UPDATING.md)

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

### Version History

- **v0.6.5-alpha**: Current. Adds optional z-web-pack compatibility layer (`tools/pkb_compat/`), collector health check (`tools/check_collectors.py`), and bridge execution support. Built-in web_pack remains the default.
- **v0.6.4-alpha**: Fixes default starter_repo_url placeholder, official update source for fresh installs.
- **v0.6.3-alpha**: Fresh install self-consistency, docs-update safety, recovery from v0.6.2-alpha.
- **v0.6.2-alpha**: Custom install paths, built-in update client, enhanced config preservation.
- **v0.5.0-alpha**: Adds sync/update/migration workflow. Baseline is v0.4.1-alpha.
- **v0.4.1-alpha**: Z-Skills Compatibility Module (commit 9e8d33b). Introduced `tools/zskill_bridge.py`, `skill_adapters/z_skills_adapter.md`, `docs/Z_WEB_PACK_PARITY.md`, and skills_registry.

### Language Templates

PKB Starter v0.6.0-alpha adds Chinese (zh-CN) localization support. Users can install with `--lang zh-CN` or `--lang bilingual`.

During update:

- `update_pkb.py` does NOT overwrite user-customized README, AGENTS, or COMMANDS files, regardless of language.
- The `language`, `wiki_language`, and `output_language` fields in `pkb.config.json` are preserved during update.
- If new language template files are added in a later version, `update_pkb.py` only adds missing files — it never overwrites user-modified documents.
- Bilingual installations keep both English (`*.md`) and Chinese (`*.zh-CN.md`) root documents.
- Wiki content language is controlled by `wiki_language` in `pkb.config.json`, not by which template was installed.

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

## Recovering from v0.6.2-alpha

If you installed v0.6.2-alpha and are seeing stale docs or malformed version strings, see the dedicated recovery guide: [RECOVER_FROM_0.6.2_ALPHA.md](RECOVER_FROM_0.6.2_ALPHA.md).

Quick recovery:
```bash
python tools/pkb_update_client.py --checkout v0.6.4-alpha          # dry-run (safe)
python tools/pkb_update_client.py --checkout v0.6.4-alpha --apply  # apply changes
```

---

## For Installed PKB Users

When pkb-starter releases a new version on GitHub, your installed knowledge base can be upgraded **without reinstalling**. All your data, config, and skills are preserved.

### Update Modes

#### Mode 1: Update client (recommended)

The update client is installed in every KB at `tools/pkb_update_client.py`:

```bash
cd "D:\MyKB"
python tools/pkb_update_client.py              # Preview changes (safe, dry-run by default)
python tools/pkb_update_client.py --apply      # Apply update
```

This reads `starter_repo_url` from `pkb.config.json`, clones/pulls the repo to `.pkb_system/starter_cache/`, then runs the updater.

Or in Claude Code:
```
/project:update                  # Dry-run by default
/project:update --apply          # Apply after review
```

#### Mode 2: Local starter path

If you have a local pkb-starter clone:

```bash
python tools/pkb_update_client.py --starter-path "D:\pkb-starter"            # dry-run (safe)
python tools/pkb_update_client.py --starter-path "D:\pkb-starter" --apply    # apply changes
```

#### Mode 3: Direct update_pkb.py (advanced)

```bash
python scripts/update_pkb.py "D:\MyKB" --dry-run
python scripts/update_pkb.py "D:\MyKB"
```

### Checking Your Version

```bash
cat pkb.config.json | grep starter_version
```

### Configuring starter_repo_url

Fresh v0.6.4-alpha installs default to the official starter repo:

```json
{
  "starter_repo_url": "https://github.com/Clockworkhg/pkb-starter.git"
}
```

Fork users can change this to their own fork URL. If your config still shows the old `<your-username>` placeholder (from v0.6.2-alpha), fix it with:

```bash
python tools/pkb_update_client.py --repo-url "https://github.com/Clockworkhg/pkb-starter.git" --checkout v0.6.4-alpha --apply
```

After `--apply`, the repo URL is saved to `pkb.config.json` for future updates. If not set, use `--repo-url` or `--starter-path` with the update client.

### What the Update Does

1. Detect your current version from `pkb.config.json`.
2. Create a backup in `.pkb_backup/`.
3. Run any pending migrations.
4. Update system files.
5. Generate `update_report.md` and `update_client_report.md`.

### Preview Before Updating

```
/project:update                  # Dry-run by default — preview only
/project:update --apply          # Apply changes after review
```

The update client defaults to dry-run. No changes are made without `--apply`.

### Manual Update

If you prefer to update manually:

```bash
cd D:\pkb-starter
git pull
python scripts/update_pkb.py "D:\MyKB" --dry-run    # Preview
python scripts/update_pkb.py "D:\MyKB"               # Apply
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
- `skills/_vendor/` — Your installed skill source code (including z-skills vendor directory)
- `skills/_vendor/z-skills/` — Z-skills local clone, never touched by update
- `.pkb_local/` — Your local configuration
- `.pkb_local/patches/` — Your local patches, never overwritten
- `zskill_audit_report.md` — Z-skills audit report, never overwritten
- `skill_manager_report.md` — Skill manager report, never overwritten
- `pkb.config.json` user settings — Your preferences, profiles, enabled skills
- `pkb.config.json` skills state — `installed_profiles`, `installed_skills`, `enabled_skills`, `disabled_skills`, `vendor_downloads`, `enabled_adapters`, `pending_audit` are preserved
- Any file not explicitly listed as a system file

### Z-Skills State Preservation

If you have z-skills installed and z-web-pack-local enabled:
- `skills/_vendor/` is **never** touched during update
- `enabled_adapters` in `pkb.config.json` is preserved (your `z-web-pack-local` stays enabled)
- `vendor_downloads` is preserved (your z-skills clone path stays)
- `zskill_audit_report.md` is never overwritten
- `.pkb_local/patches/` is never overwritten

The update only touches PKB system files — it never updates third-party vendor code.

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
1. Personal paths are replaced (`<PRIVATE_PKB_ROOT>` -> `<PKB_ROOT>`)
2. Email addresses are replaced (`user@example.com` -> `<USER_EMAIL>`)
3. User name variants are replaced (`JohnDoe` -> `<USER_NAME>`)
4. Remaining generic emails are caught and replaced
5. Sensitive keywords (token, password, api_key) are flagged

> **Placeholder notes**: `<PRIVATE_PKB_ROOT>` represents the maintainer's private PKB directory. `<PKB_STARTER_ROOT>` represents the public template repository. Regular users do not need to run the private PKB → starter sync flow — this section documents the maintainer pipeline only.

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
