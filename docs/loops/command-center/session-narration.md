---
needs: [one-repository, runner-dispatch]
touches: [services/runner/narration/, services/runner/runner/session.py, services/runner/tests/test_narration.py]
effects: []
ships-to: production/runner
---
# A running session's milestones appear in its session thread as they happen

## Done when

- **C1** Each session posts its milestones to its session thread within 10 seconds of each one: started,
  branch opened, tests run with the result, PR opened, stopped at a gate (naming it), and finished or stopped,
  with what it spent. Prove: a dispatched `/loop-build` on a test concern, comparing timestamps with the job's
  log, on staging.
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

### Approach

This is the one interface between the runner and the thread store (per D1, D6). "What it spent" is the
runner's final estimate (per D23). It is kept as its own concern so that
neither needs the other. The runner posts through the threads API (`services/threads/openapi.yaml`, per D29)
with Cloud Run's service identity, as the session and labelled with its sponsor (per D28). Milestones carry the
milestone kind, so the app collapses the rest of the narration by default.

## Decisions

| # | Decision | Decided by, date | Closes |
| --- | --- | --- | --- |

## Questions

| # | Question | Blocks | Default if unanswered |
| --- | --- | --- | --- |

## Evidence

## Shipped
