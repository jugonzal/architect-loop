---
needs: [one-repository, app-shell, status-api]
touches: [app/src/app/(tabs)/loops/, app/src/features/loops/]
effects: []
ships-to: production/app
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
of the artboard are left out, and the concern-thread link at the bottom opens `app-threads`.

## Decisions

| # | Decision | Decided by, date | Closes |
| --- | --- | --- | --- |

## Questions

| # | Question | Blocks | Default if unanswered |
| --- | --- | --- | --- |

## Evidence

## Shipped
