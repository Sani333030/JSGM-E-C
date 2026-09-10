"""Close period records -- one per month, the container everything else hangs off."""
from __future__ import annotations

import sqlite3


def create_period(conn: sqlite3.Connection, label: str, start_date: str, target_close_date: str) -> int:
    cur = conn.execute(
        "INSERT INTO close_periods (label, start_date, target_close_date) VALUES (?, ?, ?)",
        (label, start_date, target_close_date),
    )
    return cur.lastrowid


def list_periods(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM close_periods ORDER BY start_date").fetchall()


def get_period(conn: sqlite3.Connection, period_id: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM close_periods WHERE id = ?", (period_id,)).fetchone()


def close_period(conn: sqlite3.Connection, period_id: int, actual_close_date: str) -> None:
    conn.execute(
        "UPDATE close_periods SET status = 'closed', actual_close_date = ? WHERE id = ?",
        (actual_close_date, period_id),
    )


def set_at_risk(conn: sqlite3.Connection, period_id: int, reason: str) -> None:
    conn.execute("UPDATE close_periods SET at_risk = 1, at_risk_reason = ? WHERE id = ?", (reason, period_id))


def clear_at_risk(conn: sqlite3.Connection, period_id: int) -> None:
    conn.execute("UPDATE close_periods SET at_risk = 0, at_risk_reason = NULL WHERE id = ?", (period_id,))
