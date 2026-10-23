---
needs: [app-shell, status-api]
touches: [app/src/app/(tabs)/environments/, app/src/features/environments/]
effects: []
ships-to: staging/app
---
# Anyone on the project can see what each environment serves, and what is merged but not shipped

## Done when

- **C1** The Environments tab shows one row for each environment in `LOOP.md` §3. Each row has the commit it
  serves, when that was read, and the concerns merged but not yet served. When the read failed, the row says
  `unknown` with the failure, and nothing is filled in from memory. Prove: app tests against fixtures with a
  known and an unknown environment, in CI on main, and a device check against staging.

## Design

### Approach

Follow the Environments artboard (per D4). The ship brief opens as the inbox's ship card, so this tab links to
it and does not duplicate it. The `local/<service>` rows name `localhost`, so the status service reads them as
`unknown` (per D53, D56), and the tab shows them that way. `staging/app` reads through `app-served` once it is
deployed (per D57).

## Decisions

| # | Decision | Decided by, date | Closes |
| --- | --- | --- | --- |

## Questions

| # | Question | Blocks | Default if unanswered |
| --- | --- | --- | --- |

## Evidence

## Shipped
