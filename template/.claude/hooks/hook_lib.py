#!/usr/bin/env python3
"""
PKB Hook Library — shared utilities for all PKB hook scripts.

Provides:
  - get_root()          → Path to PKB_ROOT (from env var)
  - is_safe_to_run()    → Idempotency guard (cooldown-based)
  - warn() / block()    → Severity-graded output functions
  - hook_timer()        → Context manager for timeout enforcement
  - check_pkb_env()     → Verify PKB_ROOT and required directories exist
  - load_hook_config()  → Merge settings.json + settings.local.json for a hook

Design principles:
  - Hook failures should not block workflow (return 0 on exception)
  - PreToolUse safety violations are the only blocking case
  - All hooks support --dry-run for testing
"""

import os
import sys
import json
import time
import signal
import threading
from pathlib import Path
from datetime import datetime, timezone


# ──────────────────────────────────────────────
# Environment
# ──────────────────────────────────────────────

def get_root() -> Path:
    """Get PKB root directory from PKB_ROOT env var."""
    root = os.environ.get("PKB_ROOT")
    if root:
        return Path(root)
    # Fallback: walk up from this script
    p = Path(__file__).resolve().parents[2]
    return p


def check_pkb_env() -> dict:
    """Verify PKB environment is ready. Returns {ok: bool, issues: [str]}."""
    issues = []
    root = get_root()
    required = [
        root / "tools" / "pkb_auto.py",
        root / ".claude" / "settings.json",
        root / "wiki",
        root / "raw",
    ]
    for p in required:
        if not p.exists():
            issues.append(f"Missing: {p.relative_to(root)}")
    return {"ok": len(issues) == 0, "issues": issues, "root": str(root)}


# ──────────────────────────────────────────────
# Idempotency
# ──────────────────────────────────────────────

def _hook_state_dir() -> Path:
    """Get or create the hook state cache directory."""
    root = get_root()
    d = root / "_INBOX" / ".hook_state"
    d.mkdir(parents=True, exist_ok=True)
    return d


def is_safe_to_run(hook_name: str, cooldown_secs: int = 60) -> bool:
    """
    Return True if the hook should run now (outside cooldown window).
    Uses a JSON cache file in _INBOX/.hook_state/.
    If cache is missing or corrupt, always returns True.
    """
    state_file = _hook_state_dir() / f"{hook_name}.json"
    now = time.time()
    try:
        if state_file.exists():
            data = json.loads(state_file.read_text(encoding="utf-8"))
            last_run = data.get("last_run", 0)
            if now - last_run < cooldown_secs:
                return False
    except Exception:
        pass
    # Update timestamp
    state_file.write_text(
        json.dumps({"last_run": now, "hook": hook_name}, indent=2),
        encoding="utf-8",
    )
    return True


def clear_hook_state(hook_name: str = None):
    """Clear hook state cache (useful for testing)."""
    d = _hook_state_dir()
    if hook_name:
        f = d / f"{hook_name}.json"
        if f.exists():
            f.unlink()
    else:
        for f in d.glob("*.json"):
            f.unlink()


# ──────────────────────────────────────────────
# Output protocol
# ──────────────────────────────────────────────

def warn(msg: str) -> None:
    """Print a warning (non-blocking)."""
    print(f"[PKB Hook ⚠️] {msg}", file=sys.stderr)


def block(msg: str) -> None:
    """Print a blocking message and exit with code 1."""
    print(f"[PKB Hook 🛑 BLOCKED] {msg}", file=sys.stderr)
    sys.exit(1)


def info(msg: str) -> None:
    """Print informational output."""
    print(f"[PKB Hook] {msg}")


def ok(msg: str = "") -> None:
    """Print success (silent by default, verbose if msg provided)."""
    if msg:
        print(f"[PKB Hook ✅] {msg}")


# ──────────────────────────────────────────────
# Timeout
# ──────────────────────────────────────────────

class HookTimeout(Exception):
    """Raised when a hook exceeds its time budget."""
    pass


class hook_timer:
    """
    Context manager that enforces a timeout on hook execution.
    Uses signal.alarm on Unix, threading.Timer fallback on Windows.

    Usage:
        with hook_timer(30):
            do_work()
    """

    def __init__(self, timeout_secs: int):
        self.timeout = timeout_secs
        self.timer = None
        self.timed_out = False

    def _handle_timeout(self):
        self.timed_out = True
        print(
            f"[PKB Hook ⚠️] Timeout after {self.timeout}s — aborting hook",
            file=sys.stderr,
        )

    def __enter__(self):
        try:
            # Prefer signal-based (Unix)
            signal.signal(signal.SIGALRM, lambda s, f: self._handle_timeout())
            signal.alarm(self.timeout)
        except (AttributeError, ValueError):
            # Fallback to threading (Windows)
            self.timer = threading.Timer(self.timeout, self._handle_timeout)
            self.timer.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            signal.alarm(0)
        except Exception:
            pass
        if self.timer:
            self.timer.cancel()
        if self.timed_out:
            raise HookTimeout(f"Hook exceeded {self.timeout}s budget")
        return False


# ──────────────────────────────────────────────
# Config merging (Phase 3)
# ──────────────────────────────────────────────

def load_hook_config(hook_name: str) -> dict:
    """
    Load merged hook config from settings.json + settings.local.json.
    Returns {"enabled": True, "config": {...}} dict.
    If settings.local.json doesn't exist, returns settings.json config only.
    """
    root = get_root()
    config = {"enabled": True, "config": {}}

    # Load from settings.json
    settings_path = root / ".claude" / "settings.json"
    try:
        if settings_path.exists():
            data = json.loads(settings_path.read_text(encoding="utf-8"))
            hooks = data.get("hooks", {}).get(hook_name, [])
            if hooks:
                config["_settings_json"] = hooks
    except Exception:
        pass

    # Merge from settings.local.json
    local_path = root / ".claude" / "settings.local.json"
    try:
        if local_path.exists():
            data = json.loads(local_path.read_text(encoding="utf-8"))
            hook_cfg = data.get("hooks", {}).get(hook_name, {})
            if isinstance(hook_cfg, dict):
                config["enabled"] = hook_cfg.get("enabled", config["enabled"])
                config["config"] = {**config["config"], **hook_cfg.get("config", {})}
    except Exception:
        pass

    return config


# ──────────────────────────────────────────────
# Tool input parsing (for PreToolUse / PostToolUse)
# ──────────────────────────────────────────────

def parse_tool_input() -> dict:
    """
    Parse the CLAUDE_TOOL_INPUT and CLAUDE_TOOL_NAME env vars.
    CLAUDE_TOOL_INPUT is JSON: {"tool_name": "...", "tool_input": {...}}

    Returns {"tool_name": str, "tool_input": dict, "ok": bool, "error": str}
    """
    tool_input_raw = os.environ.get("CLAUDE_TOOL_INPUT", "")
    tool_name = os.environ.get("CLAUDE_TOOL_NAME", "")

    if not tool_input_raw:
        return {"tool_name": tool_name, "tool_input": {}, "ok": False, "error": "CLAUDE_TOOL_INPUT not set"}

    try:
        data = json.loads(tool_input_raw)
        return {
            "tool_name": data.get("tool_name", tool_name),
            "tool_input": data.get("tool_input", {}),
            "ok": True,
            "error": "",
        }
    except json.JSONDecodeError as e:
        return {"tool_name": tool_name, "tool_input": {}, "ok": False, "error": str(e)}


# ──────────────────────────────────────────────
# Git helpers
# ──────────────────────────────────────────────

def git_staged_files() -> list:
    """Return list of files staged for commit (git diff --cached --name-only)."""
    import subprocess
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            capture_output=True, text=True, cwd=str(get_root()), timeout=10,
        )
        if result.returncode == 0:
            return [f.strip() for f in result.stdout.splitlines() if f.strip()]
    except Exception:
        pass
    return []


def git_uncommitted_files() -> list:
    """Return list of modified or untracked files."""
    import subprocess
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True, text=True, cwd=str(get_root()), timeout=10,
        )
        if result.returncode == 0:
            files = []
            for line in result.stdout.splitlines():
                if len(line) > 3:
                    files.append(line[3:].strip())
            return files
    except Exception:
        pass
    return []


def git_recent_commits(count: int = 5) -> list:
    """Return recent commit subjects."""
    import subprocess
    try:
        result = subprocess.run(
            ["git", "log", f"-{count}", "--format=%h %s"],
            capture_output=True, text=True, cwd=str(get_root()), timeout=10,
        )
        if result.returncode == 0:
            return [l.strip() for l in result.stdout.splitlines() if l.strip()]
    except Exception:
        pass
    return []


# ──────────────────────────────────────────────
# Content scanning
# ──────────────────────────────────────────────

# Patterns that indicate secrets (never commit these)
SECRET_PATTERNS = [
    (r'api_key\s*[=:]\s*["\']?\w{20,}', "API key assignment"),
    (r'api[_-]?key\s*[=:]\s*["\']?\w{20,}', "API key assignment (alt)"),
    (r'secret\s*[=:]\s*["\']?\w{20,}', "Secret assignment"),
    (r'password\s*[=:]\s*["\'][^"\']+["\']', "Hardcoded password"),
    (r'-----BEGIN\s+(RSA\s+)?PRIVATE\s+KEY-----', "Private key (PEM)"),
    (r'-----BEGIN\s+EC\s+PRIVATE\s+KEY-----', "EC private key (PEM)"),
    (r'sk-(?:ant|proj)?-?[a-zA-Z0-9_-]{20,}', "OpenAI/Anthropic API key pattern"),
    (r'token\s*[=:]\s*["\']?[\w-]{20,}', "Token assignment"),
    (r'access_key\s*[=:]\s*["\']?\w{20,}', "Access key assignment"),
    (r'ghp_[a-zA-Z0-9]{36}', "GitHub personal access token"),
    (r'gho_[a-zA-Z0-9]{36}', "GitHub OAuth token"),
    (r'ghu_[a-zA-Z0-9]{36}', "GitHub user token"),
]

SENSITIVE_FILE_PATTERNS = [
    ".env", ".env.local", ".env.production",
    "credentials.json", "credentials.yml", "credentials.yaml",
    "service-account.json", "service_account.json",
    "id_rsa", "id_ecdsa", "id_ed25519",
]

SENSITIVE_EXTENSIONS = [".pem", ".key", ".p12", ".pfx", ".jks", ".keystore"]


def scan_content_for_secrets(content: str) -> list:
    """Scan text content for secret patterns. Returns list of (pattern, description)."""
    import re
    findings = []
    for pattern, desc in SECRET_PATTERNS:
        if re.search(pattern, content, re.IGNORECASE):
            findings.append((pattern, desc))
    return findings


def is_sensitive_filename(filepath: str) -> tuple:
    """Check if a filename matches sensitive patterns. Returns (is_sensitive, reason)."""
    import fnmatch
    basename = os.path.basename(filepath)
    for pattern in SENSITIVE_FILE_PATTERNS:
        if fnmatch.fnmatch(basename, pattern):
            return (True, f"Filename matches sensitive pattern: {pattern}")
    ext = os.path.splitext(basename)[1].lower()
    if ext in SENSITIVE_EXTENSIONS:
        return (True, f"File extension is sensitive: {ext}")
    return (False, "")


# ──────────────────────────────────────────────
# Protected paths
# ──────────────────────────────────────────────

PROTECTED_PREFIXES = [
    "raw/",            # Raw layer is append-only
    ".claude/settings.json",  # Core config — edit with care
]

PROTECTED_DELETE_PREFIXES = [
    "raw/",            # Never delete raw materials
    "wiki/",           # Wiki pages — archive instead of delete
    ".claude/",        # Config files
]


def is_protected_write_path(filepath: str) -> tuple:
    """Check if writing to this path should be blocked/warned. Returns (is_protected, reason)."""
    rel = filepath.replace("\\", "/")
    for prefix in PROTECTED_PREFIXES:
        if rel.startswith(prefix) or rel == prefix.rstrip("/"):
            return (True, f"Writing to protected path: {prefix}")
    return (False, "")


def is_protected_delete_path(filepath: str) -> tuple:
    """Check if deleting this path should be blocked. Returns (is_protected, reason)."""
    rel = filepath.replace("\\", "/")
    # Normalize: strip leading / or ./
    rel = rel.lstrip("/").lstrip("./")
    for prefix in PROTECTED_DELETE_PREFIXES:
        if rel.startswith(prefix):
            return (True, f"Deleting from protected path: {prefix}")
    return (False, "")


# ──────────────────────────────────────────────
# Wiki helpers
# ──────────────────────────────────────────────

def count_wiki_pages() -> dict:
    """Count wiki pages by type. Returns {concepts: N, sources: N, projects: N, total: N}."""
    root = get_root()
    counts = {"concepts": 0, "sources": 0, "projects": 0, "outputs": 0, "total": 0}
    wiki_root = root / "wiki"
    if not wiki_root.exists():
        return counts
    for subdir in ["concepts", "sources", "projects", "outputs"]:
        d = wiki_root / subdir
        if d.exists():
            n = len(list(d.glob("*.md")))
            counts[subdir] = n
            counts["total"] += n
    return counts


# ──────────────────────────────────────────────
# Dry-run detection
# ──────────────────────────────────────────────

def is_dry_run() -> bool:
    """Check if --dry-run was passed."""
    return "--dry-run" in sys.argv


# ──────────────────────────────────────────────
# Main (for testing)
# ──────────────────────────────────────────────

if __name__ == "__main__":
    env = check_pkb_env()
    print(f"PKB Root: {env['root']}")
    print(f"Environment: {'OK' if env['ok'] else 'ISSUES: ' + str(env['issues'])}")
    print(f"Wiki pages: {count_wiki_pages()}")
    print(f"Uncommitted: {git_uncommitted_files()}")
    print(f"Dry run: {is_dry_run()}")
    # Test idempotency
    print(f"Safe to run 'test': {is_safe_to_run('test', cooldown_secs=5)}")
    print(f"Safe to run 'test' again: {is_safe_to_run('test', cooldown_secs=5)}")
