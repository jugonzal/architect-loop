---
needs: [status-api, queue-items]
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
  corrected 2026-10-20 for the move.) (Superseded 2026-10-22, main @18b866b: PR #27 (964d370) made it
  `loop_status.py`; see Shipped.)
- Verified 2026-10-20 (`one-repository` C3's evidence): the table has no rule for a pull request merged in
  another repository, and runs of the 0.2.0 skill on the same facts returned different boards. (Superseded
  2026-10-22: step 3 of the table has D19's rule since PR #27.)
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
(per D33). That reader, `plugin/skills/loop-status/scripts/questions.py`, is on `main` since PR #18, so this
concern no longer waits for `question-options` (per D42). A concern's `ships-to` names a `LOOP.md` §3 row, such as
`production/runner` (per D43), and the script looks the row up by that name.

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

2026-10-21, to `main`, its `ships-to`. Terminals have it since release v0.4.0 (18b866b).

- **What shipped.** PR #27 (merge 964d370) added `plugin/skills/loop-status/scripts/loop_status.py`, standard
  library only. `gather` writes a facts document, `derive --facts` is a pure function of it, and with no
  subcommand it prints the board or, with `--json`, the status document. Git's answers (ancestry, changes under
  `touches`, merge bases) go into the facts round by round (`pending_queries`), so a caller without git, like the
  status service (per D9), can supply complete facts. It reads the loop documents from main's commit, never the
  working tree, and imports `questions.py` rather than parsing questions again (per D33, D41). The skill's steps 1
  to 6 now run it, with the table as its specification. The table gained D19's rule, and step 5 the loop state
  `unknown` (per D37). `tests/test_loop_status.py` added 44 tests: one case per table row and definition, a
  fixture world holding every state, and that world both gathered from a real repository with a fake `gh` and
  supplied as facts, with identical output.
- **Departures from the design.** Every queue item's `gate` is null. D38 gave no rule for mapping an effect to a
  gate, so the build stopped there. D58 to D60 now give one, and `addressed-to-people` builds it. `waits_on` and
  `visible_to` stay empty as designed. Where the table is silent, the script reads it eight ways, listed in PR
  #27's body. For example, a claim that held and went stale counts toward `stale`, not `shipped`. A PR closed
  unmerged is not linked work. A PR merged into another branch, with nothing left open, reads `unknown`. None of
  the eight is a recorded decision yet. Since then PR #32 (6894ad2) changed the blocked row for D50
  (`needs-proven`).
- **Learned.** The script's first run on this repository disagreed with the table read by hand on one concern.
  `one-repository` was stale, not done, because its `touches` cover most of the repository. Under the table it
  then blocked every concern that needed it. That led to D49, and, with every staging and app row unreadable
  leaving nothing ready, to D50. A derivation in code turns readings that used to differ between runs into rules
  that someone must choose. That is why the eight readings belong in `/loop-design`, not in the script alone.
