---
needs: [queue]
touches: [src/dashboard/, src/export/csv.py]
effects: []
ships-to: production
---
# Operators see queue depth and failures on one page

Row: open. Q1 blocks C1 and is unanswered. It records options and a recommendation, which the question item
carries as questions.py reads them.

## Done when

- **C1** The queue depth shown is never more than 30 s old. Prove: a timed check, on production.

## Decisions

| # | Decision | Decided by, date | Closes |
| --- | --- | --- | --- |

## Questions

| # | Question | Blocks | Default if unanswered |
| --- | --- | --- | --- |
| Q1 | Which store holds the dashboard's metrics? | C1 | The reports database, until the page needs more than one sample a minute |

**Q1 options**
- **The reports database**: nothing new to run or back up, but queries slow the reports above one sample a
  minute. (recommended)
- **A separate time-series store**: a sample every second, but one more service to deploy, monitor and back up.

## Evidence

## Shipped
