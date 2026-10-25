---
name: loop-reconcile
description: Retired in architect-loop 0.2 and replaced by loop-status. Use only when someone types /loop-reconcile, to point them at the replacement.
license: MIT
metadata:
  author: architect-loop
  version: "0.2"
---

# loop-reconcile (retired)

Generation 2 of the Architect Loop replaced numbered plan steps with concerns, and stopped writing status down.
This command is now:

- `/loop-status` checks loop documents against the facts every time it runs.
- `/loop-status audit` checks runbooks, memory and other documents, as this skill used to.

If this project still has generation 1 proposals in progress (a `**Status:**` line and `Step n` headings in
`docs/proposals/`), run `/loop-init` to upgrade it. This stub will be removed in the next release.
