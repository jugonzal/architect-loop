---
needs: [one-repository, runner-dispatch, service-manifests]
touches: [services/runner/service.json, services/runner/runner/firestore_store.py, services/runner/runner/main.py, services/runner/requirements.txt, services/runner/requirements-dev.txt, services/runner/tests/test_firestore_store.py, .github/workflows/runner.yml]
effects: [the runner's own Firestore database in each GCP project, created by the bootstrap from the runner's manifest (spending; cloud IAM; per command-center/D44, D46; the owner runs the bootstrap)]
ships-to: production/runner
---
# Every runner container claims a concern from one shared store

## Done when

- **C1** The runner's store is a Firestore database of its own, which the service and every session's job share
  (per command-center/D44, D26). It keeps sessions, their spend and their final messages, and claims a concern in
  one transaction, so dispatches made at once from different service instances start at most one holding
  session per concern and at most the cap per sponsor. Prove: the store's tests against the Firestore emulator,
  run by `runner.yml`, in CI on main, then ten dispatches at once on one concern and four at once by one sponsor,
  on staging/runner and then production/runner.

## Design

### Where we are

- Verified 2026-10-20 (main @a9fde89): `services/runner/runner/store.py` defines the store the service and the job
  use, with one implementation, SQLite. Separate Cloud Run containers cannot share it, so the runner cannot run on
  staging until this concern merges. `RUNNER_STORE` in its config names the store.
- `runner-dispatch` changes what a claim is: only `/loop-build` and `/loop-design` hold a concern (per
  `session-runner` D6), and each session keeps its final message. This concern implements the store as that
  change leaves it, so it needs `runner-dispatch`. It also sets the store in the runner's manifest, which
  `service-manifests` writes first, so it needs that too (per command-center/D42).

### Approach

Per command-center/D44 and D26: `firestore_store.py` implements the store's interface with
`google-cloud-firestore`, against a database named after the service, `runner`, in its environment's project.
A claim runs in one transaction that reads the concern's claim document and the sponsor's running sessions, and
writes the new session only if both allow it. `main.py` picks the store from `RUNNER_STORE`; SQLite stays for
local runs and tests. `runner.yml` starts the Firestore emulator for the store's tests. The runner's manifest,
`services/runner/service.json`, declares the database and sets `RUNNER_STORE` to it, so the bootstrap creates the
database and every deploy points the service and its jobs at it (per command-center/D46).

Rollback: redeploy the previous commit, which reads SQLite and so cannot run across containers. The Firestore data
stays, and wiping it loses session history and the estimates' medians, never a loop's state (G4).

## Decisions

| # | Decision | Decided by, date | Closes |
| --- | --- | --- | --- |

## Questions

| # | Question | Blocks | Default if unanswered |
| --- | --- | --- | --- |

## Evidence

## Shipped
