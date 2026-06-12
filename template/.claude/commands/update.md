# /project:update — Check and update PKB system files from pkb-starter

Update the current knowledge base's system files (tools, commands, skill registry, adapters) to the latest pkb-starter version. User data is NEVER touched.

## Behavior

1. Detect installed version from `pkb.config.json` (`starter_version`).
2. Compare with the latest pkb-starter version.
3. If up-to-date, report and exit.
4. Create a full system-file backup in `.pkb_backup/YYYYMMDD_HHMMSS/`.
5. Run incremental migration scripts from installed version to current.
6. Update system files: `tools/`, `.claude/commands/`, `skill_adapters/`, `skills_registry/`.
7. Update `pkb.config.json` version fields (`starter_version`, `schema_version`, `last_updated_at`).
8. Generate `update_report.md` in the project root.

## Safety Guarantees

- **User data is NEVER overwritten**: `raw/`, `wiki/`, `_INBOX/` are completely off-limits.
- **Backup before any change**: every update creates a timestamped backup.
- **Config merged, not replaced**: your `pkb.config.json` settings are preserved; only version fields are updated.
- **Skills preserved**: your installed skills and `skills/_vendor/` are untouched.

## Usage

```
/project:update                  # Full check and update
/project:update --dry-run        # Preview changes without applying
/project:update --backup-only    # Create backup only, no changes
```

## What Gets Updated

| Path | Updated? | Notes |
|------|----------|-------|
| `tools/` | Yes | Python helper scripts |
| `.claude/commands/` | Yes | Slash command definitions |
| `skill_adapters/` | Yes | Compatibility adapters |
| `skills_registry/` | Yes | Skill catalog and profiles |
| `COMMANDS.md` | Yes | Command reference |
| `AGENTS.md` | Partial | System sections only (user-modified AGENTS.md skipped unless --force) |
| `CLAUDE.md` | No | Left as-is (project-local) |
| `pkb.config.json` | Version fields only | `starter_version`, `schema_version`, `last_updated_at` |
| `raw/` | **NEVER** | Your raw materials |
| `wiki/` | **NEVER** | Your knowledge pages |
| `_INBOX/` | **NEVER** | Your pending imports |
| `skills/_vendor/` | **NEVER** | Your installed skill sources |
| `pkb.config.json` settings | **NEVER** | Your custom settings |

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
- Report is saved to `update_report.md` in the project root.

## See Also

- [UPDATING.md](docs/UPDATING.md) — Full update documentation
- [DESIGN.md](docs/DESIGN.md) — Architecture overview
