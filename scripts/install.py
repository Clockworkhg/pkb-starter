#!/usr/bin/env python3
"""PKB Starter -- One-shot installer.

Creates a new PKB directory from the pkb-starter template.

Usage:
    python scripts/install.py "<target_directory>"
    python scripts/install.py "<target_directory>" --profile student
    python scripts/install.py "<target_directory>" --interactive-skills
    python scripts/install.py "<target_directory>" --skip-skills
    python scripts/install.py "<target_directory>" --no-git
    python scripts/install.py "<target_directory>" --force
"""

import os
import sys
import shutil
import json
import subprocess
from pathlib import Path
from datetime import datetime, timezone

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "template"
SKILLS_DIR = Path(__file__).resolve().parent.parent / "skills"


def copy_template(target: Path, force: bool = False) -> list[str]:
    """Copy template files to target directory. Returns list of created paths."""
    if not TEMPLATE_DIR.is_dir():
        print(f"[ERROR] Template directory not found: {TEMPLATE_DIR}")
        sys.exit(1)

    created = []
    for src in TEMPLATE_DIR.rglob("*"):
        if src.is_dir():
            continue
        # Skip __pycache__ and other artifacts
        if any(p.startswith("__") for p in src.parts):
            continue

        rel = src.relative_to(TEMPLATE_DIR)
        dst = target / rel
        dst.parent.mkdir(parents=True, exist_ok=True)

        if dst.exists() and not force:
            print(f"  [SKIP] {rel} -- already exists (use --force to overwrite)")
            continue

        shutil.copy2(src, dst)
        created.append(str(rel))

    return created


def create_directories(target: Path) -> list[str]:
    """Create PKB directory structure."""
    dirs = [
        "_INBOX/imported",
        "_INBOX/imported-folders",
        "raw/webpacks",
        "raw/clippings",
        "raw/papers",
        "raw/projects",
        "raw/courses",
        "raw/creation",
        "raw/media/images",
        "raw/media/video",
        "raw/media/audio",
        "raw/personal",
        "raw/assets",
        "raw/imported_processed",
        "wiki/concepts",
        "wiki/sources",
        "wiki/projects",
        "wiki/outputs",
        "wiki/tasks",
        "wiki/meta",
        "skills",
        "templates",
    ]
    created = []
    for d in dirs:
        p = target / d
        if not p.is_dir():
            p.mkdir(parents=True, exist_ok=True)
            created.append(d)
    return created


def generate_config(target: Path) -> Path:
    """Generate pkb.config.json."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    config = {
        "name": target.name,
        "version": "0.1.0",
        "created": today,
        "template": "pkb-starter",
        "directories": {
            "raw": "raw",
            "wiki": "wiki",
            "inbox": "_INBOX",
            "skills": "skills",
            "tools": "tools",
            "templates": "templates",
        },
        "settings": {
            "autopilot": True,
            "auto_commit": True,
            "privacy_level": "local",
        },
    }
    config_path = target / "pkb.config.json"
    config_path.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")
    return config_path


def init_git(target: Path) -> bool:
    """Initialize git repository. Returns True on success."""
    try:
        subprocess.run(
            ["git", "init"],
            cwd=str(target), capture_output=True, timeout=10,
            encoding='utf-8', errors='replace'
        )
        # Create initial .gitkeep files to preserve empty dirs
        for subdir in ["raw/webpacks", "raw/papers", "raw/imported_processed",
                       "wiki/concepts", "wiki/sources", "wiki/projects", "_INBOX/imported"]:
            keep = target / subdir / ".gitkeep"
            keep.parent.mkdir(parents=True, exist_ok=True)
            keep.touch(exist_ok=True)
        return True
    except Exception as e:
        print(f"  [WARN] Git init failed: {e}")
        return False


def check_python() -> bool:
    """Check Python version >= 3.9."""
    return sys.version_info >= (3, 9)


def check_git() -> bool:
    """Check if git is available."""
    try:
        subprocess.run(["git", "--version"], capture_output=True, timeout=5)
        return True
    except Exception:
        return False


def install_requirements(target: Path) -> bool:
    """Install Python dependencies."""
    req_file = Path(__file__).resolve().parent.parent / "requirements.txt"
    if not req_file.is_file():
        print("  [WARN] requirements.txt not found, skipping pip install")
        return False

    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-r", str(req_file)],
            cwd=str(target), timeout=120,
            encoding='utf-8', errors='replace'
        )
        return True
    except Exception as e:
        print(f"  [WARN] pip install failed: {e}")
        print(f"  Run manually: pip install -r requirements.txt")
        return False


def _run_skill_installer(target: Path, profile: str):
    """Run install_skills.py as a subprocess from the starter directory."""
    installer = Path(__file__).resolve().parent / "install_skills.py"
    if not installer.is_file():
        print(f"  [WARN] install_skills.py not found -- skipping skill installation")
        return

    cmd = [sys.executable, str(installer), "--target", str(target), "--profile", profile]
    try:
        result = subprocess.run(cmd, timeout=300, encoding="utf-8", errors="replace",
                                capture_output=True, text=True)
        # Pass through stdout
        if result.stdout:
            # Filter out JSON report (printed separately by install_skills.py)
            in_json = False
            for line in result.stdout.split("\n"):
                if line.strip() == "--- JSON REPORT ---":
                    in_json = True
                    continue
                if in_json:
                    continue
                print(f"  {line}")
        if result.returncode != 0:
            print(f"  [WARN] Skill installer exited with code {result.returncode}")
    except subprocess.TimeoutExpired:
        print(f"  [WARN] Skill installer timed out (300s)")
    except Exception as e:
        print(f"  [WARN] Skill installer failed: {e}")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    target_dir = sys.argv[1]
    force = "--force" in sys.argv
    skip_git = "--no-git" in sys.argv
    skip_deps = "--no-deps" in sys.argv
    skip_skills = "--skip-skills" in sys.argv
    interactive_skills = "--interactive-skills" in sys.argv

    # Parse --profile
    profile = "core"
    for i, arg in enumerate(sys.argv):
        if arg == "--profile" and i + 1 < len(sys.argv):
            profile = sys.argv[i + 1]
            break

    target = Path(target_dir).resolve()

    print(f"=== PKB Starter Installer ===")
    print(f"Target: {target}")
    print()

    # Pre-flight checks
    print("[1/6] Checking environment...")
    if not check_python():
        print("[ERROR] Python 3.9+ required")
        sys.exit(1)
    print(f"  Python {sys.version_info.major}.{sys.version_info.minor} -- OK")
    if check_git():
        print(f"  Git -- OK")
    else:
        print(f"  Git -- NOT FOUND (--no-git to skip)")

    # Create directories
    print("[2/6] Creating directory structure...")
    dirs = create_directories(target)
    print(f"  {len(dirs)} directories created")

    # Copy template files
    print("[3/6] Copying template files...")
    created = copy_template(target, force=force)
    print(f"  {len(created)} files copied")
    for f in sorted(created):
        print(f"    {f}")

    # Generate config
    print("[4/6] Generating pkb.config.json...")
    config_path = generate_config(target)
    print(f"  {config_path}")

    # Initialize git
    if not skip_git:
        print("[5/6] Initializing git...")
        if init_git(target):
            print(f"  Git repository initialized")
            # Copy .gitignore from template (already done in step 3, but ensure)
            gitignore_src = TEMPLATE_DIR / ".gitignore"
            gitignore_dst = target / ".gitignore"
            if gitignore_src.is_file() and not gitignore_dst.is_file():
                shutil.copy2(gitignore_src, gitignore_dst)
        else:
            print(f"  Git init skipped (use --no-git to suppress)")
    else:
        print("[5/6] Git -- skipped (--no-git)")

    # Install dependencies
    total_steps = 7 if not skip_skills else 6
    if not skip_deps:
        print(f"[6/{total_steps}] Installing Python dependencies...")
        install_requirements(target)
    else:
        print(f"[6/{total_steps}] Dependencies -- skipped (--no-deps)")

    # Install optional skills
    if not skip_skills:
        if interactive_skills:
            profile = "custom"
        print(f"[7/{total_steps}] Installing optional skills (profile: {profile})...")
        _run_skill_installer(target, profile)
    else:
        if interactive_skills:
            print(f"[WARN] --interactive-skills ignored (--skip-skills is set)")
        print(f"[7/{total_steps}] Skills -- skipped (--skip-skills)")
        total_steps = 6  # correction for display

    # Done
    print()
    print("=" * 60)
    print("  PKB initialized successfully!")
    print("=" * 60)
    print(f"""
Next steps:
  cd "{target}"

  # Start Claude Code (project mode)
  claude

  # In Claude Code, project commands use /project:<name>:
  /project:help               -- see all commands
  /project:pkb <anything>     -- start adding knowledge
  /project:pkb <url>          -- collect a web page
  /project:pkb <file.pdf>     -- import a file
  /project:skills             -- manage optional skills

  # Or open from anywhere:
  claude --project "{target}"
""")
    print(f"  Knowledge base location: {target}")
    print(f"  Config file: {config_path}")


if __name__ == "__main__":
    main()
