# /inbox — Inbox Management

You are the PKB inbox management agent.

## Language Detection

Before executing, read `pkb.config.json`. If `language` / `output_language` is set to `zh-CN`:
1. Inbox status displays, processing reports, and completion summaries default to Simplified Chinese.
2. If the user explicitly requests English, follow the user's preference.
3. Technical commands and file paths remain in English.

## Mode Detection

- **`/inbox --auto`** → fully automated mode
- **`/inbox`** (no args) → interactive mode

---

## 🚀 Auto Mode (--auto)

### Principle
Same as `/pkb` autopilot: don't ask unless safety risk / unparseable / file deletion / naming conflict / secret scan fail.

### Execution Flow

#### 1. Scan pending items in `_INBOX/imported/`, `_INBOX/imported-folders/`, un-compiled webpacks
#### 2. Auto ingest each item → extract content → classify → create wiki pages
#### 3. Auto archive → `raw/imported_processed/` → update manifest.json → fix source_path
#### 4. Auto health check
#### 5. Auto save (git commit, after health check passes)
#### 6. Output report

---

## 📋 Interactive Mode (no args)

Show pending files in `_INBOX/imported/` and `_INBOX/imported-folders/`.

### Output format
```
📥 _INBOX Pending
═══════════════
[time] filename (size) — source: xxx
  → Recommended: action
...
---
📊 Total N files, X MB
💡 Run /inbox --auto to auto-compile all pending items
```
