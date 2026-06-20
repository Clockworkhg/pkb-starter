#!/usr/bin/env python3
"""
PKB Starter -- Optional Skill Installer (v0.4.0)

Installs third-party Claude Code skills from the PKB skill catalog (42 entries)
into a target PKB directory. Skills are cloned into skills/_vendor/ and mapped
to PKB's raw/wiki structure via adapters.

Usage:
    python scripts/install_skills.py --list
    python scripts/install_skills.py --target "D:\\MyKB" --profile student
    python scripts/install_skills.py --target "D:\\MyKB" --profile full --dry-run
    python scripts/install_skills.py --target "D:\\MyKB" --profile custom --enable-risky
    python scripts/install_skills.py --target "D:\\MyKB" --audit-only

Safety:
    - No third-party code is auto-executed (git clone only).
    - High-risk skills require explicit --enable-risky.
    - Reference-only skills are never installed.
    - Plugin marketplace skills are listed with manual install instructions.
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

# -- Constants --------------------------------------------------------

REGISTRY_DIR = Path(__file__).resolve().parent.parent / "skills_registry"
CATALOG_PATH = REGISTRY_DIR / "skill_catalog.json"
PROFILES_PATH = REGISTRY_DIR / "profiles.json"
ADAPTERS_SRC = Path(__file__).resolve().parent.parent / "template" / "skill_adapters"

VENDOR_DIR_NAME = "skills"
VENDOR_SUBDIR = "_vendor"

PROFILE_CHOICES = ["core", "student", "research", "developer", "creator", "output", "security", "full", "custom"]


# -- JSON Helpers -----------------------------------------------------

def load_json(path: Path) -> dict:
    """Load a JSON file. Exit with message on failure."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"[FAIL] Cannot load {path}: {e}")
        sys.exit(1)


# -- Catalog Listing --------------------------------------------------

def list_catalog(catalog: dict):
    """Print the full skill catalog with metadata."""
    skills = catalog.get("skills", [])
    stats = catalog.get("stats", {})

    print()
    print("=" * 70)
    print("  PKB Skill Catalog -- {} entries".format(len(skills)))
    print("=" * 70)
    print()
    print("  Stats: {} external repos, {} self-built, {} MCP, {} reference-only".format(
        stats.get("external_repos", "?"),
        stats.get("self_built_skills", "?"),
        stats.get("mcp_servers", "?"),
        stats.get("reference_only", "?"),
    ))
    print()

    # Group by category
    categories = {}
    for s in skills:
        cat = s.get("category", "other")
        categories.setdefault(cat, []).append(s)

    cat_names = {
        "knowledge_capture": "Knowledge Capture",
        "academic_research": "Academic Research",
        "document_processing": "Document Processing",
        "knowledge_management": "Knowledge Management",
        "security_privacy": "Security & Privacy",
        "creation_output": "Creation & Output",
        "meta_tooling": "Meta Tooling",
        "development": "Development",
        "reference": "Reference Only",
    }

    for cat_key in sorted(categories.keys()):
        cat_label = cat_names.get(cat_key, cat_key.replace("_", " ").title())
        print("  -- {} --".format(cat_label))
        print()
        for s in sorted(categories[cat_key], key=lambda x: x["id"]):
            risk = s.get("risk_level", "?").upper()
            src = s.get("source_type", "?").replace("_", " ")
            mcp = " [MCP]" if s.get("requires_mcp") else ""
            api = " [API]" if s.get("requires_api_key") else ""
            lic = s.get("license_status", "?")
            sub = " ({} sub-skills)".format(len(s.get("sub_skills", []))) if s.get("sub_skills") else ""
            rec = " [RECOMMENDED]" if s.get("recommended") else ""
            default = " [DEFAULT]" if s.get("default_enabled") else ""

            print("  {:<35s} [{:<5s}] {:<15s} {}{}{}{}{}".format(
                s["id"], risk, src, lic, mcp, api, rec, default
            ))
            print("    {}".format(s.get("description", "")[:120]))
            if sub:
                print("    Sub-skills: {}".format(", ".join(s.get("sub_skills", []))))
            print()

    print("=" * 70)
    print()
    print("  Risk legend:")
    print("    LOW      = auto-install, no warnings")
    print("    MEDIUM   = install with dependency/token warnings")
    print("    HIGH     = requires --enable-risky flag")
    print("    REFERENCE_ONLY = never installed (license/proprietary)")
    print()
    print("  Source types:")
    print("    built_in          = PKB core template (always present)")
    print("    local_template    = PKB self-built (bundled)")
    print("    external_repo     = third-party git clone")
    print("    plugin_marketplace = Claude Code plugin marketplace")
    print("    mcp_server        = MCP server config")
    print("    reference_only    = design reference, never installed")
    print()
    print("  Use --profile <name> to install a preset group.")
    print("  Profiles: {}".format(", ".join(PROFILE_CHOICES)))
    print()


def list_profiles(profiles: dict):
    """Print all profiles with their skill selections."""
    print()
    print("=" * 70)
    print("  PKB Skill Profiles")
    print("=" * 70)
    print()

    for pid, pdef in profiles.get("profiles", {}).items():
        skills = pdef.get("skills", [])
        desc = pdef.get("description", "")
        default_for = pdef.get("default_for", "")
        interactive = pdef.get("interactive", False)

        tag = " [INTERACTIVE]" if interactive else ""
        print("  {:<12s} {} skill(s){} — for {}".format(
            pid, len(skills), tag, default_for
        ))
        print("    {}".format(desc))
        if skills:
            print("    Skills: {}".format(", ".join(skills)))
        built_in = pdef.get("built_in_included", [])
        if built_in:
            print("    Built-in: {}".format(", ".join(built_in)))
        note = pdef.get("note", "")
        if note:
            print("    Note: {}".format(note))
        print()

    print("=" * 70)


# -- Skill Resolution -------------------------------------------------

def resolve_skills(profile: str, catalog: dict, profiles: dict) -> tuple:
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
        entry = catalog_map[sid]
        if entry.get("install_method") == "reference_only":
            warnings.append(f"Skill '{sid}' is reference-only -- skipped (never installable)")
            continue
        entries.append(entry)

    return entries, warnings


def _interactive_select(catalog: dict) -> list[str]:
    """Interactive skill selection for custom profile. Returns list of skill IDs."""
    print()
    print("=" * 60)
    print("  Custom Profile -- Select Skills")
    print("=" * 60)
    print()
    print("  Enter skill IDs separated by spaces, or 'all' for all installable skills.")
    print("  Reference-only and plugin_marketplace skills cannot be auto-installed.")
    print("  Use 'list' to see the full catalog first.")
    print()

    installable = [
        s for s in catalog["skills"]
        if s["install_method"] not in ("reference_only", "plugin_marketplace")
    ]
    for i, skill in enumerate(installable, 1):
        risk_tag = f"[{skill['risk_level'].upper()}]"
        sub_n = len(skill.get("sub_skills", []))
        sub_tag = f" ({sub_n} sub-skills)" if sub_n else ""
        mcp_tag = " [MCP]" if skill.get("requires_mcp") else ""
        api_tag = " [API]" if skill.get("requires_api_key") else ""
        print(f"  {i:2d}. {skill['id']:<32s} {risk_tag:<12s} {skill['category']}{sub_tag}{mcp_tag}{api_tag}")

    print()
    print("  Plugin marketplace (manual install only):")
    for skill in catalog["skills"]:
        if skill["install_method"] == "plugin_marketplace":
            print(f"       {skill['id']} — {skill.get('repo_url', '?')}")

    print()
    print("  Reference-only (never installable):")
    for skill in catalog["skills"]:
        if skill["install_method"] == "reference_only":
            print(f"       {skill['id']} — {skill.get('notes', '')[:100]}")

    print()
    choice = input("  Enter skill IDs (space-separated, or 'all'): ").strip()

    if choice.lower() == "list":
        list_catalog(catalog)
        choice = input("  Enter skill IDs (space-separated, or 'all'): ").strip()

    if choice.lower() == "all":
        return [s["id"] for s in installable if s.get("risk_level") != "high"]

    selected = choice.split()
    valid_ids = {s["id"] for s in installable}
    return [s for s in selected if s in valid_ids]


def filter_by_risk(entries: list[dict], enable_risky: bool) -> tuple:
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


# -- Installation Operations ------------------------------------------

def install_skill(entry: dict, target: Path, dry_run: bool = False) -> dict:
    """
    Install a skill based on its install_method.
    Returns installation result dict.
    """
    method = entry.get("install_method", "git_clone")
    skill_id = entry["id"]
    repo_url = entry.get("repo_url")

    if method == "plugin_marketplace":
        return {
            "id": skill_id,
            "status": "skipped",
            "vendor_path": "N/A (plugin marketplace)",
            "action": "manual_plugin_install",
            "reason": "Install via Claude Code plugin marketplace: /plugin marketplace add <repo>",
        }

    if method == "mcp_config":
        return {
            "id": skill_id,
            "status": "skipped",
            "vendor_path": "N/A (MCP server)",
            "action": "manual_mcp_config",
            "reason": "Configure in .claude/mcp.json. Requires external runtime.",
        }

    if method == "reference_only":
        return {
            "id": skill_id,
            "status": "skipped",
            "vendor_path": "N/A (reference only)",
            "action": "none",
            "reason": "Reference-only. Never installed.",
        }

    # template_bundled / built_in: these are already part of the PKB template.
    # They were copied by install.py — no git clone needed. Report as "built-in, available".
    if method in ("template_bundled", "built_in"):
        return {
            "id": skill_id,
            "status": "skipped",
            "vendor_path": "N/A (built into PKB template)",
            "action": "built_in_available",
            "reason": f"Built into PKB template — already available, no separate install needed",
        }

    if not repo_url:
        return {
            "id": skill_id,
            "status": "failed",
            "vendor_path": "",
            "action": "none",
            "error": "No repo_url in catalog entry",
        }

    # Standard git_clone or git_clone_selective
    vendor_dir = target / VENDOR_DIR_NAME / VENDOR_SUBDIR / skill_id

    result = {
        "id": skill_id,
        "status": "pending",
        "vendor_path": str(vendor_dir.relative_to(target)),
        "action": method,
    }

    if dry_run:
        result["status"] = "would_install"
        return result

    # Create vendor directory
    vendor_dir.parent.mkdir(parents=True, exist_ok=True)

    # Remove existing if present (re-install)
    if vendor_dir.exists():
        shutil.rmtree(vendor_dir, ignore_errors=True)

    # Git clone
    try:
        proc = subprocess.run(
            ["git", "clone", "--depth", "1", "--quiet", repo_url, str(vendor_dir)],
            capture_output=True, text=True, timeout=180,
            encoding="utf-8", errors="replace",
        )
        if proc.returncode == 0:
            result["status"] = "installed"
        else:
            result["status"] = "failed"
            result["error"] = proc.stderr.strip()[:500]
    except subprocess.TimeoutExpired:
        result["status"] = "failed"
        result["error"] = "Clone timed out (180s)"
    except FileNotFoundError:
        result["status"] = "failed"
        result["error"] = "git not found in PATH"
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
    repo_url = entry.get("repo_url", "N/A")
    method = entry.get("install_method", "git_clone")

    content = f"""# {entry['name']} -- Install Note

> Installed by PKB Starter install_skills.py v0.4.0 on {today}

## Source

- Repository: {repo_url}
- Category: {entry.get('category', 'unknown')}
- Risk Level: {entry.get('risk_level', 'unknown')}
- Install Method: {method}
- License: {entry.get('license_status', 'unknown')}

## Integration

This skill is installed into `skills/_vendor/{skill_id}/`.

PKB maps its output via the adapter: `templates/skill_adapters/{entry.get('adapter', 'none')}`

## Sub-Skills

{chr(10).join('- ' + s for s in entry.get('sub_skills', [])) if entry.get('sub_skills') else 'None (single skill)'}

## Safety Notes

- This is third-party code. Review its LICENSE before use.
- PKB Starter does not auto-execute any skill scripts.
- PKB Starter does not read or configure API keys for this skill.
- If this skill requires MCP, you must configure `.claude/mcp.json` manually.
- To remove: delete `skills/_vendor/{skill_id}/` and remove from SKILL_LINKS.md.

## Adapter Routing

{entry.get('notes', 'No adapter notes.')}

---
*Generated by PKB Starter install_skills.py v0.4.0*
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


# -- Config File Updates ----------------------------------------------

def update_pkb_config(target: Path, profile: str, installed: list):
    """Update pkb.config.json with selected profile and installed skills."""
    config_path = target / "pkb.config.json"

    if not config_path.is_file():
        # Create default config if missing
        config = {"version": "0.3.0", "created": datetime.now(timezone.utc).isoformat()}
    else:
        config = load_json(config_path)

    config["skill_profile"] = profile
    config["installed_skills"] = [
        {"id": s["id"], "installed_at": datetime.now(timezone.utc).isoformat()}
        for s in installed if s["status"] in ("installed", "would_install")
    ]
    config["skill_registry_version"] = "0.3.0"
    config_path.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")


# Module-level variable to pass profile context
_last_profile = "core"


def update_skill_links(target: Path, entries: list, results: list, dry_run: bool = False):
    """Update or create SKILL_LINKS.md with installed skill entries."""
    links_path = target / "SKILL_LINKS.md"

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    installed = [r for r in results if r["status"] in ("installed", "would_install")]
    skipped = [r for r in results if r["status"] == "skipped"]
    failed = [r for r in results if r["status"] == "failed"]

    lines = [
        "# SKILL_LINKS.md -- Installed Skill Index",
        "",
        f"> Auto-generated by PKB Starter install_skills.py v0.4.0 on {today}.",
        f"> Profile: {_last_profile}",
        "",
        "## Installed Skills",
        "",
    ]

    for entry in entries:
        vendor_path = f"skills/_vendor/{entry['id']}/"
        adapter = entry.get("adapter", "none")
        method = entry.get("install_method", "git_clone")

        lines.append(f"### {entry['name']}")
        lines.append(f"- ID: `{entry['id']}`")
        lines.append(f"- Category: {entry.get('category', 'unknown')}")
        if entry.get("repo_url"):
            lines.append(f"- Repository: {entry['repo_url']}")
        lines.append(f"- Install method: {method}")
        if method in ("git_clone", "git_clone_selective"):
            lines.append(f"- Vendor path: `{vendor_path}`")
        lines.append(f"- Adapter: `templates/skill_adapters/{adapter}`" if adapter else "- Adapter: none")
        lines.append(f"- Risk level: {entry.get('risk_level', 'unknown')}")
        lines.append(f"- Requires MCP: {'Yes' if entry.get('requires_mcp') else 'No'}")
        lines.append(f"- License: {entry.get('license_status', 'unknown')}")
        sub = entry.get("sub_skills", [])
        if sub:
            lines.append(f"- Sub-skills ({len(sub)}): {', '.join(sub)}")
        lines.append(f"- Notes: {entry.get('notes', '')}")
        lines.append("")

    if skipped:
        lines.append("## Skipped / Manual Install Required")
        lines.append("")
        for r in skipped:
            lines.append(f"- **{r['id']}**: {r.get('reason', 'skipped')}")
        lines.append("")

    if failed:
        lines.append("## Failed Installs")
        lines.append("")
        for r in failed:
            lines.append(f"- **{r['id']}**: {r.get('error', 'unknown error')[:200]}")
        lines.append("")

    lines.append("---")
    lines.append("*Generated by PKB Starter v0.4.0*")
    lines.append("")

    if not dry_run:
        links_path.write_text("\n".join(lines), encoding="utf-8")


# -- Audit ------------------------------------------------------------

def audit_skills(target: Path, catalog: dict):
    """Audit installed skills against the catalog. Print report."""
    vendor_dir = target / VENDOR_DIR_NAME / VENDOR_SUBDIR
    catalog_map = {s["id"]: s for s in catalog["skills"]}

    print()
    print("=" * 70)
    print("  PKB Skill Audit")
    print("=" * 70)

    if not vendor_dir.is_dir():
        print("  No skills installed.")
        print(f"  Vendor directory not found: {vendor_dir}")
        print()
        print("  Run: python scripts/install_skills.py --target . --profile student")
        return

    installed_dirs = [d for d in vendor_dir.iterdir() if d.is_dir()]
    if not installed_dirs:
        print("  No skills installed (vendor directory is empty).")
        print()
        print("  Run: python scripts/install_skills.py --target . --profile student")
        return

    print(f"  Found {len(installed_dirs)} installed skill(s):")
    print()

    known = 0
    unknown = 0
    for d in sorted(installed_dirs):
        skill_id = d.name
        catalog_entry = catalog_map.get(skill_id)

        if catalog_entry:
            known += 1
            risk = catalog_entry.get("risk_level", "unknown")
            lic = catalog_entry.get("license_status", "?")
            print(f"  [{risk.upper():<16s}] {skill_id}")
            print(f"                      {catalog_entry.get('name', '?')}")
            print(f"                      {catalog_entry.get('repo_url', '?')}")
            print(f"                      License: {lic}")
        else:
            unknown += 1
            print(f"  [UNKNOWN             ] {skill_id}")
            print(f"                      Not in catalog -- may have been manually installed.")

        # Check for INSTALL_NOTE.md
        note = d / "INSTALL_NOTE.md"
        if note.is_file():
            print(f"                      INSTALL_NOTE.md: present")
        else:
            print(f"                      INSTALL_NOTE.md: MISSING")

        # Check for .git
        git_dir = d / ".git"
        if git_dir.is_dir():
            print(f"                      .git: present (clone verified)")
        else:
            print(f"                      .git: MISSING (may be copy, not clone)")
        print()

    print("=" * 70)
    print(f"  Summary: {known} known, {unknown} unknown, {known + unknown} total")
    print(f"  Catalog version: {catalog.get('version', '?')}")
    print("=" * 70)


# -- Display Helpers --------------------------------------------------

def print_install_plan(entries: list, to_install: list, skipped: list,
                       profile: str, enable_risky: bool, dry_run: bool):
    """Print what will be installed before proceeding — categorized."""
    action = "[DRY RUN] Would install" if dry_run else "Will install"

    print()
    print("=" * 70)
    print(f"  PKB Skill Installer v0.4.0 -- Profile: {profile}")
    print("=" * 70)
    print()

    if not entries:
        print("  No skills selected for this profile.")
        print()
        print("  [INFO] PKB will be installed with core tools only.")
        print("         Add skills later with: /project:skills --install <profile>")
        return

    # Categorize to_install entries by install method
    to_clone = [e for e in to_install if e.get("install_method") not in ("template_bundled", "built_in")]
    built_in = [e for e in to_install if e.get("install_method") in ("template_bundled", "built_in")]
    plugin_marketplace = [e for e in to_install if e.get("install_method") == "plugin_marketplace"]
    mcp_config = [e for e in to_install if e.get("install_method") == "mcp_config"]

    # Show what will be git cloned
    if to_clone:
        print(f"  {action} via git clone ({len(to_clone)} skill(s)):")
        for entry in to_clone:
            risk = entry.get("risk_level", "?").upper()
            mcp = " [MCP]" if entry.get("requires_mcp") else ""
            api = " [API]" if entry.get("requires_api_key") else ""
            runtime = " [EXT]" if entry.get("requires_external_runtime") else ""
            sub_n = len(entry.get("sub_skills", []))
            sub_tag = f" ({sub_n} sub-skills)" if sub_n else ""
            print(f"    [{risk:<5s}] {entry['id']:<32s} {entry.get('category', '')}{sub_tag}{mcp}{api}{runtime}")
        print()

    # Show what's already built-in
    if built_in:
        print(f"  ⚠️  Already Built-In — no install needed ({len(built_in)} skill(s)):")
        for entry in built_in:
            print(f"    [BUILT-IN] {entry['id']:<32s} — part of PKB template, available immediately")
        print()

    # Plugin marketplace
    if plugin_marketplace:
        print(f"  ⚠️  Plugin Marketplace — manual install only ({len(plugin_marketplace)} skill(s)):")
        for entry in plugin_marketplace:
            print(f"    [PLUGIN] {entry['id']:<32s} — /plugin marketplace add <repo>")
        print()

    # MCP config
    if mcp_config:
        print(f"  ⚠️  MCP Configuration — manual setup only ({len(mcp_config)} skill(s)):")
        for entry in mcp_config:
            print(f"    [MCP]   {entry['id']:<32s} — configure .claude/mcp.json")
        print()

    # High-risk skipped (not selected due to --enable-risky)
    if skipped:
        print(f"  ⚠️  Skipped — High Risk or Reference-Only ({len(skipped)} skill(s)):")
        for entry in skipped:
            risk = entry.get("risk_level", "?").upper()
            if risk == "REFERENCE_ONLY":
                reason = "reference-only (not installable)"
            elif risk == "HIGH":
                reason = "high risk (use --enable-risky to install)"
            else:
                reason = "unknown reason"
            print(f"    [{risk:<5s}] {entry['id']:<32s} -- {reason}")
            notes = entry.get("notes", "")
            if notes:
                print(f"             {notes[:120]}")
        print()

    if not enable_risky:
        high_count = sum(1 for e in entries if e.get("risk_level") == "high")
        if high_count > 0:
            print(f"  [INFO] {high_count} high-risk skill(s) in this profile. Use --enable-risky to install them.")
            print(f"         High-risk skills: {', '.join(e['id'] for e in entries if e.get('risk_level') == 'high')}")
            print()

    print("=" * 70)


def print_install_report(results: list, skipped_entries: list, dry_run: bool):
    """Print the final installation report with categorized results."""
    action_label = "[DRY RUN] Would install" if dry_run else "Installed"

    succeeded = [r for r in results if r["status"] in ("installed", "would_install")]
    failed = [r for r in results if r["status"] == "failed"]

    # Categorize skipped results for clearer reporting
    skipped_builtin = [r for r in results if r["status"] == "skipped" and r.get("action") == "built_in_available"]
    skipped_plugin = [r for r in results if r["status"] == "skipped" and r.get("action") == "manual_plugin_install"]
    skipped_mcp = [r for r in results if r["status"] == "skipped" and r.get("action") == "manual_mcp_config"]
    skipped_other = [r for r in results if r["status"] == "skipped"
                     and r.get("action") not in ("built_in_available", "manual_plugin_install", "manual_mcp_config")]
    skipped_high_risk = skipped_entries  # entries not installed due to --enable-risky not set

    print()
    print("=" * 70)
    print(f"  PKB Skill Installation Report")
    print("=" * 70)

    # ✅ Success
    if succeeded:
        print(f"  ✅ {action_label} ({len(succeeded)} skill(s)):")
        for r in succeeded:
            path = r.get("vendor_path", "")
            label = "[DRY]" if r["status"] == "would_install" else "[OK] "
            print(f"     {label} {r['id']}")
            if path and "N/A" not in path:
                print(f"         → {path}")
        print()

    # ⚠️ Skipped — built-in (already available)
    if skipped_builtin:
        print(f"  ⚠️  Built-in / Already Available ({len(skipped_builtin)} skill(s)):")
        for r in skipped_builtin:
            print(f"     [BUILT-IN] {r['id']} — already in PKB template, no separate install needed")
        print()

    # ⚠️ Skipped — plugin marketplace
    if skipped_plugin:
        print(f"  ⚠️  Manual Install Required ({len(skipped_plugin)} skill(s)):")
        for r in skipped_plugin:
            print(f"     [PLUGIN] {r['id']} — install via /plugin marketplace add <repo>")
        print()

    # ⚠️ Skipped — MCP config
    if skipped_mcp:
        print(f"  ⚠️  MCP Configuration Required ({len(skipped_mcp)} skill(s)):")
        for r in skipped_mcp:
            print(f"     [MCP] {r['id']} — configure in .claude/mcp.json manually")
        print()

    # ⚠️ Skipped — high risk
    if skipped_high_risk:
        print(f"  ⚠️  High-Risk Skipped ({len(skipped_high_risk)} skill(s)) — use --enable-risky to install:")
        for entry in skipped_high_risk:
            risk = entry.get("risk_level", "?").upper()
            reason = "reference-only (not installable)" if risk == "REFERENCE_ONLY" else "high risk (--enable-risky not set)"
            print(f"     [SKIP] {entry['id']} — {reason}")
        print()

    # ⚠️ Other skipped
    if skipped_other:
        print(f"  ⚠️  Skipped ({len(skipped_other)} skill(s)):")
        for r in skipped_other:
            print(f"     [SKIP] {r['id']}: {r.get('reason', 'unknown')[:120]}")
        print()

    # ❌ Failed
    if failed:
        print(f"  ❌ Failed ({len(failed)} skill(s)):")
        for r in failed:
            error = r.get('error', 'unknown error')[:150]
            print(f"     [FAIL] {r['id']}: {error}")
        print()

    total_skipped = len(skipped_builtin) + len(skipped_plugin) + len(skipped_mcp) + len(skipped_other) + len(skipped_high_risk)
    print(f"  Summary: {len(succeeded)} succeeded, {len(failed)} failed, {total_skipped} skipped")
    if not dry_run and succeeded:
        print(f"  Skills directory: {VENDOR_DIR_NAME}/{VENDOR_SUBDIR}/")
        print(f"  Review: SKILL_LINKS.md for adapter mappings")
        print(f"  Audit:  python scripts/install_skills.py --target . --audit-only")
    print("=" * 70)

    # JSON report for agent parsing
    report = {
        "profile": _last_profile,
        "dry_run": dry_run,
        "version": "0.3.0",
        "total_selected": len(results) + len(skipped_entries),
        "installed": len(succeeded),
        "failed": len(failed),
        "skipped": total_skipped,
        "results": [
            {"id": r["id"], "status": r["status"], "path": r.get("vendor_path", ""),
             "error": r.get("error", ""), "reason": r.get("reason", "")}
            for r in results
        ],
    }
    print()
    print("--- JSON REPORT ---")
    print(json.dumps(report, indent=2, ensure_ascii=False))


# -- Main -------------------------------------------------------------

def main():
    global _last_profile

    parser = argparse.ArgumentParser(
        description="PKB Starter -- Optional Skill Installer (v0.4.0)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Examples:
              python scripts/install_skills.py --list
              python scripts/install_skills.py --list-profiles
              python scripts/install_skills.py --target "D:\\\\MyKB" --profile student
              python scripts/install_skills.py --target "D:\\\\MyKB" --profile research --dry-run
              python scripts/install_skills.py --target "D:\\\\MyKB" --profile full --enable-risky
              python scripts/install_skills.py --target "D:\\\\MyKB" --profile custom
              python scripts/install_skills.py --target "D:\\\\MyKB" --audit-only
        """),
    )
    parser.add_argument("--target", default=None,
                        help="Path to PKB target directory")
    parser.add_argument("--profile", default="core",
                        choices=PROFILE_CHOICES,
                        help="Skill profile to install (default: core)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be installed without making changes")
    parser.add_argument("--audit-only", action="store_true",
                        help="Audit installed skills only, no installation")
    parser.add_argument("--enable-risky", action="store_true",
                        help="Allow installation of high-risk skills (MCP, external runtime)")
    parser.add_argument("--list", action="store_true",
                        help="List the full skill catalog and exit")
    parser.add_argument("--list-profiles", action="store_true",
                        help="List all profiles and exit")

    args = parser.parse_args()

    # Load catalog and profiles
    catalog = load_json(CATALOG_PATH)
    profiles = load_json(PROFILES_PATH)

    # List-only modes (no --target needed)
    if args.list:
        list_catalog(catalog)
        return

    if args.list_profiles:
        list_profiles(profiles)
        return

    # Operations that need --target
    if not args.target:
        print("[FAIL] --target is required for installation or audit.")
        print("       Use --list or --list-profiles for read-only operations.")
        sys.exit(1)

    target = Path(args.target).resolve()
    if not target.is_dir():
        print(f"[FAIL] Target directory does not exist: {target}")
        print(f"       Run install.py first: python scripts/install.py \"{target}\"")
        sys.exit(1)

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
        method = entry.get("install_method", "git_clone")
        if args.dry_run:
            print(f"  [DRY RUN] Would install: {entry['id']} (method: {method})")
        else:
            print(f"  Installing: {entry['id']} (method: {method})...")

        result = install_skill(entry, target, dry_run=args.dry_run)
        results.append(result)

        if result["status"] in ("installed", "would_install"):
            # Write INSTALL_NOTE.md (only for git_clone methods)
            if method in ("git_clone", "git_clone_selective"):
                write_install_note(entry, target, dry_run=args.dry_run)

            # Copy adapter
            adapter_copied = copy_adapter(entry, target, dry_run=args.dry_run)
            if adapter_copied:
                msg = "    [OK] Adapter: {}".format(entry.get("adapter"))
                if args.dry_run:
                    msg = "    [DRY] Would copy adapter: {}".format(entry.get("adapter"))
                print(msg)

            # Warn about requirements
            if entry.get("requires_mcp"):
                print(f"    [WARN] Requires MCP -- configure .claude/mcp.json manually")
            if entry.get("requires_external_runtime"):
                print(f"    [WARN] Requires external runtime -- install separately")
            if entry.get("requires_api_key"):
                print(f"    [WARN] Requires API key -- configure manually, never store in PKB")

        elif result["status"] == "failed":
            print(f"    [FAIL] {result.get('error', 'unknown error')[:200]}")
        elif result["status"] == "skipped":
            print(f"    [SKIP] {result.get('reason', 'skipped')[:120]}")

    # Update config files
    if not args.dry_run:
        print()
        print("  Updating config files...")
        update_pkb_config(target, args.profile, results)
        print(f"    [OK] pkb.config.json updated")
        update_skill_links(target, entries, results, dry_run=False)
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
        plugin_skills = [e for e in entries if e.get("install_method") == "plugin_marketplace"]
        mcp_skills = [e for e in entries if e.get("requires_mcp")]
        for e in plugin_skills:
            print(f"    - Install {e['id']} via Claude Code plugin marketplace")
        for e in mcp_skills:
            print(f"    - Configure MCP for {e['id']}: add to .claude/mcp.json")
        installed_skills = [r for r in results if r["status"] == "installed"]
        if installed_skills:
            print(f"    - Review adapters in templates/skill_adapters/")
            print(f"    - Restart Claude Code to load new skills")
            print(f"    - Run /project:skills --audit to verify")


if __name__ == "__main__":
    main()
