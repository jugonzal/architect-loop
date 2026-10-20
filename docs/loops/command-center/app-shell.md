---
needs: [one-repository, status-api]
touches: [app/package.json, app/app.json, app/eas.json, app/tsconfig.json, app/src/app/_layout.tsx, app/src/app/(tabs)/_layout.tsx, app/src/shell/, app/src/api/, app/src/theme/]
effects: [a GitHub OAuth app for sign-in (identity and access), an Expo account with EAS and push credentials (new vendor account: identity and access; spending; secrets), Apple Developer and Google Play accounts (identity and access; spending), TestFlight and Play internal-testing submissions (owner only)]
ships-to: production
---
# A signed-in person has the app on their phone, registered for push, with a tab for each screen

## Done when

- **C1** A build installs on iOS and Android, signs in with GitHub, and shows the person's name. It shows the
  tabs from the screen design (Needs you, Loops, Agents, Environments) without a More tab (per D4). Prove: a
  TestFlight build and a Play internal build, installed on devices and signed in against staging.
- **C2** The device registers for push, and a test notification sent to that person arrives on their devices
  and no one else's. Prove: two devices with two accounts, on staging.

## Design

### Where we are

- No app exists (2026-10-20). The screen design is 390×844 artboards in IBM Plex Sans and Mono, with a pale
  green-grey ground (`#EEF0EC`), ink `#15181C`, accent `#2443B8`, and verdict colours for HOLDS (green),
  UNPROVEN (amber) and CONTRADICTS or objections (rust). This is from the canvas, read 2026-10-20 (per D4).

### Approach

Expo with Expo Router and TypeScript (per D7). Routes are file-based, so each screen concern adds its own files
under `app/src/app/(tabs)/<screen>/` and `app/src/features/<screen>/` without editing a shared file. `src/api/`
holds a typed client generated from `plugin/skills/loop-status/scripts/status.schema.json` in the same commit (per D15), and stubs
that load its fixtures. `src/theme/` holds the design's tokens. Rollback: a store build cannot be recalled. An
EAS update can revert JavaScript, and a native change needs a new build.

## Decisions

| # | Decision | Decided by, date | Closes |
| --- | --- | --- | --- |

## Questions

| # | Question | Blocks | Default if unanswered |
| --- | --- | --- | --- |

## Evidence

## Shipped
