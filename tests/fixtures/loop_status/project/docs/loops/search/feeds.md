---
needs: [reports/metrics]
touches: [src/feeds/]
effects: []
ships-to: production
---
# Each requester has a feed of their reports' durations

Row: blocked. reports/metrics, which it needs, is on main, but its one HOLDS is no longer current: src/metrics.py
changed after the commit it cites (command-center/D50). Its next step is the proof that would meet the need, on
staging, the lowest environment that serves it.

## Done when

- **C1** A finished report shows its duration in the requester's feed. Prove: 20 reports, on production.

## Decisions

| # | Decision | Decided by, date | Closes |
| --- | --- | --- | --- |

## Questions

| # | Question | Blocks | Default if unanswered |
| --- | --- | --- | --- |

## Evidence

## Shipped
