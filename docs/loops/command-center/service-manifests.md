---
needs: []
touches: [scripts/gcp/, docs/runbooks/deploy.md, tests/test_layout.py, tests/test_service_manifests.py, services/runner/service.json, services/threads/service.json]
effects: [each service's settings, secret references, Cloud SQL attachment, runtime identity and jobs, applied on every deploy (the owner runs each deploy, per LOOP.md §2), the APIs and Firestore databases the manifests declare, created by the bootstrap (spending; cloud IAM; the owner runs it), the runtime identities and their IAM roles (cloud IAM), the secrets' values in Secret Manager (secrets; the owner creates them, and the manifests hold only their names)]
ships-to: main
---
# Each service deploys with exactly the config its folder declares

## Done when

- **C1** `deploy.sh <service> <env> <sha>` reads `services/<service>/service.json` as it is at `<sha>` and applies
  all of it: settings, secrets by name, Cloud SQL instance, runtime identity and jobs (per command-center/D46). A
  deploy leaves the service configured exactly as its commit's manifest says, and deploying an earlier commit
  restores that commit's config. A manifest that does not fit the format is refused before any `gcloud` call.
  Prove: tests with a fake `gcloud`, in CI on main, then deploying the runner and threads from a commit on main
  and reading their config back, on staging and then production.
- **C2** `bootstrap.sh <env>` enables the APIs every manifest lists and creates the Firestore databases they
  declare, and a second run changes nothing (per `environments` D1). Prove: fake-`gcloud` tests, in CI on main,
  then two runs from a commit on main, on staging and then production.
- **C3** The runner's and threads' manifests declare every setting and secret their code requires without a
  default, and no secret's value. Prove: a test that compares each manifest with the variables its service's
  config reads, in CI on main.

## Design

### Where we are

- Verified 2026-10-20 (main @a9fde89, `scripts/gcp/`): `deploy.sh` builds and deploys a commit with
  `--update-env-vars` for `COMMIT_SHA` alone (per command-center/D47) and `--allow-unauthenticated`, and keeps
  everything else the service already has. `common.sh` lists the APIs `bootstrap.sh` enables: Cloud Run,
  Artifact Registry, Secret Manager, IAM credentials and billing budgets. Nothing in the repository says what a
  service's settings, secrets, Cloud SQL instance, identity or jobs are.
- Verified 2026-10-20 (main @a9fde89): the runner reads `RUNNER_*` variables (`services/runner/runner/config.py`),
  among them `RUNNER_APP_PRIVATE_KEY` and `RUNNER_STORE`, and runs each session as a Cloud Run job. Threads reads
  `THREADS_*` variables, among them its app key, webhook secret and `THREADS_PROJECTS`, and needs a Cloud SQL
  instance. Threads starts unconfigured, answering only `/version`, until they are set.
- Verified 2026-10-20 (`tests/test_layout.py`): the tests for `scripts/gcp/` run the scripts with fake
  executables first on `PATH`. Any new test that calls `check.sh` must set `CHECK_SKIP_TESTS=1` (`LOOP.md` §7).

### Approach

Per command-center/D46, D32 and D47, and `environments` D1:

- **Format:** one JSON file per service, read with Python's standard library, so the scripts need nothing new.
  Its fields are fixed by this concern's fixtures and described in `docs/runbooks/deploy.md`. It holds settings by
  value, secrets by their Secret Manager names, the Cloud SQL instance, the runtime identity, the jobs (the
  runner's session job) and the APIs and Firestore databases the service needs. `runner-store` adds the runner's
  Firestore database and store setting to its manifest (per command-center/D44). `status-service` and `notifications` each add their own manifest in this format.
- **Deploy:** `deploy.sh` applies the manifest of the commit it deploys, after its existing checks, so a rollback
  to an earlier commit restores that commit's config. It still sets `COMMIT_SHA` itself.
- **Bootstrap:** it adds the manifests' APIs to the ones it enables, and creates their Firestore databases and
  runtime identities, each step reading first, so a second run prints `0 changes`.
- **Manifests:** `services/runner/service.json` and `services/threads/service.json`, matching what their code reads
  today. C3's test reads the variable names from each service's config, so a new required variable fails CI until
  the manifest names it.
- **Runbook:** `docs/runbooks/deploy.md` gains the steps for secrets, which the owner creates before the first
  deploy of a service that names them.

`LOOP.md` is not in `touches`: the deploy and bootstrap commands keep their names and arguments, so §3 and §4 stay
true. Rollback: revert the PR. Config already applied to a service stays until the next deploy.

## Decisions

| # | Decision | Decided by, date | Closes |
| --- | --- | --- | --- |

## Questions

| # | Question | Blocks | Default if unanswered |
| --- | --- | --- | --- |

## Evidence

## Shipped
