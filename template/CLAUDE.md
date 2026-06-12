# CLAUDE.md — PKB Quick Reference

> Loaded automatically every Claude Code session. See [AGENTS.md](AGENTS.md) for full rules.

## Project Identity

**PKB** = a compiled personal knowledge base following the Karpathy LLM Wiki pattern.
Three-layer architecture: `raw/` (immutable source materials) → `wiki/` (LLM-maintained structured knowledge) → `skills/` (agent automation rules).

## Key Paths

```
raw/webpacks/        Web collection packs (web_pack.py output)
raw/papers/          Paper PDFs + manifest.json
wiki/concepts/       Atomic concept notes
wiki/sources/        Knowledge source index (with literature map)
wiki/projects/       Project notes
.claude/commands/    Slash Commands
.claude/hooks/       Harness Hooks
tools/               Python helper scripts
```

## Skill Routing Reference

| User Intent | Command |
|-------------|---------|
| Ingest anything | `/pkb <anything>` |
| Privacy cleanup | `/sanitize` |
| Health check | `/lint` |

## Coding Conventions

- **Wiki pages**: YAML frontmatter must include `created`/`updated`/`tags`/`type`
- **Wikilinks**: Use `[[wikilink]]` within wiki, Markdown links across layers
- **raw/ is immutable**: Append only, never modify or delete; metadata in manifest.json
- **Python tools**: `encoding='utf-8', errors='replace'` (Windows compatibility)
- **Git commit format**: `[PKB] <domain>: <summary>`

## Tools Reference

| Tool | Purpose |
|------|---------|
| `tools/check_collectors.py` | Collector availability detection — run before any web collection (`--json` / `--recommend`) |
| `tools/web_pack.py` | Structured web collection |
| `tools/pkb_auto.py` | Auto ingest + health check |
| `tools/docs_update.py` | Documentation freshness check and safe apply (`--check`/`--apply`/`--json`/`--summary`) |
| `tools/import_to_inbox.py` | File import to _INBOX |
| `tools/sanitize.py` | Privacy pattern scanner |
| `tools/pkb_update_client.py` | Check and apply pkb-starter updates |
| `tools/zskill_bridge.py` | Z-skills compatibility bridge |

## Common Workflows

### Auto Ingest (most common)
```
/pkb <file/URL/anything>
```
Fully automatic: collect → compile wiki → archive → health check → commit. No questions.

### Save
```
/save "commit message"
```
Auto-update docs → health check → commit. Omitting the message auto-generates one.

### Document Update
```
/docs-update
```
Diagnose + fix project docs, no commit. `/save` includes this step.

## Collector Priority

When collecting web content, run `python tools/check_collectors.py --json` first. Priority order:

1. **z-web-pack** — if fully installed, audited, adapter enabled, and bridge executable
2. **PKB built-in web_pack** — if Python deps (requests, bs4) are importable
3. **WebFetch** — always available as ultimate fallback (single-page only)
4. **gstack** — if registered as an available skill (complex JS pages)

**Never assume z-web-pack is available.** Always run the health check. Always auto-fallback — never fail because a specific collector is missing.

## Code of Conduct

1. **Fully automatic by default** — `/pkb` never pauses to ask "next step?"
2. **Safety first** — Detect and block API keys, tokens, passwords, private keys
3. **Transparent** — Clear change report after every operation
4. **Never destroy source material** — Don't move or delete files in raw/
5. **Maintain consistency** — Auto-update indices and logs after imports

## Pause Conditions

Only pause to ask the user when:
- Sensitive info detected (API key / token / password / private key / PII)
- File deletion requested
- File cannot be parsed (corrupted or unsupported format)
- Wiki page naming conflict that cannot auto-merge
- Git commit pre-flight secret scan fails

## Hooks

| Hook | Event | Purpose |
|------|-------|---------|
| `01_session_start.py` | SessionStart | Environment validation + context card + docs freshness |
| `02_pre_tool_use.py` | PreToolUse | Security gate: blocks secret commits, raw/ deletion |
| `03_post_tool_use.py` | PostToolUse | Wiki frontmatter + post-commit health check |
| `04_post_tool_use_failure.py` | PostToolUseFailure | 11-category error classification + recovery |
| `05_stop.py` | Stop | Uncommitted change reminder + session summary |
| `06_user_prompt_submit.py` | UserPromptSubmit | Smart routing suggestions |

---

*Keep in sync with [AGENTS.md](AGENTS.md). Last updated: 2026-06-12*
