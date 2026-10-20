---
needs: [one-repository, session-runner, threads]
touches: [services/runner/narration/]
effects: []
ships-to: production
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

- Neither the runner nor the thread store exists yet (2026-10-20).

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
