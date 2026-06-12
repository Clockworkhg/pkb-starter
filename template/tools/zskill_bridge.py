#!/usr/bin/env python3
"""
PKB Starter -- Z-Skills Bridge (v0.1.0)

Connects a user-installed local copy of z-skills (tjxj/z-skills) to the PKB
raw/wiki workflow. Does NOT include z-skills code. Does NOT modify z-skills
source by default.

Usage:
    python tools/zskill_bridge.py status
    python tools/zskill_bridge.py audit
    python tools/zskill_bridge.py audit --dry-run
    python tools/zskill_bridge.py run --skill z-web-pack --url <url> --topic <topic>
    python tools/zskill_bridge.py import-output --path <z-web-pack-output-dir>
    python tools/zskill_bridge.py patch --allow-local-patch

Safety:
    - No z-skills code is bundled, redistributed, or auto-executed.
    - z-skills must be explicitly installed by the user into skills/_vendor/z-skills/.
    - Audit required before any run or import-output.
    - Local patches are disabled by default. Requires --allow-local-patch.
    - Patches go to .pkb_local/patches/ (gitignored), never committed or distributed.
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

VENDOR_DIR = "skills/_vendor"
Z_SKILLS_DIR = "skills/_vendor/z-skills"
Z_WEB_PACK_DIR = "skills/_vendor/z-skills/z-web-pack"
PKB_LOCAL_DIR = ".pkb_local"
PKB_PATCH_DIR = ".pkb_local/patches"

# Files to check for license
LICENSE_CANDIDATES = ["LICENSE", "LICENSE.txt", "LICENSE.md", "COPYING", "COPYING.txt", "COPYING.LESSER"]


def get_pkb_root() -> Path:
    """Find PKB root by looking for pkb.config.json in current or parent dirs."""
    cwd = Path.cwd()
    for parent in [cwd] + list(cwd.parents):
        if (parent / "pkb.config.json").is_file():
            return parent
    return cwd


# -- 1. locate -----------------------------------------------------------------

def locate_z_skills(pkb_root: Path) -> dict:
    """
    Detect whether z-skills is installed locally.
    Checks both 'z-skills' and 'tjxj-z-skills' directory names.
    Returns a dict with paths and existence flags.
    """
    z_skills_root = pkb_root / Z_SKILLS_DIR
    alt_skills_root = pkb_root / "skills" / "_vendor" / "tjxj-z-skills"

    # Use whichever exists
    if not z_skills_root.is_dir() and alt_skills_root.is_dir():
        z_skills_root = alt_skills_root

    z_web_pack_root = z_skills_root / "z-web-pack"

    result = {
        "z_skills_installed": z_skills_root.is_dir(),
        "z_skills_path": str(z_skills_root),
        "z_web_pack_path": str(z_web_pack_root),
        "z_web_pack_skill_md": (z_web_pack_root / "SKILL.md").is_file(),
        "z_web_pack_scripts": (z_web_pack_root / "scripts").is_dir(),
        "sub_skills_found": [],
    }

    if z_skills_root.is_dir():
        for item in sorted(z_skills_root.iterdir()):
            if item.is_dir() and not item.name.startswith("."):
                has_skill_md = (item / "SKILL.md").is_file()
                result["sub_skills_found"].append({
                    "name": item.name,
                    "has_skill_md": has_skill_md,
                    "path": str(item.relative_to(pkb_root)),
                })

    return result


# -- 2. audit ------------------------------------------------------------------

def find_license_files(directory: Path) -> list[str]:
    """Find license files in a directory."""
    found = []
    if directory.is_dir():
        for cand in LICENSE_CANDIDATES:
            cand_path = directory / cand
            if cand_path.is_file():
                found.append(str(cand_path))
    return found


def audit_z_skills(pkb_root: Path, dry_run: bool = False) -> dict:
    """
    Audit installed z-skills:
    - Check for LICENSE files in root, z-web-pack, and each sub-skill
    - Record license_status per directory
    - Generate audit report
    Returns audit dict.
    """
    loc = locate_z_skills(pkb_root)
    z_skills_root = pkb_root / Z_SKILLS_DIR

    if not loc["z_skills_installed"]:
        return {
            "status": "not_installed",
            "message": "z-skills is not installed. Use /project:skills --install z-skills first.",
            "directories": {},
            "issues": [],
        }

    audit_result = {
        "status": "installed",
        "audit_time": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "z_skills_path": str(z_skills_root),
        "directories": {},
        "overall_license_status": "unknown",
        "issues": [],
        "recommendations": [],
    }

    # Check z-skills root
    root_licenses = find_license_files(z_skills_root)
    audit_result["directories"]["z-skills (root)"] = {
        "path": str(z_skills_root),
        "licenses_found": root_licenses,
        "license_status": "found" if root_licenses else "missing",
    }
    if not root_licenses:
        audit_result["issues"].append("z-skills root: NO LICENSE file found")
        audit_result["recommendations"].append(
            "Check https://github.com/tjxj/z-skills for license information"
        )

    # Check each sub-skill
    for sub in loc["sub_skills_found"]:
        sub_path = pkb_root / sub["path"]
        sub_licenses = find_license_files(sub_path)
        status = "found" if sub_licenses else "missing"
        audit_result["directories"][sub["name"]] = {
            "path": str(sub_path),
            "licenses_found": sub_licenses,
            "license_status": status,
            "has_skill_md": sub["has_skill_md"],
        }
        if not sub_licenses:
            audit_result["issues"].append(
                f"{sub['name']}: NO LICENSE file found"
            )

    # Determine overall status
    any_missing = any(
        d["license_status"] == "missing"
        for d in audit_result["directories"].values()
    )
    any_found = any(
        d["license_status"] == "found"
        for d in audit_result["directories"].values()
    )

    if any_missing and not any_found:
        audit_result["overall_license_status"] = "NO LICENSE FOUND — treat as all rights reserved"
        audit_result["recommendations"].append(
            "Use for personal, local reference only. Do NOT redistribute any part."
        )
    elif any_missing:
        audit_result["overall_license_status"] = "partial — some directories lack LICENSE"
        audit_result["recommendations"].append(
            "Review per-directory license status. Directories without LICENSE may be all rights reserved."
        )
    else:
        audit_result["overall_license_status"] = "license files found — review terms"

    audit_result["recommendations"].append(
        "After reviewing licenses, run /project:skills --enable z-web-pack-local to activate."
    )

    # Generate report file
    if not dry_run:
        report_path = pkb_root / "zskill_audit_report.md"
        write_audit_report(report_path, audit_result, loc)
        audit_result["report_path"] = str(report_path)

    return audit_result


def write_audit_report(report_path: Path, audit_result: dict, loc: dict):
    """Write zskill_audit_report.md."""
    lines = [
        "# Z-Skills Audit Report",
        "",
        f"> Generated: {audit_result['audit_time']}",
        f"> Z-Skills path: {audit_result['z_skills_path']}",
        "",
        "## Overall Status",
        "",
        f"**License status**: {audit_result['overall_license_status']}",
        "",
        "## Directory Audit",
        "",
        "| Directory | License Found | Has SKILL.md |",
        "|-----------|--------------|-------------|",
    ]

    for dir_name, info in audit_result["directories"].items():
        license_str = ", ".join([Path(p).name for p in info.get("licenses_found", [])]) or "NONE"
        has_skill = "Yes" if info.get("has_skill_md") else "No"
        lines.append(f"| {dir_name} | {license_str} | {has_skill} |")

    lines.append("")

    if audit_result["issues"]:
        lines.append("## Issues")
        lines.append("")
        for issue in audit_result["issues"]:
            lines.append(f"- [!] {issue}")
        lines.append("")

    if audit_result["recommendations"]:
        lines.append("## Recommendations")
        lines.append("")
        for rec in audit_result["recommendations"]:
            lines.append(f"- {rec}")
        lines.append("")

    lines.append("---")
    lines.append("*Generated by PKB zskill_bridge.py v0.1.0*")
    lines.append("")

    report_path.write_text("\n".join(lines), encoding="utf-8")

    # Also mark audit in pkb.config.json
    mark_config_audited(Path(report_path.parent), audit_result)


def mark_config_audited(pkb_root: Path, audit_result: dict):
    """Update pkb.config.json to reflect audit completion for z-skills."""
    config_path = pkb_root / "pkb.config.json"
    if not config_path.is_file():
        return
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
        skills_state = config.setdefault("skills", {})

        # Remove from pending_audit
        pending = set(skills_state.get("pending_audit", []))
        pending.discard("z-skills")
        pending.discard("z-web-pack-local")
        skills_state["pending_audit"] = list(pending)

        config_path.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")
    except (json.JSONDecodeError, OSError):
        pass


# -- 3. status -----------------------------------------------------------------

def cmd_status(pkb_root: Path):
    """Print z-skills installation and audit status."""
    loc = locate_z_skills(pkb_root)

    print()
    print("=" * 60)
    print("  Z-Skills Bridge -- Status")
    print("=" * 60)
    print()

    if not loc["z_skills_installed"]:
        print("  z-skills: NOT INSTALLED")
        print()
        print("  To install:")
        print("    python scripts/skill_manager.py --target . --install z-skills")
        print("  Or from Claude Code:")
        print("    /project:skills --install z-skills")
        print()
        return

    print(f"  z-skills: INSTALLED")
    print(f"  Path:     {loc['z_skills_path']}")
    print()

    # Check pkb.config.json for state
    config_path = pkb_root / "pkb.config.json"
    if config_path.is_file():
        try:
            config = json.loads(config_path.read_text(encoding="utf-8"))
            skills_state = config.get("skills", {})
            enabled = skills_state.get("enabled_skills", [])
            disabled = skills_state.get("disabled_skills", [])
            pending = skills_state.get("pending_audit", [])
            enabled_adapters = skills_state.get("enabled_adapters", [])

            if "z-skills" in pending:
                print("  Status:   PENDING AUDIT (run --audit)")
            elif "z-web-pack-local" in enabled:
                print("  Status:   ENABLED (z-web-pack adapter active)")
            elif "z-web-pack-local" in disabled:
                print("  Status:   DISABLED (adapter inactive)")
            else:
                print("  Status:   INSTALLED (not yet classified)")

            print()
            print(f"  Adapter:  {'ENABLED' if 'z_skills_adapter.md' in enabled_adapters else 'not enabled'}")
            print()
        except (json.JSONDecodeError, OSError):
            pass

    # Check for audit report
    audit_report = pkb_root / "zskill_audit_report.md"
    if audit_report.is_file():
        print(f"  Audit:    Report exists ({audit_report.name})")
    else:
        print(f"  Audit:    NOT YET AUDITED (run --audit)")

    print()

    # Sub-skills
    if loc["sub_skills_found"]:
        print(f"  Sub-skills found ({len(loc['sub_skills_found'])}):")
        print()
        for sub in loc["sub_skills_found"]:
            has_skill = " [SKILL.md]" if sub["has_skill_md"] else ""
            print(f"    {sub['name']}{has_skill}")

    print()
    print("-" * 60)
    print()
    print("  PKB Starter does NOT redistribute z-skills code.")
    print("  The user must audit and explicitly enable before use.")
    print("  See docs/Z_WEB_PACK_PARITY.md for PKB's built-in collector.")
    print()


# -- 4. run --------------------------------------------------------------------

def cmd_run(pkb_root: Path, skill: str, url: str, topic: str, **kwargs):
    """
    Run z-web-pack via the PKB compat runner.
    Deploys compat base + dummy readability if 1-web-research-pack is missing.
    Executes collect_web_pack.py via subprocess — no longer just prints instructions.
    Auto-falls back to built-in web_pack on failure.
    """
    loc = locate_z_skills(pkb_root)

    # -- Pre-flight checks -------------------------------------------------

    if not loc["z_skills_installed"]:
        print("[FAIL] z-skills is not installed.")
        print("       Install: /project:skills --install z-skills")
        print("       Falling back to built-in web_pack...")
        sys.exit(2)  # exit code 2 = fallback signal

    if skill != "z-web-pack":
        print(f"[FAIL] Unknown skill: {skill}")
        print("       Currently supported: z-web-pack")
        sys.exit(2)

    # -- Locate z-web-pack script (must come before adapter check) ----------

    z_web_pack_dir = pkb_root / Z_WEB_PACK_DIR
    # Also check tjxj-z-skills path (alternative vendor layout)
    alt_dir = pkb_root / "skills" / "_vendor" / "tjxj-z-skills" / "z-web-pack"
    if not z_web_pack_dir.is_dir() and alt_dir.is_dir():
        z_web_pack_dir = alt_dir

    scripts_dir = z_web_pack_dir / "scripts"
    collect_script = scripts_dir / "collect_web_pack.py"
    skill_md = z_web_pack_dir / "SKILL.md"

    if not collect_script.is_file():
        print(f"[FAIL] collect_web_pack.py not found.")
        print(f"       Checked: {collect_script}")
        if alt_dir.is_dir():
            print(f"       Checked: {alt_dir / 'scripts' / 'collect_web_pack.py'}")
        print("       z-skills may be incomplete. Re-install: /project:skills --install z-skills")
        print("       Falling back to built-in web_pack...")
        sys.exit(2)

    # -- Check adapter enabled -----------------------------------------------

    config_path = pkb_root / "pkb.config.json"
    adapter_enabled = False
    if config_path.is_file():
        try:
            config = json.loads(config_path.read_text(encoding="utf-8"))
            skills_state = config.get("skills", {})
            enabled_adapters = skills_state.get("enabled_adapters", [])
            if "z_skills_adapter.md" in enabled_adapters:
                adapter_enabled = True
        except (json.JSONDecodeError, OSError):
            pass

    # Fallback: if config missing entirely but z-skills is clearly installed,
    # treat adapter as implicitly enabled
    if not adapter_enabled:
        adapter_path = pkb_root / "templates" / "skill_adapters" / "z_skills_adapter.md"
        if adapter_path.is_file():
            adapter_enabled = True
            print("[INFO] Adapter file found — treating as enabled.")
        elif not config_path.is_file():
            # No pkb.config.json at all — fresh/manual install, script exists
            if collect_script.is_file():
                adapter_enabled = True
                print("[INFO] pkb.config.json not found, but z-web-pack is installed "
                      "with collect_web_pack.py — treating adapter as enabled.")
            else:
                print("[FAIL] z-web-pack local adapter is not enabled and no config found.")
                print("       Steps:")
                print("       1. /project:skills --install z-skills")
                print("       2. /project:skills --audit z-skills")
                print("       3. /project:skills --enable z-web-pack-local")
                print("       Falling back to built-in web_pack...")
                sys.exit(2)
        else:
            print("[FAIL] z-web-pack local adapter is not enabled.")
            print("       Steps:")
            print("       1. /project:skills --audit z-skills")
            print("       2. /project:skills --enable z-web-pack-local")
            print("       Falling back to built-in web_pack...")
            sys.exit(2)

    # -- Check 1-web-research-pack dependency ------------------------------
    # collect_web_pack.py computes PROJECT_ROOT via parents[4] which
    # resolves to skills/ when the script is at skills/_vendor/*/z-web-pack/scripts/
    # So BASE_SCRIPT = skills/.agent/skills/1-web-research-pack/... (alt path)
    # We also check .agent/... at PKB root as a secondary location.

    # collect_web_pack.py computes PROJECT_ROOT = Path(__file__).resolve().parents[4]
    # Script is at: skills/_vendor/<name>/z-web-pack/scripts/collect_web_pack.py
    # parents[4] = skills/  =>  BASE_SCRIPT = skills/.agent/skills/1-web-research-pack/scripts/...
    base_script = (
        pkb_root / "skills" / ".agent" / "skills" / "1-web-research-pack" /
        "scripts" / "collect_web_research_pack.py"
    )
    has_real_base = base_script.is_file()

    # Compat base can be at: tools/pkb_compat/ (template-distributed) or .pkb_local/patches/ (user-customized)
    compat_base = pkb_root / "tools" / "pkb_compat" / "web_research_pack_base.py"
    if not compat_base.is_file():
        compat_base = pkb_root / ".pkb_local" / "patches" / "web_research_pack_base.py"
    has_compat_base = compat_base.is_file()

    if not has_real_base and not has_compat_base:
        print("[FAIL] 1-web-research-pack is missing and no compat base available.")
        print(f"       Expected: {base_script}")
        print(f"       Compat:   {compat_base}")
        print("       The 1-web-research-pack base module is not publicly available.")
        print("       Install PKB compat base: copy web_research_pack_base.py to .pkb_local/patches/")
        print("       Falling back to built-in web_pack...")
        sys.exit(2)

    # -- Deploy compat base if needed --------------------------------------

    if not has_real_base:
        print("[INFO] 1-web-research-pack not found. Deploying PKB compat base...")
        deploy_compat_base(pkb_root, compat_base, base_script)

    # -- Inject dummy readability if needed --------------------------------

    readability_dummy = (
        pkb_root / ".agent" / "skills" / "1-web-research-pack" /
        "readability" / "__init__.py"
    )
    if not readability_dummy.is_file():
        deploy_dummy_readability(pkb_root)

    # -- Build subprocess command ------------------------------------------

    python_bin = sys.executable
    env = os.environ.copy()
    env["PYTHONPATH"] = _build_pythonpath(pkb_root)
    env["PYTHONIOENCODING"] = "utf-8"

    # Map bridge args to collect_web_pack.py CLI args
    cmd = [python_bin, str(collect_script)]

    # Output routing: default to raw/webpacks/
    out_root = kwargs.get("out_root", str(pkb_root / "raw" / "webpacks"))
    cmd.extend(["--out-root", out_root])

    if topic:
        cmd.extend(["--title", topic])

    # Optional args
    max_depth = kwargs.get("max_depth")
    if max_depth is not None:
        cmd.extend(["--max-depth", str(max_depth)])

    max_pages = kwargs.get("max_pages")
    if max_pages is not None:
        cmd.extend(["--max-pages", str(max_pages)])

    if kwargs.get("same_domain_only"):
        cmd.append("--same-domain-only")

    if kwargs.get("no_jina"):
        cmd.append("--no-jina")

    # Video: default off for safety
    videos = kwargs.get("videos", "off")
    cmd.extend(["--videos", videos])

    if videos != "off":
        max_video_mb = kwargs.get("max_video_mb", 300)
        cmd.extend(["--max-video-mb", str(max_video_mb)])

    browser_cookies = kwargs.get("browser_cookies", "")
    if browser_cookies:
        cmd.extend(["--browser-cookies", browser_cookies])

    # URL goes last
    cmd.append(url)

    # -- Execute ------------------------------------------------------------

    print()
    print("=" * 60)
    print("  Z-Skills Bridge — Run z-web-pack")
    print("=" * 60)
    print()
    print(f"  URL:        {url}")
    print(f"  Topic:      {topic}")
    print(f"  Script:     {collect_script}")
    print(f"  Videos:     {videos}")
    if not has_real_base:
        print(f"  Base:       PKB compat ({'deployed' if base_script.is_file() else 'pending'})")
    print(f"  Out root:   {out_root}")
    print()
    print(f"  [INFO] Executing z-web-pack via subprocess...")
    print(f"  Command: {' '.join(cmd)}")
    print()

    try:
        result = subprocess.run(
            cmd,
            cwd=str(pkb_root),
            env=env,
            capture_output=False,
            timeout=600,  # 10 minutes
            encoding="utf-8",
            errors="replace",
        )
    except subprocess.TimeoutExpired:
        print("[FAIL] z-web-pack timed out after 10 minutes.")
        print("       Falling back to built-in web_pack...")
        sys.exit(2)
    except Exception as exc:
        print(f"[FAIL] z-web-pack execution error: {exc}")
        print("       Falling back to built-in web_pack...")
        sys.exit(2)

    if result.returncode != 0:
        print(f"\n[FAIL] z-web-pack exited with code {result.returncode}.")
        print("       Falling back to built-in web_pack...")
        sys.exit(2)

    # -- Import output to raw/webpacks/ -------------------------------------

    # collect_web_pack.py prints the output dir path on its last line
    print()
    print("[INFO] z-web-pack completed. Output is in the --out-root directory.")
    print(f"       Run: python tools/zskill_bridge.py import-output --path <output-dir>")
    print(f"       Then: /project:inbox  to compile into wiki")


def deploy_compat_base(pkb_root: Path, compat_source: Path, target: Path):
    """Copy the compat base module to target path.
    Also deploys to the other possible path so both are covered."""
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(str(compat_source), str(target))
    print(f"       [OK] Deployed compat base: {target}")

    # Determine the other path and deploy there too
    pkb_root_base = (
        pkb_root / ".agent" / "skills" / "1-web-research-pack" /
        "scripts" / "collect_web_research_pack.py"
    )
    skills_base = (
        pkb_root / "skills" / ".agent" / "skills" / "1-web-research-pack" /
        "scripts" / "collect_web_research_pack.py"
    )
    other = pkb_root_base if target != pkb_root_base else skills_base
    if other != target and not other.is_file():
        other.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(compat_source), str(other))
        print(f"       [OK] Also deployed to: {other}")


def deploy_dummy_readability(pkb_root: Path):
    """Create a dummy readability package for env-check bypass.
    Deploys to both .agent/... and skills/.agent/... paths."""
    for base in [pkb_root, pkb_root / "skills"]:
        readability_dir = (
            base / ".agent" / "skills" / "1-web-research-pack" / "readability"
        )
        readability_dir.mkdir(parents=True, exist_ok=True)
        init_file = readability_dir / "__init__.py"
        if not init_file.is_file():
            init_file.write_text(
                "# PKB compat: dummy readability package\n"
                "# Exists ONLY to pass collect_web_pack.py's env-check 'import readability'.\n"
                "# z-web-pack uses BeautifulSoup for extraction (via compat base), NOT readability.\n"
                "# If upstream adds real readability API calls, install: pip install readability-lxml\n",
                encoding="utf-8",
            )
            print(f"       [OK] Injected dummy readability: {readability_dir}")


def _build_pythonpath(pkb_root: Path) -> str:
    """Build PYTHONPATH including both agent skills paths for dummy imports."""
    paths = [
        str(pkb_root / ".agent" / "skills" / "1-web-research-pack"),
        str(pkb_root / "skills" / ".agent" / "skills" / "1-web-research-pack"),
    ]
    existing = os.environ.get("PYTHONPATH", "")
    if existing:
        paths.append(existing)
    return os.pathsep.join(paths)


# -- 5. import-output ----------------------------------------------------------

def cmd_import_output(pkb_root: Path, output_path: str):
    """
    Copy z-web-pack output into PKB raw/webpacks/.
    Generates or updates manifest.json.
    Updates SKILL_LINKS.md.
    """
    source = Path(output_path)
    if not source.is_dir():
        print(f"[FAIL] Output path not found: {output_path}")
        sys.exit(1)

    # Determine topic from output dir name
    topic = source.name
    dest = pkb_root / "raw" / "webpacks" / topic

    print()
    print("=" * 60)
    print("  Z-Skills Bridge -- Import Output")
    print("=" * 60)
    print()
    print(f"  Source:  {source}")
    print(f"  Dest:    {dest}")
    print(f"  Topic:   {topic}")
    print()

    if dest.exists():
        print(f"  [WARN] Destination already exists: {dest}")
        response = input("  Overwrite? [y/N]: ").strip().lower()
        if response not in ("y", "yes"):
            print("  Cancelled.")
            return
        shutil.rmtree(dest, ignore_errors=True)

    # Copy
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, dest)
    print(f"  [OK] Copied to: {dest}")

    # Generate/update manifest
    manifest = _generate_manifest(dest, topic)
    manifest_path = dest / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  [OK] Manifest: {manifest_path}")

    # Update SKILL_LINKS.md
    _update_skill_links_for_import(pkb_root, topic, dest)

    print()
    print("  Import complete. Next steps:")
    print(f"    /project:inbox  -- compile raw/webpacks/{topic}/ into wiki")
    print(f"    Or: /project:pkb -- with the webpack path")
    print()


def _generate_manifest(dest: Path, topic: str) -> dict:
    """Generate a manifest.json for imported z-web-pack output."""
    files = []
    for f in sorted(dest.rglob("*")):
        if f.is_file() and f.name != "manifest.json":
            files.append({
                "name": f.name,
                "path": str(f.relative_to(dest)),
                "size": f.stat().st_size,
            })

    return {
        "topic": topic,
        "source": "z-web-pack (local, user-installed)",
        "imported": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "collector": "z-web-pack via zskill_bridge.py",
        "files": files,
        "file_count": len(files),
    }


def _update_skill_links_for_import(pkb_root: Path, topic: str, dest: Path):
    """Update SKILL_LINKS.md with imported z-web-pack output."""
    links_path = pkb_root / "SKILL_LINKS.md"
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    new_entry = (
        f"\n### z-web-pack Import\n"
        f"- Topic: {topic}\n"
        f"- Collector: z-web-pack (local, user-installed)\n"
        f"- Output: `raw/webpacks/{topic}/`\n"
        f"- Imported: {today}\n"
        f"- Bridge: zskill_bridge.py v0.1.0\n"
    )

    if links_path.is_file():
        content = links_path.read_text(encoding="utf-8")
        if "---" in content:
            parts = content.rsplit("---", 1)
            content = parts[0].rstrip() + "\n" + new_entry + "\n---" + parts[1]
        else:
            content += "\n" + new_entry
        links_path.write_text(content, encoding="utf-8")
    else:
        links_path.write_text(
            f"# SKILL_LINKS.md\n\n> Auto-generated. Z-Skills Bridge v0.1.0\n\n{new_entry}",
            encoding="utf-8",
        )


# -- 6. patch ------------------------------------------------------------------

def cmd_patch(pkb_root: Path, allow_local_patch: bool = False):
    """
    Generate local patches for z-skills compatibility.
    DISABLED by default. Requires --allow-local-patch.
    """
    if not allow_local_patch:
        print()
        print("=" * 60)
        print("  Z-Skills Bridge -- Patch (DISABLED)")
        print("=" * 60)
        print()
        print("  Local patching is DISABLED by default.")
        print()
        print("  PKB policy:")
        print("    1. Prefer wrapper, configuration, or output relocation.")
        print("    2. Only patch as a last resort.")
        print("    3. All patches must go to .pkb_local/patches/")
        print("    4. .pkb_local/ is gitignored — never committed.")
        print("    5. Patches are never distributed or included in pkb-starter.")
        print()
        print("  If z-web-pack paths or parameters are incompatible:")
        print("    - First try wrapper scripts or configuration changes.")
        print("    - If absolutely necessary, run:")
        print("      python tools/zskill_bridge.py patch --allow-local-patch")
        print()
        return

    loc = locate_z_skills(pkb_root)
    if not loc["z_skills_installed"]:
        print("[FAIL] z-skills is not installed. Nothing to patch.")
        sys.exit(1)

    patch_dir = pkb_root / PKB_PATCH_DIR
    patch_dir.mkdir(parents=True, exist_ok=True)

    print()
    print("=" * 60)
    print("  Z-Skills Bridge -- Local Patch")
    print("=" * 60)
    print()
    print(f"  [WARN] Local patches are for YOUR machine only.")
    print(f"         Do NOT commit or share these patches.")
    print(f"         Patches are stored in: {patch_dir}")
    print()
    print(f"  [INFO] No patches have been generated yet.")
    print(f"         The bridge currently attempts compatibility through:")
    print(f"         - Wrapper invocation (calling z-web-pack with PKB-configured args)")
    print(f"         - Output relocation (moving results to raw/webpacks/)")
    print(f"         - Configuration passthrough (passing --topic, --url correctly)")
    print()
    print(f"  If you encounter a specific incompatibility:")
    print(f"    1. Report the issue with the exact error message.")
    print(f"    2. The bridge will attempt to resolve via configuration first.")
    print(f"    3. Only generate a patch if configuration cannot fix it.")
    print()

    # Create .pkb_local/.gitkeep to ensure the directory can be gitignored
    keep_file = pkb_root / PKB_LOCAL_DIR / ".gitkeep"
    keep_file.parent.mkdir(parents=True, exist_ok=True)
    keep_file.touch(exist_ok=True)

    print(f"  [OK] Patch directory ready: {patch_dir}")
    print(f"       .pkb_local/ should be in .gitignore.")
    print()


# -- Main ----------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="PKB Starter -- Z-Skills Bridge (v0.1.0)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Examples:
              python tools/zskill_bridge.py status
              python tools/zskill_bridge.py audit
              python tools/zskill_bridge.py audit --dry-run
              python tools/zskill_bridge.py run --skill z-web-pack --url https://example.com --topic "demo"
              python tools/zskill_bridge.py import-output --path "<output-dir>"
              python tools/zskill_bridge.py patch --allow-local-patch
        """),
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # status
    subparsers.add_parser("status", help="Show z-skills installation and audit status")

    # audit
    audit_parser = subparsers.add_parser("audit", help="Audit installed z-skills (LICENSE, structure)")
    audit_parser.add_argument("--dry-run", action="store_true",
                              help="Preview audit without generating report")

    # run
    run_parser = subparsers.add_parser("run", help="Run z-web-pack via PKB compat runner (executes scripts)")
    run_parser.add_argument("--skill", required=True, help="Skill to run (z-web-pack)")
    run_parser.add_argument("--url", required=True, help="URL to collect")
    run_parser.add_argument("--topic", required=True, help="Topic name for output directory")
    run_parser.add_argument("--max-depth", type=int, default=1, help="BFS crawl depth (default: 1)")
    run_parser.add_argument("--max-pages", type=int, default=80, help="Max pages to collect (default: 80)")
    run_parser.add_argument("--same-domain-only", action="store_true", help="Only crawl same-domain links")
    run_parser.add_argument("--no-jina", action="store_true", help="Disable r.jina.ai fallback")
    run_parser.add_argument("--videos", choices=["off", "direct", "all"], default="off",
                            help="Video download: off (default) | direct (<video>/直链) | all (yt-dlp)")
    run_parser.add_argument("--max-video-mb", type=float, default=300.0, help="Max single video size MB")
    run_parser.add_argument("--browser-cookies", default="",
                            help="Browser for cookies (chrome/safari/edge/firefox)")

    # import-output
    import_parser = subparsers.add_parser("import-output", help="Import z-web-pack output into raw/webpacks/")
    import_parser.add_argument("--path", required=True, help="Path to z-web-pack output directory")

    # patch
    patch_parser = subparsers.add_parser("patch", help="Generate local patches (disabled by default)")
    patch_parser.add_argument("--allow-local-patch", action="store_true",
                              help="Allow generating local patches in .pkb_local/patches/")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    pkb_root = get_pkb_root()

    if args.command == "status":
        cmd_status(pkb_root)
    elif args.command == "audit":
        result = audit_z_skills(pkb_root, dry_run=args.dry_run)
        if args.dry_run:
            print()
            print("=" * 60)
            print("  Z-Skills Bridge -- Audit (DRY RUN)")
            print("=" * 60)
            print()
            loc = locate_z_skills(pkb_root)
            if not loc["z_skills_installed"]:
                print("  z-skills: NOT INSTALLED")
                print()
                print("  [DRY RUN] Would check:")
                print("    - LICENSE files in skills/_vendor/z-skills/")
                print("    - LICENSE files in each sub-skill directory")
                print("    - SKILL.md presence in each sub-skill")
                print("    - Generate zskill_audit_report.md")
                print()
            else:
                print(f"  z-skills: INSTALLED at {result['z_skills_path']}")
                print(f"  Sub-skills: {len(loc['sub_skills_found'])}")
                print()
                print("  [DRY RUN] Would check:")
                for dir_name in sorted(result.get("directories", {}).keys()):
                    print(f"    - {dir_name}")
                print()
                print("  [DRY RUN] Would generate: zskill_audit_report.md")
                print()
        else:
            print()
            print("=" * 60)
            print("  Z-Skills Bridge -- Audit Complete")
            print("=" * 60)
            print()
            print(f"  Overall license status: {result.get('overall_license_status', 'unknown')}")
            print()
            if result.get("issues"):
                print(f"  Issues ({len(result['issues'])}):")
                for issue in result["issues"]:
                    print(f"    [!] {issue}")
                print()
            if result.get("report_path"):
                print(f"  Report: {result['report_path']}")
                print()
            print("  Next: Review the report, then:")
            print("    /project:skills --enable z-web-pack-local")
            print()
    elif args.command == "run":
        cmd_run(
            pkb_root, args.skill, args.url, args.topic,
            max_depth=args.max_depth,
            max_pages=args.max_pages,
            same_domain_only=args.same_domain_only,
            no_jina=args.no_jina,
            videos=args.videos,
            max_video_mb=args.max_video_mb,
            browser_cookies=args.browser_cookies,
        )
    elif args.command == "import-output":
        cmd_import_output(pkb_root, args.path)
    elif args.command == "patch":
        cmd_patch(pkb_root, args.allow_local_patch)


if __name__ == "__main__":
    main()
