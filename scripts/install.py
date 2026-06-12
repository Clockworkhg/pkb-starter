#!/usr/bin/env python3
"""PKB Starter -- One-shot installer.

Creates a new PKB directory from the pkb-starter template.

Usage:
    python scripts/install.py "<target_directory>"
    python scripts/install.py "<target_directory>" --profile student
    python scripts/install.py "<target_directory>" --profile student --dry-run
    python scripts/install.py "<target_directory>" --interactive-skills
    python scripts/install.py "<target_directory>" --skip-skills
    python scripts/install.py "<target_directory>" --no-git
    python scripts/install.py "<target_directory>" --force
    python scripts/install.py "<target_directory>" --lang zh-CN
    python scripts/install.py "<target_directory>" --lang bilingual
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


# Profile descriptions for display during interactive selection
PROFILE_DESCRIPTIONS = {
    "core": {
        "title": "Core",
        "tagline": "Pure PKB. Zero external skills.",
        "desc": "Basic personal knowledge base with PKB's built-in tools only: web collection, auto ingest, file import, health checks, privacy scanning, document conversion, git versioning. Start here and add skills later.",
        "skills": 0,
    },
    "student": {
        "title": "Student",
        "tagline": "Coursework, papers, literature review.",
        "desc": "Academic essentials for students: literature search and review, paper section writing, citation management (APA/GB/T 7714/IEEE), article extraction for research sources, YouTube transcript capture. Ideal for undergraduates and coursework-focused grad students.",
        "skills": 8,
    },
    "research": {
        "title": "Research",
        "tagline": "Full academic pipeline. Graduate-level.",
        "desc": "Comprehensive academic workflow: deep multi-turn research, agent-based research pipeline (31 sub-skills), literature tools, experiment design, data analysis, figure/table generation, Zotero integration, CNKI Chinese database access. For systematic academic research.",
        "skills": 12,
    },
    "developer": {
        "title": "Developer",
        "tagline": "Code projects, docs, GitHub research.",
        "desc": "Software engineering focused: document processing for technical docs, semantic code search (QMD), project kanban boards, GitHub repository analysis, code debugging, article extraction. For developers documenting projects and researching code.",
        "skills": 7,
    },
    "creator": {
        "title": "Creator",
        "tagline": "Writers, musicians, filmmakers.",
        "desc": "Content creation toolkit: AI prompt library management, song/lyrics archive with version tracking, script breakdown and storyboard generation, article extraction, YouTube transcripts, kanban project management. For creative professionals building a reference library.",
        "skills": 7,
    },
    "output": {
        "title": "Output & Publishing",
        "tagline": "Reports, papers, presentations.",
        "desc": "Output-focused: document conversion (DOCX/PDF/PPTX/MD), academic paper writing with evidence support, citation management, prompt library, slide generation. For users who primarily produce documents and reports.",
        "skills": 7,
    },
    "security": {
        "title": "Security & Privacy",
        "tagline": "Audit, sanitize, harden.",
        "desc": "Security-hardened minimal setup: enhanced secret scanning, privacy sanitization, git versioning with pre-commit checks. For auditing your knowledge base before sharing or publishing. Built-in sanitize-tool is always active regardless of profile.",
        "skills": 3,
    },
    "full": {
        "title": "Full Stack",
        "tagline": "All 24 recommended skills. Power user.",
        "desc": "Complete PKB ecosystem: academic research, document processing, creation tools, semantic search, project management, security hardening. High-risk skills (CNKI, Zotero) are NOT auto-enabled -- use --enable-risky to add them. Review risk levels before installing.",
        "skills": 24,
    },
    "custom": {
        "title": "Custom",
        "tagline": "Hand-pick from 42 entries.",
        "desc": "Interactive selection: browse the full 42-entry catalog and choose exactly which skills to install. See descriptions and risk levels before selecting. Best for advanced users who know what they need.",
        "skills": "interactive",
    },
}


def generate_config(target: Path, lang: str = "en") -> Path:
    """Generate pkb.config.json with full skills state model and language fields."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Language settings
    if lang == "zh-CN":
        language = "zh-CN"
        wiki_language = "zh-CN"
        output_language = "zh-CN"
    elif lang == "bilingual":
        language = "bilingual"
        wiki_language = "zh-CN"
        output_language = "zh-CN"
    else:
        language = "en"
        wiki_language = "en"
        output_language = "en"

    config = {
        "name": target.name,
        "version": "0.1.0",
        "starter_version": "0.6.1-alpha",
        "schema_version": "0.6.0",
        "created": today,
        "last_updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "template": "pkb-starter",
        "language": language,
        "wiki_language": wiki_language,
        "output_language": output_language,
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
        "skills": {
            "catalog_version": "0.5.0",
            "installed_profiles": [],
            "installed_skills": [],
            "enabled_skills": [],
            "disabled_skills": [],
            "vendor_downloads": [],
            "enabled_adapters": [],
            "pending_audit": [],
        },
    }
    config_path = target / "pkb.config.json"
    config_path.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")
    return config_path


def apply_locale(target: Path, lang: str) -> list[str]:
    """Apply Chinese locale files after template copy. Returns list of applied files."""
    if lang not in ("zh-CN", "bilingual"):
        return []

    locale_dir = TEMPLATE_DIR / "locales" / "zh-CN"
    if not locale_dir.is_dir():
        print(f"  [WARN] Locale directory not found: {locale_dir}")
        return []

    applied = []

    # zh-CN mode: overwrite root files with Chinese versions
    if lang == "zh-CN":
        root_files = {
            "README.md": "README.md",
            "AGENTS.md": "AGENTS.md",
            "COMMANDS.md": "COMMANDS.md",
            "index.md": "index.md",
            "log.md": "log.md",
        }
        for src_name, dst_name in root_files.items():
            src = locale_dir / src_name
            dst = target / dst_name
            if src.is_file():
                shutil.copy2(src, dst)
                applied.append(str(dst_name))

        # Wiki files
        wiki_files = {
            "wiki_index.md": "wiki/index.md",
            "wiki_log.md": "wiki/log.md",
        }
        for src_name, dst_rel in wiki_files.items():
            src = locale_dir / src_name
            dst = target / dst_rel
            if src.is_file():
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
                applied.append(str(dst_rel))

    # bilingual mode: keep English files, add Chinese alongside
    elif lang == "bilingual":
        bilingual_files = {
            "README.md": "README.zh-CN.md",
            "AGENTS.md": "AGENTS.zh-CN.md",
            "COMMANDS.md": "COMMANDS.zh-CN.md",
            "index.md": "index.zh-CN.md",
            "log.md": "log.zh-CN.md",
        }
        for src_name, dst_name in bilingual_files.items():
            src = locale_dir / src_name
            dst = target / dst_name
            if src.is_file():
                shutil.copy2(src, dst)
                applied.append(str(dst_name))

        # Wiki files still use Chinese content
        wiki_files = {
            "wiki_index.md": "wiki/index.md",
            "wiki_log.md": "wiki/log.md",
        }
        for src_name, dst_rel in wiki_files.items():
            src = locale_dir / src_name
            dst = target / dst_rel
            if src.is_file():
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
                applied.append(str(dst_rel))

    return applied


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
    dry_run = "--dry-run" in sys.argv

    # Parse --profile
    profile = "core"
    for i, arg in enumerate(sys.argv):
        if arg == "--profile" and i + 1 < len(sys.argv):
            profile = sys.argv[i + 1]
            break

    # Parse --lang
    lang = "en"
    for i, arg in enumerate(sys.argv):
        if arg == "--lang" and i + 1 < len(sys.argv):
            lang_val = sys.argv[i + 1]
            if lang_val in ("en", "zh-CN", "bilingual"):
                lang = lang_val
            else:
                print(f"[WARN] Unknown language '{lang_val}', using 'en'")
            break

    target = Path(target_dir).resolve()

    if interactive_skills:
        profile = "custom"

    print(f"=== PKB Starter Installer v0.6.1-alpha ===")
    print(f"Target: {target}")
    print(f"Language: {lang}")
    if dry_run:
        print(f"Mode: DRY RUN -- no files will be written")
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

    # Apply locale (zh-CN / bilingual)
    if lang != "en":
        print(f"  Applying locale: {lang}...")
        locale_files = apply_locale(target, lang)
        if locale_files:
            print(f"  {len(locale_files)} locale files applied")
            for f in sorted(locale_files):
                print(f"    {f}")

    # Generate config
    print("[4/6] Generating pkb.config.json...")
    config_path = generate_config(target, lang=lang)
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

        # Show profile description
        if profile in PROFILE_DESCRIPTIONS:
            pd = PROFILE_DESCRIPTIONS[profile]
            print(f"[7/{total_steps}] Optional Skills: {pd['title']} Profile")
            print()
            print(f"  {pd['tagline']}")
            print(f"  {pd['desc']}")
            print()
            if pd['skills'] != "interactive" and pd['skills'] > 0:
                print(f"  Skills in this profile: {pd['skills']}")
                print()
            if profile == "full":
                print(f"  [NOTE] Full profile installs all recommended skills.")
                print(f"         High-risk skills (CNKI, Zotero) are NOT auto-enabled.")
                print(f"         Start with a smaller profile if unsure.")
                print(f"         Recommended: install Core first, add skills later via /project:skills.")
                print()
            if profile == "custom":
                print(f"  [NOTE] Custom profile lets you pick individual skills.")
                print(f"         You will see the full catalog with descriptions and risks.")
                print()
        else:
            print(f"[7/{total_steps}] Optional Skills: profile '{profile}'")

        if dry_run:
            print(f"  [DRY RUN] Would install skills for profile: {profile}")
            print(f"  Run without --dry-run to actually install.")
        else:
            print(f"  Installing optional skills (profile: {profile})...")
            _run_skill_installer(target, profile)
    else:
        if interactive_skills:
            print(f"[WARN] --interactive-skills ignored (--skip-skills is set)")
        if profile != "core":
            print(f"[WARN] --profile {profile} ignored (--skip-skills is set)")
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
