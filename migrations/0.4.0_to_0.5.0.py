#!/usr/bin/env python3
"""Migration: 0.4.0 -> 0.5.0

Changes:
  - Add starter_version and schema_version to pkb.config.json
  - Add last_updated_at timestamp
  - Add .claude/commands/update.md (project:update command)
  - Ensure skills.catalog_version is set
  - Add .pkb_backup/ to .gitignore
"""

import json
import sys
from pathlib import Path
from datetime import datetime, timezone


def can_migrate(target: Path) -> bool:
    """Check if this migration can run on the target."""
    config_path = target / "pkb.config.json"
    if not config_path.is_file():
        print(f"  [SKIP] No pkb.config.json found in {target}")
        return False

    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"  [ERROR] Cannot read config: {e}")
        return False

    # Check version range
    version = config.get("starter_version") or config.get("version") or "0.0.0"
    if not _version_lt(version, "0.5.0"):
        print(f"  [SKIP] Already at version {version} (>= 0.5.0)")
        return False

    return True


def dry_run(target: Path):
    """Preview what would change."""
    print(f"  Dry run: 0.4.0 -> 0.5.0 migration for {target}")
    print(f"  Would update: pkb.config.json (add starter_version, schema_version, last_updated_at)")
    print(f"  Would create: .claude/commands/update.md")
    print(f"  Would update: .gitignore (add .pkb_backup/)")
    print(f"  Would set:    skills.catalog_version = '0.5.0'")


def upgrade(target: Path) -> list:
    """Execute the migration. Returns list of changed paths."""
    changes = []

    # 1. Update pkb.config.json
    config_path = target / "pkb.config.json"
    if config_path.is_file():
        config = json.loads(config_path.read_text(encoding="utf-8"))
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        if "starter_version" not in config:
            config["starter_version"] = "0.5.0"
            changes.append("pkb.config.json: added starter_version = 0.5.0")

        if "schema_version" not in config:
            config["schema_version"] = "0.5.0"
            changes.append("pkb.config.json: added schema_version = 0.5.0")

        config["last_updated_at"] = now
        changes.append("pkb.config.json: updated last_updated_at")

        # Ensure skills section has catalog_version
        if "skills" not in config:
            config["skills"] = {}
        config["skills"]["catalog_version"] = "0.5.0"
        changes.append("pkb.config.json: set skills.catalog_version = 0.5.0")

        config_path.write_text(
            json.dumps(config, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )

    # 2. Create .claude/commands/update.md if not present
    update_cmd = target / ".claude" / "commands" / "update.md"
    if not update_cmd.is_file():
        update_cmd.parent.mkdir(parents=True, exist_ok=True)
        update_cmd.write_text(_UPDATE_COMMAND_CONTENT, encoding="utf-8")
        changes.append(".claude/commands/update.md: created")

    # 3. Ensure .gitignore has .pkb_backup/
    gitignore = target / ".gitignore"
    backup_entry = ".pkb_backup/"
    if gitignore.is_file():
        content = gitignore.read_text(encoding="utf-8")
        if backup_entry not in content:
            content += f"\n{backup_entry}\n"
            gitignore.write_text(content, encoding="utf-8")
            changes.append(".gitignore: added .pkb_backup/")
    else:
        gitignore.write_text(f"{backup_entry}\n", encoding="utf-8")
        changes.append(".gitignore: created with .pkb_backup/")

    return changes


def _version_lt(a: str, b: str) -> bool:
    """Compare semantic versions: True if a < b."""
    try:
        parts_a = [int(x) for x in a.split(".")]
        parts_b = [int(x) for x in b.split(".")]
        # Pad to same length
        while len(parts_a) < 3:
            parts_a.append(0)
        while len(parts_b) < 3:
            parts_b.append(0)
        return parts_a < parts_b
    except Exception:
        return a < b


_UPDATE_COMMAND_CONTENT = """# /project:update — Check and update PKB system files from pkb-starter

Update the current knowledge base's system files (tools, commands, skill registry,
adapters) to the latest pkb-starter version. User data is NEVER touched.

## Behavior

1. Detect installed version from pkb.config.json (starter_version).
2. Compare with latest pkb-starter version.
3. If up-to-date, report and exit.
4. Create backup in .pkb_backup/YYYYMMDD_HHMMSS/.
5. Run incremental migrations from installed version to current.
6. Update system files: tools/, .claude/commands/, skill_adapters/, skills_registry/.
7. Update pkb.config.json version fields.
8. Generate update_report.md.

## Safety

- **No overwrite of user data**: raw/, wiki/, _INBOX/ are never touched.
- **Backup before changes**: full system file backup in .pkb_backup/.
- **Config preserved**: user settings in pkb.config.json are merged, not replaced.
- **Dry-run support**: use /project:update --dry-run to preview.

## Usage

```
/project:update              # Check and update
/project:update --dry-run    # Preview changes without applying
/project:update --backup-only # Create backup only
```

## Fallback

If the update fails, restore from the backup directory:
```
cp -r .pkb_backup/<LATEST>/* .
```

## Notes

- Requires git installed (for safety diff).
- Migrations are incremental and idempotent.
- This command is itself updated by the migration process.
"""


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python 0.4.0_to_0.5.0.py <target_pkb_path> [--dry-run]")
        sys.exit(1)

    target = Path(sys.argv[1])
    is_dry = "--dry-run" in sys.argv

    if not target.is_dir():
        print(f"[ERROR] Target not found: {target}")
        sys.exit(1)

    if not can_migrate(target):
        sys.exit(0)

    if is_dry:
        dry_run(target)
    else:
        changes = upgrade(target)
        print(f"  Migration 0.4.0 -> 0.5.0: {len(changes)} change(s)")
        for c in changes:
            print(f"    - {c}")
