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

Example: `0.4.1_to_0.5.0.py`

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
| 0.5.0-alpha | 2026-06-12 | sync/update/migration workflow from baseline v0.4.1-alpha |
| 0.4.1-alpha | 2026-06-12 | Z-Skills Compatibility Module (commit 9e8d33b) — zskill_bridge, z_skills_adapter, skills_registry |
| 0.4.0 | — | Skills registry v2 |
| 0.3.0 | — | Optional skill packs |
| 0.2.0 | — | Compatibility adapters |
| 0.1.0 | — | Initial release |

### Version Notes

- **v0.4.1-alpha**: Baseline that includes the Z-Skills Compatibility Module. Users on this version have `tools/zskill_bridge.py`, `skill_adapters/z_skills_adapter.md`, `.claude/commands/skills.md` (with z-skills sections), and `docs/Z_WEB_PACK_PARITY.md`.
- **v0.5.0-alpha**: Adds the full sync/update/migration workflow. Migration from 0.4.1-alpha preserves all z-skills state, enabled_adapters, and vendor downloads.

## Backup

Before any migration, `update_pkb.py` creates a full backup in:
```
.pkb_backup/YYYYMMDD_HHMMSS/
```

If a migration fails, the backup can be restored manually.
