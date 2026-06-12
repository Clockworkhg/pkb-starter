#!/usr/bin/env python3
"""
PKB Starter -- Runtime Skill Manager (v0.4.0)

Manages optional skills in a live PKB installation. Supports listing, describing,
installing, auditing, enabling, disabling, and updating skills. All third-party
skills are downloaded to skills/_vendor/ and never auto-executed.

Usage:
    python skill_manager.py --target "D:\\MyKB" --list
    python skill_manager.py --target "D:\\MyKB" --describe deep-research-skills
    python skill_manager.py --target "D:\\MyKB" --install deep-research-skills
    python skill_manager.py --target "D:\\MyKB" --install-profile student
    python skill_manager.py --target "D:\\MyKB" --audit
    python skill_manager.py --target "D:\\MyKB" --enabled
    python skill_manager.py --target "D:\\MyKB" --enable <skill-id>
    python skill_manager.py --target "D:\\MyKB" --disable <skill-id>
    python skill_manager.py --target "D:\\MyKB" --update-catalog

Safety:
    - No third-party code is auto-executed (git clone only).
    - High-risk skills require explicit user confirmation.
    - Reference-only skills are never installed.
    - Plugin marketplace skills show manual install instructions.
    - MCP is never auto-configured.
    - API keys are never read, stored, or configured.
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


# -- Path resolution --------------------------------------------------------

STARTER_DIR = Path(__file__).resolve().parent.parent
CATALOG_PATH = STARTER_DIR / "skills_registry" / "skill_catalog.json"
PROFILES_PATH = STARTER_DIR / "skills_registry" / "profiles.json"
ADAPTERS_SRC = STARTER_DIR / "template" / "skill_adapters"

VENDOR_DIR_REL = "skills/_vendor"
ADAPTER_DIR_REL = "templates/skill_adapters"

ALLOWED_PROFILES = ["core", "student", "research", "developer", "creator", "output", "security", "full", "custom"]

CATEGORY_LABELS = {
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

RISK_SYMBOLS = {
    "low": "[LOW]",
    "medium": "[MEDIUM]",
    "high": "[HIGH]",
    "reference_only": "[REF]",
}


# -- JSON Helpers ------------------------------------------------------------

def load_json(path: Path) -> dict:
    """Load a JSON file. Exit with message on failure."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"[FAIL] Cannot load {path}: {e}")
        sys.exit(1)


def load_pkb_config(target: Path) -> dict:
    """Load pkb.config.json, creating default if missing."""
    config_path = target / "pkb.config.json"
    if not config_path.is_file():
        return {
            "version": "0.1.0",
            "skills": {
                "catalog_version": "0.4.0",
                "installed_profiles": [],
                "installed_skills": [],
                "enabled_skills": [],
                "disabled_skills": [],
                "vendor_downloads": [],
                "enabled_adapters": [],
                "pending_audit": [],
            }
        }
    config = load_json(config_path)
    if "skills" not in config:
        config["skills"] = {
            "catalog_version": "0.4.0",
            "installed_profiles": [],
            "installed_skills": [],
            "enabled_skills": [],
            "disabled_skills": [],
            "vendor_downloads": [],
            "enabled_adapters": [],
            "pending_audit": [],
        }
    return config


def save_pkb_config(target: Path, config: dict):
    """Save pkb.config.json."""
    config_path = target / "pkb.config.json"
    config_path.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")


# -- Display Helpers ---------------------------------------------------------

def print_header(title: str):
    print()
    print("=" * 72)
    print(f"  {title}")
    print("=" * 72)
    print()


def print_separator():
    print("-" * 72)


# -- Status / Overview -------------------------------------------------------

def cmd_status(target: Path, catalog: dict, profiles: dict, pkb_config: dict):
    """Show installed skills, available profiles, and enabled status."""
    skills_state = pkb_config.get("skills", {})
    catalog_map = {s["id"]: s for s in catalog["skills"]}

    print_header("PKB Skill Manager -- Status")

    # Installed profiles
    installed_profiles = skills_state.get("installed_profiles", [])
    print(f"  Installed profiles: {', '.join(installed_profiles) if installed_profiles else 'None (core only)'}")

    # Installed skills (from skills/_vendor/)
    vendor_dir = target / VENDOR_DIR_REL
    installed_ids = []
    if vendor_dir.is_dir():
        installed_ids = [d.name for d in vendor_dir.iterdir() if d.is_dir()]

    enabled_ids = skills_state.get("enabled_skills", [])
    disabled_ids = skills_state.get("disabled_skills", [])
    pending_ids = skills_state.get("pending_audit", [])

    print()
    print(f"  Skills in skills/_vendor/: {len(installed_ids)}")
    print()

    if installed_ids:
        print(f"  {'Skill ID':<35s} {'Risk':<10s} {'Status':<15s} {'Source'}")
        print(f"  {'-'*35} {'-'*10} {'-'*15} {'-'*20}")
        for sid in sorted(installed_ids):
            entry = catalog_map.get(sid, {})
            risk = entry.get("risk_level", "unknown")
            src = entry.get("source_type", "unknown").replace("_", " ")

            if sid in enabled_ids:
                status = "[ENABLED]"
            elif sid in disabled_ids:
                status = "[DISABLED]"
            elif sid in pending_ids:
                status = "[PENDING AUDIT]"
            else:
                status = "[INSTALLED]"

            print(f"  {sid:<35s} {risk:<10s} {status:<15s} {src}")
        print()

    # Available adapters
    adapter_dir = target / ADAPTER_DIR_REL
    if adapter_dir.is_dir():
        adapters = [f.name for f in adapter_dir.iterdir() if f.is_file() and f.suffix == ".md"]
        enabled_adapters = skills_state.get("enabled_adapters", [])
        print(f"  Adapters: {len(adapters)} available, {len(enabled_adapters)} enabled")
        if adapters:
            for a in sorted(adapters):
                tag = " [ENABLED]" if a in enabled_adapters else ""
                print(f"    {a}{tag}")
        print()

    # Available profiles summary
    print(f"  Available profiles (use --install-profile <name>):")
    print()
    for pid in ALLOWED_PROFILES:
        pdef = profiles.get("profiles", {}).get(pid, {})
        count = len(pdef.get("skills", []))
        desc = pdef.get("description", "")
        installed = " [INSTALLED]" if pid in installed_profiles else ""
        print(f"    {pid:<12s} {count:>2d} skills  {desc[:80]}{installed}")
    print()

    print_separator()
    print(f"  Catalog version: {catalog.get('version', '?')}  |  PKB skills config version: {skills_state.get('catalog_version', '?')}")
    print(f"  Run --list to see all 42 catalog entries with descriptions.")
    print(f"  Run --describe <id> to see full details for a skill.")
    print()


# -- List Catalog ------------------------------------------------------------

def cmd_list(catalog: dict, target: Path):
    """List the full skill catalog with descriptions."""
    skills = catalog.get("skills", [])
    pkb_config = load_pkb_config(target)
    installed_ids = set(pkb_config.get("skills", {}).get("installed_skills", []))
    enabled_ids = set(pkb_config.get("skills", {}).get("enabled_skills", []))

    print_header("PKB Skill Catalog -- {} entries (v{})".format(
        len(skills), catalog.get("version", "?")))

    categories = {}
    for s in skills:
        cat = s.get("category", "other")
        categories.setdefault(cat, []).append(s)

    for cat_key in sorted(categories.keys()):
        cat_label = CATEGORY_LABELS.get(cat_key, cat_key.replace("_", " ").title())
        print()
        print(f"  [{cat_label}]")
        print()

        for s in sorted(categories[cat_key], key=lambda x: x["id"]):
            risk = s.get("risk_level", "?").upper()
            src = s.get("source_type", "?").replace("_", " ")
            mcp = " [MCP]" if s.get("requires_mcp") else ""
            api = " [API]" if s.get("requires_api_key") else ""
            installed = " [INSTALLED]" if s["id"] in installed_ids else ""
            enabled = " [ENABLED]" if s["id"] in enabled_ids else ""

            print(f"  {s['id']:<35s} {RISK_SYMBOLS.get(s.get('risk_level'), '[?]'):<8s} {src}{mcp}{api}{installed}{enabled}")
            print(f"    {s.get('short_description', s.get('description', ''))}")
            sub = s.get("sub_skills", [])
            if sub:
                print(f"    Sub-skills ({len(sub)}): {', '.join(sub[:8])}{' ...' if len(sub) > 8 else ''}")
            print()

    print_separator()
    print()
    print("  Risk legend:")
    print("    [LOW]     = auto-install safe, no external dependencies")
    print("    [MEDIUM]  = install with warnings (deps, tokens, or API)")
    print("    [HIGH]    = requires confirmation (MCP, external runtime, login)")
    print("    [REF]     = reference only, never installable")
    print()
    print("  Use --describe <skill-id> to see full details for any skill.")
    print("  Use --install-profile <profile> to install a preset group.")
    print()


# -- Describe Skill ----------------------------------------------------------

def cmd_describe(catalog: dict, skill_id: str):
    """Show full details for a single skill."""
    catalog_map = {s["id"]: s for s in catalog["skills"]}
    s = catalog_map.get(skill_id)

    if not s:
        print(f"[FAIL] Skill not found: {skill_id}")
        print(f"       Run --list to see all available skills.")
        sys.exit(1)

    print_header(f"Skill: {s['name']} ({s['id']})")

    # Identity
    print(f"  ID:              {s['id']}")
    print(f"  Name:            {s['name']}")
    print(f"  Category:        {CATEGORY_LABELS.get(s.get('category', ''), s.get('category', ''))}")
    print()

    # Description
    print(f"  [What it does]")
    print(f"  {s.get('short_description', 'No description.')}")
    print()
    print(f"  [Details]")
    long_desc = s.get('long_description', s.get('description', ''))
    for line in textwrap.wrap(long_desc, width=68):
        print(f"  {line}")
    print()

    # Best for / Not for
    best = s.get("best_for", [])
    if best:
        print(f"  [Best for]")
        for b in best:
            print(f"    - {b}")
        print()

    not_for = s.get("not_for", [])
    if not_for:
        print(f"  [Not for]")
        for n in not_for:
            print(f"    - {n}")
        print()

    # Risk
    risk = s.get("risk_level", "unknown")
    print(f"  [Risk]")
    print(f"  Level:          {risk.upper()}")
    print(f"  Explanation:    {s.get('risk_explanation', 'No explanation provided.')}")
    print()

    # Requirements
    print(f"  [Requirements]")
    print(f"  API key needed:         {'Yes' if s.get('requires_api_key') else 'No'}")
    print(f"  MCP server needed:      {'Yes' if s.get('requires_mcp') else 'No'}")
    print(f"  External runtime:       {'Yes' if s.get('requires_external_runtime') else 'No'}")
    print()

    # Installation
    print(f"  [Installation]")
    print(f"  Source type:     {s.get('source_type', 'unknown')}")
    print(f"  Install method:  {s.get('install_method', 'unknown')}")
    if s.get("repo_url"):
        print(f"  Repository:      {s['repo_url']}")
    print(f"  License:         {s.get('license_status', 'unknown')}")
    print()

    # Adapter
    adapter = s.get("adapter")
    if adapter:
        print(f"  [Adapter]")
        print(f"  Adapter file:    {adapter}")
        print(f"  Installed to:    templates/skill_adapters/{adapter}")
        print()

    # Profiles
    profiles = s.get("recommended_profiles", [])
    if profiles:
        print(f"  [Recommended profiles]")
        print(f"  {', '.join(profiles)}")
        print()

    # Sub-skills
    sub = s.get("sub_skills", [])
    if sub:
        print(f"  [Sub-skills] ({len(sub)})")
        for sk in sub:
            print(f"    - {sk}")
        print()

    # Default enabled
    print(f"  [Default]")
    print(f"  Enabled by default: {'Yes' if s.get('default_enabled') else 'No'}")
    print()

    # Notes
    notes = s.get("notes", "")
    if notes:
        print(f"  [Additional notes]")
        for line in textwrap.wrap(notes, width=68):
            print(f"  {line}")
        print()

    print_separator()
    print()

    # Install hint
    installable = s.get("install_method") not in ("reference_only",)
    if installable:
        print(f"  To install: python scripts/skill_manager.py --target . --install {skill_id}")
    else:
        print(f"  [REFERENCE ONLY] This skill cannot be installed.")
    print()


# -- Install Single Skill ----------------------------------------------------

def cmd_install(target: Path, catalog: dict, skill_id: str, dry_run: bool = False,
                enable_risky: bool = False, yes: bool = False):
    """Install a single skill."""
    catalog_map = {s["id"]: s for s in catalog["skills"]}
    entry = catalog_map.get(skill_id)

    if not entry:
        print(f"[FAIL] Skill not found: {skill_id}")
        sys.exit(1)

    method = entry.get("install_method", "git_clone")

    # Check installability
    if method == "reference_only":
        print(f"[BLOCKED] {skill_id} is reference-only. Never installed.")
        print(f"         {entry.get('risk_explanation', '')}")
        sys.exit(1)

    if method == "plugin_marketplace":
        print(f"[MANUAL] {skill_id} is a Claude Code plugin marketplace skill.")
        print(f"         Install via: /plugin marketplace add {entry.get('repo_url', '?')}")
        print(f"         Then: /plugin install {skill_id}")
        return

    if method == "mcp_config":
        print(f"[MANUAL] {skill_id} requires MCP server configuration.")
        print(f"         Configure in .claude/mcp.json manually.")
        print(f"         PKB never auto-configures MCP servers.")
        return

    if method == "requires_z_skills_vendor_clone":
        print(f"[BLOCKED] {skill_id} requires z-skills to be installed first.")
        print(f"         Run: python scripts/skill_manager.py --target . --install z-skills")
        print(f"         Then audit z-skills, then enable {skill_id}.")
        sys.exit(1)

    # Special handling for z-skills
    if skill_id == "z-skills":
        return _cmd_install_z_skills(target, entry, dry_run, enable_risky, yes)

    # Risk check
    risk = entry.get("risk_level", "medium")
    if risk == "high" and not enable_risky:
        print(f"[BLOCKED] {skill_id} is HIGH RISK. Use --enable-risky to install.")
        print(f"         {entry.get('risk_explanation', '')}")
        sys.exit(1)

    # Show what will be installed
    print()
    print(f"  Skill: {entry['name']} ({entry['id']})")
    print(f"  Category: {CATEGORY_LABELS.get(entry.get('category', ''), entry.get('category', ''))}")
    print(f"  Risk: {risk.upper()}")
    print(f"  {entry.get('short_description', '')}")
    print()

    if risk == "high":
        print(f"  [!] HIGH RISK: {entry.get('risk_explanation', '')}")
        print()

    if entry.get("requires_mcp"):
        print(f"  [WARN] Requires MCP server -- must be configured manually")
    if entry.get("requires_external_runtime"):
        print(f"  [WARN] Requires external runtime -- must be installed separately")
    if entry.get("requires_api_key"):
        print(f"  [WARN] Requires API key -- configure yourself, never store in PKB")
    if entry.get("license_status", "").startswith("NO LICENSE"):
        print(f"  [WARN] {entry['license_status']}")

    if any([entry.get("requires_mcp"), entry.get("requires_external_runtime"),
            entry.get("requires_api_key")]):
        print()

    # Confirm unless --yes
    if not yes and not dry_run:
        print(f"  Install to: {target / VENDOR_DIR_REL / skill_id}/")
        print()
        response = input(f"  Proceed with installation? [y/N]: ").strip().lower()
        if response not in ("y", "yes"):
            print("  Cancelled.")
            return

    # Execute installation
    if dry_run:
        print(f"  [DRY RUN] Would install: {skill_id}")
        _simulate_install(entry, target, dry_run=True)
        return

    print(f"  Installing {skill_id}...")
    result = _do_install_skill(entry, target)

    if result["status"] == "installed":
        print(f"  [OK] Installed to {result['vendor_path']}")

        # Copy adapter
        if entry.get("adapter"):
            copied = _copy_adapter(entry, target)
            if copied:
                print(f"  [OK] Adapter: {entry['adapter']} -> {ADAPTER_DIR_REL}/")

        # Update config
        _update_pkb_config_for_install(target, entry)
        _update_skill_links_for_install(target, entry)
        print(f"  [OK] Config updated: pkb.config.json, SKILL_LINKS.md")

        # Add to pending audit
        _mark_pending_audit(target, entry["id"])

        print()
        print(f"  Next steps:")
        print(f"    1. Review the skill's LICENSE in {VENDOR_DIR_REL}/{skill_id}/")
        print(f"    2. Run --audit to verify installation")
        print(f"    3. Run --enable {skill_id} to activate the adapter")
        print(f"    4. Restart Claude Code to load new skills")
    else:
        print(f"  [FAIL] {result.get('error', 'unknown error')}")


def _cmd_install_z_skills(target: Path, entry: dict, dry_run: bool,
                          enable_risky: bool, yes: bool):
    """Special installation flow for z-skills with explicit warnings."""
    print()
    print("=" * 72)
    print("  [!] Z-Skills — Third-Party Local Installation")
    print("=" * 72)
    print()
    print("  IMPORTANT — Please read carefully:")
    print()
    print("  1. PKB Starter does NOT redistribute z-skills code.")
    print("     This installation clones directly from:")
    print(f"     {entry.get('repo_url', 'https://github.com/tjxj/z-skills')}")
    print()
    print("  2. z-skills is a third-party repository. Each sub-directory")
    print("     may have its own license terms. You must audit before use.")
    print()
    print("  3. After installation, z-skills will be in:")
    print(f"     skills/_vendor/z-skills/")
    print("     Status: pending_audit (NOT auto-enabled)")
    print()
    print("  4. You must explicitly run --audit and --enable before any")
    print("     z-skills code can be invoked through the PKB adapter.")
    print()
    print("  5. PKB never auto-executes z-skills scripts.")
    print("     The adapter only routes z-web-pack output to raw/webpacks/.")
    print()
    print("  6. You are responsible for complying with the repository's")
    print("     license terms. If no license is found, treat as")
    print("     'all rights reserved' — personal reference only.")
    print()

    if dry_run:
        print("  [DRY RUN] Would git clone into: skills/_vendor/z-skills/")
        print("  [DRY RUN] Status would be: pending_audit")
        print("  [DRY RUN] Adapter: z_skills_adapter.md")
        print()
        _simulate_install(entry, target, dry_run=True)
        return

    # Confirmation
    if not yes:
        response = input(
            "  Type 'INSTALL' to confirm you understand and consent: "
        ).strip()
        if response != "INSTALL":
            print("  Cancelled. z-skills was not installed.")
            return

    print()
    print(f"  Cloning z-skills into skills/_vendor/z-skills/...")
    result = _do_install_skill(entry, target)

    if result["status"] == "installed":
        print(f"  [OK] z-skills installed to {result['vendor_path']}")

        # Copy adapter
        if entry.get("adapter"):
            copied = _copy_adapter(entry, target)
            if copied:
                print(f"  [OK] Adapter: {entry['adapter']} -> {ADAPTER_DIR_REL}/")

        # Update config (pending_audit, NOT enabled)
        _update_pkb_config_for_install(target, entry)
        _update_skill_links_for_install(target, entry)
        _mark_pending_audit(target, entry["id"])
        print(f"  [OK] Config updated. Status: pending_audit")

        print()
        print(f"  Next steps:")
        print(f"    1. Run --audit to check LICENSE and structure")
        print(f"       python scripts/skill_manager.py --target . --audit")
        print(f"    2. Review the audit report: zskill_audit_report.md")
        print(f"    3. Run --enable z-web-pack-local to activate the adapter")
        print(f"    4. The adapter then connects z-web-pack output to raw/webpacks/")
    else:
        print(f"  [FAIL] {result.get('error', 'unknown error')}")


def _do_install_skill(entry: dict, target: Path) -> dict:
    """Execute git clone for a skill. Returns result dict."""
    skill_id = entry["id"]
    repo_url = entry.get("repo_url")
    vendor_dir = target / VENDOR_DIR_REL / skill_id

    vendor_dir.parent.mkdir(parents=True, exist_ok=True)

    if vendor_dir.exists():
        shutil.rmtree(vendor_dir, ignore_errors=True)

    try:
        proc = subprocess.run(
            ["git", "clone", "--depth", "1", "--quiet", repo_url, str(vendor_dir)],
            capture_output=True, text=True, timeout=180,
            encoding="utf-8", errors="replace",
        )
        if proc.returncode == 0:
            return {"status": "installed", "vendor_path": str(vendor_dir.relative_to(target)), "id": skill_id}
        else:
            return {"status": "failed", "error": proc.stderr.strip()[:500], "id": skill_id}
    except subprocess.TimeoutExpired:
        return {"status": "failed", "error": "Clone timed out (180s)", "id": skill_id}
    except FileNotFoundError:
        return {"status": "failed", "error": "git not found in PATH", "id": skill_id}
    except Exception as e:
        return {"status": "failed", "error": str(e)[:500], "id": skill_id}


def _simulate_install(entry: dict, target: Path, dry_run: bool = True):
    """Simulate installation -- print what would happen."""
    vendor_path = target / VENDOR_DIR_REL / entry["id"]
    print(f"    Vendor path:    {vendor_path}")
    print(f"    Repo:           {entry.get('repo_url', 'N/A')}")
    print(f"    Method:         {entry.get('install_method', 'git_clone')}")
    if entry.get("adapter"):
        print(f"    Adapter:        {entry['adapter']} -> {ADAPTER_DIR_REL}/")
    if entry.get("requires_mcp"):
        print(f"    [WARN] MCP configuration needed (manual)")
    if entry.get("requires_external_runtime"):
        print(f"    [WARN] External runtime needed (manual install)")
    if entry.get("requires_api_key"):
        print(f"    [WARN] API key needed (manual configuration)")
    print(f"    License:        {entry.get('license_status', 'unknown')}")
    print()


# -- Install Profile ---------------------------------------------------------

def cmd_install_profile(target: Path, catalog: dict, profiles: dict, profile: str,
                        dry_run: bool = False, enable_risky: bool = False, yes: bool = False):
    """Install all skills from a profile."""
    if profile not in profiles.get("profiles", {}):
        print(f"[FAIL] Unknown profile: {profile}")
        print(f"       Available: {', '.join(profiles['profiles'].keys())}")
        sys.exit(1)

    profile_def = profiles["profiles"][profile]
    skill_ids = profile_def.get("skills", [])
    profile_desc = profile_def.get("description", "")

    if profile == "custom":
        skill_ids = _interactive_select(catalog)
        if not skill_ids:
            print("[INFO] No skills selected. PKB core only.")
            return

    if not skill_ids:
        print(f"[INFO] Profile '{profile}' has no additional skills.")
        print(f"       {profile_desc}")
        print(f"       PKB core tools are always available.")
        return

    catalog_map = {s["id"]: s for s in catalog["skills"]}

    # Show profile overview
    print_header(f"Install Profile: {profile}")
    print(f"  {profile_desc}")
    print()
    print(f"  {len(skill_ids)} skill(s) in this profile:")
    print()

    to_install = []
    skipped = []
    for sid in skill_ids:
        entry = catalog_map.get(sid)
        if not entry:
            print(f"  [SKIP] {sid} -- not found in catalog")
            skipped.append(sid)
            continue
        method = entry.get("install_method", "")
        risk = entry.get("risk_level", "")

        if method == "reference_only":
            print(f"  [SKIP] {sid} -- reference only (not installable)")
            skipped.append(sid)
            continue
        if method == "user_approved_clone":
            print(f"  [MANUAL] {sid} -- requires explicit user consent (use --install {sid})")
            skipped.append(sid)
            continue
        if method == "requires_z_skills_vendor_clone":
            print(f"  [MANUAL] {sid} -- requires z-skills first (use --install z-skills)")
            skipped.append(sid)
            continue
        if risk == "high" and not enable_risky:
            print(f"  [SKIP] {sid} -- HIGH RISK (use --enable-risky)")
            skipped.append(sid)
            continue
        if method == "plugin_marketplace":
            print(f"  [MANUAL] {sid} -- plugin marketplace (install via Claude Code)")
            skipped.append(sid)
            continue
        if method == "mcp_config":
            print(f"  [MANUAL] {sid} -- MCP server (configure manually)")
            skipped.append(sid)
            continue

        mcp = " [MCP]" if entry.get("requires_mcp") else ""
        api = " [API]" if entry.get("requires_api_key") else ""
        print(f"  [{risk.upper():<7s}] {sid:<35s} {entry.get('short_description', '')[:60]}{mcp}{api}")
        to_install.append(entry)

    print()
    print(f"  To install: {len(to_install)}  |  Skipped: {len(skipped)}")
    print()

    if not to_install:
        print("[INFO] No auto-installable skills in this profile.")
        if skipped:
            print("       Skipped skills may require --enable-risky, manual MCP config,")
            print("       or Claude Code plugin marketplace installation.")
        return

    if dry_run:
        print(f"  [DRY RUN] Would install {len(to_install)} skills:")
        for entry in to_install:
            _simulate_install(entry, target, dry_run=True)
        _print_dry_run_config_summary(target, to_install, profile)
        return

    # Confirm
    if not yes:
        response = input(f"  Proceed with installation of {len(to_install)} skill(s)? [y/N]: ").strip().lower()
        if response not in ("y", "yes"):
            print("  Cancelled.")
            return

    # Install each
    print()
    results = []
    for entry in to_install:
        print(f"  Installing: {entry['id']}...")
        result = _do_install_skill(entry, target)
        results.append(result)

        if result["status"] == "installed":
            print(f"    [OK] -> {result['vendor_path']}")
            if entry.get("adapter"):
                _copy_adapter(entry, target)
                print(f"    [OK] Adapter: {entry['adapter']}")
            _update_pkb_config_for_install(target, entry)
        else:
            print(f"    [FAIL] {result.get('error', 'unknown')[:120]}")

    # Final config update
    _update_pkb_config_for_profile(target, profile, results)
    _update_skill_links_for_profile(target, to_install, profile)

    # Report
    succeeded = [r for r in results if r["status"] == "installed"]
    failed = [r for r in results if r["status"] == "failed"]

    print()
    print_header("Installation Report")
    print(f"  Profile:    {profile}")
    print(f"  Installed:  {len(succeeded)}")
    print(f"  Failed:     {len(failed)}")
    print(f"  Skipped:    {len(skipped)}")
    if succeeded:
        print(f"  Path:       {VENDOR_DIR_REL}/")
        print()
        print(f"  Next steps:")
        print(f"    1. Run --audit to verify installations")
        print(f"    2. Run --enable <id> for skills you want to activate")
        print(f"    3. Restart Claude Code to load new skills")
    print("=" * 72)


def _print_dry_run_config_summary(target: Path, to_install: list, profile: str):
    """Print what config changes would be made."""
    print()
    print(f"  [DRY RUN] Would update:")
    print(f"    pkb.config.json  -- installed_profiles += [{profile}]")
    print(f"    pkb.config.json  -- installed_skills += [{', '.join(e['id'] for e in to_install)}]")
    print(f"    SKILL_LINKS.md   -- add entries for {len(to_install)} skills")
    for entry in to_install:
        if entry.get("adapter"):
            print(f"    {ADAPTER_DIR_REL}/{entry['adapter']}")
    print()


# -- Audit -------------------------------------------------------------------

def cmd_audit(target: Path, catalog: dict, dry_run: bool = False):
    """Audit installed skills against the catalog."""
    vendor_dir = target / VENDOR_DIR_REL
    catalog_map = {s["id"]: s for s in catalog["skills"]}
    pkb_config = load_pkb_config(target)
    skills_state = pkb_config.get("skills", {})

    print_header("PKB Skill Audit")

    if not vendor_dir.is_dir():
        print("  No skills/_vendor/ directory found.")
        print("  No skills installed. Use --install-profile <name> to get started.")
        print()
        return

    installed_dirs = [d for d in vendor_dir.iterdir() if d.is_dir()]
    if not installed_dirs:
        print("  skills/_vendor/ is empty.")
        print("  No skills installed. Use --install-profile <name> to get started.")
        print()
        return

    print(f"  Found {len(installed_dirs)} installed skill(s):")
    print()

    known = 0
    unknown = 0
    pending = []
    no_license = []
    no_adapter = []
    issues = []

    for d in sorted(installed_dirs):
        skill_id = d.name
        entry = catalog_map.get(skill_id)

        if entry:
            known += 1
            risk = entry.get("risk_level", "unknown")
            lic = entry.get("license_status", "")
            name = entry.get("name", "?")

            print(f"  [{risk.upper():<7s}] {skill_id}  -- {name}")
            print(f"              Repo: {entry.get('repo_url', 'N/A')}")
            print(f"              License: {lic}")
        else:
            unknown += 1
            print(f"  [UNKNOWN ] {skill_id}")
            print(f"              NOT in catalog -- may be manually installed")
            issues.append(f"{skill_id}: not in catalog")

        # Check .git
        if not (d / ".git").is_dir():
            issues.append(f"{skill_id}: missing .git (not a git clone)")
            print(f"              [!] .git MISSING (may be copy, not clone)")

        # Check INSTALL_NOTE.md
        if (d / "INSTALL_NOTE.md").is_file():
            print(f"              INSTALL_NOTE.md: present")
        else:
            print(f"              INSTALL_NOTE.md: MISSING")

        # Check license in repo
        if entry and lic.startswith("NO LICENSE"):
            no_license.append(skill_id)

        # Check adapter
        adapter = entry.get("adapter") if entry else None
        if adapter:
            adapter_path = target / ADAPTER_DIR_REL / adapter
            if adapter_path.is_file():
                print(f"              Adapter: {adapter} -- present")
            else:
                no_adapter.append(skill_id)
                print(f"              Adapter: {adapter} -- MISSING")

        # Enabled?
        enabled_ids = skills_state.get("enabled_skills", [])
        disabled_ids = skills_state.get("disabled_skills", [])
        pending_ids = skills_state.get("pending_audit", [])
        if skill_id in enabled_ids:
            print(f"              Status: ENABLED")
        elif skill_id in disabled_ids:
            print(f"              Status: DISABLED")
        elif skill_id in pending_ids:
            print(f"              Status: PENDING AUDIT")
            pending.append(skill_id)
        else:
            print(f"              Status: installed (not yet classified)")

        print()

    # Summary
    print_separator()
    print(f"  Summary: {known} known, {unknown} unknown -- {known + unknown} total")
    print(f"  Catalog version: {catalog.get('version', '?')}")
    print(f"  PKB skills config: {skills_state.get('catalog_version', '?')}")
    print()

    if no_license:
        print(f"  [!] Skills with NO LICENSE ({len(no_license)}):")
        for sid in no_license:
            print(f"      {sid}")
        print(f"      Treat as all rights reserved. Use for personal reference only.")
        print()

    if no_adapter:
        print(f"  [!] Skills with missing adapters ({len(no_adapter)}):")
        for sid in no_adapter:
            print(f"      {sid}")
        print(f"      Run --install {sid} again to copy the adapter.")
        print()

    if pending:
        print(f"  [!] Skills pending audit ({len(pending)}):")
        for sid in pending:
            print(f"      {sid}")
        print(f"      Review LICENSE, code, and adapter before --enable.")
        print()

    if issues:
        print(f"  Issues found: {len(issues)}")
        for i in issues:
            print(f"    - {i}")
        print()

    if not issues and not no_license and not no_adapter and not pending:
        print(f"  [OK] All installed skills pass audit.")
        print()

    print_separator()

    # Generate report file
    if not dry_run:
        report_path = target / "skill_manager_report.md"
        _write_audit_report(report_path, installed_dirs, catalog_map, skills_state,
                           known, unknown, issues, no_license, no_adapter, pending, catalog)
        print(f"  Report: {report_path}")

    # Z-Skills specific audit (delegates to zskill_bridge.py if z-skills is installed)
    _audit_z_skills_if_present(target, dry_run)


def _audit_z_skills_if_present(target: Path, dry_run: bool):
    """Run zskill_bridge.py audit if z-skills is installed."""
    z_skills_path = target / VENDOR_DIR_REL / "z-skills"
    if not z_skills_path.is_dir():
        return

    bridge_script = target / "tools" / "zskill_bridge.py"
    if not bridge_script.is_file():
        # Bridge script might not be in target PKB yet; check pkb-starter
        bridge_script = STARTER_DIR / "template" / "tools" / "zskill_bridge.py"

    if not bridge_script.is_file():
        print()
        print("  [INFO] z-skills installed but zskill_bridge.py not found.")
        print("         Copy it from pkb-starter/template/tools/zskill_bridge.py")
        return

    print()
    print(f"  --- Z-Skills Audit (via zskill_bridge.py) ---")
    print()

    if dry_run:
        print(f"  [DRY RUN] Would run: python {bridge_script} audit")
        return

    try:
        proc = subprocess.run(
            [sys.executable, str(bridge_script), "audit"],
            capture_output=True, text=True, timeout=30,
            encoding="utf-8", errors="replace",
            cwd=str(target),
        )
        print(proc.stdout)
        if proc.stderr.strip():
            print(proc.stderr)
    except subprocess.TimeoutExpired:
        print("  [WARN] z-skills audit timed out")
    except Exception as e:
        print(f"  [WARN] z-skills audit failed: {e}")



def _write_audit_report(report_path: Path, installed_dirs, catalog_map, skills_state,
                        known, unknown, issues, no_license, no_adapter, pending, catalog):
    """Write skill_manager_report.md."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        "# PKB Skill Manager Report",
        "",
        f"> Generated: {today}",
        f"> Catalog version: {catalog.get('version', '?')}",
        "",
        "## Summary",
        "",
        f"- Installed skills: {len(installed_dirs)}",
        f"- Known (in catalog): {known}",
        f"- Unknown (not in catalog): {unknown}",
        f"- Issues: {len(issues)}",
        f"- No license: {len(no_license)}",
        f"- Missing adapter: {len(no_adapter)}",
        f"- Pending audit: {len(pending)}",
        "",
    ]
    if issues:
        lines.append("## Issues")
        lines.append("")
        for i in issues:
            lines.append(f"- {i}")
        lines.append("")
    if no_license:
        lines.append("## No License")
        lines.append("")
        for sid in no_license:
            lines.append(f"- {sid}")
        lines.append("")
    lines.append("---")
    lines.append(f"*Generated by PKB skill_manager.py v{catalog.get('version', '?')}*")
    lines.append("")
    report_path.write_text("\n".join(lines), encoding="utf-8")


# -- Enable / Disable --------------------------------------------------------

def cmd_enable(target: Path, catalog: dict, skill_id: str):
    """Enable a skill's adapter."""
    catalog_map = {s["id"]: s for s in catalog["skills"]}
    entry = catalog_map.get(skill_id)

    # Special check for z-web-pack-local: requires z-skills installed + audited
    if skill_id == "z-web-pack-local":
        z_skills_path = target / VENDOR_DIR_REL / "z-skills"
        if not z_skills_path.is_dir():
            print(f"[FAIL] z-web-pack-local requires z-skills to be installed first.")
            print(f"       Run: --install z-skills")
            sys.exit(1)

        audit_report = target / "zskill_audit_report.md"
        if not audit_report.is_file():
            print(f"[FAIL] z-skills has not been audited yet.")
            print(f"       Run: --audit (which includes z-skills audit)")
            print(f"       Or: python tools/zskill_bridge.py audit")
            sys.exit(1)

        print()
        print(f"  z-skills: INSTALLED at {z_skills_path}")
        print(f"  Audit report: {audit_report}")
        print()

    # Verify installed
    vendor_path = target / VENDOR_DIR_REL / skill_id
    if skill_id == "z-web-pack-local":
        # z-web-pack-local is adapter_only, doesn't have its own vendor dir
        pass
    elif not vendor_path.is_dir():
        print(f"[FAIL] {skill_id} is not installed in {VENDOR_DIR_REL}/")
        print(f"       Run --install {skill_id} first.")
        sys.exit(1)

    config = load_pkb_config(target)
    skills_state = config.setdefault("skills", {})

    # Move from disabled/pending to enabled
    enabled = set(skills_state.get("enabled_skills", []))
    disabled = set(skills_state.get("disabled_skills", []))
    pending = set(skills_state.get("pending_audit", []))

    disabled.discard(skill_id)
    pending.discard(skill_id)
    enabled.add(skill_id)

    # Enable adapter
    adapter = entry.get("adapter") if entry else None
    if adapter:
        adapter_src = ADAPTERS_SRC / adapter
        adapter_dst = target / ADAPTER_DIR_REL / adapter
        if adapter_src.is_file():
            adapter_dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(adapter_src, adapter_dst)
            enabled_adapters = set(skills_state.get("enabled_adapters", []))
            enabled_adapters.add(adapter)
            skills_state["enabled_adapters"] = list(enabled_adapters)
            print(f"  [OK] Adapter enabled: {adapter}")
        else:
            print(f"  [WARN] Adapter not found in pkb-starter: {adapter}")
            print(f"         Expected: {adapter_src}")

    skills_state["enabled_skills"] = list(enabled)
    skills_state["disabled_skills"] = list(disabled)
    skills_state["pending_audit"] = list(pending)

    save_pkb_config(target, config)

    print(f"  [OK] {skill_id} is now ENABLED")
    if entry:
        print(f"       {entry.get('short_description', '')}")
    print(f"       Restart Claude Code to load the skill.")


def cmd_disable(target: Path, skill_id: str):
    """Disable a skill without deleting its code."""
    # Special handling for z-web-pack-local (adapter-only, no vendor dir)
    if skill_id == "z-web-pack-local":
        config = load_pkb_config(target)
        skills_state = config.setdefault("skills", {})

        enabled = set(skills_state.get("enabled_skills", []))
        disabled = set(skills_state.get("disabled_skills", []))
        enabled_adapters = set(skills_state.get("enabled_adapters", []))

        enabled.discard(skill_id)
        disabled.add(skill_id)
        enabled_adapters.discard("z_skills_adapter.md")

        skills_state["enabled_skills"] = list(enabled)
        skills_state["disabled_skills"] = list(disabled)
        skills_state["enabled_adapters"] = list(enabled_adapters)

        save_pkb_config(target, config)

        print(f"  [OK] z-web-pack-local is now DISABLED")
        print(f"       Adapter deactivated. z-skills code remains in {VENDOR_DIR_REL}/z-skills/")
        print(f"       Run --enable z-web-pack-local to re-enable.")
        print(f"       To fully remove z-skills: delete {VENDOR_DIR_REL}/z-skills/")
        return

    vendor_path = target / VENDOR_DIR_REL / skill_id
    if not vendor_path.is_dir():
        print(f"[FAIL] {skill_id} is not installed.")
        sys.exit(1)

    config = load_pkb_config(target)
    skills_state = config.setdefault("skills", {})

    enabled = set(skills_state.get("enabled_skills", []))
    disabled = set(skills_state.get("disabled_skills", []))

    enabled.discard(skill_id)
    disabled.add(skill_id)

    skills_state["enabled_skills"] = list(enabled)
    skills_state["disabled_skills"] = list(disabled)

    save_pkb_config(target, config)

    print(f"  [OK] {skill_id} is now DISABLED")
    print(f"       Source code remains in {VENDOR_DIR_REL}/{skill_id}/")
    print(f"       Run --enable {skill_id} to re-enable.")
    print(f"       To fully remove: delete {VENDOR_DIR_REL}/{skill_id}/")


# -- Show enabled ------------------------------------------------------------

def cmd_enabled(target: Path, catalog: dict):
    """Show enabled skills and adapters."""
    config = load_pkb_config(target)
    skills_state = config.get("skills", {})
    enabled_ids = skills_state.get("enabled_skills", [])
    enabled_adapters = skills_state.get("enabled_adapters", [])
    catalog_map = {s["id"]: s for s in catalog["skills"]}

    print_header("Enabled Skills & Adapters")

    if not enabled_ids and not enabled_adapters:
        print("  No skills or adapters are currently enabled.")
        print()
        print("  Use --install-profile <name> to install skills,")
        print("  then --enable <id> to activate them.")
        print()
        return

    if enabled_ids:
        print(f"  Enabled skills ({len(enabled_ids)}):")
        print()
        for sid in sorted(enabled_ids):
            entry = catalog_map.get(sid, {})
            name = entry.get("name", sid)
            cat = entry.get("category", "?")
            print(f"    {sid:<35s} [{CATEGORY_LABELS.get(cat, cat)}] {name}")
        print()

    if enabled_adapters:
        print(f"  Enabled adapters ({len(enabled_adapters)}):")
        print()
        for a in sorted(enabled_adapters):
            adapter_path = target / ADAPTER_DIR_REL / a
            exists = adapter_path.is_file()
            tag = "present" if exists else "MISSING"
            print(f"    {a:<40s} [{tag}]")
        print()

    print_separator()


# -- Update Catalog ----------------------------------------------------------

def cmd_update_catalog(target: Path, catalog: dict, dry_run: bool = False):
    """Update the local skill catalog from pkb-starter source."""
    if dry_run:
        print(f"  [DRY RUN] Would update catalog from: {CATALOG_PATH}")
        return

    # This copies the latest catalog and profiles to the target's reference
    # (The catalog is read from pkb-starter, so "update" means refresh the local config)
    config = load_pkb_config(target)
    skills_state = config.setdefault("skills", {})
    old_version = skills_state.get("catalog_version", "?")
    skills_state["catalog_version"] = catalog.get("version", "0.4.0")
    save_pkb_config(target, config)

    print(f"  [OK] Local catalog version updated: {old_version} -> {catalog.get('version', '?')}")
    print(f"       Source: {CATALOG_PATH}")


# -- Config Helpers ----------------------------------------------------------

def _copy_adapter(entry: dict, target: Path) -> bool:
    """Copy adapter from pkb-starter to target PKB."""
    adapter_name = entry.get("adapter")
    if not adapter_name:
        return False
    adapter_src = ADAPTERS_SRC / adapter_name
    if not adapter_src.is_file():
        return False
    adapter_dst = target / ADAPTER_DIR_REL / adapter_name
    adapter_dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(adapter_src, adapter_dst)
    return True


def _update_pkb_config_for_install(target: Path, entry: dict):
    """Update pkb.config.json for a single skill install."""
    config = load_pkb_config(target)
    skills_state = config.setdefault("skills", {})

    installed = set(skills_state.get("installed_skills", []))
    installed.add(entry["id"])
    skills_state["installed_skills"] = list(installed)

    # Add to vendor_downloads
    downloads = set(skills_state.get("vendor_downloads", []))
    downloads.add(entry["id"])
    skills_state["vendor_downloads"] = list(downloads)

    # Add to pending audit
    pending = set(skills_state.get("pending_audit", []))
    pending.add(entry["id"])
    skills_state["pending_audit"] = list(pending)

    save_pkb_config(target, config)


def _update_pkb_config_for_profile(target: Path, profile: str, results: list):
    """Update pkb.config.json after profile installation."""
    config = load_pkb_config(target)
    skills_state = config.setdefault("skills", {})

    profiles = set(skills_state.get("installed_profiles", []))
    profiles.add(profile)
    skills_state["installed_profiles"] = list(profiles)

    for r in results:
        if r["status"] == "installed":
            installed = set(skills_state.get("installed_skills", []))
            installed.add(r["id"])
            skills_state["installed_skills"] = list(installed)

            downloads = set(skills_state.get("vendor_downloads", []))
            downloads.add(r["id"])
            skills_state["vendor_downloads"] = list(downloads)

            pending = set(skills_state.get("pending_audit", []))
            pending.add(r["id"])
            skills_state["pending_audit"] = list(pending)

    save_pkb_config(target, config)


def _mark_pending_audit(target: Path, skill_id: str):
    """Mark a skill as pending audit."""
    config = load_pkb_config(target)
    skills_state = config.setdefault("skills", {})
    pending = set(skills_state.get("pending_audit", []))
    pending.add(skill_id)
    skills_state["pending_audit"] = list(pending)
    save_pkb_config(target, config)


def _update_skill_links_for_install(target: Path, entry: dict):
    """Update SKILL_LINKS.md for a single skill install."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    links_path = target / "SKILL_LINKS.md"

    new_entry = f"""### {entry['name']}
- ID: `{entry['id']}`
- Category: {entry.get('category', 'unknown')}
- Repository: {entry.get('repo_url', 'N/A')}
- Install method: {entry.get('install_method', 'git_clone')}
- Vendor path: `{VENDOR_DIR_REL}/{entry['id']}/`
- Adapter: `templates/skill_adapters/{entry.get('adapter', 'none')}`
- Risk level: {entry.get('risk_level', 'unknown')}
- License: {entry.get('license_status', 'unknown')}
- Installed: {today}
- Status: pending audit
"""

    if links_path.is_file():
        content = links_path.read_text(encoding="utf-8")
        # Append before the closing marker
        if "---" in content:
            parts = content.rsplit("---", 1)
            content = parts[0].rstrip() + "\n" + new_entry + "\n---" + parts[1]
        else:
            content += "\n" + new_entry
        links_path.write_text(content, encoding="utf-8")
    else:
        header = f"""# SKILL_LINKS.md -- Installed Skill Index

> Auto-generated by PKB Starter skill_manager.py v0.4.0 on {today}.

## Installed Skills

"""
        links_path.write_text(header + new_entry, encoding="utf-8")


def _update_skill_links_for_profile(target: Path, entries: list, profile: str):
    """Update SKILL_LINKS.md after profile install."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    links_path = target / "SKILL_LINKS.md"

    lines = [
        "# SKILL_LINKS.md -- Installed Skill Index",
        "",
        f"> Auto-generated by PKB Starter skill_manager.py v0.4.0 on {today}.",
        f"> Profile: {profile}",
        "",
        "## Installed Skills",
        "",
    ]

    for entry in entries:
        lines.append(f"### {entry['name']}")
        lines.append(f"- ID: `{entry['id']}`")
        lines.append(f"- Category: {entry.get('category', 'unknown')}")
        if entry.get("repo_url"):
            lines.append(f"- Repository: {entry['repo_url']}")
        lines.append(f"- Install method: {entry.get('install_method', 'git_clone')}")
        lines.append(f"- Vendor path: `{VENDOR_DIR_REL}/{entry['id']}/`")
        adapter = entry.get("adapter")
        lines.append(f"- Adapter: `templates/skill_adapters/{adapter}`" if adapter else "- Adapter: none")
        lines.append(f"- Risk level: {entry.get('risk_level', 'unknown')}")
        lines.append(f"- License: {entry.get('license_status', 'unknown')}")
        sub = entry.get("sub_skills", [])
        if sub:
            lines.append(f"- Sub-skills ({len(sub)}): {', '.join(sub)}")
        lines.append(f"- Installed: {today}")
        lines.append("")

    lines.append("---")
    lines.append(f"*Generated by PKB Starter v0.4.0*")
    lines.append("")

    links_path.write_text("\n".join(lines), encoding="utf-8")


# -- Interactive Selection ---------------------------------------------------

def _interactive_select(catalog: dict) -> list[str]:
    """Interactive skill selection for custom profile."""
    print()
    print("=" * 60)
    print("  Custom Profile -- Select Skills")
    print("=" * 60)
    print()
    print("  Enter skill IDs separated by spaces, or 'all' for all safe skills.")
    print("  Reference-only and plugin_marketplace skills cannot be auto-installed.")
    print()

    installable = [
        s for s in catalog["skills"]
        if s["install_method"] not in ("reference_only", "plugin_marketplace", "mcp_config")
    ]
    for i, skill in enumerate(installable, 1):
        risk_tag = RISK_SYMBOLS.get(skill.get("risk_level"), "[?]")
        mcp_tag = " [MCP]" if skill.get("requires_mcp") else ""
        api_tag = " [API]" if skill.get("requires_api_key") else ""
        print(f"  {i:2d}. {skill['id']:<32s} {risk_tag:<7s} {skill.get('short_description', '')[:60]}{mcp_tag}{api_tag}")

    print()
    choice = input("  Enter skill IDs (space-separated, or 'all'): ").strip()

    if choice.lower() == "all":
        return [s["id"] for s in installable if s.get("risk_level") != "high"]

    selected = choice.split()
    valid_ids = {s["id"] for s in installable}
    return [s for s in selected if s in valid_ids]


# -- Main --------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="PKB Starter -- Runtime Skill Manager (v0.4.0)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Examples:
              python skill_manager.py --target "D:\\MyKB" --list
              python skill_manager.py --target "D:\\MyKB" --describe deep-research-skills
              python skill_manager.py --target "D:\\MyKB" --install deep-research-skills
              python skill_manager.py --target "D:\\MyKB" --install-profile student
              python skill_manager.py --target "D:\\MyKB" --audit
              python skill_manager.py --target "D:\\MyKB" --enabled
              python skill_manager.py --target "D:\\MyKB" --enable kanban-skill
              python skill_manager.py --target "D:\\MyKB" --disable kanban-skill
              python skill_manager.py --target "D:\\MyKB" --update-catalog
        """),
    )
    parser.add_argument("--target", required=True,
                        help="Path to PKB target directory")
    parser.add_argument("--list", action="store_true",
                        help="List all skills in the catalog with descriptions")
    parser.add_argument("--describe", default=None,
                        help="Show full details for a skill (by ID)")
    parser.add_argument("--install", default=None,
                        help="Install a single skill (by ID)")
    parser.add_argument("--install-profile", default=None,
                        help="Install all skills from a profile")
    parser.add_argument("--audit", action="store_true",
                        help="Audit installed skills")
    parser.add_argument("--enabled", action="store_true",
                        help="Show enabled skills and adapters")
    parser.add_argument("--enable", default=None,
                        help="Enable a skill's adapter (by ID)")
    parser.add_argument("--disable", default=None,
                        help="Disable a skill without deleting source (by ID)")
    parser.add_argument("--update-catalog", action="store_true",
                        help="Update local skill catalog version")
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview actions without making changes")
    parser.add_argument("--enable-risky", action="store_true",
                        help="Allow installation of high-risk skills")
    parser.add_argument("--yes", action="store_true",
                        help="Skip confirmation prompts")

    args = parser.parse_args()

    # Load data sources
    catalog = load_json(CATALOG_PATH)
    profiles = load_json(PROFILES_PATH)
    target = Path(args.target).resolve()

    if not target.is_dir():
        print(f"[FAIL] Target directory does not exist: {target}")
        sys.exit(1)

    # Status (no other flag)
    no_action = not any([args.list, args.describe, args.install, args.install_profile,
                          args.audit, args.enabled, args.enable, args.disable,
                          args.update_catalog])

    if no_action:
        cmd_status(target, catalog, profiles, load_pkb_config(target))
        return

    # Dispatch
    if args.list:
        cmd_list(catalog, target)
    elif args.describe:
        cmd_describe(catalog, args.describe)
    elif args.install:
        cmd_install(target, catalog, args.install, args.dry_run, args.enable_risky, args.yes)
    elif args.install_profile:
        cmd_install_profile(target, catalog, profiles, args.install_profile,
                           args.dry_run, args.enable_risky, args.yes)
    elif args.audit:
        cmd_audit(target, catalog, args.dry_run)
    elif args.enabled:
        cmd_enabled(target, catalog)
    elif args.enable:
        cmd_enable(target, catalog, args.enable)
    elif args.disable:
        cmd_disable(target, args.disable)
    elif args.update_catalog:
        cmd_update_catalog(target, catalog, args.dry_run)


if __name__ == "__main__":
    main()
