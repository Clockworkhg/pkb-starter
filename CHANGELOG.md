# PKB Changelog

All notable changes to the PKB system. Versioning follows `v<major>.<minor>.<patch>-<stage>`.

---

## v0.6.11-alpha (2026-06-18) — Global Knowledge Bridge

### ✨ New Features

- **`/ask-pkb` Global Skill**: Query PKB wiki from ANY project
  - Intelligent path detection (env var → auto-detect → config file → prompt)
  - Uses `PKB_ROOT` env var (same convention as `pkb.ps1`)
  - Falls back to walking up from cwd looking for PKB markers (`pkb.ps1` + `CLAUDE.md` + `wiki/` + `raw/`)
  - Supports `~/.pkb/config.json` as explicit config
  - Anti-pattern coding: "guess mode", "skip index", "dump all", "hallucination"
  - Structured 6-step execution with checkpoints
- **Path-agnostic design**: Sync-safe for pkb-starter distribution
  - Existing `sanitize_patterns` cover `D:\PKB_个人知识库 → <PKB_ROOT>` replacement

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
  - Environment variable override: `CHROME_DEBUG_URL`
  - Default: `http://127.0.0.1:9222`
  - Legacy `.claude/mcp.json` still supported by tools
- **Active Task State System** (`.pkb-local/state/active-task.json`)
  - `tools/pkb_task.py` — Atomic task state manager
  - Commands: `show`, `start`, `update`, `block`, `complete`, `clear`, `inject`
  - Corrupt file auto-backup + recovery
  - Schema versioning (v1)
  - Automatic timestamp updates
- **MCP Doctor / Pre-Flight** (`tools/pkb_doctor.py`)
  - 18 diagnostic checks: Python, Node, npx, Bun, Chrome, MCP, hooks, gitignore, privacy
  - Clear PASS/WARN/FAIL/SKIP output
  - `--json` for machine-readable output
  - `--quiet` for exit-code-only mode
- **SessionStart Task Context Injection**: Active task automatically shown at session start
- **CNKI Skill Capability Declarations**: `required_capabilities` in SKILL.md frontmatter
  - Honest degradation: never substitutes WebSearch for CNKI without disclosure
  - Automatic task blocking when capabilities missing

### 🔧 Improvements

- **Chrome Launcher** (`tools/launch_chrome.ps1`):
  - PKB-specific profile in `.pkb-local/chrome-profile/`
  - Preserves CNKI login state across sessions
  - Detects non-PKB Chrome instances on debug port
  - Paths with spaces, Chinese characters handled
  - Environment variable overrides (`CHROME_DEBUG_HOST`, `CHROME_DEBUG_PORT`)
- **Stop Hook**: Now touches active task timestamp on exit; `.mcp.json` added to critical file watch list
- **cnki_setup.py**: Now reads from both `.mcp.json` (standard) and `.claude/mcp.json` (legacy)
- **SessionStart Hook**: Injects active task context from `.pkb-local/state/active-task.json`

### 🛡️ Privacy & Security

- `.pkb-local/` directory added to `.gitignore`
- Chrome profile, task state, logs all kept local — never committed
- `.claude/handoff_*.md` added to `.gitignore`
- Experimental version markers (`=*`) ignored
- Private path leakage check in doctor
- Example task file at `examples/active-task.example.json`

### 📚 Documentation

- New: `docs/MCP.md` — MCP configuration and troubleshooting
- New: `docs/SESSION_CONTINUITY.md` — Session resume and task continuity
- Updated: `docs/UPDATING.md` — v0.6.9 migration notes
- Updated: `docs/CNKI.md` — CNKI workflow with new launcher
- Updated: `README.md` — Version bump, new commands
- Updated: `CLAUDE.md` — Version bump, new paths
- New: `CHANGELOG.md` (this file)

### 🧪 Testing

- New: `tests/test_pkb_task.py` — Task state management (12 tests)
- New: `tests/test_pkb_doctor.py` — Doctor diagnostics (14 tests)
- New: `tests/test_hooks_v069.py` — Hook updates with task injection
- Updated: `tests/test_cnki_skill_capabilities.py` — Skill capability validation

### ⬆️ Migration from v0.6.7

1. `.mcp.json` now at project root (updates will place it there)
2. Existing `.claude/mcp.json` is **not deleted** — tools read both locations
3. `.pkb-local/` directory auto-created on first use
4. No breaking changes to existing workflows

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
| v0.6.9-alpha | 2026-06-13 | Session Continuity & MCP Bootstrap |
| v0.6.7-alpha | 2026-06-12 | Scholarly Metadata Enrichment |
