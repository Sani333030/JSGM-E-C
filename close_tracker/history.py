"""
Cross-period historical tracking: how long each close actually took, and
which task category is the recurring bottleneck. This is what turns "the
bank rec was late again" from an anecdote into something backed by the
last several closes.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime

from . import periods as periods_module


def _parse_date(value: str):
    return datetime.strptime(value[:10], "%Y-%m-%d").date()


def close_duration_history(conn: sqlite3.Connection) -> list[dict]:
    result = []
    for p in periods_module.list_periods(conn):
        if p["status"] != "closed" or not p["actual_close_date"]:
            continue
        duration = (_parse_date(p["actual_close_date"]) - _parse_date(p["start_date"])).days
        result.append(
            {
                "label": p["label"],
                "start_date": p["start_date"],
                "actual_close_date": p["actual_close_date"],
                "duration_days": duration,
            }
        )
    return result


def category_lateness_report(conn: sqlite3.Connection) -> list[dict]:
    """Average (completed_at - due_date) in days, per category, across every
    completed task in every closed period. Positive = finishes late on
    average; the highest value is the recurring bottleneck."""
    rows = conn.execute(
        """SELECT t.category, t.due_date, t.completed_at
           FROM tasks t JOIN close_periods p ON p.id = t.close_period_id
           WHERE p.status = 'closed' AND t.completed_at IS NOT NULL"""
    ).fetchall()

    by_category: dict[str, list[int]] = {}
    for r in rows:
        lateness = (_parse_date(r["completed_at"]) - _parse_date(r["due_date"])).days
        by_category.setdefault(r["category"], []).append(lateness)

    report = [
        {
            "category": category,
            "task_count": len(latenesses),
            "avg_lateness_days": round(sum(latenesses) / len(latenesses), 1),
        }
        for category, latenesses in by_category.items()
    ]
    return sorted(report, key=lambda r: r["avg_lateness_days"], reverse=True)
