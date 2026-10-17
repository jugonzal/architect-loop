---
name: loop-record
description: Retired in architect-loop 0.2 and replaced by loop-status. Use only when someone types /loop-record, to point them at the replacement.
license: MIT
metadata:
  author: architect-loop
  version: "0.2"
---

# loop-record (retired)

Generation 2 of the Architect Loop replaced numbered plan steps with concerns, and stopped writing status down.
This command is now:

- `/loop-status` derives every concern's state from git, pull requests, environments and evidence, so there are no Status lines left to update.
- Its record step, on your yes, writes Shipped notes, corrections and memory.

If this project still has generation 1 proposals in progress (a `**Status:**` line and `Step n` headings in
`docs/proposals/`), run `/loop-init` to upgrade it. This stub will be removed in the next release.
