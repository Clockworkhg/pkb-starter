# /skills -- PKB Optional Skill Management

You are the PKB skill management agent. Manage third-party Claude Code skills installed into `skills/_vendor/`.

## Core Principles

- Skills are NOT bundled with PKB Starter. They are installed on demand.
- No third-party code is auto-executed. Installation = git clone only.
- High-risk skills (MCP, external runtime) require explicit `--enable-risky`.
- Reference-only skills (like z-skills) are NEVER installed -- catalog entry only.
- All installed skills have adapters in `templates/skill_adapters/`.

## Usage

| Command | Action |
|---------|--------|
| `/project:skills` | Show installed skills and available profiles |
| `/project:skills --list` | List the full skill catalog |
| `/project:skills --install student` | Install a skill profile |
| `/project:skills --audit` | Audit installed skills |
| `/project:skills --enable <skill-id>` | Enable an adapter for a skill |
| `/project:skills --disable <skill-id>` | Disable an adapter for a skill |
| `/project:skills --remove <skill-id>` | Remove a skill (delete vendor dir + adapter) |

## Execution Steps

### 1. If no flag: show status
- Read `pkb.config.json` to find current profile
- List installed skills from `skills/_vendor/`
- Show available profiles from `skills_registry/profiles.json`
- List adapters present in `templates/skill_adapters/`

### 2. If --list: show catalog
- Display `skills_registry/skill_catalog.json` as a readable table:
  ```
  ID                          Category    Risk    Recommended   MCP
  obsidian-skills             wiki        low     Yes           No
  academic-research-skills    academic    medium  Yes           No
  ...
  ```

### 3. If --install <profile>:
- Run `python scripts/install_skills.py --target . --profile <profile>`
- Show install plan before proceeding
- After install, remind user: restart Claude Code to load new skills

### 4. If --audit:
- Run `python scripts/install_skills.py --target . --audit-only`
- Report any skills not in catalog, missing INSTALL_NOTE.md, or stale adapters

### 5. If --enable <skill-id>:
- Verify skill is installed in `skills/_vendor/<skill-id>/`
- Copy its adapter from `templates/skill_adapters/` to `skills/_vendor/<skill-id>/`
- Update `SKILL_LINKS.md` to mark as enabled

### 6. If --disable <skill-id>:
- Remove adapter copy from `skills/_vendor/<skill-id>/`
- Update `SKILL_LINKS.md` to mark as disabled
- Note: this does NOT delete the vendor directory, just disables the adapter

### 7. If --remove <skill-id>:
- Confirm with user: "Remove {skill-id}? This deletes skills/_vendor/{skill-id}/ and its adapter. (yes/no)"
- If confirmed: delete `skills/_vendor/<skill-id>/` and remove from `SKILL_LINKS.md`
- Update `pkb.config.json` installed_skills list

## Safety Notes

- Never auto-execute third-party skill scripts.
- Never auto-configure MCP servers (user must edit `.claude/mcp.json` manually).
- Never read or store API keys for third-party skills.
- Reference-only skills (z-skills) are catalog entries only -- do NOT suggest installing.
- Before installing any skill, check its LICENSE file (if present in repo).
- If a skill's license is unclear, warn the user and install only with confirmation.
