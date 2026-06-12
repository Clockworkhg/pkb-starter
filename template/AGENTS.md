# AGENTS.md — PKB System Rules

> This is the PKB "constitution". All agent behavior must follow this file.
> Version: 1.0.0 | Last updated: YYYY-MM-DD
>
> Quick reference: [CLAUDE.md](CLAUDE.md) — loaded automatically every session

---

## I. Three-Layer Architecture

```
raw/          ← Layer 1: Raw materials (immutable, append-only)
wiki/         ← Layer 2: LLM-maintained structured knowledge (Markdown)
skills/       ← Layer 3: Meta-rules / Agent Skills (how to maintain wiki)
AGENTS.md     ← Layer 4: Schema (this file, defines rules)
```

### 1.1 Raw Layer Rules
- **raw/ is append-only**. Imported original files are permanently retained.
- Subdirectories by type: `webpacks/`, `clippings/`, `courses/`, `papers/`, `projects/`, `creation/`, `media/`, `personal/`, `assets/`
- Auto-generate `manifest.json` on import: records source, original path, import time.
- **Strictly prohibit** importing sensitive files (API keys, tokens, passwords, etc.) into raw/.

### 1.2 Wiki Layer Rules
- **wiki/ is maintained by LLM**. Humans may edit, but the primary maintainer is the Agent.
- All wiki pages use Markdown with YAML frontmatter.
- Every page must have `created`, `updated`, `tags`, `type` fields.
- Pages interconnect via `[[wikilink]]`.
- Directory structure:
  - `sources/` — knowledge source index
  - `concepts/` — concept notes (atomic, one concept per page)
  - `projects/` — project notes
  - `outputs/` — outputs (articles, reports, etc.)

### 1.3 Skills Layer Rules
- Each subdirectory under `skills/` is one skill, containing prompt templates and rules.
- Skills may reference scripts under `tools/`.

---

## II. Auto-Routing Rules

When receiving `/pkb <anything>`, the agent must auto-classify by priority:

### 2.1 File Path (local file)
**Trigger**: Input is an existing local file path.
**Action**: Run `python tools/import_to_inbox.py <path>` → file copied to `_INBOX/imported/`, generate manifest.

### 2.2 Directory Path
**Trigger**: Input is an existing local directory path.
**Action**: Run `python tools/import_to_inbox.py <path> --folder` → entire directory copied, auto-skip `.git`, `node_modules`, `.venv`, `__pycache__`, etc.

### 2.3 HTTP/HTTPS URL
**Trigger**: Input contains `http://` or `https://`.
**Action**: Run `python tools/web_pack.py --topic "<topic>" --url "<url>"` → collect web content to `raw/webpacks/YYYY-MM-DD-topic/`.
- Default mode: `full` (complete image pipeline + yt-dlp)
- GitHub repos auto-use GitHub Collector mode (API → git clone)
- Content extraction: readability-lxml → trafilatura → BeautifulSoup → Jina (fallback chain)

### 2.4 Question / Keywords
**Trigger**: Doesn't match any above pattern.
**Action**: Search `wiki/` and `raw/` for relevant content, return structured answer. If no results, suggest collecting related web pages.

---

## III. File Import Rules

Call `python tools/import_to_inbox.py`:
1. **Copy by default**, never move original files.
2. Generate `manifest.json` with source_path, imported_at, file_type, size_bytes.
3. **Auto-rename** on collision (append _1, _2 suffix).
4. **Skip directories**: `.git`, `node_modules`, `.venv`, `__pycache__`, etc.
5. **Sensitive info detection**: Scan content, block and warn on API keys, tokens, passwords, private keys.

---

## IV. Web Collection Rules

Call `python tools/web_pack.py`:
1. Extract content from each URL (readability algorithm or BeautifulSoup)
2. Download in-page images to `assets/` subdirectory
3. Generate structured webpack directory
4. Create source index page under `wiki/sources/`

---

## V. /ask Query Rules

1. Full-text search `wiki/` Markdown files (by frontmatter tags)
2. Search `raw/` for related files
3. Integrate info, return structured answer with related sources and knowledge gaps
4. If the question could generate a concept note, suggest saving to `wiki/concepts/`

---

## VI. /output Save Rules

1. Save valuable content from current conversation to `wiki/outputs/`
2. File naming: `YYYY-MM-DD-short-description.md`
3. Include frontmatter: `created`, `tags`, `source_conversation`

---

## VII. /lint Health Check Rules

Check these items:
1. **Broken wikilinks**: `[[target]]` pointing to non-existent pages
2. **Orphan pages**: pages with no inbound links
3. **Stale content**: `updated` >90 days ago with `#active` tag
4. **Missing frontmatter**: pages missing `created`/`updated`/`tags`
5. **Sensitive info leaks**: scan wiki/ and raw/ for API keys/tokens
6. **Empty directories**: under raw/ and wiki/
7. **Large files**: >50MB in raw/

---

## VIII. Privacy & API Key Security

### 8.0 Web Pack Cookie Rules
- `--browser-cookies` only available in `--mode full` + explicit flag + `--download-media`
- Cookies only passed to yt-dlp, never used for HTTP page requests
- Cookies **never written** to any file (not manifest.json, not markdown, not logs)

### 8.1 Absolutely Prohibited
- **Prohibit** writing any API keys, tokens, passwords, private keys into raw/ or wiki/
- **Prohibit** importing `.env` files or equivalent config files
- **Prohibit** hardcoding any credentials in wiki pages

### 8.2 Detection Rules
Block and warn on these patterns:
- Filenames: `.env`, `credentials.json`, `serviceAccount.json`, `id_rsa`, `*.pem`, `*.p12`, `*.pfx`
- Content: `api_key=`, `apiKey:`, `"token":`, `"secret":`, `"password":`, `"private_key":`, `-----BEGIN RSA`, `-----BEGIN OPENSSH`

### 8.3 .gitignore Guarantee
`.gitignore` must exclude sensitive files (see `template/.gitignore`).

---

## IX. Git Save & Rollback

### 9.1 Auto Save (/save)
- Remind user after important operations that `/save` can commit changes.
- Commit format: `[PKB] YYYY-MM-DD: short description`
- **Do not** auto push to remote.

### 9.2 Rollback (/rollback)
- `/rollback` — view recent 10 commits
- `/rollback <N>` — revert N commits (default `git revert`)
- `/rollback --hard <N>` — hard reset (requires double confirmation)

---

## X. Agent Code of Conduct

1. **Judge before acting**: Auto-classify input type first, then execute.
2. **Safe by default**: On sensitive info, block import and warn user.
3. **Transparent operations**: Clear report after each operation.
4. **No destructive actions**: Don't move originals, don't delete raw/ files.
5. **Maintain wiki consistency**: Check and update wiki indices after imports.

---

## XI. Autopilot Policy

### 11.1 Trigger
- **`/pkb <anything>` is autopilot by default** (no `--auto` flag needed)
- `--manual` flag switches to interactive mode
- `--collect-only` flag collects without compiling wiki
- `--plan` flag generates plan without executing

### 11.2 Auto-completed Operations
1. Scan and identify all input types
2. Copy files to `_INBOX/imported/`
3. Run `tools/web_pack.py` for URLs
4. Extract text from files
5. Auto-classify by content type
6. Create wiki source-notes with complete frontmatter
7. Create/update concept and project pages
8. Update indices and logs
9. Archive processed files
10. Fix all `source_path` frontmatter references
11. Run health checks
12. Git commit on health check pass

### 11.3 Forbidden Phrases (in autopilot mode)
- ❌ "Next step?"
- ❌ "Do you want to continue?"
- ❌ "Should I compile this?"
- ✅ Execute directly, report at the end.

### 11.4 Pause Conditions
Only pause and ask user when:
- Sensitive info detected (API key / token / password / private key / PII)
- File deletion requested
- File unparseable (corrupted or unsupported format)
- Wiki page naming conflict, cannot auto-merge
- Git commit pre-flight secret scan fails

---

## XII. Documentation Auto-Update System

`tools/docs_update.py` detects drift between filesystem and project docs (`index.md`, `COMMANDS.md`, `AGENTS.md`, `CLAUDE.md`, `log.md`).

Triggered by `/save` (Step 2) or standalone `/docs-update` command.
Only edits project-level markdown files — never touches `wiki/` content.

---

## XIII. Optional Skill Integration

### 13.1 Registration

All third-party skills must be recorded in `SKILL_LINKS.md` before use.
This includes skills installed via `install_skills.py` or manually into `skills/_vendor/`.

### 13.2 Output Routing

Any third-party skill output MUST pass through a PKB adapter that maps it to `raw/` or `wiki/`:

| Skill Output Type | PKB Target |
|------------------|-----------|
| Academic research results | `wiki/outputs/research/` or `wiki/papers/` |
| Literature sources and citations | `wiki/sources/` |
| Extracted concepts | `wiki/concepts/` |
| Project-related output | `wiki/projects/` |
| Search results | Do NOT modify wiki. Route through `/project:inbox` or `/project:output`. |
| Task/kanban data | `wiki/tasks/` |
| Document conversions | `wiki/outputs/<name>.md`, original to `raw/imported_processed/` |

### 13.3 Prohibited Output Locations

Third-party skill results must NEVER scatter files across the project root.
Acceptable paths: `wiki/`, `raw/`, `templates/`, `skills/_vendor/`.
Unacceptable: `*.md` at project root, `output/`, `results/`, `data/` (unless explicitly created by user).

### 13.4 Risk-Level Rules

| Risk Level | Policy |
|-----------|--------|
| `low` | Auto-install when selected in profile. |
| `medium` | Install with warning. Review adapter before first use. |
| `high` | Require explicit `--enable-risky`. Display MCP/runtime requirements. Never auto-enable. |
| `reference_only` | Never install. Catalog entry only. |

### 13.5 Adapter Protocol

Each skill has an adapter in `templates/skill_adapters/<adapter>.md` defining:
- When to use the skill
- What input types it accepts
- Where output must be placed in PKB structure
- How to integrate with PKB commands (`/project:inbox`, `/project:lint`, `/project:save`)

Adapters are copied to the target PKB on skill installation. They are reference documents for the LLM, not executable code.

### 13.6 MCP-Required Skills

Skills requiring MCP servers (e.g., zotero-mcp) need manual configuration:
1. Install the MCP server separately (follow its documentation).
2. Add server entry to `.claude/mcp.json` manually.
3. PKB NEVER auto-configures MCP servers.
4. PKB NEVER reads or stores MCP API keys.

---

## XIV. Language Policy

### 14.1 Language Detection

On every session, read `pkb.config.json` and check:

- `language` — UI/display language preference
- `wiki_language` — default language for wiki page generation
- `output_language` — default language for reports and command summaries

### 14.2 Behavior by Language

| Setting | Behavior |
|---------|----------|
| `language: "en"` | All output in English. This is the default. |
| `language: "zh-CN"` | All output in Simplified Chinese. |
| `language: "bilingual"` | Root docs in English, wiki pages in Chinese. |
| `wiki_language: "zh-CN"` | Generate wiki pages, source notes, concept pages in Simplified Chinese unless user explicitly requests another language. |
| `wiki_language: "en"` | Generate wiki pages in English. |
| `output_language: "zh-CN"` | Generate reports, logs, command summaries in Simplified Chinese. |
| `output_language: "en"` | Generate reports in English. |

### 14.3 Wiki Page Generation Rules (zh-CN mode)

When `wiki_language` is `"zh-CN"`:

1. Page titles use Chinese unless the concept has a well-known English name.
2. Page content is written in natural Simplified Chinese.
3. YAML frontmatter uses English keys (`created`, `updated`, `tags`, `type`).
4. Tag values may use Chinese (e.g., `tags: [机器学习, 论文]`).
5. `[[wikilink]]` targets use the page title language (Chinese for Chinese-titled pages).
6. Technical commands, file paths, and code remain in English.
7. Filenames use safe slugs (ASCII) but page titles use Chinese.

### 14.4 Report Generation Rules (zh-CN mode)

When `output_language` is `"zh-CN"`:

1. `/project:lint` output in Chinese.
2. `/project:save` commit messages may use Chinese.
3. `update_report.md` sections use Chinese headings.
4. Health check summaries use Chinese labels.
5. Error and warning messages use Chinese descriptions.

### 14.5 Mixed Mode

Users may request English output at any time regardless of language settings. The language setting is a default, not a constraint. If the user types a question in English, respond in English. If they type in Chinese, respond in Chinese.

### 14.6 GBK/ASCII Compatibility

All tool output (Python scripts, shell commands) must use ASCII-safe characters. Chinese text is only used within wiki pages, Markdown documents, and Claude Code responses — never in terminal escape sequences or binary output.

---

*Synchronized with CLAUDE.md. Last updated: YYYY-MM-DD*
