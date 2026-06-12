# PKB Starter — Examples

## Example 1: Collect and Ingest a Blog Post

```
User: /project:pkb https://karpathy.bearblog.dev/llm-wiki/

Agent:
  [1/10] Parsed: URL → web collection
  [2/10] Running: python tools/web_pack.py --topic "llm-wiki" --url "https://karpathy.bearblog.dev/llm-wiki/"
  [3/10] Collected: 1 page, 3 images, 12 links → raw/webpacks/2026-06-12-llm-wiki/
  [4/10] Ingesting: llm-wiki → wiki/sources/llm-wiki-karpathy.md + wiki/concepts/llm-wiki.md
  [5/10] Indexing: updated wiki/index.md (+1 entry)
  [6/10] Archiving: 1 webpack processed
  [7/10] Logging: wiki/log.md + log.md updated
  [8/10] Health check: ✅ passed
  [9/10] Git commit: f3a21bc — [PKB] auto ingest: 2026-06-12 — llm-wiki blog post
  [10/10] 📊 Report:
    ✅ 1 new wiki page
    ✅ 1 concept page updated
    🩺 Health: passed
    🔗 Commit: f3a21bc
```

## Example 2: Import and Analyze a PDF Paper

```
User: /project:pkb ~/Downloads/attention-is-all-you-need.pdf

Agent:
  [1/10] Parsed: local file — attention-is-all-you-need.pdf
  [2/10] Importing: ~/Downloads/attention-is-all-you-need.pdf → _INBOX/imported/
  [3/10] Ingesting: academic paper detected
           → wiki/sources/attention-is-all-you-need.md
           → wiki/concepts/transformer-architecture.md
  [4/10] Indexing: updated wiki/index.md
  [5/10] Archiving: _INBOX → raw/imported_processed/attention-is-all-you-need.pdf
  [6/10] Logging: done
  [7/10] Health check: ✅ passed
  [8/10] Git commit: a4b56cd — [PKB] auto ingest: 2026-06-12 — attention is all you need
  [9/10] 📊 Report:
    ✅ 2 new wiki pages
    📄 PDF: 12 pages, 2.3 MB
    🩺 Health: passed
    🔗 Commit: a4b56cd
```

## Example 3: Search Your Knowledge Base

```
User: /project:ask transformer attention mechanism

Agent: 🔍 Searching wiki/ and raw/ for "transformer attention mechanism"...

## 🔍 Query Results

### Direct Answer
From [[transformer-architecture]]:
The Transformer uses multi-head self-attention where Query, Key, Value
matrices compute attention scores: Attention(Q,K,V) = softmax(QK^T/√dk)V.

### Related Wiki Pages
- [[transformer-architecture]] — Full architecture description
- [[attention-is-all-you-need]] — Original paper source note
- [[llm-wiki]] — LLM Wiki knowledge base concept

### Related Raw Materials
- `raw/papers/attention-is-all-you-need.pdf` — Original paper

### Knowledge Gaps
- No content on Flash Attention or efficient attention variants
  → Run /project:web https://arxiv.org/abs/2205.14135 to collect
```

## Example 4: GitHub Repository Collection

```
User: /project:pkb https://github.com/squidfunk/mkdocs-material

Agent:
  [1/10] Parsed: GitHub URL — squidfunk/mkdocs-material
  [2/10] Running: GitHub Collector mode
           → GitHub raw: README.md, CONTRIBUTING.md
  [3/10] Collected: 3 pages, 5 code files → raw/webpacks/2026-06-12-mkdocs-material/
  [4/10] Ingesting: mkdocs-material tool → wiki/sources/mkdocs-material.md + wiki/concepts/static-site-generator.md
  ...
  [10/10] Report: [OK] 2 wiki pages, Health: passed
```

## Example 5: Daily Health Check

```
User: /project:lint

Agent:
🩺 PKB Health Check Report
═══════════════════════

✅ Passed (5 items)
  - All frontmatter complete (42 pages)
  - No broken wikilinks (156 checked)
  - No sensitive info detected
  - All source_path references valid
  - Index consistency: 42/42 pages indexed

⚠️ Warnings (2 items)
  - wiki/concepts/old-methodology.md — last updated 120 days ago
  - wiki/sources/archived-project.md — orphan page (no inbound links)

📊 Stats
  - Wiki pages: 42
  - Concepts: 18 | Sources: 15 | Projects: 5 | Outputs: 4
  - Raw files: 87
  - Total size: 156 MB
```

---

*More examples will be added as the community contributes them.*
