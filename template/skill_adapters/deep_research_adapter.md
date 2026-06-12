# Deep Research Skills Adapter

## Metadata

- **skill_name**: Deep Research Skills (Weizhena/Deep-Research-skills)
- **adapter_version**: 0.2.0
- **when_to_use**: Multi-turn deep research with iterative refinement, source tracking, and structured evidence synthesis.

## Input Types

- Complex research questions
- Multi-source investigation topics
- Evidence synthesis requests
- Source credibility evaluation

## Output Target

```
wiki/outputs/research/     # Deep research reports
wiki/sources/              # Cited sources with evidence ratings
wiki/concepts/             # Extracted key concepts
```

## Raw Mapping

| Research Output | PKB Raw Path |
|----------------|-------------|
| Collected web sources | `raw/webpacks/<date>-<topic>/` |
| Downloaded references | `raw/papers/<domain>/` |
| Research brief | Embedded in wiki report |

## Wiki Mapping

| Research Phase | PKB Wiki Output |
|---------------|----------------|
| Initial exploration | `wiki/outputs/research/<topic>-exploration.md` |
| Deep dive findings | `wiki/outputs/research/<topic>-findings.md` |
| Evidence synthesis | `wiki/outputs/research/<topic>-evidence.md` |
| Source evaluation | `wiki/sources/<source-name>.md` with `evidence_quality` field |
| Key concepts | `wiki/concepts/<concept>.md` |

## Command Integration

- `/project:pkb <url>` -- Collect web sources before deep research
- `/project:inbox` -- Process collected materials into wiki
- `/project:save` -- Commit after each research iteration
- `/project:lint` -- Verify link integrity

## Safety Notes

- Deep research may consume significant Claude API tokens. Set budget expectations upfront.
- Mark confidence level on all findings: `confidence: high|medium|low`.
- If no credible sources are cited, mark `confidence: low` and add `review_needed: true`.
- Distinguish between established facts (`evidence_quality: verified`) and speculation (`evidence_quality: speculative`).
- Route cited sources through `wiki/sources/` with full metadata.
- Research results not in `wiki/outputs/research/` should be moved there before committing.
