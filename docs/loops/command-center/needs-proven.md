---
needs: []
touches: [plugin/skills/loop-status/SKILL.md, plugin/skills/loop-status/scripts/loop_status.py, tests/test_loop_status.py, tests/fixtures/loop_status/, plugin/skills/loop-plan/SKILL.md, plugin/skills/loop-plan/templates/concern.md]
effects: [a plugin release so that terminals and agents derive needs by the new rule (the owner releases it; gates: release)]
ships-to: main
---
# A concern waits on a need only until that need is proven on some environment

## Done when

- **C1** A concern that nothing has been built for yet is blocked while one of its needs is not met, and a need is
  met as D50 says. Its work is on `main`, and each of its claims has a HOLDS line on some `LOOP.md` §3
  environment, local included, at a commit on `main` with nothing under its `touches` changed since. A claim whose
  Prove names CI holds on `main` while CI is green. The terminal and a supplied facts document give the same
  answer. Prove: fixture tests in CI on main, with a need proven only on a local row, one proven only by CI on
  main, one proven on staging, one whose `touches` changed after its HOLDS, and one with a claim unproven.
- **C2** A blocked concern's reason names each unmet need, the claims of that need that have no current HOLDS
  anywhere, and the command that would prove one (`/loop-prove <loop>/<need> <environment>`). That command
  joins "agents can start now". Prove: fixture tests and a text-output test of the board, in CI on main.

## Design

### Where we are

- Verified 2026-10-22 (`plugin/skills/loop-status/SKILL.md` step 4 and `loop_status.py` on main @e63f06b): the
  table's blocked row says "a concern in `needs` is not done", and done means every claim holds on the need's own
  `ships-to`. With every service and app row unreadable today, that leaves nothing ready (README, Where we are).
- Verified 2026-10-22 (`loop_status.py` on main @e63f06b): the script already reads every evidence line with its
  environment and commit, and asks git which paths changed between two commits. So the rule needs no new facts,
  only a new answer for the blocked row.
- Verified 2026-10-22 (`plugin/skills/loop-plan/templates/concern.md`, line 16): the template says `needs` is "what
  this concern needs first". It does not say what makes a need met, or that what only a concern's proofs rely on
  is not a need (D51).

### Approach

Per D50 and D51: the blocked row in the skill's table, and its definitions, state the rule. `loop_status.py`
implements it as `need_met(need)`, from the evidence lines and the CI state already in the facts document, so
nothing is read live and the status service gets the same answer from its own facts (per D15, `status-derivation`
C3). A need's state never changes because of the environment the consumer ships to. The `loop-plan` skill and its
concern template say what `needs` lists (D50, D51). Done keeps its meaning: every claim holds on the concern's own
`ships-to` (per D54).

This concern goes first. `addressed-to-people` changes the same script and skill, so it needs this one. Until a
release carries this change, agents run the installed release and see the old rule (per D17).

Rollback: revert the PR. Needs then read by the old rule again, and no data is written.

## Decisions

| # | Decision | Decided by, date | Closes |
| --- | --- | --- | --- |

## Questions

| # | Question | Blocks | Default if unanswered |
| --- | --- | --- | --- |

## Evidence

## Shipped
