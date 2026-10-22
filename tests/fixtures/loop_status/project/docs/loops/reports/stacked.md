---
needs: []
touches: [src/stacked.py]
effects: []
ships-to: staging
---
# A stacked change waits on its branch until it reaches main

Row: building. PR #10 merged into reports/retries, not main, so it does not count as merged; its branch still
exists, and none of its work is on main.

## Done when

- **C1** The stacked change is on main. Prove: a test, on staging.

## Decisions

| # | Decision | Decided by, date | Closes |
| --- | --- | --- | --- |

## Questions

| # | Question | Blocks | Default if unanswered |
| --- | --- | --- | --- |

## Evidence

## Shipped
