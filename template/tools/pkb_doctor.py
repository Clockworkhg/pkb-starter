#!/usr/bin/env python3
"""
PKB Runtime Doctor — comprehensive environment diagnostics.

Usage:
    python tools/pkb_doctor.py            # Full diagnostic report
    python tools/pkb_doctor.py --json     # Machine-readable output
    python tools/pkb_doctor.py --quiet    # Exit code only (0=healthy, 1=issues)

Checks:
    PKB root, Git, Python, Node, npx, Bun, Chrome executable,
    Chrome profile, Chrome debug port, .mcp.json, chrome-devtools MCP,
    MCP approval state, MCP connection, Active task, SessionStart hook,
    Stop hook, Git ignore coverage, Private path leakage.
"""

import os
import sys
import json
import subprocess
import urllib.request
import urllib.error
from pathlib import Path

# Ensure UTF-8 output on Windows terminals
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def get_root() -> Path:
    return Path(os.environ.get("PKB_ROOT", Path(__file__).resolve().parents[1]))


class CheckResult:
    def __init__(self, name: str):
        self.name = name
        self.status = "SKIP"  # PASS, WARN, FAIL, SKIP
        self.detail = ""
        self.suggestion = ""

    def to_dict(self):
        return {
            "name": self.name,
            "status": self.status,
            "detail": self.detail,
            "suggestion": self.suggestion,
        }


class Doctor:
    def __init__(self, root: Path):
        self.root = root
        self.results: list[CheckResult] = []

    def check(self, name: str, fn) -> "CheckResult":
        r = CheckResult(name)
        try:
            fn(r)
        except Exception as e:
            r.status = "FAIL"
            r.detail = str(e)
        self.results.append(r)
        return r

    def _set_pass(self, r, detail=""):
        r.status = "PASS"
        if detail:
            r.detail = detail

    def _set_fail(self, r, detail="", suggestion=""):
        r.status = "FAIL"
        if detail:
            r.detail = detail
        if suggestion:
            r.suggestion = suggestion

    def _set_warn(self, r, detail="", suggestion=""):
        r.status = "WARN"
        if detail:
            r.detail = detail
        if suggestion:
            r.suggestion = suggestion

    def run_all(self):
        root = self.root

        # PKB root
        def _check_pkb_root(r):
            if root.exists() and root.is_dir():
                self._set_pass(r, str(root))
            else:
                self._set_fail(r, str(root))
        self.check("PKB root", _check_pkb_root)

        # Git repository
        self.check("Git repository", lambda r: self._check_git(r))

        # Python
        def _check_python(r):
            if sys.version_info >= (3, 8):
                self._set_pass(r, f"Python {sys.version.split()[0]}")
            else:
                self._set_fail(r, f"Python {sys.version} (need 3.8+)")
        self.check("Python", _check_python)

        # Node.js
        self.check("Node.js", lambda r: self._check_cmd(r, "node", "--version", "Node.js"))

        # npx
        self.check("npx", lambda r: self._check_cmd(r, "npx", "--version", "npx"))

        # Bun (optional)
        self.check("Bun", lambda r: self._check_cmd_optional(r, "bun", "--version", "Bun", "Optional Bun hooks disabled"))

        # Chrome executable
        self.check("Chrome executable", lambda r: self._check_chrome(r))

        # Chrome profile path
        def _check_chrome_profile(r):
            profile_dir = root / ".pkb-local" / "chrome-profile"
            if profile_dir.exists():
                self._set_pass(r, str(profile_dir))
            else:
                self._set_warn(r, f"Not yet created: {profile_dir}", r"Run: .\pkb.ps1 cnki to auto-create")
        self.check("Chrome profile path", _check_chrome_profile)

        # Chrome debug port
        self.check("Chrome debug port", lambda r: self._check_port(r))

        # Chrome /json/version
        self.check("Chrome /json/version", lambda r: self._check_json_version(r))

        # Root .mcp.json
        mcp_path = root / ".mcp.json"
        def _check_mcp_exists(r):
            if mcp_path.exists():
                self._set_pass(r, "Found at repo root")
            else:
                self._set_fail(r, "Not found at repo root",
                               "Create .mcp.json at project root with chrome-devtools MCP config")
        self.check("Root .mcp.json", _check_mcp_exists)

        # chrome-devtools MCP entry
        self.check("chrome-devtools MCP entry", lambda r: self._check_mcp_entry(r, mcp_path))

        # MCP command validity
        self.check("MCP command validity", lambda r: self._check_mcp_command(r))

        # MCP approval state (we can't directly check, but we can note)
        def _check_mcp_approval(r):
            self._set_warn(r, "Cannot auto-detect — check `claude mcp list`",
                           "If chrome-devtools shows 'pending', approve it in Claude Code")
        self.check("MCP approval state", _check_mcp_approval)

        # MCP connection state
        self.check("MCP connection state", lambda r: self._check_mcp_connection(r))

        # Active task state
        task_file = root / ".pkb-local" / "state" / "active-task.json"
        self.check("Active task state", lambda r: self._check_active_task(r, task_file))

        # SessionStart hook
        self.check("SessionStart hook", lambda r: self._check_hook(r, "SessionStart"))

        # Stop hook
        self.check("Stop hook", lambda r: self._check_hook(r, "Stop"))

        # Git ignore coverage
        self.check("Git ignore coverage", lambda r: self._check_gitignore(r, root))

        # Private path leakage
        self.check("Private path leakage", lambda r: self._check_privacy(r, root))

        # Summary
        self._print_results()

    def _run_cmd(self, args, timeout=10):
        """Run command with UTF-8 encoding (Windows compat)."""
        return subprocess.run(
            args, capture_output=True, timeout=timeout,
            encoding="utf-8", errors="replace",
        )

    def _check_cmd(self, r, cmd: str, arg: str, label: str):
        try:
            result = self._run_cmd([cmd, arg])
            if result.returncode == 0:
                r.status = "PASS"
                r.detail = result.stdout.strip().split("\n")[0]
            else:
                r.status = "FAIL"
                r.detail = f"Exit code {result.returncode}"
                r.suggestion = f"Install {label}"
        except FileNotFoundError:
            r.status = "FAIL"
            r.detail = f"{label} not found"
            r.suggestion = f"Install {label}"
        except Exception as e:
            r.status = "FAIL"
            r.detail = str(e)

    def _check_cmd_optional(self, r, cmd: str, arg: str, label: str, warn_msg: str):
        try:
            result = self._run_cmd([cmd, arg])
            if result.returncode == 0:
                r.status = "PASS"
                r.detail = result.stdout.strip().split("\n")[0]
            else:
                r.status = "WARN"
                r.detail = f"Exit code {result.returncode} — {warn_msg}"
        except FileNotFoundError:
            r.status = "WARN"
            r.detail = f"{label} not installed — {warn_msg}"
        except Exception as e:
            r.status = "WARN"
            r.detail = f"{label} check failed: {e}"

    def _check_git(self, r):
        try:
            result = self._run_cmd(
                ["git", "rev-parse", "--show-toplevel"],
                timeout=10,
            )
            if result.returncode == 0:
                r.status = "PASS"
                r.detail = result.stdout.strip()
            else:
                r.status = "FAIL"
                r.detail = "Not a git repository"
        except FileNotFoundError:
            r.status = "FAIL"
            r.detail = "Git not found"
        except Exception as e:
            r.status = "FAIL"
            r.detail = str(e)

    def _find_chrome(self) -> str:
        candidates = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
        ]
        for p in candidates:
            if p and os.path.isfile(p):
                return p
        # Try PATH
        import shutil
        found = shutil.which("chrome.exe") or shutil.which("chrome")
        return found or ""

    def _check_chrome(self, r):
        chrome = self._find_chrome()
        if chrome:
            r.status = "PASS"
            r.detail = chrome
        else:
            r.status = "FAIL"
            r.detail = "Chrome not found"
            r.suggestion = "Install Google Chrome or Chromium"

    def _check_port(self, r):
        debug_url = os.environ.get("CHROME_DEBUG_URL", "http://127.0.0.1:9222")
        port = debug_url.split(":")[-1]
        try:
            req = urllib.request.Request(debug_url + "/json", method="HEAD")
            urllib.request.urlopen(req, timeout=3)
            r.status = "PASS"
            r.detail = f"Port {port} reachable"
        except Exception:
            # Try to detect if Chrome is running without debug port
            chrome = self._find_chrome()
            if chrome:
                # Check via tasklist
                try:
                    result = self._run_cmd(
                        ["tasklist", "/FI", "IMAGENAME eq chrome.exe"],
                        timeout=10,
                    )
                    if "chrome.exe" in result.stdout:
                        # Chrome is running but debug port isn't answering
                        r.status = "WARN"
                        r.detail = f"Port {port} not answering, but Chrome is running (may lack --remote-debugging-port)"
                        r.suggestion = "Close Chrome and run: .\\pkb.ps1 cnki"
                        return
                except Exception:
                    pass
            r.status = "FAIL"
            r.detail = f"Port {port} not reachable"
            r.suggestion = "Run: .\\pkb.ps1 cnki to start Chrome with debug port"

    def _check_json_version(self, r):
        debug_url = os.environ.get("CHROME_DEBUG_URL", "http://127.0.0.1:9222")
        try:
            resp = urllib.request.urlopen(debug_url + "/json/version", timeout=3)
            data = json.loads(resp.read().decode())
            r.status = "PASS"
            r.detail = f"Chrome {data.get('Browser', 'unknown')}"
        except urllib.error.URLError as e:
            r.status = "FAIL"
            r.detail = f"Cannot reach /json/version: {e.reason}"
        except json.JSONDecodeError:
            r.status = "FAIL"
            r.detail = "/json/version returned invalid JSON"
        except Exception as e:
            r.status = "FAIL"
            r.detail = str(e)

    def _check_mcp_entry(self, r, mcp_path: Path):
        if not mcp_path.exists():
            return  # Main check already FAILed
        try:
            data = json.loads(mcp_path.read_text(encoding="utf-8"))
            servers = data.get("mcpServers", {})
            if "chrome-devtools" in servers:
                r.status = "PASS"
                cfg = servers["chrome-devtools"]
                r.detail = f"Command: {cfg.get('command', '?')}, args: {cfg.get('args', [])}"
            else:
                r.status = "FAIL"
                r.detail = "No chrome-devtools entry in .mcp.json"
                r.suggestion = "Add chrome-devtools MCP server to .mcp.json"
        except json.JSONDecodeError:
            r.status = "FAIL"
            r.detail = ".mcp.json is invalid JSON"
        except Exception as e:
            r.status = "FAIL"
            r.detail = str(e)

    def _check_mcp_command(self, r):
        """Verify npx can resolve the MCP package."""
        try:
            result = self._run_cmd(
                ["npx", "-y", "chrome-devtools-mcp@latest", "--help"],
                timeout=30,
            )
            if result.returncode == 0 and "--browserUrl" in result.stdout:
                r.status = "PASS"
                r.detail = "chrome-devtools-mcp resolves correctly"
            else:
                r.status = "WARN"
                r.detail = f"npx returned code {result.returncode}"
        except subprocess.TimeoutExpired:
            r.status = "WARN"
            r.detail = "npx check timed out (may be downloading on first run)"
        except FileNotFoundError:
            r.status = "FAIL"
            r.detail = "npx not available"
        except Exception as e:
            r.status = "WARN"
            r.detail = str(e)

    def _check_mcp_connection(self, r):
        """Check if MCP can actually connect to Chrome."""
        debug_url = os.environ.get("CHROME_DEBUG_URL", "http://127.0.0.1:9222")
        try:
            resp = urllib.request.urlopen(debug_url + "/json", timeout=3)
            data = json.loads(resp.read().decode())
            if isinstance(data, list) and len(data) > 0:
                r.status = "PASS"
                r.detail = f"{len(data)} debuggable page(s) — MCP can connect"
            else:
                r.status = "WARN"
                r.detail = "Debug port reachable but no debuggable pages"
                r.suggestion = "Open a page in the debug Chrome instance"
        except Exception:
            r.status = "FAIL"
            r.detail = "Cannot connect to Chrome debug port — MCP server will fail to connect"
            r.suggestion = "Start Chrome with: .\\pkb.ps1 cnki"

    def _check_active_task(self, r, task_file: Path):
        if not task_file.exists():
            r.status = "WARN"
            r.detail = "No active task file"
            r.suggestion = "Create one with: python tools/pkb_task.py start"
            return
        try:
            data = json.loads(task_file.read_text(encoding="utf-8"))
            # Simple validation
            sv = data.get("schema_version")
            tid = data.get("task_id")
            status = data.get("status")
            if sv and tid and status:
                r.status = "PASS"
                r.detail = f"Task: {data.get('title', tid)} [{status}]"
            else:
                r.status = "WARN"
                r.detail = "Task file exists but missing required fields"
        except json.JSONDecodeError:
            r.status = "FAIL"
            r.detail = "Task file is corrupt JSON"
            r.suggestion = "Backup and recreate: python tools/pkb_task.py start"
        except Exception as e:
            r.status = "FAIL"
            r.detail = str(e)

    def _check_hook(self, r, hook_name: str):
        settings = self.root / ".claude" / "settings.json"
        if not settings.exists():
            r.status = "FAIL"
            r.detail = ".claude/settings.json not found"
            return
        try:
            data = json.loads(settings.read_text(encoding="utf-8"))
            hooks = data.get("hooks", {}).get(hook_name, [])
            if hooks:
                r.status = "PASS"
                r.detail = f"Configured ({len(hooks)} matcher(s))"
            else:
                r.status = "WARN"
                r.detail = f"No {hook_name} hook configured"
        except Exception as e:
            r.status = "FAIL"
            r.detail = str(e)

    def _check_gitignore(self, r, root: Path):
        gi = root / ".gitignore"
        issues = []
        if not gi.exists():
            r.status = "FAIL"
            r.detail = ".gitignore not found"
            return

        content = gi.read_text(encoding="utf-8")
        checks = [".pkb-local/", ".claude/handoff_", "=*"]
        for c in checks:
            if c not in content:
                issues.append(f"Missing: {c}")

        if issues:
            r.status = "WARN"
            r.detail = "; ".join(issues)
        else:
            r.status = "PASS"
            r.detail = ".pkb-local/, handoff, and experimental markers covered"

    def _check_privacy(self, r, root: Path):
        """Quick scan for private paths in public files."""
        private_signals = [
            r"<PKB_ROOT>",
            os.environ.get("USERPROFILE", ""),
            os.environ.get("HOME", ""),
        ]
        # Only check .mcp.json for private paths
        mcp = root / ".mcp.json"
        leaks = []
        if mcp.exists():
            content = mcp.read_text(encoding="utf-8")
            for sig in private_signals:
                if sig and sig in content:
                    leaks.append(f"Private path in .mcp.json")

        if leaks:
            r.status = "FAIL"
            r.detail = "; ".join(leaks)
        else:
            r.status = "PASS"
            r.detail = "No private paths in public .mcp.json"

    def _safe_print(self, text=""):
        """Print with encoding fallback for Windows consoles."""
        try:
            print(text)
        except UnicodeEncodeError:
            # Fall back to ASCII-safe version
            safe = text.encode("ascii", errors="replace").decode("ascii")
            print(safe)

    def _print_results(self):
        json_mode = "--json" in sys.argv
        quiet_mode = "--quiet" in sys.argv

        if json_mode:
            print(json.dumps([r.to_dict() for r in self.results], ensure_ascii=False, indent=2))
            return

        # Human-readable output with ASCII-safe icons
        status_icons = {"PASS": "[OK]", "WARN": "[!!]", "FAIL": "[XX]", "SKIP": "[--]"}
        has_fail = any(r.status == "FAIL" for r in self.results)

        if not quiet_mode:
            self._safe_print()
            self._safe_print("=" * 50)
            self._safe_print("  PKB Runtime Doctor")
            self._safe_print("=" * 50)

            for r in self.results:
                icon = status_icons.get(r.status, "[??]")
                line = f"  [{r.status}] {icon} {r.name}"
                if r.detail:
                    line += f" — {r.detail}"
                self._safe_print(line)
                if r.suggestion:
                    self._safe_print(f"         >> {r.suggestion}")

            self._safe_print("=" * 50)
            passes = sum(1 for r in self.results if r.status == "PASS")
            warns = sum(1 for r in self.results if r.status == "WARN")
            fails = sum(1 for r in self.results if r.status == "FAIL")
            skips = sum(1 for r in self.results if r.status == "SKIP")
            total = len(self.results)
            self._safe_print(f"  {passes} PASS / {warns} WARN / {fails} FAIL / {skips} SKIP ({total} checks)")
            self._safe_print("=" * 50)
            self._safe_print()

        sys.exit(1 if has_fail else 0)


def main():
    root = get_root()
    doctor = Doctor(root)
    doctor.run_all()


if __name__ == "__main__":
    main()
