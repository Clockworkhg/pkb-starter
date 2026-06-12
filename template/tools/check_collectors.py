#!/usr/bin/env python3
"""
PKB Starter — Web Collector Availability Checker (v0.1.0)

Detects all available web collectors and recommends the best one.
Always run before any web collection operation.

Usage:
    python tools/check_collectors.py                # Human-readable status report
    python tools/check_collectors.py --json         # Machine-readable JSON
    python tools/check_collectors.py --recommend    # Print recommended collector name
    python tools/check_collectors.py --quiet        # Exit 0 if any available, 1 if none

Collector priority:
    1. z-web-pack (local, user-installed) — requires all 10 checks pass
    2. PKB built-in web_pack               — requires Python deps
    3. WebFetch (Claude Code built-in)     — always available
    4. gstack (headless browser)           — requires skill registration

Key invariant: never fail because a collector is missing. Always walk the fallback chain.
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path


# -- Path resolution ------------------------------------------------------------

def get_pkb_root() -> Path:
    """Walk up from cwd looking for pkb.config.json. Fall back to PKB_ROOT env var."""
    cwd = Path.cwd()
    for parent in [cwd] + list(cwd.parents):
        if (parent / "pkb.config.json").is_file():
            return parent
    env = os.environ.get("PKB_ROOT", "")
    if env:
        return Path(env)
    return cwd


# -- Utility --------------------------------------------------------------------

def load_config(pkb_root: Path) -> dict:
    """Load pkb.config.json, returning empty dict on any failure."""
    config_path = pkb_root / "pkb.config.json"
    if not config_path.is_file():
        return {}
    try:
        return json.loads(config_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


# -- Collector 1: z-web-pack ---------------------------------------------------

MACOS_PATH_PATTERNS = [
    re.compile(r'/Users/'),
    re.compile(r'~/Library/'),
    re.compile(r'/Applications/'),
    re.compile(r'/usr/local/'),
    re.compile(r'/opt/homebrew'),
    re.compile(r'brew\s'),
    re.compile(r'\bdarwin\b', re.IGNORECASE),
    re.compile(r'/Library/'),
]


def check_z_web_pack(pkb_root: Path) -> dict:
    """Detect z-web-pack availability across 12 dimensions."""
    checks = {}
    warnings = []

    # 1. z_skills_installed (check both possible names)
    z_skills_dir = pkb_root / "skills" / "_vendor" / "z-skills"
    alt_skills_dir = pkb_root / "skills" / "_vendor" / "tjxj-z-skills"
    z_skills_found = z_skills_dir.is_dir() or alt_skills_dir.is_dir()
    effective_skills_dir = z_skills_dir if z_skills_dir.is_dir() else alt_skills_dir
    checks["z_skills_installed"] = {
        "ok": z_skills_found,
        "detail": f"skills/_vendor/z-skills/ {'exists' if z_skills_dir.is_dir() else 'NOT FOUND'}"
                  + (f" (found tjxj-z-skills)" if alt_skills_dir.is_dir() and not z_skills_dir.is_dir() else "")
    }

    # 2. z_web_pack_dir
    z_web_pack_dir = effective_skills_dir / "z-web-pack"
    checks["z_web_pack_dir"] = {
        "ok": z_web_pack_dir.is_dir(),
        "detail": f"z-web-pack/ directory {'exists' if z_web_pack_dir.is_dir() else 'NOT FOUND'}"
    }

    # 3. skill_md
    skill_md = z_web_pack_dir / "SKILL.md"
    checks["skill_md"] = {
        "ok": skill_md.is_file(),
        "detail": f"SKILL.md {'found' if skill_md.is_file() else 'NOT FOUND'}"
    }

    # 4. scripts_dir
    scripts_dir = z_web_pack_dir / "scripts"
    checks["scripts_dir"] = {
        "ok": scripts_dir.is_dir(),
        "detail": f"scripts/ directory {'exists' if scripts_dir.is_dir() else 'NOT FOUND'}"
    }

    # 5. collect_script
    collect_script = scripts_dir / "collect_web_pack.py"
    checks["collect_script"] = {
        "ok": collect_script.is_file(),
        "detail": f"collect_web_pack.py {'found' if collect_script.is_file() else 'NOT FOUND'}"
    }

    # 6a. Real 1-web-research-pack dependency (check both possible paths)
    base_script_real = (
        pkb_root / ".agent" / "skills" / "1-web-research-pack" /
        "scripts" / "collect_web_research_pack.py"
    )
    alt_base_script_real = (
        pkb_root / "skills" / ".agent" / "skills" / "1-web-research-pack" /
        "scripts" / "collect_web_research_pack.py"
    )
    has_real_base = base_script_real.is_file() or alt_base_script_real.is_file()

    # 6b. PKB compat base (tools/pkb_compat/ or .pkb_local/patches/)
    compat_base = pkb_root / "tools" / "pkb_compat" / "web_research_pack_base.py"
    if not compat_base.is_file():
        compat_base = pkb_root / ".pkb_local" / "patches" / "web_research_pack_base.py"
    has_compat_base = compat_base.is_file()

    # 6c. Dummy readability
    readability_dummy = (
        pkb_root / ".agent" / "skills" / "1-web-research-pack" /
        "readability" / "__init__.py"
    )

    if has_real_base:
        checks["research_pack_dep"] = {
            "ok": True,
            "detail": "1-web-research-pack found (real base module)"
        }
    elif has_compat_base:
        checks["research_pack_dep"] = {
            "ok": True,
            "detail": "PKB compat base available at .pkb_local/patches/web_research_pack_base.py"
        }
        warnings.append("Using PKB compat base — not the original 1-web-research-pack. "
                       "readability-lxml is NOT used (BS4 fallback).")
    else:
        checks["research_pack_dep"] = {
            "ok": False,
            "detail": "1-web-research-pack NOT FOUND. "
                      "Compat base also NOT FOUND at .pkb_local/patches/web_research_pack_base.py. "
                      "z-web-pack cannot run without this dependency."
        }

    # 7. macOS hardcoded paths
    if scripts_dir.is_dir():
        macos_findings = scan_for_macos_paths(scripts_dir)
        if macos_findings:
            is_macos = sys.platform == "darwin"
            checks["macos_paths"] = {
                "ok": is_macos,
                "detail": (f"Hardcoded macOS paths detected ({len(macos_findings)} matches): "
                          + "; ".join(macos_findings[:5])
                          + ("..." if len(macos_findings) > 5 else ""))
            }
            if not is_macos:
                warnings.append(
                    f"Scripts contain macOS-specific paths ({len(macos_findings)} matches) "
                    f"but current platform is {sys.platform}"
                )
        else:
            checks["macos_paths"] = {
                "ok": True,
                "detail": "No hardcoded macOS paths detected"
            }
    else:
        checks["macos_paths"] = {
            "ok": True,
            "detail": "Scripts directory not found — skipped macOS path scan"
        }

    # 8. Windows compatibility
    if scripts_dir.is_dir():
        compat = check_windows_compat(scripts_dir)
        checks["windows_compat"] = compat
        if not compat["ok"]:
            warnings.append(compat["detail"])
    else:
        checks["windows_compat"] = {
            "ok": True,
            "detail": "Scripts directory not found — skipped Windows compat check"
        }

    # 9. Bridge execution capability
    bridge_check = check_bridge_execution(pkb_root)
    checks["bridge_execution"] = bridge_check
    if not bridge_check["ok"]:
        warnings.append(
            "z-web-pack requires manual SKILL.md invocation in Claude Code "
            "— bridge does not auto-execute scripts"
        )

    # 10. Adapter enabled
    config = load_config(pkb_root)
    enabled_adapters = config.get("skills", {}).get("enabled_adapters", [])
    adapter_ok = "z_skills_adapter.md" in enabled_adapters
    checks["adapter_enabled"] = {
        "ok": adapter_ok,
        "detail": (
            "z_skills_adapter.md is enabled in pkb.config.json"
            if adapter_ok
            else "z_skills_adapter.md is NOT enabled in pkb.config.json"
            if config
            else "pkb.config.json not found — cannot verify adapter status"
        )
    }
    if not adapter_ok:
        warnings.append("Run /project:skills --enable z-web-pack-local to activate the adapter")

    # Compute aggregate status
    critical_keys = ["z_skills_installed", "z_web_pack_dir", "skill_md",
                     "scripts_dir", "collect_script"]
    all_critical_ok = all(checks.get(k, {}).get("ok", False) for k in critical_keys)

    if not all_critical_ok:
        status = "unavailable"
        failed_critical = [k for k in critical_keys if not checks.get(k, {}).get("ok", False)]
        warnings.insert(0, f"Critical components missing: {', '.join(failed_critical)}")
    else:
        # research_pack_dep is a hard requirement — cannot run without it
        if not checks.get("research_pack_dep", {}).get("ok", False):
            status = "unavailable"
            warnings.insert(0, "Missing base dependency: 1-web-research-pack (no real module, no compat base)")
        else:
            # With base module available, check runtime readiness
            runtime_keys = ["bridge_execution", "adapter_enabled",
                           "macos_paths", "windows_compat"]
            runtime_fail = any(
                not checks.get(k, {}).get("ok", False) for k in runtime_keys
            )
            if runtime_fail:
                status = "degraded"
                if not checks.get("bridge_execution", {}).get("ok", False):
                    warnings.append("Bridge cannot execute scripts — update pkb-starter")
                if not checks.get("adapter_enabled", {}).get("ok", False):
                    warnings.append("Adapter not enabled — run /project:skills --enable z-web-pack-local")
            else:
                status = "available"

    return {
        "name": "z-web-pack (local, user-installed)",
        "status": status,
        "priority": 1,
        "checks": checks,
        "warnings": warnings,
    }


def scan_for_macos_paths(scripts_dir: Path) -> list[str]:
    """Scan .py and .sh files under scripts_dir for hardcoded macOS paths."""
    findings = []
    for ext in (".py", ".sh", ".bash"):
        try:
            for f in scripts_dir.rglob(f"*{ext}"):
                try:
                    content = f.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue
                for pattern in MACOS_PATH_PATTERNS:
                    for match in pattern.finditer(content):
                        findings.append(f"{f.name}:{match.group(0)}")
                        if len(findings) >= 20:
                            return findings
        except OSError:
            continue
    return findings


def check_windows_compat(scripts_dir: Path) -> dict:
    """Check if scripts handle Windows platform."""
    is_windows = sys.platform == "win32"
    handles_platform = False
    has_windows_ref = False

    try:
        for f in scripts_dir.rglob("*.py"):
            try:
                content = f.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if re.search(r'sys\.platform|os\.name|platform\.system\(\)', content):
                handles_platform = True
                if re.search(r"'nt'|\"nt\"|'win32'|\"win32\"", content):
                    has_windows_ref = True
                    break
    except OSError:
        pass

    if is_windows and not handles_platform:
        return {
            "ok": False,
            "detail": "No platform detection in scripts — may assume macOS/Linux"
        }
    elif is_windows and handles_platform and not has_windows_ref:
        return {
            "ok": False,
            "detail": "Platform detection found but no Windows ('nt'/'win32') handling"
        }
    elif is_windows and has_windows_ref:
        return {
            "ok": True,
            "detail": "Windows platform handling detected in scripts"
        }
    else:
        return {
            "ok": True,
            "detail": f"Platform is {sys.platform} — Windows compat check not applicable"
        }


def check_bridge_execution(pkb_root: Path) -> dict:
    """Check if zskill_bridge.py cmd_run() actually executes scripts (v0.2+)."""
    bridge_path = pkb_root / "tools" / "zskill_bridge.py"
    if not bridge_path.is_file():
        return {"ok": False, "detail": "tools/zskill_bridge.py NOT FOUND"}

    try:
        content = bridge_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {"ok": False, "detail": "Cannot read tools/zskill_bridge.py"}

    # Check for subprocess.run() in cmd_run — indicates actual execution
    has_exec = bool(re.search(r'subprocess\.(run|Popen|call|check_output)', content))
    # Check for compat base deployment — indicates PKB bridge v0.2+
    has_compat = "deploy_compat_base" in content

    if has_exec and has_compat:
        return {
            "ok": True,
            "detail": "Bridge v0.2+ supports real subprocess execution + compat base deployment"
        }
    elif has_exec:
        return {
            "ok": True,
            "detail": "Bridge supports subprocess execution (no compat base deployment detected)"
        }
    return {
        "ok": False,
        "detail": "Bridge v0.1 — does NOT execute scripts (prints instructions only). "
                  "Update pkb-starter to v0.6.5+ for bridge execution support."
    }


# -- Collector 2: Built-in web_pack --------------------------------------------

def check_builtin_web_pack(pkb_root: Path) -> dict:
    """Detect PKB built-in web_pack availability."""
    checks = {}

    web_pack_path = pkb_root / "tools" / "web_pack.py"
    checks["script_exists"] = {
        "ok": web_pack_path.is_file(),
        "detail": f"tools/web_pack.py {'exists' if web_pack_path.is_file() else 'NOT FOUND'}"
    }

    # Required: requests
    try:
        import requests  # noqa: F401
        checks["requests"] = {"ok": True, "detail": "requests importable"}
    except ImportError:
        checks["requests"] = {"ok": False, "detail": "requests NOT installed — run: pip install requests"}

    # Required: BeautifulSoup (bs4)
    try:
        import bs4  # noqa: F401
        checks["beautifulsoup4"] = {"ok": True, "detail": "beautifulsoup4 importable"}
    except ImportError:
        checks["beautifulsoup4"] = {
            "ok": False,
            "detail": "beautifulsoup4 NOT installed — run: pip install beautifulsoup4"
        }

    # Optional: markdownify (graceful fallback if missing)
    try:
        import markdownify  # noqa: F401
        checks["markdownify"] = {"ok": True, "detail": "markdownify importable"}
    except ImportError:
        checks["markdownify"] = {
            "ok": True,  # optional — treated as ok with warning
            "detail": "markdownify NOT installed (optional) — plain-text output only. "
                      "run: pip install markdownify"
        }

    script_ok = checks["script_exists"]["ok"]
    deps_ok = checks["requests"]["ok"] and checks["beautifulsoup4"]["ok"]

    if not script_ok:
        status = "unavailable"
    elif deps_ok:
        status = "available"
    else:
        status = "unavailable"

    return {
        "name": "PKB built-in web_pack (v0.1.0)",
        "status": status,
        "priority": 2,
        "checks": checks,
    }


# -- Collector 3: WebFetch -----------------------------------------------------

def check_webfetch() -> dict:
    """WebFetch is always available as a Claude Code built-in tool."""
    return {
        "name": "WebFetch (Claude Code built-in)",
        "status": "available",
        "priority": 3,
        "checks": {
            "always_available": {
                "ok": True,
                "detail": "WebFetch is a built-in Claude Code tool — always available"
            }
        },
        "note": "Single-page fetch only. No image download, no depth crawling, no structured webpack output."
    }


# -- Collector 4: gstack -------------------------------------------------------

def check_gstack(pkb_root: Path) -> dict:
    """Detect gstack headless browser availability."""
    checks = {}

    gstack_dir = pkb_root / "skills" / "gstack"
    checks["gstack_dir"] = {
        "ok": gstack_dir.is_dir(),
        "detail": f"skills/gstack/ {'exists' if gstack_dir.is_dir() else 'not found'}"
    }

    # Check settings.json for gstack reference
    settings_path = pkb_root / ".claude" / "settings.json"
    has_ref = False
    if settings_path.is_file():
        try:
            settings = json.loads(settings_path.read_text(encoding="utf-8"))
            settings_str = json.dumps(settings)
            has_ref = "gstack" in settings_str.lower()
        except (json.JSONDecodeError, OSError):
            pass

    checks["settings_ref"] = {
        "ok": has_ref,
        "detail": f"gstack {'referenced' if has_ref else 'not referenced'} in .claude/settings.json"
    }

    status = "available" if (gstack_dir.is_dir() or has_ref) else "unavailable"

    return {
        "name": "gstack (headless browser)",
        "status": status,
        "priority": 4,
        "checks": checks,
        "note": "Best for JS-heavy pages and complex interactions. Requires gstack skill to be registered."
    }


# -- Recommendation engine -----------------------------------------------------

def recommend(collectors: list[dict]) -> dict:
    """
    Walk collectors in priority order. First AVAILABLE wins.
    If none available, try DEGRADED. WebFetch is always available so this always succeeds.
    """
    for status_level in ["available", "degraded"]:
        for c in sorted(collectors, key=lambda x: x["priority"]):
            if c["status"] == status_level:
                fallback_chain = [
                    x["name"] for x in sorted(collectors, key=lambda x: x["priority"])
                    if x["priority"] > c["priority"] and x["status"] in ("available", "degraded")
                ]
                return {
                    "collector": c["name"],
                    "priority": c["priority"],
                    "reason": (
                        f"Selected {c['name']} (priority {c['priority']}) as best available collector"
                    ),
                    "fallback_chain": fallback_chain,
                }

    # Unreachable — WebFetch is always available
    return {
        "collector": "WebFetch (Claude Code built-in)",
        "priority": 3,
        "reason": "Ultimate fallback — no other collector available",
        "fallback_chain": [],
    }


# -- Human-readable output -----------------------------------------------------

def print_human_readable(collectors: list[dict], recommendation: dict, pkb_root: Path):
    """Print a human-readable collector status report."""
    print()
    print("=" * 60)
    print("  PKB Collector Availability Check")
    print(f"  PKB Root: {pkb_root}")
    print("=" * 60)

    for c in sorted(collectors, key=lambda x: x["priority"]):
        print()
        status_label = c["status"].upper()
        print(f"  Collector {c['priority']}: {c['name']}")
        print(f"  Status:   {status_label} (priority {c['priority']})")

        for check_name, check_info in c.get("checks", {}).items():
            mark = "[OK]" if check_info["ok"] else "[FAIL]"
            print(f"    {mark:<8} {check_info['detail']}")

        if c.get("note"):
            print(f"    [NOTE]   {c['note']}")

        if c.get("warnings"):
            print(f"    [!] Warnings:")
            for w in c["warnings"]:
                print(f"      - {w}")

    print()
    print("--- Recommendation ---")
    print(f"  Best collector: {recommendation['collector']}")
    print(f"  Reason: {recommendation['reason']}")
    if recommendation.get("fallback_chain"):
        print(f"  Fallback chain: {' -> '.join(recommendation['fallback_chain'])}")
    print()


# -- Main -----------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="PKB Starter — Web Collector Availability Checker (v0.1.0)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--json", action="store_true",
                        help="Machine-readable JSON output")
    parser.add_argument("--recommend", action="store_true",
                        help="Print only the recommended collector name")
    parser.add_argument("--quiet", action="store_true",
                        help="Exit 0 if any collector available, 1 if none")
    args = parser.parse_args()

    pkb_root = get_pkb_root()

    # Run all checks
    collectors = [
        check_z_web_pack(pkb_root),
        check_builtin_web_pack(pkb_root),
        check_webfetch(),
        check_gstack(pkb_root),
    ]

    rec = recommend(collectors)

    if args.recommend:
        print(rec["collector"])
        return 0

    if args.quiet:
        any_available = any(
            c["status"] in ("available", "degraded") for c in collectors
        )
        return 0 if any_available else 1

    if args.json:
        report = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "pkb_root": str(pkb_root),
            "collectors": {_key(c): c for c in collectors},
            "recommendation": rec,
        }
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0

    print_human_readable(collectors, rec, pkb_root)
    return 0


def _key(collector: dict) -> str:
    """Generate a stable key from collector name."""
    name = collector["name"].lower()
    if "z-web-pack" in name:
        return "z-web-pack"
    if "built-in" in name or "web_pack" in name:
        return "builtin-web-pack"
    if "webfetch" in name.lower():
        return "webfetch"
    if "gstack" in name.lower():
        return "gstack"
    return re.sub(r'[^a-z0-9-]', '-', name)


if __name__ == "__main__":
    sys.exit(main())
