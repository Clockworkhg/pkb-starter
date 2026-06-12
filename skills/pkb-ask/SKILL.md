# pkb-ask — Knowledge Base Query

## When to Use
- User asks `/ask <question>` or a natural language question about their knowledge base
- User wants to find previously saved knowledge
- User wants to discover knowledge gaps

## Instructions

### 1. Parse the Question
- Extract key concepts and keywords
- Determine question type: fact lookup / concept explanation / relationship query / gap detection

### 2. Search wiki/
- Full-text search `wiki/` Markdown files
- Prioritize frontmatter `tags` field matches
- Follow `[[wikilink]]` to find related pages
- Search `wiki/concepts/` for concept definitions
- Search `wiki/sources/` for source materials

### 3. Search raw/
- Search `raw/` for related files by filename and content
- Check `raw/papers/` for academic papers
- Check `raw/webpacks/` for collected web content
- Check `raw/imported_processed/` for processed files

### 4. Compose Structured Answer
```
## 🔍 Query Results

### Direct Answer
[Based on wiki content, with [[wikilink]] citations]

### Related Wiki Pages
- [[page-1]] — brief description
- [[page-2]] — brief description

### Related Raw Materials
- `raw/papers/xxx.pdf` — context
- `raw/webpacks/topic/README.md` — context

### Knowledge Gaps
[List topics not yet covered — suggest /web to fill them]
```

### 5. No Results
If no matches found:
- Honestly report "no related content found"
- Suggest: `/web <related URL>` to collect
- Offer to help user formulate better search terms

## Examples
```
/ask transformer attention mechanism
/ask what is LLM wiki mode
/ask papers about platform governance
/ask find notes about <topic>
```

## Safety Notes
- Only search within the PKB directory — don't access external files
- Respect privacy levels in manifest.json (`privacy: internal` = don't quote in output)
- Don't expose raw file contents that may contain PII
