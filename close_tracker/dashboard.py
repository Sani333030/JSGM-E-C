"""Single-period status views: percent complete, overdue, category
breakdown, and the at-risk view that ties blocked tasks to whatever
downstream tasks depend on them."""
from __future__ import annotations

import sqlite3
from datetime import date

from . import tasks as tasks_module


def percent_complete(conn: sqlite3.Connection, close_period_id: int) -> float:
    rows = tasks_module.list_tasks(conn, close_period_id)
    if not rows:
        return 0.0
    done = sum(1 for t in rows if t["status"] == "done")
    return round(100 * done / len(rows), 1)


def status_breakdown(conn: sqlite3.Connection, close_period_id: int) -> dict[str, int]:
    rows = tasks_module.list_tasks(conn, close_period_id)
    counts = {"not_started": 0, "in_progress": 0, "done": 0, "blocked": 0}
    for t in rows:
        counts[t["status"]] += 1
    return counts


def category_breakdown(conn: sqlite3.Connection, close_period_id: int) -> list[dict]:
    rows = tasks_module.list_tasks(conn, close_period_id)
    by_category: dict[str, list] = {}
    for t in rows:
        by_category.setdefault(t["category"], []).append(t)

    result = []
    for category, task_list in by_category.items():
        done = sum(1 for t in task_list if t["status"] == "done")
        result.append(
            {
                "category": category,
                "total": len(task_list),
                "done": done,
                "percent_complete": round(100 * done / len(task_list), 1) if task_list else 0.0,
            }
        )
    return result


def overdue_tasks(conn: sqlite3.Connection, close_period_id: int, as_of: date | None = None) -> list[sqlite3.Row]:
    rows = tasks_module.list_tasks(conn, close_period_id)
    return [t for t in rows if tasks_module.is_overdue(t, as_of)]


def at_risk_view(conn: sqlite3.Connection, close_period_id: int) -> list[dict]:
    """Blocked tasks, plus every downstream task put at risk by each one --
    the direct answer to "how does this disruption ripple downstream"."""
    rows = tasks_module.list_tasks(conn, close_period_id)
    blocked = [t for t in rows if t["status"] == "blocked"]

    result = []
    for b in blocked:
        downstream = [d for d in tasks_module.downstream_impact(conn, b["id"]) if d["status"] != "done"]
        result.append(
            {
                "task": b,
                "reason": b["delay_reason"] or "(no reason given)",
                "downstream_at_risk": downstream,
            }
        )
    return result
