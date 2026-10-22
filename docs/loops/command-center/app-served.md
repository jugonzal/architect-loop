---
needs: [status-service]
touches: [services/status/status/apps.py, services/status/tests/test_apps.py, services/status/service.json, services/status/openapi.yaml]
effects: [an Expo robot account with read access to the app's builds and its token in staging's Secret Manager (the owner creates both; gates: identity, secrets), the staging/app row's served-commit command changed to the status service's URL (the owner merges it once the service serves it; gates: merge)]
ships-to: staging/status
---
# Anyone can read which commit an app channel's builds were made from, without an Expo login

## Done when

- **C1** `GET /apps/{channel}/version` on the status service answers `{"commit": "<sha>"}` when the channel's latest
  finished iOS and Android builds were both made from one commit, the rule in `app/src/shell/release/served.js`.
  Otherwise it answers 404 or 503, saying why, and never an older commit. Prove: tests against the same build-list
  fixtures as `served.test.ts`, in CI on main, then `sh scripts/gcp/served.sh` on the URL for a staging build
  whose commit is known, on staging/status.

## Design

### Where we are

- Verified 2026-10-22 (`LOOP.md` §3 and `app/src/shell/release/served.js` on main @e63f06b): the app rows run
  `eas build:list` piped through `served.js`, which needs an Expo login, and the status service may only GET a URL
  (D9). So neither agents nor the service can read what a channel serves, and no app concern could reach done
  (D57).

### Approach

Per D57, D9 and D56: a route in the status service reads EAS's build list with the Expo robot token from Secret
Manager, named in `services/status/service.json` (per D46), and applies `served.js`'s rule. Its tests use the same
fixtures as `served.test.ts`. It is unauthenticated, like `/version`, since it shows only a commit anyone can see
on the public repository (per D24, D32). It caches EAS's answer for at most 60 seconds. Once staging serves it, the
owner merges the row change, after which `/loop-status` and the status service read `staging/app` like any other
row.

It needs `status-service`, whose folder it shares. Rollback: redeploy the previous revision, and the row reads
`unknown` again.

## Decisions

| # | Decision | Decided by, date | Closes |
| --- | --- | --- | --- |

## Questions

| # | Question | Blocks | Default if unanswered |
| --- | --- | --- | --- |

## Evidence

## Shipped
