#!/usr/bin/env python3
"""
Tests for PKB Task State Manager (tools/pkb_task.py).

Coverage:
    - Create, read, update, block, complete, clear
    - JSON corruption recovery
    - Schema validation
    - Atomic writes (via .tmp rename)
    - Unicode support
    - Nonexistent path safety
"""

import json
import os
import sys
import tempfile
import shutil
from pathlib import Path
from datetime import datetime
import pytest

# Add tools dir to path
TOOLS_DIR = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS_DIR))

import pkb_task


@pytest.fixture
def temp_state_dir():
    """Create a temporary state directory for task tests."""
    d = Path(tempfile.mkdtemp(prefix="pkb_test_task_"))
    state_dir = d / ".pkb-local" / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    # Override global paths
    old_state = pkb_task.STATE_DIR
    old_task_file = pkb_task.TASK_FILE
    pkb_task.STATE_DIR = state_dir
    pkb_task.TASK_FILE = state_dir / "active-task.json"
    pkb_task.TASK_HISTORY = state_dir / "task-history"
    yield d
    # Restore
    pkb_task.STATE_DIR = old_state
    pkb_task.TASK_FILE = old_task_file
    pkb_task.TASK_HISTORY = old_state / "task-history"
    shutil.rmtree(d, ignore_errors=True)


class TestTaskCreate:
    """Test task creation."""

    def test_create_basic(self, temp_state_dir):
        """Create a basic task successfully."""
        data = {
            "schema_version": 1,
            "task_id": "test-001",
            "title": "Test Task",
            "status": "active",
            "goal": "Run tests",
            "completed": [],
            "next_action": "",
            "blocked_by": [],
            "required_capabilities": [],
            "artifacts": [],
            "notes": [],
            "created_at": pkb_task.get_now_iso(),
            "updated_at": pkb_task.get_now_iso(),
        }
        assert pkb_task.save_task(data)
        loaded = pkb_task.load_task()
        assert loaded is not None
        assert loaded["task_id"] == "test-001"
        assert loaded["title"] == "Test Task"
        assert loaded["status"] == "active"

    def test_create_unicode(self, temp_state_dir):
        """Task with Unicode content (Chinese characters)."""
        data = {
            "schema_version": 1,
            "task_id": "test-cn",
            "title": "政治传播学知网文献检索",
            "status": "active",
            "goal": "检索、筛选并下载政治传播学中文核心文献",
            "completed": ["完成英文文献初步检索", "生成中文文献初步清单"],
            "next_action": "连接 Chrome DevTools MCP",
            "blocked_by": [],
            "required_capabilities": ["chrome-devtools"],
            "artifacts": ["wiki/sources/lit-political-communication.md"],
            "notes": [],
            "created_at": pkb_task.get_now_iso(),
            "updated_at": pkb_task.get_now_iso(),
        }
        assert pkb_task.save_task(data)
        loaded = pkb_task.load_task()
        assert loaded["title"] == "政治传播学知网文献检索"
        assert "中文文献" in loaded["completed"][1]


class TestTaskRead:
    """Test task reading."""

    def test_load_nonexistent(self, temp_state_dir):
        """Loading nonexistent task returns None."""
        assert pkb_task.load_task() is None

    def test_load_valid(self, temp_state_dir):
        """Load a valid task file."""
        data = {
            "schema_version": 1,
            "task_id": "load-test",
            "title": "Load Test",
            "status": "active",
            "goal": "",
            "completed": [],
            "next_action": "",
            "blocked_by": [],
            "required_capabilities": [],
            "artifacts": [],
            "notes": [],
            "created_at": pkb_task.get_now_iso(),
            "updated_at": pkb_task.get_now_iso(),
        }
        pkb_task.save_task(data)
        loaded = pkb_task.load_task()
        assert loaded["task_id"] == "load-test"


class TestTaskUpdate:
    """Test task updates."""

    def test_update_status(self, temp_state_dir):
        """Update task status."""
        data = {
            "schema_version": 1,
            "task_id": "update-test",
            "title": "Update Test",
            "status": "active",
            "goal": "",
            "completed": [],
            "next_action": "",
            "blocked_by": [],
            "required_capabilities": [],
            "artifacts": [],
            "notes": [],
            "created_at": pkb_task.get_now_iso(),
            "updated_at": pkb_task.get_now_iso(),
        }
        pkb_task.save_task(data)

        # Update
        data["status"] = "blocked"
        data["blocked_by"] = ["MCP unavailable"]
        pkb_task.save_task(data)

        loaded = pkb_task.load_task()
        assert loaded["status"] == "blocked"
        assert "MCP unavailable" in loaded["blocked_by"]

    def test_update_completed_list(self, temp_state_dir):
        """Add items to completed list."""
        data = {
            "schema_version": 1,
            "task_id": "complete-list",
            "title": "Complete List",
            "status": "active",
            "goal": "",
            "completed": [],
            "next_action": "",
            "blocked_by": [],
            "required_capabilities": [],
            "artifacts": [],
            "notes": [],
            "created_at": pkb_task.get_now_iso(),
            "updated_at": pkb_task.get_now_iso(),
        }
        pkb_task.save_task(data)

        data["completed"].append("Step 1 done")
        pkb_task.save_task(data)
        data["completed"].append("Step 2 done")
        pkb_task.save_task(data)

        loaded = pkb_task.load_task()
        assert len(loaded["completed"]) == 2


class TestTaskBlock:
    """Test task blocking."""

    def test_block_with_reason(self, temp_state_dir):
        """Block a task with a specific reason."""
        data = {
            "schema_version": 1,
            "task_id": "block-test",
            "title": "Block Test",
            "status": "active",
            "goal": "",
            "completed": [],
            "next_action": "",
            "blocked_by": [],
            "required_capabilities": [],
            "artifacts": [],
            "notes": [],
            "created_at": pkb_task.get_now_iso(),
            "updated_at": pkb_task.get_now_iso(),
        }
        pkb_task.save_task(data)

        data["status"] = "blocked"
        data["blocked_by"].append("chrome-devtools MCP unavailable")
        pkb_task.save_task(data)

        loaded = pkb_task.load_task()
        assert loaded["status"] == "blocked"


class TestTaskComplete:
    """Test task completion."""

    def test_complete_archives(self, temp_state_dir):
        """Completing a task moves it to history."""
        data = {
            "schema_version": 1,
            "task_id": "archive-test",
            "title": "Archive Test",
            "status": "active",
            "goal": "",
            "completed": [],
            "next_action": "",
            "blocked_by": [],
            "required_capabilities": [],
            "artifacts": [],
            "notes": [],
            "created_at": pkb_task.get_now_iso(),
            "updated_at": pkb_task.get_now_iso(),
        }
        pkb_task.save_task(data)

        # Archive and clear
        pkb_task.archive_task(data)
        pkb_task.clear_task()

        assert not pkb_task.TASK_FILE.exists()
        # Should have history
        history_files = list(pkb_task.TASK_HISTORY.glob("*.json"))
        assert len(history_files) == 1


class TestTaskClear:
    """Test task clearing."""

    def test_clear_removes_file(self, temp_state_dir):
        """Clear removes the active task file."""
        data = {
            "schema_version": 1,
            "task_id": "clear-test",
            "title": "Clear Test",
            "status": "active",
            "goal": "",
            "completed": [],
            "next_action": "",
            "blocked_by": [],
            "required_capabilities": [],
            "artifacts": [],
            "notes": [],
            "created_at": pkb_task.get_now_iso(),
            "updated_at": pkb_task.get_now_iso(),
        }
        pkb_task.save_task(data)
        assert pkb_task.TASK_FILE.exists()

        pkb_task.clear_task()
        assert not pkb_task.TASK_FILE.exists()


class TestValidation:
    """Test schema validation."""

    def test_invalid_status(self, temp_state_dir):
        """Reject tasks with invalid status."""
        data = {
            "schema_version": 1,
            "task_id": "bad-status",
            "title": "Bad Status",
            "status": "invalid-status-xyz",
            "goal": "",
            "completed": [],
            "next_action": "",
            "blocked_by": [],
            "required_capabilities": [],
            "artifacts": [],
            "notes": [],
            "created_at": pkb_task.get_now_iso(),
            "updated_at": pkb_task.get_now_iso(),
        }
        errors = pkb_task.validate_task(data)
        assert len(errors) >= 1
        assert any("status" in e.lower() for e in errors)

    def test_missing_task_id(self, temp_state_dir):
        """Reject tasks without task_id."""
        data = {
            "schema_version": 1,
            "title": "No ID",
            "status": "active",
        }
        errors = pkb_task.validate_task(data)
        assert any("task_id" in e.lower() for e in errors)

    def test_missing_schema_version(self, temp_state_dir):
        """Flag missing schema_version."""
        data = {
            "task_id": "no-sv",
            "title": "No SV",
            "status": "active",
        }
        errors = pkb_task.validate_task(data)
        assert any("schema_version" in e.lower() for e in errors)


class TestCorruption:
    """Test handling of corrupt files."""

    def test_corrupt_json_backed_up(self, temp_state_dir):
        """Corrupt JSON should be backed up."""
        pkb_task.TASK_FILE.write_text("this is not json{", encoding="utf-8")
        result = pkb_task.load_task()
        assert result is None
        # Backup should exist
        bak = pkb_task.TASK_FILE.with_suffix(".json.bak")
        assert bak.exists()


class TestAtomicWrite:
    """Test atomic write behavior."""

    def test_tmp_file_cleaned(self, temp_state_dir):
        """Temporary file should be renamed, not left behind."""
        data = {
            "schema_version": 1,
            "task_id": "atomic-test",
            "title": "Atomic Test",
            "status": "active",
            "goal": "",
            "completed": [],
            "next_action": "",
            "blocked_by": [],
            "required_capabilities": [],
            "artifacts": [],
            "notes": [],
            "created_at": pkb_task.get_now_iso(),
            "updated_at": pkb_task.get_now_iso(),
        }
        pkb_task.save_task(data)
        tmp = pkb_task.TASK_FILE.with_suffix(".json.tmp")
        assert not tmp.exists()
        assert pkb_task.TASK_FILE.exists()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
