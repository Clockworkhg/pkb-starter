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
- **Default collector**: PKB basic web_pack (v0.1.0)
- **Optional collector**: z-web-pack (requires user-installed z-skills + audit + enable)
- Collects public web pages, extracts content, generates standard webpack output
- After completion, suggest user run `/inbox` to compile webpack into wiki

## Collector Backends

| Flag | Collector | Requirements |
|------|-----------|-------------|
| *(default)* | PKB basic web_pack | Always available (built-in) |
| `--collector z-web-pack` | z-web-pack (local, user-installed) | z-skills installed + audited + z-web-pack-local enabled |

### Basic Collector (default)
PKB's built-in `tools/web_pack.py`. Handles public web pages, generates standard webpack output. Always available.

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

## Task

Collect one or more web pages' content, generate standardized raw layer webpack.

## Execution Steps

### 1. Determine topic and URLs
- If user specified topic, use directly
- If not, visit first URL to get title, auto-generate topic name
- Supports multiple URLs (space-separated)

### 2. Run collector

**Default (basic) collector:**
```bash
# Basic web page collection
python tools/web_pack.py --topic "<topic>" --url "<url>" --max-depth 1 --max-pages 80

# Multiple URLs
python tools/web_pack.py --topic "<topic>" --url "<url1>" --url "<url2>"

# GitHub repository URL (converts to raw automatically)
python tools/web_pack.py --topic "<topic>" --url "https://github.com/user/repo/tree/main/path"
```

**Z-Web-Pack collector (if --collector z-web-pack):**
1. Verify z-web-pack-local is enabled (check pkb.config.json skills.enabled_adapters includes z_skills_adapter.md)
2. If not enabled, respond with the prerequisite instructions and stop.
3. Run: `python tools/zskill_bridge.py run --skill z-web-pack --url "<url>" --topic "<topic>"`
4. After z-web-pack completes, run: `python tools/zskill_bridge.py import-output --path "<z-web-pack-output-dir>"`
5. Output is routed to `raw/webpacks/<topic>/` — same location as basic collector
6. Continue with normal /inbox pipeline from there

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
