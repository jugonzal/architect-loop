---
needs: [runner-dispatch, runner-store, local-harness]
touches: [services/runner/narration/, services/runner/runner/session.py, services/runner/runner/config.py, services/runner/runner/main.py, services/runner/service.json, services/runner/tests/test_narration.py]
effects: []
ships-to: staging/runner
---
# A running session's milestones appear in its session thread as they happen

## Done when

- **C1** Each session posts its milestones to its session thread within 10 seconds of each one: started,
  branch opened, tests run with the result, PR opened, stopped at a gate (naming it), and finished or stopped,
  with what it spent. Prove: a dispatched `/loop-build` on a test concern in the sandbox loop (per
  command-center/D61), comparing timestamps with the job's log, on local and then staging/runner (per
  command-center/D53, D54).
- **C2** A member's message to a running session's thread reaches the session before its next step, and the
  session's reply is posted to the thread. Prove: redirect a running test session from a second account, on
  staging.

## Design

### Where we are

- Neither the runner nor the thread store exists yet (2026-10-20). (Superseded by the next bullet, 2026-10-20.)
- Verified 2026-10-20 (main @a9fde89): the runner (PR #20) and threads (PR #21) exist. Threads lets the runner post
  to a session's thread as that session, with its sponsor, and read members' messages since its last `seq`. The
  runner's job, `services/runner/runner/session.py`, has no hook for narration, so this concern must change it.
  `runner-dispatch` changes that file too, so this concern waits for it (per D42).
- Verified 2026-10-22 (main @e63f06b): `services/runner/runner/main.py` builds the session's job
  (`SessionJob(config, store, github, workspace)`), and nothing in the runner's config or manifest names the
  threads service. So narrating means a threads URL in `config.py` and in `services/runner/service.json`, and a
  narrator passed in from `main.py`. `runner-store` changes `main.py` and the manifest, and `local-harness`
  changes `main.py` and `config.py`. So this concern goes after `runner-store` (D1), and after `local-harness`
  because they share those two files, which also lets C1 be proven on local first. (Corrected 2026-10-22: `touches`
  lacked these three files.)

### Approach

This is the one interface between the runner and the thread store (per D1, D6). "What it spent" is the
runner's final estimate (per D23). It is kept as its own concern so that
neither needs the other. The runner posts through the threads API (`services/threads/openapi.yaml`, per D29)
with Cloud Run's service identity, as the session and labelled with its sponsor (per D28). The threads URL comes
from a setting the runner's manifest declares, `{number}`-templated like threads' own audience (per D46). Milestones carry the
milestone kind, so the app collapses the rest of the narration by default.

## Decisions

| # | Decision | Decided by, date | Closes |
| --- | --- | --- | --- |
| D1 | `runner-store` goes first. This concern needs it, and its `touches` gain `services/runner/runner/config.py`, `services/runner/runner/main.py` and `services/runner/service.json`. | Juan, 2026-10-22 | Q1 |

## Questions

| # | Question | Blocks | Default if unanswered |
| --- | --- | --- | --- |
| ~~Q1~~ | ~~Which goes first, when this concern and `runner-store` both change the runner's manifest and `main.py`? (raised by the 2026-10-22 design)~~ → D1 | | |

## Evidence

- 2026-10-25 · ship · verified · staging @633cbe4 · the owner ran `deploy.sh runner staging 633cbe4`; I then `served.sh https://runner-665570365697.us-east1.run.app/version 633cbe4` printed 633cbe477c987414bd151302c6a23728684f4e90 and exited 0, as did the threads (1eae0a3), status and notify reads. `gcloud run services describe runner` read back image tag 633cbe4, COMMIT_SHA 633cbe4, runtime identity runner@loops-512401, Ready True, and RUNNER_THREADS_URL https://threads-665570365697.us-east1.run.app; the `runner-session` job has the same image, COMMIT_SHA and RUNNER_THREADS_URL. The only WARNING in the last 2 hours was an unauthenticated GET /estimates (401) made while verifying. No session was dispatched, so session-narration C1 and C2 are not yet proven on staging

## Shipped
