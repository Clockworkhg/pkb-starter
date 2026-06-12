# /output — Save Conversation Output

You are the PKB output save agent.

## Task
Save valuable content from the current conversation to `wiki/outputs/`.

## Execution

### 1. Identify valuable content in current conversation
### 2. Save to `wiki/outputs/YYYY-MM-DD-short-description.md`
### 3. Include frontmatter:
```yaml
---
created: YYYY-MM-DD
updated: YYYY-MM-DD
type: output
tags: []
source_conversation: "<brief topic>"
---
```
### 4. If research conclusion, also update related pages in `wiki/concepts/`
### 5. Report where content was saved
