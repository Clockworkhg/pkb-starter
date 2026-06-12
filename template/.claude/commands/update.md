# /project:update — Check and update PKB system files from pkb-starter

Update the current knowledge base's system files (tools, commands, skill registry, adapters) to the latest pkb-starter version. User data is NEVER touched.

## Language Detection

Before executing, read `pkb.config.json`. If `language` / `output_language` is set to `zh-CN`:
1. Update reports, migration summaries, and status messages default to Simplified Chinese.
2. `pkb.config.json` language fields (`language`, `wiki_language`, `output_language`) are NEVER modified by the update process.
3. User-customized Chinese documents (README, AGENTS, COMMANDS) are preserved and not overwritten.
4. Technical version numbers, file paths, and command names remain in English.

## Update Modes

### Mode 1: Online update (recommended for most users)

Uses `tools/pkb_update_client.py` to pull the latest pkb-starter from the configured repo:

```
/project:update                  # Preview changes (dry-run by default)
/project:update --apply          # Apply changes after review
```

This reads `starter_repo_url` from `pkb.config.json`, clones/pulls to `.pkb_system/starter_cache/`, and runs `update_pkb.py` against the current KB.

### Mode 2: Local starter update (for users with a local pkb-starter clone)

If you already have a local pkb-starter repository:

```
python tools/pkb_update_client.py --starter-path "D:\pkb-starter" --dry-run
python tools/pkb_update_client.py --starter-path "D:\pkb-starter"
```

### Mode 3: Direct update (advanced)

```
python scripts/update_pkb.py "<KB_ROOT>" --dry-run
```

## Behavior

1. Run `python tools/pkb_update_client.py --dry-run` by default.
2. If user confirms (`--apply`), run `python tools/pkb_update_client.py`.
3. Client detects installed version from `pkb.config.json` (`starter_version`).
4. Compares with the latest pkb-starter version.
5. If up-to-date, reports and exits.
6. Creates a full system-file backup in `.pkb_backup/YYYYMMDD_HHMMSS/`.
7. Runs incremental migration scripts from installed version to current.
8. Updates system files: `tools/`, `.claude/commands/`, `skill_adapters/`, `skills_registry/`, `docs/`.
9. Updates `pkb.config.json` version fields (`starter_version`, `schema_version`, `last_updated_at`).
10. Generates `update_report.md` and `update_client_report.md` in the project root.

## Safety Guarantees

- **User data is NEVER overwritten**: `raw/`, `wiki/`, `_INBOX/` are completely off-limits.
- **Skills preserved**: `skills/_vendor/` is untouched.
- **Local patches preserved**: `.pkb_local/` is untouched.
- **Backup before any change**: every update creates a timestamped backup.
- **Config merged, not replaced**: your `pkb.config.json` settings are preserved; only version fields are updated.
- **Install path preserved**: `install_path` is never modified.
- **Repo URL preserved**: `starter_repo_url` is never modified.
- **Language fields preserved**: `language`, `wiki_language`, `output_language` are never modified.

## Usage

```
/project:update                  # Dry-run preview (safe, no changes)
/project:update --apply          # Apply update after review
```

For custom repo or version:
```
python tools/pkb_update_client.py --repo-url https://github.com/<your-fork>/pkb-starter.git
python tools/pkb_update_client.py --checkout v0.6.2-alpha
```

## What Gets Updated

| Path | Updated? | Notes |
|------|----------|-------|
| `tools/` | Yes | Python helper scripts (including pkb_update_client.py) |
| `.claude/commands/` | Yes | Slash command definitions |
| `skill_adapters/` | Yes | Compatibility adapters |
| `skills_registry/` | Yes | Skill catalog and profiles |
| `docs/` | Yes | System documentation (only adds missing) |
| `COMMANDS.md` | Yes | Command reference |
| `AGENTS.md` | Partial | System sections only (user-modified AGENTS.md skipped unless --force) |
| `CLAUDE.md` | No | Left as-is (project-local) |
| `pkb.config.json` | Version fields only | `starter_version`, `schema_version`, `last_updated_at` |
| `raw/` | **NEVER** | Your raw materials |
| `wiki/` | **NEVER** | Your knowledge pages |
| `_INBOX/` | **NEVER** | Your pending imports |
| `skills/_vendor/` | **NEVER** | Your installed skill sources |
| `.pkb_local/` | **NEVER** | Your local patches and settings |

## Rollback

If an update fails, restore from the backup:

```
cp -r .pkb_backup/<LATEST_TIMESTAMP>/* .
```

Each backup contains: `tools/`, `.claude/commands/`, `skill_adapters/`, `skills_registry/`, `COMMANDS.md`, `AGENTS.md`, `pkb.config.json`.

## Notes

- Requires `git` installed in the target PKB (used for safety checks).
- Migrations are incremental and idempotent — running twice is safe.
- This command itself is updated by the migration process.
- Report is saved to `update_report.md` and `update_client_report.md` in the project root.
- Set `starter_repo_url` in `pkb.config.json` to your pkb-starter fork for online updates.

## See Also

- [UPDATING.md](docs/UPDATING.md) — Full update documentation
- [DESIGN.md](docs/DESIGN.md) — Architecture overview
