# PKB Starter — Troubleshooting

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

**Cause**: Some dependencies or scripts assume Bun runtime.

**Fix**:
- PKB uses Python, not Bun. Ignore Bun-related errors.
- Ensure Python 3.9+ and required packages are installed: `pip install -r requirements.txt`

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

### High-risk skill won't install

**Cause**: Skills with `risk_level: high` or `reference_only` are blocked by default.

**Fix**: Use `--enable-risky` to install high-risk skills:
```
python scripts/install_skills.py --target "D:\MyKB" --profile full --enable-risky
```
Reference-only skills (like z-skills) can NEVER be installed -- they are catalog entries for design reference only.

### Skill adapter not working

**Cause**: Adapter wasn't copied to target PKB, or skill output is going to wrong directory.

**Fix**:
1. Verify adapter exists: `ls templates/skill_adapters/`
2. Re-install the skill to copy its adapter
3. Check `SKILL_LINKS.md` for adapter mappings
4. Manually copy: `cp template/skill_adapters/<adapter>.md "D:\MyKB\templates\skill_adapters\"`

### /project:skills says "unknown command"

**Cause**: The `.claude/commands/skills.md` file wasn't copied to the target PKB.

**Fix**:
1. Verify `.claude/commands/skills.md` exists in your PKB directory
2. Re-install PKB template: `python scripts/install.py "D:\MyKB" --force`
3. Or create the command file manually from the pkb-starter template

---

## Still Stuck?

1. Run `python scripts/check_env.py` to verify environment
2. Check [DESIGN.md](DESIGN.md) for architecture understanding
3. File an issue on the pkb-starter GitHub repository
