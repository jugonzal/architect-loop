---
name: loop-decide
description: Retired in architect-loop 0.2 and replaced by loop-design. Use only when someone types /loop-decide, to point them at the replacement.
license: MIT
metadata:
  author: architect-loop
  version: "0.2"
---

# loop-decide (retired)

Generation 2 of the Architect Loop replaced numbered plan steps with concerns, and stopped writing status down.
This command is now:

- `/loop-design <loop>` or `/loop-design <loop>/<concern>` asks the open questions one at a time, with options and a recommendation, and records each decision where it belongs.
- `/loop-status` gathers every open question across all loops in its "Needs you" list.

If this project still has generation 1 proposals in progress (a `**Status:**` line and `Step n` headings in
`docs/proposals/`), run `/loop-init` to upgrade it. This stub will be removed in the next release.
