import pytest

from close_tracker import db, periods


@pytest.fixture
def db_path(tmp_path):
    path = str(tmp_path / "test.db")
    db.init_db(path)
    return path


def test_create_and_get_period(db_path):
    with db.session(db_path) as conn:
        period_id = periods.create_period(conn, "March 2026", "2026-03-01", "2026-03-15")
        period = periods.get_period(conn, period_id)
    assert period["label"] == "March 2026"
    assert period["status"] == "open"


def test_close_period_sets_actual_close_date(db_path):
    with db.session(db_path) as conn:
        period_id = periods.create_period(conn, "March 2026", "2026-03-01", "2026-03-15")
        periods.close_period(conn, period_id, "2026-03-14")
        period = periods.get_period(conn, period_id)
    assert period["status"] == "closed"
    assert period["actual_close_date"] == "2026-03-14"


def test_at_risk_flag_set_and_cleared(db_path):
    with db.session(db_path) as conn:
        period_id = periods.create_period(conn, "March 2026", "2026-03-01", "2026-03-15")
        periods.set_at_risk(conn, period_id, "Two blocked tasks")
        period = periods.get_period(conn, period_id)
        assert period["at_risk"] == 1
        assert period["at_risk_reason"] == "Two blocked tasks"

        periods.clear_at_risk(conn, period_id)
        period = periods.get_period(conn, period_id)
        assert period["at_risk"] == 0
        assert period["at_risk_reason"] is None
