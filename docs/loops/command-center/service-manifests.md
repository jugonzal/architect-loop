---
needs: []
touches: [scripts/gcp/, docs/runbooks/deploy.md, tests/test_layout.py, tests/test_service_manifests.py, services/runner/service.json, services/threads/service.json]
effects: [each service's whole config from its manifest applied on every deploy (settings; secret references; Cloud SQL; runtime identity; jobs; the owner runs each deploy per LOOP.md §2; gates: deploy), the APIs and Firestore databases the manifests declare created by the bootstrap (the owner runs it; gates: spending, infra), the runtime identities and their IAM roles (gates: infra), the secrets' values in Secret Manager (the owner creates them and the manifests hold only their names; gates: secrets)]
ships-to: main
---
# Each service deploys with exactly the config its folder declares

## Done when

- **C1** `deploy.sh <service> <env> <sha>` reads `services/<service>/service.json` as it is at `<sha>` and applies
  all of it: settings, secrets by name, Cloud SQL instance, runtime identity and jobs (per command-center/D46). A
  deploy leaves the service configured exactly as its commit's manifest says, and deploying an earlier commit
  restores that commit's config. A manifest that does not fit the format is refused before any `gcloud` call.
  Prove: tests with a fake `gcloud`, in CI on main, then deploying the runner and threads from a commit on main
  and reading their config back, on staging (per command-center/D54).
- **C2** `bootstrap.sh <env>` enables the APIs every manifest lists and creates the Firestore databases they
  declare, and a second run changes nothing (per `environments` D1). Prove: fake-`gcloud` tests, in CI on main,
  then two runs from a commit on main, on staging (per command-center/D54).
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

- 2026-10-22 · C2 · HOLDS · rung 1 · main @18b866b · The owner ran `bootstrap.sh staging` twice on project loops-512401. The first run printed what `docs/runbooks/deploy.md` step 3 says, by the owner's account; its commit and output were not kept. The second, from 18b866b, printed `staging: 0 changes.` and no `changed` line. The bootstrap's inputs are identical on main from 84feb91, which first names the project, to 18b866b, so both runs read the same manifests. The APIs the manifests list read back enabled: threads' `sqladmin.googleapis.com` and `sql-component.googleapis.com`, beside `common.sh`'s 5; the runner's and the probe's manifests list none. Each manifest's identity read back with its roles: `runner@` with `roles/run.jobsExecutorWithOverrides`, `threads@` with `roles/cloudsql.client`, `probe-runtime@` with none. No manifest declares a Firestore database at 18b866b, so that half holds only vacuously on staging. The first manifest to declare one (`runner-store`'s) changes a path in `touches`, which makes this line stale until it is proven again. The fake-`gcloud` tests pass in `check` on 18b866b
- 2026-10-22 · C2 · HOLDS · rung 1 · main @92f6df9 · Re-proved after PR #35 (92f6df9) changed `docs/runbooks/deploy.md`. The owner ran `bootstrap.sh staging` again, from 92f6df9, and it ended `staging: 0 changes.` The owner reported that summary line; the rest of the output was not kept. `bootstrap.sh` counts one change for each API it enables and each identity, role or Firestore database it creates or grants, and reads every one first. So 0 changes means threads' two APIs, and every manifest's identity with its roles, were already in place. The manifests at 92f6df9 are identical to those at 18b866b, whose full run the line above records. No manifest declares a Firestore database yet, so that half still holds only vacuously. `check` is green on 92f6df9
- 2026-10-23 · C2 · HOLDS · rung 1 · main @a88018e · Re-proved after PR #42 changed `services/runner/service.json`, and the first time the Firestore half is not vacuous. The owner ran `bootstrap.sh staging` twice from a88018e on project loops-512401. The first run made exactly what the manifests at a88018e added, in 4 changes: it enabled `firestore.googleapis.com`, which the runner's manifest lists; it created the Firestore database `runner` in us-east1, which it declares; it granted `runner@` the declared `roles/datastore.user`; and it created the status manifest's identity `status@`, which has no roles. The second run printed `staging: 0 changes.`. It read back all 8 APIs (`common.sh`'s 5, the runner's 1, threads' 2), `ok  Firestore database runner (runner)`, every manifest's identity with its roles, and the 7 secrets the manifests name as missing (the runner's 2 with its job's, status' 2, threads' 3). `check` is green on a88018e
- 2026-10-23 · C2 · HOLDS · rung 1 · main @cd42938 · Re-proved after PR #48 (f93b6b1) changed `services/runner/service.json` and `services/threads/service.json`, naming staging's GitHub Apps in their settings. The owner ran `bootstrap.sh staging` from cd42938 on project loops-512401, after creating the 7 secrets the manifests name (`docs/runbooks/deploy.md` step 9). It printed `staging: 0 changes.` and no `changed` line. It read back all 8 APIs the manifests and `common.sh` list, `ok  Firestore database runner (runner)`, every manifest's identity with its roles, and each identity allowed to read exactly the secrets its manifest names: `runner@` 2, `status@` 2, `threads@` 3. `gcloud secrets get-iam-policy runner-app-private-key` listed only `runner@` with `roles/secretmanager.secretAccessor`. What the bootstrap reads from each manifest, and `scripts/gcp/`, are identical at a88018e and cd42938, so the runs that created the API and the database (the line above) read the same inputs. `check` and `status-service` are green on cd42938
- 2026-10-23 · C1 · HOLDS · rung 1 · main @1eae0a3 · The owner ran `docs/runbooks/deploy.md` step 13 on project loops-512401: `deploy.sh runner staging` and `deploy.sh threads staging` from 1eae0a3, then `gcloud ... describe --format=export` of the runner service, its `runner-session` job and the threads service. Compared field by field with what `scripts/gcp/manifest.py` at 1eae0a3 renders for staging, each export held exactly its manifest's runtime identity, its settings by value plus `COMMIT_SHA` 1eae0a3, its secrets as references at `key: latest` and nothing else in `env`, and its Cloud SQL instance (threads `loops-512401:us-east1:threads`; the runner none, its annotation empty), with the image tagged 1eae0a3. The job runs `python -m runner job` with 1 task, 0 retries and a 3600 s timeout, and only it has `ANTHROPIC_API_KEY`. The comparison flagged a changed setting and a changed secret in a copy of the exports. `served.sh` with 1eae0a3 exited 0 for both services. Not shown on staging: that a deploy replaces config a service already had, because both services answered 404 at `/version` earlier that day, so these were their first deploys; and that deploying an earlier commit restores its config. Every earlier runner or threads manifest on main that differs from 1eae0a3's leaves staging's GitHub App IDs `TODO(owner)`, which `deploy.sh` refuses before any `gcloud` call, so step 14 waits for the next commit that changes one of them. Until then that half rests on the fake-`gcloud` tests, which pass in `check` on 1eae0a3. The deploys' own output was not reported
- 2026-10-27 · C1 · HOLDS · rung 5 · main @f87dd42 · The `check` workflow on f87dd42 (run 40536615509) succeeded, and its `ok   tests` step runs `python3 -m unittest discover -s tests`. Run locally on f87dd42, `tests/test_service_manifests.py` ran 53 tests: all passed, none skipped. Among them, the fake-`gcloud` deploy tests show that the whole manifest is applied as it is at the commit, not as it is in the working tree; that deploying an earlier commit restores that commit's config and schedules; and that a manifest that is malformed, is not JSON, is missing or is left `TODO` is refused before any `gcloud` call. This line covers only the CI half. The staging half (deploy, then read the config back) was last proven at 1eae0a3, and 4 commits since then change `scripts/gcp/` or these two manifests, among them bbf959c, which adds schedules. Staging serves the runner at b2fbcfb and threads at 1eae0a3. Reading their config back needs the owner's `gcloud`
- 2026-10-27 · C2 · HOLDS · rung 5 · main @f87dd42 · The same green `check` run on f87dd42. Locally the fake-`gcloud` bootstrap tests pass: a first run creates what the manifests declare, a second run changes nothing, a malformed manifest stops the run before any call, each identity may read only its own secrets, and Cloud Scheduler is enabled only when a manifest declares a schedule. This line covers only the CI half. On staging, C2 was last proven at cd42938, and later commits change `scripts/gcp/`. Two runs from a commit on main need the owner
- 2026-10-27 · C3 · HOLDS · rung 5 · main @f87dd42 · The same green `check` run on f87dd42. Locally, the 9 tests in `ManifestsMatchTheCodeTest` pass. To check that they test the real path, I deleted `THREADS_GITHUB_WEBHOOK_SECRET` from a working copy of `services/threads/service.json`. Two of the tests then failed (`each_manifest_declares_every_variable_its_code_requires_without_a_default` and `no_manifest_holds_a_secrets_value`), and they passed again once I restored the file

## Shipped

2026-10-27, to `main`, its `ships-to`. Each deploy and bootstrap the owner runs from a commit on main after
61c365d applies it.

- **What shipped.** PR #26 (merge 61c365d) added `scripts/gcp/manifest.py`, which reads and checks
  `services/<service>/service.json`. With it, `deploy.sh` applies all of the manifest at the commit it deploys:
  settings, secrets by name, Cloud SQL instance, runtime identity and jobs. `bootstrap.sh` enables the APIs the
  manifests list and creates their Firestore databases and identities, reading first, so a second run changes
  nothing. The PR also added the runner's, threads' and the probe's manifests, the deploy runbook's steps for
  secrets, and `tests/test_service_manifests.py`. Later concerns extended the same format: `runner-store` added the
  runner's Firestore database (PR #42), PR #48 named staging's GitHub Apps, and `service-schedules` added schedules
  (PR #68). C1 to C3 hold in CI on main at e655a85.
- **Departures from the design.** The claims' Prove asks for a staging half as well as CI. That half was last shown
  for C1 at 1eae0a3, where the runner's and threads' exports matched their manifests field by field, and for C2 at
  cd42938, where two bootstrap runs ended `staging: 0 changes.`. Later commits changed `scripts/gcp/`, among them
  bbf959c, which adds schedules, and staging has not been read back since. Neither has it shown that a deploy
  replaces config a service already had, or that deploying an earlier commit restores its config. Both services'
  1eae0a3 deploys were their first, and every earlier manifest on main leaves staging's GitHub App IDs
  `TODO(owner)`, which `deploy.sh` refuses. Both rest on the fake-`gcloud` tests until the next commit that changes
  the runner's or threads' manifest, when the deploy runbook's step 14 can run.
- **Learned.** Each manifest change made the staging proof stale, so C2 was proven on staging four times in two
  days (18b866b, 92f6df9, a88018e, cd42938). The Firestore half held only vacuously until the first manifest
  declared a database. Reading a deploy back proves what it applied, but a rollback can only be shown once two
  deployable manifests exist on main.
