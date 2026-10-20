---
needs: [one-repository, status-derivation, status-api]
touches: [services/status/]
effects: [GCP projects for staging and production, with Cloud Run services (spending; cloud IAM), a GitHub App with read access to jugonzal/architect-loop and webhooks on it (identity and access), the app's private key and webhook secret in Secret Manager (secrets), new LOOP.md §3 rows with each environment's /version URL (the owner merges them)]
ships-to: production
---
# Status for the project is fresh within a minute of a push, a pull request event or a deploy

## Done when

- **C1** After a push, a PR event or a change in an environment's served commit, the service's answer reflects
  it within 60 seconds and names the commits it read. Prove: timed pushes and a PR opened, merged and closed on a
  test loop, on staging.
- **C2** It reads each served commit only with an HTTP GET of the URL in `LOOP.md` §3, and runs nothing taken
  from the repository (per D9). When that read fails, or GitHub is unreachable, it answers `unknown` for those
  facts and never serves an older value as current. Prove: point an environment's URL at a failing endpoint and
  revoke the app's token, on staging, then read the affected concerns.
- **C3** It stores no state a person typed. Deleting its cache and restarting gives the same answer. Prove: wipe
  the cache and compare, on staging.

## Design

### Where we are

- No services, no GCP project and no GitHub App exist yet (2026-10-20).

### Approach

A Cloud Run service (per D8) that runs the status script from the same commit it is built from (per D13, D15), gathers facts itself (webhooks plus polling
of the `/version` URLs, per D9), and calls `loop_status.py derive --facts` (per D15, C3 of `status-derivation`).
It serves `GET /projects/{project}/status` with the `status-api` document, keyed by project (per D18). Callers
authenticate with the GitHub token from the app's sign-in, and must be collaborators on the project's
repository. The service exposes its own `/version`. Rollback: redeploy the previous Cloud Run revision; it
writes no data.

## Decisions

| # | Decision | Decided by, date | Closes |
| --- | --- | --- | --- |

## Questions

| # | Question | Blocks | Default if unanswered |
| --- | --- | --- | --- |

## Evidence

## Shipped
