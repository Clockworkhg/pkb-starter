# PKB Starter — Troubleshooting

Languages: [English](TROUBLESHOOTING.md) | [简体中文](zh-CN/TROUBLESHOOTING.md)

## Common Issues and Solutions

### `/pkb` says "unknown command"

**Cause**: Commands in `.claude/commands/` are **project commands**, not global slash commands. They must be invoked with the `/project:` prefix.

**Fix**: Use the project command format:
```
/project:pkb <anything>
/project:inbox
/project:web <url>
/project:ask <question>
/project:lint
```

**How it works**: When you `cd` into your PKB directory and run `claude`, Claude Code detects `.claude/commands/` in the project root. These commands are then available as `/project:<name>`. They are NOT available as bare `/pkb` unless installed as a Claude Code plugin.

### `.doc` files fail to parse

**Cause**: Old-format `.doc` files (not `.docx`) require different parsing.

**Fix**:
1. Convert to `.docx` first (open in Word/LibreOffice, Save As `.docx`)
2. Or use a converter: `libreoffice --headless --convert-to docx file.doc`
3. Re-import: `/pkb file.docx`

### "python: command not found" / "python not recognized"

**Cause**: Python not in PATH, or Windows uses `python` vs `python3`.

**Fix**:
- Windows: Use `python` (not `python3`). If not found, add Python to PATH.
- macOS/Linux: Try `python3` or install: `brew install python` / `apt install python3`
- Verify: `python --version` should show 3.9+

### GitHub collection returns wrong content

**Cause**: GitHub rate limiting, private repos, or Jina fallback grabbing navigation.

**Fix**:
1. For public repos, PKB uses GitHub API → git clone → Jina (in order)
2. For private repos, ensure git is authenticated (`git config --global credential.helper`)
3. If Jina captures navigation instead of content: add `--no-jina` flag
4. Increase delay between requests: `--delay 0.5`

### WeChat (微信) article can't be collected

**Cause**: WeChat articles require specific cookie/session handling.

**Fix**:
1. PKB web_pack attempts with special WeChat handling (max-depth 0)
2. If auto-collection fails, manual workaround:
   - Open the article in WeChat desktop
   - Copy the content manually
   - Save to clipboard
   - Run `/clip`
3. The agent will auto-detect the failure and suggest manual clipping

### "Bun not found" errors

**Cause**: This message comes from external Claude Code hooks or user-global hook configurations on your machine. PKB Starter does NOT use or require Bun.

**Fix**:
- PKB Starter is a Python project — all scripts and hooks are Python 3.9+.
- The "Bun not found" message is non-blocking and does not affect PKB operations.
- If you see this message, check your global Claude Code hook settings (`~/.claude/settings.json` or `%USERPROFILE%\.claude\settings.json`) for hooks that may reference Bun.
- If you have custom hooks enabled, ensure the required runtimes are installed, or disable the hooks that use Bun.
- Verify Python dependencies: `pip install -r requirements.txt`

### Health check reports many broken links

**Cause**: Renamed or deleted wiki pages leave dangling `[[wikilink]]` references.

**Fix**:
1. Run `/lint` to see all broken links
2. Fix manually: find the broken `[[link]]` and update to the correct page name
3. Or re-run `/pkb` on the source material to regenerate links

### `git commit` fails pre-flight secret scan

**Cause**: Sensitive patterns detected in staged files.

**Fix**:
1. Read the scan report to see which files/patterns were flagged
2. Run `/sanitize <file>` to redact
3. Review and manually clean if needed
4. Re-run `/save`

### Large web collection uses too much disk space

**Cause**: Images and videos can add up quickly with `--mode full`.

**Fix**:
1. Use `--max-image-mb 5` to limit image sizes
2. Use `--max-video-mb 100` to limit video sizes
3. Use `--mode safe` for quick text-only collection
4. Review `raw/webpacks/` periodically and remove webpacks you don't need

### "Permission denied" on Windows

**Cause**: File locked by another program, or path too long.

**Fix**:
1. Close Obsidian if it has the wiki/ vault open
2. Close other programs that might lock files in the PKB directory
3. For long path issues, use a shorter root path (e.g., `D:\PKB\` instead of `D:\My Very Long Path Name\PKB\`)

### Obsidian doesn't show wiki pages

**Cause**: Obsidian vault pointing to wrong directory.

**Fix**:
- Open Obsidian → "Open folder as vault" → select the `wiki/` directory
- OR open the PKB root directory as vault (wiki links still work via path)

### Skill installation fails with "git clone" error

**Cause**: Network issue, repo URL change, or repo is private/deleted.

**Fix**:
1. Check the repo URL in `skills_registry/skill_catalog.json`
2. Verify you can access the repo in a browser
3. For private repos, ensure git is authenticated
4. Try installing skills individually: `python scripts/install_skills.py --target . --profile custom`
5. View the full catalog first: `python scripts/install_skills.py --list`

### High-risk skill won't install

**Cause**: Skills with `risk_level: high` or `reference_only` are blocked by default (5 high-risk in catalog).

**Fix**: Use `--enable-risky` to install most high-risk skills:
```
python scripts/install_skills.py --target "D:\MyKB" --profile full --enable-risky
```
Z-skills requires a different flow: use `/project:skills --install z-skills` (explicit consent).

### Z-Skills not installing

**Cause**: z-skills uses `install_method: user_approved_clone` and requires explicit consent.

**Fix**:
1. Run: `python scripts/skill_manager.py --target "D:\MyKB" --install z-skills`
2. Read the risk explanation displayed
3. Type 'INSTALL' (not 'y' or 'yes') to confirm
4. z-skills will clone to `skills/_vendor/z-skills/` in pending_audit state

### z-web-pack-local won't enable

**Cause**: z-web-pack-local requires z-skills to be installed AND audited first.

**Fix**:
1. Install z-skills: `/project:skills --install z-skills`
2. Audit: `/project:skills --audit` (automatically audits z-skills if installed)
3. Then enable: `/project:skills --enable z-web-pack-local`

### Z-skills audit report is missing

**Cause**: Audit hasn't been run, or zskill_bridge.py is not in the target PKB.

**Fix**:
1. Run: `python scripts/skill_manager.py --target "D:\MyKB" --audit`
2. Or directly: `python tools/zskill_bridge.py audit`
3. If bridge script not found: copy `template/tools/zskill_bridge.py` from pkb-starter to your PKB's `tools/` directory.

### Z-web-pack collector says "adapter is not enabled"

**Cause**: `--collector z-web-pack` was used but z-web-pack-local is not enabled.

**Fix**:
```
/project:skills --install z-skills      # install (explicit consent)
/project:skills --audit                 # audit license + structure
/project:skills --enable z-web-pack-local  # enable adapter
```
Then retry: `/project:web --collector z-web-pack <url>`

### Plugin marketplace skill not installing

**Cause**: Skills with `install_method: plugin_marketplace` (obsidian-skills, academic-research-skills) cannot be git-cloned.

**Fix**: Install manually via Claude Code:
```
/plugin marketplace add kepano/obsidian-skills
/plugin install obsidian@obsidian-skills
```
These skills appear in catalog for reference. install_skills.py skips them with a manual-install note.

### Skill adapter not working

**Cause**: Adapter wasn't copied to target PKB, or skill output is going to wrong directory.

**Fix**:
1. Verify adapter exists: `ls template/skill_adapters/`
2. Re-install the skill to copy its adapter
3. Check `SKILL_LINKS.md` for adapter mappings
4. Manually copy the adapter to your PKB's `templates/skill_adapters/`

### /project:skills says "unknown command"

**Cause**: The `.claude/commands/skills.md` file wasn't copied to the target PKB.

**Fix**:
1. Verify `.claude/commands/skills.md` exists in your PKB directory
2. Re-install PKB template: `python scripts/install.py "D:\MyKB" --force`
3. Or create the command file manually from the pkb-starter template

### Skill has NO LICENSE in catalog

**Cause**: Some repos (e.g., agent-research-skills, z-skills) lack a LICENSE file.

**Fix**:
1. Check the cloned repo's root for any license file: `ls skills/_vendor/<skill-id>/LICENSE*`
2. Check the repo's GitHub page for license info
3. If no license found, treat as "all rights reserved" — use for personal reference only
4. Run `python scripts/skill_manager.py --target . --audit` to see license status of all installed skills

### Can't find a skill after installing

**Cause**: Skills go through three stages: install → audit → enable. A newly installed skill is not yet enabled.

**Fix**:
1. Run `/project:skills` to see all installed skills and their status
2. Skills marked [INSTALLED] or [PENDING AUDIT] are downloaded but not active
3. Run `/project:skills --audit` to verify installation
4. Run `/project:skills --enable <id>` to activate
5. Restart Claude Code to load the newly enabled skill

### Want to add skills after initial setup

**Cause**: You installed with `--skip-skills` and now want to add skills.

**Fix**:
```bash
# Browse available skills
python scripts/skill_manager.py --target "D:\MyKB" --list

# Or from Claude Code
/project:skills --list
/project:skills --describe deep-research-skills
/project:skills --install-profile student
```
Skills can be added anytime — no need to reinstall PKB.

### skill_manager.py says "Target directory does not exist"

**Cause**: The --target path must point to your PKB installation, not the pkb-starter source.

**Fix**:
```bash
# Point to your PKB directory, not pkb-starter
python scripts/skill_manager.py --target "D:\MyKB" --list
# NOT: python scripts/skill_manager.py --target "D:\pkb-starter" --list
```

### Dry-run shows skills but nothing was installed

**Cause**: `--dry-run` is a preview mode. It shows what WOULD happen without making changes.

**Fix**: Remove `--dry-run` to actually install:
```bash
python scripts/skill_manager.py --target "D:\MyKB" --install-profile student
```

### Update fails with "No pkb.config.json found"

**Cause**: The target directory is not a PKB installation, or the config file was deleted.

**Fix**:
1. Verify you are pointing to your PKB install, not pkb-starter source
2. Run `ls pkb.config.json` in your PKB directory
3. If missing, reinstall: `python scripts/install.py "D:\MyKB" --force`

### Update says "Already up-to-date" but I expected changes

**Cause**: Your installed `starter_version` matches or exceeds the current version.

**Fix**:
1. Check your version: `cat pkb.config.json | grep starter_version`
2. Check pkb-starter version in `scripts/update_pkb.py` (CURRENT_VERSION)
3. If pkb-starter is ahead, pull: `cd D:\pkb-starter && git pull`
4. Then re-run the update

### Update overwrote my AGENTS.md

**Cause**: `AGENTS.md` was explicitly in the system update path and `--force` was used.

**Fix**:
1. Restore from backup: `cp .pkb_backup/<LATEST>/AGENTS.md .`
2. By default, user-modified AGENTS.md is skipped. Only use `--force` if intentional.
3. Consider adding your custom rules to a separate file and referencing it from AGENTS.md.

### Migration script failed

**Cause**: A migration script encountered unexpected state in the target PKB.

**Fix**:
1. Check the error output — migration scripts report what precondition failed.
2. Restore from backup: `cp -r .pkb_backup/<LATEST>/* .`
3. Report the issue with your pkb-starter version and target PKB state.

### Backup directory is growing large

**Cause**: Multiple updates create multiple timestamped backup directories.

**Fix**:
1. Review backups: `ls .pkb_backup/`
2. Keep the most recent 2-3 backups
3. Delete older ones: `rm -rf .pkb_backup/20250101_120000`
4. `.pkb_backup/` is in `.gitignore` and never committed

### /project:update says "unknown command"

**Cause**: The update command was added in pkb-starter v0.5.0. Older installs don't have it.

**Fix**:
1. Update manually first: `python scripts/update_pkb.py "D:\MyKB"`
2. After migration, `/project:update` will be available
3. Future updates can use the command directly

### pkb_update_client.py not found

**Cause**: Your KB was installed before v0.6.2-alpha. The update client is added in that version.

**Fix**:
1. Update manually once: `python scripts/update_pkb.py "D:\MyKB"` (from pkb-starter directory)
2. After the update, `tools/pkb_update_client.py` will be available
3. Future updates: `python tools/pkb_update_client.py`

### Update client says "No valid starter_repo_url"

**Cause**: `starter_repo_url` in `pkb.config.json` is not set or is a placeholder.

**Fix**:
1. Edit `pkb.config.json` and set `starter_repo_url` to your pkb-starter fork
2. Or use `--starter-path "D:\pkb-starter"` to point to a local clone
3. Or use `--repo-url https://github.com/<your-fork>/pkb-starter.git`

### Install fails "Target directory not empty"

**Cause**: The target install path already contains files.

**Fix**:
1. Use an empty directory: `python scripts/install.py "D:\MyKB"`
2. Or use `--force` to overwrite: `python scripts/install.py "D:\MyKB" --force`
3. Or use interactive mode to confirm: `python scripts/install.py --interactive`

### No target path provided to install.py

**Cause**: `install.py` requires a target path as the first positional argument.

**Fix**:
```bash
# Provide a target path
python scripts/install.py "D:\MyKB"

# Or use interactive mode
python scripts/install.py --interactive
```

The path can be any directory — `E:\KnowledgeBase`, `C:\Users\...\Documents\PKB`, etc. There is no default.

---

## Still Stuck?

1. Run `python scripts/check_env.py` to verify environment
2. Check [DESIGN.md](DESIGN.md) for architecture understanding
3. File an issue on the pkb-starter GitHub repository
