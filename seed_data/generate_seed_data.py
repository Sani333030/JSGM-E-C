"""
Builds a demo database: one realistic 21-task month-end close checklist
for a fictional small-to-mid-size company, applied to three periods --
two prior closed months (for historical/bottleneck trend data) and the
current, still-open period with two deliberately blocked tasks and their
downstream ripple effects.

Bank reconciliation tasks are seeded to consistently finish a day or two
late across all three periods -- a deliberate, repeated pattern so
`history.category_lateness_report` has something real to surface, echoing
the brief's own example ("bank rec is consistently the last task done --
investigate why").

All company/people names are fictional.
"""
from __future__ import annotations

import os
import sys
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from close_tracker import db, notifications, periods, tasks

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "demo.db")

# (name, category, owner, day_offset_due, duration_days, depends_on_indices)
TASK_SPEC = [
    ("Send cutoff communication to department heads", "Pre-close", "Morgan Ellis (Controller)", 1, 1, []),
    ("Lock AP sub-ledger", "Pre-close", "Priya Raman (AP Clerk)", 2, 1, [0]),
    ("Lock AR sub-ledger", "Pre-close", "Diego Alvarez (AR Clerk)", 2, 1, [0]),
    ("Bank reconciliation - operating account", "Reconciliations", "Sam Okafor (Staff Accountant)", 5, 2, [1, 2]),
    ("Bank reconciliation - payroll account", "Reconciliations", "Sam Okafor (Staff Accountant)", 5, 2, [1]),
    ("Credit card reconciliation", "Reconciliations", "Priya Raman (AP Clerk)", 4, 1, [1]),
    ("Intercompany reconciliation", "Reconciliations", "Sam Okafor (Staff Accountant)", 6, 1, [3]),
    ("Petty cash reconciliation", "Reconciliations", "Taylor Brooks (Office Manager)", 4, 1, []),
    ("Record accruals", "Journal Entries", "Sam Okafor (Staff Accountant)", 7, 1, [3, 5]),
    ("Prepaid amortization entries", "Journal Entries", "Sam Okafor (Staff Accountant)", 7, 1, [1]),
    ("Depreciation entries", "Journal Entries", "Sam Okafor (Staff Accountant)", 7, 1, [1]),
    ("Revenue recognition adjustments", "Journal Entries", "Jordan Kim (Revenue Accountant)", 8, 1, [2]),
    ("Payroll accrual entry", "Journal Entries", "Sam Okafor (Staff Accountant)", 7, 1, [4]),
    ("Intercompany elimination entries", "Journal Entries", "Sam Okafor (Staff Accountant)", 8, 1, [6]),
    ("Trial balance review", "Review & Reporting", "Morgan Ellis (Controller)", 9, 1, [8, 9, 10, 11, 12, 13]),
    ("Variance analysis vs. prior month/budget", "Review & Reporting", "Casey Nolan (FP&A Analyst)", 10, 1, [14]),
    ("Flux commentary write-up", "Review & Reporting", "Casey Nolan (FP&A Analyst)", 11, 1, [15]),
    ("Financial statement draft", "Review & Reporting", "Morgan Ellis (Controller)", 11, 1, [14]),
    ("Management review meeting", "Review & Reporting", "Alex Whitfield (CFO)", 12, 1, [16, 17]),
    ("Period lock in ERP", "Close-out", "Morgan Ellis (Controller)", 13, 1, [18]),
    ("Final sign-off / distribute financials", "Close-out", "Alex Whitfield (CFO)", 13, 1, [19]),
]

RECONCILIATION_INDICES = {3, 4, 6, 7}  # tasks that consistently run a bit late


def _build_period_tasks(conn, period_id: int, start_date: date, lateness_days: dict[int, int]) -> list[int]:
    """Creates all tasks + dependencies for a period. `lateness_days` maps
    task index -> extra days added to its due date when computing
    completed_at (0 = finished on time). Returns the list of created task ids
    in TASK_SPEC order."""
    task_ids = []
    for name, category, owner, offset, duration, _ in TASK_SPEC:
        due = start_date + timedelta(days=offset)
        tid = tasks.create_task(conn, period_id, name, category, owner, due.isoformat(), estimated_duration_days=duration)
        task_ids.append(tid)

    for idx, (_, _, _, _, _, dep_indices) in enumerate(TASK_SPEC):
        for dep_idx in dep_indices:
            tasks.add_dependency(conn, task_ids[idx], task_ids[dep_idx])

    return task_ids


def build_closed_period(conn, label: str, start_date: date) -> int:
    target_close = start_date + timedelta(days=15)
    period_id = periods.create_period(conn, label, start_date.isoformat(), target_close.isoformat())

    lateness = {idx: (2 if idx in (3, 6) else 1) for idx in RECONCILIATION_INDICES}
    task_ids = _build_period_tasks(conn, period_id, start_date, lateness)

    last_completion = start_date
    for idx, (name, category, owner, offset, duration, _) in enumerate(TASK_SPEC):
        due = start_date + timedelta(days=offset)
        completed = due + timedelta(days=lateness.get(idx, 0))
        conn.execute(
            "UPDATE tasks SET status = 'done', started_at = ?, completed_at = ? WHERE id = ?",
            (due.isoformat(), completed.isoformat() + "T16:00:00", task_ids[idx]),
        )
        last_completion = max(last_completion, completed)

    periods.close_period(conn, period_id, last_completion.isoformat())
    return period_id


def build_current_period(conn, label: str, start_date: date) -> int:
    target_close = start_date + timedelta(days=15)
    period_id = periods.create_period(conn, label, start_date.isoformat(), target_close.isoformat())
    task_ids = _build_period_tasks(conn, period_id, start_date, {})

    # Everything due before "today" (day 1-6) is done, with the usual
    # reconciliation lateness pattern -- except the two deliberately
    # blocked tasks, which are stuck and now also overdue.
    done_indices = [0, 1, 2, 3, 4, 5, 7]  # NOT 6 (intercompany recon) -- blocked below
    for idx in done_indices:
        _, _, _, offset, _, _ = TASK_SPEC[idx]
        due = start_date + timedelta(days=offset)
        lateness = 2 if idx == 3 else (1 if idx == 6 else 0)
        completed = due + timedelta(days=lateness)
        conn.execute(
            "UPDATE tasks SET status = 'done', started_at = ?, completed_at = ? WHERE id = ?",
            (due.isoformat(), completed.isoformat() + "T16:00:00", task_ids[idx]),
        )

    tasks.mark_blocked(
        conn, task_ids[6],
        "Waiting on the subsidiary's trial balance export from their local bookkeeper; requested twice, still not received.",
    )
    tasks.mark_blocked(
        conn, task_ids[11],
        "Revenue Accountant (Jordan Kim) is out on unplanned medical leave; reassigning to a backup preparer.",
    )
    periods.set_at_risk(
        conn, period_id,
        "Two blocked tasks (intercompany reconciliation, revenue recognition) are holding up trial balance review and everything downstream of it.",
    )

    # A couple of in-flight tasks with no blockers, to show a realistic mixed board.
    conn.execute("UPDATE tasks SET status = 'in_progress', started_at = ? WHERE id = ?",
                 (start_date.isoformat(), task_ids[9]))  # prepaid amortization
    conn.execute("UPDATE tasks SET status = 'in_progress', started_at = ? WHERE id = ?",
                 (start_date.isoformat(), task_ids[10]))  # depreciation

    notifications.notify_overdue_tasks(conn, period_id)
    return period_id


def main():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    db.init_db(DB_PATH)

    with db.session(DB_PATH) as conn:
        build_closed_period(conn, "July 2026 Close", date(2026, 7, 1))
        build_closed_period(conn, "August 2026 Close", date(2026, 8, 1))
        current_id = build_current_period(conn, "September 2026 Close", date(2026, 9, 1))

    print(f"Seeded database at {DB_PATH}")
    print(f"  Current open period id: {current_id} (September 2026 Close)")


if __name__ == "__main__":
    main()
