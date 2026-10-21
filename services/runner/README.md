# Session runner

Starts a loop skill on a concern as a session that names its sponsor and stops at a budget
([`docs/loops/command-center/session-runner.md`](../../docs/loops/command-center/session-runner.md)).

- **The service** (`runner.main:application`, under gunicorn) serves [`openapi.yaml`](openapi.yaml): dispatch,
  sessions with their spend, stop, the estimate before a start, and `/version`. It identifies a caller with
  `GET /user` on their GitHub token and checks them as a collaborator with the runner's own GitHub App. It
  refuses a concern with an open pull request or a running session, and a sponsor at their cap.
- **A session's job** (`python -m runner job`, one Cloud Run job execution per session) clones the project onto
  `<loop>/<concern>`, installs the commit-msg hook that adds `Concern:` and `Sponsored-by:`, extracts the plugin
  release named in the dispatch outside the clone, read-only, and runs the skill with the Agent SDK. It
  publishes its spend to the store at least every 10 seconds, stops at the first response that crosses its
  budget or when its sponsor asks, and adds the same trailers to the bodies of the pull requests it opened.
- **The trailer check** (`runner/trailers.py`, run by `.github/workflows/trailers.yml`) fails a pull request
  with a runner commit that lacks `Sponsored-by:`. It is standard library only.

## Tests

From this folder, with Python 3.12 and the packages in `requirements-dev.txt`:

```sh
python -m pip install -r requirements-dev.txt
python -m unittest discover -s tests -t . -v
```

No test reaches a network or starts an Agent SDK session: GitHub, Cloud Run and the SDK client are fakes, the
tests drop `ANTHROPIC_API_KEY`, and the SDK's entry points raise if a test calls them.

## Config

Environment variables; secrets are mounted from Secret Manager as environment variables (command-center/D32).

| Variable | Default | What |
| --- | --- | --- |
| `RUNNER_PROJECT` | `jugonzal/architect-loop` | The one project served (command-center/D18) |
| `RUNNER_CAP_PER_SPONSOR` | `3` | Sessions one sponsor may run at once (command-center/D22) |
| `RUNNER_SKILL_MODELS` | `/loop-status` on `claude-sonnet-5-5`, the rest on `claude-opus-5-5` | JSON skill to model map, merged over the default (session-runner D5) |
| `RUNNER_PRICES` | Opus 5.5 and Sonnet 5.5 list prices | JSON dollars per million tokens, for the running estimate only |
| `RUNNER_SPEND_INTERVAL_S` | `5` | How often a job publishes its spend; at most 10 (command-center/D23) |
| `RUNNER_LOST_AFTER_S` | `300` | An active session that has not published for this long ends as `lost` |
| `RUNNER_STORE` | `/tmp/runner/runner.sqlite3` | The SQLite file of the store; see "Not built" |
| `COMMIT_SHA` | the image's build argument | What `/version` answers |
| `RUNNER_APP_ID`, `RUNNER_APP_INSTALLATION_ID`, `RUNNER_APP_SLUG` | none | The runner's GitHub App |
| `RUNNER_APP_PRIVATE_KEY` | none | Secret: the app's private key (PEM). The job removes it from its environment before the session starts |
| `ANTHROPIC_API_KEY` | none | Secret, the job only: read by the Agent SDK, never by the runner's code |
| `RUNNER_GCP_PROJECT`, `RUNNER_REGION`, `RUNNER_JOB` | none, `us-east1`, `runner-session` | The Cloud Run job a dispatch executes |
| `RUNNER_SESSION_ID` | set per execution | The session a job runs |

## What the owner sets up

None of this exists yet, and each step is the owner's (LOOP.md §2).

1. **The runner's GitHub App** (command-center/D27), installed on this repository only, with repository
   permissions Contents read and write, Pull requests read and write, Metadata read, and **not** Workflows (so a
   session cannot edit the workflow that checks its trailers). It needs no webhook. Set its id, installation id
   and slug in the config above, and its private key in Secret Manager.
2. **The repository variable `RUNNER_APP_SLUG`**, the app's slug, so the trailer check recognises its commits.
   Until it is set, the check recognises none and passes with a warning.
3. **`trailers` as a required status check** on `main`'s ruleset (session-runner D4), once this workflow is on
   main.
4. **The Cloud Run service and job** from this image, in each environment (D2, D32). The job runs
   `python -m runner job`, with at most one task, **no retries** and a task timeout; the service's identity
   needs permission to run that job with overrides.

## Not built

- **The store's backend in staging and production.** `runner/store.py` defines the `Store` interface and one
  implementation on SQLite, which the tests exercise. The service and each job run in separate containers, so
  they need a shared database; which one is a decision the loop has not recorded.
- **Refreshing a session's GitHub token.** An installation token lasts an hour, so a session that runs longer
  can no longer push or open pull requests.
