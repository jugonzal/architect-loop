---
needs: [one-repository, status-derivation, status-api, queue-items, environments, question-options]
touches: [plugin/skills/loop-status/scripts/addressing.py, plugin/skills/loop-status/SKILL.md, plugin/skills/loop-plan/templates/loop.md, plugin/skills/loop-init/templates/LOOP.md, tests/test_addressing.py, LOOP.md]
effects: [gate-holder names added to LOOP.md §2 (a change to the contract; the owner merges it), a plugin release so that terminals pick the change up (the owner releases, per D17)]
ships-to: main
---
# Every "needs you" item waits on one named person, the loop owner or the gate holder for its gate

## Done when

- **C1** Each queue item names exactly one person in `waits_on`. That is the gate holder from `LOOP.md` §2 when
  the item crosses a gate, and otherwise the loop's `owner:`. A loop with no `owner:` falls back to `LOOP.md`'s
  owner. Prove: fixture tests over loops with and without an owner and with gated and ungated effects, in CI on main.
- **C2** Each queue item lists the loop's `members:` in `visible_to`, and they can see the item but not act on it
  (per D10). The terminal board shows who each item waits on. Prove: fixture tests and a text-output test, in CI on main.

## Design

### Where we are

- No loop README has `owner:` or `members:`, and `LOOP.md` §2 names no gate holders (template read 2026-10-20).
- Terminals see the change after the next plugin release (per D17).
- Corrected 2026-10-20: `touches` lacked `LOOP.md`, though `effects` adds gate holders to its §2.
  `environments` also edits `LOOP.md`, and `question-options` edits `plugin/skills/loop-plan/templates/loop.md`,
  so both are now in `needs`, which keeps any two of them from being built at once.

### Approach

Per D10 and D15: the loop README's front matter gains `owner:` (one person, the architect) and `members:` (a
list). Each gate line in `LOOP.md` §2 gains `— holder: <name>`. `addressing.py` maps the derived queue onto
people and fills `waits_on` and `visible_to` in the `status-api` document, routing an item to its gate's holder
by the item's `gate` (per D38). Delegation, where the owner hands an
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
