#!/usr/bin/env python3
"""Migration: 0.4.1-alpha -> 0.5.0-alpha

Baseline: v0.4.1-alpha (includes Z-Skills Compatibility Module, commit 9e8d33b)
Target:   v0.5.0-alpha (adds sync/update/migration workflow)

Changes:
  - Add starter_version and schema_version to pkb.config.json
  - Add last_updated_at timestamp
  - Add .claude/commands/update.md (project:update command)
  - Ensure skills.catalog_version is set (preserves existing skills state)
  - Add .pkb_backup/ to .gitignore
  - Add z-skills protected entries to .gitignore if missing
"""

import json
import sys
import re
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

    # Check version range (handles alpha suffixes)
    version = config.get("starter_version") or config.get("version") or "0.0.0"
    if not _version_lt(version, "0.5.0"):
        print(f"  [SKIP] Already at version {version} (>= 0.5.0)")
        return False

    return True


def dry_run(target: Path):
    """Preview what would change."""
    print(f"  Dry run: 0.4.1-alpha -> 0.5.0-alpha migration for {target}")
    print(f"  Baseline: v0.4.1-alpha (Z-Skills Compatibility Module, commit 9e8d33b)")
    print(f"  Would update: pkb.config.json (add starter_version, schema_version, last_updated_at)")
    print(f"  Would create: .claude/commands/update.md")
    print(f"  Would update: .gitignore (add .pkb_backup/ and z-skills entries)")
    print(f"  Would set:    skills.catalog_version = '0.5.0' (if missing)")
    print(f"  Skills state: preserved (installed_profiles, installed_skills, etc.)")


def upgrade(target: Path) -> list:
    """Execute the migration. Returns list of changed paths."""
    changes = []

    # 1. Update pkb.config.json (preserve skills state)
    config_path = target / "pkb.config.json"
    if config_path.is_file():
        config = json.loads(config_path.read_text(encoding="utf-8"))
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        if "starter_version" not in config:
            config["starter_version"] = "0.5.0-alpha"
            changes.append("pkb.config.json: added starter_version = 0.5.0-alpha")
        else:
            config["starter_version"] = "0.5.0-alpha"
            changes.append("pkb.config.json: updated starter_version -> 0.5.0-alpha")

        if "schema_version" not in config:
            config["schema_version"] = "0.5.0"
            changes.append("pkb.config.json: added schema_version = 0.5.0")
        else:
            config["schema_version"] = "0.5.0"
            changes.append("pkb.config.json: updated schema_version -> 0.5.0")

        config["last_updated_at"] = now
        changes.append("pkb.config.json: updated last_updated_at")

        # Ensure skills section exists and has catalog_version
        if "skills" not in config:
            config["skills"] = {}
        if "catalog_version" not in config["skills"]:
            config["skills"]["catalog_version"] = "0.5.0"
            changes.append("pkb.config.json: set skills.catalog_version = 0.5.0")

        # Ensure all skills state fields exist (don't clear existing!)
        skills_defaults = {
            "installed_profiles": [],
            "installed_skills": [],
            "enabled_skills": [],
            "disabled_skills": [],
            "vendor_downloads": [],
            "enabled_adapters": [],
            "pending_audit": [],
        }
        for key, default in skills_defaults.items():
            if key not in config["skills"]:
                config["skills"][key] = default
                changes.append(f"pkb.config.json: added missing skills.{key} = {default}")

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

    # 3. Ensure .gitignore has all PKB entries
    gitignore = target / ".gitignore"
    required_entries = [
        ".pkb_backup/",
        "skills/_vendor/",
        ".pkb_local/",
        "zskill_audit_report.md",
        "skill_manager_report.md",
    ]

    if gitignore.is_file():
        content = gitignore.read_text(encoding="utf-8")
        for entry in required_entries:
            if entry not in content:
                content += f"\n{entry}\n"
                changes.append(f".gitignore: added {entry}")
        gitignore.write_text(content, encoding="utf-8")
    else:
        gitignore.write_text('\n'.join(required_entries) + '\n', encoding="utf-8")
        changes.append(f".gitignore: created with {len(required_entries)} entries")

    return changes


def _version_lt(a: str, b: str) -> bool:
    """Compare semantic versions. True if a < b.
    Handles suffixes like -alpha, -beta, -rc1.
    -alpha < -beta < -rc < final (no suffix).
    """
    # Strip suffixes for numeric comparison
    def _parse(v: str) -> tuple:
        suffix_order = {"alpha": 0, "beta": 1, "rc": 2}
        # Remove leading 'v' if present
        v = v.lstrip("v")
        # Split suffix
        numeric_part = v
        suffix = ""
        suffix_num = 0
        for sep in ("-",):
            if sep in v:
                parts = v.split(sep, 1)
                numeric_part = parts[0]
                suffix_part = parts[1]
                # Extract suffix type and optional number (e.g. alpha, rc2)
                m = re.match(r"([a-zA-Z]+)(\d*)", suffix_part)
                if m:
                    suffix = m.group(1).lower()
                    suffix_num = int(m.group(2)) if m.group(2) else 0
                break
        try:
            nums = [int(x) for x in numeric_part.split(".")]
        except ValueError:
            nums = [0, 0, 0]
        while len(nums) < 3:
            nums.append(0)
        suffix_rank = suffix_order.get(suffix, 99) if suffix else 99
        return (nums[0], nums[1], nums[2], suffix_rank, suffix_num)

    return _parse(a) < _parse(b)


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
- **Skills state preserved**: installed_profiles, installed_skills, enabled_skills,
  disabled_skills, vendor_downloads, enabled_adapters, pending_audit are never cleared.
- **Z-skills vendor protected**: skills/_vendor/ and .pkb_local/patches are NEVER touched.
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
- v0.5.0-alpha baseline is v0.4.1-alpha (Z-Skills Compatibility Module).
"""


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python 0.4.1_to_0.5.0.py <target_pkb_path> [--dry-run]")
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
        print(f"  Migration 0.4.1-alpha -> 0.5.0-alpha: {len(changes)} change(s)")
        for c in changes:
            print(f"    - {c}")
