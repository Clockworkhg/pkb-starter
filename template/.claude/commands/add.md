# /add — Import Files to Inbox

You are the PKB file import agent.

## Task
Import files or folders into `_INBOX/` for later processing.

## Execution

### Single file
```bash
python tools/import_to_inbox.py "<path>"
```

### Folder
```bash
python tools/import_to_inbox.py "<path>" --folder
```

## Behavior
- **Copy** by default, never move originals
- Generate `manifest.json` with metadata
- Auto-rename on collision (append _1, _2)
- Skip: `.git`, `node_modules`, `.venv`, `__pycache__`, `dist`, `build`
- **Sensitive info detection**: block and warn on API keys, tokens, passwords

## Report
- Files imported count
- Files skipped (and why)
- Sensitive info warnings
