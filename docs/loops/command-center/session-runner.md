---
needs: [one-repository]
touches: [services/runner/, .github/workflows/trailers.yml, .github/workflows/runner.yml]
effects: [Agent SDK sessions that cost money, each with a budget shown to its sponsor before it starts (spending), Cloud Run jobs in the staging and production GCP projects (spending; cloud IAM), the runner's own store for sessions and spend in each project (spending; cloud IAM; per command-center/D26), the Anthropic API key and the runner's own GitHub App that pushes branches and opens PRs on jugonzal/architect-loop (secrets; identity and access; per command-center/D27), the repository made public and main protected so that nothing reaches it except through a PR (publishing and a repository setting; the owner does both, per command-center/D24), the trailer check made a required status check on main (a repository setting; the owner sets it, per D4)]
ships-to: production
---
# A person can start a loop skill on a concern as a session that names them as its sponsor and stops at a budget

## Done when

- **C1** Dispatching a skill (`/loop-design`, `/loop-build`, `/loop-prove`, `/loop-status`) on a named concern,
  through the API in `services/runner/openapi.yaml` (per command-center/D29), starts one session in its own
  worktree. Every commit and PR it produces carries `Sponsored-by: <person>` beside `Concern:`, and a PR with a
  runner commit that lacks it fails the required trailer check (per D4). Prove: the runner's API tests against
  `openapi.yaml`, in CI on main, then a dispatched `/loop-build` on a test concern, with the PR and commits shown,
  plus a runner commit made with `--no-verify` on a test branch, on staging.
- ~~**C2** A session that reaches its budget stops before going over, and reports what it spent in tokens, money
  and wall-clock time. Prove: a dispatch with a deliberately small budget, on staging.~~ Contradicted by the Q1
  spike (2026-10-20): the SDK stops only after the response that crosses the budget. Superseded by C4 (per D21).
- **C3** A second dispatch on a concern that already has an open PR or a running session is refused, and so is
  a dispatch that would take its sponsor past their cap of running sessions (per D22). Each refusal names the
  existing PR or sessions. Prove: a double dispatch, and one dispatch over a cap lowered to 1, on staging.
- **C4** While it runs, a session publishes its approximate spend at least every 10 seconds. It stops at the
  first model response that crosses its budget, and reports its final estimated spend: tokens, dollars
  (overshoot included) and wall-clock time (per D21, D23). Prove: a dispatch with a deliberately small budget,
  comparing the published spend with the SDK's result, on staging.

## Design

### Where we are

- Verified 2026-10-20 (Q1's evidence line, harness on `spike/session-runner-q1` @06f4b37, local Docker, rung 3):
  - `claude-agent-sdk` 0.2.168 runs in `python:3.12-slim` and bundles Claude Code 2.1.301. Wheels exist for
    linux arm64 and x86_64, 114 MB each on PyPI.
  - A session can run a loop skill on its own fresh clone, from a plugin mounted read-only (`plugins` with a
    local path, `setting_sources=[]`). A marker added only to that copy showed which copy ran.
  - `max_budget_usd` stops a session (`error_max_budget_usd`) only after the response that crosses it. The 4
    stops overshot by $0.0006 to $0.0121, and the SDK docs say the estimate "can pass this value".
  - `total_cost_usd` is a client-side estimate at list price. Per-step usage is exact for input and cache
    tokens. Its output tokens are a placeholder until the result arrives (SDK cost-tracking docs, read
    2026-10-20).
  - With `dontAsk` and narrow Bash rules, a denied compound command made 2 of 4 `/loop-status` runs give up on
    the full board.
  - A commit-msg hook adds trailers, but `git commit --no-verify` skips it.
- Measured with Opus 5.5 (spike, one sample each, estimates): a full `/loop-status` cost about $0.44 over 20
  turns and 75 s; a one-file commit about $0.10.
- Verified 2026-10-20 (`gh api repos/jugonzal/architect-loop/branches/main/protection`): `main` has no
  protection, and a private repository on this plan cannot have any. D3 counts on a protected `main`, so the
  repository goes public and the owner protects `main` (per command-center/D24).
- Missing:
  - a tagged plugin release for the job to install (none exists yet, `git tag -l` 2026-10-20; cutting it is the
    owner's, per D17);
  - staging's GCP projects (`environments` creates them, per command-center/D31; corrected 2026-10-20: this said
    `status-service`);
  - the protection on `main` (per command-center/D24);
  - the GitHub App (in effects).

### Approach

Per command-center/D8, and D1 and D2 here:
- **Dispatch:** a Cloud Run service takes dispatches and starts one Cloud Run job per session. The sponsor comes
  from the caller's GitHub identity, read with `GET /user` on the caller's token and checked as a collaborator
  with the runner's own app, never from the request body (per command-center/D27, D28). The service refuses a dispatch
  on a concern that has an open PR or a running session, and one past the sponsor's cap of running sessions
  (per D22).
- **The job:** it clones `jugonzal/architect-loop` into a fresh worktree on `<loop>/<concern>` and installs the
  plugin release named in the dispatch, never using the worktree's own `plugin/` (per D17). It runs the skill
  with the Agent SDK:
  - permissions: `dontAsk`, allowing Bash, Read, Write, Edit, Glob, Grep and Skill (per D3);
  - empty `setting_sources`;
  - the model for that skill from the runner's config (per D5);
  - `max_budget_usd` set to the session's budget (per D21).
- **Trailers:** the job installs a commit-msg hook that adds `Concern:` and `Sponsored-by:`, and puts the same
  trailers in PR bodies. `.github/workflows/trailers.yml` fails any PR with a commit from the runner's GitHub App
  that lacks `Sponsored-by:` (per D4). Skills write to the repository exactly as they do from a terminal (per D1).
- **Spend:** the job publishes spend while it runs and at the end (per D23). Before a start, the service answers
  an estimate for a skill and model: the median of that pairing's last 10 sessions. A pairing with no measured
  sessions has no estimate. The Opus 5.5 numbers above seed the first pairings.
- **API** (per command-center/D29): `services/runner/openapi.yaml` describes dispatch (skill, concern,
  arguments passed to the skill, budget, plugin release), the sponsor's running sessions with their spend, stop,
  and the estimate before a start. The app concerns generate their clients from it.
- **Store** (per command-center/D26): the runner keeps sessions and their spend in a store of its own in each
  environment, and nothing else does. A dispatch claims its concern there atomically, so two dispatches at once
  cannot both start. Wiping it loses the estimates' history and nothing about any loop (G4).
- **Build and deploy:** Python 3.12, tests in `services/runner/tests/`, run by `.github/workflows/runner.yml`
  (per command-center/D30), and the deploy convention of command-center/D32.
- **Claims and limits:** the open PR, or a running job, is the claim on a concern (C3). The runner's config
  holds the per-sponsor cap (3) and the skill → model map, and changing either is a config change, not a
  design change.
- **Rollback:** a stopped job leaves its branch and PR for a person to close. The runner merges nothing.

## Decisions

| # | Decision | Decided by, date | Closes |
| --- | --- | --- | --- |
| D1 | The first spike tests the Claude Agent SDK on our own workers, one container per session. GitHub Actions is the fallback if it fails. | Juan, 2026-10-20 | Narrows Q1 (was the loop's Q4) |
| D2 | The runner uses the Claude Agent SDK, one Cloud Run job per session. The GitHub Actions fallback is dropped: the spike held on all six parts of Q1. | Juan, 2026-10-20 | Q1 |
| D3 | Inside its container, a session may run any Bash command. It runs in `dontAsk` mode, allowing Bash, Read, Write, Edit, Glob, Grep and Skill. The container is the sandbox, and the limits live outside the session: its own clone, the GitHub App's permissions, a protected main, and the budget. | Juan, 2026-10-20 | The spike's give-ups on denied compound commands |
| D4 | Trailers are added by a commit-msg hook the runner installs, and enforced by a required CI check that fails any PR with a runner commit lacking `Sponsored-by:`. | Juan, 2026-10-20 | The spike's finding that `--no-verify` skips hooks |
| D5 | Each skill's model comes from a skill → model map in the runner's config, easy to change without a design change. It starts with `/loop-status` on Sonnet 5.5 and every other skill on Opus 5.5. | Juan, 2026-10-20 | Which model sessions use |

## Questions

| # | Question | Blocks | Default if unanswered |
| --- | --- | --- | --- |
| ~~Q1~~ | ~~Can the Claude Agent SDK, in one container per session, run a loop skill on a fresh worktree of this repository, from an installed plugin release, add `Sponsored-by:` to its commits, report tokens and cost, and stop at a budget?~~ → D2 | | |

## Evidence

- 2026-10-20 · Q1 · HOLDS · rung 3 · local @06f4b37 · Yes, for all six parts. Tested in Docker (python:3.12-slim, claude-agent-sdk 0.2.168 bundling Claude Code 2.1.301, linux/arm64; not Cloud Run) against main c6c859c, with Opus 5.5: 9 sessions, $0.94 estimated. Each session got its own container and a fresh clone. `/architect-loop:loop-status` ran from the plugin mounted read-only: a marker added only to that copy came back in 1 turn with 0 tools. A commit-msg hook installed by the runner added `Sponsored-by:` and `Concern:`, but `git commit --no-verify` skips it. Results report tokens (`usage`, `model_usage`), a client-side cost estimate (`total_cost_usd`) and time. `max_budget_usd` stopped all 4 runs that reached it (`error_max_budget_usd`), but only after the response that crossed it: overshoot +$0.0006, +$0.0057, +$0.0118 and +$0.0121, so C2's "before going over" cannot hold as worded. With `dontAsk` and narrow Bash rules, 2 of 4 full `/loop-status` runs ended without a full board after one compound command was denied

## Shipped
