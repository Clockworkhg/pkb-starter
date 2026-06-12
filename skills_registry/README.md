# PKB Starter — Skill Registry

> Complete catalog of the PKB skill ecosystem. Extracted from a live PKB installation with 35+ .claude/skills, 9 _vendor repos, 12 self-built skills, 2 plugin marketplace sources, 2 MCP servers.

## Quick Reference

| Metric | Count |
|--------|-------|
| Total catalog entries | **42** |
| External repos | 9 |
| PKB self-built skills | 12 |
| MCP servers | 2 |
| Plugin marketplace | 2 |
| Reference only | 5 |
| Built-in core tools | 5 |
| Low risk | 18 |
| Medium risk | 15 |
| High risk | 7 |

## Files

| File | Purpose |
|------|---------|
| `skill_catalog.json` | Complete 42-entry skill catalog with metadata |
| `profiles.json` | 9 installation profiles (core → full → custom) |
| `README.md` | This file |

## How It Works

1. **Catalog** (`skill_catalog.json`) lists all 42 known skills with full metadata: id, name, category, source_type, repo_url, install_method, risk_level, license_status, sub_skills, adapter.
2. **Profiles** (`profiles.json`) define 9 preset groups: Core, Student, Research, Developer, Creator, Output, Security, Full, Custom.
3. **Installer** (`scripts/install_skills.py`) clones selected skills into `skills/_vendor/` and copies adapters.
4. **Adapters** (`template/skill_adapters/`) map external skill output to PKB's `raw/` / `wiki/` structure.

## Profiles

| Profile | Skills | For |
|---------|--------|-----|
| **core** | 0 external (10 built-in) | Minimalists — pure PKB workflow |
| **student** | 8 | Undergraduates, coursework, paper writing |
| **research** | 12 | Graduate students, academics, deep research |
| **developer** | 7 | Software engineers, project documentation |
| **creator** | 7 | Writers, musicians, filmmakers, content creators |
| **output** | 7 | Document/report/presentation producers |
| **security** | 3 | Privacy audits, pre-publish hardening |
| **full** | 24 | Power users — complete ecosystem |
| **custom** | Interactive | Advanced — hand-pick from 42 entries |

## Risk Levels

| Level | Policy |
|-------|--------|
| `low` | Auto-install. No external dependencies. |
| `medium` | Install with warning. Review token usage, external deps, or API requirements. |
| `high` | Requires `--enable-risky` flag. May need MCP server, external runtime, or institutional login. |
| `reference_only` | Never installed. License unclear or code is proprietary. Design reference only. |

## Source Types

| Type | Meaning | Install Method |
|------|---------|---------------|
| `built_in` | PKB core template tool | Always present |
| `local_template` | PKB self-built skill | Bundled in template |
| `external_repo` | Third-party GitHub repo | `git clone --depth 1` |
| `plugin_marketplace` | Claude Code plugin marketplace | `/plugin marketplace add` + `/plugin install` |
| `mcp_server` | MCP server | Manual `.claude/mcp.json` config |
| `reference_only` | Design reference | NEVER installed |

## Usage

```bash
# List all known skills
python scripts/install_skills.py --list

# Install a profile
python scripts/install_skills.py --target "D:\MyKB" --profile student

# Dry run (see what would be installed)
python scripts/install_skills.py --target "D:\MyKB" --profile research --dry-run

# Audit installed skills
python scripts/install_skills.py --target "D:\MyKB" --audit-only

# Install full profile with risky skills
python scripts/install_skills.py --target "D:\MyKB" --profile full --enable-risky

# Interactive custom selection
python scripts/install_skills.py --target "D:\MyKB" --profile custom
```

## Adding New Skills

1. Add entry to `skill_catalog.json` following the schema (all required fields).
2. Add to relevant profiles in `profiles.json`.
3. Create adapter in `template/skill_adapters/` if the skill produces output.
4. Update this README's stats.

## External Repos Tracked

| Repo | Skills | License |
|------|--------|---------|
| kepano/obsidian-skills | 4 | Check repo |
| Imbad0202/academic-research-skills | 14 | Check repo |
| Weizhena/Deep-Research-skills | 5 | MIT |
| lingzhi227/agent-research-skills | 31 | NO LICENSE |
| anthropics/skills | 17 | Apache 2.0 / source-available |
| tobi/qmd | 1 (CLI+MCP) | MIT |
| mattjoyce/kanban-skill | 1 | Apache 2.0 |
| wan-huiyan/skill-anonymizer | 1 | MIT |
| michalparkola/tapestry-skills | 7 | MIT |
| ZeroPointRepo/youtube-skills | 12 | MIT |
| cookjohn/cnki-skills | 10 | Check repo |
| 54yyyu/zotero-mcp | 1 (MCP) | Check repo |
| kerim/zotero-mcp-skill | 1 | Check repo |
| tjxj/z-skills | 5 (REF ONLY) | NO LICENSE — (c) Anthropic |
| VoltAgent/awesome-agent-skills | index | Check repo |
| ComposioHQ/awesome-claude-skills | index | Check repo |
| ballred/obsidian-claude-pkm | reference | Check repo |
| aplaceforallmystuff/daily-patterns-pack | reference | Check repo |

## Security Notes

- Skills are cloned into `skills/_vendor/` (gitignored by default).
- No skill code is auto-executed. Installation = `git clone --depth 1` only.
- MCP-requiring skills need manual `.claude/mcp.json` configuration.
- Reference-only skills (z-skills) are NEVER downloaded — catalog entry only.
- API-key-requiring skills warn before install.
- Review each skill's LICENSE before use. PKB Starter does not verify third-party licenses.
- High-risk skills (CNKI, Zotero) require explicit `--enable-risky` opt-in.

---

*Part of PKB Starter v0.3.0. Updated: 2026-06-12.*
