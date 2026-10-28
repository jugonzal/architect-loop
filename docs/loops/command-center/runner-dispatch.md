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

  (Superseded 2026-10-22, main @18b866b, by PR #24 (900dc5a): `session.py` adds `Concern:` only in a
  `/loop-build` session, and `Sponsored-by:` in every one (per command-center/D45). `config.py` lets a dispatch
  name a concern, a loop or an environment, adds `loop-ship`, and lists `HOLDING_SKILLS` as `loop-build` and
  `loop-design`, which `store.py`'s claim uses. `dispatch.py` refuses a budget above `budget_ceiling_usd`, $10 by
  default. `models.py` keeps each session's `final_message`, and `openapi.yaml` serves it. The store is still
  SQLite only.)
- `session-runner`'s C5 and C6 are the claims this concern's change makes true for the runner as a whole. Its C1
  and C3, which described the runner as built, are struck (2026-10-20).
- Verified 2026-10-28 (main @142917d, unchanged under `services/runner/runner/` since b2fbcfb): `_sign_pull_requests` in `session.py` signs only what `github.py`'s `pull_requests_for_heads` returns, which asks GitHub for `state=open` pulls, and `with_trailers` keeps a `Concern:` the skill wrote (lines 84 to 94), as does the commit-msg hook in `workspace.py`. `/loop-status` links a PR whose body carries `Concern: <loop>/<concern>`, and a commit on main with that trailer, as the concern's work: #96 and its commit bd8e230 now count as `local-harness`'s. Both are corrected by `pr-signing` (per D1, D2 and command-center/D73).

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
| D1 | At a session's end, the runner signs every pull request opened from a branch the session pushed, whether it is open, merged or closed, and lists each one in the session's record. A loop-document PR the session merged itself under LOOP.md §2.1 is signed after its merge, since GitHub lets a merged PR's body be edited, and nothing checks a body before the merge. | Juan, 2026-10-28 | The 2026-10-27 CONTRADICTS of C1: five `/loop-prove` sessions merged their own PRs before ending, and `pull_requests_for_heads` asks only for `state=open` |
| D2 | The fix is a new concern, `pr-signing`, not a second build of this one, whose work is already on `main`, so the board shows it as building while it is. This concern's claims keep their wording, and C1 is proven again on staging/runner once `pr-signing` is served (with command-center/D73). | Juan, 2026-10-28 | Where the fix is built |

## Questions

| # | Question | Blocks | Default if unanswered |
| --- | --- | --- | --- |

## Evidence

- 2026-10-27 · C1 · CONTRADICTS · rung 1 · staging/runner @b2fbcfb · Every session's PRs do not carry `Sponsored-by:`. Seven sessions the owner dispatched on staging/runner at b2fbcfb (each job's COMMIT_SHA, from `gcloud run jobs executions describe`; skill, sponsor and PRs from each session's document in the runner's Firestore database `runner`): one `/loop-build` (a8982fd, PR #90), one `/loop-status command-center` (006fdb4, PR #98) and five `/loop-prove` (7f88c4f #96, 4cf25db #97, 4639c61 #102, d77008b #103, 17acc5a #104). All seven PRs' commits carry `Sponsored-by: jugonzal` as a git trailer. But only #90's and #98's bodies have a `Sponsored-by:` line: the five `/loop-prove` sessions each merged their own loop-document PR under LOOP.md §2.1 before they ended (#96 merged 22:22:31Z, its session ended 22:22:44Z), and at session end `_sign_pull_requests` asks GitHub only for `state=open` pulls on the pushed branches (`services/runner/runner/github.py` `pull_requests_for_heads`), so it found none, signed none, and recorded `pull_requests: []` for all five. #98, whose session ended with its checks pending and the PR open, was signed. The `Concern:` half: #90 carries it, as it should, and #96, a `/loop-prove`, carries `Concern: command-center/local-harness` in its commit and body, written by the skill, which `with_trailers` keeps by design (`session.py` lines 84 to 94), so the claim's "only a `/loop-build` session's" is false as worded while the runner itself added no `Concern:` to a non-build session. No `/loop-design` has been dispatched on b2fbcfb
- 2026-10-27 · C3 · UNPROVEN · rung 1 · staging/runner @b2fbcfb · Half observed. Session 006fdb4 was a dispatch that named a loop, not a concern: `/loop-status` with loop `command-center`, concern null and branch `main` in its Firestore document, and it held no concern. All seven sessions on b2fbcfb kept their final message in the store (`final_message`, non-empty for each). Not yet shown: a `/loop-ship <environment>` dispatch, and the final message served back by the runner's API, which needs a sponsor's GitHub sign-in this session does not have

## Shipped
