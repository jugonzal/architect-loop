# Status service

Serves each project's status document, fresh within a minute of a push, a pull request event or a deploy
([`docs/loops/command-center/status-service.md`](../../docs/loops/command-center/status-service.md)).

- **`GET /projects/{owner}/{repo}/status`** answers a collaborator on the project's repository the document that
  `plugin/skills/loop-status/scripts/loop_status.py --json` writes, derived by that script from the same commit the
  image was built from ([`openapi.yaml`](openapi.yaml)). A caller is identified with `GET /user` on the GitHub token
  from the app's sign-in, and checked as a collaborator with the service's own GitHub App.
- **The facts** are gathered by the service itself ([`status/facts.py`](status/facts.py)), in the shape
  `loop_status.py gather` writes: git from its own clone of the repository, pull requests (GraphQL, in `gh`'s
  shape) and the runs on main from GitHub's API, and each `LOOP.md` §3 row's served commit with a GET of the first
  `http(s)` URL in its served-commit cell (command-center/D9, D56). It runs no command taken from the repository.
  The `main` row is main's head, from the service's own fetch.
- **Freshness.** A document is reused for at most `STATUS_MAX_AGE_SECONDS` (30), and never after a signed delivery
  about the project to **`POST /webhooks/github`**. A fact that cannot be read is `unknown`; if main itself cannot
  be fetched, the answer is 503, never an earlier document.
- **State.** Its only store is its clone under `STATUS_CACHE_DIR`, a cache: deleting it and restarting gives the
  same answer. Nothing a person types is kept.

## Tests

From this folder, with Python 3.12 and the packages in `requirements-dev.txt`:

```sh
python -m pip install -r requirements-dev.txt
python -m unittest discover -s tests -v
```

No test reaches a network: the project's origin is a bare repository in a temporary folder, GitHub is a fake over
HTTP on 127.0.0.1, and so is each environment's `/version`. `.github/workflows/status-service.yml` runs them on
every push and pull request.

## Config

Environment variables, listed in [`status/config.py`](status/config.py). The manifest,
[`service.json`](service.json), sets `STATUS_PROJECTS` and `STATUS_GITHUB_APP_ID` and names the two secrets; the
rest have defaults. `deploy.sh` sets `COMMIT_SHA`.

## What the owner sets up

None of this exists yet, and each step is the owner's (LOOP.md §2).

1. **The status service's GitHub App** (command-center/D27), installed on this repository only, with repository
   permissions Contents read, Pull requests read, Actions read, Checks read, Commit statuses read and Metadata read,
   and nothing it can write. Its webhook URL is `https://status-<project number>.us-east1.run.app/webhooks/github`,
   with a webhook secret, subscribed to Push, Pull request, Create, Delete, Workflow run, Check suite and Status.
   Name its id in `service.json` (`STATUS_GITHUB_APP_ID`, `TODO(owner)` until then, so `deploy.sh` refuses to
   deploy it).
2. **Its two secrets** in the environment's Secret Manager: `status-github-app-private-key` (the app's private key,
   PEM) and `status-github-webhook-secret`, as `docs/runbooks/deploy.md` step 9 creates the others.
3. **The runtime identity** `status@<project>.iam.gserviceaccount.com`, which `bootstrap.sh` creates from the
   manifest, with no role, and lets read those two secrets.
4. **The deploy:** `sh scripts/gcp/deploy.sh status staging <sha>` from a commit on main.
