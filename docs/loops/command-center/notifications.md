---
needs: [one-repository, app-shell, status-service, addressed-to-people]
touches: [services/notify/, .github/workflows/notify.yml, app/src/app/notifications/, app/src/features/notifications/]
effects: [Expo push credentials, with an APNs key and an FCM key (secrets; identity and access), push notifications and digests sent to real users (sending to real users), the notifier's own store for devices and settings in each GCP project (spending; cloud IAM; per D26), a Cloud Run service in each project (spending)]
ships-to: production
---
# Each person hears about the items waiting on them, blocking ones at once and the rest in their digest

## Done when

- **C1** A device registers for push from the app, and a test notification sent to that person arrives on their
  devices and no one else's. Prove: two devices with two accounts, on staging. (Moved from `app-shell` C2, per
  D35.)
- **C2** Within a minute of the status changing, a push goes out for each blocking item that waits on the person,
  once, and everything else waits for the digest. Prove: two accounts with one blocking and one non-blocking
  item, on staging. (Moved from `app-inbox` C3, per D35.)
- **C3** The digest arrives at the time the person set, and nothing is pushed during their quiet hours. Prove: a
  test schedule on one account, comparing delivery times with its settings, on staging.

## Design

### Where we are

- No service and no device store exist (2026-10-20).
- Proposal §5: push only for blocking items addressed to the person; everything else in a digest the person
  schedules; quiet hours per person; backlog loops carry no notifications.
- `waits_on` comes from `addressed-to-people`, and the queue from `status-service`.

### Approach

Per D35, D26, D28, D29, D30 and D32: a Cloud Run service in `services/notify/`, in Python 3.12, with tests in
`services/notify/tests/` run by `.github/workflows/notify.yml`. It keeps each person's devices, digest time and
quiet hours in its own store, along with the items it has already pushed, so each one is pushed once. It reads
the status service's queue with its Cloud Run service identity, polling often enough to push within a minute, and
sends through Expo's push service. Its API is in `services/notify/openapi.yaml`. The app's registration and
settings screen lives in `app/src/app/notifications/` and `app/src/features/notifications/`, so it edits no file
of `app-shell`'s. Rollback: redeploy the previous revision. A push that was sent cannot be recalled.

## Decisions

| # | Decision | Decided by, date | Closes |
| --- | --- | --- | --- |

## Questions

| # | Question | Blocks | Default if unanswered |
| --- | --- | --- | --- |
| Q1 | Is the digest a push, an email, or a list in the app? Options: one push at the person's chosen time, opening the inbox; an email, which needs a sender and addresses kept; no digest, because the inbox already is one. | C3 | One push at the person's chosen time, saying how many items wait and opening the inbox |
| Q2 | What counts as blocking? Options: an item that unblocks at least one concern; only an item that crosses a gate; whatever the person marks. | C2 | An item that unblocks at least one concern |

## Evidence

## Shipped
