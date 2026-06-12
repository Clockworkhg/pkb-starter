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
/project:update --doctor          # Diagnostic checks only (no changes)
```

This reads `starter_repo_url` from `pkb.config.json`, clones/pulls to `.pkb_system/starter_cache/`, and runs `update_pkb.py` against the current KB.

### Mode 2: Local starter update (for users with a local pkb-starter clone)

If you already have a local pkb-starter repository:

```
python tools/pkb_update_client.py --starter-path "D:\pkb-starter"            # dry-run (safe)
python tools/pkb_update_client.py --starter-path "D:\pkb-starter" --apply    # apply changes
```

### Mode 3: Direct update (advanced)

```
python scripts/update_pkb.py "<KB_ROOT>" --dry-run
```

## Version Discovery

The update client ALWAYS refreshes remote tags before checking versions:

1. `git fetch origin --tags --force` in `.pkb_system/starter_cache/` (always runs)
2. `git ls-remote --tags` against the configured `starter_repo_url`
3. Version tags sorted using semantic version comparison (`v0.6.4-alpha` < `v0.6.5-alpha` < `v0.6.6-alpha`)
4. Output shows: installed version, latest remote tag, selected checkout, cache path, cache refresh status

**The update client does NOT rely on stale cache to determine latest.** It fetches remote tags on every run.

## Behavior

1. **Verify CWD**: If the current working directory is inside `.pkb_system/starter_cache/`, abort and tell the user to `cd` to the KB root.
2. Run `python tools/pkb_update_client.py` by default (dry-run, no files changed).
3. Client fetches remote tags and discovers the latest version.
4. Client displays: installed version, latest remote tag, selected checkout, cache path.
5. Client refreshes starter cache (`git fetch --tags --force`) if needed.
6. Client checks out the latest tag (or user-specified `--checkout` ref) in the cache.
7. Runs `update_pkb.py` from the cache against the KB root (**cwd = KB root, NOT cache**).
8. `update_pkb.py` compares installed version with its `CURRENT_VERSION` and applies updates if newer.
9. If up-to-date, reports and exits.
10. Creates a full system-file backup in `.pkb_backup/YYYYMMDD_HHMMSS/`.
11. Runs incremental migration scripts from installed version to current.
12. Updates system files: `tools/`, `.claude/commands/`, `.claude/hooks/`, `skill_adapters/`, `skills_registry/`, `docs/`.
13. Updates `pkb.config.json` version fields (`starter_version`, `schema_version`, `last_updated_at`).
14. Generates `update_report.md` and `update_client_report.md` in the KB root.
15. On `--apply`, checks and repairs any hook paths that reference `.pkb_system/starter_cache/`.

## Doctor Mode

Run diagnostic checks to verify update system health:

```
/project:update --doctor
python tools/pkb_update_client.py --doctor
python tools/pkb_update_client.py --doctor --json    # Machine-readable output
```

Checks performed:
1. **cwd_is_kb_root** — Current working directory is the KB root (not inside starter_cache)
2. **pkb_config_exists** — `pkb.config.json` exists
3. **starter_repo_url_valid** — `starter_repo_url` is set and not a placeholder
4. **starter_cache_exists** — `.pkb_system/starter_cache/` exists and is a git repo
5. **cache_head** — Current HEAD/tag of the cache
6. **remote_latest_tag** — Latest version tag on the remote
7. **settings_json_exists** — `.claude/settings.json` exists
8. **hooks_path_ok** — Hook commands do NOT reference `.pkb_system/starter_cache/`
9. **hook_05_stop_exists** — `.claude/hooks/05_stop.py` exists
10. **bun_non_blocking** — Note that "Bun not found" is a non-blocking external hook issue

## Safety Guarantees

- **User data is NEVER overwritten**: `raw/`, `wiki/`, `_INBOX/` are completely off-limits.
- **Skills preserved**: `skills/_vendor/` is untouched.
- **Local patches preserved**: `.pkb_local/` is untouched.
- **Backup before any change**: every update creates a timestamped backup.
- **Config merged, not replaced**: your `pkb.config.json` settings are preserved; only version fields are updated.
- **Install path preserved**: `install_path` is never modified.
- **Repo URL preserved**: `starter_repo_url` is never modified.
- **Language fields preserved**: `language`, `wiki_language`, `output_language` are never modified.
- **Hook paths preserved**: `.claude/settings.json` is NEVER written by the update process. Hook commands are kept as KB-relative paths (e.g., `python .claude/hooks/05_stop.py`).
- **Dry-run safe**: Default mode makes NO changes to KB files. Git cache refresh in `.pkb_system/` is a cache operation, not a KB modification.

## CWD Safety

The update client checks that it is running from the KB root directory:

- If CWD is inside `.pkb_system/starter_cache/`, the client ABORTS and tells the user to `cd` to the KB root.
- Git operations run with `cwd=cache_dir` (subprocess only, never changes global CWD).
- `update_pkb.py` runs with **cwd = KB root** so hooks, settings, and paths all resolve correctly.
- Claude Code MUST be started from the KB root directory for hooks to work correctly.

## "Bun not found" Error

If you see "Bun not found" during `/update`:

- This is a **non-blocking external hook** issue. PKB Starter does NOT use or require Bun.
- All PKB hooks are Python 3.9+. The "Bun not found" message comes from your global Claude Code hook settings or another plugin.
- It does NOT indicate a PKB update failure. The update proceeds normally.
- To suppress: check `~/.claude/settings.json` (or `%USERPROFILE%\.claude\settings.json`) for hooks referencing `bun`.

## Usage

```
/project:update                  # Dry-run preview (safe, no changes)
/project:update --apply          # Apply update after review
/project:update --doctor          # Diagnostic checks only
```

For custom repo or version:
```
python tools/pkb_update_client.py --repo-url https://github.com/<your-fork>/pkb-starter.git
python tools/pkb_update_client.py --checkout v0.6.5-alpha
python tools/pkb_update_client.py --checkout v0.6.6-alpha --apply
```

## What Gets Updated

| Path | Updated? | Notes |
|------|----------|-------|
| `tools/` | Yes | Python helper scripts (including pkb_update_client.py) |
| `.claude/commands/` | Yes | Slash command definitions |
| `.claude/hooks/` | Yes | Harness hook scripts |
| `skill_adapters/` | Yes | Compatibility adapters |
| `skills_registry/` | Yes | Skill catalog and profiles |
| `docs/` | Yes | System documentation (only adds missing) |
| `COMMANDS.md` | Yes | Command reference |
| `AGENTS.md` | Partial | System sections only (user-modified AGENTS.md skipped unless --force) |
| `CLAUDE.md` | No | Left as-is (project-local) |
| `.claude/settings.json` | **NEVER** | Your personal Claude Code settings |
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

Each backup contains: `tools/`, `.claude/commands/`, `.claude/hooks/`, `skill_adapters/`, `skills_registry/`, `COMMANDS.md`, `AGENTS.md`, `pkb.config.json`.

## Notes

- Requires `git` installed on the system.
- Migrations are incremental and idempotent — running twice is safe.
- This command itself is updated by the migration process.
- Report is saved to `update_report.md` and `update_client_report.md` in the KB root.
- Set `starter_repo_url` in `pkb.config.json` to your pkb-starter fork for online updates.
- **Start Claude Code from the KB root directory** for hooks to work correctly.
- **If `/update` reports "Already up-to-date" but you know a newer version exists**, run with `--checkout <new-version>` or use `--doctor` to diagnose.

## See Also

- [UPDATING.md](docs/UPDATING.md) — Full update documentation
- [TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) — Troubleshooting guide
- [DESIGN.md](docs/DESIGN.md) — Architecture overview
