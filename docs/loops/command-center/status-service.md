---
needs: [status-derivation, status-api, queue-items, service-manifests]
touches: [services/status/, .github/workflows/status-service.yml]
effects: [Cloud Run services in staging's GCP project (gates: spending, infra), the status service's own GitHub App with read access to jugonzal/architect-loop and webhooks on it (per D27; gates: identity), the app's private key and webhook secret in Secret Manager (gates: secrets)]
ships-to: staging/status
---
# Status for the project is fresh within a minute of a push, a pull request event or a deploy

## Done when

- **C1** After a push, a PR event or a change in an environment's served commit, the service's answer reflects
  it within 60 seconds and names the commits it read. Prove: timed pushes and a PR opened, merged and closed in
  the sandbox loop (per D61), on local and then staging/status (per D53, D54).
- **C2** It reads each served commit only with an HTTP GET of the URL in `LOOP.md` §3, and runs nothing taken
  from the repository (per D9). The URL is the first `http(s)` URL in the row's served-commit cell, and a row
  without one is `unknown` (per D56). When that read fails, or GitHub is unreachable, it answers `unknown` for those
  facts and never serves an older value as current. Prove: point an environment's URL at a failing endpoint and
  revoke the app's token, on staging, then read the affected concerns.
- **C3** It stores no state a person typed. Deleting its cache and restarting gives the same answer. Prove: wipe
  the cache and compare, on staging.

## Design

### Where we are

- Verified 2026-10-22 (`loop_status.py` on main @e63f06b): `derive --facts` and `pending_queries(facts)` let a
  caller supply its own facts and answer the git questions the derivation asks, which this service does from its
  own clone. Staging exists (`loops-512401`), and `status` answers 404 there, so it is not deployed.
- No services, no GCP project and no GitHub App exist yet (2026-10-20). The projects and the `LOOP.md` §3 rows
  come from `environments` now, not from this concern (per D31). (Corrected 2026-10-20, main @a9fde89: the runner
  and threads services exist, `environments` added one §3 row per service, and no project exists yet.)

### Approach

A Cloud Run service (per D8) that runs the status script from the same commit it is built from (per D13, D15), gathers facts itself (webhooks plus polling
of the `/version` URLs, per D9), and calls `loop_status.py derive --facts` (per D15, C3 of `status-derivation`).
It serves `GET /projects/{owner}/{repo}/status` with the `status-api` document, keyed by project (per D18, D48). A caller
is identified with `GET /user` on the token from the app's sign-in, and must be a collaborator on the project's
repository, checked with the service's own read-only app (per D27, D28). Python 3.12, tests in
`services/status/tests/`, run by `.github/workflows/status-service.yml` (per D30). It follows the deploy
convention of D32, including its own `/version`, reads its commit from `COMMIT_SHA` (per D47), and declares its
deploy config in `services/status/service.json`, in the format `service-manifests` defines (per D46). GitHub's API URL
and every other outside endpoint are settings, so the local harness can point them at its fakes (per D53). Each
row's URL is found as D56 says. `app-served` adds `/apps/{channel}/version` after this concern (per D57). Rollback:
redeploy the previous Cloud Run revision; it writes no data.

## Decisions

| # | Decision | Decided by, date | Closes |
| --- | --- | --- | --- |

## Questions

| # | Question | Blocks | Default if unanswered |
| --- | --- | --- | --- |

## Evidence

## Shipped
