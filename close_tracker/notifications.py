"""Simulated notifications: logs what *would* be sent and to whom,
without actually sending email/Slack/etc. Good enough to demonstrate the
close process reacting to overdue items; wiring up a real notification
channel is an integration detail specific to whatever the firm already
uses, not something to fake convincingly here."""
from __future__ import annotations

import sqlite3

from . import dashboard as dashboard_module


def log_notification(conn: sqlite3.Connection, task_id: int, message: str) -> None:
    conn.execute("INSERT INTO notifications_log (task_id, message) VALUES (?, ?)", (task_id, message))


def notify_overdue_tasks(conn: sqlite3.Connection, close_period_id: int) -> list[str]:
    messages = []
    for task in dashboard_module.overdue_tasks(conn, close_period_id):
        message = f"Would notify {task['owner']}: '{task['name']}' is overdue (was due {task['due_date']})."
        log_notification(conn, task["id"], message)
        messages.append(message)
    return messages


def get_log(conn: sqlite3.Connection, task_id: int | None = None) -> list[sqlite3.Row]:
    if task_id is not None:
        return conn.execute(
            "SELECT * FROM notifications_log WHERE task_id = ? ORDER BY created_at", (task_id,)
        ).fetchall()
    return conn.execute("SELECT * FROM notifications_log ORDER BY created_at").fetchall()
