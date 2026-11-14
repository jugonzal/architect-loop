---
needs: [app-shell, status-api]
touches: [app/src/app/(tabs)/environments/, app/src/features/environments/]
effects: []
ships-to: staging/app-android
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

- 2026-11-13 · C1 · HOLDS · rung 1 · staging/app-android @d45ed2a · Device check on the owner's Android phone with the preview APK, signed in against staging, during the G0 walkthrough; the installed build is taken to be the latest finished preview build, which the row serves (`served.sh`, d45ed2a). The owner's screenshot of the Environments tab at 23:37 UTC shows `local/threads` and `local/notify` as UNKNOWN, each with "Its served commit could not be read, so nothing is filled in from memory", the failure (`GET http://localhost:8703/version failed: [Errno 111] Connection refused`, and 8704) and "Tried 9 min ago"; `main` serving @0182b89, "read 9 min ago", "Nothing merged is waiting for it"; and `staging/status` serving @fb3569f with the same line. Those match what the rows served then: `git rev-parse origin/main` gave 0182b89 and `served.sh` on staging/status gave fb3569f at 23:25 UTC, and the terminal's board had no concern merged and unserved. The screenshot covers four of the sixteen rows; for the rest the owner reported the tab good, and no row with a merged, unserved concern existed to be shown

## Shipped
