# Changelog

All notable changes to PKB Starter.

---

## [0.6.7-alpha] — 2026-06-13

### Added — MarkItDown Document Ingestion (Phase 1.5)

- Added `tools/markitdown_convert.py` — local document-to-Markdown pre-extraction engine (PDF, DOCX, PPTX, XLSX, XLS).
- Added `tools/pkb_ingest.py` — local file ingest orchestrator (import → MarkItDown → cache → wiki).
- Added conversion cache (`.pkb-cache/extractions/`) — avoids repeated extraction.
- Added runtime version detection via `importlib.metadata.version("markitdown")`.
- Added `ExtractionResult` and `IngestResult` metadata for extraction tracking.
- Added fallback state machine: MarkItDown success → LLM Read from cache; MarkItDown failure → LLM direct read from `_INBOX`; still fails → `_PENDING_CONVERSION.md`.
- Added dependency missing graceful degradation (MarkItDown is optional).
- Added DOCX, PDF, PPTX, XLSX, XLS test fixtures and 89 regression tests.
- Added `requirements-markitdown.txt` with pinned optional dependencies.
- Legacy `.doc` returns explicit `legacy_doc_unsupported` status (not silently ignored).
- OCR not enabled by default (Phase 2+).

### Added — Web Pack Dynamic Content Fallback (v3.1)

- Added `tools/content_quality.py` — content quality scoring to decide when Playwright fallback is needed.
- Added `tools/playwright_renderer.py` — optional Playwright Chromium DOM rendering fallback.
- Added `tools/network_capture.py` — XHR/Fetch network response candidate extraction.
- Added `tools/network_content.py` — network body candidate extraction with deduplication.
- Added `tools/selection_engine.py` — three-way selector: HTTP static → Playwright DOM → Playwright Network.
- Added `--render` flag: enables Playwright fallback only when static extraction quality is insufficient.
- Added `--headed` flag: visible browser window for manual login (auto-enables `--render`).
- Added `--debug-network` flag: sanitized network diagnostics (no body/headers/cookies output).
- Added `requirements-playwright.txt` with Playwright optional dependencies.
- Added 6 test files: 145 unit tests + 10 Chromium integration tests.
- Added 4 dynamic site test fixtures (local HTTP server for integration testing).
- Sensitive URL parameter sanitization in debug and network capture output.
- Default static web collection behavior unchanged — Chromium not launched unless quality gates trigger.
- PKB-dedicated browser profile (not user's daily Chrome profile); safe mode does not persist login state.
- App-only pages may still be uncollectable; xiaoheihe and similar sites are validation cases, not guarantees.

### Fixed

- `--force` sync no longer corrupts binary test fixtures on re-sync.
- Test import paths corrected for pkb-starter directory layout (tests at `tools/tests/`).

### Safety

- Web Pack `--render` does NOT bypass login, CAPTCHA, or access controls.
- `--debug-network` does NOT save response body, headers, or cookies.
- Private PKB is NEVER pushed; only pkb-starter receives public commits.
- All sensitive patterns in sync source are sanitized before reaching public repository.

---

## [0.6.6-alpha] — 2026-06-13

### Fixed

- Fixed update client failing to detect newer remote tags (e.g. v0.6.5-alpha not found from v0.6.4-alpha).
- Fixed stale starter cache causing `/update` to report the installed version as latest.
- Fixed update flows that could resolve Claude hook paths under `.pkb_system/starter_cache/`.
- Fixed `update_pkb.py` running with `cwd` in starter cache instead of KB root — now uses `cwd=KB_ROOT`.
- `pkb_update_client.py` now always fetches remote tags (`git fetch --tags --force`) before checking versions.
- Version discovery no longer relies solely on hardcoded `CURRENT_VERSION` — also queries `git ls-remote --tags`.
- Cache auto-refresh: if cache is on detached HEAD, checkout master before fetching.

### Added

- Added `--doctor` diagnostic mode to `pkb_update_client.py` — runs 10 checks for update system health.
- Added hook path pollution detection and repair in doctor mode.
- Added automatic hook path repair on `--apply` (fixes `starter_cache` references in `.claude/settings.json`).
- Added CWD safety check: aborts if running from inside `.pkb_system/starter_cache/`.
- Update output now shows: installed version, latest remote tag, selected checkout, cache path, cache refresh status.

### Safety

- Dry-run still does NOT modify any KB files.
- Git cache refresh in `.pkb_system/` is allowed during dry-run but only affects the cache, not KB content.
- `.claude/settings.json` remains NEVER written by the update process.
- Hook commands remain KB-relative paths (e.g. `python .claude/hooks/05_stop.py`).
- "Bun not found" is documented as a non-blocking external hook issue — not a PKB update failure.
- Existing v0.6.2-alpha, v0.6.3-alpha, v0.6.4-alpha, and v0.6.5-alpha tags remain unchanged.

---

## [0.6.5-alpha] — 2026-06-12

### Added

- Added optional z-web-pack compatibility layer.
- Added PKB compatibility base (`tools/pkb_compat/web_research_pack_base.py`) for missing 1-web-research-pack dependency.
- Added `tools/pkb_compat/run_z_web_pack.py` — standalone z-web-pack runner with runtime compat base deployment.
- Added collector health check (`tools/check_collectors.py`) — detects availability of built-in web_pack, z-web-pack, WebFetch, and gstack.
- Added WebFetch and gstack collector documentation to `/web` and `/pkb` commands.

### Changed

- `zskill_bridge.py run` now executes z-skill scripts through `subprocess.run()` instead of only printing instructions.
- `/web` and `/pkb` collector routing now checks collector health before choosing a collector.
- Built-in web_pack remains the default recommended collector; z-web-pack is opt-in.
- `check_collectors.py` supports `--json`, `--recommend`, and `--quiet` flags for CI/automation use.

### Safety

- z-web-pack remains optional and is not a PKB core dependency.
- Video downloading defaults to `off`; `--videos all` requires explicit opt-in.
- `--max-video-mb` defaults to 300 MB; subprocess timeout at 10 minutes.
- Compatibility files are deployed at runtime to `.agent/skills/` (gitignored) — third-party vendor source code is never modified.
- Dummy readability module only bypasses import pre-check; real readability API calls will raise errors and trigger fallback.

---

## [0.6.4-alpha] — 2026-06-12

### Fixed

- Fixed default `starter_repo_url` still using the `<your-username>` placeholder in fresh installs — now defaults to the official repo `https://github.com/Clockworkhg/pkb-starter.git`.
- Fixed `pkb_update_client.py` to detect old placeholder `starter_repo_url` and guide users to fix it (with `--repo-url` flag).
- `pkb_update_client.py --apply` now writes the `--repo-url` back to `pkb.config.json` so future `/update` calls work without repeating the flag.
- Preserved `--repo-url` override behavior for fork users.
- Confirmed dry-run does not modify `pkb.config.json` and `--apply` writes back the selected repo URL safely.

### Migration

Users on v0.6.2-alpha or v0.6.3-alpha should update to v0.6.4-alpha:
```bash
python tools/pkb_update_client.py --checkout v0.6.4-alpha          # dry-run (safe)
python tools/pkb_update_client.py --checkout v0.6.4-alpha --apply  # apply changes
```

If `starter_repo_url` is still the `<your-username>` placeholder, use:
```bash
python tools/pkb_update_client.py --repo-url "https://github.com/Clockworkhg/pkb-starter.git" --checkout v0.6.4-alpha
python tools/pkb_update_client.py --repo-url "https://github.com/Clockworkhg/pkb-starter.git" --checkout v0.6.4-alpha --apply
```

After `--apply`, the official repo URL is saved to `pkb.config.json` and future `/update` calls work without the `--repo-url` flag.

See [UPDATING.md](docs/UPDATING.md) and [RECOVER_FROM_0.6.2_ALPHA.md](docs/RECOVER_FROM_0.6.2_ALPHA.md).

---

## [0.6.3-alpha] — 2026-06-12

### Fixed

- Fixed fresh installs reporting stale documentation immediately after installation (replaced `YYYY-MM-DD` placeholders with actual dates in all template files).
- Fixed `docs_update.py` incorrectly rewriting version strings into malformed values such as `v06-12` (version and date fields are now handled separately with context-anchored regex).
- Fixed `/docs-update` behavior so protected rule files (`CLAUDE.md`, `AGENTS.md`) are reported for manual review instead of being overwritten.
- Updated starter template docs (`index.md`, `log.md`, `AGENTS.md` EN/ZH) so v0.6.3-alpha installs are self-consistent with stale count = 0 on fresh install.
- Updated version references in `install.py`, `pkb_update_client.py`, `update.md`, `README`, `QUICKSTART`, and `UPDATING` docs to v0.6.3-alpha.
- Added `--check` and `--apply` flags to `docs_update.py` with safe, context-aware version/date replacement.
- Updated `/docs-update` command to default to diagnostic mode, require explicit confirmation for apply, and never bypass ARS scope guard.
- Added recovery instructions for users who installed v0.6.2-alpha (`docs/RECOVER_FROM_0.6.2_ALPHA.md` EN+ZH).
- Confirmed PKB Starter has zero Bun dependencies — all hooks and tools are Python 3.9+.

### Added

- `docs/RECOVER_FROM_0.6.2_ALPHA.md` — English recovery guide for v0.6.2-alpha users.
- `docs/zh-CN/RECOVER_FROM_0.6.2_ALPHA.md` — Chinese recovery guide for v0.6.2-alpha users.
- Protected-file awareness in `docs_update.py`: `CLAUDE.md` and `AGENTS.md` are check-only, never auto-modified.

### Migration

Users on v0.6.2-alpha should update to v0.6.4-alpha using:
```bash
python tools/pkb_update_client.py --checkout v0.6.4-alpha          # dry-run (safe)
python tools/pkb_update_client.py --checkout v0.6.4-alpha --apply  # apply changes
```

See [UPDATING.md](docs/UPDATING.md) and [RECOVER_FROM_0.6.2_ALPHA.md](docs/RECOVER_FROM_0.6.2_ALPHA.md).

---

## [0.6.2-alpha] — 2026-06-12

This alpha release adds custom install paths, a built-in update client, and enhanced user data protection.

### Added

**Custom Install Path**
- `install.py` now accepts any target directory — no default path is forced
- `--interactive` mode for guided setup with path, language, skills, and repo URL prompts
- `--repo-url` parameter to configure a custom pkb-starter fork at install time
- Path guidance in all docs: `D:\MyKB` is an example, users choose their own path

**Built-in Update Client**
- `tools/pkb_update_client.py` — installed in every KB, supports three update modes:
  - Online update (clone/pull from configured `starter_repo_url`)
  - Local starter update (`--starter-path`)
  - Specific version checkout (`--checkout v0.6.2-alpha`)
- Client defaults to **dry-run** — preview changes before applying
- `--apply` flag required to actually modify files
- Generates `update_client_report.md` with protected data, preserved fields, and change summary

**Enhanced Config Preservation**
- `install_path` — preserved across updates, never modified
- `starter_repo_url` — preserved, never reset to default
- `starter_update_channel` — preserved (alpha/beta/stable)
- `starter_cache_dir` — preserved (`.pkb_system/starter_cache` default)
- `language`, `wiki_language`, `output_language` — all preserved
- `skills.*` state — fully preserved including installed, enabled, disabled, vendor downloads, adapters

**Report Improvements**
- `update_client_report.md` — generated by the update client, distinct from update_report.md
- `update_report.md` — generated by update_pkb.py with config fields preserved section
- Both reports clearly distinguish dry-run from live mode

**User Data Protection**
- Protected directories: `raw/`, `wiki/`, `_INBOX/`, `skills/_vendor/`, `.pkb_local/`
- Protected files: `zskill_audit_report.md`, `skill_manager_report.md`
- `install.py` refuses non-empty directories without `--force`
- Backup created before every update in `.pkb_backup/`

**.gitignore Updates**
- Root and template `.gitignore` include: `.pkb_system/`, `update_client_report.md`, `update_report.md`, `test-pkb-*/`
- Template `.gitignore` includes: `skills/_vendor/`, `.pkb_local/`, `update_client_report.md`

### Changed

- `install.py` now writes `starter_update_channel` and `starter_cache_dir` to config
- `update_pkb.py` config whitelist expanded to include all new preserved fields
- `README.md` and `QUICKSTART.md` now display current version prominently
- Doc examples use `D:\MyKB` as illustrative path, not a fixed requirement
- All path references are parameterized; users choose their install location

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
