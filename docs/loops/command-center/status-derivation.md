---
needs: [one-repository, status-api, queue-items, question-options]
touches: [plugin/skills/loop-status/scripts/loop_status.py, plugin/skills/loop-status/SKILL.md, tests/test_loop_status.py, tests/fixtures/loop_status/]
effects: []
ships-to: main
---
# The loop-status derivation runs as one deterministic script that the terminal and the service share

## Done when

- **C1** Given the same facts, the script derives the same state for every concern and loop as the derivation
  table in `loop-status` SKILL.md steps 3 to 5, including `unknown`. Prove: fixture tests with one case per table
  row and per definition (serves, current HOLDS, `@?`, unknown), in CI on main.
- **C2** Its `--json` output validates against the status schema, and every concern's state carries its reason
  and the facts it came from (main SHA, served commit or the failure, linked PRs and commits). Prove: tests
  validating every fixture's output, in CI on main.
- **C3** Gathering facts is separate from deriving state. The terminal gathers with git, `gh` and the
  served-commit commands, while a caller may supply its own facts document. The status service does this,
  reading served commits over HTTP (per D9). The same facts give the same output either way. Prove: a test
  that derives from gathered and from supplied facts and compares them, in CI on main.

## Design

### Where we are

- The derivation is prose only (`plugin/skills/loop-status/SKILL.md`, steps 1 to 6, read 2026-10-20). (Path
  corrected 2026-10-20 for the move.)
- Verified 2026-10-20 (`one-repository` C3's evidence): the table has no rule for a pull request merged in
  another repository, and runs of the 0.2.0 skill on the same facts returned different boards.
- The skills' scripts use only the Python 3 standard library (`migrate_gen1.py` imports argparse, subprocess, re,
  dataclasses and similar) and are tested with `python3 -m unittest` (`scripts/check.sh`). This script follows
  both conventions.

### Approach

Per D15: `loop_status.py gather` writes a facts document; `loop_status.py derive --facts <file>` is a pure
function from facts to the status document of `status-api` (per D15); `loop_status.py` with no subcommand does
both, and prints the board in the skill's existing text format or, with `--json`, the document. The skill's
steps 1 to 6 say to run the script and keep the table as its specification, and the skill's note stays: if two
runs disagree, fix the table, then the script. Addressing (who an item waits on) is not part of this concern; it
comes with `addressed-to-people`.

The queue carries all seven kinds of item that step 6 lists (per D34), each with the gate it crosses or null
(per D38). Step 5 of the table gains a loop state `unknown`, for a loop whose state rests on a fact that could not
be read (per D37). A question item takes its options and
recommendation from the reader that `question-options` adds beside this script, so the format has one parser
(per D33).

Before the script implements the table, the table gains D19's rule: a pull request merged in another repository
counts as merged when its merge commit is on that repository's main. C1's fixtures get a row for it (per D19).

## Decisions

| # | Decision | Decided by, date | Closes |
| --- | --- | --- | --- |

## Questions

| # | Question | Blocks | Default if unanswered |
| --- | --- | --- | --- |

## Evidence

## Shipped
