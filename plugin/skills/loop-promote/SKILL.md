---
name: loop-promote
description: Retired in architect-loop 0.2 and replaced by loop-ship. Use only when someone types /loop-promote, to point them at the replacement.
license: MIT
metadata:
  author: architect-loop
  version: "0.2"
---

# loop-promote (retired)

Generation 2 of the Architect Loop replaced numbered plan steps with concerns, and stopped writing status down.
This command is now:

- `/loop-ship <env>` writes the brief for every merged concern the environment does not serve yet, stops for you, and verifies what the environment serves afterwards.

If this project still has generation 1 proposals in progress (a `**Status:**` line and `Step n` headings in
`docs/proposals/`), run `/loop-init` to upgrade it. This stub will be removed in the next release.
