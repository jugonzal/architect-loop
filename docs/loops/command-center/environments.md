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
  has not been bootstrapped. No service is deployed to staging: all four answer 404. `docs/runbooks/deploy.md`
  still reads "not yet run".)
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

## Shipped
