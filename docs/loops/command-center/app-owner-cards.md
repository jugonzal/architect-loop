---
needs: [owner-queue]
touches: [app/src/features/inbox/cards.tsx, app/src/features/inbox/__tests__/]
effects: [a staging app build so that the channel serves it (the owner builds and submits it per LOOP.md §3; gates: deploy)]
ships-to: staging/app-android
---
# The inbox shows a fact or a stuck concern as a read-only card

## Done when

- **C1** A `fact` item opens a read-only card. It shows which fact is missing, why it cannot be read, who can supply
  it, the concerns waiting on it, and the command to run once it is to hand (per D76). Prove: the inbox's screen
  tests, with a `fact` item in the fixture document, in CI on main. Then, on the staging app build, the owner opens
  the `staging/app-android` fact card and reads its concerns (per D80).
- **C2** A `stuck` item opens a read-only card. It shows the concern, its state, why nothing leads anywhere, and
  its next step (per D77). Every kind in the schema has a body, so no card is ever blank. Prove: the inbox's screen
  tests, with a `stuck` item and a check that walks every `QueueKind`, in CI on main. Then, on the staging app
  build, the owner opens a `stuck` card if the served queue has one. If it has none, this claim rests on CI.

## Design

### Where we are

- **Verified** (`app/src/features/inbox/cards.tsx` at main @41597ff):
  - `ItemBody` switches over the seven kinds of D34, with no default.
  - The read-only bodies (`ProofBody`, `ContradictionBody`, `RefusedPrBody`) show a title, the item's `why`, a card
    of facts and `Command`.
- **Assumed:** after `owner-queue`, `queue.ts` lists `fact` and `stuck` as read-only kinds with labels, and
  `status.gen.ts` types their details (per `owner-queue` D1). Check `queue.ts` and `status.gen.ts` on main before
  building.

### Approach

Per D76 and D77:
- Add `FactBody` and `StuckBody` beside the other read-only bodies, built from the same parts.
- Add a `default` to `ItemBody`'s switch that shows the item's title and `why`, so a kind added later never renders
  blank. TypeScript's exhaustiveness check still catches a missing case when the types are regenerated.
- The screen tests gain both kinds, and a test that renders each kind in `KIND_LABELS`.

Rollback: ship the previous staging build. Nothing is stored.

## Decisions

| # | Decision | Decided by, date | Closes |
| --- | --- | --- | --- |

## Questions

| # | Question | Blocks | Default if unanswered |
| --- | --- | --- | --- |

## Evidence

## Shipped
