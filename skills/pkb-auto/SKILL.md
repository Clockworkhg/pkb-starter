# pkb-auto — Fully Automated Knowledge Ingest

## When to Use
- User throws anything at `/pkb <anything>`
- User wants a file, URL, or folder automatically processed end-to-end
- Trigger: `/pkb`, `/pkb --safe`, `/pkb --manual`, `/pkb --collect-only`, `/pkb --plan`

## Instructions

### Default Behavior: 10-Step Autopilot
Execute all steps without asking user:

1. **Parse input** — classify as file / folder / GitHub / Gist / WeChat / web / existing webpack
2. **Collect raw material** — copy files or run `tools/web_pack.py`
3. **Auto ingest** — extract content, classify by type, create wiki pages
4. **Update indices** — `wiki/index.md` + root `index.md`
5. **Auto archive** — move from `_INBOX` to `raw/imported_processed/`
6. **Update logs** — `wiki/log.md` + root `log.md`
7. **Health check** — `python tools/pkb_auto.py --check`
8. **Decision** — pass → continue, fail → report issues, no commit
9. **Git commit** — `[PKB] auto ingest: YYYY-MM-DD — <summary>`
10. **Report** — summary of new/updated pages, health status, commit hash

### Content Classification
| Type | Signals | Creates |
|------|---------|---------|
| Academic paper | PDF/DOCX + university/journal keywords | `wiki/sources/` + `wiki/concepts/` |
| Coursework | DOCX/PPTX + course/exam keywords | `wiki/sources/` + `wiki/outputs/` |
| Guidelines | DOC/DOCX + rules/standards keywords | `wiki/sources/` + `wiki/concepts/` |
| Project | PPTX + project/proposal keywords | `wiki/sources/` + `wiki/projects/` |
| GitHub/Gist | code/markdown/awesome-list | `wiki/sources/` + `wiki/concepts/` |
| Methodology | framework/pattern concepts | `wiki/concepts/` |
| Unknown | none of the above | `wiki/sources/` with `review_needed: true` |

### Wiki Page Format
Every page must have:
```yaml
---
created: YYYY-MM-DD
updated: YYYY-MM-DD
type: <source-note|concept|project|output>
tags: [relevant, tags]
source_path: raw/... (source-notes only)
---
```

### Pause Conditions
Only pause when:
- Sensitive info detected
- File deletion requested
- File unparseable
- Wiki page naming conflict
- Pre-commit secret scan fails

## Safety Notes
- Never delete raw/ files
- Never move user's original files
- Scan for API keys, tokens, passwords before archiving
- Mark uncertain classifications with `review_needed: true`
