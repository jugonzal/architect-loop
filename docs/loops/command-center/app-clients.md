---
needs: [app-shell, runner-dispatch, threads]
touches: [app/package.json, app/src/api/, app/src/shell/config.ts, app/src/shell/__tests__/config.test.ts, app/eas.json]
effects: []
ships-to: staging/app
---
# The app has one typed client for each service it calls, and knows each service's URL

## Done when

- **C1** `app/src/api/` holds clients for the runner and threads, generated from `services/runner/openapi.yaml` and
  `services/threads/openapi.yaml` and called through the signed-in fetch. A check fails when either no longer
  matches its file, as `check:status` does for the status types (per D55). Prove: the app's tests and the check,
  in CI on main.
- **C2** The app's config reads the runner's, threads' and the notifier's URLs per build profile, as it reads the
  status service's. A build without one says so instead of calling it. `app/eas.json`'s staging profile names
  staging's URLs (project number 665570365697). Prove: config tests, in CI on main.

## Design

### Where we are

- Verified 2026-10-22 (`app/src/api/` and `app/package.json` on main @e63f06b): the status client's types are
  generated from the status schema by `generate-status-types.js` with `json-schema-to-typescript`, and checked by
  `check:status` and a test beside it. There is no OpenAPI generator.
- Verified 2026-10-22 (`app/src/shell/config.ts`, `app/eas.json`): config knows only `EXPO_PUBLIC_STATUS_URL`, and
  both profiles' values are `TODO(owner)`.
- Verified 2026-10-22 (`services/runner/openapi.yaml` 0.2.0 and `services/threads/openapi.yaml` on main): both are
  OpenAPI 3.1 files in YAML, checked against their services by `runner-dispatch` C2 and `threads` C1.

### Approach

Per D55 and D29's first half: the generator and its check follow the status types' pattern, a plain Node script
under `app/src/api/` that `package.json` runs. Generated files are committed, and a test fails when they drift. The
runner's and threads' clients take their base URL from config and their token from the signed-in fetch, so a
screen only calls them. The URLs follow `https://<service>-<project number>.us-east1.run.app` (per D32). Staging's
are filled in now; production stays `TODO(owner)` (per D54). `notifications` generates its own client with the same
generator, once its API exists.

It needs `app-shell`, `runner-dispatch` and `threads`, whose files and APIs it builds on. All three meet D50 by CI
on main (`app-shell` D2, `threads` D7). `app-agents`, `app-inbox`, `app-threads` and `notifications` need this
concern. It ships to `staging/app`, like the rest of the app (per D54). Its claims are proven in CI, and that is
what meets D50 for the screens that need it.

Rollback: revert the PR. No screen calls these clients yet.

## Decisions

| # | Decision | Decided by, date | Closes |
| --- | --- | --- | --- |

## Questions

| # | Question | Blocks | Default if unanswered |
| --- | --- | --- | --- |

## Evidence

## Shipped
