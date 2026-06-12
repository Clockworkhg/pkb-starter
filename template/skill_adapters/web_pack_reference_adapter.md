# Web Pack Reference Adapter (LEGACY)

> **NOTE**: This adapter is superseded by `z_skills_adapter.md` (v0.4.1+).
> Z-skills is now available as a user-approved local install.
> See [docs/Z_WEB_PACK_PARITY.md](../docs/Z_WEB_PACK_PARITY.md) for details.

## Metadata

- **skill_name**: Z-Skills / z-web-pack (tjxj/z-skills)
- **adapter_version**: 0.2.0 (legacy reference)
- **install_status**: SUPERSEDED — use `z_skills_adapter.md` for installable z-skills
- **when_to_use**: Design reference for PKB's web_pack collector. For actual z-web-pack integration, use `/project:skills --install z-skills`.

## Historical Reference

This adapter was created when z-skills was categorized as reference_only in the catalog. As of PKB Starter v0.4.1, z-skills is available as a user-approved local install. PKB Starter still does NOT distribute z-skills code, but users may now install it locally with explicit consent.

## What to Use Instead

- **For design reference**: Read `z_skills_adapter.md` for the current integration rules.
- **For z-web-pack integration**: Use `/project:skills --install z-skills` flow.
- **For PKB's built-in collector**: Continue using `tools/web_pack.py` (default).
- **For capability comparison**: See `docs/Z_WEB_PACK_PARITY.md`.

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

## Safety Notes

- This adapter is legacy. For current z-skills safety rules, see `z_skills_adapter.md`.
- PKB Starter does NOT distribute z-skills code.
- User must explicitly install, audit, and enable z-skills before use.
- Default collector is PKB's built-in web_pack (always available).
