#!/usr/bin/env python3
"""
PKB Starter -- Optional Skill Installer (v0.2.0)

Installs third-party Claude Code skills from the PKB skill catalog into a
target PKB directory. Skills are cloned into skills/_vendor/ and mapped to
PKB's raw/wiki structure via adapters.

Usage:
    python scripts/install_skills.py --target "D:\\MyKB" --profile student
    python scripts/install_skills.py --target "D:\\MyKB" --profile full --dry-run
    python scripts/install_skills.py --target "D:\\MyKB" --profile custom --enable-risky
    python scripts/install_skills.py --target "D:\\MyKB" --audit-only

Safety:
    - No third-party code is auto-executed (git clone only).
    - High-risk skills require explicit --enable-risky.
    - Reference-only skills are never installed.
    - MCP/external runtime requirements are flagged, not auto-configured.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import textwrap
from datetime import datetime, timezone
from pathlib import Path

# ── Constants ──────────────────────────────────────────────────────

REGISTRY_DIR = Path(__file__).resolve().parent.parent / "skills_registry"
CATALOG_PATH = REGISTRY_DIR / "skill_catalog.json"
PROFILES_PATH = REGISTRY_DIR / "profiles.json"
ADAPTERS_SRC = Path(__file__).resolve().parent.parent / "template" / "skill_adapters"

VENDOR_DIR_NAME = "skills"
VENDOR_SUBDIR = "_vendor"


# ── JSON Helpers ───────────────────────────────────────────────────

def load_json(path: Path) -> dict:
    """Load a JSON file. Exit with message on failure."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"[FAIL] Cannot load {path}: {e}")
        sys.exit(1)


# ── Skill Resolution ───────────────────────────────────────────────

def resolve_skills(profile: str, catalog: dict, profiles: dict) -> tuple[list[dict], list[str]]:
    """
    Resolve a profile to its skill list.
    Returns (skill_entries, warnings).
    """
    if profile not in profiles["profiles"]:
        print(f"[FAIL] Unknown profile: {profile}")
        print(f"       Available: {', '.join(profiles['profiles'].keys())}")
        sys.exit(1)

    profile_def = profiles["profiles"][profile]
    skill_ids = profile_def.get("skills", [])

    if profile == "custom":
        # Custom: all installable skills are candidates, user picks interactively
        skill_ids = _interactive_select(catalog)
        if not skill_ids:
            print("[INFO] No skills selected. Installing core-only PKB.")
            return [], []

    # Map IDs to catalog entries
    catalog_map = {s["id"]: s for s in catalog["skills"]}
    entries = []
    warnings = []

    for sid in skill_ids:
        if sid not in catalog_map:
            warnings.append(f"Skill '{sid}' not found in catalog -- skipped")
            continue
        entries.append(catalog_map[sid])

    return entries, warnings


def _interactive_select(catalog: dict) -> list[str]:
    """Interactive skill selection for custom profile. Returns list of skill IDs."""
    print()
    print("=" * 60)
    print("  Custom Profile -- Select Skills")
    print("=" * 60)
    print()
    print("  Enter skill IDs separated by spaces, or 'all' for all installable skills.")
    print("  Reference-only skills cannot be installed.")
    print()

    installable = [s for s in catalog["skills"] if s["install_method"] != "reference_only"]
    for i, skill in enumerate(installable, 1):
        risk_tag = f"[{skill['risk_level'].upper()}]"
        rec_tag = " [RECOMMENDED]" if skill.get("recommended") else ""
        print(f"  {i:2d}. {skill['id']:<30s} {risk_tag:<12s} {skill['category']}{rec_tag}")

    print()
    print("  Reference-only (not installable):")
    for skill in catalog["skills"]:
        if skill["install_method"] == "reference_only":
            print(f"       {skill['id']} -- {skill['notes']}")

    print()
    choice = input("  Enter skill IDs (space-separated, or 'all'): ").strip()

    if choice.lower() == "all":
        return [s["id"] for s in installable]

    selected = choice.split()
    valid_ids = {s["id"] for s in installable}
    return [s for s in selected if s in valid_ids]


def filter_by_risk(entries: list[dict], enable_risky: bool) -> tuple[list[dict], list[dict]]:
    """
    Filter entries by risk level.
    Returns (to_install, skipped_due_to_risk).
    """
    to_install = []
    skipped = []

    for entry in entries:
        risk = entry.get("risk_level", "medium")

        if risk == "reference_only":
            skipped.append(entry)
        elif risk == "high" and not enable_risky:
            skipped.append(entry)
        else:
            to_install.append(entry)

    return to_install, skipped


# ── Installation Operations ────────────────────────────────────────

def install_skill(entry: dict, target: Path, dry_run: bool = False) -> dict:
    """
    Clone a skill into skills/_vendor/.
    Returns installation result dict.
    """
    skill_id = entry["id"]
    vendor_dir = target / VENDOR_DIR_NAME / VENDOR_SUBDIR / skill_id
    repo_url = entry["repo_url"]

    result = {
        "id": skill_id,
        "status": "pending",
        "vendor_path": str(vendor_dir.relative_to(target)),
        "action": "git_clone",
    }

    if dry_run:
        result["status"] = "would_install"
        return result

    # Create vendor directory
    vendor_dir.parent.mkdir(parents=True, exist_ok=True)

    # Remove existing if present (re-install)
    if vendor_dir.exists():
        shutil.rmtree(vendor_dir)

    # Git clone
    try:
        proc = subprocess.run(
            ["git", "clone", "--depth", "1", "--quiet", repo_url, str(vendor_dir)],
            capture_output=True, text=True, timeout=120,
            encoding="utf-8", errors="replace",
        )
        if proc.returncode == 0:
            result["status"] = "installed"
        else:
            result["status"] = "failed"
            result["error"] = proc.stderr.strip()[:500]
    except subprocess.TimeoutExpired:
        result["status"] = "failed"
        result["error"] = "Clone timed out (120s)"
    except Exception as e:
        result["status"] = "failed"
        result["error"] = str(e)[:500]

    return result


def write_install_note(entry: dict, target: Path, dry_run: bool = False):
    """Write INSTALL_NOTE.md for a skill."""
    skill_id = entry["id"]
    note_dir = target / VENDOR_DIR_NAME / VENDOR_SUBDIR / skill_id
    note_path = note_dir / "INSTALL_NOTE.md"

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    repo_url = entry["repo_url"]

    content = f"""# {entry['name']} -- Install Note

> Installed by PKB Starter install_skills.py on {today}

## Source

- Repository: {repo_url}
- Category: {entry.get('category', 'unknown')}
- Risk Level: {entry.get('risk_level', 'unknown')}

## Integration

This skill is installed into `skills/_vendor/{skill_id}/`.

PKB maps its output via the adapter: `template/skill_adapters/{entry.get('adapter', 'none')}`

## Safety Notes

- This is third-party code. Review its LICENSE before use.
- PKB Starter does not auto-execute any skill scripts.
- PKB Starter does not read or configure API keys for this skill.
- If this skill requires MCP, you must configure `.claude/mcp.json` manually.
- To remove: delete `skills/_vendor/{skill_id}/` and remove from SKILL_LINKS.md.

## Adapter Routing

{entry.get('notes', 'No adapter notes.')}

---
*Generated by PKB Starter install_skills.py v0.2.0*
"""
    if not dry_run:
        note_dir.mkdir(parents=True, exist_ok=True)
        note_path.write_text(content, encoding="utf-8")


def copy_adapter(entry: dict, target: Path, dry_run: bool = False) -> bool:
    """Copy the skill adapter to the target. Returns True if adapter was found and copied."""
    adapter_name = entry.get("adapter")
    if not adapter_name:
        return False

    adapter_src = ADAPTERS_SRC / adapter_name
    if not adapter_src.is_file():
        return False

    adapter_dst_dir = target / "templates" / "skill_adapters"
    adapter_dst = adapter_dst_dir / adapter_name

    if not dry_run:
        adapter_dst_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(adapter_src, adapter_dst)

    return True


# ── Config File Updates ────────────────────────────────────────────

def update_pkb_config(target: Path, profile: str, installed: list[dict]):
    """Update pkb.config.json with selected profile and installed skills."""
    config_path = target / "pkb.config.json"

    if not config_path.is_file():
        return

    config = load_json(config_path)
    config["skill_profile"] = profile
    config["installed_skills"] = [
        {"id": s["id"], "installed_at": datetime.now(timezone.utc).isoformat()}
        for s in installed if s["status"] == "installed" or s["status"] == "would_install"
    ]
    config_path.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")


def update_skill_links(target: Path, entries: list[dict], dry_run: bool = False):
    """Update or create SKILL_LINKS.md with installed skill entries."""
    links_path = target / "SKILL_LINKS.md"

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    lines = [
        "# SKILL_LINKS.md -- Installed Skill Index",
        "",
        f"> Auto-generated by PKB Starter install_skills.py on {today}.",
        f"> Profile: {_last_profile}",
        "",
        "## Installed Skills",
        "",
    ]

    for entry in entries:
        vendor_path = f"skills/_vendor/{entry['id']}/"
        adapter = entry.get("adapter", "none")
        lines.append(f"### {entry['name']}")
        lines.append(f"- ID: `{entry['id']}`")
        lines.append(f"- Category: {entry.get('category', 'unknown')}")
        lines.append(f"- Repository: {entry['repo_url']}")
        lines.append(f"- Vendor path: `{vendor_path}`")
        lines.append(f"- Adapter: `templates/skill_adapters/{adapter}`" if adapter else "- Adapter: none")
        lines.append(f"- Risk level: {entry.get('risk_level', 'unknown')}")
        lines.append(f"- Requires MCP: {'Yes' if entry.get('requires_mcp') else 'No'}")
        lines.append(f"- Notes: {entry.get('notes', '')}")
        lines.append("")

    lines.append("---")
    lines.append("*Generated by PKB Starter v0.2.0*")
    lines.append("")

    if not dry_run:
        links_path.write_text("\n".join(lines), encoding="utf-8")


# Module-level variable to pass profile to update_skill_links
_last_profile = "core"


# ── Audit ──────────────────────────────────────────────────────────

def audit_skills(target: Path, catalog: dict):
    """Audit installed skills against the catalog. Print report."""
    vendor_dir = target / VENDOR_DIR_NAME / VENDOR_SUBDIR
    catalog_map = {s["id"]: s for s in catalog["skills"]}

    print()
    print("=" * 60)
    print("  PKB Skill Audit")
    print("=" * 60)

    if not vendor_dir.is_dir():
        print("  No skills installed.")
        print(f"  Vendor directory not found: {vendor_dir}")
        return

    installed_dirs = [d for d in vendor_dir.iterdir() if d.is_dir()]
    if not installed_dirs:
        print("  No skills installed (vendor directory is empty).")
        return

    print(f"  Found {len(installed_dirs)} installed skill(s):")
    print()

    for d in sorted(installed_dirs):
        skill_id = d.name
        catalog_entry = catalog_map.get(skill_id)

        if catalog_entry:
            risk = catalog_entry.get("risk_level", "unknown")
            print(f"  [{risk.upper():<14s}] {skill_id}")
            print(f"                    {catalog_entry.get('name', '?')}")
            print(f"                    {catalog_entry.get('repo_url', '?')}")
        else:
            print(f"  [UNKNOWN           ] {skill_id}")
            print(f"                    Not in catalog -- may have been manually installed.")

        # Check for INSTALL_NOTE.md
        note = d / "INSTALL_NOTE.md"
        if note.is_file():
            print(f"                    INSTALL_NOTE.md: present")
        else:
            print(f"                    INSTALL_NOTE.md: MISSING")
        print()

    print("=" * 60)


# ── Display Helpers ────────────────────────────────────────────────

def print_install_plan(entries: list[dict], to_install: list[dict], skipped: list[dict],
                       profile: str, enable_risky: bool, dry_run: bool):
    """Print what will be installed before proceeding."""
    action = "[DRY RUN] Would install" if dry_run else "Will install"

    print()
    print("=" * 60)
    print(f"  PKB Skill Installer -- Profile: {profile}")
    print("=" * 60)
    print()

    if not entries:
        print("  No skills selected for this profile.")
        print()
        print("  [INFO] PKB will be installed with core tools only.")
        print("         Add skills later with: /project:skills --install <profile>")
        return

    if to_install:
        print(f"  {action} ({len(to_install)} skill(s)):")
        for entry in to_install:
            risk = entry.get("risk_level", "?").upper()
            rec = " [RECOMMENDED]" if entry.get("recommended") else ""
            mcp = " [MCP]" if entry.get("requires_mcp") else ""
            print(f"    [{risk:<5s}] {entry['id']:<30s} {entry.get('category', '')}{rec}{mcp}")
        print()

    if skipped:
        print(f"  Skipped ({len(skipped)} skill(s)):")
        for entry in skipped:
            risk = entry.get("risk_level", "?").upper()
            reason = "reference-only" if risk == "REFERENCE_ONLY" else "high risk (use --enable-risky)"
            print(f"    [{risk:<5s}] {entry['id']:<30s} -- {reason}")
            if entry.get("notes"):
                print(f"             {entry['notes']}")
        print()

    if not enable_risky:
        high_count = sum(1 for e in entries if e.get("risk_level") == "high")
        if high_count > 0:
            print(f"  [INFO] {high_count} high-risk skill(s) skipped. Use --enable-risky to install.")
            print()

    print("=" * 60)


def print_install_report(results: list[dict], skipped: list[dict], dry_run: bool):
    """Print the final installation report."""
    print()
    print("=" * 60)
    print(f"  PKB Skill Installation Report")
    print("=" * 60)

    succeeded = [r for r in results if r["status"] in ("installed", "would_install")]
    failed = [r for r in results if r["status"] == "failed"]

    for r in results:
        if r["status"] == "installed":
            print(f"  [OK]    {r['id']} -> {r['vendor_path']}")
        elif r["status"] == "would_install":
            print(f"  [DRY]   {r['id']} -> {r['vendor_path']}")
        elif r["status"] == "failed":
            print(f"  [FAIL]  {r['id']}: {r.get('error', 'unknown error')[:100]}")
        elif r["status"] == "skipped":
            reason = r.get("reason", "unknown")
            print(f"  [SKIP]  {r['id']}: {reason}")

    for entry in skipped:
        risk = entry.get("risk_level", "?").upper()
        if risk == "REFERENCE_ONLY":
            print(f"  [SKIP]  {entry['id']}: reference-only (not installable)")
        else:
            print(f"  [SKIP]  {entry['id']}: high risk (--enable-risky not set)")

    print()
    print(f"  Summary: {len(succeeded)} installed, {len(failed)} failed, {len(skipped)} skipped")
    if not dry_run and succeeded:
        print(f"  Skills directory: {VENDOR_DIR_NAME}/{VENDOR_SUBDIR}/")
        print(f"  Review: SKILL_LINKS.md for adapter mappings")
        print(f"  Audit:  python scripts/install_skills.py --target . --audit-only")
    print("=" * 60)

    # JSON report for agent parsing
    report = {
        "profile": _last_profile,
        "dry_run": dry_run,
        "total_selected": len(results) + len(skipped),
        "installed": len(succeeded),
        "failed": len(failed),
        "skipped": len(skipped),
        "results": [
            {"id": r["id"], "status": r["status"], "path": r.get("vendor_path", "")}
            for r in results
        ],
    }
    print()
    print("--- JSON REPORT ---")
    print(json.dumps(report, indent=2, ensure_ascii=False))


# ── Main ───────────────────────────────────────────────────────────

def main():
    global _last_profile

    parser = argparse.ArgumentParser(
        description="PKB Starter -- Optional Skill Installer (v0.2.0)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Examples:
              python scripts/install_skills.py --target "D:\\\\MyKB" --profile student
              python scripts/install_skills.py --target "D:\\\\MyKB" --profile full --dry-run
              python scripts/install_skills.py --target "D:\\\\MyKB" --profile custom --enable-risky
              python scripts/install_skills.py --target "D:\\\\MyKB" --audit-only
        """),
    )
    parser.add_argument("--target", required=True,
                        help="Path to PKB target directory")
    parser.add_argument("--profile", default="core",
                        choices=["core", "student", "research", "developer", "creator", "full", "custom"],
                        help="Skill profile to install (default: core)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be installed without making changes")
    parser.add_argument("--audit-only", action="store_true",
                        help="Audit installed skills only, no installation")
    parser.add_argument("--enable-risky", action="store_true",
                        help="Allow installation of high-risk skills (MCP, external runtime)")

    args = parser.parse_args()

    target = Path(args.target).resolve()
    if not target.is_dir():
        print(f"[FAIL] Target directory does not exist: {target}")
        print(f"       Run install.py first: python scripts/install.py \"{target}\"")
        sys.exit(1)

    # Load catalog and profiles
    catalog = load_json(CATALOG_PATH)
    profiles = load_json(PROFILES_PATH)

    # Audit-only mode
    if args.audit_only:
        audit_skills(target, catalog)
        return

    # Resolve skills from profile
    _last_profile = args.profile
    entries, warnings = resolve_skills(args.profile, catalog, profiles)

    for w in warnings:
        print(f"[WARN] {w}")

    # Filter by risk
    to_install, skipped = filter_by_risk(entries, args.enable_risky)

    # Display plan
    print_install_plan(entries, to_install, skipped, args.profile, args.enable_risky, args.dry_run)

    if not to_install and not skipped:
        # Core profile or empty custom: still update config
        if not args.dry_run:
            update_pkb_config(target, args.profile, [])
        print("[INFO] PKB core installed. No additional skills selected.")
        return

    # Install each skill
    results = []
    for entry in to_install:
        print(f"  Installing: {entry['id']}..." if not args.dry_run else f"  [DRY RUN] Would install: {entry['id']}")

        result = install_skill(entry, target, dry_run=args.dry_run)
        results.append(result)

        if result["status"] in ("installed", "would_install"):
            # Write INSTALL_NOTE.md
            write_install_note(entry, target, dry_run=args.dry_run)

            # Copy adapter
            adapter_copied = copy_adapter(entry, target, dry_run=args.dry_run)
            if adapter_copied:
                print(f"    [OK] Adapter: {entry.get('adapter')}" if not args.dry_run else
                      f"    [DRY] Would copy adapter: {entry.get('adapter')}")

            # Warn about requirements
            if entry.get("requires_mcp"):
                print(f"    [WARN] Requires MCP -- configure .claude/mcp.json manually")
            if entry.get("requires_external_runtime"):
                print(f"    [WARN] Requires external runtime -- install separately")

        elif result["status"] == "failed":
            print(f"    [FAIL] {result.get('error', 'unknown error')[:200]}")

    # Update config files
    if not args.dry_run:
        print()
        print("  Updating config files...")
        update_pkb_config(target, args.profile, results)
        print(f"    [OK] pkb.config.json updated")
        update_skill_links(target, entries, dry_run=False)
        print(f"    [OK] SKILL_LINKS.md updated")
    else:
        print()
        print("  [DRY RUN] Would update: pkb.config.json, SKILL_LINKS.md")

    # Print report
    print_install_report(results, skipped, args.dry_run)

    # Final reminders
    if not args.dry_run:
        print()
        print("  Next steps:")
        for entry in entries:
            if entry.get("requires_mcp"):
                print(f"    - Configure MCP for {entry['id']}: add to .claude/mcp.json")
        print(f"    - Review adapters in templates/skill_adapters/")
        print(f"    - Restart Claude Code to load new skills")
        print(f"    - Run /project:skills --audit to verify")


if __name__ == "__main__":
    main()
