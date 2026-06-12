# PKB Starter — Migrations

Version-to-version incremental migration scripts for installed PKB knowledge bases.

## How Migrations Work

1. `scripts/update_pkb.py` detects the installed `starter_version` in `pkb.config.json`.
2. It runs all migration scripts between the installed version and the current pkb-starter version.
3. Each migration script transforms only system files (tools, commands, registry, adapters).
4. User data (`raw/`, `wiki/`, `_INBOX/`) is NEVER touched.

## Naming Convention

```
<VERSION_FROM>_to_<VERSION_TO>.py
```

Example: `0.4.0_to_0.5.0.py`

## What a Migration Script Does

- Adds new system files introduced in the target version.
- Updates existing system files with breaking changes.
- Removes deprecated files.
- Transforms `pkb.config.json` schema if needed.
- Reports what was changed.

## What a Migration Script MUST NOT Do

- Read, write, or delete files in `raw/`, `wiki/`, or `_INBOX/`.
- Modify user configuration values in `pkb.config.json`.
- Access the network.
- Execute shell commands outside the target PKB directory.

## Writing a New Migration

1. Copy the previous migration as a template.
2. Implement `upgrade(target_path)` — the main transformation.
3. Implement `dry_run(target_path)` — print what WOULD change.
4. Implement `can_migrate(target_path)` — check preconditions.
5. Test with `python scripts/update_pkb.py <test-pkb> --dry-run --from-version X --to-version Y`.

## Migration History

| Version | Date | Changes |
|---------|------|---------|
| 0.5.0 | 2026-06-12 | starter_version + schema_version fields, update command |
| 0.4.0 | — | Skills registry v2 |
| 0.3.0 | — | Optional skill packs |
| 0.2.0 | — | Compatibility adapters |
| 0.1.0 | — | Initial release |

## Backup

Before any migration, `update_pkb.py` creates a full backup in:
```
.pkb_backup/YYYYMMDD_HHMMSS/
```

If a migration fails, the backup can be restored manually.
