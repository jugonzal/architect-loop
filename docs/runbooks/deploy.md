# Runbook: create an environment, and deploy a service to it from a commit on main

**Status:** draft — not yet run | **Last run as written:** never

Use this to create staging or production on GCP, or to check one, and to deploy a service (or the probe) from a
commit on `main`. Afterwards the environment's project exists with its registry, deploy identity and budget, and
the service's `/version` answers the commit that was deployed. Written from `scripts/gcp/` before its first real
run (command-center/environments): every expected output below is what the scripts print, and every failure
signature is what Google Cloud is known to answer, not what a run here showed. Correct it after the first run.

## Quick reference

```bash
sh scripts/gcp/bootstrap.sh staging --billing-account=<BILLING_ACCOUNT_ID> --budget=<AMOUNT>   # e.g. --budget=25USD
sh scripts/gcp/bootstrap.sh staging --billing-account=<BILLING_ACCOUNT_ID> --budget=<AMOUNT>   # again: "0 changes"
git fetch origin && sh scripts/gcp/deploy.sh probe staging "$(git rev-parse origin/main)"
sh scripts/gcp/served.sh https://probe-<PROJECT_NUMBER>.us-east1.run.app/version "$(git rev-parse origin/main)"
sh scripts/gcp/deploy.sh <service> production <SHA>
```

## Preconditions

- The owner runs every step that changes GCP: creating projects and linking billing (spending), grants (cloud
  IAM), and every deploy (LOOP.md §2). Agents may run only `served.sh`, which needs no credentials.
- A checkout of `main` that is up to date (`git switch main && git pull`), because the scripts and
  `scripts/gcp/projects.txt` are read from the working tree, while the image is always built from the commit.
- `gcloud` signed in as the owner: `gcloud auth list` marks the account active. The account must be able to link
  the billing account (Billing Account Administrator or User on it). Budget emails go to those roles.
- Docker running, able to build for linux/amd64 (Docker Desktop does this on Apple silicon). `git`, `curl`, `sh`.
- Expected cost at idle: close to nothing, per Google's published pricing rather than anything measured here. Cloud
  Run scales to zero, and Artifact Registry charges for stored images beyond its free tier. The budget is the
  backstop (environments/D2).

## Steps

### 1. Name the projects

Replace each `TODO(owner)` in `scripts/gcp/projects.txt` with a project ID, then check that it is free in your
account:

```bash
gcloud projects list --filter='projectId:<PROJECT_ID>' --format='value(projectId)'
```

- **Success prints:** nothing.
- **Failure looks like:** the ID is printed: a project with that ID already exists in your account. Bootstrap
  would adopt it as it is, so choose a new ID unless that is what you want.
- **Safe to re-run:** yes. Commit `projects.txt` on a branch and merge it, so that everyone deploys to the same
  projects.

### 2. Find the billing account

```bash
gcloud billing accounts list
```

- **Success prints:** a row with `OPEN` `True`. Its `ACCOUNT_ID` is `<BILLING_ACCOUNT_ID>`.
- **Failure looks like:** no rows: the account has no billing account, or no role on one.
- **Safe to re-run:** yes; it only reads.

### 3. Bootstrap staging

```bash
sh scripts/gcp/bootstrap.sh staging --billing-account=<BILLING_ACCOUNT_ID> --budget=<AMOUNT>
```

`<AMOUNT>` is a whole monthly amount, optionally with the billing account's currency, e.g. `25USD`.

- **Success prints:** `bootstrap staging: project <PROJECT_ID> in us-east1, as <you>`, then one `changed` line
  each for the project, the billing link, the APIs, the `services` repository, the deploy identity
  `deploy@<PROJECT_ID>.iam.gserviceaccount.com`, its three roles, your right to act as it, and the budget
  `<PROJECT_ID>-monthly`. It ends with `staging: 10 changes. Project <PROJECT_ID>, number <PROJECT_NUMBER>, region
  us-east1.` and four lines `staging/<service>  sh scripts/gcp/served.sh https://<service>-<PROJECT_NUMBER>.us-east1.run.app/version`.
  Keep those four lines for step 5.
- **Failure looks like:**
  - `TODO(owner): name staging's GCP project ID in scripts/gcp/projects.txt first`: step 1 is not done.
  - `gcloud.projects.create` says the ID is already in use: someone else holds it (IDs are global and never
    reused). Choose another in step 1.
  - The billing link is denied (`billing.resourceAssociations.create`): your account has no role on that billing
    account.
  - `... is linked to billing account <X>, not <Y>; not changing it`: the project is already billed elsewhere. The
    script never moves billing; do it by hand if you mean to, then re-run.
  - Enabling the APIs fails because billing is not enabled yet: the link has not taken effect. Wait a minute and
    re-run.
  - `retrying in 10 s (n of 4)` lines: a grant or call that Google Cloud has not caught up with yet. The script
    tries 5 times; if it still fails, wait and re-run.
- **Safe to re-run:** yes. Every step reads first and changes only what is missing. It never relinks billing,
  deletes anything or removes a grant. This step spends money: the project is billed from now on.

### 4. Run it again, and list what it made (C1)

```bash
sh scripts/gcp/bootstrap.sh staging --billing-account=<BILLING_ACCOUNT_ID> --budget=<AMOUNT>
gcloud services list --enabled --project=<PROJECT_ID> --format='value(config.name)'
gcloud artifacts repositories list --project=<PROJECT_ID> --location=us-east1
gcloud iam service-accounts list --project=<PROJECT_ID>
gcloud projects get-iam-policy <PROJECT_ID> --flatten='bindings[].members' --filter='bindings.members:serviceAccount:deploy@<PROJECT_ID>.iam.gserviceaccount.com' --format='value(bindings.role)'
gcloud billing budgets list --billing-account=<BILLING_ACCOUNT_ID> --billing-project=<PROJECT_ID>
```

- **Success prints:** the bootstrap prints only `ok` lines and `staging: 0 changes.` The APIs include
  `run.googleapis.com`, `artifactregistry.googleapis.com`, `secretmanager.googleapis.com`,
  `iamcredentials.googleapis.com` and `billingbudgets.googleapis.com`. The repository `services` is `DOCKER` in
  `us-east1`. `deploy@<PROJECT_ID>.iam.gserviceaccount.com` is listed and holds `roles/artifactregistry.writer`,
  `roles/iam.serviceAccountUser` and `roles/run.admin`. One budget, `<PROJECT_ID>-monthly`, has the amount you named
  and thresholds 0.5, 0.9 and 1.0.
- **Failure looks like:** any `changed` line on the second run: the step that printed it is not idempotent.
  Record it as a trap and flag `scripts/gcp/bootstrap.sh` for `/loop-build`.
- **Safe to re-run:** yes. Keep both runs' output and the listings: they are C1's evidence for `/loop-prove`.

### 5. Fill in LOOP.md §3

In each `staging/<service>` row, replace the `TODO(owner)` served-commit cell with that service's line from step
3 (in backticks), and `<URL>` in its verify cell with the URL. Merge that change through a pull request: it changes
the contract, so the owner merges it.

```bash
sh scripts/gcp/served.sh https://status-<PROJECT_NUMBER>.us-east1.run.app/version
```

- **Success prints:** until `status` is deployed, `curl: (22) The requested URL returned error: 404` and
  `served: GET ... failed`, with exit status 1, and `/loop-status` shows that row as unknown, which is true.
- **Failure looks like:** a DNS error rather than a 404: the URL is mistyped, or the project number is wrong.
- **Safe to re-run:** yes.

### 6. Deploy the probe from main (C2)

```bash
git fetch origin && sha=$(git rev-parse origin/main)
sh scripts/gcp/deploy.sh probe staging "$sha"
```

- **Success prints:** `deploy probe to staging: commit <SHA>, project <PROJECT_ID>, region us-east1`, the docker
  build, `Login Succeeded`, the push, gcloud's deploy progress with
  `Service URL: https://probe-<PROJECT_NUMBER>.us-east1.run.app`, and last
  `deployed probe to staging: https://probe-<PROJECT_NUMBER>.us-east1.run.app/version answers <SHA>`.
- **Failure looks like:**
  - `deploy: refusing <SHA>: it is not on origin/main`: the commit is not on main. Expected in step 8.
  - `Cannot connect to the Docker daemon`: start Docker.
  - `gcloud.auth.print-access-token` is denied `iam.serviceAccounts.getAccessToken`: the right to act as the
    deploy identity, granted in step 3, has not reached IAM yet. That can take minutes. Wait and re-run.
  - The push is denied `artifactregistry.repositories.uploadArtifacts`: the same delay, or a grant is missing.
    Re-run step 3, then this step.
  - `gcloud run deploy` is denied `iam.serviceaccounts.actAs` on `<PROJECT_NUMBER>-compute@developer.gserviceaccount.com`:
    the deploy identity cannot run the service as the project's default runtime identity. Re-run step 3. If the
    error says that account does not exist, the project has no default runtime identity: stop, record it as a
    trap, and take it to `/loop-design`, which has not decided which identity services run as.
  - Cloud Run rejects the image because it does not support amd64/linux: the build did not target linux/amd64.
    `deploy.sh` asks for it, so check that Docker can build for that platform.
  - The deploy succeeds but `served: ... serves <old SHA>, not <SHA>`: traffic is pinned to an older revision (see
    Rollback). `gcloud run services update-traffic probe --to-latest --region=us-east1 --project=<PROJECT_ID>`.
- **Safe to re-run:** yes. Each run deploys a new revision of the same commit. `docker login` leaves a token for
  `us-east1-docker.pkg.dev` in Docker's credentials, which expires within the hour.

### 7. Read /version

```bash
sh scripts/gcp/served.sh https://probe-<PROJECT_NUMBER>.us-east1.run.app/version "$sha"
curl -s https://probe-<PROJECT_NUMBER>.us-east1.run.app/version
```

- **Success prints:** the SHA, with exit status 0; and `{"commit": "<SHA>"}`. Neither needs credentials.
- **Failure looks like:** `served: ... serves <X>, not <SHA>`: see step 6. A 403: `/version` is not public, so
  `--allow-unauthenticated` did not apply (an organization policy can forbid it).
- **Safe to re-run:** yes; it only reads.

### 8. Try a commit that is not on main (C2's refusal)

```bash
git switch -c probe/refusal && git commit --allow-empty -m "Check that deploy refuses a commit not on main"
sh scripts/gcp/deploy.sh probe staging "$(git rev-parse HEAD)"; echo "exit $?"
git switch main && git branch -D probe/refusal
```

- **Success prints:** `deploy: refusing <SHA>: it is not on origin/main. Only a commit on main is deployed
  (command-center/D32).` and `exit 1`. Nothing is built or deployed, and step 7 still prints the earlier SHA.
- **Failure looks like:** a build starts: stop it (Ctrl-C) and flag `scripts/gcp/deploy.sh` for `/loop-build`.
- **Safe to re-run:** yes. The branch is local and deleted at the end.

### 9. Production

Repeat steps 3 to 8 with `production` in place of `staging`. Its budget may be a different amount.

## Verify

```bash
sh scripts/gcp/bootstrap.sh <staging|production> --billing-account=<BILLING_ACCOUNT_ID> --budget=<AMOUNT>
sh scripts/gcp/served.sh https://<service>-<PROJECT_NUMBER>.us-east1.run.app/version <SHA>
```

The bootstrap prints `0 changes`, and `served.sh` prints the deployed SHA with exit status 0. Then `/loop-status`,
from an installed release, shows each §3 row with its served commit, or unknown for a service not yet deployed.

## Rollback

- **A bad deploy:** deploy the previous commit with the same command,
  `sh scripts/gcp/deploy.sh <service> <env> <PREVIOUS_SHA>`. It rebuilds that commit's image and checks
  `/version`. A deploy that fails leaves the previous revision serving. Do not roll back with
  `gcloud run services update-traffic --to-revisions`: traffic stays pinned to that revision, and later deploys
  then receive none.
- **The probe:** it can stay, since it scales to zero. Deleting it is
  `gcloud run services delete probe --region=us-east1 --project=<PROJECT_ID>`.
- **What does not roll back:** the bootstrap. The project, its billing link, the APIs, the repository, the deploy
  identity, its grants and the budget stay until removed by hand. Removing a whole environment is
  `gcloud projects delete <PROJECT_ID>`, the owner's and gated: the project can be restored for a while after,
  and its ID can never be used again. Money spent, images pushed and budget emails sent do not roll back either.

## Traps

Each learned in a real run. Newest first.

- None yet: this runbook has not been run.

## Corrections

- None yet.
