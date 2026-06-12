# Z-Skills Adapter

## Metadata

- **skill_name**: Z-Skills (tjxj/z-skills)
- **adapter_version**: 0.1.0
- **install_status**: USER OPT-IN ONLY — NOT bundled, NOT distributed
- **when_to_use**: Only after user explicitly installs z-skills into `skills/_vendor/z-skills/`, passes audit, and enables this adapter.

## Purpose

This adapter connects user-installed z-skills (specifically z-web-pack) output into PKB's standard `raw/webpacks/` and wiki ingestion pipeline. It does NOT contain z-skills code. It is a routing bridge only.

## Supported Local Paths

| Component | Expected Path |
|-----------|--------------|
| z-skills root | `skills/_vendor/z-skills/` |
| z-web-pack SKILL.md | `skills/_vendor/z-skills/z-web-pack/SKILL.md` |
| z-web-pack scripts | `skills/_vendor/z-skills/z-web-pack/scripts/` |
| Audit report | `zskill_audit_report.md` (generated in PKB root) |
| Local patches (if any) | `.pkb_local/patches/` (never committed, never distributed) |

## Install Lifecycle

```
User runs:        /project:skills --install z-skills
                  |
                  +---> git clone https://github.com/tjxj/z-skills
                  |     -> skills/_vendor/z-skills/
                  |     -> Status: pending_audit (NOT auto-enabled)
                  |
User runs:        /project:skills --audit z-skills
                  |
                  +---> python tools/zskill_bridge.py audit
                  |     -> Checks LICENSE / LICENSE.txt / COPYING
                  |     -> Records license_status per directory
                  |     -> Generates zskill_audit_report.md
                  |
User runs:        /project:skills --enable z-web-pack-local
                  |
                  +---> Only if z-skills installed AND audited
                  |     -> Enables z_skills_adapter.md
                  |     -> Does NOT copy z-web-pack code
                  |     -> Does NOT patch z-web-pack source
                  |
                  |     Now usable as collector backend:
                  |     /project:web --collector z-web-pack <url>
                  |     /project:pkb --collector z-web-pack <url>
```

## Audit Requirements

Before enabling, the user must audit:

1. **LICENSE check**: Look for LICENSE, LICENSE.txt, or COPYING in:
   - `skills/_vendor/z-skills/` (root)
   - `skills/_vendor/z-skills/z-web-pack/`
   - Each sub-skill directory may have its own license terms.

2. **If no license found**: Treat as "all rights reserved." Use for personal, local reference only. Do NOT redistribute any part.

3. **If license restricts copying/derivative works/distribution**: Mark as `local_use_only`. Adapter may route output but must not modify or redistribute any z-skills code.

4. **Run**: `python tools/zskill_bridge.py audit` to generate a structured report.

## How Z-Web-Pack Output Maps to PKB

When z-web-pack runs, its output directory is copied/synced to PKB's standard locations:

| Z-Web-Pack Output | PKB Destination |
|-------------------|-----------------|
| `<output-dir>/` (webpack) | `raw/webpacks/<topic>/` |
| README.md | Preserved in webpack dir |
| manifest.json | Merged into PKB manifest |
| Image/media files | `raw/webpacks/<topic>/` (same structure) |
| *.md inventories | Preserved for wiki compilation |

The `zskill_bridge.py import-output` command handles this mapping.

## Safety Rules

1. **Never auto-execute**: z-skills scripts are NEVER auto-executed. The bridge only runs when the user explicitly invokes it after enabling the adapter.
2. **Never auto-configure**: No MCP, API keys, or environment variables are configured for z-skills.
3. **Never redistribute**: PKB Starter does not include, copy, or redistribute z-skills code.
4. **Never auto-patch**: z-skills source is never modified by default.
5. **Output isolation**: All z-web-pack output is routed to `raw/webpacks/` — the same location as PKB's built-in web_pack output. It never writes to wiki/ directly.
6. **Adapter-only**: This adapter is a routing document. It contains no executable code.
7. **Disable, don't delete**: `/project:skills --disable z-web-pack-local` deactivates the adapter but leaves `skills/_vendor/z-skills/` intact.

## No Redistribution Policy

- PKB Starter does NOT include any z-skills source code, scripts, or documentation.
- The `repo_url` field in the catalog points to the original repository. Users clone directly from there.
- This adapter only describes how PKB interacts with a user's local clone.
- If the user removes `skills/_vendor/z-skills/`, this adapter becomes inert.

## No Default Patching Policy

- The bridge does NOT modify z-skills source code by default.
- If a path or parameter is incompatible, the bridge attempts to handle it through:
  1. Wrapper scripts (calling z-web-pack with correct arguments)
  2. Configuration (passing correct flags)
  3. Output relocation (moving results to PKB paths after z-web-pack finishes)
- Local patches are a last resort — see below.

## Local Patch Policy (If Absolutely Needed)

If z-skills code MUST be locally modified to work with PKB:

1. The user must explicitly run: `python tools/zskill_bridge.py patch --allow-local-patch`
2. Patches are generated in `.pkb_local/patches/` (gitignored).
3. `.pkb_local/` is in `.gitignore` — never committed.
4. Patches are NEVER distributed, committed, or included in pkb-starter.
5. The bridge warns: "Local patches are for your machine only. Do not commit or share."
6. Original z-skills files are never modified — patches are applied as overlays.
