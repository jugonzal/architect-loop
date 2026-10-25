---
needs: []
touches: [sandbox/build-target/]
effects: []
ships-to: main
---
# A /loop-build session has a trivial concern to build whose PR is thrown away

## Done when

- **C1** `sandbox/build-target/hello.txt` holds the single line `hello` on the session's branch. Prove: read the
  file on that branch after a dispatched `/loop-build`, on staging/runner. Its PR is closed unmerged (per
  command-center/D61).
- **C2** Every commit the session makes carries `Concern: sandbox/build-target` and `Sponsored-by: <person>` (per
  command-center/D45). Prove: list the branch's commit trailers, on staging/runner.

## Design

### Where we are

- Missing: `sandbox/` does not exist. The build creates it, on a branch that is never merged.

## Decisions

| # | Decision | Decided by, date | Closes |
| --- | --- | --- | --- |

## Questions

| # | Question | Blocks | Default if unanswered |
| --- | --- | --- | --- |

## Evidence

## Shipped
