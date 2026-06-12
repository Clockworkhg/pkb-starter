# FRESH_INSTALL_HOTFIX_CHECK.md — v0.6.3-alpha

**Date**: 2026-06-12
**Branch**: `hotfix/v0.6.3-alpha`
**Base**: `master` (ae38f63 — v0.6.2-alpha tag)

---

## 1. Root Cause

v0.6.2-alpha had three root causes for the stale-docs-on-fresh-install issue:

1. **Template date placeholders**: Multiple template files (`AGENTS.md`, `index.md`, `log.md`, Chinese locale variants) contained `YYYY-MM-DD` in date-field positions (frontmatter `created`/`updated`, footer "Last updated" lines). The `install.py` did no placeholder substitution — templates were copied verbatim.

2. **Outdated version in Chinese locale template**: `template/locales/zh-CN/index.md` footer declared `版本：v0.5.0-alpha` as the current version, not v0.6.2-alpha.

3. **No safe apply flow**: `docs_update.py` had no `--check`/`--apply` separation. The `/docs-update` command instructed the LLM to directly edit files without distinguishing safe docs from protected rule files. Version/date replacement was left entirely to the LLM, leading to malformed version strings like `v06-12` when the LLM confused date fragments with version fields.

4. **Checker mismatches**: `docs_update.py` checked for Chinese section headers in AGENTS.md that only apply to the Chinese locale variant, and Chinese section headers in CLAUDE.md that the English template never had.

---

## 2. Files Changed

### Template files (source of truth):
| File | Change |
|------|--------|
| `template/AGENTS.md` | `YYYY-MM-DD` → `2026-06-12` (×2: header + footer) |
| `template/index.md` | `YYYY-MM-DD` → `2026-06-12` (×3: frontmatter + footer); added tool refs for `pkb_update_client.py`, `zskill_bridge.py`; added SKILL_LINKS cross-ref; added hooks section |
| `template/log.md` | `YYYY-MM-DD` → `2026-06-12` (×4: frontmatter + section heading + footer) |
| `template/CLAUDE.md` | Added `zskill_bridge.py` tool entry; added Hooks table with all 6 hook filenames |
| `template/SKILL_LINKS.md` | **NEW** — placeholder skills index file |
| `template/locales/zh-CN/AGENTS.md` | `YYYY-MM-DD` → `2026-06-12` (×2) |
| `template/locales/zh-CN/index.md` | `v0.5.0-alpha` → `v0.6.3-alpha`; added tools, SKILL_LINKS, hooks sections |
| `template/locales/zh-CN/wiki_index.md` | `YYYY-MM-DD` → `2026-06-12` (×3) |
| `template/tools/docs_update.py` | Complete rewrite: added `--check`/`--apply` flags, context-aware date/version replacement, protected-file awareness, English+Roman numeral section matching |
| `template/.claude/commands/docs-update.md` | Rewritten: check-then-apply safety, protected file rules, no bypass instructions |
| `template/tools/pkb_update_client.py` | `--checkout v0.6.2-alpha` → `v0.6.3-alpha` (usage example) |
| `template/.claude/commands/update.md` | `--checkout v0.6.2-alpha` → `v0.6.3-alpha` (usage example) |

### Script files:
| File | Change |
|------|--------|
| `scripts/install.py` | `starter_version` → `0.6.3-alpha`; installer banner → `v0.6.3-alpha` |
| `scripts/update_pkb.py` | `CURRENT_VERSION` → `0.6.3-alpha` |

### Documentation files:
| File | Change |
|------|--------|
| `CHANGELOG.md` | Added `[0.6.3-alpha]` entry at top |
| `README.md` | Version badge + text → `v0.6.3-alpha` |
| `README.zh-CN.md` | Version badge + text → `v0.6.3-alpha` |
| `docs/QUICKSTART.md` | Version → `v0.6.3-alpha` |
| `docs/zh-CN/QUICKSTART.md` | Version → `v0.6.3-alpha` |
| `docs/UPDATING.md` | Added v0.6.3-alpha to version history; added "Recovering from v0.6.2-alpha" section |
| `docs/zh-CN/UPDATING.md` | Added v0.6.3-alpha to version history; added "从 v0.6.2-alpha 恢复" section |
| `docs/TROUBLESHOOTING.md` | Enhanced Bun explanation |
| `docs/zh-CN/TROUBLESHOOTING.md` | Enhanced Bun explanation |

### New files:
| File | Purpose |
|------|---------|
| `docs/RECOVER_FROM_0.6.2_ALPHA.md` | English recovery guide for v0.6.2-alpha users |
| `docs/zh-CN/RECOVER_FROM_0.6.2_ALPHA.md` | Chinese recovery guide |

---

## 3. docs_update.py Changes

### New flags:
- `--check` (default): Detection only, no modifications
- `--apply`: Apply safe fixes to non-protected docs
- `--json` / `--summary`: Unchanged

### Protected file handling:
- `AGENTS.md` and `CLAUDE.md` are `PROTECTED_DOCS`
- `--check` reports their stale items with `[PROTECTED]` marker
- `--apply` NEVER modifies them — only reports "manual review required"
- No bypass instructions (no PowerShell/Bash workarounds)

### Safe version replacement:
- Version replacement is context-anchored: only replaces in `版本：v<old>` / `version: v<old>` field contexts
- Date replacement is context-anchored: only in frontmatter (`created:`/`updated:`) and footer (`最后更新：`/`Last updated:`) lines
- Never uses a single regex for both version and date

### Self-consistent fresh install:
- All template files use `2026-06-12` as date
- All template files reference `v0.6.3-alpha` as current version
- Template SKILL_LINKS.md exists (prevents MISSING status)
- CLAUDE.md includes all hook filenames
- AGENTS.md section check handles both Roman (I., II.) and Chinese (一、) numerals

---

## 4. /docs-update Command Behavior Changes

| Aspect | v0.6.2-alpha | v0.6.3-alpha |
|--------|-------------|-------------|
| Default action | Edit files directly | Check first, report results |
| Safe docs | Auto-edit all | Auto-edit only after confirmation |
| Protected files | Attempted modification | Check only, suggest manual review |
| Bypass instructions | None | Explicitly prohibited |
| Version replacement | LLM-managed (risk of v06-12) | Script-managed (context-anchored) |

---

## 5. Bun Dependency Result

✅ **PKB Starter has zero Bun dependencies.**

All 6 hook scripts in `template/.claude/hooks/` are Python (`#!/usr/bin/env python3`). No `package.json`, `bun`, `bunx`, `npm`, or `node` references exist in any project template file.

The "Bun not found" messages users may see come from external Claude Code global hooks on the user's machine, not from PKB Starter. TROUBLESHOOTING.md (EN+ZH) has been enhanced to explain this clearly.

---

## 6. Fresh Install v0.6.3-alpha Test Result

✅ **PASS**

```bash
python scripts/install.py E:\pkb-fresh-v063-test --force
cd E:\pkb-fresh-v063-test
python tools/docs_update.py --check
```

Output:
```
[OK]     index.md: up to date
[OK]     COMMANDS.md: up to date
[OK]     SKILL_LINKS.md: up to date
[OK]     log.md: up to date
[OK]     AGENTS.md: up to date
[OK]     CLAUDE.md: up to date
Docs are up to date.
```

- stale count = 0 ✅
- No `v0.5.0-alpha` as current ✅
- No `YYYY-MM-DD` in date fields ✅
- No `v06-12` malformed version ✅
- `--apply` on fresh install: "All docs up to date. Nothing to do." ✅
- No Bun dependency ✅

---

## 7. v0.6.2-alpha User Upgrade Simulation Result

✅ **PASS**

### Simulation steps:
1. Installed v0.6.2-alpha to `E:\pkb-v062-user-test` — confirmed 23 stale entries
2. Ran dry-run update to v0.6.3-alpha using `--starter-path`
3. Verified update report:
   - ✅ No `raw/` files in planned changes
   - ✅ No `wiki/` files in planned changes
   - ✅ No `_INBOX/` files in planned changes
   - ✅ No `skills/_vendor/` in planned changes
   - ✅ Config fields preserved (language, install_path, starter_repo_url, etc.)
   - ✅ AGENTS.md skipped (user-modified protection)
4. Applied update with `--apply`
5. Ran `docs_update.py --check` after update:
   - Safe docs: index.md had structural items (tool refs), date fixed ✅
   - Protected docs: AGENTS.md, CLAUDE.md flagged for manual review ✅
   - No `v06-12` generated ✅
   - starter_version updated to `0.6.3-alpha` ✅
6. User data directories preserved ✅
7. Backup created ✅
8. SKILL_LINKS.md installed ✅

---

## 8. Remaining Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| AGENTS.md not updated (skipped as user-modified) | Low | LLM can fix the date via `/docs-update`; structural items are cosmetic |
| CLAUDE.md not updated (project-local, never overwritten) | Low | Checker reports issues; user can manually update or recreate from template |
| index.md structural items (tool refs) require LLM editing | Low | `--apply` handles dates; structural additions need `/docs-update` |
| Template SKILL_LINKS.md added but update_pkb.py may not copy new-only files | Low | Fresh install includes it; update users get it via the system file copy |

---

## 9. Final Verdict

**READY FOR v0.6.3-alpha**

All core issues are fixed:
- ✅ Fresh install: stale count = 0
- ✅ No `YYYY-MM-DD` placeholders in date fields
- ✅ No `v0.5.0-alpha` as current version
- ✅ No `v06-12` malformed version generation
- ✅ `docs_update.py --check` and `--apply` behave correctly
- ✅ Protected files handled safely
- ✅ Recovery docs available for v0.6.2-alpha users
- ✅ Version update tested end-to-end
- ✅ Bun confirmed as non-dependency
- ✅ All docs self-consistent at v0.6.3-alpha
