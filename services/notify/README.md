# Notifier

Tells each person about the items waiting on them: blocking ones at once, the rest in a daily digest at the time
they chose, and nothing during their quiet hours
([`docs/loops/command-center/notifications.md`](../../docs/loops/command-center/notifications.md)).

- **The API** ([`openapi.yaml`](openapi.yaml)): a person registers their devices' Expo push tokens, sets their
  digest time, time zone and quiet hours, and sends a test notification to their own devices. A caller is
  identified with `GET /user` on the GitHub token from the app's sign-in (command-center/D28), and sees and changes
  only their own devices and settings. The app's client is generated from this file into `app/src/api/notify.gen.ts`
  (command-center/D55).
- **The tick** (`POST /tick`, [`notify/notifier.py`](notify/notifier.py)): a Cloud Scheduler job that the manifest
  declares calls it every minute with an OIDC token for the notifier's own identity, and the notifier refuses any
  other token ([`notify/identity.py`](notify/identity.py); notifications D3, command-center/D67). On each tick it
  reads each project's status document with an ID token for its Cloud Run identity, which the status service
  trusts (command-center/D66). A queue item that waits on a person and whose `unblocks` names a concern is pushed
  to that person's devices, once (notifications D2); everything else waits for the digest, one push that says how
  many items wait and opens the inbox (notifications D1, D5). Items of a loop in the backlog carry none.
- **Sending** is through Expo's push service ([`notify/expo.py`](notify/expo.py)), which reaches iOS and Android
  with the APNs and FCM credentials held by the Expo project. A device Expo says is gone is forgotten.
- **State** ([`notify/store.py`](notify/store.py)): devices, settings, and a mark for each push and digest sent, in
  the notifier's own Firestore database (command-center/D26, D44). Wiping it loses those and nothing else; the
  first read after a wipe marks what already stands as seen, so nothing is pushed twice because of it (G4, D7).

## Who may register

A person the project's status document names as a loop's owner or member (command-center/D62, D69), checked
against the document when they register a device. The notifier has no GitHub App of its own, and it only ever
pushes a person the items that wait on their own login, and their own test notification, at most one a minute.

## Tests

From this folder, with Python 3.12 and the packages in `requirements-dev.txt`:

```sh
python -m pip install -r requirements-dev.txt
python -m unittest discover -s tests -v
```

No test reaches a network or a device: GitHub, the status service and Expo are fakes, the real clients run against
fake servers on 127.0.0.1, and a tick's token is checked against a made-up key set served there. The Firestore
store's tests run when `FIRESTORE_EMULATOR_HOST` names an emulator, and `.github/workflows/notify.yml` runs them
against one.

## Config

Environment variables, listed in [`notify/config.py`](notify/config.py). The manifest,
[`service.json`](service.json), sets the project, the store (`firestore:notify`), its GCP project, the status
service's URL, its own URL as the audience a tick's token must name, and its own identity as the one whose tick it
accepts. It declares the `notify` Firestore database and the schedule `tick` (`* * * * *`, `POST /tick`); the rest
have defaults. `deploy.sh` sets `COMMIT_SHA`. It names no secret: `NOTIFY_EXPO_ACCESS_TOKEN` is needed only if the
Expo project turns on enhanced push security (D8), and then a pull request names its secret in the manifest.

## What the owner sets up

None of this exists yet, and each step is the owner's (LOOP.md §2).

1. **Expo push credentials** (gates: secrets, identity): an APNs key for iOS and an FCM key for Android, uploaded
   to the Expo project with `eas credentials`. The notifier holds neither.
2. **The bootstrap** (gates: spending, infra): `sh scripts/gcp/bootstrap.sh staging ...` creates what this manifest
   declares: the `notify` Firestore database in us-east1, the runtime identity
   `notify@<project>.iam.gserviceaccount.com` with `roles/datastore.user`, and Cloud Scheduler, allowed to mint
   tokens as that identity.
3. **The status service's deploy** (gates: deploy): staging/status must serve status-callers, which trusts
   `notify@` at the status service's own URL, before any tick can read the queue.
4. **The deploy** (gates: deploy, spending, infra): `sh scripts/gcp/deploy.sh notify staging <sha>` from a commit on
   main deploys the service and creates the Cloud Scheduler job `notify-tick`. From then on it pushes to real
   people (gates: send). Roll back by deploying the previous commit; a push that was sent cannot be recalled.
