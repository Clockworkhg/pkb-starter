# PKB web_pack -- Z-Web-Pack Parity

> Capability comparison between

Languages: [English](Z_WEB_PACK_PARITY.md) | [简体中文](zh-CN/Z_WEB_PACK_PARITY.md) PKB's built-in web_pack collector and z-web-pack (tjxj/z-skills), plus z-skills compatibility module documentation.

## Two Collectors

PKB offers two web collector backends:

| | PKB Basic web_pack | Z-Web-Pack (via z-skills) |
|---|---|---|
| **Status** | Built-in, always available | Optional, user-installed locally |
| **Distribution** | Bundled in PKB Starter (MIT) | NOT distributed by PKB |
| **Install** | Included in template | User clones from tjxj/z-skills |
| **License** | MIT (PKB project) | Per-directory, audit required |
| **Default** | Yes | No (explicit opt-in) |
| **Activation** | Always active | Install -> audit -> enable |

## v0.1.0 Status: Basic Collector (PKB built-in)

The v0.1.0 release ships a basic web collector covering:

| Capability | Status |
|-----------|--------|
| Single URL collection | [OK] |
| Multi-URL collection | [OK] |
| Content extraction (requests + BS4) | [OK] |
| Markdown conversion (markdownify) | [OK] |
| Title / body / link / image extraction | [OK] |
| GitHub blob/raw URL handling | [OK] |
| Standard output structure | [OK] |
| README.md + manifest.json | [OK] |
| 01-link-inventory.md | [OK] |
| 02-image-inventory.md | [OK] |
| 03-reading-map.md | [OK] |
| 04-media-inventory.md | [OK] |

## Capability Comparison

| Capability | PKB basic web_pack | z-web-pack |
|---|---|---|
| Public web page collection | Yes | Yes |
| Readability content extraction | Yes (readability-lxml + trafilatura) | Yes |
| BeautifulSoup fallback | Yes | Yes |
| Markdown conversion | Yes (markdownify) | Yes |
| Structured webpack output | Yes | Yes |
| README + manifest | Yes | Yes |
| Link inventory | Yes | Yes |
| Image inventory | Basic | Advanced (srcset, magic bytes) |
| Reading map | Yes | Yes |
| Media inventory | Basic | Advanced |
| Image download | Basic | Advanced (SHA256 dedup, Referer) |
| Image srcset / picture handling | Planned v0.2 | Yes |
| Magic bytes detection | Planned v0.2 | Yes |
| Video / yt-dlp integration | Not planned | Yes |
| Browser cookie support | Not included | Opt-in |
| GitHub collection | Yes (API + git clone) | Yes |
| WeChat article handling | Yes (max-depth 0) | Unknown |
| Multi-layer crawling | Basic | Advanced |
| Jina Reader fallback | Planned v0.2 | Unknown |
| Tracking pixel / favicon filter | Planned v0.2 | Yes |

## v0.2 Roadmap (PKB built-in)

1. Lazy-loading image attribute support (data-src, data-original, etc.)
2. Deduplication of downloaded assets
3. GitHub API + git clone depth-1 fallback chain
4. Content quality heuristics (weak content detection)
5. Optional media download (opt-in, no cookie handling)

All v0.2 features will be independently implemented without reference to z-web-pack code.

## Output Structure Compatibility

PKB web_pack produces the same output file structure as z-web-pack for basic collections:

```
raw/webpacks/<YYYY-MM-DD>-<topic>/
  README.md
  manifest.json
  01-link-inventory.md
  02-image-inventory.md
  03-reading-map.md
  04-media-inventory.md
  MAIN-<topic>.md
  snapshots/
    <page>.md
  assets/
```

This structural compatibility means wiki ingestion scripts work identically regardless of which collector produced the webpack.

---

## Z-Skills Compatibility Module (v0.4.1)

### What It Is

A bridge module that allows PKB users to optionally install z-skills locally and use z-web-pack as an alternative collector backend.

### What It Is NOT

- NOT a redistribution of z-skills code
- NOT a modification of z-skills source
- NOT a replacement of PKB's built-in web_pack
- NOT a dependency or requirement
- NOT enabled by default

### Architecture

```
User action                      PKB / Z-Skills state
-----------                      --------------------
/project:skills --install
  z-skills            ------>    git clone tjxj/z-skills
                                 -> skills/_vendor/z-skills/
                                 -> Status: pending_audit
                                 -> NOT auto-enabled

/project:skills --audit ------>  zskill_bridge.py audit
                                 -> Check LICENSE files
                                 -> Generate zskill_audit_report.md

/project:skills --enable
  z-web-pack-local    ------>    Enable z_skills_adapter.md
                                 -> z-web-pack now selectable
                                 -> Does NOT modify z-skills code

/project:web --collector
  z-web-pack <url>    ------>    zskill_bridge.py run
                                 -> Invoke z-web-pack
                                 -> import-output to raw/webpacks/
                                 -> Same wiki pipeline from here
```

### Files Involved

| File | Location | Purpose |
|------|----------|---------|
| `z_skills_adapter.md` | `template/skill_adapters/` | Adapter routing rules |
| `zskill_bridge.py` | `template/tools/` | Bridge: locate, audit, run, import |
| `skill_catalog.json` | `skills_registry/` | z-skills + z-web-pack-local entries |
| `skills.md` | `template/.claude/commands/` | /project:skills z-skills flow |
| `web.md` | `template/.claude/commands/` | --collector z-web-pack option |
| `pkb.md` | `template/.claude/commands/` | --collector z-web-pack option |
| `.gitignore` | `template/` | skills/_vendor/, .pkb_local/, reports |

### No Code from Z-Skills

PKB Starter contains ZERO lines of z-skills code. The bridge:

- Reads `SKILL.md` to understand z-web-pack's interface (conceptual reference only)
- Invokes z-web-pack through Claude Code skill invocation (not direct script execution)
- Copies z-web-pack output from its output directory to PKB's `raw/webpacks/`

### Safety Rules

1. **No code redistribution**: PKB Starter does NOT include, copy, or bundle z-skills source.
2. **User explicit opt-in**: Installing z-skills requires typing 'INSTALL' after reading the risk explanation.
3. **Audit before enable**: z-skills goes to `pending_audit` after clone. Must pass audit before `z-web-pack-local` can be enabled.
4. **No auto-execution**: The bridge does NOT auto-execute z-skills scripts.
5. **No default patching**: z-skills source is never modified. Incompatibilities are resolved through wrappers, configuration, or output relocation.
6. **Local patches only (if absolutely needed)**: Require `--allow-local-patch`. Stored in `.pkb_local/patches/` (gitignored). Never committed or distributed.
7. **Output isolation**: z-web-pack output goes to `raw/webpacks/` (same as PKB's built-in collector).
8. **Default collector unchanged**: The basic web_pack remains default. z-web-pack is opt-in.

### Why Not Just Use Z-Web-Pack by Default

1. **Licensing**: z-skills has per-directory licensing. PKB Starter cannot assume permission to distribute.
2. **User choice**: Users should decide which third-party code runs on their machine.
3. **Simplicity**: PKB's built-in collector handles 90%+ of common use cases with zero setup.
4. **Independence**: PKB's collector can evolve on its own roadmap without external dependencies.
5. **Security**: Audit-before-use is the safer default for third-party code.

### Choosing Between Collectors

| Scenario | Recommended Collector |
|----------|----------------------|
| Quick article save | PKB basic web_pack |
| Research paper collection | PKB basic web_pack |
| GitHub README/docs | PKB basic web_pack |
| WeChat articles | PKB basic web_pack |
| Heavy image sites (srcset needed) | z-web-pack |
| Video page archiving | z-web-pack |
| Multi-layer deep crawl | z-web-pack |
| Side-by-side comparison | Both |

### Default Path

The **default is always PKB basic web_pack**. It works without any setup. Z-web-pack is available for users who need its advanced capabilities and are willing to install, audit, and enable it manually.

---

## Legal Note

z-web-pack is a Claude Code skill by tjxj in the z-skills repository. PKB Starter does not include, derive from, or redistribute z-web-pack or z-skills code. Users who want z-web-pack's full capabilities should install it directly from https://github.com/tjxj/z-skills and observe its license terms.

PKB's web_pack.py is an independent clean-room implementation whose functional design was inspired by z-web-pack's documented output structure. No z-web-pack code, constants, regex, comments, or scripts were used in PKB's implementation.

---

*PKB Starter v0.4.1. Updated: 2026-06-12.*
