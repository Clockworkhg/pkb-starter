#!/usr/bin/env python3
"""
PKB z-web-pack runner (v0.1.0)

Prepares the environment so collect_web_pack.py can run:
  1. Deploys the PKB compat base module to the path that collect_web_pack.py expects
  2. Injects a dummy readability package so the env-check import passes
     (z-web-pack does NOT call readability APIs; extraction uses BS4 via the compat base)
  3. Executes collect_web_pack.py via subprocess with user args
  4. Prints the output path for bridge to import

Invoked by: zskill_bridge.py cmd_run()

Safety:
  - All deployment goes to .agent/skills/ (gitignored in PKB)
  - Does NOT modify skills/_vendor/ (z-skills source stays pristine)
  - Uses subprocess.run() with list args — NEVER shell=True
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path


# -- Paths -----------------------------------------------------------------

def find_pkb_root() -> Path:
    """Locate PKB root by finding pkb.config.json or using PKB_ROOT env var."""
    cwd = Path.cwd()
    for parent in [cwd] + list(cwd.parents):
        if (parent / "pkb.config.json").is_file():
            return parent
    env = os.environ.get("PKB_ROOT", "")
    if env:
        return Path(env)
    return cwd


# -- Deploy compat base ----------------------------------------------------

def deploy_compat_base(pkb_root: Path) -> Path:
    """
    Ensure the compat base module exists at the path collect_web_pack.py expects:
        .agent/skills/1-web-research-pack/scripts/collect_web_research_pack.py

    Returns the path to the deployed base script.
    """
    target_dir = pkb_root / ".agent" / "skills" / "1-web-research-pack" / "scripts"
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / "collect_web_research_pack.py"

    compat_source = pkb_root / ".pkb_local" / "patches" / "web_research_pack_base.py"

    if compat_source.is_file():
        shutil.copy2(compat_source, target)
        print(f"[PKB runner] Deployed compat base: {target}")
    elif not target.is_file():
        raise FileNotFoundError(
            f"Compat base not found at {compat_source}. "
            "Run 'python tools/zskill_bridge.py status' to check installation."
        )
    return target


# -- Dummy readability -----------------------------------------------------

def inject_dummy_readability(pkb_root: Path) -> Path:
    """
    Create a dummy readability package so collect_web_pack.py's
    `import readability` env-check passes.

    collect_web_pack.py does NOT call any readability APIs —
    it only imports readability as a pre-flight check (line 34-38).
    Actual content extraction goes through base._extract_article_soup
    which uses BeautifulSoup.

    If future z-web-pack versions add actual readability API calls,
    this dummy will NOT silently work — it will raise AttributeError.
    """
    readability_dir = (
        pkb_root / ".agent" / "skills" / "1-web-research-pack" / "readability"
    )
    readability_dir.mkdir(parents=True, exist_ok=True)
    init_file = readability_dir / "__init__.py"

    if not init_file.is_file():
        init_file.write_text(
            "# PKB compat: dummy readability package\n"
            "# This exists ONLY to pass collect_web_pack.py's env-check import.\n"
            "# z-web-pack does NOT call readability APIs — extraction uses BS4.\n"
            "# If you see ImportError about readability.xxx, the upstream script\n"
            "# has added real readability API calls. Remove this dummy and install\n"
            "# readability-lxml: pip install readability-lxml\n",
            encoding="utf-8",
        )
        print(f"[PKB runner] Injected dummy readability: {readability_dir}")

    return readability_dir


def ensure_syspath(pkb_root: Path) -> str:
    """
    Build a PYTHONPATH that includes:
      - .agent/skills/1-web-research-pack/  (so 'import readability' finds the dummy)
      - The existing PYTHONPATH
    Returns the new PYTHONPATH value.
    """
    agent_skills = str(pkb_root / ".agent" / "skills" / "1-web-research-pack")
    existing = os.environ.get("PYTHONPATH", "")
    if existing:
        return f"{agent_skills}{os.pathsep}{existing}"
    return agent_skills


# -- Execute ---------------------------------------------------------------

def run_collect(pkb_root: Path, args: list[str]) -> subprocess.CompletedProcess:
    """
    Execute collect_web_pack.py with the given CLI arguments.
    All args after 'run' / '--skill' / '--url' / '--topic' are forwarded.
    """
    z_web_pack_script = (
        pkb_root / "skills" / "_vendor" / "tjxj-z-skills" / "z-web-pack" /
        "scripts" / "collect_web_pack.py"
    )
    # Also try the standard z-skills path
    if not z_web_pack_script.is_file():
        z_web_pack_script = (
            pkb_root / "skills" / "_vendor" / "z-skills" / "z-web-pack" /
            "scripts" / "collect_web_pack.py"
        )

    if not z_web_pack_script.is_file():
        raise FileNotFoundError(
            f"collect_web_pack.py not found. Checked:\n"
            f"  {pkb_root / 'skills' / '_vendor' / 'tjxj-z-skills' / 'z-web-pack' / 'scripts' / 'collect_web_pack.py'}\n"
            f"  {pkb_root / 'skills' / '_vendor' / 'z-skills' / 'z-web-pack' / 'scripts' / 'collect_web_pack.py'}"
        )

    python_bin = sys.executable
    env = os.environ.copy()
    env["PYTHONPATH"] = ensure_syspath(pkb_root)
    env["PYTHONIOENCODING"] = "utf-8"

    cmd = [python_bin, str(z_web_pack_script)] + args
    print(f"[PKB runner] Executing: {' '.join(cmd)}")
    print(f"[PKB runner] PYTHONPATH includes: {env['PYTHONPATH']}")
    print()

    result = subprocess.run(
        cmd,
        cwd=str(pkb_root),
        env=env,
        capture_output=False,
        encoding="utf-8",
        errors="replace",
    )
    return result


# -- Main ------------------------------------------------------------------

def main():
    if len(sys.argv) < 2:
        print("Usage: python run_z_web_pack.py [--out-root DIR] [--title TITLE] [URLS...]")
        print("       All args are forwarded to collect_web_pack.py")
        sys.exit(1)

    pkb_root = find_pkb_root()
    print(f"[PKB runner] PKB root: {pkb_root}")

    # Step 1: Deploy compat base
    deploy_compat_base(pkb_root)

    # Step 2: Inject dummy readability
    inject_dummy_readability(pkb_root)

    # Step 3: Execute z-web-pack
    result = run_collect(pkb_root, sys.argv[1:])

    if result.returncode != 0:
        print(f"\n[PKB runner] z-web-pack exited with code {result.returncode}")
    else:
        print(f"\n[PKB runner] z-web-pack completed successfully")

    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
