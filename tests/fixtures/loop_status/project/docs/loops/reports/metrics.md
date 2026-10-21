---
needs: [contract]
touches: [src/metrics.py]
effects: []
ships-to: staging
---
# Each report job records its duration and outcome

Row: stale. C1 had a current HOLDS on staging, but src/metrics.py changed after the commit it cites, and staging
serves that change.

## Done when

- **C1** Every finished job writes one duration and one outcome. Prove: 200 jobs, on staging.

## Decisions

| # | Decision | Decided by, date | Closes |
| --- | --- | --- | --- |

## Questions

| # | Question | Blocks | Default if unanswered |
| --- | --- | --- | --- |

## Evidence

- 2026-10-14 · C1 · HOLDS · rung 1 · staging @{sha:metrics-merge} · 200 of 200 jobs wrote both

## Shipped
