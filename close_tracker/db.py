"""SQLite schema and connection helper -- same pattern as the journal
entry tool: stdlib sqlite3, no ORM, schema simple enough to read directly."""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager

CATEGORIES = ["Pre-close", "Reconciliations", "Journal Entries", "Review & Reporting", "Close-out"]
STATUSES = ["not_started", "in_progress", "done", "blocked"]

SCHEMA = """
CREATE TABLE IF NOT EXISTS close_periods (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    label TEXT NOT NULL UNIQUE,
    start_date TEXT NOT NULL,
    target_close_date TEXT NOT NULL,
    actual_close_date TEXT,
    status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'closed')),
    at_risk INTEGER NOT NULL DEFAULT 0,
    at_risk_reason TEXT
);

CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    close_period_id INTEGER NOT NULL REFERENCES close_periods(id),
    name TEXT NOT NULL,
    category TEXT NOT NULL CHECK (category IN
        ('Pre-close', 'Reconciliations', 'Journal Entries', 'Review & Reporting', 'Close-out')),
    owner TEXT NOT NULL,
    due_date TEXT NOT NULL,
    estimated_duration_days INTEGER NOT NULL DEFAULT 1,
    status TEXT NOT NULL DEFAULT 'not_started' CHECK (status IN ('not_started', 'in_progress', 'done', 'blocked')),
    notes TEXT,
    delay_reason TEXT,
    started_at TEXT,
    completed_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS task_dependencies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER NOT NULL REFERENCES tasks(id),
    depends_on_task_id INTEGER NOT NULL REFERENCES tasks(id),
    UNIQUE (task_id, depends_on_task_id)
);

CREATE TABLE IF NOT EXISTS notifications_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER NOT NULL REFERENCES tasks(id),
    message TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


def connect(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(path: str) -> None:
    conn = connect(path)
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()


@contextmanager
def session(path: str):
    conn = connect(path)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()
