# /skills — PKB Optional Skill Manager

You are the PKB skill management agent, available at any time after PKB installation. Manage third-party Claude Code skills installed into `skills/_vendor/`.

## Language Detection

Before executing, read `pkb.config.json`. If `language` / `output_language` is set to `zh-CN`:
1. Status displays, catalog listings, skill descriptions, audit reports, and operation confirmations default to Simplified Chinese.
2. Skill IDs and technical identifiers remain in English.
3. Chinese catalog entries (name_zh, short_description_zh, etc.) should be used when available.
4. If the user explicitly requests English, follow the user's preference.

## Core Principles

- Skills are NOT bundled. They are installed on demand from the PKB ecosystem catalog (42 entries).
- No third-party code is auto-executed. Installation = git clone only.
- High-risk skills (MCP, external runtime) require explicit user confirmation.
- Reference-only skills are NEVER installed — catalog entry only.
- **z-skills**: Third-party collection available as user-approved local install. PKB Starter does NOT distribute its code. User must explicitly opt in, audit, and enable.
- All output from third-party skills routes through PKB adapters to `raw/` or `wiki/`.
- MCP is never auto-configured. API keys are never read, stored, or configured.
- Users can install skills at any time — during setup or months later.

## Usage

| Command | Action |
|---------|--------|
| `/project:skills` | Show status: installed, enabled, disabled, available profiles |
| `/project:skills --list` | List all 42 catalog entries with descriptions and risk levels |
| `/project:skills --describe <skill-id>` | Show full details for one skill (what, why, risk, how to install) |
| `/project:skills --install <skill-id>` | Install a single skill (with description + risk shown first) |
| `/project:skills --install-profile <profile>` | Install all skills from a profile |
| `/project:skills --audit` | Audit installed skills: license, adapter, .git, issues |
| `/project:skills --enabled` | Show enabled skills and adapters |
| `/project:skills --enable <skill-id>` | Enable an audited skill (activates its adapter) |
| `/project:skills --disable <skill-id>` | Disable a skill without deleting source |
| `/project:skills --update-catalog` | Refresh local catalog version |
| `/project:skills --describe z-skills` | Learn about z-skills local install option |
| `/project:skills --install z-skills` | Install z-skills to skills/_vendor/ (explicit consent) |
| `/project:skills --audit z-skills` | Audit z-skills license and structure |
| `/project:skills --enable z-web-pack-local` | Enable z-web-pack as collector backend |

## Execution Steps

### Step 0: Determine PKB root

Find the PKB root directory (the directory containing `pkb.config.json`). If this command is invoked from a PKB project, use the project root. Otherwise, ask the user to provide the PKB path.

### Step 1: If no flag — show status

Read `pkb.config.json` to extract the `skills` state. Then display:

```
=== PKB Skill Manager ===

Installed profiles: core (or: student, research, ...)

Skills in skills/_vendor/: N

  Skill ID                          Risk       Status            Source
  --------------------------------------------------------------------
  deep-research-skills              medium     [ENABLED]         external repo
  kanban-skill                      low        [DISABLED]        external repo
  qmd                               medium     [PENDING AUDIT]   external repo

Adapters: M available, N enabled
  academic_research_adapter.md [ENABLED]
  deep_research_adapter.md
  ...

Available profiles (use --install-profile <name>):

  core          0 skills  Pure PKB. Zero external skills. [INSTALLED]
  student       8 skills  Coursework, papers, literature review.
  research     12 skills  Full academic pipeline. Graduate-level.
  developer     7 skills  Code projects, docs, GitHub research.
  creator       7 skills  Writers, musicians, filmmakers.
  output        7 skills  Reports, papers, presentations.
  security      3 skills  Audit, sanitize, harden.
  full         24 skills  All recommended skills. Power user.
  custom       interactive Hand-pick from 42 entries.

Catalog version: 0.4.0
Run --list to see all 42 entries with descriptions.
Run --describe <id> to learn about a specific skill.
```

### Step 2: If --list

Display the full catalog with one-line descriptions. Group by category:

```
=== PKB Skill Catalog — 42 entries (v0.4.0) ===

[Knowledge Capture]
  web-pack           [LOW]   built_in
    Core web content collector that saves complete webpages...
  pkb-auto           [LOW]   built_in
    Full autopilot ingest pipeline that takes anything...
  ...

[Academic Research]
  ...

Risk legend:
  [LOW]     = auto-install safe, no external dependencies
  [MEDIUM]  = install with warnings (deps, tokens, or API)
  [HIGH]    = requires confirmation (MCP, external runtime, login)
  [REF]     = reference only, never installable

Use --describe <skill-id> to see full details for any skill.
Use --install-profile <profile> to install a preset group.
```

### Step 3: If --describe <skill-id>

Display the complete skill profile:

```
=== Skill: Deep Research Skills (deep-research-skills) ===

[What it does]
Structured multi-turn deep research: topic scoping, multi-source
information gathering, evidence synthesis, and structured report
generation.

[Details]
A prompt-only skill set (5 sub-skills) designed for thorough
multi-turn research. Starts with topic scoping and question
decomposition, searches multiple sources iteratively, synthesizes
findings with evidence tracking, and generates structured reports.

[Best for]
  - Complex research questions requiring multiple angles
  - Generating comprehensive research reports
  - Evidence-based writing with source tracking

[Not for]
  - Quick factual lookups (use /project:ask)
  - Real-time news (training data cutoff applies)

[Risk] MEDIUM
  MIT licensed. Prompt-only design — no executable code, no
  external API calls, no data upload. Main cost is token usage.

[Requirements]
  API key needed:         No
  MCP server needed:      No
  External runtime:       No

[Installation]
  Source type:     external_repo
  Install method:  git_clone_selective
  Repository:      https://github.com/Weizhena/Deep-Research-skills
  License:         MIT

[Adapter]
  Adapter file:    deep_research_adapter.md

[Recommended profiles]
  research, full

[Sub-skills] (5)
  - research, research-deep, research-report, research-add-items,
    research-add-fields

---
To install: python scripts/skill_manager.py --target . --install deep-research-skills
```

### Step 4: If --install <skill-id>

1. Show the skill's description, risk, and requirements (same as --describe but compact).
2. If HIGH RISK, warn: "This skill requires MCP configuration / external runtime / institutional login. PKB never auto-configures these. Proceed only if you understand the requirements."
3. Confirm: "Install {skill-id} to skills/_vendor/? [y/N]"
4. If confirmed, run: `python scripts/skill_manager.py --target . --install <skill-id> --yes`
5. Report result. Remind: "Skill installed to skills/_vendor/. Review its LICENSE, then run --audit and --enable <id> to activate."

### Step 5: If --install-profile <profile>

1. Show profile overview with description.
2. List all skills in the profile with risk tags.
3. Note any skills that will be skipped (high risk, plugin marketplace, MCP server).
4. Confirm: "Install {N} skills from profile '{profile}'? [y/N]"
5. If confirmed, run: `python scripts/skill_manager.py --target . --install-profile <profile> --yes`
6. Report results with counts: installed, failed, skipped.
7. Remind: "Skills installed. Run --audit to verify, then --enable <id> to activate."

### Step 6: If --audit

Run: `python scripts/skill_manager.py --target . --audit`
Display the audit results. Flag issues:
- Skills not in catalog
- Missing .git directory
- Missing INSTALL_NOTE.md
- NO LICENSE repos
- Missing adapters

### Step 7: If --enabled

Run: `python scripts/skill_manager.py --target . --enabled`
Display enabled skills with categories and enabled adapters.

### Step 8: If --enable <skill-id>

1. Verify skill is installed and has passed audit (or warn if not audited).
2. Show: "Enable {skill-id}? This activates its adapter in templates/skill_adapters/."
3. Run: `python scripts/skill_manager.py --target . --enable <skill-id>`
4. Report: "Skill enabled. Restart Claude Code to load it."

### Step 9: If --disable <skill-id>

1. Show: "Disable {skill-id}? Source code stays in skills/_vendor/ — only the adapter is deactivated."
2. Run: `python scripts/skill_manager.py --target . --disable <skill-id>`
3. Report: "Skill disabled. Run --enable <id> to re-enable."

### Step 10: If --update-catalog

Run: `python scripts/skill_manager.py --target . --update-catalog`
Report the version change.

## Profile Quick Reference

| Profile | Skills | Best For |
|---------|--------|----------|
| `core` | 0 external | Pure PKB. Start here, add later. |
| `student` | 8 | Coursework, papers, literature review |
| `research` | 12 | Graduate research, systematic literature |
| `developer` | 7 | Code projects, docs, GitHub research |
| `creator` | 7 | Writers, musicians, filmmakers |
| `output` | 7 | Reports, papers, presentations |
| `security` | 3 | Audit, sanitize before sharing |
| `full` | 24 | All recommended. Review risks first. |
| `custom` | interactive | Hand-pick from 42 entries |

## Z-Skills (Third-Party Local Install)

z-skills is a third-party skill collection (https://github.com/tjxj/z-skills). PKB Starter does NOT bundle or redistribute it. The user may choose to install it locally.

### Install Flow

```
/project:skills --install z-skills
  |
  +---> Shows risk explanation + "PKB does not distribute this code"
  +---> User must type 'INSTALL' to confirm
  +---> git clone -> skills/_vendor/z-skills/
  +---> Status: pending_audit (NOT auto-enabled)

/project:skills --audit
  |
  +---> Automatically audits z-skills if installed
  +---> Delegates to zskill_bridge.py for LICENSE check
  +---> Generates zskill_audit_report.md

/project:skills --enable z-web-pack-local
  |
  +---> Only if z-skills installed AND audited
  +---> Activates z_skills_adapter.md
  +---> z-web-pack now available as collector backend

/project:web --collector z-web-pack <url>
  |
  +---> Uses z-web-pack for collection
  +---> Output routed to raw/webpacks/ via adapter
```

### Important Notes

- z-skills is NOT a built-in PKB component.
- PKB Starter does not redistribute z-skills source code.
- The user must audit license terms before use.
- Adapter only connects output — does not modify z-skills source.
- Default collector is PKB's built-in basic web_pack.
- To remove: delete `skills/_vendor/z-skills/` and disable the adapter.

## Safety Rules

1. **Never auto-execute** third-party skill scripts. Installation = git clone only.
2. **Never auto-configure** MCP servers. User must edit `.claude/mcp.json` manually.
3. **Never read or store** API keys for third-party skills.
4. **z-skills is a local install option**, not a bundled component. PKB Starter does NOT distribute its code. The user must explicitly opt in via `--install z-skills`.
5. **High-risk skills** (cnki-skills, zotero-mcp, z-skills) require explicit user confirmation.
6. **NO LICENSE repos** must be flagged. Warn user: "Treat as all rights reserved — personal reference only."
7. **Before enabling** a skill, remind user to review its LICENSE and code.
8. **Always show** the skill's description, risk explanation, and requirements before installing.
9. **z-web-pack-local** can only be enabled after z-skills is installed AND audited.
10. **Never patch** z-skills source by default. If path issues arise, prefer wrapper/configuration solutions.
