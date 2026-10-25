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
- **C2** A third signed-in member of the loop sees the card and cannot act on it (per command-center/D10). Prove:
  the same app signed in as that member, on staging/app.

## Design

### Where we are

- Missing: `LOOP.md` §2 has no gate whose holder is not `jugonzal`, so the key `sandbox` is undefined until Q2 of
  the loop README is answered and the owner merges it. Until then `addressing.py` reads it as drift.

## Decisions

| # | Decision | Decided by, date | Closes |
| --- | --- | --- | --- |

## Questions

| # | Question | Blocks | Default if unanswered |
| --- | --- | --- | --- |

## Evidence

## Shipped
