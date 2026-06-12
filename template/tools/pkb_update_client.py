#!/usr/bin/env python3
"""PKB Update Client -- Update installed PKB from pkb-starter.

Reads pkb.config.json and syncs system files from the pkb-starter source.
Supports both online (git clone/pull) and local (--starter-path) modes.

SAFETY: Defaults to DRY-RUN. No files are modified unless --apply is passed.

Official starter repo: https://github.com/Clockworkhg/pkb-starter.git

Usage:
    python tools/pkb_update_client.py                          # dry-run (safe)
    python tools/pkb_update_client.py --apply                  # apply changes
    python tools/pkb_update_client.py --repo-url <repo>        # use custom repo
    python tools/pkb_update_client.py --starter-path <path>    # use local clone
    python tools/pkb_update_client.py --checkout v0.6.4-alpha  # specific version

When --repo-url is passed with --apply, the URL is saved to pkb.config.json
so future updates work without repeating the --repo-url flag.
"""

import os
import sys
import json
import shutil
import subprocess
from pathlib import Path
from datetime import datetime, timezone

OFFICIAL_REPO_URL = "https://github.com/Clockworkhg/pkb-starter.git"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def info(msg: str):
    print(f"[INFO] {msg}")


def warn(msg: str):
    print(f"[WARN] {msg}")


def ok(msg: str):
    print(f"[OK] {msg}")


def die(msg: str, code: int = 1):
    print(f"[ERROR] {msg}", file=sys.stderr)
    sys.exit(code)


def check_git() -> bool:
    """Check if git is available."""
    try:
        subprocess.run(["git", "--version"], capture_output=True, timeout=5,
                       encoding='utf-8', errors='replace')
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------

def load_config(kb_root: Path) -> dict:
    """Load pkb.config.json from knowledge base root."""
    config_path = kb_root / "pkb.config.json"
    if not config_path.is_file():
        die(f"pkb.config.json not found in {kb_root}. Is this a PKB installation?")
    try:
        return json.loads(config_path.read_text(encoding="utf-8"))
    except Exception as e:
        die(f"Failed to read pkb.config.json: {e}")


# ---------------------------------------------------------------------------
# Starter source resolution
# ---------------------------------------------------------------------------

def resolve_starter_path(opts: dict, config: dict, kb_root: Path) -> Path:
    """Determine the pkb-starter source path.

    Priority:
    1. --starter-path (local directory)
    2. --repo-url (clone/pull to cache)
    3. pkb.config.json starter_repo_url (clone/pull to cache)
    """
    # Explicit local path
    if opts.get("starter_path"):
        sp = Path(opts["starter_path"]).resolve()
        if not sp.is_dir():
            die(f"Starter path not found: {sp}")
        update_py = sp / "scripts" / "update_pkb.py"
        if not update_py.is_file():
            die(f"update_pkb.py not found in starter path: {update_py}")
        info(f"Using local starter: {sp}")
        return sp

    # Remote repo — clone or pull to cache
    repo_url = opts.get("repo_url") or config.get("starter_repo_url", "")
    if not repo_url or "<your-username>" in repo_url:
        if "<your-username>" in repo_url:
            warn("starter_repo_url in pkb.config.json is still the old placeholder:")
            warn(f"  {repo_url}")
            warn("")
            warn("To fix, run with the official repo URL:")
            warn(f'  python tools/pkb_update_client.py --repo-url "{OFFICIAL_REPO_URL}" --checkout v0.6.4-alpha')
            warn(f'  python tools/pkb_update_client.py --repo-url "{OFFICIAL_REPO_URL}" --checkout v0.6.4-alpha --apply')
            warn("")
            warn("Or use your own fork:")
            warn(f'  python tools/pkb_update_client.py --repo-url "https://github.com/<your-username>/pkb-starter.git" --checkout v0.6.4-alpha --apply')
            warn("")
            warn("After --apply, the repo URL will be saved to pkb.config.json for future updates.")
            die("Cannot continue with placeholder starter_repo_url.")
        die(
            "No starter_repo_url configured.\n"
            "  Option 1: Set starter_repo_url in pkb.config.json to your pkb-starter fork.\n"
            f"  Option 2: Use --repo-url \"{OFFICIAL_REPO_URL}\" to use the official repo.\n"
            "  Option 3: Use --starter-path <path> to point to a local pkb-starter clone."
        )

    cache_dir = kb_root / config.get("starter_cache_dir", ".pkb_system/starter_cache")

    if not cache_dir.is_dir():
        info(f"Cloning starter repo to cache: {cache_dir}")
        try:
            subprocess.run(
                ["git", "clone", "--depth", "1", repo_url, str(cache_dir)],
                capture_output=True, timeout=120,
                encoding='utf-8', errors='replace', check=True
            )
        except subprocess.CalledProcessError as e:
            die(f"Failed to clone {repo_url}: {e.stderr.strip()}")
    else:
        info(f"Updating starter cache: {cache_dir}")
        try:
            subprocess.run(
                ["git", "-C", str(cache_dir), "pull", "--ff-only"],
                capture_output=True, timeout=60,
                encoding='utf-8', errors='replace'
            )
        except Exception as e:
            warn(f"Cache update failed: {e}. Using cached version.")

    # Optional checkout
    if opts.get("checkout"):
        ref = opts["checkout"]
        info(f"Checking out: {ref}")
        try:
            subprocess.run(
                ["git", "-C", str(cache_dir), "fetch", "--tags", "--depth", "1"],
                capture_output=True, timeout=60,
                encoding='utf-8', errors='replace'
            )
            subprocess.run(
                ["git", "-C", str(cache_dir), "checkout", ref],
                capture_output=True, timeout=30,
                encoding='utf-8', errors='replace', check=True
            )
        except subprocess.CalledProcessError as e:
            die(f"Checkout failed: {e.stderr.strip()}")

    update_py = cache_dir / "scripts" / "update_pkb.py"
    if not update_py.is_file():
        die(f"update_pkb.py not found in cache: {update_py}")
    return cache_dir


# ---------------------------------------------------------------------------
# Run update
# ---------------------------------------------------------------------------

def run_update(starter_dir: Path, kb_root: Path, opts: dict):
    """Execute update_pkb.py from the resolved starter directory."""
    update_script = starter_dir / "scripts" / "update_pkb.py"
    cmd = [sys.executable, str(update_script), str(kb_root)]
    if opts.get("dry_run"):
        cmd.append("--dry-run")

    info(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=str(starter_dir), timeout=300,
                            encoding='utf-8', errors='replace')

    if result.returncode != 0:
        warn(f"update_pkb.py exited with code {result.returncode}")


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def write_report(kb_root: Path, opts: dict, config: dict, starter_dir: Path):
    """Write update_client_report.md to the KB root."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    lines = [
        "# PKB Update Client Report",
        "",
        f"**Generated**: {now}",
        f"**KB root**: `{kb_root}`",
        f"**Mode**: {'DRY RUN' if opts.get('dry_run') else 'LIVE'}",
        f"**Previous starter_version**: {config.get('starter_version', 'unknown')}",
        f"**Starter source**: {starter_dir}",
        "",
        "## Protected Data Not Touched",
        "",
        "The following data is NEVER modified by the update process:",
        "",
        "- `raw/` — all raw materials",
        "- `wiki/` — all knowledge pages",
        "- `_INBOX/` — pending imports",
        "- `skills/_vendor/` — installed third-party skills",
        "- `.pkb_local/` — local patches and settings",
        "- `pkb.config.json` user settings (only version fields updated)",
        "",
        "## Preserved Fields",
        "",
        "| Field | Status |",
        "|-------|--------|",
        f"| `language` | preserved |",
        f"| `wiki_language` | preserved |",
        f"| `output_language` | preserved |",
        f"| `install_path` | preserved |",
        f"| `starter_repo_url` | {'updated' if opts.get('repo_url') else 'preserved'} |",
        f"| `skills.*` | preserved |",
        "",
        "For detailed changes, see `update_report.md` (generated by update_pkb.py).",
        "",
        "---",
        "",
        "*Report generated by `tools/pkb_update_client.py`*",
    ]
    report_path = kb_root / "update_client_report.md"
    report_path.write_text('\n'.join(lines), encoding="utf-8")
    info(f"Report written: {report_path}")


def save_repo_url_to_config(kb_root: Path, repo_url: str):
    """Write repo_url back to pkb.config.json, preserving all other fields."""
    config_path = kb_root / "pkb.config.json"
    if not config_path.is_file():
        warn("Cannot save repo URL: pkb.config.json not found.")
        return
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
        old_url = config.get("starter_repo_url", "")
        if "<your-username>" in old_url or old_url != repo_url:
            config["starter_repo_url"] = repo_url
            config_path.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")
            ok(f"Saved starter_repo_url to config: {repo_url}")
        else:
            info(f"starter_repo_url already set to: {repo_url}")
    except Exception as e:
        warn(f"Failed to save repo URL to config: {e}")
        info(f"Edit pkb.config.json manually: set starter_repo_url to \"{repo_url}\"")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    if "--help" in sys.argv or "-h" in sys.argv:
        print(__doc__)
        sys.exit(0)

    # -------------------------------------------------------------------
    # Parse arguments — properly skip flag values to avoid mistaking
    # --starter-path / --repo-url / --checkout values as positional args.
    # -------------------------------------------------------------------
    valued_flags = {"--starter-path", "--repo-url", "--checkout"}

    positional = []
    i = 1  # skip program name (sys.argv[0])
    while i < len(sys.argv):
        arg = sys.argv[i]
        if arg in valued_flags and i + 1 < len(sys.argv):
            i += 2  # skip flag and its value
        elif arg.startswith("--") or arg.startswith("-"):
            i += 1  # skip boolean flag or short flag
        else:
            positional.append(arg)
            i += 1

    if positional:
        kb_root = Path(positional[0]).resolve()
    else:
        kb_root = Path.cwd()

    if not kb_root.is_dir():
        die(f"KB root not found: {kb_root}")

    # -------------------------------------------------------------------
    # Mode: default = dry-run (safe).  --apply is required to write files.
    # --dry-run is accepted for compatibility but is the default.
    # -------------------------------------------------------------------
    apply_mode = "--apply" in sys.argv
    dry_run = not apply_mode

    # Extract flag values
    opts = {
        "dry_run": dry_run,
        "starter_path": None,
        "repo_url": None,
        "checkout": None,
    }
    for i, arg in enumerate(sys.argv):
        if arg == "--starter-path" and i + 1 < len(sys.argv):
            opts["starter_path"] = sys.argv[i + 1]
        if arg == "--repo-url" and i + 1 < len(sys.argv):
            opts["repo_url"] = sys.argv[i + 1]
        if arg == "--checkout" and i + 1 < len(sys.argv):
            opts["checkout"] = sys.argv[i + 1]

    if not check_git():
        die("Git is required but not found. Install Git and try again.")

    config = load_config(kb_root)
    info(f"KB root: {kb_root}")
    info(f"Installed starter_version: {config.get('starter_version', 'unknown')}")
    print()

    # -------------------------------------------------------------------
    # Announce mode clearly before any work
    # -------------------------------------------------------------------
    if dry_run:
        info("=== DRY-RUN MODE: no files will be changed ===")
    else:
        info("=== APPLY MODE: files may be changed ===")
    print()

    starter_dir = resolve_starter_path(opts, config, kb_root)
    run_update(starter_dir, kb_root, opts)

    if not opts.get("dry_run"):
        # Re-read config for updated version
        try:
            config = load_config(kb_root)
        except Exception:
            pass
        # Save repo URL if user provided --repo-url (fixes placeholder configs)
        if opts.get("repo_url"):
            save_repo_url_to_config(kb_root, opts["repo_url"])
    write_report(kb_root, opts, config, starter_dir)

    print()
    ok("Update client finished.")
    if opts.get("dry_run"):
        info("This was a dry run. Run with --apply to apply changes.")
    else:
        info("Changes have been applied.")


if __name__ == "__main__":
    main()
