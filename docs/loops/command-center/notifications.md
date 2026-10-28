---
needs: [app-shell, app-clients, service-manifests, service-schedules]
touches: [services/notify/, .github/workflows/notify.yml, app/src/api/notify.gen.ts, app/src/app/notifications/, app/src/features/notifications/, app/package.json, app/app.json, app/src/shell/ShellHeader.tsx, app/src/shell/AppRoot.tsx, app/src/api/__tests__/clients.test.ts]
effects: [Expo push credentials with an APNs key and an FCM key (gates: secrets, identity), push notifications and digests sent to real users (gates: send), the notifier's own Firestore database for devices and settings in staging's GCP project (per command-center/D26 and D44; gates: spending, infra), a Cloud Run service in staging's project (gates: spending), a Cloud Scheduler job in staging's project that ticks the notifier every minute as its own identity (per command-center/D67 and D3; gates: spending, infra)]
ships-to: staging/notify
---
# Each person hears about the items waiting on them, blocking ones at once and the rest in their digest

## Done when

- **C1** A device registers for push from the app, and a test notification sent to that person arrives on their
  devices and no one else's. Prove: two devices with two accounts, on staging: the owner's login and a second login of the owner's, added as a member of the sandbox loop (per D9, D70). (Moved from `app-shell` C2, per
  D35.)
- **C2** Within two minutes of the status changing, a push goes out for each blocking item that waits on the
  person, once, and everything else waits for the digest. Prove: two accounts with one blocking and one
  non-blocking item, on staging. (Moved from `app-inbox` C3, per command-center/D35.) (Corrected 2026-10-24: this
  said within a minute; a tick every minute can be up to a minute away, per D3.)
- **C3** The digest arrives at the time the person set, and nothing is pushed during their quiet hours. Prove: a
  test schedule on one account, comparing delivery times with its settings, on staging.

## Design

### Where we are

- Corrected 2026-10-27: the service and its device store exist (`services/notify/`, built 2026-10-24 and 2026-10-25) and staging/notify serves it (its scheduler job ticks every minute, C2 evidence 2026-10-25). This said no service existed (2026-10-20; still so on main @603742a, 2026-10-24).
- **Verified** (`loop_status.py --json` and `services/notify/notify/notifier.py` `members()` on main @cf7f3af, 2026-10-27): the document's loops carry no `owner` or `members` (the derivation fills `waits_on` from them but does not output them), so `members()` finds no one and every registration gets 403. This contradicted D69's premise (C1 CONTRADICTS, 2026-10-25). Per command-center/D70 a new concern, `status-people`, adds the fields; this concern's code is unchanged, and C1 waits until staging/status serves them (per D51).
- Proposal §5: push only for blocking items addressed to the person; everything else in a digest the person
  schedules; quiet hours per person; backlog loops carry no notifications.
- `waits_on` comes from `addressed-to-people`, and the queue from `status-service`. Per command-center/D51 neither is
  in `needs`: this concern builds against the status schema and the status service's path (per D48), both on
  `main`, and its staging proofs wait until staging serves both.
- **Verified** (`services/status/status/app.py` on main @603742a, 2026-10-24): the status service answers only a
  person's GitHub token, so the notifier's service identity is refused. This contradicted the Approach, which
  assumed it could read the queue that way. `status-callers` adds the trust (per command-center/D66). Only this
  concern's staging proofs rely on it, so it is not a need (per D51): C2 and C3 wait until staging/status serves it.
- **Verified** (`scripts/gcp/manifest.py` on main @603742a, 2026-10-24): a manifest cannot keep a service's CPU
  running between requests or declare a schedule, so a poller inside the service would stall. `service-schedules`
  adds schedules to the format (per command-center/D67). This concern's manifest declares one, and `check.sh`
  refuses a field the format does not know, so its build relies on it: it is a need.
- **Verified** (`app/package.json`, `app/app.json` and `app/src/shell/` on main @603742a, 2026-10-24): the app has
  no `expo-notifications`, nothing links to a notifications screen, and nothing opens the inbox when a push is
  tapped (D1). `app-clients`' `app/src/api/__tests__/clients.test.ts` asserts that `services/notify/openapi.yaml`
  does not exist yet, so adding the file fails it. Both concerns are merged and nothing builds in those files, so
  this concern takes the five files it needs (per D4).

### Approach

Per D35, D26, D28, D29, D30 and D32: a Cloud Run service in `services/notify/`, in Python 3.12, with tests in
`services/notify/tests/` run by `.github/workflows/notify.yml`. It keeps each person's devices, digest time and
quiet hours in a Firestore database of its own (per command-center/D44), along with the items it has already
pushed, so each one is pushed once. A Cloud Scheduler job calls its tick path every minute with an OIDC token for
the notifier's own identity, and the notifier refuses a tick with any other token (per D3 and command-center/D67).
On each tick it reads the status service's document with its Cloud Run service identity, which the status service
trusts (per command-center/D66), and sends through Expo's push service. It accepts a device only from a person the
status document names as a loop's owner or member (per command-center/D69). Its API is in
`services/notify/openapi.yaml`, and the app's client for it is generated into `app/src/api/notify.gen.ts` with
`app-clients`' generator (per command-center/D55). Its deploy config is in its manifest,
`services/notify/service.json`, in the format `service-manifests` defines, with its schedule in the field
`service-schedules` adds (per command-center/D46 and D67). A blocking item is one whose `unblocks` names at least
one concern (per D2), and the digest is one push (per D1), timed per D5 and D6. The first read of a new or wiped
store pushes nothing (per D7). The app's registration and settings screen lives in `app/src/app/notifications/` and
`app/src/features/notifications/`. It adds `expo-notifications` and its config plugin to `app/package.json` and
`app/app.json`, a link to the screen from the account sheet in `ShellHeader.tsx`, and a handler in `AppRoot.tsx`
that opens the inbox when a push is tapped (per D4). (Corrected 2026-10-24: this said the screen edits no file of
`app-shell`'s.) Its app screen reaches devices with the next app build, so C1's proof needs one built after this
merges. Rollback: redeploy the previous revision. A push that was sent cannot be recalled.

## Decisions

| # | Decision | Decided by, date | Closes |
| --- | --- | --- | --- |
| D1 | The digest is one push at the time the person chose, saying how many items wait, and it opens the inbox. No email. | Juan, 2026-10-20 | Q1 |
| D2 | An item is blocking, and pushed at once, when its `unblocks` names at least one concern. Everything else waits for the digest. | Juan, 2026-10-20 | Q2 |
| D3 | The notifier reads the queue on a tick that a Cloud Scheduler job sends every minute (per command-center/D67), and it accepts a tick only with an OIDC token for its own identity. C2 allows two minutes, since a tick can be up to a minute away. | Juan, 2026-10-24 | Q3 |
| D4 | This concern's `touches` widen to `app-shell`'s `app/package.json`, `app/app.json`, `app/src/shell/ShellHeader.tsx` and `app/src/shell/AppRoot.tsx`, for `expo-notifications`, the link to the screen and opening the inbox from a push, and to `app-clients`' `app/src/api/__tests__/clients.test.ts`, whose notify test expects the OpenAPI file to be missing. | Juan, 2026-10-24 | Q4 |
| D5 | No digest goes out on a day when nothing waits, and a digest more than 15 minutes late is skipped for that day. | Juan, 2026-10-24 | confirms the first build's choice |
| D6 | A new person gets a 09:00 digest, no quiet hours, and the time zone of their first registered device, UTC until then. | Juan, 2026-10-24 | confirms the first build's choice |
| D7 | The first read of a new or wiped store marks what already waits as seen and pushes none of it, so a wipe (G4) never floods phones. | Juan, 2026-10-24 | confirms the first build's choice |
| D8 | Expo's enhanced push-security access token is optional and not in the manifest, so it is no effect for now. | Juan, 2026-10-24 | confirms the first build's choice |
| D9 | The second account for C1, C2 and C3 is a second GitHub login of the owner's, added as a member of the `sandbox` loop, signed in on a second device or profile. No other person is needed, so sandbox Q1 can stay deferred. | Juan, 2026-10-27 | Q5 |

## Questions

| # | Question | Blocks | Default if unanswered |
| --- | --- | --- | --- |
| ~~Q1~~ | ~~Is the digest a push, an email, or a list in the app?~~ → D1 | | |
| ~~Q2~~ | ~~What counts as blocking?~~ → D2 | | |
| ~~Q3~~ | ~~How often does the notifier read the queue, once a scheduler ticks it?~~ → D3 | | |
| ~~Q4~~ | ~~Where do `expo-notifications`, the link to the screen and the push-tap handler go, when they are `app-shell`'s files?~~ → D4 | | |
| ~~Q5~~ | ~~Who is the second account that C1 needs, when the sandbox's second person is deferred?~~ → D9 | | |

**Q3 options**
- **Every minute, two minutes in C2**: the most a scheduler allows, with the claim saying what a tick can
  promise. (recommended)
- **Every minute, one minute in C2**: the claim fails whenever a change lands just after a tick.

**Q4 options**
- **Widen this concern**: those concerns are merged and nothing builds there, so one branch finishes C1.
  (recommended)
- **A new app-push concern**: keeps this concern out of `app-shell`'s files, but splits C1 across two PRs.
- **Defer registration**: this merges without it, and C1 waits for a later concern.

**Q5 options**
- **A second login of the owner's**: added as a member of the sandbox loop and signed in on a second device or profile; a real two-account proof at rung 1, and no other person is needed. (recommended)
- **One account plus a refused one**: prove delivery to the owner's device and that a login absent from the document is refused, so it receives nothing. Weaker: "not delivered to another person" is inferred.
- **Wait for a real second person**: C1, C2 and C3 stay open while sandbox Q1 stays deferred.

## Evidence

- 2026-10-25 · C1 · CONTRADICTS · rung 1 · staging/notify @633cbe4 · The status document staging serves names no loop's `owner` or `members` (the fields are absent, though the schema says `owner` falls back to `LOOP.md`'s owner), and `loop_status.py --json` on the same main omits them too. The notifier's `members()` reads only those fields, so per command-center/D69 every device registration is refused with 403. Read from the document and the code; no registration was attempted, since a device would be a write to staging. Contradicts the premise of command-center/D69 that the document names each loop's owner
- 2026-10-25 · C2 · UNPROVEN · rung 1 · staging/notify @633cbe4 · Cloud Scheduler's `notify-tick` is enabled at `* * * * *` and ticked 3 times with 200 (latency 4.6 s to 13.8 s). The first tick (13:44:14 UTC) was the baseline and pushed nothing. The second (13:45:10) pushed the 5 `ship/staging/runner*` items to jugonzal, to 0 devices; whether they already waited at the baseline is not known from the logs, and if they did this departs from D7. Not done: two accounts with a blocking and a non-blocking item in the sandbox loop, which does not exist yet (per command-center/D61)
- 2026-10-25 · C3 · UNPROVEN · rung 1 · staging/notify @633cbe4 · Not run: it needs a registered device and a test schedule, and no device can register (C1)
- 2026-10-28 · C1 · UNPROVEN · rung 1 · staging/notify @633cbe4 · The blocker named on 2026-10-25 may be gone: staging/status now serves @142917d, which contains `status-people` (81018ef, `git merge-base --is-ancestor`), but this session had no GitHub token the status service accepts (401), so it could not confirm that the served document names owners and members. Still missing: the `sandbox` README has no `members:`, so D9's second login is not a member yet (the owner adds it); no staging/app build is confirmed to have the notifications screen (needs `EXPO_TOKEN`); and nobody has registered the two devices (the owner)
- 2026-10-28 · C2 · UNPROVEN · rung 1 · staging/notify @633cbe4 · Not run: it needs the two accounts and devices C1 needs, plus a blocking and a non-blocking item addressed to the second login in `sandbox`
- 2026-10-28 · C3 · UNPROVEN · rung 1 · staging/notify @633cbe4 · Not run: it needs a registered device (C1) and a test schedule on that account

## Shipped
