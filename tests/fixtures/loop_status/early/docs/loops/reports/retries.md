---
needs: [queue]
touches: [src/retries.py, tests/test_retries.py]
effects: []
ships-to: staging
---
# A failed report job is retried at most three times

The version of this concern that its branch was started from; the project's version changed after.

## Done when

- **C1** A job that fails is retried. Prove: a failing job, on staging.

## Decisions

| # | Decision | Decided by, date | Closes |
| --- | --- | --- | --- |

## Questions

| # | Question | Blocks | Default if unanswered |
| --- | --- | --- | --- |

## Evidence

## Shipped
