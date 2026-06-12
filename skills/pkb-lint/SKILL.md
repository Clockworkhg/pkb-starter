# pkb-lint — Knowledge Base Health Check

## When to Use
- User runs `/lint`
- Automatic after each `/inbox --auto` or `/pkb` autopilot cycle
- Periodic maintenance: "check my knowledge base health"
- Before archiving or migrating knowledge base

## Instructions

### Run Health Check
Execute `python tools/pkb_auto.py --check` if available, otherwise scan manually.

### 1. 🔗 Broken Wikilinks
- Scan all `[[wikilink]]` references in `wiki/`
- Verify each target page exists
- Report: file location → broken target

### 2. 👻 Orphan Pages
- Find pages with no inbound links from other pages
- Exclude index pages and home pages
- Suggest: add links or consider archiving

### 3. 📅 Stale Content
- Check `updated` date vs. today
- Flag pages >90 days old with `#active` tag
- Flag pages >365 days without update

### 4. 📋 Frontmatter Completeness
- Every wiki page must have: `created`, `updated`, `tags`, `type`
- Check `created` ≤ `updated` (no time travel)
- Check `type` is valid: source-note | concept | project | output

### 5. 🔒 Sensitive Info Scan
- Scan wiki/ and raw/ text files
- Patterns: API keys, tokens, passwords, private keys, emails, phone numbers

### 6. 📁 Empty Directories
- Check `raw/` and `wiki/` for empty subdirectories
- Report but don't delete (structure may be intentional)

### 7. 📦 Large Files
- Check `raw/` for files >50MB
- Alert user about storage/backup considerations

### 8. 📊 Index Consistency
- Verify all wiki pages appear in `wiki/index.md`
- Verify `raw/imported_processed/manifest.json` entries are valid
- Check for source_path references pointing to missing files

## Output Format
```
🩺 PKB Health Check Report
═══════════════════════

✅ Passed (X items)
  - All frontmatter complete
  - No broken links
  - ...

⚠️ Warnings (X items)
  - 3 pages >90 days without update
  - 2 empty directories in raw/
  → Run /lint --fix to auto-fix warnings

🔴 Needs Attention (X items)
  - Broken link: wiki/concepts/example.md → [[missing-page]]
  - Missing frontmatter: wiki/sources/new-page.md
  → Manual fix required

📊 Stats
  - Wiki pages: N
  - Raw files: M
  - Total size: X MB
  - Cross-references: K wikilinks
```

## Actions After Check

### Pass → OK, continue
### Warnings → offer `/lint --fix` to auto-resolve
### Failures → list required manual fixes, do NOT commit until resolved

## Safety Notes
- Health check is read-only — never modifies files without `--fix` flag
- Sensitive info scan may have false positives — always confirm
- Large file alert is informational, not a failure
