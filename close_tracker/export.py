"""Exports a close-period summary as a PDF -- something to show a
controller or manager: overall progress, on-time rate, and anything
currently blocked with what it's putting at risk downstream."""
from __future__ import annotations

import sqlite3
from datetime import datetime
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from . import dashboard as dashboard_module
from . import periods as periods_module
from . import tasks as tasks_module

STYLES = getSampleStyleSheet()
CELL_STYLE = ParagraphStyle("cell", parent=STYLES["Normal"], fontSize=8, leading=10)


def _p(text: str, style=STYLES["Normal"]) -> Paragraph:
    """A Paragraph flowable parses its text as mini-XML, so any free-text
    field (task names, reasons, owner names) must be escaped first --
    otherwise a stray '&' or '<' (e.g. "FP&A Analyst") breaks the markup
    and renders garbled instead of raising an error."""
    return Paragraph(escape(text), style)


def _on_time_rate(all_tasks) -> float:
    done = [t for t in all_tasks if t["status"] == "done" and t["completed_at"]]
    if not done:
        return 0.0
    on_time = sum(1 for t in done if t["completed_at"][:10] <= t["due_date"])
    return round(100 * on_time / len(done), 1)


def export_close_summary_pdf(conn: sqlite3.Connection, close_period_id: int, outpath: str) -> None:
    period = periods_module.get_period(conn, close_period_id)
    all_tasks = tasks_module.list_tasks(conn, close_period_id)
    breakdown = dashboard_module.status_breakdown(conn, close_period_id)
    overdue = dashboard_module.overdue_tasks(conn, close_period_id)
    at_risk = dashboard_module.at_risk_view(conn, close_period_id)
    percent = dashboard_module.percent_complete(conn, close_period_id)

    doc = SimpleDocTemplate(outpath, pagesize=letter, topMargin=0.6 * inch, bottomMargin=0.6 * inch)
    story = [
        _p(f"Month-End Close Summary -- {period['label']}", STYLES["Title"]),
        Spacer(1, 0.1 * inch),
        _p(
            f"Status: {period['status'].title()} | Target close: {period['target_close_date']} | "
            f"{percent}% complete | On-time rate (completed tasks): {_on_time_rate(all_tasks)}%",
        ),
        Spacer(1, 0.2 * inch),
    ]

    if period["at_risk"]:
        story.append(Paragraph(f"<b>Close flagged at risk:</b> {escape(period['at_risk_reason'])}", STYLES["Normal"]))
        story.append(Spacer(1, 0.15 * inch))

    summary_rows = [["Not started", "In progress", "Done", "Blocked", "Overdue"]]
    summary_rows.append(
        [str(breakdown["not_started"]), str(breakdown["in_progress"]), str(breakdown["done"]), str(breakdown["blocked"]), str(len(overdue))]
    )
    summary_table = Table(summary_rows, colWidths=[1.4 * inch] * 5)
    summary_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2b2b2b")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
            ]
        )
    )
    story.append(summary_table)
    story.append(Spacer(1, 0.2 * inch))

    if at_risk:
        story.append(Paragraph("<b>Blocked tasks and downstream impact</b>", STYLES["Heading3"]))
        for entry in at_risk:
            task = entry["task"]
            downstream_names = escape(", ".join(d["name"] for d in entry["downstream_at_risk"]) or "(none)")
            story.append(
                Paragraph(
                    f"<b>{escape(task['name'])}</b> ({escape(task['owner'])}) -- {escape(entry['reason'])}<br/>"
                    f"At-risk downstream tasks: {downstream_names}",
                    STYLES["Normal"],
                )
            )
            story.append(Spacer(1, 0.1 * inch))
        story.append(Spacer(1, 0.1 * inch))

    story.append(Paragraph("<b>All tasks</b>", STYLES["Heading3"]))
    task_rows = [["Category", "Task", "Owner", "Due", "Status"]]
    for t in all_tasks:
        status_label = t["status"].replace("_", " ").title()
        if tasks_module.is_overdue(t):
            status_label += " (overdue)"
        task_rows.append(
            [
                _p(t["category"], CELL_STYLE),
                _p(t["name"], CELL_STYLE),
                _p(t["owner"], CELL_STYLE),
                t["due_date"],
                status_label,
            ]
        )

    task_table = Table(task_rows, colWidths=[1.1 * inch, 2.1 * inch, 1.6 * inch, 0.8 * inch, 1.1 * inch])
    task_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2b2b2b")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
            ]
        )
    )
    story.append(task_table)

    doc.build(story)
