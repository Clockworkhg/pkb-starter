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

## Tools

| Tool | Purpose |
|------|---------|
| `web_pack.py` | Structured web collection with image/media pipeline |
| `import_to_inbox.py` | File import with sensitive data detection |
| `pkb_auto.py` | Health check and auto-pipeline orchestration |
| `docs_update.py` | Project documentation freshness checker |
| `sanitize.py` | Privacy scan with pattern detection |
