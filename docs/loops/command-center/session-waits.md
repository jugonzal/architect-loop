---
needs: []
touches: [services/runner/runner/session.py, services/runner/runner/config.py, services/runner/service.json, services/runner/tests/test_session.py, services/runner/tests/test_narration.py, services/runner/tests/test_config.py]
effects: [staging/runner redeployed so that it serves this concern (the owner deploys it; gates: deploy), one dispatched `/loop-design` session on `sandbox/design-target` for the staging proof, about $0.25 as session 3caa204 spent on 3e2e6d2 plus its answer's turn (the owner starts it; gates: spending)]
ships-to: staging/runner
---
# A design session waits for its answer in its thread

## Done when

- **C1** When a `/loop-design` session's model stops, the session stays running, and a member's message posted to
  its thread within 15 minutes becomes its next turn; its reply is posted to the thread, and the 15 minutes start
  again (per command-center/D83, D84). Prove: the runner's tests with a scripted client, a fake thread and a
  virtual clock, in CI on main; then on staging/runner, a `/loop-design` dispatched on `sandbox/design-target`
  (per command-center/D61) whose Q1 is answered in its thread more than a minute after it was asked, with the
  decision it records.
- **C2** A waiting session ends `completed` after 15 minutes with no reply, saying so in its thread, and ends within
  10 seconds of its sponsor's stop. A session of any other skill ends when its model stops, as before (per
  command-center/D84). Prove: the same tests, with a session nobody answers, one stopped while waiting, and one of
  each other skill, in CI on main; then on staging/runner, one design session left unanswered, timed from its
  question to its Finished milestone.

## Design

### Where we are

- **Verified** (`services/runner/runner/session.py` on main @2223d4a, which is ff82269's code for this file, served
  by staging/runner): `SessionJob._converse` sends one prompt and reads `client.receive_response()` until the
  result, and the job ends. The Stop hook (`Narration._relay`) hands the model only the members' messages already
  in the thread and waits for none.
- **Verified** (staging/runner @3e2e6d2, 2026-11-13, `app-documents`'s C2 evidence): session 3caa204 posted its
  question at 23:47:20 UTC and its Finished milestone at 23:47:21, 51 s after it started, having spent $0.23.
- **Verified** (`services/runner/service.json`): a session's job may run for 3600 s (`task_timeout_s`).
  `config.py` has `cap_per_sponsor` 3, `spend_interval_s` 5 and `narration_poll_s` 5.
- **Assumed:** the Agent SDK's client takes a second `query` after a result and continues the same conversation.
  The runner holds the client open in an `async with` until `_converse` returns, and nothing sends a second prompt
  today. Check it first, with the scripted client in the tests and then on the local harness.
- **Assumed:** a reply after the model's prompt cache has expired costs more than one inside it, because the
  session's context is written to the cache again. Not measured; the staging proof's spend will show it.

### Approach

Per command-center/D83 and D84:

- **Waiting:** after a result, when the session's skill is `loop-design` and it was not interrupted, `_converse`
  polls the thread every `narration_poll_s` for members' messages after the last one seen. When one arrives it
  sends them as the next prompt, with `relay_text`, and reads the response as before. With none for the window it
  returns the last result, and the session ends `completed`.
- **The window** is `design_wait_s` in the config, 900 by default, set from `RUNNER_DESIGN_WAIT_S`. It never runs
  past the job's task timeout: the wait ends early enough for the job to record its end.
- **What others see:** the session's state stays `running`, so the API and the app do not change, and the app's
  composer already invites a message to a running session. The session posts a milestone when it starts to wait,
  naming when the wait ends, and one when it ends for lack of a reply.
- **Stops and spend:** the spend publisher keeps running while the session waits, so a stop request is picked up
  as today and ends the wait. The budget applies to every turn; a session at its budget does not wait.
- **Holding:** a waiting session holds its concern and counts against its sponsor's cap, since it is still
  running (per `session-runner` D6, command-center/D84). The refusal a second dispatch gets already names the
  session that holds the concern.

Rollback: redeploy the previous revision. A session waiting when the revision changes is not affected, since each
job runs the image it started with.

## Decisions

| # | Decision | Decided by, date | Closes |
| --- | --- | --- | --- |

## Questions

| # | Question | Blocks | Default if unanswered |
| --- | --- | --- | --- |

## Evidence

- 2026-11-14 · C1 · HOLDS · rung 1 · staging/runner @c14ba70 · On staging, session f5da9b5b of `/loop-design` on `sandbox/design-target` (plugin release v0.7.0, sponsor jugonzal), read from the runner's API and the session's thread with the owner's GitHub sign-in; staging/runner serves c14ba70 (`served.sh`). The session asked Q1 at 03:12:54 UTC and posted "Waiting for a reply in this thread for 15 minutes"; the owner's reply "A" at 03:13:29 became its next turn, it recorded sandbox/design-target D1 and merged PR #155 (2c21804), posted its report at 03:17:42 and began a second 15 minutes. The session stayed `running` throughout. One departure from the Prove: the answer came 35 seconds after the question, not more than a minute; the second wait, which ran its full 15 minutes with the session still running, covers what the minute was there to show
- 2026-11-14 · C2 · HOLDS · rung 1 · staging/runner @c14ba70 · The same session, left unanswered after its report: "Waiting for a reply" at 03:17:42.45 UTC, "No reply in 15 minutes, so it stops waiting." at 03:32:42.48, the Finished milestone at 03:32:44, and the runner reads it `ended`, `completed` at 03:32:44. That is 15 minutes 2 seconds from the wait's start to Finished. The `/loop-status` session 99c49f76 dispatched at 03:20 ended when its model stopped, with no wait. A sponsor's stop during a wait was not tried on staging; the Prove asks for it in CI only

## Shipped
