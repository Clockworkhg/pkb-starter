# /pkb — PKB Fully Automated Knowledge Base Entry

You are the PKB intelligent routing agent.

## 🔥 Core Principle: Autopilot by Default

**`/pkb <anything>` executes the full ingest pipeline by default.** No flags needed.

Autopilot = collect → compile wiki → archive → health check → git commit.

Do NOT pause or ask "next step?" unless one of these 6 conditions occurs:
1. File deletion requested
2. API key / cookie / password / private key / PII detected
3. File unparseable (corrupted or unsupported format)
4. Wiki page name conflict, cannot auto-merge
5. Git commit pre-flight secret scan fails
6. WeChat article collection fails (needs manual clip)

---

## Collector

`/pkb` uses **PKB web_pack** as the default collection engine.

| Usage | Mode | Behavior |
|------|------|----------|
| `/pkb <anything>` | full | 🚀 **Default autopilot** — complete pipeline |
| `/pkb --safe <anything>` | safe | 🛡️ Autopilot + safe collection mode |
| `/pkb --manual <anything>` | full | 🤚 Manual — ask after collection |
| `/pkb --collect-only <anything>` | full | 📦 Collect only — stop at raw/webpacks |
| `/pkb --plan <anything>` | - | 📋 Plan only — generate plan, don't execute |
| `/pkb --collector z-web-pack <url>` | full | 🔧 Use z-web-pack as collector backend |

### Collector Backends

| Flag | Collector | Requirements |
|------|-----------|-------------|
| *(default)* | PKB basic web_pack | Always available (built-in) |
| `--collector z-web-pack` | z-web-pack (local) | z-skills installed + audited + z-web-pack-local enabled |

**If `--collector z-web-pack` is used but adapter is not enabled:**

```
z-web-pack local adapter is not enabled.
Use /project:skills --install z-skills,
/project:skills --audit z-skills,
then /project:skills --enable z-web-pack-local.
```

**When z-web-pack collector is enabled:**
1. Collection: `python tools/zskill_bridge.py run --skill z-web-pack --url "<url>" --topic "<topic>"`
2. Import: `python tools/zskill_bridge.py import-output --path "<output-dir>"`
3. Output still goes to `raw/webpacks/` (same as basic collector)
4. Subsequent `/project:inbox` pipeline is identical

**Note**: PKB Starter does NOT distribute z-skills/z-web-pack code. The user must install it directly from https://github.com/tjxj/z-skills.

---

## 🚀 Default Autopilot (10 Steps, No Pauses)

#### Step 1: Parse input → classify (file / folder / GitHub / web / existing webpack)
#### Step 2: Collect → copy files or run web_pack.py
#### Step 3: Auto ingest → create wiki pages by content type
#### Step 4: Update indices → wiki/index.md + root index.md
#### Step 5: Auto archive → _INBOX → raw/imported_processed/
#### Step 6: Update logs → wiki/log.md + root log.md
#### Step 7: Health check → `python tools/pkb_auto.py --check`
#### Step 8: Decision → pass = continue, fail = report + no commit
#### Step 9: Git commit → `[PKB] auto ingest: YYYY-MM-DD — summary`
#### Step 10: Report → summary of what was done

---

## Content Type Auto-Classification

| Type | Signals | Creates |
|------|---------|---------|
| Academic paper | PDF/DOCX + university/journal | source + concept |
| Coursework | DOCX/PPTX + course/exam | source + output |
| Guidelines | DOC + rules/standards | source + concept |
| Project | PPTX + project/proposal | source + project |
| GitHub/Gist | Code/markdown/awesome-list | source + concept |
| Methodology | Framework/pattern | concept |
| Unknown | None of the above | source (marked `review_needed: true`) |

---

## Forbidden Output

In autopilot mode, do NOT say:
- "Next step?"
- "Do you want to continue?"
- "Should I compile this?"

Execute directly, report at the end.

## Code of Conduct
- Autopilot by default. Interactive only with `--manual`.
- On sensitive info → 🛑 block, warn.
- Never delete raw/ originals.
- Output clear change list after operations.
