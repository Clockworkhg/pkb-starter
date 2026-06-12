# Kanban Skill Adapter

## Metadata

- **skill_name**: Kanban Skill (mattjoyce/kanban-skill)
- **adapter_version**: 0.2.0
- **when_to_use**: Visual task management, project tracking, sprint planning within Claude Code.

## Input Types

- Task creation (title, description, priority, assignee)
- Board management (columns, swimlanes)
- Status updates and transitions
- Sprint/release planning

## Output Target

```
wiki/tasks/                # Kanban board state persisted as markdown
wiki/projects/             # Project-level task aggregation
```

## Raw Mapping

- Kanban board data stored as markdown in `wiki/tasks/`
- Board configuration in `wiki/tasks/kanban-config.md`
- NOT stored in `raw/` (tasks are derived, not source material)

## Wiki Mapping

| Kanban Action | PKB Wiki Output |
|--------------|----------------|
| Create board | `wiki/tasks/<board-name>.md` with frontmatter |
| Add task | New `[[task-link]]` entry in board file |
| Move task | Update status in board file |
| Close task | Mark complete with completion date |
| Sprint planning | `wiki/projects/<project>/sprint-<n>.md` |

## Command Integration

- `/project:pkb <task>` -- Quick-add task to current board
- `/project:save` -- Commit after significant board changes
- `/project:lint` -- Verify task links are valid

## Safety Notes

- Kanban task data stays in `wiki/tasks/` -- do NOT scatter task files across wiki/.
- Board files use PKB-compatible frontmatter (type: task-board).
- Do NOT include personal/sensitive information in task descriptions.
- Archive completed boards to `wiki/tasks/archive/` rather than deleting.
