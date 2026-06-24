# PKB Changelog

All notable changes to the PKB system. Versioning follows `v<major>.<minor>.<patch>-<stage>`.

---

## v0.6.14-starter (2026-06-24) — Exam Export + Retrieval Engine + Paper Pipeline

### ✨ New Features

- **pkb_retrieve v3.0** (`tools/pkb_retrieve.py`): BM25 + vector RRF + Cross-encoder 3-stage hybrid retrieval pipeline
- **batch_english_papers.py**: Batch English paper metadata query (DOI → Crossref/OpenAlex/SemanticScholar)
- **cnki_batch_download.py**: CNKI batch download coordinator (MCP driven)
- **cnki_webvpn.py**: CNKI WebVPN proxy access (institutional identity auth)
- **agent-skills-catalog v2**: ~132 callable + ~120 vendor reference skills

### 📝 Changes

- CLAUDE.md: version bump to v0.6.14-starter, tool table expanded (30 tools)
- AGENTS.md: version bump to 1.3.2 (2026-06-24), hooks v1.1, pkb_retrieve v3.0
- hooks/03_post_tool_use.py: retrieval index auto-rebuild (30s cooldown) + full health check post-commit
- .gitignore: expanded with vendor skill repos, Zotero DB, scholarly metadata, privacy raw files
- template/sync: ask-pkb/SKILL.md, index.md, 03_post_tool_use.py, AGENTS.md synced

### 🔧 Sync Pipeline Fixes (2026-06-24)

- **Critical**: sync_to_starter.py binary file corruption — added BINARY_EXTENSIONS detection + read_bytes/write_bytes
- **Critical**: manifest sanitize_patterns double-backslash bug — 3 residual PKB paths leaked into starter
- **High**: deleted stale root-level CLAUDE.md (v0.6.13-alpha orphan listing 6 missing tools)
- **Medium**: removed dead `tools/tests/conftest.py` manifest mapping + duplicate target collision
- **Medium**: deleted stale root `.obsidian/workspace.json` (orphan after vault migration)
- **Docs**: COMMANDS.md, index.md, AGENTS.md — cnki_setup/setup_beauty_stack marked optional
- **Docs**: README version badge → v0.6.14-starter, skills count 7→3 built-in
- **Manifest**: +6 entries (test_pkb_retrieve.py + test-wiki fixtures), 120 mappings / 0 duplicates

---

## v0.6.13-alpha (2026-06-20) — Guided Installation + Installer UX Fixes

### ✨ New Features

- **`/install` guided installation flow** (`.claude/commands/install.md`): 10-step interactive install ensuring AI presents all options, dry-runs first, confirms high-risk skills separately, pre-warns about network failures (CN region), categorizes results, and suggests CNKI/Zotero after install
- **Post-install verification**: `--verify` flag (default: on) runs `pkb_doctor.py` after install with manual fallback checks; `--no-verify` to skip

### 🔧 Changes

- **install_skills.py → v0.4.0**: `template_bundled` skills now report as built-in SKIP instead of FAIL
- **Categorized install reports**: Results grouped as ✅ installed / ⚠️ built-in / ⚠️ plugin marketplace / ⚠️ MCP config / ❌ failed
- **install.py**: Enhanced completion message with CNKI/Zotero optional install box
- CLAUDE.md: version bump to v0.6.13-alpha, added `/install` mention

---

## v0.6.12-alpha (2026-06-20) — Multi-Source Paper Download Engine

### ✨ New Features

- **scansci_bridge v1.0** (`tools/scansci_bridge.py`): 13-source paper download engine
  - Download: `python tools/scansci_bridge.py download <DOI>` — parallel race across 13 OA sources
  - Search: `python tools/scansci_bridge.py search "<query>" --limit N`
  - Health check: `python tools/scansci_bridge.py --check` — source availability diagnostic
  - Strategies: `fastest` (default) | `oa_first` | `scihub_only` | `legal_only`
  - 6/6 sources reachable (EuropePMC/Unpaywall/SemanticScholar/OpenAlex/Crossref)
- **scihub_fetch upgrade**: Now acts as multi-source pipeline frontend (scansci-pdf → Sci-Hub fallback)
- **setup_beauty_stack**: One-click beauty tech stack installer (Tailwind + shadcn/ui + Motion + Magic UI)

### 📝 Changes

- CLAUDE.md: version bump to v0.6.12-alpha, added scansci_bridge + setup_beauty_stack documentation
- AGENTS.md: version bump to 1.3.1, scansci_bridge v1.0 marker
- COMMANDS.md: added `/setup-beauty-stack`, scansci_bridge usage examples
- README.md / README.zh-CN.md: version bump, scansci_bridge feature highlight

---

## v0.6.11-alpha (2026-06-18) — Global Knowledge Bridge

### ✨ New Features

- **`/ask-pkb` Global Skill**: Query PKB wiki from ANY project
  - Intelligent path detection (env var → auto-detect → config file → prompt)
  - Uses `PKB_ROOT` env var (same convention as `pkb.ps1`)
  - Falls back to walking up from cwd looking for PKB markers
  - Supports `~/.pkb/config.json` as explicit config
  - Anti-pattern coding: "guess mode", "skip index", "dump all", "hallucination"
  - Structured 6-step execution with checkpoints
- **Path-agnostic design**: Sync-safe for pkb-starter distribution

### 📝 Changes

- CLAUDE.md: version bump to v0.6.11-alpha, skill routing table updated
- starter_sync_manifest.json: `ask-pkb/SKILL.md` added to mappings

---

## v0.6.9-alpha (2026-06-13) — Session Continuity & MCP Bootstrap

### ✨ New Features

- **Unified Launcher** (`pkb.ps1`): Single entry point for all PKB workflows
  - `.\pkb.ps1` — Environment check + status summary
  - `.\pkb.ps1 status` — Full status report
  - `.\pkb.ps1 cnki` — CNKI workflow (Chrome + MCP + session)
  - `.\pkb.ps1 doctor` — Comprehensive diagnostics (18 checks)
  - `.\pkb.ps1 resume` — Resume session with MCP reload
- **MCP Configuration Standardization**: `.mcp.json` at project root (Claude Code standard)
- **Active Task State System** (`tools/pkb_task.py`): Atomic task state manager
- **MCP Doctor / Pre-Flight** (`tools/pkb_doctor.py`): 18 diagnostic checks
- **SessionStart Task Context Injection**: Active task automatically shown at session start
- **CNKI Skill Capability Declarations**: Honest degradation, never substitutes WebSearch without disclosure

### 🔧 Improvements

- **Chrome Launcher** (`tools/launch_chrome.ps1`): PKB-specific profile, preserves CNKI login state
- **Stop Hook**: Touches active task timestamp on exit
- **cnki_setup.py**: Reads from both `.mcp.json` and `.claude/mcp.json`

### 🛡️ Privacy & Security

- `.pkb-local/` directory added to `.gitignore`
- Chrome profile, task state, logs all kept local — never committed
- `.claude/handoff_*.md` added to `.gitignore`

### 📚 Documentation

- New: `docs/MCP.md`, `docs/SESSION_CONTINUITY.md`
- Updated: `docs/UPDATING.md`, `docs/CNKI.md`, `README.md`
- New: `CHANGELOG.md` (this file)

### 🧪 Testing

- New: `tests/test_pkb_task.py` (12 tests), `tests/test_pkb_doctor.py` (14 tests)

---

## v0.6.7-alpha (2026-06-12)

### ✨ New Features

- **Scholarly Metadata Enrichment** (Phase 1B.1): Auto-detect DOI/arXiv/PMID, enrich via Crossref/OpenAlex
- **Literature Filtering** (`tools/filter_literature.py`): Filter by journal ranking, year, citations
- **Journal Ranking Import** (`tools/import_journal_rankings.py`): CSSCI/北大核心/AMI/CSCD
- **Citation Formatting**: GB/T 7714, APA 7, BibTeX, RIS
- **Web Pack v3.1**: Playwright dynamic rendering, network capture, selection engine
- **MarkItDown Phase 1.5**: Local document → Markdown conversion (PDF/DOCX/PPTX/XLSX)

### 🔧 Improvements

- CNKI Skills integration (search, download, fill-gaps)
- MCP configuration for chrome-devtools
- 6 harness hooks (SessionStart, PreToolUse, PostToolUse, PostToolUseFailure, Stop, UserPromptSubmit)

---

## Version History

| Version | Date | Theme |
|---------|------|-------|
| v0.6.14-starter | 2026-06-24 | Exam Export + Retrieval Engine + Paper Pipeline |
| v0.6.13-alpha | 2026-06-20 | Guided Installation + Installer UX Fixes |
| v0.6.12-alpha | 2026-06-20 | Multi-Source Paper Download Engine |
| v0.6.11-alpha | 2026-06-18 | Global Knowledge Bridge |
| v0.6.9-alpha | 2026-06-13 | Session Continuity & MCP Bootstrap |
| v0.6.7-alpha | 2026-06-12 | Scholarly Metadata Enrichment |
