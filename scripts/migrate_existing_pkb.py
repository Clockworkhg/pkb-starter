#!/usr/bin/env python3
"""PKB Starter -- Migrate existing PKB to pkb-starter template.

Detects an existing PKB directory and safely upgrades it to the
pkb-starter structure without touching personal data.

Usage:
    python scripts/migrate_existing_pkb.py "<existing_pkb_path>"
    python scripts/migrate_existing_pkb.py "<existing_pkb_path>" --dry-run
"""

import os
import sys
import shutil
import json
from pathlib import Path
from datetime import datetime, timezone

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "template"
SKILLS_DIR = Path(__file__).resolve().parent.parent / "skills"

# Protected content — never overwrite these during migration
PROTECTED_PATHS = [
    "raw/**",
    "wiki/**",
    "_INBOX/**",
    "raw/imported_processed/**",
    "raw/personal/**",
]


def is_protected(rel_path: str) -> bool:
    """Check if a relative path contains user content that should not be overwritten."""
    for pattern in PROTECTED_PATHS:
        # Simple glob matching
        if pattern.endswith("/**"):
            prefix = pattern[:-3]
            if rel_path.startswith(prefix) or rel_path == prefix.rstrip("/"):
                return True
    return False


def detect_existing_pkb(path: Path) -> dict:
    """Detect if a directory is an existing PKB installation."""
    result = {
        "is_pkb": False,
        "version_hint": None,
        "has_wiki": False,
        "has_raw": False,
        "has_skills": False,
        "has_commands": False,
        "missing_sections": [],
    }

    if (path / "AGENTS.md").is_file():
        result["is_pkb"] = True

    if (path / "wiki").is_dir():
        result["has_wiki"] = True
    else:
        result["missing_sections"].append("wiki/")

    if (path / "raw").is_dir():
        result["has_raw"] = True
    else:
        result["missing_sections"].append("raw/")

    if (path / "skills").is_dir() and any((path / "skills").iterdir()):
        result["has_skills"] = True

    if (path / ".claude" / "commands").is_dir():
        result["has_commands"] = True
    else:
        result["missing_sections"].append(".claude/commands/")

    # Try to read config
    config_path = path / "pkb.config.json"
    if config_path.is_file():
        try:
            config = json.loads(config_path.read_text(encoding="utf-8"))
            result["version_hint"] = config.get("version")
        except Exception:
            pass

    return result


def migrate(path: Path, dry_run: bool = False) -> dict:
    """Migrate an existing PKB to pkb-starter template."""
    report = {
        "path": str(path),
        "created": [],
        "updated": [],
        "skipped": [],
        "errors": [],
    }

    if not path.is_dir():
        report["errors"].append(f"Directory not found: {path}")
        return report

    # Ensure required directories exist
    required_dirs = [
        "_INBOX/imported",
        "raw/webpacks",
        "raw/papers",
        "raw/imported_processed",
        "wiki/concepts",
        "wiki/sources",
        "wiki/projects",
        "wiki/outputs",
    ]
    for d in required_dirs:
        target = path / d
        if not target.is_dir():
            if dry_run:
                report["created"].append(f"{d}/ (would create)")
            else:
                target.mkdir(parents=True, exist_ok=True)
                report["created"].append(f"{d}/")

    # Copy/update template files (skip protected content)
    for src in TEMPLATE_DIR.rglob("*"):
        if src.is_dir():
            continue
        if any(p.startswith("__") for p in src.parts):
            continue

        rel = src.relative_to(TEMPLATE_DIR)
        if is_protected(str(rel)):
            continue

        dst = path / rel
        dst.parent.mkdir(parents=True, exist_ok=True)

        if dst.exists():
            if dry_run:
                report["updated"].append(str(rel) + " (would update)")
            else:
                shutil.copy2(src, dst)
                report["updated"].append(str(rel))
        else:
            if dry_run:
                report["created"].append(str(rel) + " (would create)")
            else:
                shutil.copy2(src, dst)
                report["created"].append(str(rel))

    # Update pkb.config.json
    config_path = path / "pkb.config.json"
    config = {}
    if config_path.is_file():
        try:
            config = json.loads(config_path.read_text(encoding="utf-8"))
        except Exception:
            pass

    config["template"] = "pkb-starter"
    config["migrated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if "version" not in config:
        config["version"] = "0.1.0"

    if not dry_run:
        config_path.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")
        report["updated"].append("pkb.config.json")

    return report


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    target = Path(sys.argv[1]).resolve()
    dry_run = "--dry-run" in sys.argv

    print(f"=== PKB Migration Tool ===")
    print(f"Target: {target}")
    if dry_run:
        print("Mode: DRY RUN (no changes will be made)")
    print()

    # Detect
    print("[1/3] Detecting existing PKB...")
    status = detect_existing_pkb(target)

    if not status["is_pkb"]:
        print(f"  [WARN] {target} does not appear to be an existing PKB.")
        print(f"  Use scripts/install.py for fresh installation.")
        response = input("  Continue migration anyway? [y/N]: ")
        if response.lower() != 'y':
            print("  Aborted.")
            sys.exit(0)

    print(f"  PKB detected: wiki={status['has_wiki']}, raw={status['has_raw']}, "
          f"skills={status['has_skills']}, commands={status['has_commands']}")
    if status["missing_sections"]:
        print(f"  Missing sections: {', '.join(status['missing_sections'])}")

    # Migrate
    print("[2/3] Migrating...")
    report = migrate(target, dry_run=dry_run)

    # Report
    print("[3/3] Migration report:")
    if report["errors"]:
        print(f"  Errors: {len(report['errors'])}")
        for e in report["errors"]:
            print(f"    [ERROR] {e}")
    print(f"  Created: {len(report['created'])} items")
    for item in report["created"]:
        print(f"    + {item}")
    print(f"  Updated: {len(report['updated'])} items")
    for item in report["updated"]:
        print(f"    ~ {item}")
    print(f"  Skipped (protected): {len(report['skipped'])} items")

    print()
    if dry_run:
        print("  Dry run complete. Run without --dry-run to apply changes.")
    elif report["errors"]:
        print("  Migration completed with errors. Review above.")
    else:
        print("  Migration complete. Run `claude` in the target directory to start.")
        print(f"  cd {target}")
        print("  claude")


if __name__ == "__main__":
    main()
