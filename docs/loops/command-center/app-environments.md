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

2026-11-13, to `staging/app-android`, its `ships-to`, in the preview Android build that serves d45ed2a.

- **What shipped.** PR #38 (merge 3161cca, built and merged 2026-10-23) added the Environments tab: one card for each
  environment the status document lists, with the commit it serves, when it was read, and the concerns merged but
  not served there. An environment that could not be read shows as UNKNOWN with the failure and when it was tried,
  and no served commit. C1 was proven by the app tests in CI (rung 5, @d10c48f) before the merge. The device check
  of 2026-11-13 on the preview build made it done.
- **Departures from the design.**
  - It was built against `staging/app` and its device check was left UNPROVEN in the PR. The row it ships to is now
    `staging/app-android`, where the check was made.
  - The ship brief is not drawn on this tab. The "Read the ship brief" button opens Needs you, as the Approach says.
- **Learned.** The device check covered four of the sixteen rows: `local/threads` and `local/notify` as UNKNOWN,
  `main`, and `staging/status`. No row with a merged, unserved concern existed, so a card listing merged work was
  shown only by the fixtures in the tests, never on a device. The first time a concern is merged and unserved,
  look at its card.
