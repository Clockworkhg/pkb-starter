# Zotero MCP Adapter

## Metadata

- **skill_name**: Zotero MCP Server + Zotero MCP Skill
- **adapter_version**: 0.2.0
- **applies_to**: zotero-mcp (54yyyu/zotero-mcp), zotero-mcp-skill (kerim/zotero-mcp-skill)
- **when_to_use**: Accessing Zotero reference library from Claude Code, importing citations, managing bibliography.

## Input Types

- Zotero library queries (by collection, tag, author, date)
- Citation import requests (DOI, ISBN, arXiv ID)
- Bibliography generation
- PDF attachment access from Zotero library

## Output Target

```
wiki/sources/              # Literature source pages with Zotero citations
wiki/papers/               # Paper notes linked to Zotero items
raw/papers/<domain>/        # PDFs exported from Zotero
```

## Raw Mapping

| Zotero Action | PKB Raw Path |
|--------------|-------------|
| Export PDF | `raw/papers/<domain>/<author>_<year>_<title>.pdf` |
| Export citation data | `raw/papers/manifest.json` (update) |
| Collection export | `raw/papers/<domain>/` (batch) |

## Wiki Mapping

| Zotero Item | PKB Wiki Output |
|------------|----------------|
| Journal article | `wiki/sources/<short-title>.md` with Zotero key |
| Book | `wiki/sources/<title>.md` |
| Book section | `wiki/sources/<chapter-title>.md` |
| Conference paper | `wiki/papers/<short-title>.md` |
| Collection export | `wiki/sources/lit-<collection>.md` |

## Command Integration

- `/project:pkb zotero://<item-key>` -- Import Zotero item to PKB
- `/project:inbox` -- Process imported Zotero PDFs
- `/project:save` -- Commit after import
- `/project:lint` -- Verify Zotero-key backlinks

## Safety Notes

- Requires MCP server running locally (Zotero must be open).
- Configure `.claude/mcp.json` manually -- PKB does NOT auto-configure MCP.
- Zotero API key is managed by MCP, never stored in PKB files.
- PDFs exported from Zotero go to `raw/papers/`, not project root.
- Large collection exports may produce many wiki pages -- batch process incrementally.
