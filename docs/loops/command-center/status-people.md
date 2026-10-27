---
needs: [addressed-to-people]
touches: [plugin/skills/loop-status/scripts/loop_status.py, plugin/skills/loop-status/scripts/addressing.py, tests/test_loop_status.py, tests/test_addressing.py, tests/fixtures/loop_status/, tests/fixtures/addressing/]
effects: [a plugin release so that terminals print the same fields (the owner releases it per D17; gates: release), staging/status redeployed so that it serves them (the owner deploys it; gates: deploy)]
ships-to: staging/status
---
# Each loop in the status document names its owner and members

## Done when

- **C1** Each loop in the document carries `owner`, the login in its front matter, else the one `LOOP.md` §1 gives
  (per D62), and null when neither is known, and `members`, the logins in its front matter, empty when it has none.
  The terminal's `--json` and the status service give the same fields from the same facts, and the document still
  validates against the schema. Prove: fixture tests over a loop with an `owner:` and `members:`, one with neither
  (so `LOOP.md`'s owner), one with neither and no owner in `LOOP.md` (null), and one whose `owner:` is not a login,
  in CI on main.
- **C2** The document staging/status serves names the owner of `command-center` and of `sandbox`, and the notifier
  accepts a registration from them. Prove: a read of `/projects/jugonzal/architect-loop/status` on staging/status
  (with the owner's credentials, or the notifier's identity), then one registration from the owner's login, on
  staging/notify, after both serve this concern's commit.

## Design

### Where we are

- **Verified** (`python3 plugin/skills/loop-status/scripts/loop_status.py --json` on main @cf7f3af, 2026-10-27):
  `command-center` and `sandbox` carry no `owner` or `members`, though `waits_on` on the one queue item reads
  `jugonzal`.
- **Verified** (`plugin/skills/loop-status/scripts/loop_status.py` lines 503, 504 and 746, and `addressing.py` lines
  130 to 143, on main @cf7f3af): the facts hold each loop's front-matter `owner` and `members`, and the addressing
  step resolves them into a map used to fill `waits_on` and `visible_to`. The loop objects the derivation prints
  never receive them. The schema (`status.schema.json`, `loop`) already allows both as optional.
- **Verified** (`services/notify/notify/notifier.py` `members()` on main @cf7f3af): the notifier reads
  `loop.owner` and `loop.members` and finds none, so every registration is refused (C1 CONTRADICTS on
  `notifications`, 2026-10-25).
- `services/status/status/derivation.py` imports `loop_status.py` from the repository's `plugin/` directory in its
  image, so the service gets the change at its next deploy and needs no edit of its own.
- Neither `addressed-to-people` nor `status-derivation` is being built, and both are done, so this concern's
  `touches` collide with no running work.

### Approach

Per command-center/D70, D62 and D15: where the derivation builds each loop object, it adds `owner` (the resolved
map's owner, which already applies the front matter, then `LOOP.md` §1's login, then null) and `members` (the
resolved logins). `status.schema.json` is not edited, since both fields are already in it (so `schema_version`
stays 1, per command-center/D1 of `status-api`). Fixture `expected.json` files gain the fields. A change to the
terminal's output reaches terminals only with a plugin release (per D17); the status service gets it with its next
deploy, which is the owner's. Rollback: redeploy the previous revision, which names no one.

## Decisions

| # | Decision | Decided by, date | Closes |
| --- | --- | --- | --- |

## Questions

| # | Question | Blocks | Default if unanswered |
| --- | --- | --- | --- |

## Evidence

## Shipped
