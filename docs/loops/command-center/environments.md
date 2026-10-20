---
needs: [one-repository]
touches: [LOOP.md, scripts/gcp/, docs/runbooks/deploy.md, scripts/check.sh, tests/test_layout.py]
effects: [two GCP projects, staging and production, linked to the owner's billing account (spending; cloud IAM; the owner runs the scripts that create them), an Artifact Registry repository and a deploy identity in each (spending; cloud IAM), new LOOP.md §3 rows and §4 deploy and verify commands (a change to the contract; the owner merges it), every deploy (the owner runs it, per LOOP.md §2)]
ships-to: production
---
# Any service can be deployed from a commit on main to staging or production with one command

## Done when

- **C1** Staging and production are separate GCP projects in `us-east1`, each with an Artifact Registry repository,
  a deploy identity and a budget alert of its own (per D2). Idempotent `gcloud` scripts that the owner runs create
  them, so a second run changes nothing (per D1, command-center/D8, command-center/D32). Prove: run each
  environment's bootstrap twice and list its resources and budget after each run, on staging and production.
- **C2** One command builds a service's image from a commit on `main` and deploys it to an environment by the
  convention in command-center/D32, and its `/version` then prints that commit. It refuses a commit that is not on
  `main`. Prove: deploy the probe in `scripts/gcp/probe/` by the runbook and read its `/version`, and try a commit
  that is only on a branch, on staging and production.
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
  before the first bootstrap.
- Verified 2026-10-20 (`gh repo view jugonzal/architect-loop`): the repository is private, so an unauthenticated
  `/version` would show commits of a private repository until it goes public (command-center/D24). After that,
  the commit is public anyway (command-center/D32).

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

Rollback: Cloud Run keeps earlier revisions, so redeploying the previous SHA with the same command restores it.
A failed deploy leaves the previous revision serving, and `/version` shows the old commit. Deleting a project is
the owner's, and gated.

## Decisions

| # | Decision | Decided by, date | Closes |
| --- | --- | --- | --- |
| D1 | Idempotent `gcloud` scripts that the owner runs create the infrastructure, with each step in the runbook. No Terraform. | Juan, 2026-10-20 | Which tool creates the infrastructure |
| D2 | Each project gets its own billing budget, which emails the owner at 50%, 90% and 100% of a monthly amount the owner names when running the bootstrap. | Juan, 2026-10-20 | Q1 |

## Questions

| # | Question | Blocks | Default if unanswered |
| --- | --- | --- | --- |
| ~~Q1~~ | ~~Does each project get a billing budget alert, and at what amount?~~ → D2 | | |

## Evidence

## Shipped
