---
needs: [needs-proven, status-derivation, status-api, queue-items]
touches: [plugin/skills/loop-status/scripts/addressing.py, plugin/skills/loop-status/scripts/loop_status.py, plugin/skills/loop-status/scripts/questions.py, plugin/skills/loop-status/SKILL.md, plugin/skills/loop-plan/templates/loop.md, plugin/skills/loop-plan/templates/concern.md, plugin/skills/loop-init/templates/LOOP.md, tests/test_addressing.py, tests/fixtures/addressing/]
effects: [each gate's key and holder written into this repository's LOOP.md §2 (the owner names the holders and merges it; gates: merge), a plugin release so that terminals pick the change up (the owner releases it per D17; gates: release)]
ships-to: main
---
# Every "needs you" item waits on one named person, the loop owner or the gate holder for its gate

## Done when

- **C1** Each queue item names exactly one person in `waits_on`. That is the gate holder from `LOOP.md` §2 when
  the item crosses a gate, and otherwise the loop's `owner:`. A loop with no `owner:` falls back to `LOOP.md`'s
  owner. Prove: fixture tests over loops with and without an owner and with gated and ungated effects, in CI on main.
- **C2** Each queue item lists the loop's `members:` in `visible_to`, and they can see the item but not act on it
  (per D10). The terminal board shows who each item waits on. Prove: fixture tests and a text-output test, in CI on main.
- **C3** Each queue item's `gate` comes from the keys of D58 (per D38). A review item crosses `merge`. A ship item
  is split into one item for each key its concern's effects carry other than `merge`, with that gate's manual
  steps, plus one for `deploy` (per D59). A question item crosses the key its row names, if any (per D60). An
  effect or question naming a key that `LOOP.md` §2 does not define is drift. Prove: fixture tests over effects
  with no key, one key, two keys held by different people and an unknown key, in CI on main.

## Design

### Where we are

- No loop README has `owner:` or `members:`, and `LOOP.md` §2 names no gate holders (template read 2026-10-20).
- Terminals see the change after the next plugin release (per D17).
- Corrected 2026-10-20: `touches` lacked `LOOP.md`, though `effects` adds gate holders to its §2.
  `environments` also edits `LOOP.md`, and `question-options` edits `plugin/skills/loop-plan/templates/loop.md`,
  so both are now in `needs`, which keeps any two of them from being built at once.
- Corrected 2026-10-20 (main @a9fde89): `environments` and `question-options` are on `main` (PRs #19 and #18), so
  they leave `needs` (per D42). `app-shell` joins it, because it adds the app's rows to `LOOP.md` §3 (its C3, per
  D43), so the two must not be built at once.
- Verified 2026-10-22 (`loop_status.py` on main @e63f06b): the script writes every queue item with `gate: null`,
  `waits_on: null` and `visible_to: []`, and nothing derives a gate. So this concern also changes the script,
  which calls `addressing.py` the way it calls `questions.py`, and `questions.py`, which reads a question's key
  (per D60). (Corrected 2026-10-22: `touches` lacked both.)
- Corrected 2026-10-22 (per D58): `LOOP.md` leaves `touches`. Naming each gate's holder is the owner's, so it is an
  effect, and this concern and `local-harness`, which adds rows to §3, can be built at once. `app-shell` is on
  `main`, so it leaves `needs`. `needs-proven` joins, because both concerns change `loop_status.py` and the
  skill's table.

### Approach

Per D10, D15 and D58 to D60: the loop README's front matter gains `owner:` (one person, the architect) and
`members:` (a list). Each gate line in `LOOP.md` §2 gains its key and holder, for example
`- **Spending** (key: spending; holder: jugonzal): ...`, and the `loop-init` template shows the form with the
thirteen keys of D58. The `loop-plan` concern template says an effect is one phrase without bare commas, ending in
`(...; gates: <key>, <key>)`. `addressing.py` reads the keys and holders from §2, derives each item's gate by D59
and D60, and fills `gate`, `waits_on` and `visible_to` in the `status-api` document, routing an item to its gate's
holder (per D38). `loop_status.py` calls it after building the queue, so the terminal and the status service
address items the same way. Delegation, where the owner hands an
item to a member, is out of this loop. When it comes, it will be a decision recorded as
`<name>, delegated by <owner>`.

## Decisions

| # | Decision | Decided by, date | Closes |
| --- | --- | --- | --- |

## Questions

| # | Question | Blocks | Default if unanswered |
| --- | --- | --- | --- |

## Evidence

## Shipped
