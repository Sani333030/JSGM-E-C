import pytest

from close_tracker import db, periods, tasks


@pytest.fixture
def period(tmp_path):
    db_path = str(tmp_path / "test.db")
    db.init_db(db_path)
    with db.session(db_path) as conn:
        period_id = periods.create_period(conn, "Test Month", "2026-01-01", "2026-01-15")
    return db_path, period_id


def test_create_and_list_tasks(period):
    db_path, period_id = period
    with db.session(db_path) as conn:
        tasks.create_task(conn, period_id, "Bank rec", "Reconciliations", "Sam", "2026-01-05")
        tasks.create_task(conn, period_id, "Trial balance", "Review & Reporting", "Morgan", "2026-01-10")
        result = tasks.list_tasks(conn, period_id)
    assert len(result) == 2
    assert result[0]["due_date"] <= result[1]["due_date"]


def test_dependency_cycle_is_rejected(period):
    db_path, period_id = period
    with db.session(db_path) as conn:
        a = tasks.create_task(conn, period_id, "A", "Pre-close", "Sam", "2026-01-02")
        b = tasks.create_task(conn, period_id, "B", "Pre-close", "Sam", "2026-01-03")
        tasks.add_dependency(conn, b, a)  # B depends on A

        with pytest.raises(ValueError):
            tasks.add_dependency(conn, a, b)  # would cycle back


def test_self_dependency_is_rejected(period):
    db_path, period_id = period
    with db.session(db_path) as conn:
        a = tasks.create_task(conn, period_id, "A", "Pre-close", "Sam", "2026-01-02")
        with pytest.raises(ValueError):
            tasks.add_dependency(conn, a, a)


def test_downstream_impact_is_transitive(period):
    db_path, period_id = period
    with db.session(db_path) as conn:
        a = tasks.create_task(conn, period_id, "A", "Pre-close", "Sam", "2026-01-02")
        b = tasks.create_task(conn, period_id, "B", "Reconciliations", "Sam", "2026-01-03")
        c = tasks.create_task(conn, period_id, "C", "Journal Entries", "Sam", "2026-01-04")
        tasks.add_dependency(conn, b, a)  # B depends on A
        tasks.add_dependency(conn, c, b)  # C depends on B

        downstream = {t["id"] for t in tasks.downstream_impact(conn, a)}
        assert downstream == {b, c}


def test_cannot_mark_done_with_incomplete_dependency(period):
    db_path, period_id = period
    with db.session(db_path) as conn:
        a = tasks.create_task(conn, period_id, "A", "Pre-close", "Sam", "2026-01-02")
        b = tasks.create_task(conn, period_id, "B", "Reconciliations", "Sam", "2026-01-03")
        tasks.add_dependency(conn, b, a)

        result = tasks.set_status(conn, b, "done")
        assert not result.ok
        assert tasks.get_task(conn, b)["status"] != "done"


def test_force_overrides_dependency_check(period):
    db_path, period_id = period
    with db.session(db_path) as conn:
        a = tasks.create_task(conn, period_id, "A", "Pre-close", "Sam", "2026-01-02")
        b = tasks.create_task(conn, period_id, "B", "Reconciliations", "Sam", "2026-01-03")
        tasks.add_dependency(conn, b, a)

        result = tasks.set_status(conn, b, "done", force=True)
        assert result.ok
        assert tasks.get_task(conn, b)["status"] == "done"


def test_completing_dependency_first_allows_normal_completion(period):
    db_path, period_id = period
    with db.session(db_path) as conn:
        a = tasks.create_task(conn, period_id, "A", "Pre-close", "Sam", "2026-01-02")
        b = tasks.create_task(conn, period_id, "B", "Reconciliations", "Sam", "2026-01-03")
        tasks.add_dependency(conn, b, a)

        tasks.set_status(conn, a, "done")
        result = tasks.set_status(conn, b, "done")
        assert result.ok
        assert tasks.get_task(conn, b)["status"] == "done"


def test_mark_blocked_sets_status_and_reason(period):
    db_path, period_id = period
    with db.session(db_path) as conn:
        a = tasks.create_task(conn, period_id, "A", "Pre-close", "Sam", "2026-01-02")
        tasks.mark_blocked(conn, a, "Waiting on external data")
        task = tasks.get_task(conn, a)
    assert task["status"] == "blocked"
    assert task["delay_reason"] == "Waiting on external data"


def test_is_overdue(period):
    from datetime import date

    db_path, period_id = period
    with db.session(db_path) as conn:
        a = tasks.create_task(conn, period_id, "A", "Pre-close", "Sam", "2026-01-02")
        task = tasks.get_task(conn, a)

    assert tasks.is_overdue(task, as_of=date(2026, 1, 5))
    assert not tasks.is_overdue(task, as_of=date(2026, 1, 1))
