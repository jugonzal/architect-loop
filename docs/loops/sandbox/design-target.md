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
- Verified (main @e4a2b1e, 2026-11-14): `sandbox/` does not exist on `main`, so no example prints anything yet.
  `build-target` C1 writes `hello` on a branch that is never merged (per sandbox/D3).

### Approach

- The sandbox's example prints `hello`, the same greeting `build-target` writes (per D1). Nothing is built.

## Decisions

| # | Decision | Decided by, date | Closes |
| --- | --- | --- | --- |
| D1 | The sandbox's example prints `hello`. | Juan, 2026-11-14 | Q1 |

## Questions

| # | Question | Blocks | Default if unanswered |
| --- | --- | --- | --- |
| ~~Q1~~ | ~~Which greeting does the sandbox's example print?~~ → D1 | | |

**Q1 options**
- **hello**: the shortest, and the one `build-target` already writes. (recommended)
- **hi**: shorter still, and differs from `build-target`, so a mix-up shows.

## Evidence

## Shipped
