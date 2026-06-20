# PKB Starter vX.Y.Z-alpha — One-Line Theme

> **Release title format**: `PKB Starter vX.Y.Z-alpha — Short Theme (≤60 chars)`
> All release notes are written in English for international audience.

## 🆕 What's New

- **Feature A** — one-line description of what it does.
- **Feature B** — one-line description of what it does.

### Usage

```bash
# Feature A
python tools/feature_a.py --flag value

# Feature B
/feature-b command args
```

## ⬆️ Upgrading

```bash
# Recommended: use the update client in your KB
python tools/pkb_update_client.py --apply

# Or from a local pkb-starter clone
python scripts/update_pkb.py "<KB_ROOT>" --dry-run
python scripts/update_pkb.py "<KB_ROOT>"
```

**No breaking changes** — fully backward compatible. User data (`wiki/`, `raw/`, `_INBOX/`, `.pkb_local/`) is never touched.

## 🔒 Privacy & Security

- All user data preserved during update.
- `.pkb-local/` directory is gitignored — never committed.
- No API keys, tokens, or credentials are stored in the repository.
- Sensitive content detection blocks commits that leak secrets.

## 🧪 Test Results

```
N passed, 0 failed, 0 skipped
```

## 📋 Known Limitations

| Limitation | Note |
|------------|------|
| Example limitation | Brief description and workaround if available. |

---

**Full Changelog**: [CHANGELOG.md](https://github.com/Clockworkhg/pkb-starter/blob/master/CHANGELOG.md)
