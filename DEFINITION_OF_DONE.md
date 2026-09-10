# Definition of Done

This project is considered complete when:

- [x] Core functionality implements everything in the project brief
- [x] Synthetic/sample data is generated and covers every scenario called for in the brief
- [x] Automated test suite passes
- [x] README.md documents: the close process for someone unfamiliar with it, how the tool models it, how to run it, a process-resilience section, and sample dashboard output
- [x] DESIGN_NOTES.md documents key trade-offs and judgment calls
- [x] LICENSE and .gitignore are present
- [x] The tool has actually been run end-to-end (not just code-reviewed) and output verified
- [ ] Pushed to its own GitHub repository

## Status: DONE, pending push (2026-09-09)

- Core: 5-category task checklist with enforced (force-overridable) dependencies and cycle prevention, status dashboard with overdue/at-risk views, downstream-impact calculation for blocked tasks, cross-period historical bottleneck reporting, a dependency/duration-based suggested calendar, simulated (logged, not sent) overdue notifications, SQLite storage, CLI + Streamlit UI, PDF export.
- Sample data: `seed_data/generate_seed_data.py` seeds one realistic 21-task close checklist applied to 2 closed prior months and 1 open current month, with 2 tasks deliberately blocked (with reasons) and their downstream ripple effects visible, and a consistent reconciliation-category lateness pattern so the historical bottleneck report has something real to surface.
- Tests: 20/20 passing (`pytest`).
- Verified end-to-end: ran the seed script, CLI (dashboard/history/suggest-calendar/export), and Streamlit app; read the generated PDF back to confirm layout and content. Found and fixed two real reportlab bugs in the process (column text overlap, and unescaped `&`/`<`/`>` corrupting PDF output) -- the second was also retroactively fixed in the already-shipped journal entry tool, which had the same latent bug. Also caught and removed emoji characters from the Streamlit UI before committing, per this portfolio's own style guidance.
- Repo: _(to be added once pushed)_
