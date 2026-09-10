# Month-End Close Tracker

Turns the month-end close from a checklist buried in someone's inbox into
a tracked process: every task has an owner, a due date, and a place
attached to it that isn't a status update, and a disruption anywhere in
the sequence is visible immediately, not discovered during the review
meeting.

## The month-end close, briefly

Every month, accounting has to take all the period's activity and turn it
into trustworthy financial statements before a deadline, usually 10-15
business days after the period ends. That means: locking sub-ledgers so
nothing else posts to the period, reconciling cash and other accounts
against outside statements, recording the adjusting entries that don't
show up automatically (accruals, depreciation, prepaid amortization,
revenue recognition), reviewing the resulting trial balance for anything
that looks wrong, and finally locking the period and signing off. Most of
these steps depend on an earlier one finishing first — you can't finalize
accrual entries before the bank reconciliation that tells you what's
actually outstanding — which is exactly why a single missed or delayed
task tends to cascade into a late close overall.

## How this tool models it

- **Tasks**, grouped into five fixed categories that mirror the real
  process: Pre-close, Reconciliations, Journal Entries, Review & Reporting,
  Close-out. (Reconciliations and Journal Entries are exactly what the
  other two tools in this portfolio automate — see
  [Related projects](#related-projects) below.)
- **Dependencies** between tasks, enforced, not just noted: marking a task
  "done" is blocked by default if something it depends on isn't done yet
  (`close_tracker.tasks.set_status`), with an explicit `force` override for
  when a real close genuinely needs to jump the sequence.
- **A status dashboard**: percent complete, a breakdown by status and by
  category, and an overdue list computed against the real due dates.
- **Interruption handling**: a task can be marked blocked with a reason,
  and the dashboard shows every downstream task that depends on it —
  transitively, not just the next one in line — so "this is stuck" turns
  into "here's everything at risk because of it" automatically.
- **Historical tracking**: once a period is closed, its duration and each
  category's average lateness get folded into a cross-period report, so
  "reconciliations are always last" becomes something you can actually
  see across the last several closes instead of an impression.

## Process resilience: what happens when something breaks

Real close processes get disrupted constantly — someone's out sick, a
subsidiary is late sending numbers, a bank statement doesn't show up on
time. A tool that only shows a clean checklist hides exactly the
information that matters most when that happens. So here, a blocked task:

1. Is marked with a required reason (`tasks.mark_blocked`) — never just a
   silent status change.
2. Immediately surfaces every task that depends on it, directly or
   transitively (`tasks.downstream_impact`), in the dashboard's at-risk view.
3. Can flag the whole close as at risk (`periods.set_at_risk`) with its own
   reason, visible at the top of the dashboard and in the exported PDF.
4. Still lets a task complete anyway via an explicit `force` override —
   because in practice, sometimes the sequence does get jumped under time
   pressure, and the tool's job is to make that visible, not to make it
   impossible.

The seeded demo data (see below) has two tasks blocked for realistic
reasons (a subsidiary that hasn't sent its numbers, a preparer out on
leave) specifically so this behavior is something you can see running,
not just read about.

## Running it

```bash
pip install -r requirements.txt

# Load the demo data: 2 closed months + 1 open month with 2 blocked tasks
python seed_data/generate_seed_data.py

# Web UI
streamlit run app.py

# Or the CLI
python cli.py --db seed_data/demo.db list-periods
python cli.py --db seed_data/demo.db dashboard --period 3
python cli.py --db seed_data/demo.db history
python cli.py --db seed_data/demo.db suggest-calendar --period 3
python cli.py --db seed_data/demo.db export-summary --period 3 --output close_summary.pdf
```

## Sample dashboard output

From the seeded "current" period, run through `cli.py dashboard`:

```
33.3% complete  |  {'not_started': 10, 'in_progress': 2, 'done': 7, 'blocked': 2}

Overdue (5):
  - Intercompany reconciliation (due 2026-09-07, owner Sam Okafor (Staff Accountant))
  - Record accruals (due 2026-09-08, owner Sam Okafor (Staff Accountant))
  ...

At risk (2 blocked task(s)):
  - Intercompany reconciliation: Waiting on the subsidiary's trial balance export
    from their local bookkeeper; requested twice, still not received.
      downstream: Intercompany elimination entries
      downstream: Trial balance review
      downstream: Variance analysis vs. prior month/budget
      downstream: Flux commentary write-up
      downstream: Financial statement draft
      downstream: Management review meeting
      downstream: Period lock in ERP
      downstream: Final sign-off / distribute financials
  - Revenue recognition adjustments: Revenue Accountant (Jordan Kim) is out on
    unplanned medical leave; reassigning to a backup preparer.
      downstream: Trial balance review
      ...
```

And the cross-period bottleneck report (`cli.py history`), which is where
the tool proves the brief's own example — "bank rec is consistently the
last task done" — with actual numbers rather than an anecdote:

```
Category lateness (avg days late, closed periods only):
  Reconciliations      +1.2 days avg  (n=10)
  Pre-close            +0.0 days avg  (n=6)
  Journal Entries      +0.0 days avg  (n=12)
  Review & Reporting   +0.0 days avg  (n=10)
  Close-out            +0.0 days avg  (n=4)
```

`export-summary` produces a formatted PDF version of the dashboard view,
suitable for handing to a controller or manager.

## Sample data

`seed_data/generate_seed_data.py` builds one realistic 21-task close
checklist (Pre-close through Close-out, with the dependency chain a real
close would have) and applies it to three periods: two prior months, fully
closed, with a deliberate pattern where reconciliation tasks consistently
finish a day or two late (so the historical bottleneck report has
something real to find); and the current, still-open month, with two
tasks blocked for realistic reasons and their downstream ripple effects
visible in the dashboard. All company and people names are fictional.

## Related projects

This is the fourth piece of a small accounting-automation portfolio, built
last on purpose because it ties the others together conceptually:

- **[Transaction Reconciliation Tool](../transaction-reconciliation-tool)** —
  what a "Reconciliations" category task in this tracker is actually
  automating.
- **[Journal Entry Documentation Tool](../journal-entry-tool)** — same
  relationship for the "Journal Entries" category (accruals, prepaid
  recognition, depreciation).

They're separate repos/tools, not a code dependency — this tracker
references them as the process context a real close task sits inside, the
same way the brief describes it.

## Project structure

```
close_tracker/
  db.py                 SQLite schema + connection helper
  periods.py             close period CRUD, at-risk flagging
  tasks.py                task CRUD, dependency graph (with cycle prevention), status transitions
  dashboard.py            percent complete, overdue, at-risk + downstream impact
  history.py              cross-period close duration + category bottleneck reports
  calendar_suggest.py     dependency/duration-based suggested calendar (stretch goal)
  notifications.py        simulated overdue notifications, logged not sent (stretch goal)
  export.py               PDF close summary export
cli.py                    command-line interface
app.py                    Streamlit UI: kanban checklist, dashboard, history, suggested calendar
seed_data/                generate_seed_data.py + the resulting demo.db
tests/                    one test file per module
```

See [DESIGN_NOTES.md](DESIGN_NOTES.md) for the reasoning behind specific
rules and trade-offs.

## Tests

```bash
pytest
```

## License

MIT — see [LICENSE](LICENSE).
