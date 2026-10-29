---
needs: [app-shell, runner-dispatch, threads]
touches: [app/package.json, app/src/api/, app/src/shell/config.ts, app/src/shell/__tests__/config.test.ts, app/src/shell/__tests__/shell.test.tsx, app/src/shell/release/__tests__/served.test.ts, app/src/features/environments/__tests__/route.test.tsx, app/src/features/loops/__tests__/screens.test.tsx, app/eas.json]
effects: []
ships-to: staging/app-android
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
- Verified 2026-10-23 (main @19444a4): `app/src/shell/release/__tests__/served.test.ts`, line 117, "puts no secret
  in a build profile" by allowing only `EXPO_PUBLIC_ENVIRONMENT`, `EXPO_PUBLIC_GITHUB_CLIENT_ID`,
  `EXPO_PUBLIC_STATUS_URL` and `EXPO_PUBLIC_PROJECT`, so C2's three new URLs fail it.
  `app/src/shell/__tests__/shell.test.tsx` builds a whole `AppConfig`, whose `statusUrl` is `string | null`. Both
  files are `app-shell`'s, which is on `main`, and no other open concern touches them. (Found by this concern's
  first build, which stopped there.) (Corrected 2026-10-23: two more files build a whole `AppConfig`,
  `app/src/features/environments/__tests__/route.test.tsx` and `app/src/features/loops/__tests__/screens.test.tsx`,
  from PRs #38 and #39, which were on `main` when this was written. This bullet missed them, and the second build
  stopped on them, checked with `git grep -w AppConfig origin/main -- app/src`. They are `app-environments`' and
  `app-loops-board`'s, both on `main`, and no other open concern touches them. D2 adds them.)

### Approach

Per D55 and D29's first half: the generator and its check follow the status types' pattern, a plain Node script
under `app/src/api/` that `package.json` runs. Generated files are committed, and a test fails when they drift. The
runner's and threads' clients take their base URL from config and their token from the signed-in fetch, so a screen
only calls them. The URLs follow `https://<service>-<project number>.us-east1.run.app` (per D32). Staging's are
filled in now; production stays `TODO(owner)` (per D54). The three URLs are `string | null` in `AppConfig`, like
`statusUrl`, and `served.test.ts`'s list of public variables gains their names (per D1). Every test that builds a
whole `AppConfig` gains the three URLs as `null` (per D2). `notifications` generates its own client with the same
generator, once its API exists.

It needs `app-shell`, `runner-dispatch` and `threads`, whose files and APIs it builds on. All three meet D50 by CI
on main (`app-shell` D2, `threads` D7). `app-agents`, `app-inbox`, `app-threads` and `notifications` need this
concern. It ships to `staging/app-android`, like the rest of the app (per D54, D80). Its claims are proven in CI, and that is
what meets D50 for the screens that need it.

Rollback: revert the PR. No screen calls these clients yet.

## Decisions

| # | Decision | Decided by, date | Closes |
| --- | --- | --- | --- |
| D1 | `touches` gains `app/src/shell/release/__tests__/served.test.ts`, whose no-secret test lists the public variables a build profile may hold, and `app/src/shell/__tests__/shell.test.tsx`, which builds a whole `AppConfig`. The runner's, threads' and the notifier's URLs are `string | null` in `AppConfig`, like `statusUrl`, so typecheck catches a config that leaves one out. | Juan, 2026-10-23 | Closes Q1 |
| D2 | `touches` also gains `app/src/features/environments/__tests__/route.test.tsx` and `app/src/features/loops/__tests__/screens.test.tsx`, which build a whole `AppConfig` too, so D1's required URLs hold there as well. Each gains the three URLs as `null`. | Juan, 2026-10-23 | Closes Q2 |

## Questions

| # | Question | Blocks | Default if unanswered |
| --- | --- | --- | --- |
| ~~Q1~~ | ~~Which paths join `touches`, now that C2's URLs break `served.test.ts`? (raised by the first build)~~ → D1 | | |
| ~~Q2~~ | ~~How is D1 met, now that two screens' tests also build a whole `AppConfig`? (raised by the second build)~~ → D2 | | |

**Q1 options**
- **Both tests**: the URLs are `string | null` like `statusUrl`, so typecheck catches a config that forgets one.
  (recommended)
- **`served.test.ts` only**: the URL fields stay optional; a missing one is caught only at runtime.

**Q2 options**
- **Widen `touches`**: both tests gain three `null` URLs, D1 stands, and typecheck catches a config that leaves
  one out. (recommended)
- **Revise D1 to optional**: PR #40 can be marked ready at once, but a missing URL is caught only at runtime.

## Evidence

## Shipped
