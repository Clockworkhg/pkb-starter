# Recover from v0.6.2-alpha Fresh Install Docs Issue

> If you installed v0.6.2-alpha and are seeing stale documentation warnings, this guide is for you.

Languages: [English](RECOVER_FROM_0.6.2_ALPHA.md) | [简体中文](zh-CN/RECOVER_FROM_0.6.2_ALPHA.md)

---

## 1. What Happened

v0.6.2-alpha released with several documentation issues that affect fresh installs:

- **Stale docs on fresh install**: New KBs immediately report stale documentation (up to 22 items) because template files contain placeholder dates (`YYYY-MM-DD`) and outdated version references (`v0.5.0-alpha`).
- **Malformed version strings**: The `/docs-update` command could incorrectly rewrite version strings (e.g., `v0.5.0-alpha` → `v06-12`), confusing date fragments with version numbers.
- **Protected file overwrite attempts**: `/docs-update` could attempt to modify `CLAUDE.md` and `AGENTS.md`, which are protected by the ARS scope guard.

**This does NOT affect your user data.** Your `raw/`, `wiki/`, `_INBOX/`, `skills/_vendor/`, and `.pkb_local/` directories are safe.

## 2. Who Is Affected

- Users who installed **v0.6.2-alpha**.
- Especially users who ran `/docs-update` immediately after installing.

Users on older versions (v0.5.0-alpha and earlier) who updated to v0.6.2-alpha are also affected.

## 3. What NOT to Do

- ❌ **Do NOT delete your KB**. Your data is safe.
- ❌ **Do NOT manually edit random system files** unless you know exactly what changed.
- ❌ **Do NOT force-reset** if you already added personal notes.
- ❌ **Do NOT reinstall over your existing KB** — this could overwrite your data.
- ❌ **Do NOT run `/docs-update` on v0.6.2-alpha** — wait until you've updated to v0.6.4-alpha.

## 4. If Your Update Source Is Still a Placeholder

v0.6.2-alpha installs wrote a placeholder `starter_repo_url` into `pkb.config.json`:

```json
"starter_repo_url": "https://github.com/<your-username>/pkb-starter.git"
```

This causes the update client to fail with "No valid starter_repo_url configured."

**Fix it in one step:**

```bash
cd "<your-kb-path>"

# This uses the official repo, applies the update, AND saves the URL for future use:
python tools/pkb_update_client.py --repo-url "https://github.com/Clockworkhg/pkb-starter.git" --checkout v0.6.4-alpha
python tools/pkb_update_client.py --repo-url "https://github.com/Clockworkhg/pkb-starter.git" --checkout v0.6.4-alpha --apply
```

After `--apply`, `starter_repo_url` is updated in `pkb.config.json` and you can use `/update` directly going forward.

If you use a personal fork, replace the URL with your fork URL.

## 5. Safe Update to v0.6.4-alpha

v0.6.4-alpha fixes all these issues. Use the built-in update client:

```bash
cd "<your-kb-path>"

# Step 1: Preview what will change (safe, no files modified)
python tools/pkb_update_client.py --checkout v0.6.4-alpha

# Step 2: Review the report
# Open update_client_report.md and check:
#   - No raw/ files in planned changes
#   - No wiki/ files in planned changes
#   - No _INBOX/ files in planned changes

# Step 3: Apply the update
python tools/pkb_update_client.py --checkout v0.6.4-alpha --apply
```

**After update, verify:**

```bash
python tools/docs_update.py --check
```

Expected output:
- `stale count = 0`
- No `v0.5.0-alpha` as current version
- No `YYYY-MM-DD` placeholder
- No malformed `v06-12` version
- `[OK]` for all tracked docs

## 6. If Docs Were Already Modified by /docs-update on v0.6.2-alpha

If you ran `/docs-update` while on v0.6.2-alpha, your docs may have incorrect version strings or date values.

**Recovery steps:**

1. **Run dry-run first:**
   ```bash
   python tools/pkb_update_client.py --checkout v0.6.4-alpha
   ```

2. **Check the update report:**
   - If `update_client_report.md` lists core doc conflicts, accept the v0.6.4-alpha template versions (unless you intentionally customized them).
   - If you see your personal wiki notes or raw files in planned changes, **STOP** and ask for help.

3. **Apply the update:**
   ```bash
   python tools/pkb_update_client.py --checkout v0.6.4-alpha --apply
   ```

4. **Verify:**
   ```bash
   python tools/docs_update.py --check
   ```

## 7. If the Update Client Is Missing or Broken

If `tools/pkb_update_client.py` is missing (installed before v0.6.2-alpha) or broken:

**Option A: Use a local pkb-starter clone**

```bash
cd "<your-kb-path>"
python tools/pkb_update_client.py --starter-path "D:\pkb-starter" --checkout v0.6.4-alpha
python tools/pkb_update_client.py --starter-path "D:\pkb-starter" --checkout v0.6.4-alpha --apply
```

**Option B: Fresh install for comparison, then manual update**

```bash
# Install fresh v0.6.4-alpha to a temp directory for comparison
git clone https://github.com/pkb-starter/pkb-starter.git D:\pkb-starter-temp
cd D:\pkb-starter-temp
git checkout v0.6.4-alpha
python scripts/install.py E:\pkb-fresh-063 --force

# Compare system files between fresh install and your KB
# Manually copy only system template files that need updating
```

## 8. Verify After Update

Run all checks:

```bash
cd "<your-kb-path>"

# Documentation freshness
python tools/docs_update.py --check
# Expected: stale count = 0

# Check version in config
python -c "import json; c=json.load(open('pkb.config.json')); print(c.get('starter_version'))"
# Expected: v0.6.4-alpha

# Check no malformed versions in docs
python -c "import re, pathlib; [print(f'{f.name}: v06-12') for f in pathlib.Path('.').glob('*.md') if 'v06-12' in f.read_text()]"
# Expected: no output
```

## 9. When to Ask for Help

Contact the pkb-starter maintainers if:

- Update report lists **conflicts in core files** you didn't customize
- **User data** (raw/, wiki/) appears in planned changes
- `git status` shows **unexpected deletions**
- You cannot resolve conflicts after the update

---

*This guide applies to v0.6.2-alpha/v0.6.3-alpha → v0.6.4-alpha migration. For general update information, see [UPDATING.md](UPDATING.md).*
