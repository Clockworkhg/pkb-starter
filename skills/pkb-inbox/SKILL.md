# pkb-inbox — Inbox Processing (Raw → Wiki)

## When to Use
- User runs `/inbox` or `/inbox --auto`
- After `/web` collects raw materials
- Batch processing pending files in `_INBOX/`

## Instructions

### Auto Mode (`/inbox --auto`)

#### 1. Scan Pending Items
- Files in `_INBOX/imported/`
- Folders in `_INBOX/imported-folders/`
- Uncompiled webpacks in `raw/webpacks/` (check for missing wiki source-notes)

#### 2. Auto Ingest Each Item
For each pending item:
- **Extract content**: PDF/DOCX/PPTX/MD → plain text
- **Classify**: academic paper / coursework / project / guidelines / unknown
- **Create wiki pages**: source-note in `wiki/sources/`, concept/project/output pages as needed
- **Run sensitive info scan** before archiving
- **Tag uncertain classifications** with `review_needed: true`

#### 3. Auto Archive
- Move processed files: `_INBOX/imported/` → `raw/imported_processed/`
- Generate/update `raw/imported_processed/manifest.json`
- Fix all `source_path` frontmatter in wiki pages

#### 4. Auto Health Check
Run `python tools/pkb_auto.py --check`:
- Frontmatter completeness
- Zero broken wikilinks
- Zero unindexed pages
- No stale `_INBOX` references
- All `source_path` values correct

#### 5. Auto Save
```bash
git add -A
git commit -m "[PKB] inbox: auto-ingest N items — <summary>"
```

#### 6. Output Report
```
📊 Inbox Processing Complete
   ✅ Ingested: N items
   📄 New pages: M wiki pages
   🗄️ Archived: K files → raw/imported_processed/
   🔗 Commit: <hash>
   🩺 Health: ✅ passed
```

### Interactive Mode (`/inbox` without args)

#### 1. List pending items with recommendations
#### 2. Let user select items to process
#### 3. Ask before each major action

### Content Classification Logic

| Type | Detection Signals |
|------|------------------|
| Academic paper | PDF/DOCX + contains abstract/DOI/references; university/journal name in content |
| Coursework | DOCX/PPTX + course/exam/assignment keywords |
| Guidelines | DOC + rules/standards/regulations content |
| Project | PPTX + project/proposal/plan keywords |
| GitHub | webpack with github source type |
| Unknown | Doesn't match any pattern → `review_needed: true` |

## Safety Notes
- Scan for sensitive info BEFORE writing to raw/imported_processed/
- Never delete original imported files
- If health check fails, report issues — don't commit
- Auto-merge compatible wiki pages; flag conflicts for user
