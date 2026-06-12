# PKB web_pack -- z-web-pack Relationship

## Summary

PKB Starter's `tools/web_pack.py` is a **clean-room basic collector** whose functional
design is inspired by [z-web-pack](https://github.com/tjxj/z-skills/tree/main/z-web-pack).
No code from z-web-pack is included or distributed with PKB Starter.

z-web-pack is copyright Anthropic, PBC. All rights reserved. It is not licensed for
redistribution. See the z-web-pack repository for its license terms.

## v0.1.0 Status: Basic Collector

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

## What's NOT in v0.1.0

The following z-web-pack capabilities are NOT present in v0.1.0:

- `srcset` responsive image selection
- `<picture>` element handling
- Magic bytes extension correction
- SHA256 image deduplication
- Tracking pixel / favicon filter
- Referer header anti-leech
- yt-dlp video/ media integration
- Browser cookie support
- Jina Reader fallback
- GitHub API / git clone fallback chain
- `--mode full` / `--mode safe` distinction
- Per-image/video size caps

## v0.2 Roadmap

These capabilities are planned for a v0.2 clean-room reimplementation:

1. Lazy-loading image attribute support (data-src, data-original, etc.)
2. Deduplication of downloaded assets
3. GitHub API + git clone depth-1 fallback chain
4. Content quality heuristics (weak content detection)
5. Optional media download (opt-in, no cookie handling)

All v0.2 features will be independently implemented without reference to z-web-pack code.

## Output Structure Compatibility

PKB web_pack v0.1.0 produces the same output file structure as z-web-pack
for basic collections:

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

This structural compatibility means wiki ingestion scripts work identically
regardless of which collector produced the webpack.

## Legal Note

z-web-pack is a Claude Code skill created by Anthropic, distributed under
Anthropic's Terms of Service with ALL RIGHTS RESERVED. It is available for
personal use within Claude Code through the z-skills plugin. PKB Starter
does not include, derive from, or redistribute z-web-pack code. Users who
want z-web-pack's full capabilities should install it directly and observe
its license terms.
