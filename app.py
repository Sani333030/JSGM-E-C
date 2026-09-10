"""Streamlit UI: a kanban-style close checklist, a status dashboard,
at-risk/downstream-impact view, historical trends, and a suggested
calendar -- all built on the same close_tracker library the CLI uses."""
from __future__ import annotations

import os
import tempfile

import streamlit as st

from close_tracker import calendar_suggest, dashboard, db, export, history, notifications, periods, tasks

DB_PATH = os.environ.get("CLOSE_TRACKER_DB", os.path.join("seed_data", "demo.db"))

st.set_page_config(page_title="Month-End Close Tracker", layout="wide")

if not os.path.exists(DB_PATH):
    db.init_db(DB_PATH)

st.title("Month-End Close Tracker")
st.caption("Every task has an owner, a due date, and -- when something goes wrong -- a reason the tool won't let get lost.")

with db.session(DB_PATH) as conn:
    all_periods = periods.list_periods(conn)

if not all_periods:
    st.warning("No close periods yet. Run `python seed_data/generate_seed_data.py` to load the demo data, or create one below.")
    with st.form("new_period"):
        label = st.text_input("Period label (e.g. 'October 2026 Close')")
        start = st.date_input("Start date")
        target = st.date_input("Target close date")
        if st.form_submit_button("Create period") and label:
            with db.session(DB_PATH) as conn:
                periods.create_period(conn, label, str(start), str(target))
            st.rerun()
    st.stop()

period_names = {p["id"]: f"{p['label']} ({p['status']})" for p in all_periods}
default_period = next((p["id"] for p in all_periods if p["status"] == "open"), all_periods[0]["id"])
period_id = st.sidebar.selectbox(
    "Close period", options=list(period_names), format_func=lambda i: period_names[i],
    index=list(period_names).index(default_period),
)

with db.session(DB_PATH) as conn:
    period = periods.get_period(conn, period_id)

tab_board, tab_dashboard, tab_history, tab_calendar = st.tabs(
    ["Checklist", "Dashboard & At-Risk", "Historical Trends", "Suggested Calendar"]
)

with tab_board:
    st.subheader(f"{period['label']} -- checklist")

    with st.expander("Add a task"):
        with st.form("new_task"):
            c1, c2 = st.columns(2)
            name = c1.text_input("Task name")
            category = c2.selectbox("Category", options=db.CATEGORIES)
            c3, c4, c5 = st.columns(3)
            owner = c3.text_input("Owner")
            due = c4.date_input("Due date")
            duration = c5.number_input("Estimated duration (days)", min_value=1, value=1)
            notes = st.text_area("Notes")
            if st.form_submit_button("Create task") and name and owner:
                with db.session(DB_PATH) as conn:
                    tasks.create_task(conn, period_id, name, category, owner, str(due), notes, int(duration))
                st.rerun()

    with db.session(DB_PATH) as conn:
        all_tasks = tasks.list_tasks(conn, period_id)

    columns = st.columns(4)
    labels = {"not_started": "Not Started", "in_progress": "In Progress", "done": "Done", "blocked": "Blocked"}
    for col, status in zip(columns, ["not_started", "in_progress", "done", "blocked"]):
        col.markdown(f"**{labels[status]}**")
        for t in [t for t in all_tasks if t["status"] == status]:
            overdue = tasks.is_overdue(t)
            tag = "[OVERDUE] " if overdue else ""
            with col.container(border=True):
                st.write(f"{tag}**{t['name']}**")
                st.caption(f"{t['category']} - {t['owner']} - due {t['due_date']}")
                if t["delay_reason"]:
                    st.caption(f"Reason: {t['delay_reason']}")

                new_status = st.selectbox(
                    "Status", options=list(labels), format_func=lambda s: labels[s],
                    index=list(labels).index(t["status"]), key=f"status_{t['id']}", label_visibility="collapsed",
                )
                if new_status != t["status"]:
                    if new_status == "blocked":
                        reason = st.text_input("Reason blocked", key=f"reason_{t['id']}")
                        if reason and st.button("Confirm block", key=f"block_btn_{t['id']}"):
                            with db.session(DB_PATH) as conn:
                                tasks.mark_blocked(conn, t["id"], reason)
                            st.rerun()
                    else:
                        with db.session(DB_PATH) as conn:
                            result = tasks.set_status(conn, t["id"], new_status)
                        if not result.ok:
                            for e in result.errors:
                                st.error(e)
                            if st.button("Force anyway", key=f"force_{t['id']}"):
                                with db.session(DB_PATH) as conn:
                                    tasks.set_status(conn, t["id"], new_status, force=True)
                                st.rerun()
                        else:
                            st.rerun()

with tab_dashboard:
    st.subheader(f"{period['label']} -- dashboard")
    with db.session(DB_PATH) as conn:
        pct = dashboard.percent_complete(conn, period_id)
        breakdown = dashboard.status_breakdown(conn, period_id)
        overdue = dashboard.overdue_tasks(conn, period_id)
        at_risk = dashboard.at_risk_view(conn, period_id)
        category_stats = dashboard.category_breakdown(conn, period_id)

    st.metric("Overall progress", f"{pct}%")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Not started", breakdown["not_started"])
    c2.metric("In progress", breakdown["in_progress"])
    c3.metric("Done", breakdown["done"])
    c4.metric("Blocked", breakdown["blocked"])

    if period["at_risk"]:
        st.error(f"Close flagged at risk: {period['at_risk_reason']}")

    st.markdown("**By category**")
    st.table(category_stats)

    st.markdown(f"**Overdue ({len(overdue)})**")
    for t in overdue:
        st.write(f"- {t['name']} (due {t['due_date']}, owner {t['owner']})")

    st.markdown(f"**Blocked tasks and downstream impact ({len(at_risk)})**")
    for entry in at_risk:
        st.warning(
            f"**{entry['task']['name']}** -- {entry['reason']}\n\n"
            f"At-risk downstream: {', '.join(d['name'] for d in entry['downstream_at_risk']) or '(none)'}"
        )

    st.markdown("---")
    if st.button("Simulate overdue notifications"):
        with db.session(DB_PATH) as conn:
            messages = notifications.notify_overdue_tasks(conn, period_id)
        for m in messages:
            st.write(m)
        if not messages:
            st.write("Nothing overdue.")

    if st.button("Export close summary PDF"):
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        tmp.close()
        with db.session(DB_PATH) as conn:
            export.export_close_summary_pdf(conn, period_id, tmp.name)
        with open(tmp.name, "rb") as f:
            st.download_button("Download PDF", f.read(), file_name=f"close_summary_{period_id}.pdf", mime="application/pdf")

with tab_history:
    st.subheader("Historical close trends")
    with db.session(DB_PATH) as conn:
        durations = history.close_duration_history(conn)
        lateness = history.category_lateness_report(conn)

    if durations:
        st.markdown("**Close duration by month**")
        st.bar_chart({d["label"]: d["duration_days"] for d in durations})
    else:
        st.write("No closed periods yet.")

    st.markdown("**Category lateness (avg days late, closed periods)**")
    st.caption("The category at the top is the recurring bottleneck.")
    st.table(lateness)

with tab_calendar:
    st.subheader(f"{period['label']} -- suggested calendar")
    st.caption(
        "Earliest possible start/finish for each task based on its dependencies and estimated duration -- "
        "not a replacement for the actual due dates, just a check on whether the schedule has slack or is tight."
    )
    with db.session(DB_PATH) as conn:
        suggestion = calendar_suggest.suggest_calendar(conn, period_id)
    st.table(suggestion)
