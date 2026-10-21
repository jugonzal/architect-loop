---
needs: []
touches: [src/jobs/contract.py, tests/test_contract.py]
effects: []
ships-to: main
---
# Every report job carries a versioned payload

Row: done, by a claim whose Prove is CI on main (rung 5, no line needed), with no Shipped note, so a record item.

## Done when

- **C1** A job payload without a version is rejected before it is queued. Prove: unit tests, in CI on main.

## Decisions

| # | Decision | Decided by, date | Closes |
| --- | --- | --- | --- |

## Questions

| # | Question | Blocks | Default if unanswered |
| --- | --- | --- | --- |

## Evidence

## Shipped

<!-- Written once, by loop-status, when the concern is done. -->
