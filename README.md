# PKB Starter ![version](https://img.shields.io/badge/version-v0.6.3--alpha-blue)

> **One command to rule your knowledge.** `/pkb <anything>` — throw in a URL, file, or idea. The LLM organizes everything.
>
> **Current version**: v0.6.3-alpha

Languages: [English](README.md) | [简体中文](README.zh-CN.md)

PKB Starter is a **Claude Code plugin + project template** that gives you a local, LLM-maintained personal knowledge base in minutes. Based on Karpathy's [LLM Wiki](https://karpathy.bearblog.dev/llm-wiki/) concept.

## What It Does

```
You: /project:pkb https://karpathy.bearblog.dev/llm-wiki/
PKB: [auto-collects → extracts → classifies → creates wiki page → links concepts → git commits]
     Done. 2 wiki pages created. Health: [OK]
```

## Features

- 🚀 **One command**: `/pkb <anything>` — fully automatic ingest
- 🧠 **LLM-organized**: AI classifies, links, and maintains your knowledge
- 📄 **Rich collection**: Web pages, PDFs, DOCX, PPTX, GitHub repos, videos
- 🔗 **Obsidian-compatible**: `[[wikilink]]` graph, open wiki/ as vault
- 🔒 **Local-first**: Nothing leaves your machine
- 🩺 **Self-healing**: Health checks find broken links, stale content, orphans
- 💾 **Git-native**: Every change is a commit, full rollback support

## Quick Install

```bash
git clone https://github.com/pkb-starter/pkb-starter.git
cd pkb-starter
python scripts/install.py "D:\MyKB"
cd "D:\MyKB"
pip install -r requirements.txt
claude
```

> **Path is up to you**: `D:\MyKB` is an example. Install anywhere — `E:\KnowledgeBase`, `C:\Users\...\Documents\PKB`, `F:\ResearchKB`, etc. The first positional argument to `install.py` is your chosen target directory. ASCII paths are recommended to avoid encoding issues with Python, Git, and shell tools.

In Claude Code (project mode):
```
/project:help                        # See all commands
/project:pkb https://example.com     # Start collecting
```

> **Note**: Commands use `/project:<name>` format. Bare `/pkb` is only available if pkb-starter is installed as a Claude Code plugin. See [TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) if commands aren't found.

[Full Quick Start →](docs/QUICKSTART.md)

## Architecture

```
raw/          Immutable raw materials (web collections, PDFs, files)
wiki/         LLM-maintained structured knowledge (Markdown + [[wikilinks]])
skills/       Agent automation rules (7 skills)
tools/        Python helper scripts (web_pack, import, sanitize, etc.)
```

[Design Deep Dive →](docs/DESIGN.md)

## Commands

| Command | What It Does |
|---------|-------------|
| `/project:pkb <anything>` | Smart entry — auto-detects type and processes |
| `/project:web <url>` | Collect web content to raw/webpacks |
| `/project:inbox` | Process pending files |
| `/project:ask <question>` | Search your knowledge base |
| `/project:lint` | Health check |
| `/project:save` | Git commit with auto doc update |
| `/project:rollback` | View/rollback git history |
| `/project:sanitize` | Privacy scan |
| `/project:skills` | Manage optional skill packs |
| `/project:update` | Update system files from pkb-starter |

## Optional Skills

PKB Starter ships with zero external dependencies. Extend it with **optional skill packs** from a catalog of 43 entries across 9 tracked external repositories (plus z-skills as user-approved local install):

```bash
# During installation
python scripts/install.py "D:\MyKB" --profile student    # 8 skills — academic essentials
python scripts/install.py "D:\MyKB" --profile developer  # 7 skills — docs + projects
python scripts/install.py "D:\MyKB" --profile research   # 12 skills — full pipeline
python scripts/install.py "D:\MyKB" --interactive-skills # pick from 42 entries

# Anytime after installation
python scripts/skill_manager.py --target "D:\MyKB" --list
python scripts/skill_manager.py --target "D:\MyKB" --install-profile student
python scripts/skill_manager.py --target "D:\MyKB" --install deep-research-skills
```

Or from Claude Code:
```
/project:skills                       # See status
/project:skills --list                # Browse catalog
/project:skills --describe <id>       # Learn about a skill
/project:skills --install-profile student
/project:skills --audit
```

Profiles: **Core** (0 external) | **Student** (8) | **Research** (12) | **Developer** (7) | **Creator** (7) | **Output** (7) | **Security** (3) | **Full** (24) | **Custom** (interactive)

Every skill shows its description, risk level, and requirements before installation. Third-party skills are cloned to `skills/_vendor/` — never auto-executed, never auto-configured. Start with Core, add skills as needed.

See the full catalog: `python scripts/skill_manager.py --target "D:\MyKB" --list`

[Optional Skills Guide →](docs/OPTIONAL_SKILLS.md)

## Who Is This For?

- **Researchers**: Collect papers, build literature maps, auto-generate citations
- **Developers**: Document projects, collect code references, maintain design decisions
- **Writers**: Research topics, organize sources, build concept maps
- **Students**: Course notes, paper analysis, exam prep
- **Anyone** who wants a "second brain" that maintains itself

## What PKB Is NOT

- **NOT a cloud service** — everything is local files on your disk
- **NOT a note-taking app** — use Obsidian for that; PKB is the auto-organizer
- **NOT a search engine** — it searches YOUR knowledge, not the web
- **NOT a backup tool** — use proper backups; PKB uses git for versioning

## Web Collector

PKB Starter v0.1.0 ships with a **basic web collector** (`tools/web_pack.py`) that handles:
- Public web page fetching (requests + BeautifulSoup)
- Content extraction (title, body, links, images)
- Markdown conversion (markdownify)
- GitHub blob/raw URL handling
- Standard output structure (README, manifest, inventories)

**Z-Web-Pack (optional local install)**: Users may optionally install [z-web-pack](https://github.com/tjxj/z-skills/tree/main/z-web-pack) as an alternative collector backend. PKB Starter does NOT distribute z-skills or z-web-pack code. The user must:
1. Explicitly opt in: `/project:skills --install z-skills`
2. Audit license: `/project:skills --audit z-skills`
3. Enable adapter: `/project:skills --enable z-web-pack-local`
4. Use: `/project:web --collector z-web-pack <url>`

See [Z_WEB_PACK_PARITY.md](docs/Z_WEB_PACK_PARITY.md) for capability comparison and the z-skills compatibility module.

## Updating

PKB Starter tracks its version in `pkb.config.json`. When you update pkb-starter from GitHub, your installed KB can be upgraded without reinstalling.

**Recommended — use the update client installed in your KB:**

```bash
cd "D:\MyKB"
python tools/pkb_update_client.py              # Preview (dry-run by default)
python tools/pkb_update_client.py --apply      # Apply changes
```

Or in Claude Code:
```
/project:update                  # Dry-run by default
/project:update --apply          # Apply changes
```

**Alternative — for users with a local pkb-starter clone:**

```bash
python tools/pkb_update_client.py --starter-path "D:\pkb-starter"
```

**Advanced — direct update_pkb.py:**

```bash
python scripts/update_pkb.py "D:\MyKB" --dry-run
```

Every update creates a timestamped backup in `.pkb_backup/`. User data (`raw/`, `wiki/`, `_INBOX/`, `skills/_vendor/`, `.pkb_local/`) is **never** touched. Config fields (`language`, `install_path`, `starter_repo_url`) are **always preserved**.

[Update Guide →](docs/UPDATING.md)

## Safety

- Nothing uploaded by default
- Sensitive info detection (API keys, tokens, PII)
- `.gitignore` with comprehensive security rules
- Safe/full collection modes
- [Security Guide →](docs/SECURITY.md)

## Requirements

- **Claude Code** (with Claude API access)
- **Python 3.9+**
- **Git**
- Optional: Obsidian (for visual browsing)

## Documentation

| Doc | Content |
|-----|---------|
| [QUICKSTART.md](docs/QUICKSTART.md) | 5-minute setup |
| [DESIGN.md](docs/DESIGN.md) | Architecture deep dive |
| [SECURITY.md](docs/SECURITY.md) | Privacy & safety |
| [Z_WEB_PACK_PARITY.md](docs/Z_WEB_PACK_PARITY.md) | web_pack capabilities |
| [TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) | Common issues |
| [OPTIONAL_SKILLS.md](docs/OPTIONAL_SKILLS.md) | Optional skill packs |
| [UPDATING.md](docs/UPDATING.md) | Update and migration guide |
| [EXAMPLES.md](docs/EXAMPLES.md) | Usage examples |

## Contributing

Contributions welcome! Areas we'd love help with:
- Additional content type classifiers
- More source format support
- Platform-specific install scripts
- Documentation improvements

## License

MIT — see [LICENSE](LICENSE)

---

*Built on the idea that knowledge management should be 1% human effort, 99% AI organization.*
