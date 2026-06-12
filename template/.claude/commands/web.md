# /web — Raw Layer Web Collection

You are the PKB raw layer web collection agent.

## Language Detection

Before executing, read `pkb.config.json`. If `language` / `output_language` is set to `zh-CN`:
1. Collection status messages, completion summaries, and next-step suggestions default to Simplified Chinese.
2. Collected content language is determined by the source page, not the PKB language setting.
3. Webpack directory names and file paths remain in English (ASCII slugs).
4. If the user explicitly requests English output, follow the user's preference.

## Core Principles

- `/web` is a **raw layer collection command**, only generates `raw/webpacks/` materials
- `/web` does **not directly modify wiki**
- **Collector auto-detection**: Before collection, `check_collectors.py` probes all backends and recommends the best one
- **Auto-fallback**: If the preferred collector is unavailable, automatically falls back to next best. Never fails due to missing collector.
- **Default collector**: PKB basic web_pack (v0.1.0)
- **Optional collector**: z-web-pack (requires user-installed z-skills + audit + enable)
- Collects public web pages, extracts content, generates standard webpack output
- After completion, suggest user run `/inbox` to compile webpack into wiki

## Collector Backends

Collector priority (highest to lowest): z-web-pack → built-in web_pack → WebFetch → gstack

| Flag | Collector | Auto-Detect | Requirements |
|------|-----------|------------|-------------|
| *(auto)* | Best available | **Yes** — `check_collectors.py` | None — always finds a working collector |
| *(default)* | PKB basic web_pack | Yes | Python deps (requests, bs4) |
| `--collector z-web-pack` | z-web-pack (local, user-installed) | Yes | z-skills installed + audited + z-web-pack-local enabled |
| `--collector webfetch` | WebFetch (Claude Code built-in) | Yes | Always available |
| `--collector gstack` | gstack (headless browser) | Yes | gstack skill registered |

### Basic Collector (default)
PKB's built-in `tools/web_pack.py`. Handles public web pages, generates standard webpack output. Always available when Python deps are installed.

### Z-Web-Pack Collector (optional)
Uses a user-installed local copy of z-web-pack from `skills/_vendor/z-skills/z-web-pack/`. 

**Prerequisites:**
1. `/project:skills --install z-skills` — user explicitly opts in
2. `/project:skills --audit` — audits z-skills license and structure
3. `/project:skills --enable z-web-pack-local` — activates adapter

If z-web-pack adapter is not enabled, the agent responds:
```
z-web-pack local adapter is not enabled.
Use /project:skills --install z-skills,
/project:skills --audit z-skills,
then /project:skills --enable z-web-pack-local.
```

**Note**: PKB Starter does NOT distribute z-skills code. The user clones directly from https://github.com/tjxj/z-skills. Output is routed to `raw/webpacks/` — same location as the basic collector.

### WebFetch Collector (built-in fallback)
Claude Code's built-in WebFetch tool. Always available. Best for: single-page JS-rendered content that `web_pack.py` cannot fetch. Limited to one page at a time — no depth crawling, no image download, no structured webpack output. Use when `web_pack.py` returns weak/empty content.

### gstack Collector (headless browser)
Headless browser for complex interactions. Best for: login-required pages, multi-step forms, dynamic SPAs. Requires gstack skill registration.

## Task

Collect one or more web pages' content, generate standardized raw layer webpack.

## Execution Steps

### 0. Collector Health Check (ALWAYS RUN FIRST)

Before any collection, run the collector availability check:

```bash
python tools/check_collectors.py --json
```

**Decision logic:**
1. Parse the JSON output. Read `recommendation.collector`.
2. Use the recommended collector. If status is DEGRADED for the recommended collector, skip to the next AVAILABLE collector in the `fallback_chain`.
3. **Never fail** because a specific collector is missing. Always walk the fallback chain.
4. If `--collector <name>` is explicitly passed, skip auto-detection and force that collector.

| Recommended Collector | Action |
|----------------------|--------|
| z-web-pack (fully AVAILABLE) | Run via zskill_bridge: `python tools/zskill_bridge.py run --skill z-web-pack --url "<url>" --topic "<topic>"` then `python tools/zskill_bridge.py import-output --path "<output-dir>"` |
| z-web-pack (DEGRADED) | Log degradation reason from JSON warnings. Fall back to built-in web_pack. |
| PKB built-in web_pack | Run: `python tools/web_pack.py --topic "<topic>" --url "<url>"` |
| WebFetch | Use built-in `WebFetch` tool to fetch the page content. Manually create webpack directory structure. |
| gstack | Use gstack skill for headless browser collection |

**Fallback rules:**
- If recommended collector fails at runtime: retry with next collector in `recommendation.fallback_chain`
- If `web_pack.py` returns weak content (JS-only page): fall back to WebFetch for that specific URL
- If WebFetch is used: note in the report that structured webpack was not generated — suggest running `/inbox` with the raw content

### 1. Determine topic and URLs
- If user specified topic, use directly
- If not, visit first URL to get title, auto-generate topic name
- Supports multiple URLs (space-separated)

### 2. Run collector

Use the collector chosen in Step 0. Report which collector was selected and why.

**Auto-detect (recommended):**
Follow the recommendation from `check_collectors.py --json`. The agent runs the appropriate command based on the table in Step 0.

**Default (basic) collector:**
```bash
python tools/web_pack.py --topic "<topic>" --url "<url>" --max-depth 1 --max-pages 80

# Multiple URLs
python tools/web_pack.py --topic "<topic>" --url "<url1>" --url "<url2>"

# GitHub repository URL (converts to raw automatically)
python tools/web_pack.py --topic "<topic>" --url "https://github.com/user/repo/tree/main/path"
```

**Z-Web-Pack collector (if --collector z-web-pack or auto-detected as AVAILABLE):**
1. Verify z-web-pack-local is enabled (check pkb.config.json skills.enabled_adapters includes z_skills_adapter.md)
2. If not enabled, respond with the prerequisite instructions and fall back to built-in web_pack.
3. Run: `python tools/zskill_bridge.py run --skill z-web-pack --url "<url>" --topic "<topic>"`
4. After z-web-pack completes, run: `python tools/zskill_bridge.py import-output --path "<z-web-pack-output-dir>"`
5. Output is routed to `raw/webpacks/<topic>/` — same location as basic collector
6. Continue with normal /inbox pipeline from there

**WebFetch collector (if auto-detected or JS-rendered page needed):**
1. Use Claude Code's built-in WebFetch tool to fetch the URL
2. Create `raw/webpacks/<YYYY-MM-DD>-<topic>/` directory manually
3. Save fetched content as `snapshots/<page>.md`
4. Generate minimal `manifest.json` and `README.md`
5. Note in report: "WebFetch used — single-page collection. No depth crawling or image download."

**gstack collector (if auto-detected or complex interaction needed):**
1. Use gstack skill for headless browser navigation
2. Route output to `raw/webpacks/<topic>/`

### 3. Parse results — JSON REPORT at end of script output
### 4. Display results summary
### 5. Suggest next steps — open README.md or run `/inbox`

## Security Rules

**Always follow**:
- Skip login-required pages
- Skip personal account pages
- Don't execute webpage scripts
- Don't auto-upload any files
- Don't delete any files
- Don't modify wiki

**Conditional support** (planned for v0.2):
- Media/video download (opt-in, not yet implemented in v0.1.0)
- Advanced image pipeline (srcset, magic bytes, dedup — planned for v0.2)
