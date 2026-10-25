---
needs: []
touches: [docs/loops/sandbox/design-target.md]
effects: []
ships-to: main
---
# A /loop-design session has an open question to answer inside the sandbox

## Done when

- **C1** A dispatched `/loop-design` answers Q1 below as a decision in this file and changes nothing outside
  `docs/loops/sandbox/` (per command-center/D61). Prove: the session's diff, on staging/runner.

## Design

### Where we are

- The question below exists only to be answered. Its answer changes nothing in the system.

## Decisions

| # | Decision | Decided by, date | Closes |
| --- | --- | --- | --- |

## Questions

| # | Question | Blocks | Default if unanswered |
| --- | --- | --- | --- |
| Q1 | Which greeting does the sandbox's example print? | C1 | `hello` |

**Q1 options**
- **hello**: the shortest, and the one `build-target` already writes. (recommended)
- **hi**: shorter still, and differs from `build-target`, so a mix-up shows.

## Evidence

## Shipped
