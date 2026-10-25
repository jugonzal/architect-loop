---
needs: [command-center/D58, command-center/D62]
touches: [docs/loops/sandbox/gated-target.md]
effects: [a sandbox-only action that waits on the second person (gates: sandbox)]
ships-to: main
---
# A card for a gate only the sandbox crosses reaches the second person's inbox, not the owner's

## Done when

- **C1** The effect above puts its card in the inbox of the gate's holder and not in the owner's. Prove: the app
  signed in as each of the two, on staging/app, against staging/status.
- ~~**C2** A third signed-in member of the loop sees the card and cannot act on it (per command-center/D10). Prove:
  the same app signed in as that member, on staging/app.~~ (deferred, per D1)

## Design

### Where we are

- Missing: `LOOP.md` §2 has no gate whose holder is not `jugonzal`. The key `sandbox` is chosen (per sandbox/D2)
  but undefined until a PR adds it to §2 and the owner merges it, and its holder waits on the loop README's Q1.
  Until then `addressing.py` reads the key as drift.
- Missing: the loop README has no `owner:` or `members:`, so nobody is a member to see the card (verified in
  `addressing.py`). It needs the second person's login once Q1 names it.

## Decisions

| # | Decision | Decided by, date | Closes |
| --- | --- | --- | --- |
| D1 | C2 is deferred: a third member is not named, and the loop has no `members:` yet. One claim remains until Q1 of the loop README is answered. | Juan, 2026-10-25 | Defers the third-member question |

## Questions

| # | Question | Blocks | Default if unanswered |
| --- | --- | --- | --- |

## Evidence

## Shipped
