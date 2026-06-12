# AGENTS.md — PKB System Rules

> This is the PKB "constitution". All agent behavior must follow this file.
> Version: 1.0.0 | Last updated: 2026-06-12
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
**Action**:
  1. **Run `python tools/check_collectors.py --json`** to detect the best available collector
  2. Use the recommended collector (see §2.X for full priority rules)
  3. If collection succeeds: continue to Step 3 (auto ingest)
  4. If collection fails: try next collector in `fallback_chain`

**NEVER assume z-web-pack is available.** Always run the health check. Always auto-fallback.

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

### 4.0 Collector Health Check (MANDATORY)

**Before any web collection**, run `python tools/check_collectors.py --json`. Parse the `recommendation` and use the recommended collector. Never skip this step. Never assume z-web-pack is available.

### 4.1 Collector Priority

| Priority | Collector | When to Use |
|----------|-----------|-------------|
| 1 | z-web-pack (local) | Fully available: installed + audited + adapter enabled + bridge executable |
| 2 | PKB built-in web_pack | Python deps (requests, bs4) importable |
| 3 | WebFetch (Claude Code built-in) | Always available — single-page, JS-rendered pages that web_pack can't handle |
| 4 | gstack (headless browser) | gstack skill registered — complex interactions, login-required pages |

### 4.2 Fallback Rules

1. **Auto-fallback**: If the recommended collector is DEGRADED or UNAVAILABLE, skip to the next AVAILABLE collector in priority order.
2. **Runtime failure**: If the selected collector fails at runtime, retry with the next collector in `recommendation.fallback_chain`.
3. **Never fail** because a collector is missing. WebFetch is the ultimate fallback — always available.
4. **Explicit override**: If `--collector <name>` is passed, skip detection and use that collector directly. If it fails, report and suggest alternatives — do not silently fall back.
5. **JS-rendered pages**: If `web_pack.py` returns weak/empty content (detected via `detect_content_weakness()`), automatically retry with WebFetch.

### 4.3 Built-in Collector

Call `python tools/web_pack.py`:
1. Extract content from each URL (readability algorithm or BeautifulSoup)
2. Download in-page images to `assets/` subdirectory
3. Generate structured webpack directory
4. Create source index page under `wiki/sources/`

### 4.4 WebFetch Collector

Use Claude Code's built-in WebFetch tool:
1. Fetch single page content
2. Create `raw/webpacks/<YYYY-MM-DD>-<topic>/` directory
3. Save content as `snapshots/<page>.md`
4. Generate minimal `manifest.json` and `README.md`
5. Note: no depth crawling, no image download — single page only

### 4.5 gstack Collector

Use gstack skill for headless browser collection. Best for JS-heavy SPAs, login-required pages, multi-step interactions. Route output to `raw/webpacks/<topic>/`.

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
8. Do not generate Chinese filenames unless the user explicitly requests them.
9. Markdown filenames, directory names, slugs, and source note filenames default to ASCII-safe English slugs (e.g., `personal-knowledge-base.md`, not `个人知识库.md`).

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

## XV. Hooks System

### 15.1 Overview

PKB uses Claude Code harness hooks to elevate security rules, health checks, and state management from the prompt layer to the harness layer. Hooks are registered in `.claude/settings.json` with scripts in `.claude/hooks/`.

**Design principles**:
- Hook failures never block workflow (except security violations)
- Idempotency: cooldown windows prevent redundant execution (state cached in `_INBOX/.hook_state/`)
- Performance budget: all hooks total < 65s
- Dry-run mode: every script supports `--dry-run` for testing

### 15.2 Hook Inventory

| # | Hook | Event | Matcher | Behavior | Blocks? |
|---|------|-------|---------|----------|---------|
| 1 | `01_session_start.py` | SessionStart | — | Environment validation + context card + docs freshness | No |
| 2 | `02_pre_tool_use.py` | PreToolUse | All tools | Blocks secret commits, raw/ deletion, sensitive file writes | **Yes** |
| 3 | `03_post_tool_use.py` | PostToolUse | Write\|Edit | Wiki frontmatter quick check; post-commit full health check | No |
| 4 | `04_post_tool_use_failure.py` | PostToolUseFailure | — | 11-category error classification + recovery suggestions | No |
| 5 | `05_stop.py` | Stop | — | Uncommitted change reminder + INBOX staleness + session summary | No |
| 6 | `06_user_prompt_submit.py` | UserPromptSubmit | — | Smart routing: URL/path/CNKI/paper suggestions | No |

### 15.3 Shared Library (hook_lib.py)

`hook_lib.py` provides common utilities for all hook scripts:

| Module | Function |
|--------|----------|
| `get_root()` | Resolve PKB root from `PKB_ROOT` env var |
| `is_safe_to_run(name, cooldown)` | Idempotency guard — skip within cooldown window |
| `warn(msg)` / `block(msg)` | Severity-graded output — warn is non-blocking, block exits 1 |
| `hook_timer(secs)` | Timeout context manager — auto-aborts hung hooks |
| `check_pkb_env()` | Verify PKB_ROOT and critical directories exist |
| `scan_content_for_secrets()` | 11 secret pattern detectors (API key / token / private key / password) |
| `is_sensitive_filename()` | Sensitive filename detection (.env / credentials / .pem / .key) |
| `is_protected_write_path()` | Protected path check (raw/ / .claude/) |
| `is_protected_delete_path()` | Forbidden delete path check (raw/ / wiki/ / .claude/) |
| `git_staged_files()` | List staged files (git diff --cached) |
| `git_uncommitted_files()` | List modified or untracked files |
| `count_wiki_pages()` | Count wiki pages by type |
| `load_hook_config()` | Merge settings.json + settings.local.json config |
| `is_dry_run()` | Detect `--dry-run` flag |

### 15.4 Security Gate Rules (PreToolUse)

| Trigger | Action | Notes |
|---------|--------|-------|
| `Bash(git commit)` + staged files contain secret patterns | 🛑 block | Detects API key / token / password / private key |
| `Bash(rm/del/rd)` + path under `raw/` | 🛑 block | "Never delete raw/ materials" |
| `Write/Edit` + path under `raw/` | 🛑 block | raw/ is append-only, cannot modify existing files |
| `Write/Edit` + filename matches sensitive pattern | 🛑 block | .env / credentials / .pem / .key / id_rsa |
| `Bash(git push)` | ⚠️ warn | Push is not default PKB behavior |

**Note**: Does not duplicate existing `settings.json` `deny` rules (`rm -rf`, `git push --force`, `curl`, `wget`).

### 15.5 Error Classification (PostToolUseFailure)

| Category | Trigger Pattern | Recovery Suggestion |
|----------|----------------|---------------------|
| network | ConnectionError / Timeout | Retry or use `--collect-only` |
| commit_blocked | git commit rejected | Run `/lint` to see health check issues |
| permission | Permission denied | Check file locks |
| security | Sensitive content detected | Remove API key / token |
| encoding | GBK encoding error | `export PYTHONIOENCODING=utf-8` |
| auth | 401 / 403 / Jina fail | Use raw URL or manual collection |
| not_found | 404 / FileNotFoundError | Check URL/path spelling |
| invalid_url | Invalid protocol | Use `/pkb <path>` for local files |
| server_error | 502/503/504 | Retry later |
| dependency | ModuleNotFoundError | `pip install <package>` |
| tool_missing | yt-dlp/ffmpeg missing | Install required tool |

### 15.6 Smart Routing (UserPromptSubmit)

| Input Pattern | Suggestion |
|---------------|------------|
| GitHub/Gist/WeChat URL | `/pkb <url>` |
| Generic URL | `/pkb <url>` or `/web <url>` |
| File path | `/pkb <path>` |
| Contains "CNKI"/"知网" | `/pkb-cnki search ...` |
| Contains "paper"/"literature review" | `/paper` or `/research` |
| Contains "save"/"commit" | `/save` |
| Contains "check"/"lint" | `/lint` |

> Suggestion only, never redirects. 30-second cooldown to avoid noise.

### 15.7 Configuration & Overrides

- **Global config**: `.claude/settings.json` — registers all 6 hooks
- **User overrides**: `.claude/settings.local.json` (gitignored) — disable or tune per hook
- **Hook state cache**: `_INBOX/.hook_state/` (gitignored) — stores cooldown timestamps; loss is non-fatal

### 15.8 Maintenance Rules

- Add hook script → update `.claude/settings.json` registration + update CLAUDE.md hooks table + update this §15.2
- Modify hook behavior → update corresponding subsection + sync CLAUDE.md
- Hook troubleshooting → check `_INBOX/.hook_state/` cache + `--dry-run` test
- `/save` auto-detects whether CLAUDE.md includes hooks entries

---

*Synchronized with CLAUDE.md. Last updated: 2026-06-12*
