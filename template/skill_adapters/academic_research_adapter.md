# Academic Research Skills Adapter

## Metadata

- **skill_name**: Academic Research Skills (Imbad0202/academic-research-skills)
- **adapter_version**: 0.2.0
- **when_to_use**: Academic paper analysis, literature review planning, research methodology design, synthesis of findings across sources.

## Input Types

- Research questions and hypotheses
- Academic paper PDFs (imported to _INBOX first)
- Literature search results
- Methodological requirements
- Synthesis instructions

## Output Target

```
wiki/outputs/research/     # Research reports, syntheses, methodology plans
wiki/sources/              # Literature source notes (one per paper)
wiki/concepts/             # Key concepts extracted during research
wiki/papers/               # Paper analysis and summaries
```

## Raw Mapping

| Research Output | PKB Raw Path |
|----------------|-------------|
| Paper PDFs | `raw/papers/<domain>/<filename>.pdf` |
| Research data | `raw/projects/<project>/data/` |
| Methodology templates | `templates/skill_adapters/` (reference) |

## Wiki Mapping

| Research Phase | PKB Wiki Output |
|---------------|----------------|
| Research architect design | `wiki/outputs/research/<topic>-methodology.md` |
| Literature search results | `wiki/sources/lit-<topic>.md` |
| Paper analysis | `wiki/papers/<short-title>.md` |
| Evidence synthesis | `wiki/outputs/research/<topic>-synthesis.md` |
| Key concepts | `wiki/concepts/<concept-name>.md` |
| Report compilation | `wiki/outputs/research/<topic>-report.md` |

## Command Integration

- `/project:inbox` -- Process imported papers before research
- `/project:pkb <paper.pdf>` -- Import and start research pipeline
- `/project:save` -- Commit after each research phase
- `/project:lint` -- Verify citation links after synthesis

## Safety Notes

- All research output goes to `wiki/outputs/research/` or `wiki/sources/`, NOT project root.
- Mark synthesis confidence in frontmatter: `confidence: high|medium|low|review_needed`.
- Cite all sources with full `[[wikilink]]` backlinks.
- If no citations are provided, mark `confidence: low` and add `review_needed: true`.
- Academic integrity: do not fabricate citations or data.
