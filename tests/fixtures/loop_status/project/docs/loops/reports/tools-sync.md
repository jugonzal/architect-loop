---
needs: []
touches: [example/tools:sync/]
effects: []
ships-to: main
prs: [example/tools#11]
---
# The tools repository syncs report templates

Row: done, by the rule for a pull request merged in another repository (command-center/D19): example/tools#11
counts as merged because its merge commit is on that repository's main, and for ships-to main that main serves it.
C1 holds by CI on main. It already has a Shipped note.

## Done when

- **C1** A template changed in the tools repository reaches the reports. Prove: the sync tests, in CI on main.

## Decisions

| # | Decision | Decided by, date | Closes |
| --- | --- | --- | --- |

## Questions

| # | Question | Blocks | Default if unanswered |
| --- | --- | --- | --- |

## Evidence

## Shipped

2026-10-20, to `main`, in example/tools#11.
