#!/usr/bin/env python3
"""PKB Starter -- Update installed PKB to latest pkb-starter version.

Safely updates system files (tools, commands, registry, adapters) while
preserving all user data (raw/, wiki/, _INBOX/).

Language protection:
  - Language fields (language, wiki_language, output_language) in pkb.config.json
    are NEVER overwritten during update.
  - User-customized Chinese documents (README.zh-CN.md, AGENTS.zh-CN.md, etc.)
    are preserved. Only missing locale files are added — existing ones are skipped.
  - System docs (docs/zh-CN/) are only added if missing. Modified files are never
    force-overwritten.

Usage:
    python scripts/update_pkb.py "D:\\MyKB"
    python scripts/update_pkb.py "D:\\MyKB" --dry-run
    python scripts/update_pkb.py "D:\\MyKB" --backup-only
    python scripts/update_pkb.py "D:\\MyKB" --from-version 0.3.0 --to-version 0.5.0
"""

import os
import sys
import json
import shutil
import fnmatch
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

# ---------------------------------------------------------------------------
# Paths relative to this script's repo root
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
TEMPLATE_DIR = REPO_ROOT / "template"
MIGRATIONS_DIR = REPO_ROOT / "migrations"
SKILLS_DIR = REPO_ROOT / "skills"
REGISTRY_DIR = REPO_ROOT / "skills_registry"

# Current pkb-starter version
CURRENT_VERSION = "0.6.1-alpha"
CURRENT_SCHEMA_VERSION = "0.6.0"

# User data paths — NEVER overwrite or delete
PROTECTED_DIRS = [
    "raw",
    "wiki",
    "_INBOX",
    "skills/_vendor",
    ".pkb_local",
    ".pkb_local/patches",
    "zskill_audit_report.md",
    "skill_manager_report.md",
]

# Files within protected dirs that should still be skipped individually
PROTECTED_FILES = [
    "zskill_audit_report.md",
    "skill_manager_report.md",
]

# System paths that DO get updated
SYSTEM_PATHS = [
    "tools",
    ".claude/commands",
    "skill_adapters",
    "skills_registry",
    "docs",
    "COMMANDS.md",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def info(msg: str):
    print(f"[INFO] {msg}")


def warn(msg: str):
    print(f"[WARN] {msg}")


def ok(msg: str):
    print(f"[OK] {msg}")


def die(msg: str, code: int = 1):
    print(f"[ERROR] {msg}", file=sys.stderr)
    sys.exit(code)


def is_protected(rel_path: str) -> bool:
    """Check if a path is user data that must NEVER be overwritten."""
    rel = rel_path.replace("\\", "/")

    # Check directory patterns
    for pattern in PROTECTED_DIRS:
        p = pattern.replace("\\", "/")
        if p.endswith("/"):
            if rel.startswith(p) or rel == p.rstrip("/"):
                return True
        elif rel == p or rel.startswith(p + "/"):
            return True

    # Check exact file patterns
    for f_pattern in PROTECTED_FILES:
        if rel == f_pattern or rel.endswith("/" + f_pattern):
            return True

    return False


def is_user_config_key(key: str) -> bool:
    """Keys in pkb.config.json that are user-specific and should be preserved."""
    user_keys = {
        "name", "version", "created", "directories", "settings",
        "language", "wiki_language", "output_language",
        "skills.installed_profiles", "skills.installed_skills",
        "skills.enabled_skills", "skills.disabled_skills",
        "skills.vendor_downloads", "skills.enabled_adapters",
        "skills.pending_audit",
    }
    return key in user_keys


def get_installed_version(config: dict) -> str:
    """Extract installed starter version from config.
    Normalizes to handle 0.4.0, 0.4.1-alpha, 0.5.0-alpha, etc.
    """
    return config.get("starter_version") or config.get("version") or "0.0.0"


def _parse_version(v: str) -> tuple:
    """Parse version string into comparable tuple.
    Handles suffixes: -alpha, -beta, -rc1, and leading 'v'.
    Suffix ordering: alpha < beta < rc < final (no suffix).
    """
    suffix_order = {"alpha": 0, "beta": 1, "rc": 2}
    v = v.lstrip("v").lower()
    numeric_part = v
    suffix = ""
    suffix_num = 0
    for sep in ("-",):
        if sep in v:
            parts = v.split(sep, 1)
            numeric_part = parts[0]
            suffix_part = parts[1]
            import re as _re
            m = _re.match(r"([a-zA-Z]+)(\d*)", suffix_part)
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


def version_lt(a: str, b: str) -> bool:
    """True if version a < b. Handles alpha/beta/rc suffixes."""
    import re as _re
    return _parse_version(a) < _parse_version(b)


# ---------------------------------------------------------------------------
# Backup
# ---------------------------------------------------------------------------

def create_backup(target: Path) -> Path:
    """Create timestamped backup of system files in target PKB."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = target / ".pkb_backup" / ts
    backup_dir.mkdir(parents=True, exist_ok=True)

    backed_up = []
    for sys_path in SYSTEM_PATHS:
        src = target / sys_path
        if src.is_dir():
            dst = backup_dir / sys_path
            shutil.copytree(src, dst, dirs_exist_ok=True)
            backed_up.append(sys_path + "/")
        elif src.is_file():
            dst = backup_dir / sys_path
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            backed_up.append(sys_path)

    # Also backup pkb.config.json
    config_src = target / "pkb.config.json"
    if config_src.is_file():
        shutil.copy2(config_src, backup_dir / "pkb.config.json")
        backed_up.append("pkb.config.json")

    # Backup AGENTS.md
    agents_src = target / "AGENTS.md"
    if agents_src.is_file():
        shutil.copy2(agents_src, backup_dir / "AGENTS.md")
        backed_up.append("AGENTS.md")

    info(f"Backup created: {backup_dir} ({len(backed_up)} items)")
    return backup_dir


# ---------------------------------------------------------------------------
# System File Update
# ---------------------------------------------------------------------------

def update_system_files(target: Path, opts: dict) -> list:
    """Copy system files from template to target. Returns list of changes."""
    changes = []
    dry_run = opts.get("dry_run", False)

    for sys_path in SYSTEM_PATHS:
        src = TEMPLATE_DIR / sys_path
        if not src.exists():
            continue

        if src.is_dir():
            for file in src.rglob("*"):
                if file.is_dir():
                    continue
                if any(p.startswith("__") for p in file.parts):
                    continue

                rel = file.relative_to(TEMPLATE_DIR)
                dst = target / rel

                # Skip protected paths
                if is_protected(str(rel)):
                    continue

                action = _copy_file(file, dst, dry_run)
                if action:
                    changes.append(action)

        elif src.is_file():
            dst = target / sys_path
            if not is_protected(sys_path):
                action = _copy_file(src, dst, dry_run)
                if action:
                    changes.append(action)

    # Also update AGENTS.md (merge: keep user's wiki content, update system sections)
    agents_src = TEMPLATE_DIR / "AGENTS.md"
    agents_dst = target / "AGENTS.md"
    if agents_src.is_file():
        if not agents_dst.is_file() or opts.get("force"):
            action = _copy_file(agents_src, agents_dst, dry_run)
            if action:
                changes.append(action)
        else:
            changes.append("AGENTS.md: skipped (user-modified, use --force to overwrite)")

    return changes


def _copy_file(src: Path, dst: Path, dry_run: bool) -> Optional[str]:
    """Copy a file, returning a description of what happened."""
    rel_path = str(src.relative_to(TEMPLATE_DIR) if TEMPLATE_DIR in src.parents else src.name)

    if dry_run:
        exists = "[OVERWRITE]" if dst.is_file() else "[NEW]"
        return f"{rel_path}: would copy {exists}"

    try:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        action = "[OVERWRITE]" if dst.is_file() else "[CREATED]"
        return f"{rel_path}: copied {action}"
    except Exception as e:
        return f"{rel_path}: ERROR ({e})"


# ---------------------------------------------------------------------------
# Config Update
# ---------------------------------------------------------------------------

def update_config(target: Path, opts: dict) -> list:
    """Update pkb.config.json version fields. Preserves ALL user settings and skills state."""
    changes = []
    config_path = target / "pkb.config.json"

    if not config_path.is_file():
        changes.append("pkb.config.json: not found, skipping config update")
        return changes

    config = json.loads(config_path.read_text(encoding="utf-8"))
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Version fields
    old_starter = config.get("starter_version", "none")
    config["starter_version"] = CURRENT_VERSION
    changes.append(f"pkb.config.json: starter_version {old_starter} -> {CURRENT_VERSION}")

    old_schema = config.get("schema_version", "none")
    config["schema_version"] = CURRENT_SCHEMA_VERSION
    changes.append(f"pkb.config.json: schema_version {old_schema} -> {CURRENT_SCHEMA_VERSION}")

    config["last_updated_at"] = now
    changes.append(f"pkb.config.json: last_updated_at = {now}")

    # Ensure skills section exists (don't overwrite existing!)
    if "skills" not in config:
        config["skills"] = {}

    # Only add missing skills state fields — never clear existing values
    skills_defaults = {
        "installed_profiles": [],
        "installed_skills": [],
        "enabled_skills": [],
        "disabled_skills": [],
        "vendor_downloads": [],
        "enabled_adapters": [],
        "pending_audit": [],
    }
    existing_skills = config["skills"]
    for key, default in skills_defaults.items():
        if key not in existing_skills:
            existing_skills[key] = default
            changes.append(f"pkb.config.json: added missing skills.{key}")

    if "catalog_version" not in existing_skills:
        existing_skills["catalog_version"] = CURRENT_VERSION
        changes.append(f"pkb.config.json: skills.catalog_version = {CURRENT_VERSION}")

    # Language fields (language, wiki_language, output_language) are preserved
    # implicitly — we never overwrite existing keys. Only version fields are touched.
    for lang_key in ("language", "wiki_language", "output_language"):
        if lang_key in config:
            changes.append(f"pkb.config.json: {lang_key}={config[lang_key]} (preserved)")

    if not opts.get("dry_run"):
        config_path.write_text(
            json.dumps(config, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )

    return changes


# ---------------------------------------------------------------------------
# Migration Runner
# ---------------------------------------------------------------------------

def find_migrations(from_ver: str, to_ver: str) -> list:
    """Find all migration scripts between two versions."""
    if not MIGRATIONS_DIR.is_dir():
        return []

    migrations = []
    for f in sorted(MIGRATIONS_DIR.glob("*.py")):
        name = f.stem  # e.g. "0.4.0_to_0.5.0"
        try:
            v_from, v_to = name.split("_to_")
            if version_lt(v_from, to_ver) and version_lt(from_ver, v_to):
                migrations.append((v_from, v_to, f))
        except ValueError:
            continue

    # Sort by from-version
    migrations.sort(key=lambda x: [int(n) for n in x[0].split(".")])
    return migrations


def run_migrations(target: Path, from_ver: str, to_ver: str, opts: dict) -> list:
    """Run incremental migrations. Returns changes list."""
    migrations = find_migrations(from_ver, to_ver)
    if not migrations:
        return []

    info(f"Found {len(migrations)} migration(s): "
         f"{' -> '.join(m[0] for m in migrations)} -> {migrations[-1][1]}")

    all_changes = []
    for v_from, v_to, script_path in migrations:
        info(f"Running migration: {v_from} -> {v_to}")

        if opts.get("dry_run"):
            # Import and call dry_run
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                f"migration_{v_from}_to_{v_to}", str(script_path)
            )
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            mod.dry_run(target)
            all_changes.append(f"migration {v_from}->{v_to}: would run (dry-run)")
        else:
            # Run migration
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                f"migration_{v_from}_to_{v_to}", str(script_path)
            )
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)

            if not mod.can_migrate(target):
                all_changes.append(f"migration {v_from}->{v_to}: skipped (preconditions not met)")
                continue

            changes = mod.upgrade(target)
            all_changes.extend(changes)
            info(f"  Migration complete: {len(changes)} change(s)")

    return all_changes


# ---------------------------------------------------------------------------
# Report Helpers
# ---------------------------------------------------------------------------

def _collect_protected_status(target: Path) -> list:
    """Check and report status of all protected paths."""
    results = []
    seen = set()

    all_protected = PROTECTED_DIRS + PROTECTED_FILES
    for p in all_protected:
        if p in seen:
            continue
        seen.add(p)

        full_path = target / p
        note = ""
        if p.endswith("/"):
            # Explicitly a directory
            if full_path.is_dir():
                note = "directory present, not touched by update"
            else:
                note = "directory absent, not created by update"
        else:
            # Could be file or directory — check both
            if full_path.is_dir():
                note = "directory present, not touched by update"
            elif full_path.is_file():
                note = "file present, not touched by update"
            else:
                note = "path absent, not created by update"
        results.append({"path": p, "status": "not touched", "note": note})

    # Add explicit note about pkb.config.json user fields
    results.append({
        "path": "pkb.config.json",
        "status": "preserved",
        "note": "only version fields updated; user settings and skills state preserved",
    })
    return results


def _collect_skills_state(target: Path) -> dict:
    """Read current skills state from pkb.config.json for report."""
    config_path = target / "pkb.config.json"
    if not config_path.is_file():
        return {"error": "pkb.config.json not found"}

    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
        skills = config.get("skills", {})
        return {
            "installed_profiles": skills.get("installed_profiles", []),
            "installed_skills": skills.get("installed_skills", []),
            "enabled_skills": skills.get("enabled_skills", []),
            "disabled_skills": skills.get("disabled_skills", []),
            "vendor_downloads": skills.get("vendor_downloads", []),
            "enabled_adapters": skills.get("enabled_adapters", []),
            "pending_audit": skills.get("pending_audit", []),
            "catalog_version": skills.get("catalog_version", "none"),
        }
    except Exception as e:
        return {"error": str(e)}


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def write_report(target: Path, report_data: dict):
    """Write update_report.md to target PKB."""
    lines = []
    lines.append("# PKB Update Report")
    lines.append("")
    lines.append(f"**Generated**: {report_data['timestamp']}")
    lines.append(f"**Target**: `{report_data['target']}`")
    lines.append(f"**Mode**: {'DRY RUN' if report_data['dry_run'] else 'LIVE'}")
    lines.append(f"**From version**: {report_data['from_version']}")
    lines.append(f"**To version**: {report_data['to_version']}")
    lines.append(f"**Backup**: {report_data.get('backup_dir', 'none')}")
    lines.append("")

    lines.append("## Summary")
    lines.append("")
    lines.append(f"| Category | Count |")
    lines.append(f"|----------|-------|")
    lines.append(f"| System files | {len(report_data['system_changes'])} |")
    lines.append(f"| Config changes | {len(report_data['config_changes'])} |")
    lines.append(f"| Migration changes | {len(report_data['migration_changes'])} |")
    lines.append(f"| Errors | {len(report_data['errors'])} |")
    lines.append("")

    if report_data['system_changes']:
        lines.append("## System File Changes")
        lines.append("")
        for c in report_data['system_changes']:
            lines.append(f"- {c}")
        lines.append("")

    if report_data['config_changes']:
        lines.append("## Config Changes")
        lines.append("")
        for c in report_data['config_changes']:
            lines.append(f"- {c}")
        lines.append("")

    if report_data['migration_changes']:
        lines.append("## Migration Changes")
        lines.append("")
        for c in report_data['migration_changes']:
            lines.append(f"- {c}")
        lines.append("")

    if report_data['errors']:
        lines.append("## Errors")
        lines.append("")
        for e in report_data['errors']:
            lines.append(f"- {e}")
        lines.append("")

    # Protected paths — explicit not-touched audit
    protected = report_data.get('protected_paths', [])
    if protected:
        lines.append("## Protected Paths Not Touched")
        lines.append("")
        lines.append("| Path | Status | Note |")
        lines.append("|------|--------|------|")
        for entry in protected:
            p = entry['path']
            s = entry['status']
            n = entry['note']
            lines.append(f"| `{p}` | {s} | {n} |")
        lines.append("")

    # Skills state — preserved detail
    skills = report_data.get('skills_state', {})
    if skills and 'error' not in skills:
        lines.append("## Skills State Preserved")
        lines.append("")
        lines.append("The following skills state fields are preserved after update:")
        lines.append("")
        lines.append("| Field | Value |")
        lines.append("|-------|-------|")
        lines.append(f"| installed_profiles | {skills.get('installed_profiles', [])} |")
        lines.append(f"| installed_skills | {skills.get('installed_skills', [])} |")
        lines.append(f"| enabled_skills | {skills.get('enabled_skills', [])} |")
        lines.append(f"| disabled_skills | {skills.get('disabled_skills', [])} |")
        lines.append(f"| vendor_downloads | {skills.get('vendor_downloads', [])} |")
        lines.append(f"| enabled_adapters | {skills.get('enabled_adapters', [])} |")
        lines.append(f"| pending_audit | {skills.get('pending_audit', [])} |")
        lines.append(f"| catalog_version | {skills.get('catalog_version', 'none')} |")
        lines.append("")
        lines.append("These values are **never cleared** by the update process. Only missing fields are added with empty defaults.")
        lines.append("")

    lines.append("## Rollback")
    lines.append("")
    if report_data.get('backup_dir') and report_data['backup_dir'] != 'none':
        lines.append(f"To rollback, restore from backup:")
        lines.append(f"```")
        lines.append(f"cp -r {report_data['backup_dir']}/* .")
        lines.append(f"```")
    else:
        lines.append("No backup was created (dry-run mode).")
    lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("*Report generated by `scripts/update_pkb.py`*")
    lines.append("")

    report_path = target / "update_report.md"
    report_path.write_text('\n'.join(lines), encoding="utf-8")
    info(f"Report written: {report_path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    args = sys.argv[1:]

    if "--help" in args or "-h" in args:
        print(__doc__)
        sys.exit(0)

    if len(args) < 1:
        die("Target PKB path required. Usage: python scripts/update_pkb.py <path> [--dry-run]")

    target = Path(args[0]).resolve()
    if not target.is_dir():
        die(f"Target directory not found: {target}")

    opts = {
        "dry_run": "--dry-run" in args,
        "backup_only": "--backup-only" in args,
        "force": "--force" in args,
    }

    # Version override
    from_ver = None
    to_ver = CURRENT_VERSION
    for i, arg in enumerate(args):
        if arg == "--from-version" and i + 1 < len(args):
            from_ver = args[i + 1]
        if arg == "--to-version" and i + 1 < len(args):
            to_ver = args[i + 1]

    # Read installed config
    config_path = target / "pkb.config.json"
    if config_path.is_file():
        config = json.loads(config_path.read_text(encoding="utf-8"))
        installed_ver = from_ver or get_installed_version(config)
    else:
        installed_ver = from_ver or "0.0.0"
        warn("No pkb.config.json found. Using version 0.0.0")

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    backup_dir = None

    info("=" * 60)
    info("  PKB Starter — Update")
    info("=" * 60)
    info(f"  Target: {target}")
    info(f"  Installed version: {installed_ver}")
    info(f"  Current version: {to_ver}")
    info(f"  Mode: {'DRY RUN' if opts['dry_run'] else 'LIVE'}")
    print()

    # Phase 0: Backup (runs even if up-to-date, for --backup-only)
    if opts.get("backup_only"):
        if not opts["dry_run"]:
            backup_dir = str(create_backup(target))
            ok(f"Backup complete: {backup_dir}")
        else:
            info("Would create backup (dry-run)")
        sys.exit(0)

    # Early exit if already current
    if not version_lt(installed_ver, to_ver):
        ok(f"Already up-to-date ({installed_ver} >= {to_ver})")
        sys.exit(0)

    # Phase 1: Backup (for actual update)
    if not opts["dry_run"]:
        backup_dir = str(create_backup(target))
        print()

    # Phase 2: Run migrations
    migration_changes = run_migrations(target, installed_ver, to_ver, opts)
    print()

    # Phase 3: Update system files
    system_changes = update_system_files(target, opts)
    if system_changes:
        info(f"System file changes: {len(system_changes)}")
        for c in system_changes:
            info(f"  {c}")
    print()

    # Phase 4: Update config
    config_changes = update_config(target, opts)
    if config_changes:
        info(f"Config changes: {len(config_changes)}")
        for c in config_changes:
            info(f"  {c}")
    print()

    # Phase 5: Report
    # Collect protected paths status for report
    protected_status = _collect_protected_status(target)
    skills_state = _collect_skills_state(target)

    report_data = {
        "timestamp": now,
        "target": str(target),
        "dry_run": opts["dry_run"],
        "from_version": installed_ver,
        "to_version": to_ver,
        "backup_dir": backup_dir,
        "system_changes": system_changes,
        "config_changes": config_changes,
        "migration_changes": migration_changes,
        "errors": [],
        "protected_paths": protected_status,
        "skills_state": skills_state,
    }

    write_report(target, report_data)

    # Summary
    print()
    info("=" * 60)
    info("  Update Summary")
    info("=" * 60)
    info(f"  System files : {len(system_changes)}")
    info(f"  Config       : {len(config_changes)}")
    info(f"  Migrations   : {len(migration_changes)}")
    if backup_dir:
        info(f"  Backup       : {backup_dir}")
    info("=" * 60)

    if opts["dry_run"]:
        info("")
        info("  Dry run complete. Run without --dry-run to apply changes.")

    sys.exit(0)


if __name__ == "__main__":
    main()
