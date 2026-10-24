---
needs: [service-manifests]
touches: [scripts/gcp/manifest.py, scripts/gcp/deploy.sh, scripts/gcp/bootstrap.sh, scripts/gcp/common.sh, docs/runbooks/deploy.md, tests/test_service_manifests.py]
effects: [each schedule a manifest declares created or updated as a Cloud Scheduler job on every deploy (the owner runs each deploy; gates: deploy), Cloud Scheduler enabled and allowed to mint OIDC tokens as each identity whose manifest declares a schedule (the owner runs the bootstrap; gates: infra, spending)]
ships-to: main
---
# A service's manifest can declare the schedules that call it

## Done when

- **C1** A manifest may declare `schedules`, each with a cron, a time zone and the path it calls. `manifest.py
  check` refuses a malformed one, and `render` writes the commands that create or update each declared Cloud
  Scheduler job and delete the service's jobs the manifest no longer declares. Prove:
  `tests/test_service_manifests.py`, by CI on main.
- **C2** `deploy.sh` runs those commands only after the new revision answers `/version` with the commit, each job
  calls the service with an OIDC token for the service's own identity and its URL as the audience, and
  `bootstrap.sh` enables Cloud Scheduler and lets it mint those tokens. Prove: `deploy.sh` and `bootstrap.sh` run
  against a fake `gcloud` in `tests/test_service_manifests.py`, by CI on main.

## Design

### Where we are

- **Verified** (`scripts/gcp/manifest.py` on main @603742a, 2026-10-24): a manifest's fields are `identity`,
  `apis`, `settings`, `secrets`, `cloudsql`, `firestore` and `jobs`, and `check` refuses any other. Nothing can call
  a service on a schedule or keep its CPU running between requests.
- Cloud Scheduler's price, read 2026-10-24: $0.10 per job per 31 days, with the first 3 jobs per billing account
  free (https://cloud.google.com/scheduler/pricing). Its finest schedule is a cron's, once a minute.
- `notifications` is the first user and needs this concern (per command-center/D67), so its claims are proven on
  main, not on staging, and the first real schedule is checked by `notifications`' C2 on staging.
- This changes the manifest format, so `service-manifests` goes stale and its C1 and C2 are proven again after it
  merges.

### Approach

Per command-center/D67, D46 and D32: `manifest.py` gains a `schedules` field, `{"<name>": {"cron": "* * * * *",
"time_zone": "Etc/UTC", "path": "/tick"}}`, checked like `jobs`, and `render` writes the `gcloud scheduler jobs`
commands for the service's region, naming each job `<service>-<name>`. `deploy.sh` runs them after its `/version`
check passes, so a failed deploy leaves the old schedule calling the old revision. `bootstrap.sh` enables
`cloudscheduler.googleapis.com` and grants the Cloud Scheduler service agent the right to mint tokens as each
identity whose manifest declares a schedule. `docs/runbooks/deploy.md` documents the field for people. Rollback:
deploy the previous commit; a schedule its manifest does not declare is deleted.

## Decisions

| # | Decision | Decided by, date | Closes |
| --- | --- | --- | --- |

## Questions

| # | Question | Blocks | Default if unanswered |
| --- | --- | --- | --- |

## Evidence

## Shipped
