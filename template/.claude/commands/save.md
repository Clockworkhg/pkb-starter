# /save — Git Save + Auto Doc Update

You are the PKB git save agent.

## Task
Auto-update project docs, then commit all changes to git.

## Execution Steps

### 1. Check status
```bash
git status --short
```

### 2. Auto-update docs
```bash
python tools/docs_update.py --summary
```

If output is not "[OK] Docs up to date.":
- Read `python tools/docs_update.py --json` for full diagnosis
- Auto-fill missing entries in docs (tools, commands, wiki pages, commits)
- Wiki pages use `[[wikilink]]`, regular paths use Markdown links
- Update date stamps to today

### 3. Show changes to user
### 4. Generate commit message — `[PKB] YYYY-MM-DD: <auto-summary>`
### 5. Execute commit
```bash
git add -A
git commit -m "<message>"
```

### 6. Report
```
💾 Saved
Commit: <hash>
Message: "<message>"
Changes: X files (+N, -M)
Docs auto-updated: Y files (or [OK] already fresh)
```

## Security Rules
- Verify `.gitignore` is effective
- Scan for .env / sensitive files before commit
- Do NOT auto push to remote
- Doc updates only touch project-level markdown files, never wiki/ content
