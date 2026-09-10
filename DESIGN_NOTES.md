# Design Notes

Trade-offs and judgment calls made while building this, and why.

## Dependencies are enforced by default, with an explicit override

`tasks.set_status` refuses to mark a task "done" if something it depends
on isn't done yet — this directly implements the brief's own example
("JEs can't be finalized until bank rec is done"). But real closes do
sometimes need to jump the sequence under real time pressure, so a
`force=True` override exists rather than making the rule absolute. The
difference from a silent allowance: forcing is a deliberate, visible
action a preparer has to take, not something that happens by accident —
the tool still tells you exactly what dependency you're skipping past.

## Cycles are prevented at the point a dependency is added, not detected later

`tasks.add_dependency` walks the existing dependency graph before
inserting a new edge and refuses anything that would create a cycle. The
alternative — allowing cycles and detecting them later (e.g., when
computing a suggested calendar) — would mean a broken dependency graph
could sit in the data for a while before anything noticed. Refusing at
insertion means a valid topological order is guaranteed to exist
everywhere else in the codebase that assumes one (`calendar_suggest.py`
relies on this directly).

## Downstream impact excludes tasks that are already done

`dashboard.at_risk_view` filters `tasks.downstream_impact()` down to
tasks that aren't done yet. A task that already finished isn't at risk
just because something upstream of it (in the dependency graph, not in
time) is now blocked — dependency direction and chronological order are
related but not identical, and only the tasks still ahead of the blocker
are actually affected.

## The close-level "at risk" flag is a manual/narrative signal, not auto-computed

Individual tasks compute their overdue status automatically (`due_date`
vs. today). Whether the *whole close* is at risk is set explicitly
(`periods.set_at_risk`) with a required reason, rather than being derived
automatically from "N tasks are blocked." A close with one blocked task
that has no real downstream impact isn't necessarily at risk; a close
with one blocked task sitting in front of eleven downstream tasks
probably is. That's a judgment call about materiality that this tool
surfaces the *inputs* for (the at-risk view, the downstream list) rather
than trying to encode as a threshold that would inevitably be wrong for
some periods.

## The suggested calendar is a critical-path calculation, not a scheduler

`calendar_suggest.py` computes each task's earliest possible start/finish
from its dependencies and estimated duration — a forward pass over the
dependency DAG, not a resource-constrained scheduling algorithm. It
doesn't know that the same person owns five tasks and can't do them all
simultaneously; it answers "what does the dependency structure alone
allow," which is a useful sanity check (are the actual due dates tighter
or looser than the minimum the dependencies require) without pretending
to solve a harder problem (who's actually available when) that would need
capacity data this tool doesn't model.

## Notifications are logged, not sent

`notifications.notify_overdue_tasks` records what message *would* go to
whom and never touches email/Slack/anything external. Simulating a
convincing-looking send would be strictly worse than being honest that
it's a log: a fake "sent" status invites someone to trust that a real
person was actually notified when they weren't. Wiring this to a real
channel is a last-mile integration decision specific to whatever a given
firm already uses.

## Two real bugs found and fixed while building the PDF export

Both are documented here rather than just silently fixed, because they're
the kind of mistake that's easy to make with `reportlab` and easy to miss
in testing if your test data happens not to trigger them:

1. **Column overlap**: `reportlab.Table` cells given plain strings don't
   wrap — a long owner name simply overflowed into the next column. Fixed
   by wrapping free-text cell content in `Paragraph` flowables, which do
   wrap within the column width.
2. **Broken entities on `&`/`<`/`>`**: `Paragraph` parses its text as
   mini-XML, so an unescaped `&` (e.g. "FP&A Analyst") silently rendered
   as a broken entity reference instead of the literal character. Fixed
   by escaping all free-text content (`xml.sax.saxutils.escape`) before
   it reaches a `Paragraph`. The same bug existed in the journal entry
   tool's PDF export (built earlier in this portfolio, before this one
   surfaced the pattern) and was fixed there too once found here.

## Fixed categories, not a user-defined taxonomy

The five categories (Pre-close, Reconciliations, Journal Entries, Review &
Reporting, Close-out) are a `CHECK` constraint, not a free-text field or a
configurable list. The brief explicitly asks for "a realistic, general
small-to-mid-size company close process" applied consistently rather than
modeling every possible close variant — a fixed, opinionated taxonomy is
what makes the historical bottleneck report ("which category is
consistently late") meaningful across periods; a free-text category field
would let the same real task get spelled three different ways across
three months and quietly break that comparison.

## What's intentionally out of scope

- **Multi-user accounts/permissions** — owners are names on a task, not
  logins. Consistent with the same choice in the journal entry tool: a
  demo tool proving the workflow logic doesn't need an auth system to do
  that.
- **Real calendar/email integration** — due dates and notifications are
  data and log entries, not live calendar invites or sent messages.
- **Resource-constrained scheduling** — see the suggested-calendar note
  above; capacity planning (who can actually do what, when) is a
  meaningfully larger problem than the dependency-based calendar this
  tool provides.
