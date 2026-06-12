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
    python tools/pkb_update_client.py --checkout v0.6.5-alpha  # specific version
    python tools/pkb_update_client.py --doctor                 # diagnostic checks
    python tools/pkb_update_client.py --doctor --json           # diagnostic (JSON)

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
# Version parsing — handles v0.6.4-alpha < v0.6.5-alpha < v0.6.6-alpha
# ---------------------------------------------------------------------------

def _parse_version(v: str) -> tuple:
    """Parse version string into comparable tuple.

    Handles suffixes: -alpha, -beta, -rc1, and leading 'v'.
    Suffix ordering: alpha < beta < rc < final (no suffix).
    Returns (major, minor, patch, suffix_rank, suffix_num).
    """
    suffix_order = {"alpha": 0, "beta": 1, "rc": 2}
    v = v.lstrip("v").lower()
    numeric_part = v
    suffix = ""
    suffix_num = 0
    for sep in ("-",):
        if sep in v:
            parts = v.split(sep, 1)
            numeric_part = parts[0]
            suffix_part = parts[1]
            import re as _re
            m = _re.match(r"([a-zA-Z]+)(\d*)", suffix_part)
            if m:
                suffix = m.group(1).lower()
                suffix_num = int(m.group(2)) if m.group(2) else 0
            break
    try:
        nums = [int(x) for x in numeric_part.split(".")]
    except ValueError:
        nums = [0, 0, 0]
    while len(nums) < 3:
        nums.append(0)
    suffix_rank = suffix_order.get(suffix, 99) if suffix else 99
    return (nums[0], nums[1], nums[2], suffix_rank, suffix_num)


def version_lt(a: str, b: str) -> bool:
    """True if version a < b. Handles alpha/beta/rc suffixes."""
    return _parse_version(a) < _parse_version(b)


def version_sort_key(tag: str) -> tuple:
    """Sort key for version tags. Non-version strings sort last."""
    try:
        return (0,) + _parse_version(tag)
    except Exception:
        return (1, 0, 0, 0, 99, 0)


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
# Remote tag discovery
# ---------------------------------------------------------------------------

def get_remote_tags(repo_url: str) -> list[str]:
    """Fetch all version tags from the remote repo (no local clone needed).
    Returns list of tag names like ['v0.6.2-alpha', 'v0.6.5-alpha', ...].
    """
    try:
        result = subprocess.run(
            ["git", "ls-remote", "--tags", "--refs", repo_url],
            capture_output=True, timeout=30,
            encoding='utf-8', errors='replace'
        )
        if result.returncode != 0:
            return []
        tags = []
        for line in result.stdout.strip().split("\n"):
            if not line:
                continue
            # Format: "<sha>\trefs/tags/<tagname>"
            parts = line.split("\t")
            if len(parts) >= 2:
                ref = parts[1]
                if ref.startswith("refs/tags/"):
                    tag = ref[len("refs/tags/"):]
                    # Skip non-version tags and ^{} dereferences
                    if not tag.endswith("^{}"):
                        tags.append(tag)
        return tags
    except Exception:
        return []


def get_latest_remote_tag(repo_url: str) -> str | None:
    """Return the latest version tag from the remote repo.

    Sorts tags using version-aware comparison.
    Returns None if no version tags found.
    """
    all_tags = get_remote_tags(repo_url)
    # Filter to version-like tags: v<num>.<num>...
    import re
    version_tags = [t for t in all_tags if re.match(r'^v?\d+\.\d+', t)]
    if not version_tags:
        return None
    version_tags.sort(key=version_sort_key, reverse=True)
    return version_tags[0]


# ---------------------------------------------------------------------------
# Cache management
# ---------------------------------------------------------------------------

def ensure_cache_dir(kb_root: Path, config: dict) -> Path:
    """Return the starter cache directory path."""
    cache_rel = config.get("starter_cache_dir", ".pkb_system/starter_cache")
    return kb_root / cache_rel


def get_cache_head(cache_dir: Path) -> str | None:
    """Get the current HEAD description of the cache repo."""
    try:
        result = subprocess.run(
            ["git", "-C", str(cache_dir), "describe", "--tags", "--always"],
            capture_output=True, timeout=10,
            encoding='utf-8', errors='replace'
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return None


def is_git_repo(path: Path) -> bool:
    """Check if path is a git repository."""
    git_dir = path / ".git"
    if git_dir.is_dir():
        return True
    # Also check for bare repo or worktree
    try:
        result = subprocess.run(
            ["git", "-C", str(path), "rev-parse", "--git-dir"],
            capture_output=True, timeout=10,
            encoding='utf-8', errors='replace'
        )
        return result.returncode == 0
    except Exception:
        return False


def refresh_cache(cache_dir: Path, repo_url: str) -> dict:
    """Refresh the starter cache: fetch origin and all tags.

    Returns a dict with cache status information.
    Does NOT change the global CWD — all git ops use cwd=cache_dir.
    """
    status = {
        "cache_path": str(cache_dir),
        "cache_exists": cache_dir.is_dir(),
        "cache_is_repo": False,
        "cache_head": None,
        "cache_refreshed": False,
        "cache_error": None,
    }

    if not cache_dir.is_dir():
        return status

    if not is_git_repo(cache_dir):
        status["cache_error"] = "Cache directory exists but is not a git repo"
        return status

    status["cache_is_repo"] = True
    status["cache_head"] = get_cache_head(cache_dir)

    # Check if on detached HEAD — if so, checkout master first
    try:
        result = subprocess.run(
            ["git", "-C", str(cache_dir), "symbolic-ref", "-q", "HEAD"],
            capture_output=True, timeout=10,
            encoding='utf-8', errors='replace'
        )
        detached = (result.returncode != 0)
    except Exception:
        detached = True

    if detached:
        info(f"Cache is on detached HEAD ({status['cache_head']}), checking out master")
        try:
            subprocess.run(
                ["git", "-C", str(cache_dir), "checkout", "master"],
                capture_output=True, timeout=30,
                encoding='utf-8', errors='replace'
            )
        except Exception:
            # Try main instead
            try:
                subprocess.run(
                    ["git", "-C", str(cache_dir), "checkout", "main"],
                    capture_output=True, timeout=30,
                    encoding='utf-8', errors='replace'
                )
            except Exception:
                pass  # Stay on detached HEAD, will fix via checkout later

    # Fetch origin and ALL tags (--force to overwrite existing)
    try:
        subprocess.run(
            ["git", "-C", str(cache_dir), "fetch", "origin", "--tags", "--force"],
            capture_output=True, timeout=60,
            encoding='utf-8', errors='replace'
        )
        status["cache_refreshed"] = True
    except Exception as e:
        status["cache_error"] = f"Fetch failed: {e}"

    # Update cache HEAD after refresh
    status["cache_head"] = get_cache_head(cache_dir)
    return status


def clone_or_refresh_cache(cache_dir: Path, repo_url: str) -> dict:
    """Ensure cache exists and is up-to-date. Clone if missing.
    Returns cache status dict.
    """
    if not cache_dir.is_dir():
        info(f"Cloning starter repo to cache: {cache_dir}")
        cache_dir.parent.mkdir(parents=True, exist_ok=True)
        try:
            subprocess.run(
                ["git", "clone", repo_url, str(cache_dir)],
                capture_output=True, timeout=120,
                encoding='utf-8', errors='replace', check=True
            )
            info("Cache cloned successfully")
        except subprocess.CalledProcessError as e:
            die(f"Failed to clone {repo_url}: {e.stderr.strip() if e.stderr else e}")

    # Refresh (fetch tags)
    status = refresh_cache(cache_dir, repo_url)
    if status["cache_refreshed"]:
        info(f"Cache refreshed: {status['cache_head']}")
    elif status["cache_error"]:
        warn(f"Cache refresh issue: {status['cache_error']}")
    else:
        info("Cache exists (not refreshed — no remote changes)")
    return status


def checkout_in_cache(cache_dir: Path, ref: str) -> bool:
    """Checkout a specific tag or branch in the cache.
    All git ops use cwd=cache_dir — global CWD is never changed.
    """
    info(f"Checking out: {ref}")
    try:
        subprocess.run(
            ["git", "-C", str(cache_dir), "checkout", ref],
            capture_output=True, timeout=30,
            encoding='utf-8', errors='replace', check=True
        )
        ok(f"Checked out: {ref}")
        return True
    except subprocess.CalledProcessError as e:
        warn(f"Checkout failed: {e.stderr.strip() if e.stderr else e}")
        return False


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
            die(f"update_pyb.py not found in starter path: {update_py}")
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

    cache_dir = ensure_cache_dir(kb_root, config)

    # Clone or refresh cache (always fetches tags)
    cache_status = clone_or_refresh_cache(cache_dir, repo_url)

    # Print cache info
    info(f"Cache path: {cache_dir}")
    info(f"Cache HEAD: {cache_status.get('cache_head', 'unknown')}")
    if cache_status.get("cache_refreshed"):
        info("Cache was refreshed (remote tags fetched)")

    # Determine which ref to checkout
    checkout_ref = opts.get("checkout")
    if not checkout_ref:
        # Auto-select: use the latest remote tag
        latest_remote = get_latest_remote_tag(repo_url)
        if latest_remote:
            # Check if cache is already on that tag
            cache_head = get_cache_head(cache_dir)
            if cache_head and latest_remote in cache_head:
                info(f"Cache already at latest: {latest_remote}")
            else:
                info(f"Latest remote tag: {latest_remote}")
                checkout_in_cache(cache_dir, latest_remote)
            checkout_ref = latest_remote
        else:
            info("No version tags found on remote; using cache as-is")

    # Explicit checkout (overrides auto-selected latest)
    if opts.get("checkout"):
        checkout_ref = opts["checkout"]
        info(f"Selected checkout: {checkout_ref}")
        checkout_in_cache(cache_dir, checkout_ref)

    update_py = cache_dir / "scripts" / "update_pkb.py"
    if not update_py.is_file():
        die(f"update_pkb.py not found in cache: {update_py}")
    return cache_dir


# ---------------------------------------------------------------------------
# Run update
# ---------------------------------------------------------------------------

def run_update(starter_dir: Path, kb_root: Path, opts: dict):
    """Execute update_pkb.py from the resolved starter directory.

    IMPORTANT: Runs with cwd = kb_root, NOT starter_dir.
    This ensures hooks, settings, and paths all resolve relative to the KB root.
    """
    update_script = starter_dir / "scripts" / "update_pkb.py"
    cmd = [sys.executable, str(update_script), str(kb_root)]
    if opts.get("dry_run"):
        cmd.append("--dry-run")

    info(f"Running: {' '.join(cmd)}")
    info(f"Working directory: {kb_root}")
    result = subprocess.run(cmd, cwd=str(kb_root), timeout=300,
                            encoding='utf-8', errors='replace')

    if result.returncode != 0:
        warn(f"update_pkb.py exited with code {result.returncode}")
        if result.returncode == 2:
            info("Exit code 2 is non-fatal (may indicate fallback or partial update)")


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def write_report(kb_root: Path, opts: dict, config: dict, starter_dir: Path,
                 latest_remote: str | None = None):
    """Write update_client_report.md to the KB root."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    lines = [
        "# PKB Update Client Report",
        "",
        f"**Generated**: {now}",
        f"**KB root**: `{kb_root}`",
        f"**Mode**: {'DRY RUN' if opts.get('dry_run') else 'LIVE'}",
        f"**Installed version**: {config.get('starter_version', 'unknown')}",
    ]
    if latest_remote:
        lines.append(f"**Latest remote tag**: {latest_remote}")
    if opts.get("checkout"):
        lines.append(f"**Selected checkout**: {opts['checkout']}")
    lines += [
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
# Doctor — diagnostic checks
# ---------------------------------------------------------------------------

def run_doctor(kb_root: Path, config: dict, opts: dict) -> dict:
    """Run 10 diagnostic checks and return results dict.

    If opts['json_output'] is True, prints JSON to stdout instead of human-readable.
    """
    results = []

    # --- Check 1: CWD is KB root ---
    cwd = Path.cwd()
    is_kb_root = (kb_root.resolve() == cwd.resolve())
    # Also check if we're inside .pkb_system/starter_cache
    in_starter_cache = ".pkb_system" in str(cwd) and "starter_cache" in str(cwd)
    results.append({
        "check": "cwd_is_kb_root",
        "ok": is_kb_root,
        "detail": f"CWD={cwd}",
        "warning": "Current directory is inside .pkb_system/starter_cache! Run from KB root."
                   if in_starter_cache else ("" if is_kb_root else f"CWD is not KB root: {kb_root}"),
    })

    # --- Check 2: pkb.config.json exists ---
    config_exists = (kb_root / "pkb.config.json").is_file()
    results.append({
        "check": "pkb_config_exists",
        "ok": config_exists,
        "detail": f"{(kb_root / 'pkb.config.json')} {'found' if config_exists else 'MISSING'}",
    })

    # --- Check 3: starter_repo_url is valid ---
    repo_url = config.get("starter_repo_url", "")
    url_ok = bool(repo_url) and "<your-username>" not in repo_url
    results.append({
        "check": "starter_repo_url_valid",
        "ok": url_ok,
        "detail": f"starter_repo_url={'<not set>' if not repo_url else repo_url}",
        "warning": "" if url_ok else "Run with --repo-url to set a valid repository URL",
    })

    # --- Check 4: starter_cache exists ---
    cache_dir = ensure_cache_dir(kb_root, config)
    cache_exists = cache_dir.is_dir()
    cache_is_repo = is_git_repo(cache_dir) if cache_exists else False
    cache_head = get_cache_head(cache_dir) if cache_is_repo else None
    results.append({
        "check": "starter_cache_exists",
        "ok": cache_exists and cache_is_repo,
        "detail": f"Cache: {cache_dir} | repo={cache_is_repo} | HEAD={cache_head or 'N/A'}",
        "warning": "" if (cache_exists and cache_is_repo) else "Cache missing or corrupted — will be rebuilt on update",
    })

    # --- Check 5: Cache HEAD / tag ---
    results.append({
        "check": "cache_head",
        "ok": bool(cache_head),
        "detail": f"Cache HEAD: {cache_head or 'N/A'}",
    })

    # --- Check 6: Remote latest tag ---
    latest_remote = None
    remote_ok = False
    remote_detail = "No repo URL configured"
    if url_ok:
        latest_remote = get_latest_remote_tag(repo_url)
        remote_ok = latest_remote is not None
        remote_detail = f"Latest remote: {latest_remote or 'no version tags found'}"
    results.append({
        "check": "remote_latest_tag",
        "ok": remote_ok,
        "detail": remote_detail,
    })

    # --- Check 7: .claude/settings.json exists ---
    settings_path = kb_root / ".claude" / "settings.json"
    settings_exists = settings_path.is_file()
    results.append({
        "check": "settings_json_exists",
        "ok": settings_exists,
        "detail": f"{settings_path} {'found' if settings_exists else 'MISSING'}",
    })

    # --- Check 8: Hooks not pointing to starter_cache ---
    hooks_ok = True
    hooks_detail = "settings.json not found"
    if settings_exists:
        try:
            settings = json.loads(settings_path.read_text(encoding="utf-8"))
            hook_commands = []
            for event_name, event_hooks in settings.get("hooks", {}).items():
                for matcher_block in event_hooks:
                    for hook in matcher_block.get("hooks", []):
                        cmd = hook.get("command", "")
                        hook_commands.append(cmd)
            # Check for starter_cache in hook commands
            polluted = [c for c in hook_commands if "starter_cache" in c or ".pkb_system" in c]
            if polluted:
                hooks_ok = False
                hooks_detail = f"HOOKS POLLUTED: {polluted}"
            else:
                hooks_detail = f"All {len(hook_commands)} hook commands clean (no starter_cache references)"
        except Exception as e:
            hooks_detail = f"Error reading settings.json: {e}"
    results.append({
        "check": "hooks_path_ok",
        "ok": hooks_ok,
        "detail": hooks_detail,
        "warning": "" if hooks_ok else (
            "Hook commands reference .pkb_system/starter_cache! "
            "Run update with --apply to fix, or manually edit .claude/settings.json"
        ),
    })

    # --- Check 9: .claude/hooks/05_stop.py exists ---
    stop_hook = kb_root / ".claude" / "hooks" / "05_stop.py"
    stop_exists = stop_hook.is_file()
    results.append({
        "check": "hook_05_stop_exists",
        "ok": stop_exists,
        "detail": f"{stop_hook} {'found' if stop_exists else 'MISSING'}",
    })

    # --- Check 10: Bun not found note ---
    results.append({
        "check": "bun_non_blocking",
        "ok": True,
        "detail": (
            "'Bun not found' is a non-blocking external hook issue. "
            "PKB Starter does not use or require Bun. All PKB hooks are Python 3.9+. "
            "Check your global Claude Code hook settings if this error persists."
        ),
    })

    # Output
    if opts.get("json_output"):
        print(json.dumps(results, indent=2, ensure_ascii=False))
    else:
        print()
        print("=" * 60)
        print("  PKB Update Doctor — Diagnostic Report")
        print("=" * 60)
        print(f"  KB root: {kb_root}")
        print(f"  CWD: {cwd}")
        print()
        all_ok = True
        for r in results:
            icon = "[OK]" if r["ok"] else "[!!]"
            line = f"  {icon} {r['check']}: {r['detail']}"
            # Truncate long lines
            if len(line) > 120:
                line = line[:117] + "..."
            print(line)
            if r.get("warning"):
                print(f"       WARNING: {r['warning']}")
                all_ok = False
        print()
        print("=" * 60)
        if all_ok:
            ok("All critical checks passed")
        else:
            warn("Some checks need attention (see WARNING lines above)")
        print()

    return {"checks": results}


# ---------------------------------------------------------------------------
# Hook path repair
# ---------------------------------------------------------------------------

def repair_hook_paths(kb_root: Path, dry_run: bool = True) -> list[str]:
    """Check and optionally fix hook paths in .claude/settings.json.

    Detects any hook command that references .pkb_system/starter_cache
    and replaces it with the correct KB-relative path.

    Returns list of actions taken.
    """
    actions = []
    settings_path = kb_root / ".claude" / "settings.json"
    if not settings_path.is_file():
        return ["settings.json not found — nothing to repair"]

    try:
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
        modified = False

        for event_name, event_hooks in settings.get("hooks", {}).items():
            for matcher_block in event_hooks:
                for hook in matcher_block.get("hooks", []):
                    cmd = hook.get("command", "")
                    if "starter_cache" in cmd or ".pkb_system" in cmd:
                        old_cmd = cmd
                        # Replace starter_cache paths with correct KB-relative paths
                        # Pattern: .../.pkb_system/starter_cache/.claude/hooks/xxx.py
                        # Target: .claude/hooks/xxx.py
                        import re
                        new_cmd = re.sub(
                            r'\.pkb_system[/\\]starter_cache[/\\]\.claude[/\\]hooks[/\\]',
                            '.claude/hooks/',
                            cmd
                        )
                        new_cmd = re.sub(
                            r'[^"\'\s]*\.pkb_system[/\\]starter_cache[/\\]',
                            '',
                            new_cmd
                        )
                        new_cmd = new_cmd.strip()
                        if not new_cmd or new_cmd == old_cmd:
                            # Fallback: extract just the script name and use KB-relative path
                            script_name = old_cmd.split("/")[-1].split("\\")[-1]
                            if script_name.endswith(".py"):
                                new_cmd = f"python .claude/hooks/{script_name}"

                        action = f"Hook repair: '{old_cmd}' -> '{new_cmd}'"
                        if dry_run:
                            actions.append(f"[DRY-RUN] Would repair: {action}")
                        else:
                            hook["command"] = new_cmd
                            modified = True
                            actions.append(f"[REPAIRED] {action}")

        if modified and not dry_run:
            settings_path.write_text(
                json.dumps(settings, indent=2, ensure_ascii=False),
                encoding="utf-8"
            )
            actions.append("settings.json saved with repaired hook paths")

        if not actions:
            actions.append("No hook path pollution detected")

    except Exception as e:
        actions.append(f"Error repairing hooks: {e}")

    return actions


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
    # -------------------------------------------------------------------
    apply_mode = "--apply" in sys.argv
    dry_run = not apply_mode
    doctor_mode = "--doctor" in sys.argv
    json_output = "--json" in sys.argv

    # Extract flag values
    opts = {
        "dry_run": dry_run,
        "starter_path": None,
        "repo_url": None,
        "checkout": None,
        "json_output": json_output,
    }
    for idx, arg in enumerate(sys.argv):
        if arg == "--starter-path" and idx + 1 < len(sys.argv):
            opts["starter_path"] = sys.argv[idx + 1]
        if arg == "--repo-url" and idx + 1 < len(sys.argv):
            opts["repo_url"] = sys.argv[idx + 1]
        if arg == "--checkout" and idx + 1 < len(sys.argv):
            opts["checkout"] = sys.argv[idx + 1]

    # -------------------------------------------------------------------
    # Early CWD check: refuse to run from inside starter_cache
    # (Must happen before load_config because starter_cache has no config)
    # -------------------------------------------------------------------
    if not kb_root.is_dir():
        die(f"KB root not found: {kb_root}")
    cwd = Path.cwd()
    if ".pkb_system" in str(cwd) and "starter_cache" in str(cwd):
        die(
            f"Current working directory is inside starter_cache:\n"
            f"  {cwd}\n"
            f"Please cd to the KB root and re-run:\n"
            f"  cd <your-kb-root>\n"
            f"  python tools/pkb_update_client.py"
        )

    if not check_git():
        die("Git is required but not found. Install Git and try again.")

    config = load_config(kb_root)
    installed_version = config.get("starter_version", config.get("version", "unknown"))

    # -------------------------------------------------------------------
    # Doctor mode — diagnostics only, then exit
    # -------------------------------------------------------------------
    if doctor_mode:
        run_doctor(kb_root, config, opts)
        # Also show hook repair preview if needed
        settings_path = kb_root / ".claude" / "settings.json"
        if settings_path.is_file():
            repair_actions = repair_hook_paths(kb_root, dry_run=True)
            if len(repair_actions) > 1 or "No hook path pollution" not in repair_actions[0]:
                print("--- Hook Path Check ---")
                for action in repair_actions:
                    print(f"  {action}")
        return

    # -------------------------------------------------------------------
    # Normal update flow
    # -------------------------------------------------------------------
    info(f"KB root: {kb_root}")
    info(f"Installed version: {installed_version}")

    # Discover latest remote tag (before resolver, to display to user)
    repo_url = opts.get("repo_url") or config.get("starter_repo_url", "")
    latest_remote = None
    if repo_url and "<your-username>" not in repo_url:
        latest_remote = get_latest_remote_tag(repo_url)
        if latest_remote:
            info(f"Latest remote tag: {latest_remote}")
            if version_lt(installed_version.lstrip("v"), latest_remote.lstrip("v")):
                info(f"Update available: {installed_version} -> {latest_remote}")
            else:
                info(f"Installed version ({installed_version}) is current or newer than remote ({latest_remote})")
        else:
            info("No version tags found on remote")
    print()

    # -------------------------------------------------------------------
    # Announce mode clearly before any work
    # -------------------------------------------------------------------
    if dry_run:
        info("=== DRY-RUN MODE: no KB files will be changed ===")
        info("=== (git cache refresh is allowed — this does not change your KB) ===")
    else:
        info("=== APPLY MODE: files may be changed ===")
    print()

    starter_dir = resolve_starter_path(opts, config, kb_root)

    # -------------------------------------------------------------------
    # Run update_pkb.py with cwd = kb_root (NOT starter_dir)
    # This ensures hooks, settings, and all paths resolve relative to KB root.
    # -------------------------------------------------------------------
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

        # Check and repair hook paths
        repair_actions = repair_hook_paths(kb_root, dry_run=False)
        for action in repair_actions:
            if "[REPAIRED]" in action:
                ok(action)
            elif "No hook path pollution" in action:
                info(action)
            else:
                info(action)

    write_report(kb_root, opts, config, starter_dir, latest_remote)

    print()
    ok("Update client finished.")
    if opts.get("dry_run"):
        info("This was a dry run. Run with --apply to apply changes.")
        if latest_remote and version_lt(installed_version.lstrip("v"), latest_remote.lstrip("v")):
            info(f"Update {installed_version} -> {latest_remote} is available.")
    else:
        info("Changes have been applied.")


if __name__ == "__main__":
    main()
