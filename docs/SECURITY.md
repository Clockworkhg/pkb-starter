# PKB Starter — Security

Languages: [English](SECURITY.md) | [简体中文](zh-CN/SECURITY.md)

## What PKB Does NOT Upload

PKB is a **local-first** system. By default:
- **Nothing leaves your machine** — no cloud sync, no telemetry, no analytics
- **No auto-push** to remote git repositories
- **No external API calls** except when YOU explicitly request web collection (`/web`)
- **All knowledge stays in `raw/` and `wiki/`** on your local disk

## What You Should NOT Put in PKB

### 🔴 Never add:
- API keys, tokens, passwords, secrets
- Private keys (SSH, PGP, SSL certificates)
- `.env` files or equivalent
- OAuth client secrets
- Database connection strings
- Credit card numbers, bank accounts
- Government ID numbers, passport scans
- Medical records
- Authentication cookies

### 🟡 Be cautious with:
- Personal email addresses in wiki pages (use `redacted@example.com` or generic placeholders)
- Phone numbers
- Home addresses
- Employment contracts
- Proprietary code from work
- Confidential documents

### 🟢 Safe to add:
- Public web articles
- Academic papers (published)
- Open source code
- Personal notes and summaries
- Project documentation
- Learning materials

## Cookie / Full Mode Security

`web_pack.py` has two modes:

### `--mode safe` (recommended for sensitive browsing)
- No cookies read
- No video downloads
- No login-state handling
- Basic image collection only

### `--mode full` (opt-in, more capable)
- `--browser-cookies` flag available ONLY when combined with `--download-media`
- Cookies are ONLY passed to yt-dlp for video platform access
- Cookies are NEVER used for HTTP page requests
- Cookies are NEVER written to any file (not manifest.json, not markdown, not logs)
- Cookies are NEVER included in git commits

## Git Safety

### `.gitignore` protects:
```
.env, .env.*
*credentials*, *serviceAccount*
*.pem, *.p12, *.pfx, *.key
id_rsa*, *_rsa
.claude/settings.local.json
raw/personal/*id_card*, *passport*, *bank*, *medical*
```

### `/save` pre-commit check:
Before every git commit, `/save` runs a secret scan:
1. Checks all staged files for API key / token / password patterns
2. Blocks commit if critical patterns found
3. Warns on potential PII (email, phone)

## Before Sharing Your Knowledge Base

If you plan to make your PKB public (e.g., on GitHub):

1. **Run sanitize**: `/sanitize wiki/` scans and reports sensitive patterns
2. **Remove raw/personal/**: This directory exists specifically for content you NEVER want public
3. **Review wiki/**: Check for accidentally included personal info
4. **Check git history**: `git log -p` to verify no sensitive data in commit history
5. **Squash if needed**: If sensitive data was ever committed, use `git filter-branch` or similar

## Sharing Specific Pages Safely

To share just a wiki page:
```
/sanitize wiki/concepts/my-concept.md --fix
# Review the sanitized version
# Share the sanitized copy only
```

The original remains untouched. Sanitize creates a copy with redactions.

## Privacy Levels

PKB supports marking content with privacy levels:

```yaml
---
privacy: internal   # Don't quote in /ask output
privacy: public     # Safe to share
---
```

Set in frontmatter. The `/ask` skill respects this and won't expose `internal` content in responses.

## Optional Skills Security

PKB's optional skill system (42 catalog entries, 9 distinct external repos) uses the following safety measures:

1. **No auto-execution**: Skills are installed via `git clone --depth 1` only. No install scripts, no post-clone hooks, no npm/pip install.
2. **Vendored isolation**: Skills live in `skills/_vendor/` (gitignored). They do not modify PKB core files.
3. **Adapter routing**: All skill output goes through PKB adapters that enforce `raw/`/`wiki/` placement. Skills cannot scatter files in the project root.
4. **No MCP auto-config**: Skills requiring MCP servers need manual `.claude/mcp.json` configuration. PKB never touches MCP config.
5. **No API key storage**: PKB never reads, stores, or passes API keys for third-party skills.
6. **Risk classification**: 
   - 28 low-risk (auto-install)
   - 10 medium-risk (warn before install)
   - 5 high-risk (require explicit confirmation)
   - 0 reference-only (z-skills is now user-approved local install)
7. **LICENSE review**: Each skill entry records its license status. Skills with NO LICENSE are flagged. Z-skills requires full audit before enable.
8. **Z-skills local install**: User must explicitly opt in ("INSTALL"), audit the repository, and explicitly enable the adapter. PKB Starter does NOT distribute z-skills code. See docs/Z_WEB_PACK_PARITY.md.
8. **Plugin marketplace**: 2 skills are only installable via Claude Code's official plugin marketplace, not via git clone.
9. **Removal = delete directory**: To remove a skill, delete `skills/_vendor/<skill-id>/`. No lingering state.
10. **Audit trail**: `skill_manager.py --audit` and `/project:skills --audit` report all installed skills with risk levels, license status, .git verification, adapter presence, and INSTALL_NOTE.md presence. Z-skills audit is delegated to `zskill_bridge.py audit` and generates `zskill_audit_report.md`.

### Runtime Safety

Skills can be installed at any time — during setup or months later. The same safety rules apply:

- **Every skill shows its description and risk before installation** — both in CLI and Claude Code.
- **Installation does NOT equal activation** — skills go through audit before being enabled.
- **Enable is explicit** — `--enable <id>` is a separate step after audit.
- **Disable doesn't delete** — `--disable <id>` deactivates the adapter but keeps source code.
- **Start small** — Core profile (zero external skills) is the safest default. Add skills incrementally.
- **Full profile warning** — The Full profile lists all 24 recommended skills but does NOT auto-enable high-risk ones.

### Z-Skills Safety

PKB Starter's z-skills compatibility module follows strict safety rules:

1. **No code redistribution** — PKB Starter does NOT include, copy, or bundle z-skills source.
2. **User explicit opt-in** — Installing z-skills requires typing 'INSTALL' after reading the risk explanation.
3. **Audit before enable** — z-skills goes to `pending_audit` after clone. Must pass audit before `z-web-pack-local` can be enabled.
4. **No auto-execution** — The zskill_bridge.py does NOT auto-execute z-skills scripts. It only describes how to invoke them.
5. **No default patching** — z-skills source is never modified. Incompatibilities are resolved through wrappers, configuration, or output relocation.
6. **Local patches only (if absolutely needed)** — Require `--allow-local-patch`. Stored in `.pkb_local/patches/` (gitignored). Never committed or distributed.
7. **Output isolation** — z-web-pack output goes to `raw/webpacks/` (same as PKB's built-in collector). Never writes to wiki/ directly.
8. **Default collector unchanged** — The basic web_pack remains default. z-web-pack is opt-in.

## Reporting Security Issues

Found a security issue in PKB Starter? Please report via GitHub Issues on the pkb-starter repository. Do NOT include sensitive data in the issue.
