# QMD Adapter

## Metadata

- **skill_name**: QMD (tobi/qmd)
- **adapter_version**: 0.2.0
- **when_to_use**: Semantic search and question-answering over local markdown knowledge bases.

## Input Types

- Natural language queries
- Semantic search across wiki/ and raw/
- Factual lookups
- Cross-document relationship discovery

## Output Target

```
QMD does NOT directly modify wiki/. Results are ephemeral.
To persist results, route through:
  wiki/outputs/             # Saved Q&A sessions
  wiki/concepts/            # Newly discovered concept relationships
```

## Raw Mapping

- QMD indexes `wiki/` and `raw/` but does not write to either.
- Search index is stored in QMD's own directory (not PKB-managed).

## Wiki Mapping

| QMD Output | PKB Action |
|-----------|-----------|
| Search result | Display to user. Do NOT auto-create wiki pages. |
| Discovered relationship | Suggest creating `wiki/concepts/<concept>.md` linking both. |
| Q&A session | Save to `wiki/outputs/<date>-qa-session.md` ONLY if user confirms. |

## Command Integration

- `/project:ask <question>` -- Route question through QMD if installed
- `/project:inbox` -- If QMD results suggest new source material, import first
- `/project:output qmd-results` -- Persist a QMD session to wiki

## Safety Notes

- QMD search results are read-only. Do NOT auto-create wiki pages from search results.
- User must explicitly confirm before any QMD output is persisted to wiki/.
- QMD does not require external API keys by default.
- If QMD index is stale, run reindex before relying on results.
