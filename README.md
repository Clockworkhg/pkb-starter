# PKB Starter

> **One command to rule your knowledge.** `/pkb <anything>` — throw in a URL, file, or idea. The LLM organizes everything.

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
python scripts/install.py "D:\MyKnowledgeBase"
cd "D:\MyKnowledgeBase"
pip install -r requirements.txt
claude
```

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

**What's NOT included**: Advanced image pipeline (srcset, magic bytes, tracking filter), video/yt-dlp integration, browser cookie support, Jina Reader fallback. These capabilities are planned for v0.2 clean-room implementation.

The collector's functional design is inspired by [z-web-pack](https://github.com/tjxj/z-skills/tree/main/z-web-pack). No code from z-web-pack is included — see [Z_WEB_PACK_PARITY.md](docs/Z_WEB_PACK_PARITY.md) for details. To use z-web-pack directly, refer to its repository and license terms.

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
