# PKB Starter — Design

## Philosophy

PKB is based on Andrej Karpathy's **LLM Wiki** concept: a compiled knowledge base where LLMs do the heavy lifting of organizing, linking, and maintaining knowledge. You throw things in; the system structures them.

### Core Insight

Traditional personal knowledge management requires humans to:
1. Decide where to file things
2. Write summaries and notes
3. Create links between concepts
4. Maintain consistency over time

PKB inverts this: the **human provides raw materials** (files, URLs, notes), and the **LLM maintains the structure**. This makes knowledge capture near-zero effort.

## Three-Layer Architecture

```
┌──────────────────────────────────────────────┐
│  Layer 3: skills/                            │
│  Agent automation rules                      │
│  "How to maintain the knowledge base"        │
├──────────────────────────────────────────────┤
│  Layer 2: wiki/                              │
│  LLM-maintained structured knowledge         │
│  Markdown + [[wikilink]] + frontmatter       │
├──────────────────────────────────────────────┤
│  Layer 1: raw/                               │
│  Immutable raw materials                     │
│  Append-only, never modified                 │
└──────────────────────────────────────────────┘
```

### Layer 1: `raw/` — Immutable Archive

Raw materials are **never modified** after ingestion. This preserves provenance and enables reprocessing when the LLM gets better.

| Subdirectory | Content |
|-------------|---------|
| `webpacks/` | Structured web collections (pages + images + metadata) |
| `papers/` | Academic papers (PDF) |
| `imported_processed/` | Processed files moved from `_INBOX` |
| `clippings/` | Quick clips from clipboard |
| `personal/` | Private notes and references |

### Layer 2: `wiki/` — Living Knowledge

LLM-maintained Markdown pages with:
- **YAML frontmatter**: `created`, `updated`, `tags`, `type`, `source_path`
- **`[[wikilink]]`** connections between pages
- **Atomic concepts**: one concept per page
- **Source tracking**: every concept traces back to raw materials

| Subdirectory | Purpose |
|-------------|---------|
| `concepts/` | Atomic concept notes |
| `sources/` | Knowledge source indices |
| `projects/` | Project-specific pages |
| `outputs/` | Generated articles, reports |

### Layer 3: `skills/` — Agent Rules

Claude Code skills that automate the entire pipeline:
- **pkb-auto**: Full autopilot ingest
- **pkb-web-pack**: Web content collection
- **pkb-inbox**: Raw → Wiki compilation
- **pkb-ask**: Knowledge base query
- **pkb-sanitize**: Privacy scanning
- **pkb-lint**: Health checks
- **pkb-init**: New PKB setup

## Autopilot Ingest Flow

```
User: /pkb <anything>
         │
         ├─ File? ──→ Copy to _INBOX
         ├─ URL?  ──→ web_pack.py → raw/webpacks/
         └─ Text? ──→ Search wiki, answer
              │
    ┌─────────┴──────────┐
    │  Auto Ingest       │
    │  • Extract content │
    │  • Classify type   │
    │  • Create wiki     │
    │  • Update indices  │
    └─────────┬──────────┘
              │
    ┌─────────┴──────────┐
    │  Auto Archive      │
    │  • INBOX → raw/    │
    │  • Fix source_path │
    └─────────┬──────────┘
              │
    ┌─────────┴──────────┐
    │  Health Check      │
    │  • Broken links?   │
    │  • Missing meta?   │
    │  • Sensitive info? │
    └─────────┬──────────┘
              │
         Git commit
              │
         📊 Report
```

## Key Design Decisions

### 1. Append-only raw/
Files are never deleted from raw/. If you import the wrong thing, it stays — mark it in metadata. This prevents accidental data loss and preserves provenance.

### 2. LLM as primary maintainer
Humans CAN edit wiki pages, but the LLM is the primary author. This means:
- Consistent formatting and linking
- Automatic cross-referencing
- Freshness tracking

### 3. Autopilot by default
`/pkb <anything>` never asks "next step?" — it executes the full pipeline and reports at the end. This is the key insight: if the LLM is the maintainer, don't block on human decisions.

### 4. Git-native
Every change is a git commit. You can rollback, branch, and collaborate using standard git workflows. The knowledge base IS a git repository.

### 5. Obsidian-compatible
The `wiki/` directory structure and `[[wikilink]]` syntax are fully Obsidian-compatible. Open `wiki/` as an Obsidian vault for visual graph browsing.

### 6. Optional Skill Architecture

PKB's skill system follows a **registry + adapter** pattern, cataloging the full PKB ecosystem. Skills can be installed during initial setup OR anytime later via the runtime skill manager.

```
skills_registry/           pkb-starter (catalog, not bundled)
  skill_catalog.json       42 catalog entries with full metadata
  profiles.json            9 preset profiles (core/student/.../custom)

scripts/
  install.py               One-shot installer (setup time)
  install_skills.py         Skill installer (setup time, legacy)
  skill_manager.py          Runtime skill manager (anytime) [NEW v0.4.0]

skills/_vendor/            target PKB (installed on demand)
  obsidian-skills/         cloned via git, never auto-executed
  agent-research-skills/   31 sub-skills, selective activation
  deep-research-skills/    5 sub-skills, prompt-only (safe)
  ...

template/skill_adapters/   pkb-starter (routing rules)
  <adapter>.md             maps skill output -> raw/wiki paths

template/.claude/commands/
  skills.md                /project:skills command (anytime management)
```

Key principles:
- **Catalog-driven**: 42 entries across 9 distinct external repos. Extracted from live PKB installation.
- **No bundling**: Skills are cloned from their own repos, not copied from pkb-starter.
- **Adapter pattern**: Each skill gets a markdown adapter telling the LLM where to route output.
- **Risk classification**: low (auto-install, 28 skills), medium (warn, 10 skills), high (require explicit confirmation, 5 skills), reference_only (never install, 0 skills).
- **No auto-execution**: Installation = `git clone --depth 1`. Nothing runs until you invoke the skill in Claude Code.
- **Incremental adoption**: Start with Core (0 external). Add skills via `/project:skills --install-profile <name>` or `skill_manager.py` anytime.
- **Explicit activation**: Install → audit → enable is a three-step process. Installation alone does not activate a skill.
- **Source diversity**: external_repo (24 entries from 9 repos), local_template (10), plugin_marketplace (2), mcp_server (1), adapter_only (1), built_in (5).
- **Z-skills compatibility**: User-approved local install via explicit consent. PKB does NOT distribute z-skills code. Bridge (zskill_bridge.py) handles locate, audit, run, import-output, and patch.

### 6.1 Runtime Skill Management

The skill manager (`scripts/skill_manager.py` and `/project:skills`) works on a live PKB installation:

- **Status**: Shows installed, enabled, disabled, pending audit skills
- **List**: Full catalog with descriptions and risk levels
- **Describe**: Detailed view of any skill (what, why, risk, how to install)
- **Install**: Single skill or entire profile, with dry-run support
- **Audit**: LICENSE check, .git verification, adapter presence
- **Enable/Disable**: Toggle without deleting source code
- **Update catalog**: Refresh local catalog version

Every skill shows its description, risk explanation, best-for/not-for guidance, and requirements (API keys, MCP, external runtime) before installation. High-risk skills require explicit user confirmation.

### 6.2 Z-Skills Compatibility Module

PKB Starter includes a bridge module for optional z-skills integration:

- **No code redistribution**: PKB does NOT bundle, copy, or redistribute z-skills source.
- **User explicit opt-in**: Installing z-skills requires typing 'INSTALL' after reading risks.
- **Bridge architecture**: `zskill_bridge.py` handles locate, audit, status, run, import-output, and patch.
- **Three-stage lifecycle**: install (user clone) -> audit (LICENSE check) -> enable (activate adapter).
- **Default collector unchanged**: PKB's built-in web_pack is the default. z-web-pack is opt-in.
- **Local patches only**: Patches require `--allow-local-patch`, stored in `.pkb_local/patches/` (gitignored).

See [Z_WEB_PACK_PARITY.md](Z_WEB_PACK_PARITY.md) for the full capability comparison and architecture.

## Tools

| Tool | Purpose |
|------|---------|
| `web_pack.py` | Structured web collection with image/media pipeline |
| `import_to_inbox.py` | File import with sensitive data detection |
| `pkb_auto.py` | Health check and auto-pipeline orchestration |
| `docs_update.py` | Project documentation freshness checker |
| `sanitize.py` | Privacy scan with pattern detection |
