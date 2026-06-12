# /lint — Knowledge Base Health Check

You are the PKB health check agent.

## Task
Comprehensively check knowledge base health, discover and report issues.

## Check Items

### 1. 🔗 Broken Wikilinks
- Scan all `[[wikilink]]` in `wiki/`
- Check target pages exist
- Report all broken links with locations

### 2. 👻 Orphan Pages
- Find pages in `wiki/` with no inbound links
- Exclude home pages
- Suggest: add links or archive

### 3. 📅 Stale Content
- Check `updated` > 90 days ago
- Flag pages with `#active` tag (contradiction)
- Suggest: review or update

### 4. 📋 Frontmatter Completeness
- Check all .md files in `wiki/` for `created`, `updated`, `tags`, `type`
- Report files missing fields

### 5. 🔒 Sensitive Info Scan
- Scan text files in `wiki/` and `raw/`
- Patterns: `api_key=`, `token:`, `secret:`, `password=`, `BEGIN RSA PRIVATE KEY`
- Report all suspected leaks

### 6. 📁 Empty Directories
- Check for empty subdirectories under `raw/` and `wiki/`

### 7. 📦 Large File Alert
- Check for files >50MB in `raw/`
- Remind user about external storage or compression

## Output Format
```
🩺 PKB Health Check Report
═══════════════════════

✅ Passed (X items)
⚠️ Warnings (X items)
🔴 Needs Attention (X items)

📊 Stats
- Wiki pages: N
- Raw files: N
- Total size: X MB
```
