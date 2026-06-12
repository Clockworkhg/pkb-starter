# Document Skills Adapter

## Metadata

- **skill_name**: Anthropic Skills (anthropics/skills)
- **adapter_version**: 0.2.0
- **when_to_use**: Document processing, PDF handling, Office format conversion, content extraction from documents.

## Input Types

- PDF documents
- DOCX/PPTX/XLSX Office files
- Markdown/HTML/Text files
- Document conversion requests

## Output Target

```
wiki/outputs/              # Processed document output
wiki/sources/              # Source notes for processed documents
raw/imported_processed/    # Original documents after processing
```

## Raw Mapping

| Document Action | PKB Raw Path |
|----------------|-------------|
| PDF processed | `raw/imported_processed/<filename>` (original archived) |
| Office file converted | Output written to `wiki/outputs/`, original to `raw/imported_processed/` |
| Content extracted | Written as markdown in `wiki/outputs/` or `wiki/sources/` |

## Wiki Mapping

| Document Type | PKB Wiki Output |
|--------------|----------------|
| PDF paper | `wiki/papers/<title>.md` |
| PDF report | `wiki/outputs/<title>.md` |
| DOCX article | `wiki/sources/<title>.md` |
| PPTX presentation | `wiki/projects/<project>/slides-summary.md` |
| XLSX spreadsheet | `wiki/outputs/<name>-data-summary.md` |

## Command Integration

- `/project:pkb <file>` -- Import and process document through anthropic-skills
- `/project:inbox` -- Route processed output through inbox pipeline
- `/project:save` -- Commit after processing
- `/project:lint` -- Verify source links

## Safety Notes

- Anthropic Skills are official Anthropic tools. Observe their LICENSE (Anthropic Terms of Service).
- Do NOT process documents containing PII or sensitive data through external Claude API.
- Converted output goes to `wiki/`, never overwrites `raw/` originals.
- Large documents (>50 pages) may exceed context window -- split or summarize.
