# Obsidian Skills Adapter

## Metadata

- **skill_name**: Obsidian Skills (kepano/obsidian-skills)
- **adapter_version**: 0.2.0
- **applies_to**: obsidian-skills, obsidian-claude-pkm, daily-patterns-pack
- **when_to_use**: Managing Obsidian vault notes from Claude Code, creating/renaming/moving markdown files in wiki/

## Input Types

- Note creation requests
- Wikilink management
- Vault search queries
- Template application
- Note refactoring (rename, move, merge)

## Output Target

```
wiki/                  # Primary output -- all new notes go here
wiki/concepts/         # Atomic concept notes
wiki/sources/          # Source reference notes
wiki/projects/         # Project notes
wiki/outputs/          # Generated content (research, reports)
wiki/tasks/            # Task/todo notes
wiki/meta/             # Templates and meta-configuration
```

## Raw Mapping

- Obsidian vault = `wiki/` directory
- Note templates stored in `wiki/meta/templates/`
- `.obsidian/` config is NOT managed by PKB -- user responsibility

## Wiki Mapping

| Obsidian Action | PKB Target |
|----------------|-----------|
| Create note | Respect PKB frontmatter requirements (created/updated/tags/type) |
| Rename note | Update all `[[wikilinks]]` in wiki/ |
| Delete note | Archive to `.trash/`, do NOT permanently delete without confirmation |
| Search vault | Search both wiki/ AND raw/ for completeness |
| Apply template | Copy from `wiki/meta/templates/`, fill PKB frontmatter |

## Command Integration

- `/project:inbox` -- After obsidian-skills creates notes from raw materials, run to update indices
- `/project:lint` -- Verify no broken wikilinks after bulk operations
- `/project:save` -- Commit after any vault mutation

## Safety Notes

- Never delete wiki/ notes without user confirmation.
- When creating notes, always include PKB frontmatter (created, updated, tags, type).
- Wikilinks must use `[[page-name]]` format, not full paths.
- Back up vault before bulk operations.
- Obsidian-skills may modify `.obsidian/` config -- review changes before committing.
