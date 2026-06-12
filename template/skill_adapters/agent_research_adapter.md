# Agent Research Skills Adapter

## Metadata

- **skill_name**: Agent Research Skills (lingzhi227/agent-research-skills)
- **adapter_version**: 0.2.0
- **when_to_use**: Agent-based research pipeline for literature search, paper analysis, and citation extraction.

## Input Types

- Literature search queries
- Paper metadata (title, authors, DOI, abstract)
- Citation network exploration
- Batch paper analysis requests

## Output Target

```
wiki/papers/               # Paper summaries and analysis
wiki/sources/              # Literature collection pages
wiki/outputs/research/     # Agent-generated research output
wiki/concepts/             # Extracted concepts from papers
```

## Raw Mapping

| Research Output | PKB Raw Path |
|----------------|-------------|
| Downloaded papers | `raw/papers/<domain>/<filename>.pdf` |
| Citation data | `raw/papers/manifest.json` (updated) |
| Agent run logs | Not stored -- summary in wiki report |

## Wiki Mapping

| Agent Action | PKB Wiki Output |
|-------------|----------------|
| Literature search | `wiki/sources/lit-<query>.md` with result table |
| Paper analysis | `wiki/papers/<short-title>.md` |
| Citation extraction | Inline citations in paper notes with `[[wikilink]]` |
| Batch processing | `wiki/outputs/research/<topic>-batch-analysis.md` |
| Concept extraction | `wiki/concepts/<concept>.md` |

## Command Integration

- `/project:pkb <paper.pdf>` -- Import paper before agent analysis
- `/project:inbox` -- Process imported papers
- `/project:save` -- Commit after batch completion
- `/project:lint` -- Verify citation links

## Safety Notes

- Agent may consume significant tokens for batch operations -- set limits.
- Verify agent-extracted citations against original papers when possible.
- Mark agent-generated content with `generated_by: agent-research-skills` in frontmatter.
- If paper metadata is incomplete, mark `review_needed: true`.
- Batch results go to `wiki/outputs/research/`, individual papers to `wiki/papers/`.
