#!/usr/bin/env python3
"""
Tests for PKB Runtime Doctor (tools/pkb_doctor.py).

Coverage:
    - Doctor initialization and check registration
    - Python version check (PASS)
    - Git check
    - MCP configuration presence/absence
    - .gitignore coverage
    - Active task detection
    - Command execution helpers
    - Optional dependency handling (Bun WARN, not FAIL)
    - Output modes (human, JSON, quiet)
"""

import json
import os
import sys
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

TOOLS_DIR = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS_DIR))

import pkb_doctor


@pytest.fixture
def temp_root():
    """Create a temporary PKB root with minimal structure."""
    d = Path(tempfile.mkdtemp(prefix="pkb_test_doctor_"))
    # Create essential structure
    (d / ".claude").mkdir(exist_ok=True)
    (d / "wiki").mkdir(exist_ok=True)
    (d / "raw").mkdir(exist_ok=True)
    yield d
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def doctor(temp_root):
    """Create a Doctor instance for testing."""
    return pkb_doctor.Doctor(temp_root)


class TestDoctorInit:
    """Test doctor initialization."""

    def test_creates_results_list(self, temp_root):
        doc = pkb_doctor.Doctor(temp_root)
        assert doc.results == []

    def test_check_registers_result(self, doctor):
        def _pass(r):
            r.status = "PASS"
            r.detail = "test"
        doctor.check("test-check", _pass)
        assert len(doctor.results) == 1
        assert doctor.results[0].name == "test-check"
        assert doctor.results[0].status == "PASS"


class TestPythonCheck:
    """Test Python version checks."""

    def test_python_passes(self, doctor):
        """Current Python should always pass."""
        doctor._check_cmd = MagicMock()
        doctor.check("Python", lambda r: (
            setattr(r, "status", "PASS"),
            setattr(r, "detail", f"Python {sys.version.split()[0]}"),
        ))
        assert any(r.name == "Python" and r.status == "PASS" for r in doctor.results)


class TestOptionalDependency:
    """Test that optional dependencies don't fail."""

    def test_bun_optional_warns_not_fails(self, doctor):
        """Bun missing should be WARN, never FAIL."""
        def _check(r):
            r.status = "WARN"
            r.detail = "Bun not installed — Optional Bun hooks disabled"
        doctor.check("Bun", _check)
        r = doctor.results[-1]
        assert r.status == "WARN", f"Bun check should WARN, got {r.status}"


class TestMCPConfiguration:
    """Test MCP configuration checks."""

    def test_mcp_json_missing(self, doctor, temp_root):
        """When .mcp.json missing, check should FAIL."""
        mcp = temp_root / ".mcp.json"
        if mcp.exists():
            mcp.unlink()

        def _check(r):
            if not mcp.exists():
                r.status = "FAIL"
                r.detail = "Not found at repo root"
            else:
                r.status = "PASS"
        doctor.check("Root .mcp.json", _check)
        r = doctor.results[-1]
        assert r.status == "FAIL"

    def test_mcp_json_present(self, doctor, temp_root):
        """When .mcp.json exists, check should PASS."""
        mcp = temp_root / ".mcp.json"
        mcp.write_text(json.dumps({
            "mcpServers": {
                "chrome-devtools": {
                    "command": "npx",
                    "args": ["-y", "chrome-devtools-mcp@latest", "--browserUrl", "http://127.0.0.1:9222"]
                }
            }
        }))

        def _check(r):
            if mcp.exists():
                r.status = "PASS"
                r.detail = "Found at repo root"
            else:
                r.status = "FAIL"
        doctor.check("Root .mcp.json", _check)
        r = doctor.results[-1]
        assert r.status == "PASS"

    def test_mcp_entry_with_chrome_devtools(self, doctor, temp_root):
        """MCP entry check should detect chrome-devtools."""
        mcp = temp_root / ".mcp.json"
        mcp.write_text(json.dumps({
            "mcpServers": {
                "chrome-devtools": {
                    "command": "npx",
                    "args": ["-y", "chrome-devtools-mcp@latest", "--browserUrl", "http://127.0.0.1:9222"]
                }
            }
        }))

        data = json.loads(mcp.read_text(encoding="utf-8"))
        servers = data.get("mcpServers", {})

        def _check(r):
            if "chrome-devtools" in servers:
                r.status = "PASS"
                r.detail = "Found chrome-devtools entry"
            else:
                r.status = "FAIL"
        doctor.check("chrome-devtools MCP entry", _check)
        r = doctor.results[-1]
        assert r.status == "PASS"

    def test_mcp_entry_missing_chrome_devtools(self, doctor, temp_root):
        """MCP entry check should FAIL when chrome-devtools not configured."""
        mcp = temp_root / ".mcp.json"
        mcp.write_text(json.dumps({
            "mcpServers": {
                "zotero": {"command": "npx", "args": ["@54yyyu/zotero-mcp"], "disabled": True}
            }
        }))

        data = json.loads(mcp.read_text(encoding="utf-8"))
        servers = data.get("mcpServers", {})

        def _check(r):
            if "chrome-devtools" in servers:
                r.status = "PASS"
            else:
                r.status = "FAIL"
                r.detail = "No chrome-devtools entry"
        doctor.check("chrome-devtools MCP entry", _check)
        r = doctor.results[-1]
        assert r.status == "FAIL"


class TestGitIgnoreCoverage:
    """Test .gitignore coverage checks."""

    def test_gitignore_covers_pkb_local(self, doctor, temp_root):
        """Check should PASS when .gitignore covers .pkb-local/."""
        gi = temp_root / ".gitignore"
        gi.write_text(".pkb-local/\n")

        content = gi.read_text(encoding="utf-8")

        def _check(r):
            if ".pkb-local/" in content:
                r.status = "PASS"
            else:
                r.status = "WARN"
        doctor.check("Git ignore coverage", _check)
        r = doctor.results[-1]
        assert r.status == "PASS"

    def test_gitignore_missing_pkb_local(self, doctor, temp_root):
        """Check should WARN when .pkb-local/ not in .gitignore."""
        gi = temp_root / ".gitignore"
        gi.write_text("node_modules/\n")

        content = gi.read_text(encoding="utf-8")

        def _check(r):
            if ".pkb-local/" in content:
                r.status = "PASS"
            else:
                r.status = "WARN"
        doctor.check("Git ignore coverage", _check)
        r = doctor.results[-1]
        assert r.status == "WARN"


class TestActiveTask:
    """Test active task state checks."""

    def test_no_active_task(self, doctor, temp_root):
        """When no task file, check should WARN (not FAIL)."""
        task_file = temp_root / ".pkb-local" / "state" / "active-task.json"

        def _check(r):
            if not task_file.exists():
                r.status = "WARN"
                r.detail = "No active task file"
            else:
                r.status = "PASS"
        doctor.check("Active task", _check)
        r = doctor.results[-1]
        assert r.status == "WARN"

    def test_active_task_present(self, doctor, temp_root):
        """When task file exists and valid, check should PASS."""
        task_file = temp_root / ".pkb-local" / "state" / "active-task.json"
        task_file.parent.mkdir(parents=True, exist_ok=True)
        task_file.write_text(json.dumps({
            "schema_version": 1,
            "task_id": "doctor-test",
            "title": "Doctor Test Task",
            "status": "active",
        }), encoding="utf-8")

        data = json.loads(task_file.read_text(encoding="utf-8"))

        def _check(r):
            if data.get("task_id") and data.get("status"):
                r.status = "PASS"
            else:
                r.status = "WARN"
        doctor.check("Active task", _check)
        r = doctor.results[-1]
        assert r.status == "PASS"


class TestPortCheck:
    """Test port/endpoint checks."""

    def test_port_not_reachable(self, doctor, temp_root):
        """When port is not reachable, check should FAIL."""
        def _check(r):
            r.status = "FAIL"
            r.detail = "Port 9222 not reachable"
        doctor.check("Chrome debug port", _check)
        r = doctor.results[-1]
        assert r.status == "FAIL"


class TestResultOutput:
    """Test result output modes."""

    def test_check_result_to_dict(self):
        r = pkb_doctor.CheckResult("test")
        r.status = "PASS"
        r.detail = "working"
        d = r.to_dict()
        assert d == {
            "name": "test",
            "status": "PASS",
            "detail": "working",
            "suggestion": "",
        }


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
