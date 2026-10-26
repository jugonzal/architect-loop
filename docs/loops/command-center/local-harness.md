---
needs: [runner-store]
touches: [scripts/local/, LOOP.md, docs/runbooks/local.md, .github/workflows/local.yml, services/runner/runner/github.py, services/runner/runner/launcher.py, services/runner/runner/config.py, services/runner/runner/main.py, services/threads/threads/]
effects: [new local rows in LOOP.md §3 and the smoke test in §4 (a change to the contract; the owner merges it; gates: merge)]
ships-to: main
---
# Every service runs on one machine against fakes, so a claim can be proven before staging

## Done when

- **C1** One command, run from a clean checkout of a commit on `main`, builds every service in `services/` and
  runs it with its manifest's settings (per D46), Postgres, the Firestore emulator and the fakes. Each one's
  `/version` answers that commit, and `LOOP.md` §3's `local/<service>` rows read it. A dirty working tree is
  refused. Prove: run it from a commit on `main` and read every local row with `/loop-status`, on local, and the
  same run in `.github/workflows/local.yml`, in CI on main.
- **C2** A dispatch to the local runner runs a session from start to end against the fake GitHub and the fake
  Agent SDK. The concern is claimed in the shared store, the session's job runs in its own container, spend is
  published, and the final message is kept. Threads answers a member's read and post. Nothing leaves the machine
  and nothing is spent. Prove: the smoke script, which `LOOP.md` §4 names as the smoke test, in CI on main and on
  local.

## Design

### Where we are

- Verified 2026-10-22 (`LOOP.md` §4 on main @e63f06b): the smoke test is `TODO(owner)`, and no local environment
  exists.
- Verified 2026-10-22 (`services/runner/runner/github.py`, `launcher.py` and `main.py` on main @e63f06b): the
  runner hard-codes `https://api.github.com` and launches each session as a Cloud Run job, so it cannot run on one
  machine without a change. The service and its job are separate containers, so locally they need the shared
  store that `runner-store` adds. That is why this concern needs `runner-store`.
- Verified 2026-10-22 (`services/threads/threads/config.py` and `identity.py`): threads takes its GitHub API URL
  from `THREADS_GITHUB_API_URL`, and checks the runner's Google-signed ID token against Google's keys. Locally the
  runner has no metadata server to ask for a token, so the harness needs a stand-in for that identity.
- Verified 2026-10-22 (`services/runner/tests/fakes.py` and `services/threads/tests/fakegithub.py`): both test
  suites have in-process fakes for GitHub, and the runner's has one for the SDK. They are a start for the
  harness's fakes, which run as their own process.

### Approach

Per D53, D32 and D46:

- `scripts/local/up.sh` builds each `services/<name>/Dockerfile` at the checkout's `HEAD`, the way `deploy.sh`
  does, and starts it with the settings its `service.json` declares. Secrets get fake values. It finds services
  by folder, so `status-service` and `notifications` join without editing the harness.
- Fakes in `scripts/local/fakes/` stand in for GitHub (`GET /user`, collaborator checks, installation tokens,
  pull requests, webhooks to the services), the Agent SDK, Cloud Run's job launch, and the metadata server's ID
  tokens.
- The runner gains a configurable GitHub API URL and a launcher that starts a container instead of a Cloud Run job.
  Threads gains a configurable key set for service identity. Both default to what they do today, so staging is
  unchanged.
- `LOOP.md` §3 gains `local/status`, `local/runner`, `local/threads` and `local/notify` rows, listed first, each
  reading `http://localhost:<port>/version` with `served.sh`. §4 names the smoke script. Evidence lines cite
  `local @<sha>`, where the sha is a commit on `main`.
- `docs/runbooks/local.md` says how to run it, written with `/loop-runbook` and corrected after the first run.

The status service in the cloud reads local rows as `unknown` (per D56), which only affects the environments list:
needs are decided from evidence (per D50). Rollback: revert the PR. Nothing outside the machine changes.

## Decisions

| # | Decision | Decided by, date | Closes |
| --- | --- | --- | --- |

## Questions

| # | Question | Blocks | Default if unanswered |
| --- | --- | --- | --- |

## Evidence

- 2026-10-26 · C1 · HOLDS · rung 2 · main @162886b · CI run 40405651839 (`local` workflow, push to main, ubuntu-latest): `up.sh` refused nothing, built all 5 images (fakes, status, runner, threads, notify) at 162886b55a5f, started Postgres and the Firestore emulator, and each of local/status, runner, threads and notify answered 162886b55a5f at :8701-:8704/version and read 162886b with `served.sh` from its LOOP.md §3 row; the dirty-tree refusal is covered by the harness's own tests in the same run (26/26 OK, staged and changed tracked files refused); 30 of the last 30 `local` runs on main succeeded. Gap: the "on local" half (a developer machine, rows read by `/loop-status`) was not run, because this session's machine has no Docker; the owner can close it with `sh scripts/local/smoke.sh` then `/loop-status`
- 2026-10-26 · C2 · HOLDS · rung 2 · main @162886b · CI run 40405651839: `sh scripts/local/smoke.sh` passed 27/27 checks: a /loop-build on command-center/addressed-to-people dispatched and ran start to end against the fake GitHub and fake SDK, a second dispatch and a non-collaborator were refused, the claim was in the runner's Firestore, spend was published during and at the end, the final message was kept, the job ran in its own container and exited 0, the runner asked only the fakes, no container on the internal network reached api.github.com or 1.1.1.1, and threads served a member's read and post, refused a non-member, and took a post with the runner's ID token; 30 of the last 30 `local` runs on main succeeded. Gap: not run on a developer machine (no Docker here); the owner can close it with `sh scripts/local/smoke.sh`

## Shipped
