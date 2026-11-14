---
needs: [app-shell, status-api]
touches: [app/src/app/(tabs)/loops/, app/src/features/loops/]
effects: []
ships-to: staging/app-android
---
# Anyone on the project can see every loop and concern with its state and the fact behind it

## Done when

- **C1** The Loops tab shows active loops first with their concerns' states, then the backlog one line each,
  then parked loops. Prove: app tests against the status fixtures, in CI on main.
- **C2** A concern page shows its contract (`needs`, `touches`, `effects`, `ships-to`), each claim with its
  latest verdict and the commit it cites, and its state with the fact that produced it. The states are exactly
  the derivation's (per D5). Prove: app tests against fixtures covering every state, in CI on main, and a device
  check against staging.

## Design

### Approach

Follow the Loops and Concern artboards (per D4). The concern page's state strip is redrawn with the derivation's
states, and "in review" or "proving" becomes the reason line under it (per D5). The batons and sessions sections
of the artboard are left out, and the concern-thread link at the bottom opens
`/threads/loops/[loop]/concerns/[concern]`, which `app-threads` serves (per D52).

## Decisions

| # | Decision | Decided by, date | Closes |
| --- | --- | --- | --- |

## Questions

| # | Question | Blocks | Default if unanswered |
| --- | --- | --- | --- |

## Evidence

- 2026-11-13 · C2 · HOLDS · rung 1 · staging/app-android @d45ed2a · Device check on the owner's Android phone with the preview APK, signed in against staging, during the G0 walkthrough; the installed build is taken to be the latest finished preview build, which the row serves (`served.sh`, d45ed2a). The owner's screenshot of `command-center/app-environments` at 23:36 UTC shows the state strip with exactly the derivation's eleven states (parked, contradicted, open, blocked, ready, building, merged, shipped, stale, done, unknown) and `shipped` marked, the fact that produced it ("staging/app-android serves its work, and C1 has no evidence"), its next step (`/loop-prove command-center/app-environments staging/app-android`), `main @0182b89` and the served commit @d45ed2a, which is what the terminal's board derived for it on 0182b89. The contract and the claims are below the fold of the screenshot; the owner reported the page shows the contract, the claims and the state

## Shipped
