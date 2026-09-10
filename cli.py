"""Command-line interface for the month-end close tracker."""
from __future__ import annotations

import argparse
import sys

from close_tracker import calendar_suggest, dashboard, db, export, history, notifications, periods, tasks

DEFAULT_DB = "close_tracker.db"


def cmd_init_db(args):
    db.init_db(args.db)
    print(f"Initialized database at {args.db}")


def cmd_list_periods(args):
    with db.session(args.db) as conn:
        for p in periods.list_periods(conn):
            flag = " [AT RISK]" if p["at_risk"] else ""
            print(f"{p['id']:>3}  {p['label']:<25} {p['status']:<8} target={p['target_close_date']}{flag}")


def cmd_list_tasks(args):
    with db.session(args.db) as conn:
        for t in tasks.list_tasks(conn, args.period):
            overdue = " (OVERDUE)" if tasks.is_overdue(t) else ""
            print(f"{t['id']:>4}  {t['due_date']}  {t['status']:<12} {t['category']:<20} {t['name']}{overdue}")


def cmd_create_task(args):
    with db.session(args.db) as conn:
        task_id = tasks.create_task(
            conn, args.period, args.name, args.category, args.owner, args.due,
            notes=args.notes or "", estimated_duration_days=args.duration,
        )
    print(f"Created task {task_id}")


def cmd_add_dependency(args):
    with db.session(args.db) as conn:
        try:
            tasks.add_dependency(conn, args.task, args.depends_on)
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
    print(f"Task {args.task} now depends on task {args.depends_on}")


def cmd_set_status(args):
    with db.session(args.db) as conn:
        result = tasks.set_status(conn, args.task, args.status, force=args.force)
    if not result.ok:
        for e in result.errors:
            print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    print(f"Task {args.task} -> {args.status}")


def cmd_mark_blocked(args):
    with db.session(args.db) as conn:
        tasks.mark_blocked(conn, args.task, args.reason)
    print(f"Task {args.task} marked blocked: {args.reason}")


def cmd_dashboard(args):
    with db.session(args.db) as conn:
        pct = dashboard.percent_complete(conn, args.period)
        breakdown = dashboard.status_breakdown(conn, args.period)
        overdue = dashboard.overdue_tasks(conn, args.period)
        at_risk = dashboard.at_risk_view(conn, args.period)

    print(f"{pct}% complete  |  {breakdown}")
    print()
    print(f"Overdue ({len(overdue)}):")
    for t in overdue:
        print(f"  - {t['name']} (due {t['due_date']}, owner {t['owner']})")
    print()
    print(f"At risk ({len(at_risk)} blocked task(s)):")
    for entry in at_risk:
        print(f"  - {entry['task']['name']}: {entry['reason']}")
        for d in entry["downstream_at_risk"]:
            print(f"      downstream: {d['name']}")


def cmd_history(args):
    with db.session(args.db) as conn:
        print("Close duration history:")
        for h in history.close_duration_history(conn):
            print(f"  {h['label']}: {h['duration_days']} days ({h['start_date']} -> {h['actual_close_date']})")
        print()
        print("Category lateness (avg days late, closed periods only):")
        for h in history.category_lateness_report(conn):
            print(f"  {h['category']:<20} {h['avg_lateness_days']:+.1f} days avg  (n={h['task_count']})")


def cmd_suggest_calendar(args):
    with db.session(args.db) as conn:
        for row in calendar_suggest.suggest_calendar(conn, args.period):
            behind = " <-- behind actual due date" if row["behind_schedule"] else ""
            print(f"{row['suggested_start']} -> {row['suggested_finish']}  {row['name']} (due {row['actual_due_date']}){behind}")


def cmd_notify_overdue(args):
    with db.session(args.db) as conn:
        messages = notifications.notify_overdue_tasks(conn, args.period)
    for m in messages:
        print(m)
    if not messages:
        print("Nothing overdue.")


def cmd_export_summary(args):
    with db.session(args.db) as conn:
        export.export_close_summary_pdf(conn, args.period, args.output)
    print(f"Wrote {args.output}")


def main():
    parser = argparse.ArgumentParser(description="Month-end close tracker")
    parser.add_argument("--db", default=DEFAULT_DB)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init-db").set_defaults(func=cmd_init_db)
    sub.add_parser("list-periods").set_defaults(func=cmd_list_periods)

    p = sub.add_parser("list-tasks")
    p.add_argument("--period", type=int, required=True)
    p.set_defaults(func=cmd_list_tasks)

    p = sub.add_parser("create-task")
    p.add_argument("--period", type=int, required=True)
    p.add_argument("--name", required=True)
    p.add_argument("--category", required=True, choices=db.CATEGORIES)
    p.add_argument("--owner", required=True)
    p.add_argument("--due", required=True)
    p.add_argument("--duration", type=int, default=1)
    p.add_argument("--notes")
    p.set_defaults(func=cmd_create_task)

    p = sub.add_parser("add-dependency")
    p.add_argument("--task", type=int, required=True)
    p.add_argument("--depends-on", type=int, required=True, dest="depends_on")
    p.set_defaults(func=cmd_add_dependency)

    p = sub.add_parser("set-status")
    p.add_argument("--task", type=int, required=True)
    p.add_argument("--status", required=True, choices=db.STATUSES)
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=cmd_set_status)

    p = sub.add_parser("mark-blocked")
    p.add_argument("--task", type=int, required=True)
    p.add_argument("--reason", required=True)
    p.set_defaults(func=cmd_mark_blocked)

    p = sub.add_parser("dashboard")
    p.add_argument("--period", type=int, required=True)
    p.set_defaults(func=cmd_dashboard)

    sub.add_parser("history").set_defaults(func=cmd_history)

    p = sub.add_parser("suggest-calendar")
    p.add_argument("--period", type=int, required=True)
    p.set_defaults(func=cmd_suggest_calendar)

    p = sub.add_parser("notify-overdue")
    p.add_argument("--period", type=int, required=True)
    p.set_defaults(func=cmd_notify_overdue)

    p = sub.add_parser("export-summary")
    p.add_argument("--period", type=int, required=True)
    p.add_argument("--output", required=True)
    p.set_defaults(func=cmd_export_summary)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
