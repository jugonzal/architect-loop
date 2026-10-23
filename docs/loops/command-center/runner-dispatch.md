---
needs: []
touches: [services/runner/runner/, services/runner/openapi.yaml, services/runner/tests/]
effects: []
ships-to: staging/runner
---
# A runner dispatch holds a concern only when its skill changes it

## Done when

- **C1** Only a `/loop-build` session's commits and PR body carry `Concern: <loop>/<concern>`. Every session's
  commits and PRs carry `Sponsored-by: <person>`, whatever its skill (per command-center/D45). Prove: the job's
  tests for each skill it can run, in CI on main, then a dispatched `/loop-build` and a dispatched `/loop-design`
  on a test concern in the sandbox loop (per command-center/D61), with their commits' trailers listed, on
  staging/runner (per command-center/D54).
- **C2** A `/loop-build` or `/loop-design` dispatch on a concern that has an open PR, or a running session of
  either skill, is refused, naming the PR or the session. `/loop-prove` and `/loop-status` on that concern are
  admitted (per `session-runner` D6). A dispatch past its sponsor's cap of running sessions (per command-center/D22),
  or with a budget above the ceiling in the runner's config, $10 (per `session-runner` D8), is refused, naming
  the cap or the ceiling. Prove: API tests against `services/runner/openapi.yaml` for each case, in CI on main,
  then the same dispatches on staging/runner (per command-center/D54).
- **C3** A dispatch may name a loop or an environment instead of a concern: `/loop-ship <environment>`,
  `/loop-status <loop>` and `/loop-design <loop>`, and such a dispatch holds no concern. Each session's final
  message is kept and served with the session (per `app-inbox` D1, D2, D3). Prove: API and job tests, in CI on
  main, then a dispatched `/loop-ship` whose brief is read back from the runner, on staging/runner (per
  command-center/D54).

## Design

### Where we are

- Verified 2026-10-20 (main @a9fde89, `services/runner/runner/`):
  - `session.py` adds `Concern:` to every session's commits and PR body, beside `Sponsored-by:`, whatever the
    skill.
  - `config.py` lists the skills that can be dispatched, `loop-design`, `loop-build`, `loop-prove` and
    `loop-status`, and `dispatch.py` requires every dispatch to name a concern and accepts any positive budget.
  - `store.py`'s claim refuses any dispatch on a concern that has an open PR or a running session, whatever the
    skill. The only store is SQLite; `runner-store` adds Firestore after this concern (per command-center/D44).
  - Nothing keeps a session's final message.
- `session-runner`'s C5 and C6 are the claims this concern's change makes true for the runner as a whole. Its C1
  and C3, which described the runner as built, are struck (2026-10-20).

### Approach

Per command-center/D45, `session-runner` D5, D6 and D8, and `app-inbox` D1 to D3:

- **Trailers:** the commit-msg hook and the PR-body step add `Concern:` only when the session's skill is
  `loop-build`. `Sponsored-by:` stays on every session's work, so the trailer check (`session-runner` D4) is
  unchanged.
- **Claims:** a concern is held by an open PR or by a running `loop-build` or `loop-design` session. The store's
  claim takes the skill, and refuses only those two skills on a held concern. `loop-prove` and `loop-status`
  sessions are admitted and hold nothing.
- **Limits:** the config gains a budget ceiling, $10 by default, and a dispatch above it is refused with a new
  refusal reason in `openapi.yaml`. The sponsor cap (D22) still counts every running session.
- **Scope:** a dispatch names exactly one of a concern, a loop or an environment. `loop-ship` joins the skill →
  model map on Opus 5.5, like every skill but `loop-status` (per `session-runner` D5). A loop- or
  environment-scoped session clones `main` and pushes no branch of its own unless its skill opens a PR.
- **Final message:** the job stores the session's last assistant message with its result, and the session
  resource in `openapi.yaml` serves it.
- **Tests:** the existing suite in `services/runner/tests/` is updated, not replaced, and `contract.py` keeps
  checking every answer against `openapi.yaml`.

The sessions this lets start cost money, under `session-runner`'s effects. Rollback: revert the PR. A session in
flight finishes under the code it started with.

## Decisions

| # | Decision | Decided by, date | Closes |
| --- | --- | --- | --- |

## Questions

| # | Question | Blocks | Default if unanswered |
| --- | --- | --- | --- |

## Evidence

## Shipped
