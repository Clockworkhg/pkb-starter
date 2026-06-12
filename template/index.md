---
created: 2026-06-12
updated: 2026-06-12
tags: [home, index]
---

# PKB — Personal Knowledge Base

> 🏠 **Project-level home** — PKB system navigation entry. Knowledge content directory: [[wiki/index]].

LLM Wiki mode compiled personal knowledge base. Three-layer architecture: `raw/` (immutable raw materials) → `wiki/` (LLM-maintained structured knowledge) → `skills/` (Agent automation rules).

## Navigation

### 📥 Entry Points
- `/pkb <anything>` — 🚀 Single entry, fully automatic ingest
- `raw/webpacks/` — Web collection packs
- `raw/imported_processed/` — Processed archive
- `raw/papers/` — Paper PDFs

### 🧠 Core Concepts
- [[llm-wiki]] — Karpathy LLM Wiki compiled knowledge base (PKB theoretical foundation)
- [[compiled-knowledge-base]] — Compiled vs retrieval-based knowledge bases
- [[web-pack]] — Web collection pack concept
- [[pkb-web-pack]] — PKB web_pack implementation
- [[raw-layer]] — Raw layer concept

### 🗂️ Projects
- Add your projects here as `[[project-name]]`

### ⚙️ System
- [COMMANDS](COMMANDS.md) — Command reference
- [AGENTS](AGENTS.md) — System rules (for agents)
- [CLAUDE](CLAUDE.md) — Quick reference (auto-loaded each session)
- [log](log.md) — Project-level change log
- [[wiki/index]] — Knowledge-level full index
- [[wiki/log]] — Knowledge-level change log

### 🛠 Tools
- `tools/web_pack.py` — Basic web collector (v0.1.0)
- `tools/pkb_auto.py` — Fully automated ingest + health check
- `tools/docs_update.py` — Project documentation auto-update
- `tools/import_to_inbox.py` — File import to inbox
- `tools/sanitize.py` — Privacy scan and sanitization
- `tools/pkb_update_client.py` — Update pkb-starter system files
- `tools/zskill_bridge.py` — Z-skills compatibility bridge

### 🔗 Skills
- [SKILL_LINKS](SKILL_LINKS.md) — Installed skills index and adapter registry

### 🪝 Hooks
- `.claude/hooks/` — 6 harness hooks (session start, pre-tool-use, post-tool-use, error recovery, stop, prompt submit)

---

*Maintained by the PKB system. Last updated: 2026-06-12*
