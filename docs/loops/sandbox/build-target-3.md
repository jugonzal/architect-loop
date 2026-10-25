---
needs: []
touches: [sandbox/build-target-3/]
effects: []
ships-to: main
---
# A third /loop-build target exists for a session to build, after two were used up

## Done when

- **C1** `sandbox/build-target-3/hello.txt` holds the single line `hello` on the session's branch. Prove: read the
  file on that branch after a dispatched `/loop-build`, on staging/runner. Its PR is closed unmerged (per
  command-center/D61).
- **C2** Every commit the session makes carries `Concern: sandbox/build-target-3` and `Sponsored-by: <person>` (per
  command-center/D45). Prove: list the branch's commit trailers, on staging/runner.

## Design

### Where we are

- Verified (main @4b6bb85, 2026-10-25): `build-target` was built and its PR merged by mistake (#73), then reverted
  (#74), and `build-target-2` was marked shipped by the docs commit that added it, which carried a `Concern:`
  trailer. `/loop-status` counts any commit with the trailer as the concern's work, so both are shipped and
  `/loop-build` refuses them (per sandbox/D3, D4). This concern is the same target under a fresh name.
- Missing: `sandbox/build-target-3/` does not exist. The build creates it, on a branch that is never merged.

## Decisions

| # | Decision | Decided by, date | Closes |
| --- | --- | --- | --- |

## Questions

| # | Question | Blocks | Default if unanswered |
| --- | --- | --- | --- |

## Evidence

## Shipped
