"""
Suggests a close calendar from task dependencies and estimated durations
-- a small critical-path calculation, not a scheduling algorithm that
needs its own library: each task's earliest possible start is the latest
finish of everything it depends on (or the period's start date, for tasks
with no dependencies), and its finish is start + estimated duration.

Cycles are already prevented at the point a dependency is added
(`tasks.add_dependency`), so a valid topological order always exists here.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta

from . import periods as periods_module
from . import tasks as tasks_module


def _add_business_days(start, days: int):
    """Adds `days` calendar days. Kept simple (no weekend-skipping) since
    close calendars are often measured in fixed calendar-day SLAs; a
    weekend-aware version would need a holiday calendar to be accurate
    anyway, which is out of scope here."""
    return start + timedelta(days=days)


def suggest_calendar(conn: sqlite3.Connection, close_period_id: int) -> list[dict]:
    period = periods_module.get_period(conn, close_period_id)
    period_start = datetime.strptime(period["start_date"], "%Y-%m-%d").date()

    all_tasks = tasks_module.list_tasks(conn, close_period_id)
    finish_dates: dict[int, object] = {}

    def compute_finish(task) -> object:
        if task["id"] in finish_dates:
            return finish_dates[task["id"]]

        deps = tasks_module.get_dependencies(conn, task["id"])
        if not deps:
            earliest_start = period_start
        else:
            earliest_start = max(compute_finish(d) for d in deps)

        finish = _add_business_days(earliest_start, task["estimated_duration_days"])
        finish_dates[task["id"]] = finish
        return finish

    result = []
    for t in all_tasks:
        deps = tasks_module.get_dependencies(conn, t["id"])
        start = period_start if not deps else max(compute_finish(d) for d in deps)
        finish = compute_finish(t)
        result.append(
            {
                "task_id": t["id"],
                "name": t["name"],
                "category": t["category"],
                "suggested_start": start.isoformat(),
                "suggested_finish": finish.isoformat(),
                "actual_due_date": t["due_date"],
                "behind_schedule": finish.isoformat() > t["due_date"],
            }
        )
    return sorted(result, key=lambda r: r["suggested_finish"])
