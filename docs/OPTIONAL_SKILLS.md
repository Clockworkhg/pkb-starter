# PKB Starter -- Optional Skills

> Skill packs extend PKB with third-party Claude Code skills. None are bundled -- you choose what to install.

## Philosophy

PKB Starter is a **core framework** that works out of the box with zero external skills.
Optional skills add domain-specific capabilities: academic research, document processing,
semantic search, project management.

We do NOT bundle third-party code because:
1. **License clarity** -- each skill has its own LICENSE. Bundling would mix licenses.
2. **User choice** -- you decide which external code runs on your machine.
3. **Update independence** -- skills update on their own schedule from their repos.
4. **Security** -- you audit what you install, not what we pre-installed.

## Profiles

| Profile | Skills | Best For |
|---------|--------|----------|
| **Core** | (none) | Minimal PKB. Just the tools. |
| **Student** | obsidian-skills, academic-research-skills, deep-research-skills | Learning, paper analysis, literature review |
| **Research** | Student + agent-research-skills + qmd | Deep multi-source research, semantic search |
| **Developer** | obsidian-skills, anthropic-skills, qmd, kanban-skill | Coding docs, project tracking, code search |
| **Creator** | obsidian-skills, kanban-skill | Writing, content creation, task management |
| **Full** | All 7 recommended skills | Power users who want everything |
| **Custom** | Interactive pick | You choose exactly which skills |

## Installation

### With install.py (recommended)
```bash
python scripts/install.py "D:\MyKB" --profile student
python scripts/install.py "D:\MyKB" --interactive-skills
python scripts/install.py "D:\MyKB" --skip-skills   # core only
```

### With install_skills.py (standalone)
```bash
python scripts/install_skills.py --target "D:\MyKB" --profile research --dry-run
python scripts/install_skills.py --target "D:\MyKB" --profile full --enable-risky
python scripts/install_skills.py --target "D:\MyKB" --audit-only
```

### From Claude Code
```
/project:skills --install student
/project:skills --list
/project:skills --audit
```

## Risk Levels

Skills are classified by risk to help you make informed decisions:

| Level | Policy | Examples |
|-------|--------|----------|
| `low` | Auto-install. No external dependencies. | obsidian-skills, kanban-skill, index skills |
| `medium` | Install with warning. Review adapter before use. | academic-research-skills, deep-research-skills, qmd |
| `high` | Requires `--enable-risky`. MCP or external runtime needed. | zotero-mcp, zotero-mcp-skill |
| `reference_only` | Never installed. Catalog entry for design reference. | z-skills (Anthropic copyrighted) |

## How Adapters Work

Every installed skill gets an **adapter** -- a markdown document that tells Claude Code
where to route the skill's output within PKB:

```
External Skill Output          Adapter Routes To
----------------------         -------------------------
Research report       --->     wiki/outputs/research/
Paper analysis        --->     wiki/papers/
Literature sources    --->     wiki/sources/
Extracted concept     --->     wiki/concepts/
Project task          --->     wiki/tasks/
Search result         --->     (read-only, not persisted)
Document conversion   --->     wiki/outputs/ (+ raw/imported_processed/)
```

Adapters are NOT executable code. They are reference documents for the LLM to follow
when integrating skill output into your knowledge base.

## Skill Catalog (v0.2.0)

### wiki
| ID | Description | Risk |
|----|-------------|------|
| obsidian-skills | Obsidian vault management from Claude Code | low |

### academic
| ID | Description | Risk |
|----|-------------|------|
| academic-research-skills | Research architect, synthesis, report compilation | medium |
| agent-research-skills | Agent-based literature search and paper analysis | medium |
| zotero-mcp | Zotero MCP server for reference management | high |
| zotero-mcp-skill | Claude Code skill for Zotero MCP | high |

### research
| ID | Description | Risk |
|----|-------------|------|
| deep-research-skills | Multi-turn deep research with source tracking | medium |

### document
| ID | Description | Risk |
|----|-------------|------|
| anthropic-skills | Official Anthropic document processing skills | medium |

### search
| ID | Description | Risk |
|----|-------------|------|
| qmd | Semantic search over local markdown knowledge | medium |

### project
| ID | Description | Risk |
|----|-------------|------|
| kanban-skill | Kanban board management for task tracking | low |

### pkm-reference
| ID | Description | Risk |
|----|-------------|------|
| obsidian-claude-pkm | Reference Claude + Obsidian PKM workflow | low |
| daily-patterns-pack | Daily note templates and patterns | low |

### index
| ID | Description | Risk |
|----|-------------|------|
| awesome-agent-skills | Curated index of agent skills | low |
| awesome-claude-skills | Composio-curated Claude skills index | low |

### reference
| ID | Description | Risk |
|----|-------------|------|
| z-skills | Comprehensive skill collection (Anthropic copyright) | reference_only |

## Adding a New Skill

1. Add entry to `skills_registry/skill_catalog.json`
2. Create adapter in `template/skill_adapters/<adapter>.md`
3. Optionally add to profiles in `skills_registry/profiles.json`
4. Test: `python scripts/install_skills.py --target . --profile custom --dry-run`

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
- No skill code is auto-executed -- installation = `git clone --depth 1`.
- MCP-requiring skills need manual `.claude/mcp.json` configuration.
- PKB never reads or stores API keys for third-party skills.
- Review each skill's LICENSE before use (check the cloned repo for LICENSE file).
- Remove a skill by deleting its `skills/_vendor/<id>/` directory.

---
*PKB Starter v0.2.0*
