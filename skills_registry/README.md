# PKB Starter -- Skill Registry

> Optional skill packs for PKB. Skills are NOT bundled -- installed on demand.

## How It Works

1. **Catalog** (`skill_catalog.json`) lists all known skills with metadata.
2. **Profiles** (`profiles.json`) define preset groups: Core, Student, Research, Developer, Creator, Full, Custom.
3. **Installer** (`scripts/install_skills.py`) clones selected skills into `skills/_vendor/`.
4. **Adapters** (`template/skill_adapters/`) map external skill output to PKB's `raw/` / `wiki/` structure.

## Risk Levels

| Level | Policy |
|-------|--------|
| `low` | Auto-install. No external dependencies. |
| `medium` | Install with warning. Review token usage and output paths. |
| `high` | Requires `--enable-risky` flag. May need MCP server or external runtime. |
| `reference_only` | Never installed. Read for design inspiration only. |

## Profiles at a Glance

| Profile | Skills | For |
|---------|--------|-----|
| `core` | (none) | Minimal PKB |
| `student` | obsidian, academic-research, deep-research | Learning, papers |
| `research` | student + agent-research + qmd | Deep research |
| `developer` | obsidian, anthropic, qmd, kanban | Coding, docs |
| `creator` | obsidian, kanban | Writing, content |
| `full` | all recommended (7 skills) | Power users |
| `custom` | interactive pick | Advanced |

## Adding New Skills

1. Add entry to `skill_catalog.json` with all required fields.
2. Create an adapter in `template/skill_adapters/` mapping the skill's output to PKB structure.
3. Optionally add the skill to one or more profiles in `profiles.json`.
4. Update this README.

## Security Notes

- Skills are cloned into `skills/_vendor/` (gitignored by default).
- No skill code is auto-executed. Installation = git clone only.
- MCP-requiring skills need manual `.claude/mcp.json` configuration.
- Reference-only skills (like z-skills) are never downloaded -- catalog entry only.
- Review each skill's LICENSE before use. PKB Starter does not verify third-party licenses.
