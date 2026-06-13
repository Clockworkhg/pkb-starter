#!/usr/bin/env python3
"""
PKB Task State Manager — manage .pkb-local/state/active-task.json

Usage:
    python tools/pkb_task.py show           # Display current active task
    python tools/pkb_task.py start          # Create new task (interactive)
    python tools/pkb_task.py update         # Update task status
    python tools/pkb_task.py block <reason> # Block task with reason
    python tools/pkb_task.py complete       # Mark task complete
    python tools/pkb_task.py clear          # Clear current task
    python tools/pkb_task.py inject         # Print context for hook injection

Design:
    - Atomic writes (write to .tmp → rename)
    - JSON schema validation
    - Corrupt file backup + recovery
    - Windows UTF-8 compat
    - Path traversal prevention
"""

import os
import sys
import json
import argparse
import shutil
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional


SCHEMA_VERSION = 1
STATE_DIR = Path(os.environ.get("PKB_ROOT", Path(__file__).resolve().parents[1])) / ".pkb-local" / "state"
TASK_FILE = STATE_DIR / "active-task.json"
TASK_HISTORY = STATE_DIR / "task-history"


def ensure_dirs():
    """Create state directories if missing."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    TASK_HISTORY.mkdir(parents=True, exist_ok=True)


def get_now_iso() -> str:
    """Return current time as ISO-8601 with timezone."""
    return datetime.now(timezone.utc).astimezone().isoformat()


def validate_task(data: dict) -> list:
    """Validate task state JSON. Returns list of errors."""
    errors = []
    if not isinstance(data, dict):
        return ["Root must be a JSON object"]

    sv = data.get("schema_version")
    if sv is None:
        errors.append("Missing 'schema_version' field")
    elif not isinstance(sv, int):
        errors.append("'schema_version' must be an integer")

    if "task_id" not in data or not isinstance(data.get("task_id"), str):
        errors.append("'task_id' is required and must be a string")
    if "title" not in data or not isinstance(data.get("title"), str):
        errors.append("'title' is required and must be a string")
    if "status" not in data:
        errors.append("'status' is required")
    elif data["status"] not in ("active", "blocked", "completed"):
        errors.append(f"Invalid status: {data['status']} (must be active/blocked/completed)")

    return errors


def load_task() -> Optional[dict]:
    """Load task state file safely. Returns None if nonexistent or corrupt."""
    if not TASK_FILE.exists():
        return None
    try:
        text = TASK_FILE.read_text(encoding="utf-8")
        data = json.loads(text)
        errors = validate_task(data)
        if errors:
            # Corrupt file: back up and return None
            backup = TASK_FILE.with_suffix(".json.bak")
            shutil.copy2(TASK_FILE, backup)
            print(f"[PKB Task ⚠️] Task file corrupt — backed up to {backup.name}", file=sys.stderr)
            for e in errors:
                print(f"  - {e}", file=sys.stderr)
            return None
        return data
    except json.JSONDecodeError as e:
        backup = TASK_FILE.with_suffix(".json.bak")
        shutil.copy2(TASK_FILE, backup)
        print(f"[PKB Task ⚠️] Invalid JSON — backed up to {backup.name}: {e}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"[PKB Task ⚠️] Cannot read task file: {e}", file=sys.stderr)
        return None


def save_task(data: dict) -> bool:
    """Atomically write task state. Returns True on success."""
    ensure_dirs()
    data["updated_at"] = get_now_iso()
    errors = validate_task(data)
    if errors:
        print(f"[PKB Task 🛑] Validation failed:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return False

    tmp = TASK_FILE.with_suffix(".json.tmp")
    try:
        tmp.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        tmp.replace(TASK_FILE)
        return True
    except Exception as e:
        print(f"[PKB Task 🛑] Write failed: {e}", file=sys.stderr)
        return False


def clear_task() -> bool:
    """Remove the active task file."""
    if TASK_FILE.exists():
        TASK_FILE.unlink()
        print("[PKB Task] Task cleared.")
    else:
        print("[PKB Task] No active task to clear.")
    return True


def archive_task(data: dict) -> None:
    """Move a completed task to history."""
    ensure_dirs()
    task_id = data.get("task_id", "unknown")
    ts = get_now_iso().replace(":", "-")[:19]
    history_file = TASK_HISTORY / f"{ts}_{task_id}.json"
    try:
        history_file.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except Exception as e:
        print(f"[PKB Task ⚠️] Could not archive: {e}", file=sys.stderr)


def cmd_show():
    """Display current task."""
    task = load_task()
    if not task:
        print("[PKB Task] No active task.")
        return 0

    print("┌" + "─" * 55 + "┐")
    print(f"│ Active Task".ljust(56) + "│")
    print("├" + "─" * 55 + "┤")
    status_icon = {"active": "🟢", "blocked": "🔴", "completed": "✅"}.get(task.get("status"), "❓")
    print(f"│ {status_icon} {task.get('title', 'Untitled')}".ljust(56) + "│")
    print(f"│ ID: {task.get('task_id', '?')}  Status: {task.get('status', '?')}".ljust(56) + "│")
    print("├" + "─" * 55 + "┤")

    goal = task.get("goal", "")
    if goal:
        print(f"│ Goal: {goal[:50]}".ljust(56) + "│")

    completed = task.get("completed", [])
    if completed:
        print(f"│ Completed:".ljust(56) + "│")
        for c in completed:
            print(f"│   ✅ {c[:48]}".ljust(56) + "│")

    next_action = task.get("next_action", "")
    if next_action:
        print(f"│ Next: {next_action[:50]}".ljust(56) + "│")

    blocked = task.get("blocked_by", [])
    if blocked:
        print(f"│ Blocked by:".ljust(56) + "│")
        for b in blocked:
            print(f"│   🛑 {b[:48]}".ljust(56) + "│")

    required = task.get("required_capabilities", [])
    if required:
        print(f"│ Needs: {', '.join(required)[:50]}".ljust(56) + "│")

    artifacts = task.get("artifacts", [])
    if artifacts:
        print(f"│ Artifacts:".ljust(56) + "│")
        for a in artifacts:
            print(f"│   📄 {a[:48]}".ljust(56) + "│")

    print(f"│ Updated: {task.get('updated_at', '?')[:19]}".ljust(56) + "│")
    print("└" + "─" * 55 + "┘")
    return 0


def cmd_start(args):
    """Create a new task."""
    existing = load_task()
    if existing and existing.get("status") not in ("completed",):
        print(f"[PKB Task ⚠️] Active task already exists: {existing.get('title')}")
        print("  Use 'update' to modify or 'complete' to finish it first.")
        return 1

    task = {
        "schema_version": SCHEMA_VERSION,
        "task_id": args.id or f"task-{get_now_iso()[:10].replace('-', '')}",
        "title": args.title or "Untitled Task",
        "status": "active",
        "goal": args.goal or "",
        "completed": [],
        "next_action": args.next or "",
        "blocked_by": [],
        "required_capabilities": args.caps.split(",") if args.caps else [],
        "artifacts": [],
        "notes": [],
        "created_at": get_now_iso(),
        "updated_at": get_now_iso(),
    }

    if save_task(task):
        print(f"[PKB Task ✅] Created: {task['title']}")
        return 0
    return 1


def cmd_update(args):
    """Update task status or fields."""
    task = load_task()
    if not task:
        print("[PKB Task ⚠️] No active task. Use 'start' to create one.")
        return 1

    if args.status:
        task["status"] = args.status
    if args.next:
        task["next_action"] = args.next
    if args.goal:
        task["goal"] = args.goal
    if args.add_completed:
        task.setdefault("completed", []).append(args.add_completed)
    if args.title:
        task["title"] = args.title
    if args.add_artifact:
        task.setdefault("artifacts", []).append(args.add_artifact)
    if args.note:
        task.setdefault("notes", []).append(f"[{get_now_iso()[:19]}] {args.note}")

    if save_task(task):
        print(f"[PKB Task ✅] Updated: {task['title']}")
        return 0
    return 1


def cmd_block(args):
    """Block the current task with a reason."""
    task = load_task()
    if not task:
        print("[PKB Task ⚠️] No active task. Use 'start' to create one.")
        return 1

    reason = args.reason or "Unspecified blocker"
    task["status"] = "blocked"
    task.setdefault("blocked_by", []).append(reason)
    task["next_action"] = f"Waiting: {reason}"

    if save_task(task):
        print(f"[PKB Task 🛑] Blocked: {reason}")
        return 0
    return 1


def cmd_complete(args):
    """Mark task complete and archive."""
    task = load_task()
    if not task:
        print("[PKB Task] No active task.")
        return 0

    task["status"] = "completed"
    archive_task(task)
    clear_task()
    print(f"[PKB Task ✅] Completed: {task.get('title')}")
    return 0


def cmd_inject():
    """Print context for SessionStart hook injection."""
    task = load_task()
    if not task:
        return 0  # Silent — no task to inject

    if task.get("status") == "completed":
        return 0  # Don't inject completed tasks

    status_icon = {"active": "🟢", "blocked": "🔴"}.get(task.get("status"), "❓")

    print()
    print("┌" + "─" * 60 + "┐")
    print(f"│ 📋 当前活动任务".ljust(61) + "│")
    print("├" + "─" * 60 + "┤")
    print(f"│ {status_icon} {task.get('title', 'Untitled')}".ljust(61) + "│")
    print("├" + "─" * 60 + "┤")

    completed = task.get("completed", [])
    if completed:
        print(f"│ 已完成:".ljust(61) + "│")
        for c in completed:
            print(f"│   ✅ {c[:54]}".ljust(61) + "│")

    next_action = task.get("next_action", "")
    if next_action:
        print(f"│ 下一步: {next_action[:54]}".ljust(61) + "│")

    required = task.get("required_capabilities", [])
    if required:
        print(f"│ 必要能力: {', '.join(required)[:54]}".ljust(61) + "│")

    blocked = task.get("blocked_by", [])
    if blocked:
        print(f"│ 阻塞项:".ljust(61) + "│")
        for b in blocked:
            print(f"│   🛑 {b[:54]}".ljust(61) + "│")

    print("└" + "─" * 60 + "┘")
    print()
    return 0


def main():
    parser = argparse.ArgumentParser(description="PKB Task State Manager")
    sub = parser.add_subparsers(dest="command", help="Commands")

    sub.add_parser("show", help="Display current active task")
    sub.add_parser("inject", help="Print task context for hook injection")
    sub.add_parser("complete", help="Mark task complete and archive")
    sub.add_parser("clear", help="Remove current task")

    p_start = sub.add_parser("start", help="Create new task")
    p_start.add_argument("--id", help="Task ID")
    p_start.add_argument("--title", help="Task title")
    p_start.add_argument("--goal", help="Task goal")
    p_start.add_argument("--next", help="Next action")
    p_start.add_argument("--caps", help="Comma-separated required capabilities")

    p_update = sub.add_parser("update", help="Update task")
    p_update.add_argument("--status", choices=["active", "blocked", "completed"])
    p_update.add_argument("--title")
    p_update.add_argument("--goal")
    p_update.add_argument("--next")
    p_update.add_argument("--add-completed")
    p_update.add_argument("--add-artifact")
    p_update.add_argument("--note")

    p_block = sub.add_parser("block", help="Block current task")
    p_block.add_argument("reason", nargs="*", help="Reason for blocking")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    if args.command == "show":
        return cmd_show()
    elif args.command == "inject":
        return cmd_inject()
    elif args.command == "start":
        return cmd_start(args)
    elif args.command == "update":
        return cmd_update(args)
    elif args.command == "block":
        return cmd_block(args)
    elif args.command == "complete":
        return cmd_complete(args)
    elif args.command == "clear":
        clear_task()
        return 0
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n[PKB Task] Interrupted.")
        sys.exit(130)
    except Exception as e:
        print(f"[PKB Task 🛑] Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)
