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
  command-center/D61), comparing each post's time with the event it reports (the session's `started_at` for the
  start, per D2; GitHub's own timestamps for the branch and the PR; the job's end log for the finish), on local and
  then staging/runner (per command-center/D53, D54). The gate milestone is proven by the runner's tests in CI on
  main, rung 5, and staging is not asked to show it (per D3). That the tests milestone appears only for a command
  that runs tests is `narration-tests-milestone`'s claim, not this one's.
- **C2** A member's message to a running session's thread reaches the session before its next step, and the
  session's reply is posted to the thread. Prove: redirect a running test session from a member's account, the
  sponsor's own included (per D4), on staging.

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
| D2 | "Started" is measured against the session's own `started_at`, which the job stamps when it marks the session running. The container's boot before that, about 17 to 21 s in the staging runs of 2026-10-26, is not counted. The runner posts nothing at dispatch. | Juan, 2026-10-26 | Settles what C1's "started" is |
| D3 | The "stopped at a gate" milestone is proven by the runner's scripted test in CI on main (rung 5), which asserts its 10-second window on a virtual clock. Staging is not asked to show a session stopping at a gate, and no sandbox concern is added for it. This milestone stays unseen on a real session. | Juan, 2026-10-26 | Settles how C1's gate milestone is proven |
| D4 | A message from the session's own sponsor counts as "a member's message" for C2, so a second account is not needed to prove it. The case of a second account stays untested. | Juan, 2026-10-26 | Settles C2's Prove step; its HOLDS line of 2026-10-26 stands |

## Questions

| # | Question | Blocks | Default if unanswered |
| --- | --- | --- | --- |
| ~~Q1~~ | ~~Which goes first, when this concern and `runner-store` both change the runner's manifest and `main.py`? (raised by the 2026-10-22 design)~~ → D1 | | |

## Evidence

- 2026-10-25 · ship · verified · staging @633cbe4 · the owner ran `deploy.sh runner staging 633cbe4`; I then `served.sh https://runner-665570365697.us-east1.run.app/version 633cbe4` printed 633cbe477c987414bd151302c6a23728684f4e90 and exited 0, as did the threads (1eae0a3), status and notify reads. `gcloud run services describe runner` read back image tag 633cbe4, COMMIT_SHA 633cbe4, runtime identity runner@loops-512401, Ready True, and RUNNER_THREADS_URL https://threads-665570365697.us-east1.run.app; the `runner-session` job has the same image, COMMIT_SHA and RUNNER_THREADS_URL. The only WARNING in the last 2 hours was an unauthenticated GET /estimates (401) made while verifying. No session was dispatched, so session-narration C1 and C2 are not yet proven on staging
- 2026-10-26 · C1 · UNPROVEN · rung 2 · staging @633cbe4 · The owner started session d89d993 from the app's Agents tab at 12:58 EDT (16:58 UTC) on sandbox/build-target-3 with a $3.00 budget; the job `runner-session-bmvqj` was created at 16:58:57Z, ended `completed` at 17:06:25Z with exit 0, and opened PR #81 with one commit carrying Concern and Sponsored-by trailers. Served commit re-read as 633cbe4 before and after. Narration was attempted but never reached a thread: the job logged 21 `could not post/read` errors, every one `threads answered 500`, and threads' own logs for 16:58-17:07Z show 11 `UndefinedTable: relation "messages" does not exist` and 10 for `"threads"`. Staging's threads database has no tables, so its migrations (`docs/runbooks/deploy.md` step 10, `python -m threads.migrate`, a migration on shared data and the owner's) were never applied. First post attempt 16:59:19Z, 22 s after the job was created, so the 10 s timing cannot be judged. Not contradicted: the runner kept the session going through 21 failures and finished it, so a threads outage does not fail a session. Missing: threads' tables, then another dispatch
- 2026-10-26 · C2 · UNPROVEN · rung 2 · staging @633cbe4 · The owner started session d89d993 from the app's Agents tab at 12:58 EDT (16:58 UTC) on sandbox/build-target-3 with a $3.00 budget; the job `runner-session-bmvqj` was created at 16:58:57Z, ended `completed` at 17:06:25Z with exit 0, and opened PR #81 with one commit carrying Concern and Sponsored-by trailers. Served commit re-read as 633cbe4 before and after. The runner's reads of the thread (`messages_after`) all answered 500 for the same missing tables, so no member message could reach the session, and no second account redirected it. Missing: threads' tables, and a second signed-in collaborator (sandbox Q1)
- 2026-10-26 · C1 · UNPROVEN · rung 2 · staging @633cbe4 · Session c79c36c, started by the owner from the app at 17:39 UTC on sandbox/build-target-3 with a $3.00 budget (job `runner-session-28s86`, started 17:39:06Z, ended `completed` at 17:44:08Z, opened PR #83). Threads' tables had been created by the owner's migration, and served commits were re-read as 633cbe4 (runner) and 1eae0a3 (threads) before. Narration reached the session's thread: 10 posts, all 201, no threads error, and the owner's screenshots show started, three narration lines (collapsed by default behind "Hide narration"), branch opened, tests run, PR #83 opened and "Finished. It spent about $0.4057 over 281 s, an estimate". Timing against events outside the runner: PR opened 17:43:46.33 against GitHub's 17:43:45 (+1.3 s, GitHub rounds to the second); finished 17:44:05.20 against the job's own `ended: completed` at 17:44:05.24 (0 s); branch opened 17:43:33.99 against the commit at 17:43:27, the push in between, so under 7 s. Not shown: "stopped at a gate, naming it", because no gate was hit; and "started", whose post came 17.5 s after Cloud Run's execution start (17:39:06.5), a span that includes the container booting and that the logs cannot split. Defect found: the "Tests run, passed" milestone also appeared for `git add && git commit` and for `cat > /tmp/prbody.md <<'EOF'`, which are not test runs. `TEST_COMMAND` in `services/runner/runner/session.py` is searched over the whole command text, so a heredoc commit message or PR body that mentions `check.sh` or `unittest` matches; this is read from the code and not yet reproduced by an A/B. Missing: a session that stops at a gate, and a decision on the tests milestone
- 2026-10-26 · C2 · UNPROVEN · rung 2 · staging @633cbe4 · Session c79c36c, started by the owner from the app at 17:39 UTC on sandbox/build-target-3 with a $3.00 budget (job `runner-session-28s86`, started 17:39:06Z, ended `completed` at 17:44:08Z, opened PR #83). Threads' tables had been created by the owner's migration, and served commits were re-read as 633cbe4 (runner) and 1eae0a3 (threads) before. The runner polled the thread for members' messages every 5 to 7 s and every poll answered 200 with no message, so the path from threads to the session is up. No one wrote to the thread while it ran, so a message reaching the session before its next step, and the session's reply, are not shown. Missing: a member's message sent to a running session. The claim says "a member's message", and the owner is a member, but its Prove step says "from a second account" (sandbox Q1); one of the two needs deciding
- 2026-10-26 · C2 · HOLDS · rung 2 · staging @633cbe4 · One run, with the owner as the member: the owner chose to write the message from their own account, not a second one, so the second-account case of the claim's Prove step is untested. Session a0f3083 (job `runner-session-9n2gg`, started 19:13:37Z, ended `completed` at 19:18:06Z, PR #85), served commits re-read as 633cbe4 (runner) and 1eae0a3 (threads). The owner wrote "Before your next step, tell me in this thread which git branch you are on and what your budget is" in the session's thread at 19:15:54.98Z (threads logged the POST, 201). The runner's next read of the thread was at 19:17:38.60Z, 104 s later, and returned the message (the response grew from 155 to 513 bytes); it posted a message 0.05 s after. The runner reads only between the session's steps, so the 104 s is the length of the step then running, and the first run showed a 3-minute gap between reads for the same reason. The session's final message, posted at 19:18:03Z, answers it: it is on `sandbox/build-target-3` (one commit, 87c8182b, on `origin/main` @82764b67), its budget is $3.00 and about $0.33 is spent, which it could only have got from the message. The answer came only in that final message, not as a separate reply, and the claim sets no time. One run; not shown: a message sent to a session that is between steps, or from a second account

## Shipped
