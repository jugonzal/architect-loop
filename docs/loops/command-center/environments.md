---
needs: []
touches: [LOOP.md, scripts/gcp/, docs/runbooks/deploy.md, scripts/check.sh, tests/test_layout.py]
effects: [a GCP project for staging linked to the owner's billing account (production's belongs to a later loop per command-center/D54; the owner runs the script that creates it; gates: spending, infra), an Artifact Registry repository and a deploy identity in it (gates: spending, infra), new LOOP.md §3 rows and §4 deploy and verify commands (a change to the contract; the owner merges it; gates: merge), every deploy (the owner runs it per LOOP.md §2; gates: deploy)]
ships-to: main
---
# Any service can be deployed from a commit on main to staging or production with one command

## Done when

- **C1** Staging and production are separate GCP projects in `us-east1`, each with an Artifact Registry repository,
  a deploy identity and a budget alert of its own (per D2). Idempotent `gcloud` scripts that the owner runs create
  them, so a second run changes nothing (per D1, command-center/D8, command-center/D32). Prove: run staging's
  bootstrap twice and list its resources and budget after each run, on staging. Production's run belongs to the
  later loop (per command-center/D54).
- **C2** One command builds a service's image from a commit on `main` and deploys it to an environment by the
  convention in command-center/D32, and its `/version` then prints that commit. It refuses a commit that is not on
  `main`. Prove: deploy the probe in `scripts/gcp/probe/` by the runbook and read its `/version`, and try a commit
  that is only on a branch, on staging (per command-center/D54).
- **C3** `LOOP.md` §3 has a row for each service in each environment, whose served-commit command reads that
  service's `/version`, and §4 has the deploy and verify commands. `/loop-status` reads every row and shows
  `unknown` for a service not yet deployed. The independence check in `scripts/check.sh` also fails on the
  services' hosts under `plugin/` (per command-center/D14). Prove: `/loop-status` from an installed release, and
  the independence test with a planted host, on main.

## Design

### Where we are

- Verified 2026-10-20 (`LOOP.md` on main @7b1f9aa): the staging and production rows of §3, and the deploy, verify
  and smoke-test commands of §4, are `TODO(owner)`. `docs/runbooks/` does not exist.
- Verified 2026-10-20 (`one-repository` C2's evidence): the independence check has no service host in its pattern
  yet, because no service has one.
- Assumed: no GCP project exists for this repository. Check with `gcloud projects list` on the owner's account
  before the first bootstrap. (Overtaken 2026-10-22: staging's bootstrap has run; see the next bullet.)
- Verified 2026-10-20 (main @a9fde89, PR #19): `scripts/gcp/` holds `bootstrap.sh`, `deploy.sh`, `served.sh`,
  `common.sh`, `projects.txt` and `probe/`, and `docs/runbooks/deploy.md` is a draft, not yet run. `LOOP.md` §3 has
  one row per service and environment, with every URL `TODO(owner)`, and §4 has the bootstrap, deploy and verify
  commands. Both project IDs in `projects.txt` are `TODO(owner)` (per D3). `deploy.sh` sets `COMMIT_SHA` (per
  command-center/D47) and changes nothing else in a service's config, so the runner's and threads' settings,
  secrets and Cloud SQL instance have no home yet; `service-manifests` adds one (per command-center/D46). No
  `gcloud` command has been run against the owner's account. (Superseded in part, 2026-10-22, main @18b866b:
  `projects.txt` names staging `loops-512401` and production `loops-512402`. Staging's bootstrap ran on
  2026-10-22 (project number 665570365697), and §3 holds staging's four URLs since PR #30 (9f57ff2). Production
  has not been bootstrapped. No service is deployed to staging: all four answer 404.)
- Verified 2026-10-20 (`gh repo view jugonzal/architect-loop`): the repository is public, so an unauthenticated
  `/version` shows only a commit anyone can already see (command-center/D24, D32). (Corrected 2026-10-20: this
  said the repository was private.)

### Approach

Per command-center/D31 and D32, and D1 here:

- `scripts/gcp/bootstrap.sh <env>` creates or confirms the environment's project, links billing, enables Cloud
  Run, Artifact Registry and Secret Manager, and creates the registry, a deploy identity and the project's budget
  alert (per D2). It is idempotent and prints what it changed. The owner runs it, because it spends money and
  grants IAM roles.
- `scripts/gcp/deploy.sh <service> <env> <sha>` checks that `<sha>` is on `origin/main`, builds
  `services/<service>/Dockerfile` with the repository root as context, tags the image with the SHA, and deploys it
  to Cloud Run with the SHA in an environment variable that the service's `/version` returns. The owner runs it.
- `scripts/gcp/probe/` is a minimal container that follows the convention, so C2 can be proven before any real
  service exists.
- `docs/runbooks/deploy.md` is written with `/loop-runbook` and corrected after the first real run.
- `LOOP.md` §3 gets one row per service and environment (status, runner, threads, notifications), each with its
  `/version` URL. Agents may read them, because `/version` needs no credentials. A row for a service not yet
  deployed fails to read and shows `unknown`, which is true. §4 gets the deploy and verify commands.
- The services' hosts join the independence pattern in `scripts/check.sh`, with a planted-host test.

Per command-center/D43 this concern ships to `main`: its work is scripts the owner runs from `main`. C1 and C2 are
proven by running them from a commit on `main` against staging's and then production's project, and their
evidence lines cite that commit as `main @<sha>`, with the projects named in the line. Per command-center/D54,
phase 1 proves them on staging only. Staging's bootstrap ran on 2026-10-22 (project `loops-512401`, per PR #30's
body), which is evidence C1 can be proven from. Per command-center/D46,
`service-manifests` extends `deploy.sh` and `bootstrap.sh` to apply each service's manifest.

Rollback: Cloud Run keeps earlier revisions, so redeploying the previous SHA with the same command restores it.
A failed deploy leaves the previous revision serving, and `/version` shows the old commit. Deleting a project is
the owner's, and gated.

## Decisions

| # | Decision | Decided by, date | Closes |
| --- | --- | --- | --- |
| D1 | Idempotent `gcloud` scripts that the owner runs create the infrastructure, with each step in the runbook. No Terraform. | Juan, 2026-10-20 | Which tool creates the infrastructure |
| D2 | Each project gets its own billing budget, which emails the owner at 50%, 90% and 100% of a monthly amount the owner names when running the bootstrap. | Juan, 2026-10-20 | Q1 |
| D3 | The owner names each environment's GCP project ID in `scripts/gcp/projects.txt` before its first bootstrap, and both scripts refuse an environment until it is named. | Juan, 2026-10-20 | Q2; confirms PR #19 |

## Questions

| # | Question | Blocks | Default if unanswered |
| --- | --- | --- | --- |
| ~~Q1~~ | ~~Does each project get a billing budget alert, and at what amount?~~ → D2 | | |
| ~~Q2~~ | ~~Where are the project IDs recorded, when they exist only once the owner picks them? (raised by this concern's build)~~ → D3 | | |

## Evidence

- 2026-10-22 · C1 · HOLDS · rung 1 · main @18b866b · Staging only; production's run belongs to the later loop (per command-center/D54). The owner ran `bootstrap.sh staging` twice on project loops-512401 (number 665570365697). The first run printed what `docs/runbooks/deploy.md` step 3 says, by the owner's account; its commit and output were not kept. The second, from 18b866b, printed `staging: 0 changes.` and no `changed` line. Its `ok` lines are `gcloud` reads, and show billing linked, the 7 APIs (`common.sh`'s 5 and threads' 2), the `services` repository in us-east1, `deploy@` holding `roles/run.admin`, `roles/artifactregistry.writer` and `roles/iam.serviceAccountUser` with the owner allowed to act as it, and the budget `loops-512401-monthly` at 25 CAD a month. `gcloud billing budgets list` then showed that budget scoped to `projects/665570365697`, monthly, with threshold rules at 0.5, 0.9 and 1.0 of current spend. The bootstrap's inputs (`scripts/gcp/`, the manifests) are identical on main from 84feb91, which first names the project, to 18b866b, so both runs read the same ones. Departures from Prove: there is no listing after the first run, and the bootstrap's `ok` line for the budget reads only its name and amount, so its thresholds come from the listing alone. One other budget on the billing account, not scoped to this project and not made by the bootstrap, is not counted
- 2026-10-22 · C1 · HOLDS · rung 1 · main @92f6df9 · Re-proved after PR #35 (92f6df9) changed `docs/runbooks/deploy.md`. Staging only (per command-center/D54). The owner ran `bootstrap.sh staging` again, from 92f6df9, and it ended `staging: 0 changes. Project loops-512401, number 665570365697, region us-east1.` The owner reported that summary line; the rest of the output was not kept. `bootstrap.sh` counts one change for each resource it creates, links, grants or updates, and reads every one first. So 0 changes means the project, its billing link, the APIs, the `services` repository, the deploy identity with its roles, and the budget were all already in place. `gcloud billing budgets list` showed `loops-512401-monthly` with the same etag as at the previous proof: 25 CAD a month, scoped to `projects/665570365697`, with threshold rules at 0.5, 0.9 and 1.0 of current spend. The bootstrap's inputs are identical at 18b866b and 92f6df9. Departure from Prove: besides the budget, nothing was listed after this run; the 18b866b run's `ok` lines, in the line above, are the last full read
- 2026-10-23 · C1 · HOLDS · rung 1 · main @a88018e · Re-proved after PR #46 (a88018e) changed `LOOP.md`. Staging only (per command-center/D54). The owner ran `bootstrap.sh staging` twice from a88018e on project loops-512401 (number 665570365697). The first run printed 4 `changed` lines, all for what the manifests gained since 92f6df9 (PRs #41 and #42): the Firestore API, `roles/datastore.user` for `runner@`, the `status@` identity and the Firestore database `runner`. Everything this claim covers read back `ok` and unchanged: the billing link, the `services` repository in us-east1, `deploy@` with `roles/run.admin`, `roles/artifactregistry.writer` and `roles/iam.serviceAccountUser`, the owner's right to act as it, and the budget. The second run printed `staging: 0 changes.` and no `changed` line. `gcloud billing budgets list` showed `loops-512401-monthly` with the same etag as at 18b866b and 92f6df9: 25 CAD a month, scoped to `projects/665570365697`, with threshold rules at 0.5, 0.9 and 1.0 of current spend. Departure from Prove: besides the budget, nothing was listed; each run's `ok` lines are its `gcloud` reads
- 2026-10-26 · C1 · UNPROVEN · — · main @4de7fe2 · Stale: since a88018e, bbf959c changed `scripts/gcp/bootstrap.sh` (+38 lines), `common.sh` and `manifest.py` (manifest schedules), so the a88018e proof does not cover what main runs now. Needs the owner to run `bootstrap.sh staging` twice from main and report each run's summary and `changed` lines, plus `gcloud billing budgets list`; this session has no `gcloud` and no credentials
- 2026-10-26 · C2 · UNPROVEN · — · main @4de7fe2 · Never proven. Needs the owner to run `deploy.sh probe staging <sha>` by `docs/runbooks/deploy.md` from a commit on main, read its `/version`, and try a commit only on a branch; deploying is the owner's (LOOP.md §2). This session also could not read staging's `/version` URLs: `served.sh` needs `curl`, which is not installed here, so every read failed before any request was made, which says nothing about staging
- 2026-10-26 · C3 · UNPROVEN · rung 5 · main @4de7fe2 · Half proven. The independence half holds: `python3 -m unittest tests.test_layout -k host` ran 3 tests, all passing (a planted `status-123456789012.us-east1.run.app` and a hash-style `runner-x7k2q4abcd-ue.a.run.app` each fail the check and are named in its output; a host outside the services passes), `scripts/check.sh` printed `ok independence` locally, and CI's `check`, `runner`, `app`, `status-service` and `local` jobs all succeeded on 4de7fe2. Not proven: `/loop-status` from an installed release reading every §3 row, with `unknown` for services not deployed. Production's rows are still TODO(owner), and the staging reads need a machine with `curl`. Any session with `curl` and an installed release can close this
- 2026-10-27 · C1 · UNPROVEN · — · main @049b797 · Still stale, as on 2026-10-26: nothing under this concern's touches changed from 4de7fe2 to 049b797 (`git log 4de7fe2..049b797` on them is empty), so the gap stands. Needs the owner to run `bootstrap.sh staging` twice from main and report each run's summary and `changed` lines, plus `gcloud billing budgets list`; this session has no `gcloud` and no credentials
- 2026-10-27 · C2 · UNPROVEN · rung 3 · main @049b797 · Half proven. The refusal half holds: from a checkout of 049b797, `sh scripts/gcp/deploy.sh probe staging 06f4b37` (a commit on an origin branch, not an ancestor of origin/main) printed `deploy: refusing 06f4b372…: it is not on origin/main. Only a commit on main is deployed (command-center/D32).` and exited 1. That check runs before any `gcloud` call, and this machine has no `gcloud`, so nothing reached staging. Not proven: deploying the probe and reading its `/version`, which is the owner's. Related but not proof of it: unauthenticated GETs (Python urllib, 1 read each) of staging's `/version` returned 200 for all four services, each with a commit on main: status 633cbe4, runner b2fbcfb, threads 1eae0a3, notify 633cbe4. Which command deployed them is not known here
- 2026-10-27 · C3 · UNPROVEN · rung 5 · main @049b797 · Half proven. The independence half holds again: `python3 -m unittest tests.test_layout -k host` ran 3 tests, all OK; `sh scripts/check.sh` printed `ok   independence`; CI's `check`, `app`, `status-service`, `runner` and `local` all succeeded on 049b797. Not proven: the installed release v0.4.0's `loop_status.py command-center/environments --json` read all 15 §3 rows: main gave 049b797, production's four service rows gave TODO(owner), both app rows said agents may not read them, and every local and staging row failed with `served: GET … failed`. The staging failures are this machine's: it has no `curl`, which `served.sh` needs, while the GETs in C2's line reached all four. So the status board here shows staging as unknown although staging serves, which is not what the claim says. Any session with `curl` and an installed release can close this

## Shipped
