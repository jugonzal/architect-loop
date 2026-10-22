---
needs: []
touches: [services/runner/, .github/workflows/trailers.yml, .github/workflows/runner.yml]
effects: [Agent SDK sessions that cost money, each with a budget shown to its sponsor before it starts (spending), Cloud Run jobs in the staging and production GCP projects (spending; cloud IAM), the runner's own Firestore database for sessions and spend in each project (spending; cloud IAM; per command-center/D26, D44), the Anthropic API key and the runner's own GitHub App that pushes branches and opens PRs on jugonzal/architect-loop (secrets; identity and access; per command-center/D27), the repository made public and main protected so that nothing reaches it except through a PR (publishing and a repository setting; the owner does both, per command-center/D24), the trailer check made a required status check on main (a repository setting; the owner sets it, per D4)]
ships-to: production/runner
---
# A person can start a loop skill on a concern as a session that names them as its sponsor and stops at a budget

## Done when

- ~~**C1** Dispatching a skill (`/loop-design`, `/loop-build`, `/loop-prove`, `/loop-status`) on a named concern,
  through the API in `services/runner/openapi.yaml` (per command-center/D29), starts one session in its own
  worktree. Every commit and PR it produces carries `Sponsored-by: <person>` beside `Concern:`, and a PR with a
  runner commit that lacks it fails the required trailer check (per D4). Prove: the runner's API tests against
  `openapi.yaml`, in CI on main, then a dispatched `/loop-build` on a test concern, with the PR and commits shown,
  plus a runner commit made with `--no-verify` on a test branch, on staging.~~ Superseded by C5, 2026-10-20: only
  a `/loop-build` session's work carries `Concern:` (per command-center/D45).
- ~~**C2** A session that reaches its budget stops before going over, and reports what it spent in tokens, money
  and wall-clock time. Prove: a dispatch with a deliberately small budget, on staging.~~ Contradicted by the Q1
  spike (2026-10-20): the SDK stops only after the response that crosses the budget. Superseded by C4 (per D21).
- ~~**C3** A second dispatch on a concern that already has an open PR or a running session is refused, and so is
  a dispatch that would take its sponsor past their cap of running sessions (per D22). Each refusal names the
  existing PR or sessions. Prove: a double dispatch, and one dispatch over a cap lowered to 1, on staging.~~
  Superseded by C6, 2026-10-20: only `/loop-build` and `/loop-design` hold a concern (per D6), and a budget has a
  ceiling (per D8).
- **C4** While it runs, a session publishes its approximate spend at least every 10 seconds. It stops at the
  first model response that crosses its budget, and reports its final estimated spend: tokens, dollars
  (overshoot included) and wall-clock time (per D21, D23). Prove: a dispatch with a deliberately small budget,
  comparing the published spend with the SDK's result, on staging.
- **C5** Dispatching a skill (`/loop-design`, `/loop-build`, `/loop-prove`, `/loop-status`) on a named concern,
  through the API in `services/runner/openapi.yaml` (per command-center/D29), starts one session in its own
  worktree. Every commit and PR it produces carries `Sponsored-by: <person>`, and a `/loop-build` session's also
  carry `Concern:` (per command-center/D45). A PR with a runner commit that lacks `Sponsored-by:` fails the
  required trailer check (per D4). Prove: the runner's API tests against `openapi.yaml`, in CI on main, then a
  dispatched `/loop-build` and a dispatched `/loop-design` on a test concern, with their PRs and commits shown,
  plus a runner commit made with `--no-verify` on a test branch, on staging/runner and then production/runner
  (per command-center/D43).
- **C6** While a concern has an open PR, or a `/loop-build` or `/loop-design` session is running on it, a
  dispatch of either of those two skills on it is refused, naming the PR or the session. `/loop-prove` and
  `/loop-status` are admitted beside them (per D6). A dispatch that would take its sponsor past their cap of
  running sessions (per D22), or whose budget is above the ceiling (per D8), is refused, naming the cap or the
  ceiling. Prove: a double `/loop-build`, a `/loop-prove` beside it, one dispatch over a cap lowered to 1, and one
  over the ceiling, on staging/runner and then production/runner.

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
- Verified 2026-10-20 (`gh api repos/jugonzal/architect-loop/rulesets/<id>`): the repository is public, and an
  active ruleset protects `main` with no bypass. It requires a pull request and the `skills` check, and blocks
  force pushes and deletion, which is what D3 counts on (per command-center/D24). Making `trailers` required is
  still this concern's effect, once its workflow exists. (Corrected 2026-10-20: this said `main` had no
  protection and could have none while the repository was private.)
- Verified 2026-10-20 (`git tag -l`): release v0.3.0 is tagged at fbd6d0b, so the job has a release to install.
  (Corrected 2026-10-20: this listed a tagged release as missing.)
- Verified 2026-10-20 (main @a9fde89, PR #20): the service and the job are built, with 149 tests in
  `services/runner/tests/` run by `runner.yml`, and `trailers.yml` checks PRs. The job adds `Concern:` to every
  session's commits and PR body, whatever the skill. Any open PR or running session refuses every skill on its
  concern. A dispatch must name a concern, and only `loop-design`, `loop-build`, `loop-prove` and `loop-status` can
  be dispatched. Any positive budget is accepted. The only store is SQLite. The job holds the app's private key and
  mints its own installation tokens, which expire after an hour (GitHub's docs, read 2026-10-20), and nothing
  refreshes them. The service reads its commit from `COMMIT_SHA` (per command-center/D47). The changes these
  decisions call for are built by `runner-dispatch` (C5, C6) and `runner-store` (per command-center/D44).
- Missing:
  - staging's GCP projects (`environments` creates them, per command-center/D31; corrected 2026-10-20: this said
    `status-service`);
  - the GitHub App (in effects).

### Approach

Per command-center/D8, and D1 and D2 here:
- **Dispatch:** a Cloud Run service takes dispatches and starts one Cloud Run job per session. The sponsor comes
  from the caller's GitHub identity, read with `GET /user` on the caller's token and checked as a collaborator
  with the runner's own app, never from the request body (per command-center/D27, D28). The service refuses a
  `/loop-build` or `/loop-design` dispatch on a concern that has an open PR or a running session of either skill
  (per D6), one past the sponsor's cap of running sessions (per D22), and one whose budget is above the ceiling
  (per D8).
- **The job:** it clones `jugonzal/architect-loop` into a fresh worktree on `<loop>/<concern>` and installs the
  plugin release named in the dispatch, never using the worktree's own `plugin/` (per D17). It runs the skill
  with the Agent SDK:
  - permissions: `dontAsk`, allowing Bash, Read, Write, Edit, Glob, Grep and Skill (per D3);
  - empty `setting_sources`;
  - the model for that skill from the runner's config (per D5);
  - `max_budget_usd` set to the session's budget (per D21).
- **Trailers:** the job installs a commit-msg hook that adds `Sponsored-by:`, and `Concern:` only in a
  `/loop-build` session (per command-center/D45), and puts the same trailers in PR bodies. `.github/workflows/trailers.yml` fails any PR with a commit from the runner's GitHub App
  that lacks `Sponsored-by:` (per D4). Skills write to the repository exactly as they do from a terminal (per D1).
- **Spend:** the job publishes spend while it runs and at the end (per D23). Before a start, the service answers
  an estimate for a skill and model: the median of that pairing's last 10 sessions. A pairing with no measured
  sessions has no estimate. The Opus 5.5 numbers above seed the first pairings.
- **API** (per command-center/D29): `services/runner/openapi.yaml` describes dispatch (skill, concern,
  arguments passed to the skill, budget, plugin release), the sponsor's running sessions with their spend, stop,
  and the estimate before a start. The app concerns generate their clients from it.
- **Store** (per command-center/D26, D44): the runner keeps sessions and their spend in a Firestore database of
  its own in each environment, and nothing else does. A dispatch claims its concern there atomically, so two dispatches at once
  cannot both start. Wiping it loses the estimates' history and nothing about any loop (G4).
- **Build and deploy:** Python 3.12, tests in `services/runner/tests/`, run by `.github/workflows/runner.yml`
  (per command-center/D30), and the deploy convention of command-center/D32.
- **Claims and limits:** the open PR, or a running `/loop-build` or `/loop-design` job, is the claim on a concern
  (C6, per D6). The runner's config holds the per-sponsor cap (3), the budget ceiling ($10, per D8) and the
  skill → model map, and changing any of them is a config change, not a design change.
- **Key** (per D7): the job holds the app's private key, as built, and mints the session's installation tokens.
  A session may run any Bash in its container (per D3), so it can read the key. The owner accepted that.
- **Deploy config** (per command-center/D46): the runner's manifest, `services/runner/service.json`, comes from
  `service-manifests`.
- **Rollback:** a stopped job leaves its branch and PR for a person to close. The runner merges nothing.

## Decisions

| # | Decision | Decided by, date | Closes |
| --- | --- | --- | --- |
| D1 | The first spike tests the Claude Agent SDK on our own workers, one container per session. GitHub Actions is the fallback if it fails. | Juan, 2026-10-20 | Narrows Q1 (was the loop's Q4) |
| D2 | The runner uses the Claude Agent SDK, one Cloud Run job per session. The GitHub Actions fallback is dropped: the spike held on all six parts of Q1. | Juan, 2026-10-20 | Q1 |
| D3 | Inside its container, a session may run any Bash command. It runs in `dontAsk` mode, allowing Bash, Read, Write, Edit, Glob, Grep and Skill. The container is the sandbox, and the limits live outside the session: its own clone, the GitHub App's permissions, a protected main, and the budget. | Juan, 2026-10-20 | The spike's give-ups on denied compound commands |
| D4 | Trailers are added by a commit-msg hook the runner installs, and enforced by a required CI check that fails any PR with a runner commit lacking `Sponsored-by:`. | Juan, 2026-10-20 | The spike's finding that `--no-verify` skips hooks |
| D5 | Each skill's model comes from a skill → model map in the runner's config, easy to change without a design change. It starts with `/loop-status` on Sonnet 5.5 and every other skill on Opus 5.5. | Juan, 2026-10-20 | Which model sessions use |
| D6 | Only `/loop-build` and `/loop-design` hold a concern. While it has an open PR, or one of those two runs on it, a second dispatch of either is refused. `/loop-prove` and `/loop-status` run beside them, so a proof can go into an open PR's body. | Juan, 2026-10-20 | Q2 |
| D7 | The job holds the runner app's private key, as built. A session may run any Bash in its container (per D3), so it could read the key and mint tokens with all the app's rights. The protected `main` limits what that can do to `main`, not to other branches or PRs. Accepted over having the service mint each session's token. | Juan, 2026-10-20 | Q3 |
| D8 | A dispatch whose budget is above $10 is refused, naming the ceiling. The ceiling lives in the runner's config, and the runner's own medians (per command-center/D23) show when to raise it. | Juan, 2026-10-20 | Q4 |
| D9 | The estimate before a start (per command-center/D23) counts sessions stopped by their budget or their sponsor, as built. | Juan, 2026-10-20 | Confirms PR #20 |

## Questions

| # | Question | Blocks | Default if unanswered |
| --- | --- | --- | --- |
| ~~Q1~~ | ~~Can the Claude Agent SDK, in one container per session, run a loop skill on a fresh worktree of this repository, from an installed plugin release, add `Sponsored-by:` to its commits, report tokens and cost, and stop at a budget?~~ → D2 | | |
| ~~Q2~~ | ~~Which dispatches are refused while a concern has an open PR or a running session, when refusing every skill keeps `/loop-prove` out of the PR it proves? (raised by this concern's build)~~ → D6 | | |
| ~~Q3~~ | ~~Who holds the runner app's private key, when a session can read anything in its container? (raised by this concern's build)~~ → D7 | | |
| ~~Q4~~ | ~~Is there a ceiling on a session's budget? (raised by this concern's build)~~ → D8 | | |

## Evidence

- 2026-10-20 · Q1 · HOLDS · rung 3 · local @06f4b37 · Yes, for all six parts. Tested in Docker (python:3.12-slim, claude-agent-sdk 0.2.168 bundling Claude Code 2.1.301, linux/arm64; not Cloud Run) against main c6c859c, with Opus 5.5: 9 sessions, $0.94 estimated. Each session got its own container and a fresh clone. `/architect-loop:loop-status` ran from the plugin mounted read-only: a marker added only to that copy came back in 1 turn with 0 tools. A commit-msg hook installed by the runner added `Sponsored-by:` and `Concern:`, but `git commit --no-verify` skips it. Results report tokens (`usage`, `model_usage`), a client-side cost estimate (`total_cost_usd`) and time. `max_budget_usd` stopped all 4 runs that reached it (`error_max_budget_usd`), but only after the response that crossed it: overshoot +$0.0006, +$0.0057, +$0.0118 and +$0.0121, so C2's "before going over" cannot hold as worded. With `dontAsk` and narrow Bash rules, 2 of 4 full `/loop-status` runs ended without a full board after one compound command was denied

## Shipped
