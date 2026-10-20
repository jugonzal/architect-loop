---
needs: [one-repository]
touches: [services/runner/]
effects: [Agent SDK sessions that cost money, each with a budget shown to its sponsor before it starts (spending), Cloud Run jobs in the staging and production GCP projects (spending; cloud IAM), the Anthropic API key and a GitHub App that pushes branches and opens PRs on jugonzal/architect-loop (secrets; identity and access)]
ships-to: production
---
# A person can start a loop skill on a concern as a session that names them as its sponsor and stops at a budget

## Done when

- **C1** Dispatching a skill (`/loop-design`, `/loop-build`, `/loop-prove`, `/loop-status`) on a named concern
  starts one session in its own worktree. Every commit and PR it produces carries `Sponsored-by: <person>` beside
  `Concern:`. Prove: a dispatched `/loop-build` on a test concern, with the PR and commits shown, on staging.
- **C2** A session that reaches its budget stops before going over, and reports what it spent in tokens, money
  and wall-clock time. Prove: a dispatch with a deliberately small budget, on staging.
- **C3** A second dispatch on a concern that already has an open PR or a running session is refused, and the
  refusal names the existing one. Prove: a double dispatch, on staging.

## Design

### Where we are

- Nothing exists (2026-10-20). Whether the Claude Agent SDK can do all of C1 and C2 inside one container is the
  loop's riskiest unknown (Q1).

### Approach

Per D8 and D1, pending the spike: a Cloud Run service takes dispatches, and starts one Cloud Run job per session.
The job clones `jugonzal/architect-loop` into a fresh worktree on `<loop>/<concern>` and runs the skill with the Agent SDK
under the session's budget. The sponsor comes from the caller's authenticated GitHub identity, never from the
request body. The job runs the skills from an installed plugin release named in the dispatch, never from the worktree it edits (per D17). The runner adds `Sponsored-by:` to commits and PR bodies. Skills write to the repository exactly as
they do from a terminal (per D1). The open PR, or a running job, is the claim on a concern (C3). Rollback: a
stopped job leaves its branch and PR for a person to close; nothing is merged by the runner.

## Decisions

| # | Decision | Decided by, date | Closes |
| --- | --- | --- | --- |
| D1 | The first spike tests the Claude Agent SDK on our own workers, one container per session. GitHub Actions is the fallback if it fails. | Juan, 2026-10-20 | Narrows Q1 (was the loop's Q4) |

## Questions

| # | Question | Blocks | Default if unanswered |
| --- | --- | --- | --- |
| Q1 | Can the Claude Agent SDK, in one container per session, run a loop skill on a fresh worktree of this repository, from an installed plugin release, add `Sponsored-by:` to its commits, report tokens and cost, and stop at a budget? Spike: `/loop-prove command-center/session-runner Q1` with one `/loop-status` run and a tiny budget | C1, C2 | None: the spike answers it. If it fails, fall back to GitHub Actions with `claude-code-action` (per D1) |

## Evidence

- 2026-10-20 · Q1 · HOLDS · rung 3 · local @06f4b37 · Yes, for all six parts. Tested in Docker (python:3.12-slim, claude-agent-sdk 0.2.168 bundling Claude Code 2.1.301, linux/arm64; not Cloud Run) against main c6c859c, with Opus 5.5: 9 sessions, $0.94 estimated. Each session got its own container and a fresh clone. `/architect-loop:loop-status` ran from the plugin mounted read-only: a marker added only to that copy came back in 1 turn with 0 tools. A commit-msg hook installed by the runner added `Sponsored-by:` and `Concern:`, but `git commit --no-verify` skips it. Results report tokens (`usage`, `model_usage`), a client-side cost estimate (`total_cost_usd`) and time. `max_budget_usd` stopped all 4 runs that reached it (`error_max_budget_usd`), but only after the response that crossed it: overshoot +$0.0006, +$0.0057, +$0.0118 and +$0.0121, so C2's "before going over" cannot hold as worded. With `dontAsk` and narrow Bash rules, 2 of 4 full `/loop-status` runs ended without a full board after one compound command was denied

## Shipped
