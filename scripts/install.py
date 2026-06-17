#!/usr/bin/env python3
"""PKB Starter -- One-shot installer.

Creates a new PKB directory from the pkb-starter template.

The first positional argument is the target install path. Users may choose any
directory (D:\\MyKB, E:\\KnowledgeBase, C:\\Users\\...\\Documents\\PKB, etc.).
D:\\MyKB is an example only — no default path is forced.

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
    python scripts/install.py "<target_directory>" --repo-url https://github.com/<your-fork>/pkb-starter.git
    python scripts/install.py --interactive
    python scripts/install.py --interactive --dry-run
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

DEFAULT_STARTER_REPO_URL = "https://github.com/Clockworkhg/pkb-starter.git"


def copy_template(target: Path, force: bool = False) -> list[str]:
    """Copy template files to target directory. Returns list of created paths."""
    if not TEMPLATE_DIR.is_dir():
        print(f"[ERROR] Template directory not found: {TEMPLATE_DIR}")
        sys.exit(1)

    created = []
    for src in TEMPLATE_DIR.rglob("*"):
        if src.is_dir():
            continue
        # Skip __pycache__ and other artifact directories, but NOT __init__.py
        if src.name != "__init__.py" and any(p.startswith("__") for p in src.parts):
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


def generate_config(target: Path, lang: str = "en", repo_url: str = None, dry_run: bool = False) -> Path:
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

    # Repo URL — use provided value or the official default
    if not repo_url:
        repo_url = DEFAULT_STARTER_REPO_URL

    config = {
        "name": target.name,
        "version": "0.1.0",
        "starter_version": "0.6.10-alpha",
        "schema_version": "0.6.0",
        "created": today,
        "last_updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "template": "pkb-starter",
        "language": language,
        "wiki_language": wiki_language,
        "output_language": output_language,
        "install_path": str(target.resolve()),
        "starter_repo_url": repo_url,
        "starter_update_channel": "alpha",
        "starter_cache_dir": ".pkb_system/starter_cache",
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
    if not dry_run:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")
    return config_path


def _set_pkb_root(target: Path) -> bool:
    """Replace __PKB_ROOT__ placeholder in settings.json with actual target path."""
    settings_path = target / ".claude" / "settings.json"
    if not settings_path.is_file():
        return False
    content = settings_path.read_text(encoding="utf-8")
    if "__PKB_ROOT__" not in content:
        return False
    actual_path = str(target.resolve()).replace("\\", "\\\\")
    content = content.replace("__PKB_ROOT__", actual_path)
    settings_path.write_text(content, encoding="utf-8")
    return True


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


def _interactive_prompt():
    """Interactive mode: ask user for target path, language, and profile."""
    print("=== PKB Starter — Interactive Install ===")
    print()

    # Target directory
    while True:
        target_str = input("Target directory (e.g. D:\\MyKB): ").strip()
        if not target_str:
            print("  [ERROR] Target directory is required.")
            continue
        target = Path(target_str).resolve()
        if target.exists() and any(target.iterdir()):
            print(f"  [WARN] Directory '{target}' already exists and is not empty.")
            confirm = input("  Continue? Files may be overwritten. (y/N): ").strip().lower()
            if confirm not in ("y", "yes"):
                print("  Aborted.")
                sys.exit(0)
        break

    # Language
    print()
    print("Language options:")
    print("  1. en       — English (default)")
    print("  2. zh-CN    — Simplified Chinese")
    print("  3. bilingual — English files + Chinese wiki")
    while True:
        lang_choice = input("Choose language [1-3] (default 1): ").strip()
        if not lang_choice:
            lang = "en"
            break
        if lang_choice == "1":
            lang = "en"; break
        elif lang_choice == "2":
            lang = "zh-CN"; break
        elif lang_choice == "3":
            lang = "bilingual"; break
        else:
            print("  Please enter 1, 2, or 3.")

    # Skill profile
    print()
    print("Skill profiles:")
    for key, pd in PROFILE_DESCRIPTIONS.items():
        skills_count = pd['skills'] if pd['skills'] != "interactive" else "pick"
        print(f"  {key:<12} ({skills_count} skills) — {pd['tagline']}")
    print()
    skip_skills = False
    while True:
        profile_choice = input("Choose profile (default core): ").strip().lower()
        if not profile_choice:
            profile = "core"; break
        if profile_choice in PROFILE_DESCRIPTIONS:
            profile = profile_choice; break
        elif profile_choice == "skip":
            profile = "core"
            skip_skills = True
            break
        else:
            print(f"  Unknown profile '{profile_choice}'. Valid: {', '.join(PROFILE_DESCRIPTIONS.keys())}, skip")

    # Repo URL
    print()
    print(f"Official starter repo: {DEFAULT_STARTER_REPO_URL}")
    repo_url = input("Custom repo URL (leave blank to use official, or enter your fork URL): ").strip()
    if not repo_url:
        repo_url = None

    return target, lang, profile, skip_skills, repo_url


def main():
    interactive_mode = "--interactive" in sys.argv
    force = "--force" in sys.argv
    skip_git = "--no-git" in sys.argv
    skip_deps = "--no-deps" in sys.argv
    skip_skills = "--skip-skills" in sys.argv
    interactive_skills = "--interactive-skills" in sys.argv
    dry_run = "--dry-run" in sys.argv

    # Parse --repo-url
    repo_url = None
    for i, arg in enumerate(sys.argv):
        if arg == "--repo-url" and i + 1 < len(sys.argv):
            repo_url = sys.argv[i + 1]
            break

    # Interactive mode: prompt for all settings
    if interactive_mode:
        target, lang, profile, skip_skills_interactive, repo_url_interactive = _interactive_prompt()
        if repo_url_interactive:
            repo_url = repo_url_interactive
        # Override skip_skills from interactive prompt if user chose "skip"
        if skip_skills_interactive:
            skip_skills = True
    else:
        # Non-interactive: target path is required
        if len(sys.argv) < 2 or sys.argv[1].startswith("--"):
            print("[ERROR] Target directory is required.")
            print()
            print("Usage:")
            print('  python scripts/install.py "<target_directory>"')
            print("  python scripts/install.py --interactive")
            print()
            print("D:\\MyKB is an example only -- you may use any path:")
            print("  D:\\MyKB")
            print("  E:\\KnowledgeBase")
            print("  C:\\Users\\YourName\\Documents\\PKB")
            print("  F:\\ResearchKB")
            print()
            print("Run --interactive for guided setup.")
            sys.exit(1)

        target_dir = sys.argv[1]
        target = Path(target_dir).resolve()

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

    if interactive_skills:
        profile = "custom"

    # Check target directory
    if target.exists() and any(target.iterdir()) and not force:
        print(f"[WARN] Target directory '{target}' already exists and is not empty.")
        print(f"       Use --force to overwrite existing files, or choose a different path.")
        if not interactive_mode:
            sys.exit(1)

    print(f"=== PKB Starter Installer v0.6.10-alpha ===")
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

    if not dry_run:
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

        # Set PKB_ROOT in settings.json
        if _set_pkb_root(target):
            print(f"  PKB_ROOT set in .claude/settings.json")

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
    config_path = generate_config(target, lang=lang, repo_url=repo_url, dry_run=dry_run)
    if dry_run:
        print(f"  [DRY RUN] Would write: {config_path}")
    else:
        print(f"  {config_path}")

    if not dry_run:
        # Initialize git
        if not skip_git:
            print("[5/6] Initializing git...")
            if init_git(target):
                print(f"  Git repository initialized")
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
            total_steps = 6

    # Done
    print()
    print("=" * 60)
    print("  PKB initialized successfully!")
    print("=" * 60)
    if repo_url and "<your-username>" in repo_url:
        print(f"  [NOTE] starter_repo_url still contains '<your-username>' placeholder.")
        print(f"         Edit pkb.config.json -> starter_repo_url to your actual fork URL,")
        print(f"         or set it to the official repo: {DEFAULT_STARTER_REPO_URL}")
        print()
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

  # To check for pkb-starter updates:
  python tools/pkb_update_client.py              # preview (dry-run by default)
  python tools/pkb_update_client.py --apply      # apply changes

  # Or from anywhere:
  claude --project "{target}"
""")
    print(f"  Knowledge base location: {target}")
    print(f"  Config file: {config_path}")


if __name__ == "__main__":
    main()
