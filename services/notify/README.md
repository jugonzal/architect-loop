# Notifier

Tells each person about the items waiting on them: blocking ones at once, the rest in a daily digest at the time
they chose, and nothing during their quiet hours
([`docs/loops/command-center/notifications.md`](../../docs/loops/command-center/notifications.md)).

- **The API** ([`openapi.yaml`](openapi.yaml)): a person registers their devices' Expo push tokens, sets their
  digest time, time zone and quiet hours, and sends a test notification to their own devices. A caller is
  identified with `GET /user` on the GitHub token from the app's sign-in (command-center/D28), and sees and changes
  only their own devices and settings. The app's client is generated from this file into `app/src/api/notify.gen.ts`
  (command-center/D55).
- **The poller** ([`notify/poller.py`](notify/poller.py), [`notify/notifier.py`](notify/notifier.py)) reads each
  project's status document from the status service every `NOTIFY_POLL_SECONDS` (20), with the notifier's own
  Cloud Run service identity. A queue item that waits on a person and whose `unblocks` names a concern is pushed
  to that person's devices, once (notifications D2); everything else waits for the digest, one push that says how
  many items wait and opens the inbox (notifications D1). Items of a loop in the backlog carry none.
- **Sending** is through Expo's push service ([`notify/expo.py`](notify/expo.py)), which reaches iOS and Android
  with the APNs and FCM credentials held by the Expo project. A device Expo says is gone is forgotten.
- **State** ([`notify/store.py`](notify/store.py)): devices, settings, and a mark for each push and digest sent, in
  the notifier's own Firestore database (command-center/D26, D44). Wiping it loses those and nothing else; the
  first read after a wipe marks what already stands as seen, so nothing is pushed twice because of it (G4).

## Who may register

Anyone GitHub signs in. The notifier has no GitHub App, so it does not check that a caller collaborates on the
project, as command-center/D28 says each service does. It does not need to: it only ever sends a person the items
that already wait on their own login, and their own test notification, at most one a minute. Whether that should
change is a design question in the pull request that added this service.

## Tests

From this folder, with Python 3.12 and the packages in `requirements-dev.txt`:

```sh
python -m pip install -r requirements-dev.txt
python -m unittest discover -s tests -v
```

No test reaches a network or a device: GitHub, the status service and Expo are fakes, and the real clients run
against fake servers on 127.0.0.1. The Firestore store's tests run when `FIRESTORE_EMULATOR_HOST` names an
emulator, and `.github/workflows/notify.yml` runs them against one.

## Config

Environment variables, listed in [`notify/config.py`](notify/config.py). The manifest,
[`service.json`](service.json), sets the project, the store (`firestore:notify`), its GCP project and the status
service's URL, and declares the `notify` Firestore database; the rest have defaults. `deploy.sh` sets `COMMIT_SHA`.
It names no secret: `NOTIFY_EXPO_ACCESS_TOKEN` is needed only if the Expo project turns on enhanced push security,
and then a pull request names its secret in the manifest.

## What the owner sets up

None of this exists yet, and each step is the owner's (LOOP.md §2).

1. **Expo push credentials** (gates: secrets, identity): an APNs key for iOS and an FCM key for Android, uploaded
   to the Expo project with `eas credentials`. The notifier holds neither.
2. **The bootstrap** (gates: spending, infra): `sh scripts/gcp/bootstrap.sh staging ...` creates what this manifest
   declares: the `notify` Firestore database in us-east1, and the runtime identity
   `notify@<project>.iam.gserviceaccount.com` with `roles/datastore.user`.
3. **The status service must accept the notifier's identity.** Today it answers only a person's GitHub token, so
   every read of the queue is refused until it also accepts an ID token from `notify@`, as threads accepts the
   runner's. That is a change to `services/status/`, which this concern does not touch.
4. **CPU between requests** (gates: spending): the poller runs inside the service, so Cloud Run must keep one
   instance with CPU always allocated (`--min-instances=1 --no-cpu-throttling`). Neither the manifest format nor
   `deploy.sh` can say so yet.
5. **The deploy** (gates: deploy, spending): `sh scripts/gcp/deploy.sh notify staging <sha>` from a commit on main.
   From then on it pushes to real people (gates: send). Roll back by deploying the previous commit; a push that
   was sent cannot be recalled.
