#!/usr/bin/env python3
"""PKB Starter — Environment checker.

Verifies that the system has everything needed to run PKB.

Usage:
    python scripts/check_env.py
    python scripts/check_env.py --json   # machine-readable output
"""

import sys
import json
import subprocess
from pathlib import Path
from datetime import datetime, timezone


def check_python() -> dict:
    """Check Python version."""
    version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    ok = sys.version_info >= (3, 9)
    return {
        "name": "Python",
        "version": version,
        "ok": ok,
        "detail": f"Python {version} {'>= 3.9 OK' if ok else '< 3.9 required'}"
    }


def check_git() -> dict:
    """Check git availability."""
    try:
        result = subprocess.run(
            ["git", "--version"],
            capture_output=True, text=True, timeout=5,
            encoding='utf-8', errors='replace'
        )
        version = result.stdout.strip().replace("git version ", "")
        return {"name": "Git", "version": version, "ok": True, "detail": result.stdout.strip()}
    except Exception:
        return {"name": "Git", "version": "N/A", "ok": False, "detail": "Git not found in PATH"}


def check_pip_packages() -> dict:
    """Check required Python packages."""
    # Map pip package names to import names
    pkg_import_map = {
        "readability-lxml": "readability",
        "trafilatura": "trafilatura",
        "beautifulsoup4": "bs4",
        "requests": "requests",
        "pyyaml": "yaml",
    }
    missing = []
    for pkg_name, import_name in pkg_import_map.items():
        try:
            __import__(import_name)
        except ImportError:
            missing.append(pkg_name)

    ok = len(missing) == 0
    detail = "All packages installed" if ok else f"Missing: {', '.join(missing)}"
    return {"name": "Python packages", "version": "N/A", "ok": ok, "detail": detail}


def check_disk_space(path: str = ".") -> dict:
    """Check available disk space."""
    try:
        import shutil
        usage = shutil.disk_usage(path)
        free_gb = usage.free / (1024 ** 3)
        ok = free_gb > 1.0
        return {
            "name": "Disk space",
            "version": f"{free_gb:.1f} GB free",
            "ok": ok,
            "detail": f"{free_gb:.1f} GB free {'OK' if ok else '< 1 GB — may be insufficient'}"
        }
    except Exception:
        return {"name": "Disk space", "version": "N/A", "ok": True, "detail": "Unable to check"}


def check_pkb_structure(path: str = ".") -> dict:
    """Check if current directory has PKB structure."""
    target = Path(path)
    required = ["AGENTS.md", "COMMANDS.md", ".gitignore"]
    optional = ["wiki/", "raw/", "tools/", "skills/", "templates/"]

    missing_required = [f for f in required if not (target / f).is_file()]
    missing_optional = [f for f in optional if not (target / f).is_dir()]

    ok = len(missing_required) == 0
    detail_parts = []
    if missing_required:
        detail_parts.append(f"Missing required: {', '.join(missing_required)}")
    if missing_optional:
        detail_parts.append(f"Missing optional: {', '.join(missing_optional)}")
    if not detail_parts:
        detail_parts.append("PKB structure complete")

    return {
        "name": "PKB structure",
        "version": "N/A",
        "ok": ok,
        "detail": "; ".join(detail_parts)
    }


def main():
    json_output = "--json" in sys.argv

    checks = [
        check_python(),
        check_git(),
        check_pip_packages(),
        check_disk_space(),
    ]

    # Check PKB structure if in a PKB directory
    if Path("AGENTS.md").is_file() or Path("COMMANDS.md").is_file():
        checks.append(check_pkb_structure())

    if json_output:
        report = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "checks": checks,
            "summary": {
                "total": len(checks),
                "passed": sum(1 for c in checks if c["ok"]),
                "failed": sum(1 for c in checks if not c["ok"]),
            }
        }
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0 if report["summary"]["failed"] == 0 else 1

    # Human-readable
    print("=== PKB Environment Check ===")
    print()
    all_ok = True
    for c in checks:
        status = "[OK]" if c["ok"] else "[FAIL]"
        print(f"  {status} {c['detail']}")
        if not c["ok"]:
            all_ok = False
    print()

    if all_ok:
        print("[OK] All checks passed -- ready to use PKB!")
    else:
        print("[FAIL] Some checks failed. Fix the issues above, then re-run.")
        print("   Hint: pip install -r requirements.txt")

    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
