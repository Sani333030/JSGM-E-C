import pytest
from datetime import date

from close_tracker import dashboard, db, periods, tasks


@pytest.fixture
def period(tmp_path):
    db_path = str(tmp_path / "test.db")
    db.init_db(db_path)
    with db.session(db_path) as conn:
        period_id = periods.create_period(conn, "Test Month", "2026-01-01", "2026-01-15")
    return db_path, period_id


def test_percent_complete(period):
    db_path, period_id = period
    with db.session(db_path) as conn:
        a = tasks.create_task(conn, period_id, "A", "Pre-close", "Sam", "2026-01-02")
        tasks.create_task(conn, period_id, "B", "Pre-close", "Sam", "2026-01-03")
        tasks.set_status(conn, a, "done")
        pct = dashboard.percent_complete(conn, period_id)
    assert pct == 50.0


def test_status_breakdown(period):
    db_path, period_id = period
    with db.session(db_path) as conn:
        a = tasks.create_task(conn, period_id, "A", "Pre-close", "Sam", "2026-01-02")
        tasks.create_task(conn, period_id, "B", "Pre-close", "Sam", "2026-01-03")
        tasks.set_status(conn, a, "in_progress")
        breakdown = dashboard.status_breakdown(conn, period_id)
    assert breakdown == {"not_started": 1, "in_progress": 1, "done": 0, "blocked": 0}


def test_overdue_tasks_uses_as_of_date(period):
    db_path, period_id = period
    with db.session(db_path) as conn:
        tasks.create_task(conn, period_id, "A", "Pre-close", "Sam", "2026-01-02")
        overdue_before = dashboard.overdue_tasks(conn, period_id, as_of=date(2026, 1, 1))
        overdue_after = dashboard.overdue_tasks(conn, period_id, as_of=date(2026, 1, 10))
    assert overdue_before == []
    assert len(overdue_after) == 1


def test_at_risk_view_surfaces_downstream_tasks(period):
    db_path, period_id = period
    with db.session(db_path) as conn:
        a = tasks.create_task(conn, period_id, "Bank rec", "Reconciliations", "Sam", "2026-01-05")
        b = tasks.create_task(conn, period_id, "Accruals", "Journal Entries", "Sam", "2026-01-07")
        tasks.add_dependency(conn, b, a)
        tasks.mark_blocked(conn, a, "Waiting on statement from bank")

        at_risk = dashboard.at_risk_view(conn, period_id)

    assert len(at_risk) == 1
    assert at_risk[0]["reason"] == "Waiting on statement from bank"
    assert [d["name"] for d in at_risk[0]["downstream_at_risk"]] == ["Accruals"]


def test_at_risk_view_excludes_downstream_tasks_already_done(period):
    db_path, period_id = period
    with db.session(db_path) as conn:
        a = tasks.create_task(conn, period_id, "Bank rec", "Reconciliations", "Sam", "2026-01-05")
        b = tasks.create_task(conn, period_id, "Accruals", "Journal Entries", "Sam", "2026-01-07")
        tasks.add_dependency(conn, b, a)
        tasks.set_status(conn, b, "done", force=True)
        tasks.mark_blocked(conn, a, "Late statement")

        at_risk = dashboard.at_risk_view(conn, period_id)

    assert at_risk[0]["downstream_at_risk"] == []
