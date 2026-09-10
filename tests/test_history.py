import pytest

from close_tracker import db, history, periods, tasks


@pytest.fixture
def db_path(tmp_path):
    path = str(tmp_path / "test.db")
    db.init_db(path)
    return path


def test_close_duration_history_only_includes_closed_periods(db_path):
    with db.session(db_path) as conn:
        open_id = periods.create_period(conn, "Open Month", "2026-02-01", "2026-02-15")
        closed_id = periods.create_period(conn, "Closed Month", "2026-01-01", "2026-01-15")
        periods.close_period(conn, closed_id, "2026-01-14")

        result = history.close_duration_history(conn)

    assert len(result) == 1
    assert result[0]["label"] == "Closed Month"
    assert result[0]["duration_days"] == 13


def test_category_lateness_report_averages_per_category(db_path):
    with db.session(db_path) as conn:
        period_id = periods.create_period(conn, "Month", "2026-01-01", "2026-01-15")
        t1 = tasks.create_task(conn, period_id, "Bank rec", "Reconciliations", "Sam", "2026-01-05")
        t2 = tasks.create_task(conn, period_id, "Credit card rec", "Reconciliations", "Sam", "2026-01-05")
        t3 = tasks.create_task(conn, period_id, "Accrual", "Journal Entries", "Sam", "2026-01-05")

        # t1 finishes 2 days late, t2 finishes on time -> avg 1.0 day late for Reconciliations
        conn.execute("UPDATE tasks SET status='done', completed_at=? WHERE id=?", ("2026-01-07T12:00:00", t1))
        conn.execute("UPDATE tasks SET status='done', completed_at=? WHERE id=?", ("2026-01-05T12:00:00", t2))
        # t3 finishes on time -> 0.0 for Journal Entries
        conn.execute("UPDATE tasks SET status='done', completed_at=? WHERE id=?", ("2026-01-05T12:00:00", t3))

        periods.close_period(conn, period_id, "2026-01-07")

        report = history.category_lateness_report(conn)

    by_category = {r["category"]: r["avg_lateness_days"] for r in report}
    assert by_category["Reconciliations"] == 1.0
    assert by_category["Journal Entries"] == 0.0
    # Reconciliations should sort first (worst bottleneck)
    assert report[0]["category"] == "Reconciliations"


def test_category_lateness_report_excludes_open_periods(db_path):
    with db.session(db_path) as conn:
        period_id = periods.create_period(conn, "Open Month", "2026-01-01", "2026-01-15")
        t1 = tasks.create_task(conn, period_id, "Bank rec", "Reconciliations", "Sam", "2026-01-05")
        conn.execute("UPDATE tasks SET status='done', completed_at=? WHERE id=?", ("2026-01-10T12:00:00", t1))
        # period never closed

        report = history.category_lateness_report(conn)

    assert report == []
