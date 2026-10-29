---
needs: [status-callers]
touches: [services/status/status/apps.py, services/status/status/app.py, services/status/status/config.py, services/status/tests/test_apps.py, services/status/tests/test_config.py, services/status/tests/support.py, services/status/service.json, services/status/openapi.yaml, services/status/README.md, LOOP.md, app/src/shell/release/__tests__/served.test.ts]
effects: [an Expo robot account with read access to the app's builds and its token in staging's Secret Manager (the owner creates both; gates: identity, secrets), staging/status redeployed so that it serves the route (the owner deploys it; gates: deploy), the staging/app-android and staging/app-ios rows made readable on the status service's URLs and the staging/app row removed once the app's concerns ship to staging/app-android (the owner merges it once the service serves the route; gates: merge)]
ships-to: staging/status
---
# Anyone can read which commit each app platform's builds were made from, without an Expo login

## Done when

- **C1** `GET /apps/{channel}/{platform}/version` on the status service answers `{"commit": "<sha>"}` with the
  commit that the platform's latest finished build of the channel's profile was made from (per D79). It answers
  404 when the platform has no finished build, or its latest one records no commit, and 503 when EAS cannot be
  read, saying why each time. It never answers an older commit. Prove: tests against the build-list fixtures of
  `served.test.ts`, in CI on main. Then, on staging/status, `sh scripts/gcp/served.sh` on
  `/apps/staging/android/version` must print the commit of a staging Android build whose commit is known.
- **C2** LOOP.md §3 has `staging/app-android` and `staging/app-ios` rows, each built with its platform's
  `eas build --profile staging --platform <platform>`, and app CI checks them as it checks the app rows today (per
  D79). Prove: `served.test.ts` in CI on main.

## Design

### Where we are

- Verified 2026-10-22 (`LOOP.md` §3 and `app/src/shell/release/served.js` on main @e63f06b): the app rows run
  `eas build:list` piped through `served.js`, which needs an Expo login, and the status service may only GET a URL
  (D9). So neither agents nor the service can read what a channel serves, and no app concern could reach done
  (D57).
- **Verified** (`served.js` on main @69617a2, 2026-10-28):
  - A channel serves a commit only when its latest finished iOS and Android builds were both made from it.
  - The owner builds staging for Android. With no iOS build, or one made from another commit, a both-platforms
    route would answer 404 for good, and `staging/app` would never read. D79 replaces that rule for the route.
  - `served.js` keeps its rule for `production/app` until production's loop splits it.
- **Verified** (`app/src/shell/release/__tests__/served.test.ts`): app CI pins the `staging/app` and
  `production/app` rows to their `eas build:list … served.js <profile>` commands. It also requires `eas.json`'s
  `EXPO_PUBLIC_ENVIRONMENT` to name a row. So a row change in LOOP.md fails app CI unless this test changes in the
  same PR, and both paths are in `touches` (per D79).
- **Verified** (`app/src/shell/ShellHeader.tsx`): `EXPO_PUBLIC_ENVIRONMENT` is used only to show "staging" in the
  header. The profile is shared by both platforms, so it keeps naming the channel, `staging/app`.
- **Verified** (eas-cli 22.4.0, the version `eas build:list` runs here, read 2026-10-28: `build/api.js`,
  `build/commandUtils/context/contextUtils/createGraphqlClient.js`, `build/graphql/queries/BuildQuery.js`,
  `build/graphql/types/Build.js`):
  - The build list is `POST https://api.expo.dev/graphql`, sent with `authorization: Bearer <token>`. Its query is
    `app { byId(appId) { builds(offset, limit, filter: {platform, status, buildProfile}) } }`.
  - Each build carries `platform` (`ANDROID`, `IOS`), `status` (`FINISHED` among others), `buildProfile`,
    `gitCommitHash`, `createdAt` and `completedAt`.
  - The app's EAS project id is `extra.eas.projectId` in `app/app.json`.
- **Verified** (<https://docs.expo.dev/accounts/programmatic-access/>, read 2026-10-28): robot users authenticate
  only by access token and can be given a role. The page does not say which role reads builds, so the owner picks
  the least that does.
- **Missing** (`owner-queue`, at 363ed2a): a readable row whose GET keeps failing, for example a 404 because no
  build exists, counts as a transient read failure. The concerns resting on it are left out of Needs you. This
  route answers 404 until each platform's first finished staging build, so a row made readable too early hides its
  concerns. That is why the effect makes the rows readable only once the route serves Android.

### Approach

Per D57, D79, D9 and D56:

- **The route.** It reads EAS's build list with the Expo robot token from Secret Manager, named in
  `services/status/service.json` (per D46).
  - It answers each platform on its own: the newest finished build of the channel's profile on that platform.
  - Its tests use the build-list fixtures of `served.test.ts`.
  - It is unauthenticated, like `/version`, since it shows only a commit anyone can see on the public repository
    (per D24, D32).
  - It caches EAS's answer for at most 60 seconds.
- **LOOP.md, in the build PR.**
  - It adds the `staging/app-android` and `staging/app-ios` rows, below `staging/app`. Their served-commit commands
    stay `TODO(owner)`, with the URL each will read.
  - It keeps `staging/app`, so the ten app concerns still name a row until D80's `/loop-design` PR moves them.
  - `served.test.ts` checks the two new rows' build commands and their order, and still checks `staging/app` and
    `production/app`.
- **After staging/status serves the route:**
  1. The owner merges a LOOP.md change. It points each platform row at `sh scripts/gcp/served.sh` on its URL,
     marks both readable, and removes `staging/app`, together with the line in `served.test.ts` that checks it.
  2. `/loop-status` and the status service then read `staging/app-android` like any other row.

It needs `status-callers`, which changes the same `service.json` and `openapi.yaml` (per D66), so the two are never
built at once (added 2026-10-24). It no longer needs `status-service` (per D78). Rollback: redeploy the previous
revision, and the platform rows read `unknown` again.

## Decisions

| # | Decision | Decided by, date | Closes |
| --- | --- | --- | --- |
| D1 | `touches` also cover `app.py` (the route is registered in `create_app`), `config.py` and `tests/test_config.py` (its settings, checked against `service.json`), `tests/support.py` (a fake EAS beside the fake GitHub) and the service's README (the reference for the route and its settings). | agent, from the status service's code on main @caf8038, 2026-10-28 | Raised by this concern's build |
| D2 | The route asks EAS the way eas-cli 22.4.0 does, with a GraphQL query for the channel profile's finished builds on one platform. It reads three settings: `STATUS_EXPO_TOKEN`, a secret named `status-expo-token`; `STATUS_EAS_PROJECT_ID`, `app/app.json`'s project id; and `STATUS_EXPO_API_URL`, default `https://api.expo.dev`, so the harness can point it at a fake. Without the token, only this route answers 503, and the status document is served as before. | agent, from eas-cli 22.4.0's source and the status service's config, 2026-10-28 | Raised by this concern's build |

## Questions

| # | Question | Blocks | Default if unanswered |
| --- | --- | --- | --- |

## Evidence

- 2026-10-28 · C1 · HOLDS · rung 1 · staging/status @fb3569f · `GET /apps/staging/android/version` answered 200 `{"commit": "19eb6965…"}` 3 of 3 times (0.10 to 0.21 s), and `sh scripts/gcp/served.sh` on it printed 19eb696 and exited 0. 19eb696 is the commit the owner's EAS build made on 2026-10-28 ("Prepare for android build", parent 69617a2), so the route read the real staging Android build through EAS with the robot token. `/apps/staging/ios/version` answered 404 "no finished ios build for profile staging" 3 of 3 times, so Android reads without iOS (per D79). `production/android` and `staging/windows` each answered a 404 naming why

## Shipped

2026-10-28, to `staging/status`, its `ships-to`, at fb3569f; its rows became readable on main in #129 (d45ed2a).

- **What shipped.**
  - PR #126 (merge fb3569f) added `GET /apps/{channel}/{platform}/version` to the status service. It asks EAS the
    way eas-cli 22.4.0 does, with an Expo robot token from `status-expo-token`, and answers each platform's latest
    finished build's commit. 404 means no finished build or no commit; 503 means EAS can't be read. It never
    answers an older commit.
  - The same PR added the `staging/app-android` and `staging/app-ios` rows, read through that route.
  - PR #129 made both rows readable and removed `staging/app`.
  - C1 holds at rung 1 on staging/status @fb3569f: Android answered 19eb696, the owner's real staging build, and
    iOS answered 404. C2 holds by CI.
- **Departures from the design.**
  - D57 planned one row per channel, read when its iOS and Android builds agree. With staging built for Android
    only, that rule would never read, so the owner split the rows by platform (D79). The app's concerns moved to
    `staging/app-android` (D80).
  - The `status-service` need was dropped (D78). Its unproven C1 and C2 are proofs, not something the build
    relied on.
  - The build widened `touches` to the service's `app.py`, `config.py`, `test_config.py`, `support.py` and README
    (D1), and recorded how EAS is read (D2).
  - The row switch landed without a `Concern:` trailer. With one, the concern would have read as merged until
    staging/status was redeployed.
- **Learned.**
  - The first Android build was made from a commit EAS created on the owner's local main, because
    `cli.requireCommit` met uncommitted files there. The commit was on no remote, so no service could have
    placed the build. It was pushed unchanged as `builds/staging-android-19eb696`, which must stay until a build
    from a clean checkout of `origin/main` replaces it, as LOOP.md §3 now says.
  - The robot token sits in the manifest's secrets, so every status deploy fails until that secret exists.
  - A readable row whose GET keeps failing still reads as a transient unknown in `owner-queue`, which is why the
    rows were switched only after Android served.
