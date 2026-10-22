---
needs: [queue]
touches: [src/worker/]
effects: []
ships-to: staging
---
# A worker generates each report within 30 seconds

Row: contradicted. C2's latest verdict is CONTRADICTS, and the only decision is dated before it. The line says it
contradicts a shared decision, so the item escalates. PR #3 also changed README.md, outside touches (drift).

## Done when

- **C1** A report job produces a PDF. Prove: 50 jobs, on staging.
- **C2** The p95 generation time is at most 30 s. Prove: 200 jobs, on staging.

## Decisions

| # | Decision | Decided by, date | Closes |
| --- | --- | --- | --- |
| D1 | Render with the existing PDF library. | Ana, 2026-10-03 | |

## Questions

| # | Question | Blocks | Default if unanswered |
| --- | --- | --- | --- |

## Evidence

- 2026-10-17 · C1 · HOLDS · rung 1 · staging @{sha:staging-build} · 50 of 50 jobs produced a PDF
- 2026-10-18 · C2 · CONTRADICTS · rung 1 · staging @{sha:staging-build} · p95 41 s over 200 jobs, needs at most 30 s; contradicts reports/D1

## Shipped
