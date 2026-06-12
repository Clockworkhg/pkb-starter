# PKB Starter — Optional Skills

> Comprehensive skill ecosystem: 42 catalog entries, 9 profiles, 18 external repos tracked. None are bundled — you choose what to install.

## Philosophy

PKB Starter is a **core framework** that works out of the box with zero external skills.
Optional skills add domain-specific capabilities: academic research, document processing,
semantic search, project management, security hardening.

We do NOT bundle third-party code because:
1. **License clarity** — each skill has its own LICENSE. Bundling would mix licenses.
2. **User choice** — you decide which external code runs on your machine.
3. **Update independence** — skills update on their own schedule from their repos.
4. **Security** — you audit what you install, not what we pre-installed.

## Ecosystem at a Glance

| Metric | Count |
|--------|-------|
| Total catalog entries | 42 |
| External GitHub repos tracked | 9 |
| PKB self-built skills (bundled) | 12 |
| Claude Code plugin marketplace | 2 |
| MCP servers | 2 |
| Reference only (never installed) | 5 |
| Core built-in tools | 5 |

## Profiles

9 preset profiles for different use cases:

| Profile | Skills | Best For |
|---------|--------|----------|
| **Core** | 0 external (10 built-in) | Minimalists — pure PKB workflow |
| **Student** | 8 | Undergraduates, coursework, paper writing |
| **Research** | 12 | Graduate students, academics, deep research |
| **Developer** | 7 | Software engineers, project documentation |
| **Creator** | 7 | Writers, musicians, filmmakers, content creators |
| **Output** | 7 | Document/report/presentation producers |
| **Security** | 3 | Privacy audits, pre-publish hardening |
| **Full** | 24 | Power users — complete ecosystem |
| **Custom** | Interactive | Advanced — hand-pick from 42 entries |

### Core Profile (always present)

These skills are built into the PKB template:
- `web-pack` — Web content collector (requests + BeautifulSoup + markdownify)
- `pkb-auto` — Full autopilot ingest pipeline
- `import-to-inbox` — File import with secret detection
- `sanitize-tool` — Privacy scanner (regex patterns)
- `docs-update` — Documentation freshness checker
- `git-versioning` — Enhanced git save/rollback + secret scan
- `secret-scan` — Pre-commit sensitive data detection
- `document-converter` — DOCX/PDF/PPTX ↔ Markdown
- `skill-creator` — New skill creation wizard
- `skill-lint` — Skill health check

## Installation

Skills can be installed during initial PKB setup OR anytime later. The runtime skill manager (`skill_manager.py` and `/project:skills`) works on a live PKB installation.

### During initial setup (with install.py)
```bash
python scripts/install.py "D:\MyKB" --profile student
python scripts/install.py "D:\MyKB" --profile student --dry-run   # preview only
python scripts/install.py "D:\MyKB" --interactive-skills          # pick individually
python scripts/install.py "D:\MyKB" --skip-skills                 # core only, add later
```

### Anytime after installation (with skill_manager.py)
```bash
# Browse and explore
python scripts/skill_manager.py --target "D:\MyKB" --list
python scripts/skill_manager.py --target "D:\MyKB" --describe deep-research-skills
python scripts/skill_manager.py --target "D:\MyKB" --enabled

# Install
python scripts/skill_manager.py --target "D:\MyKB" --install deep-research-skills
python scripts/skill_manager.py --target "D:\MyKB" --install-profile research --dry-run
python scripts/skill_manager.py --target "D:\MyKB" --install-profile student

# Manage
python scripts/skill_manager.py --target "D:\MyKB" --audit
python scripts/skill_manager.py --target "D:\MyKB" --enable kanban-skill
python scripts/skill_manager.py --target "D:\MyKB" --disable kanban-skill
python scripts/skill_manager.py --target "D:\MyKB" --update-catalog
```

### With install_skills.py (legacy, during setup only)
```bash
python scripts/install_skills.py --list
python scripts/install_skills.py --list-profiles
python scripts/install_skills.py --target "D:\MyKB" --profile research --dry-run
python scripts/install_skills.py --target "D:\MyKB" --profile custom
python scripts/install_skills.py --target "D:\MyKB" --audit-only
```

### From Claude Code (anytime)
```
/project:skills                       # Status overview
/project:skills --list                # Browse catalog
/project:skills --describe <id>       # Full details
/project:skills --install <id>        # Single skill
/project:skills --install-profile student
/project:skills --audit               # Health check
/project:skills --enabled             # What's active
/project:skills --enable <id>         # Activate
/project:skills --disable <id>        # Deactivate
/project:skills --update-catalog      # Refresh
```

## Runtime Skill Management

PKB's skill system is designed for incremental adoption. You don't need to decide everything during setup:

1. **Start with Core** — Pure PKB, zero external skills. All built-in tools work.
2. **Add as needed** — `/project:skills --list` to browse, `--describe` to learn, `--install` to add.
3. **Audit before enabling** — `--audit` checks LICENSE, .git, adapters. Then `--enable` activates.
4. **Disable, don't delete** — `--disable` deactivates without removing source code.
5. **Always reversible** — Delete `skills/_vendor/<id>/` to fully remove. Remove from config.

### Skill Lifecycle

```
catalog entry  --install-->  skills/_vendor/<id>/  (downloaded, not active)
                             |
                             +--audit-->  review LICENSE, code, adapter
                             |
                             +--enable-->  adapter active, skill usable
                             |
                             +--disable-->  adapter inactive, code kept
                             |
                             +--delete directory-->  fully removed
```

### State Model (in pkb.config.json)

```json
"skills": {
  "catalog_version": "0.4.0",
  "installed_profiles": ["student"],
  "installed_skills": ["deep-research-skills", "kanban-skill"],
  "enabled_skills": ["kanban-skill"],
  "disabled_skills": ["deep-research-skills"],
  "vendor_downloads": ["deep-research-skills", "kanban-skill"],
  "enabled_adapters": ["kanban_adapter.md"],
  "pending_audit": []
}
```

### Every Skill Shows Before Installation

- **Short description** — one sentence summary
- **Long description** — 2-4 sentences about use cases
- **Best for** — typical scenarios
- **Not for** — what to avoid
- **Risk explanation** — plain language risk description
- **Requirements** — API keys, MCP, external runtimes

## Risk Levels

Skills are classified by risk to help you make informed decisions:

| Level | Policy | Count | Examples |
|-------|--------|-------|----------|
| `low` | Auto-install. No external dependencies. | 18 | obsidian-skills, kanban-skill, prompt-library, article-extractor |
| `medium` | Install with warning. Review deps/token usage. | 15 | academic-research-skills, deep-research-skills, qmd, data-analysis |
| `high` | Requires `--enable-risky`. MCP or external runtime. | 7 | cnki-skills, zotero-mcp, zotero-mcp-skill, ocr-helper |
| `reference_only` | Never installed. Design reference only. | 5 | z-skills (Anthropic copyrighted) |

## Source Types

| Type | Meaning | Install Method |
|------|---------|---------------|
| `built_in` | PKB core template tool | Always present |
| `local_template` | PKB self-built skill | Bundled in template |
| `external_repo` | Third-party GitHub repo | `git clone --depth 1` |
| `plugin_marketplace` | Claude Code plugin marketplace | `/plugin marketplace add` + `/plugin install` |
| `mcp_server` | MCP server | Manual `.claude/mcp.json` config |
| `reference_only` | Design reference | NEVER installed |

## Skill Catalog (v0.3.0)

### Knowledge Capture (6 entries)

| ID | Source | Risk | Sub-Skills | Notes |
|----|--------|------|------------|-------|
| web-pack | built_in | low | — | Core web collector, always enabled |
| pkb-auto | built_in | low | — | Auto ingest pipeline |
| import-to-inbox | built_in | low | — | File import + secret detection |
| article-extractor | tapestry-skills (MIT) | low | — | Single article fast extraction |
| ocr-helper | local_template (MIT) | medium | — | OCR via Windows API/Tesseract |
| web-clipper-helper | local_template (MIT) | low | — | Browser clipping assistant |

### Academic Research (10 entries)

| ID | Source | Risk | Sub-Skills | Notes |
|----|--------|------|------------|-------|
| academic-research-skills | plugin marketplace | medium | 14 (ars-*) | Full ARS pipeline |
| deep-research-skills | Weizhena (MIT) | medium | 5 | Structured multi-turn research |
| agent-research-skills | lingzhi227 (NO LICENSE) | medium | 31 | Comprehensive agent-based pipeline |
| literature-search | agent-research (Tier 1) | low | — | Multi-source lit search |
| literature-review | agent-research (Tier 1) | low | — | Dialogic lit review |
| paper-writing-section | agent-research (Tier 1) | low | — | Academic paper drafting |
| citation-management | agent-research (Tier 2) | low | — | GB/T 7714, APA, IEEE |
| data-analysis | agent-research (Tier 2) | medium | — | Statistical analysis with 4-round review |
| cnki-skills | cookjohn (check LICENSE) | high | 10 | CNKI database (requires MCP + login) |
| zotero-mcp | 54yyyu (check LICENSE) | high | — | MCP server (requires Zotero running) |
| zotero-mcp-skill | kerim (check LICENSE) | high | — | Companion skill for zotero-mcp |

### Document Processing (2 entries)

| ID | Source | Risk | Sub-Skills | Notes |
|----|--------|------|------------|-------|
| anthropic-skills | anthropics (Apache 2.0) | medium | 17 | Official doc processing skills |
| document-converter | local_template (MIT) | low | — | DOCX/PDF/PPTX ↔ MD |

### Knowledge Management (3 entries)

| ID | Source | Risk | Sub-Skills | Notes |
|----|--------|------|------------|-------|
| obsidian-skills | plugin marketplace | low | 4 | Obsidian vault management |
| qmd | tobi (MIT) | medium | — | Semantic search (BM25+vector+LLM) |
| kanban-skill | mattjoyce (Apache 2.0) | low | — | Markdown file-based kanban |

### Security & Privacy (2 entries)

| ID | Source | Risk | Sub-Skills | Notes |
|----|--------|------|------------|-------|
| sanitize-tool | built_in | low | — | Core privacy scanner |
| sanitize-skill | wan-huiyan (MIT) | low | — | Enhanced anonymizer |

### Creation & Output (4 entries)

| ID | Source | Risk | Sub-Skills | Notes |
|----|--------|------|------------|-------|
| prompt-library | local_template (MIT) | low | — | AI prompt library management |
| song-archive | local_template (MIT) | low | — | Lyrics/Suno style versions |
| script-breakdown | local_template (MIT) | low | — | Script → storyboard → prompts |
| tapestry-skills | michalparkola (MIT) | low | 7 | Creative + tools collection |

### Meta Tooling (3 entries)

| ID | Source | Risk | Sub-Skills | Notes |
|----|--------|------|------------|-------|
| git-versioning | local_template (MIT) | low | — | Enhanced git + secret scan |
| skill-creator | local_template (MIT) | low | — | New skill creation wizard |
| skill-lint | local_template (MIT) | low | — | Skill health check |

### Development (2 entries)

| ID | Source | Risk | Sub-Skills | Notes |
|----|--------|------|------------|-------|
| code-debugging | agent-research (Tier 3) | medium | — | Systematic debug workflow |
| github-research | agent-research (Tier 3) | medium | — | GitHub repo analysis |

### Knowledge Capture — External (2 entries)

| ID | Source | Risk | Sub-Skills | Notes |
|----|--------|------|------------|-------|
| youtube-transcript | tapestry-skills (MIT) | low | — | yt-dlp based, no API key |
| youtube-skills | ZeroPointRepo (MIT) | medium | 12 | Some need TranscriptAPI key |

### Reference Only (5 entries)

| ID | Source | Risk | Notes |
|----|--------|------|-------|
| z-skills | tjxj (NO LICENSE) | reference_only | (c) Anthropic — ALL RIGHTS RESERVED |
| awesome-agent-skills | VoltAgent | reference | Skill discovery index |
| awesome-claude-skills | ComposioHQ | reference | Skill discovery index |
| obsidian-claude-pkm | ballred | reference | PKM workflow reference |
| daily-patterns-pack | aplaceforallmystuff | reference | Daily note templates reference |

## How Adapters Work

Every external skill gets an **adapter** — a markdown document that tells Claude Code
where to route the skill's output within PKB:

```
External Skill Output          Adapter Routes To
----------------------         -------------------------
Research report       --->     wiki/outputs/research/
Paper analysis        --->     wiki/sources/
Literature sources    --->     wiki/sources/
Extracted concept     --->     wiki/concepts/
Project task          --->     wiki/tasks/
Search result         --->     (read-only, not persisted)
Document conversion   --->     wiki/outputs/ (+ raw/imported_processed/)
Web collection        --->     raw/webpacks/
Academic paper        --->     raw/papers/ + wiki/sources/
YouTube transcript    --->     raw/media/transcripts/
Kanban board          --->     wiki/tasks/
```

Adapters are NOT executable code. They are reference documents for the LLM to follow
when integrating skill output into your knowledge base. Adapters live in
`template/skill_adapters/` and are copied to your PKB during skill installation.

## External Repos Tracked

| Repository | Skills | License | Risk |
|-----------|--------|---------|------|
| kepano/obsidian-skills | 4 | Check repo | low |
| Imbad0202/academic-research-skills | 14 | Check repo | medium |
| Weizhena/Deep-Research-skills | 5 | MIT | medium |
| lingzhi227/agent-research-skills | 31 | NO LICENSE | medium |
| anthropics/skills | 17 | Apache 2.0 / source-available | medium |
| tobi/qmd | 1 (CLI+MCP) | MIT | medium |
| mattjoyce/kanban-skill | 1 | Apache 2.0 | low |
| wan-huiyan/skill-anonymizer | 1 | MIT | low |
| michalparkola/tapestry-skills | 7 | MIT | low |
| ZeroPointRepo/youtube-skills | 12 | MIT | medium |
| cookjohn/cnki-skills | 10 | Check repo | high |
| 54yyyu/zotero-mcp | 1 (MCP) | Check repo | high |
| kerim/zotero-mcp-skill | 1 | Check repo | high |
| tjxj/z-skills | 5 (REF ONLY) | NO LICENSE | reference_only |
| VoltAgent/awesome-agent-skills | index | Check repo | reference |
| ComposioHQ/awesome-claude-skills | index | Check repo | reference |

## Adding a New Skill

1. Add entry to `skills_registry/skill_catalog.json` following the schema
2. Create adapter in `template/skill_adapters/<adapter>.md` if the skill produces output
3. Add to relevant profiles in `skills_registry/profiles.json`
4. Update this document's stats and tables
5. Test: `python scripts/install_skills.py --target . --profile custom --dry-run`

## Removing a Skill

```bash
# From command line
python scripts/install_skills.py --target "D:\MyKB" --audit-only  # check what's installed

# From Claude Code
/project:skills --remove <skill-id>  # interactive confirmation

# Manually
rm -rf skills/_vendor/<skill-id>/
# Then update SKILL_LINKS.md and pkb.config.json
```

## Security

- Skills are cloned to `skills/_vendor/` (gitignored by default).
- No skill code is auto-executed — installation = `git clone --depth 1`.
- MCP-requiring skills need manual `.claude/mcp.json` configuration.
- PKB never reads or stores API keys for third-party skills.
- Review each skill's LICENSE before use (check the cloned repo for LICENSE file).
- High-risk skills (CNKI, Zotero) require explicit `--enable-risky` opt-in.
- Reference-only skills (z-skills) are NEVER downloaded — catalog entry only.
- Remove a skill by deleting its `skills/_vendor/<id>/` directory.

---
*PKB Starter v0.3.0. Updated: 2026-06-12.*
