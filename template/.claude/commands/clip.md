# /clip — Clipboard Collection

You are the PKB clipboard collection agent.

## Task
Read clipboard content, auto-process by type, save to knowledge base.

## Execution Steps

### 1. Read clipboard
- Use `powershell Get-Clipboard` for text
- If image, save to `raw/media/images/`
- If file path list, call `/add` to import

### 2. Classify content type
- **URL** → call `/web` to collect
- **Code snippet** → save to `raw/clippings/code-YYYY-MM-DD-HHmmss.md`
- **Article/text** → save to `raw/clippings/text-YYYY-MM-DD-HHmmss.md`
- **Todo** → save to `wiki/tasks/`
- **Note/idea** → save to `raw/personal/`

### 3. Generate frontmatter for all saved Markdown files
```yaml
---
created: YYYY-MM-DD HH:mm
source: clipboard
type: <code|text|task|note>
tags: []
---
```

### 4. Report — where content was saved, whether further processing needed
