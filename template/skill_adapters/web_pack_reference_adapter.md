# Web Pack Reference Adapter

## Metadata

- **skill_name**: Z-Skills / z-web-pack (tjxj/z-skills)
- **adapter_version**: 0.2.0
- **install_status**: REFERENCE ONLY -- NOT INSTALLABLE
- **when_to_use**: Design reference for PKB's web_pack collector. Read for inspiration. Do NOT copy code.

## Why Reference Only

z-skills (including z-web-pack) is copyright Anthropic, PBC. ALL RIGHTS RESERVED.
Its LICENSE explicitly forbids:
- Copying code
- Creating derivative works
- Redistribution

PKB Starter respects this. We do NOT:
- Include any z-skills code
- Clone or vendor z-skills
- Auto-install z-skills as a dependency

## What to Read Instead

- PKB's `tools/web_pack.py` -- Independent clean-room basic collector (v0.1.0)
- PKB's `docs/Z_WEB_PACK_PARITY.md` -- Capability comparison and roadmap
- z-web-pack SKILL.md (read on GitHub) -- Functional design patterns (concepts only, not code)

## Conceptual Mapping (Design Inspiration Only)

| z-web-pack Concept | PKB Equivalent | Implementation |
|-------------------|---------------|---------------|
| Structured webpack output | Same directory layout | `tools/web_pack.py` (independent) |
| README + manifest | README.md + manifest.json | PKB format |
| Link inventory | 01-link-inventory.md | Clean implementation |
| Image inventory | 02-image-inventory.md | Basic (no magic bytes / srcset in v0.1.0) |
| Reading map | 03-reading-map.md | Clean implementation |
| Media inventory | 04-media-inventory.md | Clean implementation |
| Advanced image pipeline | Planned v0.2 | Clean-room design |
| Video/yt-dlp integration | NOT planned | PKB focuses on text-first collection |

## Command Integration

- N/A -- z-skills is not installed. PKB's web_pack serves the same role.
- `/project:web <url>` -- Uses PKB web_pack, not z-web-pack
- `/project:pkb <url>` -- Uses PKB web_pack for collection phase

## Safety Notes

- If you manually install z-skills, observe Anthropic's LICENSE terms.
- Do NOT mix z-web-pack code with PKB code in your local installation.
- The PKB adapter system does NOT bridge to z-skills code -- it documents the design relationship.
- If you need z-web-pack's full capabilities, install it independently per its LICENSE terms.
