# Runbook: create an environment, and deploy a service to it from a commit on main

**Status:** draft — partly run (steps 1 to 5 and 13, on staging) | **Last run as written:** 2026-10-23 on
staging by Juan, step 13's three exports; the deploys' own output was not reported. Before that, on 2026-10-22,
steps 2 and 3, and step 4's second bootstrap. Step 1 ran then too (PR #29). Step 5 ran with output that differed
from this runbook (see Corrections). Step 13 succeeding means steps 9, 11 and 12 had been done, but their output is
not recorded here, and neither is a run of step 4's listings or of steps 6 to 8, 10, 14 or 15.

Use this to create staging or production on GCP, or to check one, and to deploy a service (or the probe) from a
commit on `main` with exactly the config its manifest declares. Afterwards the environment's project exists with its
registry, deploy identity, budget and what the services' manifests declare (APIs, runtime identities, Firestore
databases), and the service's `/version` answers the commit that was deployed. Written from `scripts/gcp/` before
its first real run (command-center/environments, command-center/service-manifests): every expected output below is
what the scripts print against the fakes in `tests/`, and every failure signature is what Google Cloud is known to
answer, not what a run here showed. Correct it after the first run. Since then steps 2 and 3, and step 4's second
bootstrap, have run on staging and printed what is written. Step 5's outputs and step 13's exports have been read
against staging, and they are written below as observed. Every other step is still as drafted.

## Quick reference

```bash
sh scripts/gcp/bootstrap.sh staging --billing-account=<BILLING_ACCOUNT_ID> --budget=<AMOUNT>   # e.g. --budget=25USD
sh scripts/gcp/bootstrap.sh staging --billing-account=<BILLING_ACCOUNT_ID> --budget=<AMOUNT>   # again: "0 changes"
git fetch origin && sh scripts/gcp/deploy.sh probe staging "$(git rev-parse origin/main)"
sh scripts/gcp/served.sh https://probe-<PROJECT_NUMBER>.us-east1.run.app/version "$(git rev-parse origin/main)"
gcloud secrets create <SECRET> --project=<PROJECT_ID> --replication-policy=automatic --data-file=<FILE>   # each one named
sh scripts/gcp/bootstrap.sh staging --billing-account=<BILLING_ACCOUNT_ID> --budget=<AMOUNT>   # lets each service read its own
sh scripts/gcp/deploy.sh <service> production <SHA>
```

## Preconditions

- The owner runs every step that changes GCP: creating projects and linking billing (spending), grants (cloud
  IAM), secrets, and every deploy (LOOP.md §2). Agents may run only `served.sh`, which needs no credentials.
- A checkout of `main` that is up to date (`git switch main && git pull`), because the scripts,
  `scripts/gcp/projects.txt` and the manifests the bootstrap reads come from the working tree, while a deploy
  always builds and configures from the commit it names. After a merge that changes a manifest's identity, roles,
  APIs, secrets or Firestore databases, or gives a service its first schedule, run the bootstrap again before
  deploying that commit.
- `gcloud` signed in as the owner: `gcloud auth list` marks the account active. The account must be able to link
  the billing account (Billing Account Administrator or User on it). Budget emails go to those roles.
- Docker running, able to build for linux/amd64 (Docker Desktop does this on Apple silicon). `git`, `curl`, `sh`,
  and `python3` (3.8 or later, standard library only), which reads the manifests.
- Expected cost at idle: close to nothing for Cloud Run, Artifact Registry and Firestore, per Google's published
  pricing rather than anything measured here. Cloud Run scales to zero, and Artifact Registry charges for stored
  images beyond its free tier. Cloud Scheduler, once a manifest declares a schedule, costs $0.10 per job per 31
  days, with the first 3 jobs per billing account free (read 2026-10-24 from
  https://cloud.google.com/scheduler/pricing), and each call it makes is a Cloud Run request. A Cloud SQL instance
  (step 10) is billed while it exists, whether used or not. The
  budget is the backstop (environments/D2).

## The manifest

Each service's deploy config is `services/<service>/service.json`; the probe's is `scripts/gcp/probe/service.json`
(command-center/D46). It is reviewed in pull requests like code, `deploy.sh` applies the one in the commit it
deploys, and `bootstrap.sh` creates what the ones in the working tree declare. `scripts/gcp/manifest.py` reads it,
and both scripts refuse a manifest that does not fit before they call gcloud, naming every problem.

| Field | What | Who acts on it |
| --- | --- | --- |
| `identity` | Required. `{"name": "<service account ID>", "roles": ["roles/...", ...]}`. The service and its jobs run as `<name>@<PROJECT_ID>.iam.gserviceaccount.com`. | The bootstrap creates it and grants the roles on the project. |
| `apis` | APIs beyond those every project has (`APIS` in `common.sh`). `cloudsql` needs `sqladmin.googleapis.com` and `sql-component.googleapis.com`; `firestore` needs `firestore.googleapis.com`. | The bootstrap enables them. |
| `settings` | Environment variables by value: `{"NAME": "value"}`, or `{"NAME": {"staging": "...", "production": "..."}}`. A value may use `{project}`, `{number}` and `{region}`. `"TODO(owner)"` is a value only the owner can name. | Every deploy sets exactly these, plus `COMMIT_SHA` (command-center/D47). A deploy refuses a value still `TODO(owner)` for its environment. |
| `secrets` | Environment variables from Secret Manager: `{"NAME": "<secret name>"}`, at its latest version. Never a value. | The owner creates each secret (step 9). The bootstrap lets the service's identity read the ones its manifest names, and no others. Every deploy mounts exactly these. |
| `cloudsql` | The Cloud SQL instance the service connects to, by name, in the environment's project and region. | The owner creates it (step 10). Every deploy attaches exactly it, or none. |
| `firestore` | The Firestore databases the service uses, by ID (command-center/D44). | The bootstrap creates each in us-east1, in native mode. |
| `jobs` | `{"<job>": {"command": [...], "tasks": n, "max_retries": n, "task_timeout_s": n, "settings": {...}, "secrets": {...}}}`: Cloud Run jobs from the service's image. A job runs as the service's identity, with the service's settings, secrets and Cloud SQL instance plus its own. | Every deploy deploys each job, before the service. |
| `schedules` | `{"<name>": {"cron": "* * * * *", "time_zone": "Etc/UTC", "path": "/tick"}}`: Cloud Scheduler jobs that call the service (command-center/D67). `cron` is five fields; `time_zone` a tz database name; `path` starts with `/`. Each is the Cloud Scheduler job `<service>-<name>` in us-east1, which POSTs to `https://<service>-<PROJECT_NUMBER>.us-east1.run.app<path>` with an OIDC token for the service's identity and that URL as the audience, so the service checks the token as it checks any caller's. Its finest schedule is once a minute. | The bootstrap enables Cloud Scheduler (no need to list it in `apis`), gives the deploy identity `roles/cloudscheduler.admin`, and lets Cloud Scheduler's service agent mint tokens as the identity. Every deploy, once `/version` answers the commit, creates or updates each one and deletes the service's jobs (those calling its URL) the manifest no longer declares (step 16). |

Nothing else is allowed. No manifest may set `COMMIT_SHA`, `PORT` or Cloud Run's other own variables, or a
setting whose name says it holds a secret (`KEY`, `SECRET`, `PASSWORD`, `TOKEN`, `CREDENTIAL`, `DATABASE_URL`).

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
  each for the project, the billing link, the APIs (the five every project has, then `sqladmin.googleapis.com` and
  `sql-component.googleapis.com` from threads' manifest), the `services` repository, the deploy identity
  `deploy@<PROJECT_ID>.iam.gserviceaccount.com`, its three roles, your right to act as it, the runtime identities
  `runner@`, `threads@` and `probe-runtime@<PROJECT_ID>.iam.gserviceaccount.com`, `roles/run.jobsExecutorWithOverrides`
  for the runner and `roles/cloudsql.client` for threads, and the budget `<PROJECT_ID>-monthly`. Five
  `missing  secret <SECRET>, which <service> names` lines name the secrets step 9 creates. With the manifests on
  main when this was written, it ends with `staging: 15 changes. Project <PROJECT_ID>, number <PROJECT_NUMBER>,
  region us-east1.`, the list of secrets to create, and four lines
  `staging/<service>  sh scripts/gcp/served.sh https://<service>-<PROJECT_NUMBER>.us-east1.run.app/version`.
  Keep those four lines for step 5.
- **Failure looks like:**
  - `TODO(owner): name staging's GCP project ID in scripts/gcp/projects.txt first`: step 1 is not done.
  - `manifest: services/<service>/service.json does not fit the manifest format`, with the reasons: nothing was
    read or changed in Google Cloud. Fix the manifest in a pull request (or update the checkout), then re-run.
  - `gcloud.projects.create` says the ID is already in use: someone else holds it (IDs are global and never
    reused). Choose another in step 1.
  - The billing link is denied (`billing.resourceAssociations.create`): your account has no role on that billing
    account.
  - `... is linked to billing account <X>, not <Y>; not changing it`: the project is already billed elsewhere. The
    script never moves billing; do it by hand if you mean to, then re-run.
  - Enabling the APIs fails because billing is not enabled yet: the link has not taken effect. Wait a minute and
    re-run.
  - A grant fails with `INVALID_ARGUMENT` naming a role: Google Cloud does not offer that role on a project. Record
    it as a trap and take the manifest's `roles` to `/loop-build`. (`roles/run.jobsExecutorWithOverrides` was
    granted on staging on 2026-10-22, so a project accepts it. Whether it is enough for the runner to start its
    job is unproven until a dispatch. If it is not, `roles/run.developer` also lets the runner start its job, with
    more rights.)
  - `retrying in 10 s (n of 4)` lines: a grant or call that Google Cloud has not caught up with yet. The script
    tries 5 times; if it still fails, wait and re-run.
- **Safe to re-run:** yes. Every step reads first and changes only what is missing. It never relinks billing,
  deletes anything, removes a grant or creates a secret. This step spends money: the project is billed from now on.

### 4. Run it again, and list what it made (environments C1, service-manifests C2)

```bash
sh scripts/gcp/bootstrap.sh staging --billing-account=<BILLING_ACCOUNT_ID> --budget=<AMOUNT>
gcloud services list --enabled --project=<PROJECT_ID> --format='value(config.name)'
gcloud artifacts repositories list --project=<PROJECT_ID> --location=us-east1
gcloud iam service-accounts list --project=<PROJECT_ID>
gcloud projects get-iam-policy <PROJECT_ID> --flatten='bindings[].members' --filter='bindings.members:serviceAccount:deploy@<PROJECT_ID>.iam.gserviceaccount.com' --format='value(bindings.role)'
gcloud projects get-iam-policy <PROJECT_ID> --flatten='bindings[].members' --filter='bindings.members:serviceAccount:runner@<PROJECT_ID>.iam.gserviceaccount.com' --format='value(bindings.role)'
gcloud projects get-iam-policy <PROJECT_ID> --flatten='bindings[].members' --filter='bindings.members:serviceAccount:threads@<PROJECT_ID>.iam.gserviceaccount.com' --format='value(bindings.role)'
gcloud firestore databases list --project=<PROJECT_ID> --format='value(name)'
gcloud billing budgets list --billing-account=<BILLING_ACCOUNT_ID> --billing-project=<PROJECT_ID>
```

- **Success prints:** the bootstrap prints only `ok` and `missing  secret` lines and `staging: 0 changes.`, then the
  same closing lines as step 3: the secrets to create, the four served-commit lines and `Next:`. Each `ok` line
  comes from a `gcloud` read of the same thing a listing below shows, except one. The budget's `ok` line checks only
  its name and amount, so only the budget listing shows its alert thresholds. The APIs
  include `run.googleapis.com`, `artifactregistry.googleapis.com`, `secretmanager.googleapis.com`,
  `iamcredentials.googleapis.com`, `billingbudgets.googleapis.com`, `sqladmin.googleapis.com` and
  `sql-component.googleapis.com`. The repository `services` is `DOCKER` in `us-east1`. The accounts listed include
  `deploy@`, `runner@`, `threads@` and `probe-runtime@<PROJECT_ID>.iam.gserviceaccount.com`. The deploy identity
  holds `roles/artifactregistry.writer`, `roles/iam.serviceAccountUser` and `roles/run.admin`, the runner
  `roles/run.jobsExecutorWithOverrides`, and threads `roles/cloudsql.client`. Firestore lists a
  `projects/<PROJECT_ID>/databases/<ID>` line for each database a manifest declares (none until `runner-store`
  adds the runner's). One budget, `<PROJECT_ID>-monthly`, has the amount you named and thresholds 0.5, 0.9 and 1.0.
- **Failure looks like:** any `changed` line on the second run: the step that printed it is not idempotent.
  Record it as a trap and flag `scripts/gcp/bootstrap.sh` for `/loop-build`.
- **Safe to re-run:** yes. Keep both runs' output and the listings: they are the evidence for `/loop-prove`.

### 5. Fill in LOOP.md §3

In each `staging/<service>` row, replace the `TODO(owner)` served-commit cell with that service's line from step
3 (in backticks), and `<URL>` in its verify cell with the URL. Merge that change through a pull request: it changes
the contract, so the owner merges it.

```bash
sh scripts/gcp/served.sh https://status-<PROJECT_NUMBER>.us-east1.run.app/version
curl -s -o /dev/null -w '%{http_code} %{size_download}\n' https://status-<PROJECT_NUMBER>.us-east1.run.app/version
```

- **Success prints:** until `status` is deployed, `curl: (56) The requested URL returned error: 404` (the curl
  macOS ships, 8.7.1, over HTTP/2; other versions print `curl: (22)`) and `served: GET ... failed`, with exit
  status 1, and `/loop-status` shows that row as unknown, which is true. The second command prints `404 0`: an
  empty 404, which is what a project answers for a service it does not have.
- **Failure looks like:** a 404 with a size above 0 (`404 272` here), an HTML body that says "Error: Page not
  found": the project number or the region in the URL is wrong. Cloud Run answers every `*.run.app` name, so a wrong URL never fails DNS, and
  `served.sh` prints the same lines for it as for a service not yet deployed. A mistyped service name in the right
  project answers the same empty 404 as an undeployed service, so compare each name with step 3's lines.
- **Safe to re-run:** yes; it only reads.

### 6. Deploy the probe from main (environments C2, service-manifests C1)

```bash
git fetch origin && sha=$(git rev-parse origin/main)
sh scripts/gcp/deploy.sh probe staging "$sha"
```

- **Success prints:** `deploy probe to staging: commit <SHA>, project <PROJECT_ID>, region us-east1`, then
  `config from scripts/gcp/probe/service.json: runs as probe-runtime@<PROJECT_ID>.iam.gserviceaccount.com`,
  `settings  COMMIT_SHA`, `secrets   none`, `Cloud SQL none`, the docker build, `Login Succeeded`, the push,
  gcloud's deploy progress with `Service URL: https://probe-<PROJECT_NUMBER>.us-east1.run.app`, and last
  `deployed probe to staging: https://probe-<PROJECT_NUMBER>.us-east1.run.app/version answers <SHA>`.
- **Failure looks like:**
  - `deploy: refusing <SHA>: it is not on origin/main`: the commit is not on main. Expected in step 8.
  - `deploy: commit <SHA> has no scripts/gcp/probe/service.json`: the commit predates the manifests. Deploy a
    later commit.
  - `Cannot connect to the Docker daemon`: start Docker.
  - `gcloud.auth.print-access-token` is denied `iam.serviceAccounts.getAccessToken`: the right to act as the
    deploy identity, granted in step 3, has not reached IAM yet. That can take minutes. Wait and re-run.
  - The push is denied `artifactregistry.repositories.uploadArtifacts`: the same delay, or a grant is missing.
    Re-run step 3, then this step.
  - `Service account probe-runtime@<PROJECT_ID>.iam.gserviceaccount.com does not exist`: the bootstrap ran from a
    checkout without the probe's manifest. Update the checkout, re-run step 3, then this step.
  - `gcloud run deploy` is denied `iam.serviceaccounts.actAs` on a runtime identity: the deploy identity's
    `roles/iam.serviceAccountUser` grant has not reached IAM yet. Wait and re-run.
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

### 8. Try a commit that is not on main (environments C2's refusal)

```bash
git switch -c probe/refusal && git commit --allow-empty -m "Check that deploy refuses a commit not on main"
sh scripts/gcp/deploy.sh probe staging "$(git rev-parse HEAD)"; echo "exit $?"
git switch main && git branch -D probe/refusal
```

- **Success prints:** `deploy: refusing <SHA>: it is not on origin/main. Only a commit on main is deployed
  (command-center/D32).` and `exit 1`. Nothing is built or deployed, and step 7 still prints the earlier SHA.
- **Failure looks like:** a build starts: stop it (Ctrl-C) and flag `scripts/gcp/deploy.sh` for `/loop-build`.
- **Safe to re-run:** yes. The branch is local and deleted at the end.

### 9. Create the secrets the manifests name

The bootstrap's `missing  secret` lines name them. Each is the owner's (LOOP.md §2, secrets). With the manifests
on main when this was written:

| Secret | Holds | Comes from |
| --- | --- | --- |
| `runner-app-private-key` | The runner's GitHub App private key (PEM) | The runner's app, which `session-runner` declares |
| `runner-anthropic-api-key` | The Anthropic API key a session's job uses, never the service | The Anthropic console |
| `threads-github-app-private-key` | Threads' GitHub App private key (PEM) | Threads' app, which `threads` declares |
| `threads-github-webhook-secret` | That app's webhook secret | The same app's settings |
| `threads-database-url` | `postgresql://threads:<PASSWORD>@/threads?host=/cloudsql/<PROJECT_ID>:us-east1:threads` | Step 10 |

A key file:

```bash
gcloud secrets create <SECRET> --project=<PROJECT_ID> --replication-policy=automatic --data-file=<PATH_TO_PEM>
```

A value you type, without echoing it or leaving it in the shell's history (zsh or bash):

```bash
read -rs value && printf '%s' "$value" | gcloud secrets create <SECRET> --project=<PROJECT_ID> --replication-policy=automatic --data-file=- ; unset value
```

To replace a value later, `gcloud secrets versions add <SECRET> --project=<PROJECT_ID> --data-file=...`, then
deploy again: a running instance keeps the value it started with.

- **Success prints:** `Created version [1] of the secret [<SECRET>].`
- **Failure looks like:** `ALREADY_EXISTS`: it exists; add a version instead if the value is wrong. A trailing
  newline in a typed value (from `echo` or a pasted line) becomes part of the secret, and the service then fails
  to use it: use `printf '%s'` as above.
- **Safe to re-run:** no for `create` (it fails once the secret exists); yes for `versions add`, which keeps the
  earlier versions. A secret's value never rolls back with a deploy.

### 10. Create threads' Cloud SQL instance

Threads' manifest attaches the instance `threads` in the environment's project and region (its database, `threads`,
is named in `threads-database-url`). Creating it is `threads`' effect, and it is billed while it exists. Check the
tier's price before running; `db-f1-micro` is the smallest shared-core tier.

```bash
gcloud sql instances create threads --project=<PROJECT_ID> --region=us-east1 --database-version=POSTGRES_16 --edition=enterprise --tier=db-f1-micro
gcloud sql databases create threads --instance=threads --project=<PROJECT_ID>
gcloud sql users create threads --instance=threads --project=<PROJECT_ID>
gcloud sql users set-password threads --instance=threads --project=<PROJECT_ID> --prompt-for-password
```

(`users create` takes a password only on the command line, where the shell keeps it; `set-password` prompts for it.)

Then create `threads-database-url` (step 9) with that password, and apply threads' migrations before its first
deploy serves requests (`python -m threads.migrate` from `services/threads/`, per the `threads` concern; a
migration on shared data is the owner's).

- **Success prints:** the instance with `STATUS: RUNNABLE` after some minutes, then `Created database [threads].`,
  `Created user [threads].`, a password prompt, and the update of the user.
- **Failure looks like:** `SERVICE_DISABLED` for `sqladmin.googleapis.com`: step 3 has not enabled it; re-run step
  3. A tier the edition does not offer: pick one the error lists.
- **Safe to re-run:** no: `create` fails once the instance exists. Deleting it deletes every message in it.

### 11. Name the values only the owner knows

The manifests leave `TODO(owner)` where only the owner can name a value: the runner's `RUNNER_APP_ID`,
`RUNNER_APP_INSTALLATION_ID` and `RUNNER_APP_SLUG`, and threads' `THREADS_GITHUB_APP_ID`. Once the apps exist,
replace each in `services/runner/service.json` and `services/threads/service.json` on a branch and merge it. When
staging and production use different apps, write the value as `{"staging": "<ID>", "production": "<ID>"}`.

```bash
grep -n 'TODO(owner)' services/*/service.json
```

- **Success prints:** nothing, once both are named for both environments (or a `TODO(owner)` only inside the
  environment not yet deployed).
- **Failure looks like:** `deploy.sh` later prints `manifest: services/<service>/service.json leaves
  settings.<NAME> TODO(owner) for <env>; name it in a pull request first`, and deploys nothing.
- **Safe to re-run:** yes; it only reads.

### 12. Let each service read its own secrets (service-manifests C2)

```bash
sh scripts/gcp/bootstrap.sh staging --billing-account=<BILLING_ACCOUNT_ID> --budget=<AMOUNT>
sh scripts/gcp/bootstrap.sh staging --billing-account=<BILLING_ACCOUNT_ID> --budget=<AMOUNT>
gcloud secrets get-iam-policy runner-app-private-key --project=<PROJECT_ID>
```

- **Success prints:** the first run prints one `changed  let <identity> read secret <SECRET>
  (roles/secretmanager.secretAccessor)` line per secret, `runner@` for the runner's two and `threads@` for threads'
  three, and `staging: 5 changes.`; the second prints `staging: 0 changes.` and no `missing  secret` line. The
  policy lists `roles/secretmanager.secretAccessor` for `serviceAccount:runner@<PROJECT_ID>.iam.gserviceaccount.com`
  only.
- **Failure looks like:** a `missing  secret` line: step 9 is not done for that secret.
- **Safe to re-run:** yes.

### 13. Deploy the runner and threads, and read their config back (service-manifests C1)

```bash
git fetch origin && sha=$(git rev-parse origin/main)
sh scripts/gcp/deploy.sh runner staging "$sha"
sh scripts/gcp/deploy.sh threads staging "$sha"
gcloud run services describe runner --region=us-east1 --project=<PROJECT_ID> --format=export
gcloud run jobs describe runner-session --region=us-east1 --project=<PROJECT_ID> --format=export
gcloud run services describe threads --region=us-east1 --project=<PROJECT_ID> --format=export
```

To see what each export must hold, render the manifest the way `deploy.sh` does, from the checkout at `$sha` (the
preconditions keep it up to date). It only reads, and needs no credentials:

```bash
python3 scripts/gcp/manifest.py render services/<service>/service.json --name=<service> --env=staging --project=<PROJECT_ID> --region=us-east1 --number=<PROJECT_NUMBER> --commit="$sha" --service=<service> --out=<DIR>
```

It prints the summary the deploy prints, and writes every setting's value to `<DIR>/service.env.yaml` (and, for the
runner, `<DIR>/job-runner-session.env.yaml`), and the identity, secrets and Cloud SQL instance to
`<DIR>/service.flags`.

- **Success prints:** each deploy prints `config from services/<service>/service.json: runs as
  <service>@<PROJECT_ID>.iam.gserviceaccount.com` and its settings, secrets, Cloud SQL instance and (for the
  runner) `job runner-session: python -m runner job; tasks 1, retries 0, timeout 3600 s`, then gcloud's
  progress for the job and the service, and `deployed <service> to staging: ... answers <SHA>`. Each `export`
  shows `serviceAccountName: <service>@<PROJECT_ID>.iam.gserviceaccount.com`; an `env` entry with a `value` for each
  setting and for `COMMIT_SHA: <SHA>`, and one with `valueFrom.secretKeyRef` (`key: latest`) for each secret, and
  nothing else; threads has the annotation `run.googleapis.com/cloudsql-instances: <PROJECT_ID>:us-east1:threads`;
  the job has `maxRetries: 0`, `timeoutSeconds: '3600'` and the command `python` with args `-m runner job`, and
  `ANTHROPIC_API_KEY` among its secrets while the service has not. Also seen on staging on 2026-10-23: the
  runner's service has `run.googleapis.com/cloudsql-instances: ''`, empty, because `deploy.sh` clears the instance
  when a manifest names none; both services have `run.googleapis.com/maxScale: '3'`, which no manifest or script
  here sets, so Cloud Run or gcloud set it; and the job's export has no Cloud SQL annotation.
- **Failure looks like:**
  - `manifest: ... leaves settings.<NAME> TODO(owner) for staging`: step 11 is not done. Nothing was deployed.
  - `manifest: ... does not fit the manifest format`: the commit's manifest is broken. Nothing was deployed; fix it
    in a pull request and deploy that commit.
  - `Permission denied on secret: <SECRET>:latest for Revision service account <identity>`: step 12 is not done,
    or its grant has not reached IAM yet. The previous revision keeps serving.
  - `Secret ... was not found`: step 9 is not done for it.
  - `API [sql-component.googleapis.com] not enabled on project` and `Aborted by user`: the bootstrap that enabled
    threads' APIs has not run in this project. Re-run step 3.
  - `Permission denied` running the job later, from a dispatch: the runner's role from step 3 is missing.
- **Safe to re-run:** yes. Each run deploys new revisions of the same commit with the same config.

### 14. Roll back one commit and read the config again (service-manifests C1)

```bash
sh scripts/gcp/deploy.sh <service> staging <PREVIOUS_SHA>
gcloud run services describe <service> --region=us-east1 --project=<PROJECT_ID> --format=export
sh scripts/gcp/deploy.sh <service> staging "$sha"
```

Pick a `<PREVIOUS_SHA>` on main whose `services/<service>/service.json` differs from `$sha`'s
(`git log --oneline -- services/<service>/service.json`), and that this environment can deploy. This prints
nothing and exits 0 when it can:

```bash
git show <PREVIOUS_SHA>:services/<service>/service.json > <FILE> && python3 scripts/gcp/manifest.py check <FILE> --name=<service> --env=staging
```

If no such commit exists yet, this step waits for the next commit on main that changes the manifest (see Traps,
2026-10-23): deploy that commit with step 13, then roll back to the commit before it.

- **Success prints:** the export shows exactly the previous commit's settings, secrets and Cloud SQL instance, and
  `COMMIT_SHA: <PREVIOUS_SHA>`: a variable added later is gone. The last command restores the current one.
- **Failure looks like:** a variable the previous manifest did not have is still there: the deploy did not
  replace the variables. Record it as a trap and flag `scripts/gcp/deploy.sh` for `/loop-build`.
- **Safe to re-run:** yes.

### 15. Production

Repeat steps 3 to 14, and step 16 once a manifest declares a schedule, with `production` in place of
`staging`. Its budget may be a different amount, and its secrets
and Cloud SQL instance are its own. Step 14 meets the same wait there: the commit that first names production's
values has no earlier commit production can deploy (see Traps, 2026-10-23).

### 16. Deploy a service with schedules, and read them back (service-schedules C2)

Only once a service's manifest declares `schedules` (the first is `notify`'s, per command-center/D67). Run step 3
again first, from a checkout that has that manifest, then deploy it as in step 13:

```bash
sh scripts/gcp/bootstrap.sh staging --billing-account=<BILLING_ACCOUNT_ID> --budget=<AMOUNT>
git fetch origin && sha=$(git rev-parse origin/main)
sh scripts/gcp/deploy.sh <service> staging "$sha"
gcloud scheduler jobs list --location=us-east1 --project=<PROJECT_ID>
gcloud scheduler jobs describe <service>-<name> --location=us-east1 --project=<PROJECT_ID>
```

- **Success prints:** the bootstrap's first run after the manifest adds `changed  enabled cloudscheduler.googleapis.com`
  (with any other new API), `changed  granted roles/cloudscheduler.admin to deploy@<PROJECT_ID>...` and
  `changed  let Cloud Scheduler mint tokens as <identity> (<service>; roles/iam.serviceAccountTokenCreator)`; its
  next run prints `ok       Cloud Scheduler may call as <identity> (<service>)`. The deploy prints, in its config
  summary, `schedule <service>-<name>: create, <cron> <time zone>, POST https://<service>-<PROJECT_NUMBER>.us-east1.run.app<path> as <identity>`
  (`update` on later deploys), then, after `/version` answers, gcloud's output for each job, and last `deployed
  <service> to staging: ... answers <SHA>`. `describe` shows `httpTarget.uri` that URL, `httpMethod: POST`,
  `oidcToken.serviceAccountEmail` the service's identity, `oidcToken.audience` its URL without the path, the
  manifest's `schedule` and `timeZone`, and `state: ENABLED`. The service's logs then show a POST to the path at
  each tick, from `Google-Cloud-Scheduler`.
- **Failure looks like:**
  - `deploy: services/<service>/service.json declares schedules, but Cloud Scheduler is not enabled in
    <PROJECT_ID>`: the bootstrap has not run since the manifest gained its first schedule. Nothing was built. Run
    step 3, then this step.
  - `gcloud scheduler jobs list` denied `cloudscheduler.jobs.list` to the deploy identity: its
    `roles/cloudscheduler.admin` grant has not reached IAM yet, or the bootstrap ran from a checkout without a
    schedule. Nothing was built. Re-run step 3 from an up-to-date checkout, wait, and re-run.
  - A scheduler call fails after `/version` answers (for instance `iam.serviceAccounts.actAs` on the identity):
    the new revision serves, but its schedules are as the failing call left them. Fix the cause and deploy the
    same commit again, which creates or updates every job.
  - The bootstrap's token grant fails with `INVALID_ARGUMENT` on
    `service-<PROJECT_NUMBER>@gcp-sa-cloudscheduler.iam.gserviceaccount.com` after its retries: Google has not
    created Cloud Scheduler's service agent yet. Wait a few minutes and re-run step 3.
  - The job runs but its `status` shows an error: a 401 or 403 means the service refused the token (check that it
    expects `https://<service>-<PROJECT_NUMBER>.us-east1.run.app` as the audience and the service's own identity
    as the caller); a 404 means the path is wrong.
- **Safe to re-run:** yes. A deploy updates each declared job in place and deletes only the service's jobs that its
  manifest does not declare; jobs that call other services, or live in another region, are left alone.

## Verify

```bash
sh scripts/gcp/bootstrap.sh <staging|production> --billing-account=<BILLING_ACCOUNT_ID> --budget=<AMOUNT>
sh scripts/gcp/served.sh https://<service>-<PROJECT_NUMBER>.us-east1.run.app/version <SHA>
gcloud run services describe <service> --region=us-east1 --project=<PROJECT_ID> --format=export
```

The bootstrap prints `0 changes` and no `missing  secret` line, `served.sh` prints the deployed SHA with exit
status 0, and the export holds exactly what `services/<service>/service.json` says at that SHA. Then
`/loop-status`, from an installed release, shows each §3 row with its served commit, or unknown for a service not
yet deployed.

## Rollback

- **A bad deploy:** deploy the previous commit with the same command,
  `sh scripts/gcp/deploy.sh <service> <env> <PREVIOUS_SHA>`. It rebuilds that commit's image, applies that
  commit's manifest, and checks `/version`. A deploy that fails leaves the previous revision serving. Do not roll
  back with `gcloud run services update-traffic --to-revisions`: traffic stays pinned to that revision, and later
  deploys then receive none.
- **Schedules** roll back with the deploy: deploying the previous commit creates or updates the jobs its
  manifest declares and deletes the service's jobs it does not. A deploy that fails before `/version` answers
  changes no schedule. To stop one at once without a deploy, `gcloud scheduler jobs pause <service>-<name>
  --location=us-east1 --project=<PROJECT_ID>`. Whether a later deploy's update resumes a paused job is unproven
  here: read its `state` with `describe` afterwards, and `gcloud scheduler jobs resume` it when it should run.
- **A bad manifest:** revert it in a pull request and deploy the revert. A commit from before the manifests
  existed cannot be deployed: `deploy.sh` refuses a commit without one. Nor can a commit whose manifest leaves a
  value `TODO(owner)` for that environment: on staging, that is every runner or threads commit before 1bdb337.
- **The probe:** it can stay, since it scales to zero. Deleting it is
  `gcloud run services delete probe --region=us-east1 --project=<PROJECT_ID>`.
- **What does not roll back:**
  - The bootstrap: the project, its billing link, the APIs, the repository, the identities, their grants, the
    Firestore databases, Cloud Scheduler's API and its grants, and the budget stay until removed by hand. A
    role or secret a manifest stops naming keeps
    its grant, and a job or a database it stops naming is not deleted.
  - Secrets' values: a deploy points at each secret's latest version, whatever the commit.
  - A Cloud SQL instance a job's manifest stops naming stays attached to the job: Cloud Run jobs have no flag that
    clears one. Services do clear it.
  - Data: Firestore documents and threads' messages. Removing a whole environment is
    `gcloud projects delete <PROJECT_ID>`, the owner's and gated: the project can be restored for a while after,
    and its ID can never be used again. Money spent, images pushed and budget emails sent do not roll back either.

## Traps

Each learned in a real run. Newest first.

- **2026-10-23:** step 14 had no commit to roll back to, after step 13 deployed the runner and threads from
  1eae0a3 → staging's GitHub App IDs were first named in 1bdb337 (PR #48). Every earlier runner or threads
  manifest leaves them `TODO(owner)` for staging, and `deploy.sh` refuses such a commit before any `gcloud` call.
  Every later commit had the same manifests as 1eae0a3, and the probe's manifest has never changed → check
  `<PREVIOUS_SHA>` with step 14's `manifest.py check` before deploying it. Until one passes, wait for the next
  commit that changes `services/runner/service.json` or `services/threads/service.json`, deploy it with step 13,
  then roll back to the commit before it. In production, the commit that first names its values will meet the
  same wait. Found by checking each earlier manifest with `manifest.py check --env=staging`, read-only.
- **2026-10-22:** a staging row whose URL is wrong reads as unknown forever, just like a service not yet
  deployed → Cloud Run answers every `*.run.app` name, so a wrong project number or region gets a 404 (with a
  "Page not found" body) instead of a DNS error, and `served.sh` fails the same way on any 404 → before merging
  step 5's rows, check that each URL answers an empty 404 (`404 0` from step 5's second command), and that its
  service name matches step 3's line. Found by reading staging's four URLs, a made-up project number, `us-west1`
  in place of `us-east1`, and two made-up service names, all read-only.

## Corrections

- 2026-10-23: Status, Last run as written and intro: the owner ran step 13 on staging from 1eae0a3 and reported
  its three exports, which hold what step 13 says (see `service-manifests` C1's evidence line at 1eae0a3). The
  status said no run of steps 6 to 15 was recorded. The deploys' own output was not reported, so it is still as
  drafted.
- 2026-10-23: Step 13: added the `manifest.py render` command that gives what each export must hold, and three
  things the exports show that the step did not say: the runner's empty `cloudsql-instances` annotation, both
  services' `maxScale: '3'`, and no Cloud SQL annotation on the job.
- 2026-10-23: Step 14: `<PREVIOUS_SHA>` must also be deployable to the environment, checked with `manifest.py
  check`. As of 1eae0a3 no runner or threads commit qualifies (see Traps). Step 15 and Rollback say the same.
- 2026-10-22: Status and intro: steps 1 to 3 and 5 ran on staging on 2026-10-22, by the owner. Step 1 is PR #29,
  which names the projects in `projects.txt`. PR #30's body quotes the served-commit lines step 3 printed. Step 5
  is PR #30, which fills in staging's four rows of `LOOP.md` §3. The runbook said it had never run.
- 2026-10-22: Last run as written: the owner confirmed that steps 2 and 3 printed what is written, so the status
  names them. Nothing in either step changed.
- 2026-10-22: Step 4: the second bootstrap on staging printed what is written, ending `staging: 0 changes.` with
  every resource `ok` and the five `missing  secret` lines. Step 4 now says the run ends with step 3's closing
  lines, and that the budget's `ok` line does not read its thresholds (`bootstrap.sh` checks only the name and
  amount). Step 3: `roles/run.jobsExecutorWithOverrides` was granted, so it is no longer an unproven role name.
- 2026-10-22: Step 5's success: the curl macOS ships (8.7.1) prints `curl: (56)`, not `curl: (22)`, for the same
  404 over HTTP/2. `served.sh` fails on any non-zero exit, so what it does is unchanged. `(22)` came from the fake
  `curl` in `tests/test_layout.py`.
- 2026-10-22: Step 5's failure: a wrong project number or region answers a 404 with a body, not a DNS error. Step
  5 gained a second command that tells the two 404s apart.
