# COMMANDS.md — PKB Command Reference

> You only need to remember ONE command.

---

## 🚀 Single Entry Point: `/pkb`

```
/pkb <anything>
```

Throw anything at `/pkb`, the Agent auto-decides what to do:

| You throw in | Agent auto-does |
|-------------|-----------------|
| `/pkb C:\Users\me\paper.pdf` | 📥 Import file to _INBOX |
| `/pkb C:\Users\me\project\` | 📥 Import entire folder |
| `/pkb https://example.com/article` | 🌐 Raw layer collection → raw/webpacks |
| `/pkb https://github.com/author/repo` | 🌐 GitHub special collection → raw/webpacks |
| `/pkb transformer attention concept` | 🔍 Search wiki and answer |
| `/pkb save` | 💾 Git commit current state |
| `/pkb check` | 🩺 Run health check |

### /pkb Routing Logic

| Input Type | Executes | Notes |
|-----------|----------|-------|
| Single webpage | `/clip` | Quick clip to raw/clippings |
| GitHub link | `/web` | GitHub README/raw preferred |
| Multiple links | `/web` | Generate webpack |
| Paper link | `/web` | Expand references |
| Docs/tutorials | `/web` | Expand related pages |
| Question/keywords | search wiki | Answer from knowledge base |
| "save" | `/save` | Git commit |
| "check" | `/lint` | Health check |

---

## 📋 Standalone Commands

### Core Commands
| Command | Purpose |
|---------|---------|
| `/add <path>` | Import file/folder to _INBOX |
| `/inbox` | View pending files |
| `/web <URL>` | 🌐 Raw layer web collection → raw/webpacks |
| `/clip` | Collect clipboard content |
| `/ask <question>` | Search knowledge base |
| `/output` | Save conversation output |
| `/lint` | Knowledge base health check |
| `/docs-update` | Auto-detect + update project docs |
| `/save "message"` | Git commit (with auto doc update) |
| `/rollback` | View/rollback git history |
| `/help` | Show help |
| `/skills` | Manage optional skill packs |

### Skill Management Commands
| Command | Purpose |
|---------|---------|
| `/project:skills` | Show installed skills, enabled status, and available profiles |
| `/project:skills --list` | List all 42 catalog entries with descriptions and risk levels |
| `/project:skills --describe <id>` | Show full details for a skill (what, risk, how to install) |
| `/project:skills --install <id>` | Install a single skill with description + risk shown first |
| `/project:skills --install-profile <profile>` | Install all skills from a profile (core/student/research/...) |
| `/project:skills --audit` | Audit installed skills: license, adapter, .git, issues |
| `/project:skills --enabled` | Show currently enabled skills and adapters |
| `/project:skills --enable <id>` | Enable an audited skill (activates its adapter) |
| `/project:skills --disable <id>` | Disable a skill without deleting source code |
| `/project:skills --update-catalog` | Refresh local catalog version |

### Research Commands (requires academic-research-skills plugin)
| Command | Purpose |
|---------|---------|
| `/research <topic>` | Deep research (multi-source search + report) |
| `/paper <path>` | Paper analysis/writing |
| `/literature-search <query>` | Multi-source academic search |
| `/literature-review <topic>` | Lit review with multi-perspective dialogue |

### Tool Commands
| Command | Purpose |
|---------|---------|
| `/sanitize <file>` | Privacy sanitization |
| `/search <keyword>` | Full-text search |

---

## 💡 Laziest Daily Usage

```
# Throw it in and done (default autopilot)
/pkb "file path or URL"

# Batch process _INBOX (default autopilot)
/inbox

# Query
/ask question

# Manual control (if you want to review)
/pkb --manual "file path"
/pkb --collect-only "https://..."
/pkb --plan "file1" "file2"
```

**`/pkb` is autopilot by default**: import → classify → compile wiki → archive → health check → git commit.
You only need to read the final report.

### /web — Web Pack

```bash
# Default full mode (complete image pipeline + GitHub Collector)
python tools/web_pack.py --topic "Topic" --url "https://..."

# Safe mode (no cookie/video/login state)
python tools/web_pack.py --topic "Topic" --url "https://..." --mode safe

# Video collection
python tools/web_pack.py --topic "Topic" --url "https://..." --videos all --download-media

# Key parameters
--mode full|safe         # Mode (default full)
--videos off|direct|all  # Video mode (default direct)
--download-media         # Full media download
--browser-cookies chrome # yt-dlp cookie (full mode only)
--max-image-mb 20        # Per-image cap
--max-video-mb 300       # Per-video cap
--same-domain-only       # Same-domain only
```

Output: `raw/webpacks/YYYY-MM-DD-topic/`
Content extraction: readability-lxml → trafilatura → BeautifulSoup → Jina
Image capability: srcset, magic bytes, SHA256 dedup, tracking filter, Referer anti-leech (16 features)
Video capability: yt-dlp platform videos, subtitles, thumbnails, 1080p cap

---

*Part of PKB Starter. See AGENTS.md for detailed rules.*
