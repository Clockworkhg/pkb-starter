---
created: 2026-06-12
updated: 2026-06-12
type: concept
tags: [llm, knowledge-management, architecture]
---

# LLM Wiki

An **LLM Wiki** is a personal knowledge base maintained primarily by a Large Language Model rather than by a human. Coined by Andrej Karpathy, the concept inverts traditional personal knowledge management: instead of humans organizing and linking notes, the LLM does the structuring work.

## Core Principles

1. **Compiled, not retrieved**: The LLM reads and rewrites content into structured form, unlike RAG which retrieves chunks from a vector store
2. **Living knowledge**: As LLMs improve, the wiki can be regenerated with better organization
3. **Low-friction capture**: Users throw in raw materials (URLs, files, notes); the system handles organization

## How It Works

```
Raw Material → LLM reads → Classifies → Creates structured page → Links to related concepts
```

1. User provides input (web page, PDF, note)
2. LLM extracts and understands the content
3. LLM creates a wiki page with proper frontmatter and `[[wikilinks]]`
4. LLM updates indices and cross-references

## Advantages Over Traditional PKM

| Traditional PKM | LLM Wiki |
|----------------|----------|
| Human organizes | LLM organizes |
| Manual linking | Auto-linking |
| Stale over time | Can be regenerated |
| High friction | Low friction |

## PKB Implementation

PKB implements LLM Wiki as a three-layer architecture:
- `raw/` — Immutable raw materials
- `wiki/` — LLM-maintained structured knowledge
- `skills/` — Agent rules for automation

## References

- [[compiled-knowledge-base]] — Compiled vs retrieval comparison
- [[karpathy-llm-wiki-gist]] — Original source material
- [[raw-layer]] — Raw layer design
- [[pkb-web-pack]] — Web collection tool
