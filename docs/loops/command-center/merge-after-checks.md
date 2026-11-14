---
needs: []
touches: [plugin/skills/loop-status/SKILL.md, plugin/skills/loop-design/SKILL.md, plugin/skills/loop-prove/SKILL.md, plugin/skills/loop-ship/SKILL.md, tests/test_merge_after_checks.py]
effects: [a plugin release so that runner sessions and terminals run the new text (the owner releases it per command-center/D17; gates: release)]
ships-to: main
---
# A skill that may merge its loop-document PR waits for the PR's checks first

## Done when

- **C1** Each skill that may merge a loop-document PR under `LOOP.md` §2.1 (`loop-status`, `loop-design`,
  `loop-prove`, `loop-ship`) names the command that waits for the PR's checks, says to give it time to finish, and
  says not to end the turn before it answers (per command-center/D85). Prove: a test that reads each of the four
  skills and fails when one may merge and does not name the wait, in CI on main.

## Design

### Where we are

- **Verified** (staging/runner @ff82269, 2026-11-13, `app-inbox`'s C2 evidence): session b38044a ran `loop-status`'s
  record step at release v0.6.0, opened #148, saw that its checks had no result yet, and ended without merging. The
  checks finished 2 min 34 s after they started.
- **Verified** (`plugin/skills/` and `LOOP.md` §2.1 on main @2223d4a): `LOOP.md` lets an agent merge a
  loop-document PR when `check_loop_pr.sh` passes and "its checks pass". `loop-status` says to merge "if it passes
  and the PR's checks are green". `loop-design`, `loop-prove` and `loop-ship` name only `check_loop_pr.sh`. None
  of the four says how to wait for the checks.
- **Verified** (this repository's CI, PRs #139 to #149): a loop-document PR's checks take about two to three
  minutes, and they report nothing for the first seconds after the PR opens, so a look taken at once finds no
  checks at all.
- **Assumed:** a session follows the sentence. One staging run after the release shows it, as `app-inbox` C2's
  proof; the wording is the only lever this concern has.

### Approach

Per command-center/D85:

- **The text:** where each skill says to merge its loop-document PR, it says to run
  `gh pr checks <n> --watch` first, allowing it ten minutes, to run it again if it says no checks are reported yet,
  to merge only when every check passed, and otherwise to leave the PR for the owner and say which check failed.
- **The test:** `tests/test_merge_after_checks.py` finds each skill under `plugin/skills/` whose text allows it
  to merge under §2.1, and fails unless that skill names the wait command. A fifth skill that gains the right to
  merge is caught the same way.
- **The independence check** in `scripts/check.sh` is not touched: the text names `gh`, which the skills already
  use, and nothing from `app/` or `services/`.

Rollback: release the plugin again without the text. Nothing persists.

## Decisions

| # | Decision | Decided by, date | Closes |
| --- | --- | --- | --- |

## Questions

| # | Question | Blocks | Default if unanswered |
| --- | --- | --- | --- |

## Evidence

## Shipped
