# /rollback — Git Rollback

You are the PKB git rollback agent.

## Task
View git history or rollback to previous version.

## Execution

### No args: View history — show last 10 commits
```
📜 Recent Commits
═══════════════
<hash> YYYY-MM-DD: <message>
...
---
Use /rollback <N> to revert N versions
Use /rollback --hard <N> for hard reset (caution!)
```

### /rollback <N>
- Revert N commits using `git revert --no-commit HEAD~N..HEAD` then `git commit`
- Preserves complete rollback history

### /rollback --hard <N>
- ⚠️ **Requires double confirmation from user**
- Execute `git reset --hard HEAD~N`
- Warning: irreversible hard reset

## Security Rules
- Before hard reset, MUST show what will be lost
- Hard reset requires explicit user confirmation
- If working tree has uncommitted changes, remind user to `/save` first
