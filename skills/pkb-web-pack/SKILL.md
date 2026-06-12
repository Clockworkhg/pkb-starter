# pkb-web-pack — Web Content Collection

## When to Use
- User provides URLs to collect: `/web <url>` or `/pkb <url>`
- GitHub repository collection
- WeChat article collection
- Any web content that needs structured archival

## Instructions

### 1. Determine topic and mode
- Extract topic from URL title or user specification
- Default mode: `full` (complete image pipeline + media)
- Safe mode: `--mode safe` (no cookies, no videos, basic images)

### 2. Run web_pack.py
```bash
# Standard web page
python tools/web_pack.py --topic "<topic>" --url "<url>" --max-depth 1 --max-pages 80

# GitHub repository (auto-detects and uses API → git clone)
python tools/web_pack.py --topic "<topic>" --url "https://github.com/user/repo"

# Safe mode (restricted environments)
python tools/web_pack.py --topic "<topic>" --url "<url>" --mode safe

# With video
python tools/web_pack.py --topic "<topic>" --url "<url>" --videos all --download-media
```

### 3. Output Structure
```
raw/webpacks/YYYY-MM-DD-<topic>/
├── README.md                  # Overview
├── 00-research-brief.md       # Research context
├── 01-link-inventory.md       # All links found
├── 02-image-inventory.md      # All images found
├── 03-reading-map.md          # Content reading guide
├── 04-media-inventory.md      # Media files (if any)
├── MAIN-01-<title>.md         # Main page content
├── LINKED-02-<title>.md       # Linked pages
├── manifest.json              # Machine-readable metadata
└── assets/                    # Downloaded images/media
```

### 4. Content Extraction Pipeline
1. GitHub repo/blob → API / raw URL
2. readability-lxml (primary)
3. trafilatura (fallback)
4. BeautifulSoup + markdownify (fallback)
5. Jina Reader (last resort)

### 5. Image Capabilities (full mode)
- Lazy loading: `data-src`, `data-original`, `data-lazy-src`, `data-actualsrc`, `data-echo`, `data-url`
- Responsive: `srcset` picks largest, `picture > source`
- Anti-leech: all image requests with page Referer
- Fix: magic bytes to correct extensions
- Dedup: SHA256 content hash global dedup
- Filter: 1×1 tracking pixels, shields.io badges, favicons, placeholders
- Content-Type validation

### 6. Video/Media (explicit opt-in)
- `direct` (default): `<video>` / `<source>` / direct mp4/webm/mov links
- `all`: yt-dlp for YouTube/Bilibili/Vimeo/X/TikTok/m3u8
- Subtitles: `--write-subs --write-auto-subs`
- Thumbnails: `--write-thumbnail`, converted to jpg
- 1080p cap, per-video size limit configurable

## Safety Notes
- Skip login-required pages (detect login/signin/token/cookie patterns)
- Skip personal account pages
- Don't execute webpage scripts
- Don't auto-upload any files
- `--browser-cookies` only for yt-dlp, never for HTTP requests, never written to files
- `--mode safe` disables cookies, videos, and login-state handling entirely
