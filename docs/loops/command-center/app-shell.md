---
needs: [status-api, queue-items]
touches: [app/package.json, app/app.json, app/eas.json, app/tsconfig.json, app/src/app/_layout.tsx, app/src/app/(tabs)/_layout.tsx, app/src/shell/, app/src/api/, app/src/theme/, .github/workflows/app.yml, LOOP.md]
effects: [a GitHub OAuth app for sign-in, with the device flow enabled, that asks for no repository access (identity and access; per command-center/D28 and D1 here), an Expo account with EAS build credentials (new vendor account: identity and access; spending; secrets), Apple Developer and Google Play accounts (identity and access; spending), TestFlight and Play internal-testing submissions (owner only)]
ships-to: production/app
---
# A signed-in person has the app on their phone, registered for push, with a tab for each screen

## Done when

- **C1** A build installs on iOS and Android, signs in with GitHub through the device flow (per D1), and shows the
  person's name. It shows the tabs from the screen design (Needs you, Loops, Agents, Environments) without a More
  tab (per command-center/D4). Prove: a TestFlight build and a Play internal build, installed on devices and signed
  in against staging.
- ~~**C2** The device registers for push, and a test notification sent to that person arrives on their devices
  and no one else's. Prove: two devices with two accounts, on staging.~~ Moved to `notifications` C1, which owns
  registration, the device store and sending (per command-center/D35).
- **C3** `LOOP.md` §3 has a `staging/app` and a `production/app` row. Each has a served-commit command that prints
  the commit that the build serving that channel was made from, and `/loop-status` reads both (per
  command-center/D43). Prove: each row's command against a build whose commit is known, on staging/app, then
  production/app.

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
  cannot read the rows, and that is a question for `/loop-design`.

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

## Questions

| # | Question | Blocks | Default if unanswered |
| --- | --- | --- | --- |
| ~~Q1~~ | ~~How does the app sign in, when GitHub's web flow needs a client secret that a phone app cannot keep? (raised by this design's read of GitHub's docs)~~ → D1 | | |

## Evidence

## Shipped
