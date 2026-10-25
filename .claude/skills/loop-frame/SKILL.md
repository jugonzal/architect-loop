---
name: loop-frame
description: Retired in architect-loop 0.2 and replaced by loop-plan and loop-design. Use only when someone types /loop-frame, to point them at the replacement.
license: MIT
metadata:
  author: architect-loop
  version: "0.2"
---

# loop-frame (retired)

Generation 2 of the Architect Loop replaced numbered plan steps with concerns, and stopped writing status down.
This command is now:

- `/loop-plan <intent>` adds a loop to the backlog: its goals, a first cut of independent concerns, and how it relates to the loops already tracked.
- `/loop-design <loop>` works out how it will be built, grilling you on open decisions and new constraints.

If this project still has generation 1 proposals in progress (a `**Status:**` line and `Step n` headings in
`docs/proposals/`), run `/loop-init` to upgrade it. This stub will be removed in the next release.
