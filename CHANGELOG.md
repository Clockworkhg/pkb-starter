# Changelog

All notable changes to PKB Starter.

---

## [0.5.0-alpha] — 2026-06-12

This alpha release turns PKB Starter from a one-time project template into a maintainable local LLM Wiki system.

### Added

**Update & Migration Workflow**
- `/project:update` command — check and update installed PKB system files
- `scripts/update_pkb.py` — safe updater with backup, migration, and report
- `migrations/` — incremental version migration scripts (0.4.1 -> 0.5.0)
- Automatic backup to `.pkb_backup/YYYYMMDD_HHMMSS/` before every update
- `update_report.md` generated after each update with full change audit

**Private PKB -> pkb-starter Sync Pipeline**
- `starter_sync_manifest.json` — controlled file mappings with never_sync rules
- `tools/sync_to_starter.py` — sanitized one-way sync with dry-run and diff
- `sync_report.md` — per-entry sync audit with skip/block reasons
- License-sensitive path detection and blocking

**Protected Paths & State Preservation**
- Explicit protection for `raw/`, `wiki/`, `_INBOX/`, `skills/_vendor/`, `.pkb_local/`
- `zskill_audit_report.md` and `skill_manager_report.md` never overwritten
- Skills state fully preserved across updates:
  - `installed_profiles`, `installed_skills`, `enabled_skills`, `disabled_skills`
  - `vendor_downloads`, `enabled_adapters`, `pending_audit`

**Version Tracking**
- `pkb.config.json` now includes `starter_version`, `schema_version`, `last_updated_at`
- New installs default to `starter_version: "0.5.0-alpha"`
- Version comparison handles `-alpha`, `-beta`, `-rc` suffixes

**Documentation**
- `docs/UPDATING.md` — complete update + sync guide
- `CHANGELOG.md` — this file

### Changed

- Migration baseline: v0.4.1-alpha (Z-Skills Compatibility Module, commit `9e8d33b`)
- `scripts/install.py` now writes `starter_version`, `schema_version`, `last_updated_at`
- `.gitignore` (root and template) includes `.pkb_backup/`

---

## [0.4.1-alpha] — 2026-06-12

### Added

**Z-Skills Compatibility Module**
- `tools/zskill_bridge.py` — bridge for optional z-skills integration
- `skill_adapters/z_skills_adapter.md` — z-skills output routing
- `docs/Z_WEB_PACK_PARITY.md` — web_pack capability comparison
- z-web-pack-local adapter in skills registry
- Audit report: `zskill_audit_report.md`

**Principles**
- No third-party code redistribution — user must explicitly opt in
- Three-stage lifecycle: install -> audit -> enable
- Bridge architecture: locate, audit, status, run, import-output, patch
- Default collector unchanged (built-in web_pack is default)

---

## [0.4.0] — 2026-06

### Added

**Runtime Optional Skill Manager**
- `scripts/skill_manager.py` — manage skills on live PKB installation
- `/project:skills` command with full lifecycle:
  - `--list` — browse catalog
  - `--describe <id>` — detailed view
  - `--install <id>` — single skill
  - `--install-profile <name>` — batch install
  - `--audit` — license and structure check
  - `--enable / --disable` — toggle without delete
- State model in `pkb.config.json` skills section
- Skill lifecycle: install -> audit -> enable (three stages)
- Risk classification: low / medium / high / reference_only

---

## [0.3.0] — 2026-06

### Added

**Expanded Skill Registry**
- 43 catalog entries across 9 external repos
- `skills_registry/skill_catalog.json` with full metadata
- `skills_registry/profiles.json` with 9 profiles
- Profile presets: Core (0), Student (8), Research (12), Developer (7), Creator (7), Output (7), Security (3), Full (24), Custom (interactive)
- `scripts/install.py --profile <name>` during setup
- `scripts/install_skills.py` for post-install skill management

---

## [0.2.0] — 2026-06

### Added

**Optional Skill Packs + Compatibility Adapters**
- `skills/` directory with 6 core skills (pkb-ask, pkb-auto, pkb-inbox, pkb-init, pkb-lint, pkb-sanitize)
- `template/skill_adapters/` — routing rules for skill output
- Adapter pattern: maps skill output -> raw/wiki paths
- Optional third-party skill source tracking

---

## [0.1.0] — 2026-06

### Added

**Initial Release**
- Three-layer architecture: raw/ -> wiki/ -> skills/
- Claude Code project template with `.claude/commands/`
- `/project:pkb` — smart ingest (auto-detect URL / file / text)
- `/project:web` — web collection
- `/project:inbox` — process pending files
- `/project:ask` — search knowledge base
- `/project:lint` — health check
- `/project:save` — git commit with auto doc update
- `/project:rollback` — git history rollback
- `/project:sanitize` — privacy scan
- `scripts/install.py` — one-shot installer
- `scripts/check_env.py` — environment verification
- `scripts/migrate_existing_pkb.py` — upgrade existing PKB
- `tools/web_pack.py` — structured web collection
- `tools/import_to_inbox.py` — file import with sensitive data detection
- `tools/pkb_auto.py` — health check and auto-pipeline
- `tools/sanitize.py` — privacy pattern scanner
- `tools/docs_update.py` — documentation freshness checker
- Obsidian-compatible `[[wikilink]]` syntax
- Autopilot by default — no "next step?" prompts
- Git-native: every change is a commit
- GBK-compatible Windows tooling
