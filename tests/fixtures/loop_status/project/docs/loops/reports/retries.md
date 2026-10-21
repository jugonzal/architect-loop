---
needs: [queue]
touches: [src/retries.py, tests/test_retries.py]
effects: []
ships-to: staging
---
# A failed report job is retried at most three times

Row: building. PR #5 is open and ready for review, so a review item. The branch started before this file was last
changed, and queue, which it needs, is not done yet (both drift).

## Done when

- **C1** A job that fails three times is marked failed and not retried again. Prove: a failing job, on staging.

## Decisions

| # | Decision | Decided by, date | Closes |
| --- | --- | --- | --- |

## Questions

| # | Question | Blocks | Default if unanswered |
| --- | --- | --- | --- |

## Evidence

## Shipped
