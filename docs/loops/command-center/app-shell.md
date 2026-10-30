---
needs: [status-api, queue-items]
touches: [app/package.json, app/app.json, app/eas.json, app/tsconfig.json, app/src/app/_layout.tsx, app/src/app/(tabs)/_layout.tsx, app/src/shell/, app/src/api/, app/src/theme/, .github/workflows/app.yml, LOOP.md]
effects: [a GitHub OAuth app for sign-in with the device flow enabled that asks for no repository access (per command-center/D28 and D1 here; gates: identity), an Expo account with EAS build credentials (a new vendor account; gates: identity, spending, secrets), Apple Developer and Google Play accounts (gates: identity, spending), TestFlight and Play internal-testing submissions (the owner submits them; gates: store)]
ships-to: staging/app-android
---
# A signed-in person has the app on their phone, registered for push, with a tab for each screen

## Done when

- ~~**C1** A build installs on iOS and Android, signs in with GitHub through the device flow (per D1), and shows the
  person's name. It shows the tabs from the screen design (Needs you, Loops, Agents, Environments) without a More
  tab (per command-center/D4). Prove: the shell's tests, which sign in against a fake GitHub and render the four
  tabs, in CI on main (per D2), then a TestFlight build and a Play internal build, installed on devices and signed
  in against staging.~~ Superseded by C4 and C5 (per D3, command-center/D80).
- ~~**C2** The device registers for push, and a test notification sent to that person arrives on their devices
  and no one else's. Prove: two devices with two accounts, on staging.~~ Moved to `notifications` C1, which owns
  registration, the device store and sending (per command-center/D35).
- ~~**C3** `LOOP.md` §3 has a `staging/app` and a `production/app` row. Each has a served-commit command that prints
  the commit that the build serving that channel was made from, and `/loop-status` reads both (per
  command-center/D43). Prove: `served.js`'s tests against EAS build-list fixtures, in CI on main (per D2), then the
  `staging/app` row's command against a build whose commit is known, on staging/app. Production's row is proven
  by the later loop (per command-center/D54). Once `app-served` is deployed, the row reads through the status
  service (per command-center/D57).~~ Superseded by C6 (per D4, command-center/D79).
- ~~**C4** A staging Android build installs from Google Play internal testing, signs in with GitHub through the
  device flow (per D1), and shows the person's name. It shows the tabs from the screen design (Needs you, Loops,
  Agents, Environments) without a More tab (per command-center/D4). Prove: the shell's tests, which sign in against
  a fake GitHub and render the four tabs, in CI on main (per D2), then a Play internal build installed on an Android
  device and signed in against staging, on staging/app-android (per D3).~~ Superseded by C7 (per D5, command-center/D81).
- ~~**C5** The same on iOS: a TestFlight build installs, signs in and shows the tabs.~~ Moved out of this concern
  until a decision ships the app to staging/app-ios (per D3, command-center/D80).
- ~~**C6** `LOOP.md` §3 has `staging/app-android` and `staging/app-ios` rows, each reading its own platform's commit
  through the status service's `/apps/staging/<platform>/version` (per command-center/D79, D57), and a
  `production/app` row whose command prints the commit both platforms' latest production builds were made from
  (per command-center/D43). `/loop-status` reads the platform rows like any other. Prove: `served.test.ts` and
  `served.js`'s tests, in CI on main (per D2), then `sh scripts/gcp/served.sh` on the Android row's URL against a
  build whose commit is known, on staging/app-android (per D4). Production's row is proven by the later loop (per
  command-center/D54).~~ Superseded by C8 (per D5, command-center/D81, D82).
- **C7** An Android build of the `preview` profile installs on a device as an APK, signs in with GitHub through the
  device flow (per D1), and shows the person's name. It shows the tabs from the screen design (Needs you, Loops,
  Agents, Environments) without a More tab (per command-center/D4). Prove: the shell's tests, which sign in against
  a fake GitHub and render the four tabs, in CI on main (per D2), then a preview build installed on an Android
  device and signed in against staging, on staging/app-android (per command-center/D81).
- **C8** `LOOP.md` §3 has `staging/app-android`, read through the status service's
  `/apps/preview/android/version`, and `staging/app-ios`, read through `/apps/staging/ios/version` (per
  command-center/D81, D82), and a `production/app` row whose command prints the commit both platforms' latest
  production builds were made from (per command-center/D43). `/loop-status` reads the platform rows like any other.
  Prove: `served.test.ts` and `served.js`'s tests, in CI on main (per D2), then `sh scripts/gcp/served.sh` on the
  Android row's URL against a build whose commit is known, on staging/app-android. Production's row is proven by the
  later loop (per command-center/D54).

## Design

### Where we are

- No app exists (2026-10-20). The screen design is 390×844 artboards in IBM Plex Sans and Mono, with a pale
  green-grey ground (`#EEF0EC`), ink `#15181C`, accent `#2443B8`, and verdict colours for HOLDS (green),
  UNPROVEN (amber) and CONTRADICTS or objections (rust). This is from the canvas, read 2026-10-20 (per command-center/D4).
- Verified (GitHub's docs, https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/authorizing-oauth-apps,
  read 2026-10-20): the web flow's token exchange requires the OAuth app's client secret, with or without PKCE,
  and a phone app cannot keep one. The device flow needs only the client ID, and must be enabled in the OAuth
  app's settings (per D1).
- Assumed: an EAS build records the git commit it was built from, so C3's rows can read it. Check with
  `eas build:list --json` on the first build, and whether reading it needs an Expo token; if it does, agents
  cannot read the rows, and that is a question for `/loop-design`. (Answered 2026-10-22: reading it needs an Expo
  login, per `LOOP.md` §3, so `app-served` serves it at a URL, per command-center/D57.)
- Verified 2026-10-22 (main @e63f06b): `src/shell/__tests__/shell.test.tsx` and `src/shell/auth/__tests__/signIn.test.ts`
  sign in against a fake GitHub and render the tabs, and `src/shell/release/__tests__/served.test.ts` covers the
  rows' rule. `.github/workflows/app.yml` runs them. Under command-center/D50 the six screen concerns wait until
  every claim here holds somewhere, so C1 and C3 now start with that CI rung (D2).

### Approach

Expo with Expo Router and TypeScript (per command-center/D7). Routes are file-based, so each screen concern adds its own files
under `app/src/app/(tabs)/<screen>/` and `app/src/features/<screen>/` without editing a shared file. `src/api/`
holds the signed-in fetch and a typed client generated from
`plugin/skills/loop-status/scripts/status.schema.json` in the same commit (per command-center/D15), with stubs that load its
fixtures. Sign-in uses GitHub's device flow (per D1): the app asks for a device code with only its client ID,
shows and copies the code, opens `https://github.com/login/device`, and polls for the token, so no secret is in
the app or in any service. The runner's and the threads' clients belong to the screens that use them (per command-center/D29). Sign-in proves
who the person is and asks GitHub for no repository access (per command-center/D28). `.github/workflows/app.yml` runs the app's
tests, which the screen concerns' "in CI on main" claims rely on (per command-center/D30). `src/theme/` holds the design's
tokens. C3 adds the app's two rows to `LOOP.md` §3 (per command-center/D43). Rollback: a store build cannot be recalled. An EAS update can revert JavaScript, and a native change
needs a new build.

## Decisions

| # | Decision | Decided by, date | Closes |
| --- | --- | --- | --- |
| D1 | The app signs in with GitHub's device flow. No client secret is kept in the app or in any service, and no service is needed for sign-in, so this concern needs none. The person copies a code and confirms it on github.com. The owner enables the device flow on the OAuth app. | Juan, 2026-10-20 | Q1 |
| D2 | C1 and C3 start their Prove with a CI rung, from the shell's and `served.js`'s tests on main, so this concern meets command-center/D50 and the screens can be built. The staging/app steps still decide done. | Juan, 2026-10-22 | Q2 |
| D3 | C1's Android half becomes C4, proven with a Play internal build on staging/app-android. Its iOS half, C5, is moved out until a decision ships the app to staging/app-ios. | Juan, 2026-10-29 | Follows command-center/D80 |
| D4 | C3 is restated as C6 for the per-platform rows: `staging/app-android` and `staging/app-ios` read through `app-served`'s route, and `production/app` keeps `served.js`. | Juan, 2026-10-29 | Follows command-center/D79 |
| D5 | C4 becomes C7 and C6 becomes C8, for the preview profile's Android builds: C7 is proven with an installed APK, not a Google Play internal build, and C8 names the Android row's route as `/apps/preview/android/version`. | Juan, 2026-10-30 | Refines D3 and D4, follows command-center/D81, D82 |

## Questions

| # | Question | Blocks | Default if unanswered |
| --- | --- | --- | --- |
| ~~Q1~~ | ~~How does the app sign in, when GitHub's web flow needs a client secret that a phone app cannot keep? (raised by this design's read of GitHub's docs)~~ → D1 | | |
| ~~Q2~~ | ~~How do the screens start, when command-center/D50 holds them until every claim here is proven and C1 needs a TestFlight build? (raised by the 2026-10-22 design)~~ → D2 | | |

## Evidence

## Shipped
