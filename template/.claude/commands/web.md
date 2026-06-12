# /web — Raw Layer Web Collection

You are the PKB raw layer web collection agent.

## Core Principles

- `/web` is a **raw layer collection command**, only generates `raw/webpacks/` materials
- `/web` does **not directly modify wiki**
- Collector: **PKB web_pack** — basic web collector (v0.1.0)
- Collects public web pages, extracts content, generates standard webpack output
- After completion, suggest user run `/inbox` to compile webpack into wiki

## Task

Collect one or more web pages' content, generate standardized raw layer webpack.

## Execution Steps

### 1. Determine topic and URLs
- If user specified topic, use directly
- If not, visit first URL to get title, auto-generate topic name
- Supports multiple URLs (space-separated)

### 2. Run collector
```bash
# Basic web page collection
python tools/web_pack.py --topic "<topic>" --url "<url>" --max-depth 1 --max-pages 80

# Multiple URLs
python tools/web_pack.py --topic "<topic>" --url "<url1>" --url "<url2>"

# GitHub repository URL (converts to raw automatically)
python tools/web_pack.py --topic "<topic>" --url "https://github.com/user/repo/tree/main/path"
```

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
