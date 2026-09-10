"""
Task CRUD, status transitions, and dependency tracking.

Dependencies are enforced, not just displayed: marking a task "done" is
blocked by default if something it depends on isn't done yet (mirrors the
brief's own example -- "JEs can't be finalized until bank rec is done").
A `force` override exists because real close processes sometimes do need
to jump the sequence under time pressure, but forcing is explicit and
never silent.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, date


@dataclass
class StatusChangeResult:
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def create_task(
    conn: sqlite3.Connection,
    close_period_id: int,
    name: str,
    category: str,
    owner: str,
    due_date: str,
    notes: str = "",
    estimated_duration_days: int = 1,
) -> int:
    cur = conn.execute(
        """INSERT INTO tasks (close_period_id, name, category, owner, due_date, notes, estimated_duration_days)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (close_period_id, name, category, owner, due_date, notes, estimated_duration_days),
    )
    return cur.lastrowid


def get_task(conn: sqlite3.Connection, task_id: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()


def list_tasks(conn: sqlite3.Connection, close_period_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM tasks WHERE close_period_id = ? ORDER BY due_date, id", (close_period_id,)
    ).fetchall()


def _direct_dependency_ids(conn: sqlite3.Connection, task_id: int) -> list[int]:
    rows = conn.execute("SELECT depends_on_task_id FROM task_dependencies WHERE task_id = ?", (task_id,)).fetchall()
    return [r["depends_on_task_id"] for r in rows]


def _direct_dependent_ids(conn: sqlite3.Connection, task_id: int) -> list[int]:
    rows = conn.execute("SELECT task_id FROM task_dependencies WHERE depends_on_task_id = ?", (task_id,)).fetchall()
    return [r["task_id"] for r in rows]


def _transitive_closure(conn: sqlite3.Connection, start_id: int, neighbor_fn) -> set[int]:
    seen: set[int] = set()
    frontier = [start_id]
    while frontier:
        current = frontier.pop()
        for neighbor in neighbor_fn(conn, current):
            if neighbor not in seen:
                seen.add(neighbor)
                frontier.append(neighbor)
    return seen


def get_dependencies(conn: sqlite3.Connection, task_id: int) -> list[sqlite3.Row]:
    """Tasks that must complete before this one can (direct only)."""
    return [get_task(conn, tid) for tid in _direct_dependency_ids(conn, task_id)]


def get_dependents(conn: sqlite3.Connection, task_id: int) -> list[sqlite3.Row]:
    """Tasks that depend directly on this one."""
    return [get_task(conn, tid) for tid in _direct_dependent_ids(conn, task_id)]


def downstream_impact(conn: sqlite3.Connection, task_id: int) -> list[sqlite3.Row]:
    """All tasks (direct or transitive) that depend on this one -- what's
    put at risk if this task is blocked or delayed."""
    ids = _transitive_closure(conn, task_id, _direct_dependent_ids)
    return [get_task(conn, tid) for tid in ids]


def add_dependency(conn: sqlite3.Connection, task_id: int, depends_on_task_id: int) -> None:
    if task_id == depends_on_task_id:
        raise ValueError("A task cannot depend on itself.")
    ancestors = _transitive_closure(conn, depends_on_task_id, _direct_dependency_ids)
    if task_id in ancestors:
        raise ValueError("That dependency would create a cycle.")
    conn.execute(
        "INSERT OR IGNORE INTO task_dependencies (task_id, depends_on_task_id) VALUES (?, ?)",
        (task_id, depends_on_task_id),
    )


def set_status(conn: sqlite3.Connection, task_id: int, new_status: str, *, force: bool = False) -> StatusChangeResult:
    result = StatusChangeResult()

    if new_status == "done" and not force:
        incomplete = [d for d in get_dependencies(conn, task_id) if d["status"] != "done"]
        if incomplete:
            names = ", ".join(f"'{d['name']}' ({d['status']})" for d in incomplete)
            result.errors.append(f"Cannot mark done -- depends on incomplete task(s): {names}")
            return result

    now = datetime.now().isoformat(timespec="seconds")
    task = get_task(conn, task_id)

    started_at = task["started_at"]
    if new_status == "in_progress" and started_at is None:
        started_at = now

    completed_at = task["completed_at"]
    if new_status == "done" and completed_at is None:
        completed_at = now

    conn.execute(
        "UPDATE tasks SET status = ?, started_at = ?, completed_at = ? WHERE id = ?",
        (new_status, started_at, completed_at, task_id),
    )
    return result


def mark_blocked(conn: sqlite3.Connection, task_id: int, reason: str) -> None:
    conn.execute("UPDATE tasks SET status = 'blocked', delay_reason = ? WHERE id = ?", (reason, task_id))


def is_overdue(task: sqlite3.Row, as_of: date | None = None) -> bool:
    as_of = as_of or date.today()
    due = datetime.strptime(task["due_date"], "%Y-%m-%d").date()
    return task["status"] != "done" and due < as_of
