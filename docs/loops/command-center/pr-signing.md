---
needs: []
touches: [services/runner/runner/session.py, services/runner/runner/github.py, services/runner/runner/trailers.py, services/runner/runner/workspace.py, services/runner/tests/]
effects: [staging/runner redeployed so that it serves this concern (the owner deploys it; gates: deploy), one dispatched `/loop-prove` session for the staging proof, about $0.43 as 7f88c4f spent on b2fbcfb (the owner starts it; gates: spending)]
ships-to: staging/runner
---
# Every runner session's pull requests are signed, and only a build's name a concern

## Done when

- **C1** When a session ends, every pull request opened from a branch it pushed carries `Sponsored-by: <person>` in
  its body, whether it is still open, already merged or closed, and the session's record lists each one (per
  `runner-dispatch` D1). Prove: the runner's tests with a fake GitHub in which the session's PR merged before the
  session ended, and one that is still open, in CI on main, then a dispatched `/loop-prove` on staging/runner that
  merges its own loop-document PR, reading that PR's body and the session's `pull_requests` back.
- **C2** No commit or pull-request body from a session whose skill is not `/loop-build` carries `Concern:`. A
  `Concern:` line such a session writes itself is removed by the commit-msg hook and by the PR-body step, and a
  `/loop-build` session's is kept (per command-center/D73, D45). Prove: tests of the hook and of `with_trailers` for
  each skill, with a session-written `Concern:` in a commit message and in a PR body, in CI on main, then the same
  dispatched `/loop-prove` on staging/runner, listing its commit's trailers and its PR body.

## Design

### Where we are

- **Verified** (main @142917d, `services/runner/runner/`, unchanged since b2fbcfb, which staging/runner serves):
  `session.py`'s `_sign_pull_requests` runs at a session's end, lists the branches the clone pushed
  (`workspace.py`'s `pushed_branches`), asks `github.py`'s `pull_requests_for_heads` for their PRs with
  `state=open`, and puts the trailers in each body with `with_trailers`. Narration also calls
  `pull_requests_for_heads` while the session runs, to post "PR opened", and wants only open PRs there.
- **Verified** (`with_trailers`, `session.py` lines 80 to 97, and the commit-msg hook `workspace.py` installs, with
  `trailers.py`): `Concern:` is added only in a `/loop-build` session (per command-center/D45), but a `Concern:`
  line already in a message or body is kept, whatever the skill.
- **Verified** (staging/runner @b2fbcfb, 2026-10-27, `runner-dispatch`'s C1 evidence): five `/loop-prove`
  sessions merged their own PRs (#96, #97, #102, #103, #104) before ending, and none of their bodies has
  `Sponsored-by:`; their commits all do. #96's commit and body carry a session-written `Concern:`, so
  `/loop-status` counts #96 and bd8e230 as `local-harness`'s work.
- `.github/workflows/trailers.yml` runs `trailers.py` from the base branch to fail a PR with a runner commit lacking
  `Sponsored-by:` (`session-runner` D4). It checks commits, not bodies, and this concern does not change what it
  checks.

### Approach

Per `runner-dispatch` D1, D2 and command-center/D73, D45:

- **Lookup:** the end-of-session step asks for the pushed branches' PRs in every state (`state=all`), and
  narration's call keeps asking for open ones only, so "PR opened" is unchanged.
- **Signing:** `with_trailers` adds `Sponsored-by:` to any body that lacks it, open or merged, and, for a session
  that is not `/loop-build`, drops a `Concern:` line; for `/loop-build` it keeps the skill's or adds its own. The
  session's record lists every PR found.
- **Commits:** the commit-msg hook drops a `Concern:` trailer from a non-build session's message before adding
  `Sponsored-by:`, so nothing a proof, design or record session commits links as build work.
- **Tests:** the existing suites in `services/runner/tests/` gain the cases, with the fake GitHub returning a
  merged PR for a pushed branch.

Rollback: redeploy the previous revision. PR bodies already signed stay signed, and a `Concern:` already removed is
not put back. Commits already on `main` keep the trailers they have.

## Decisions

| # | Decision | Decided by, date | Closes |
| --- | --- | --- | --- |

## Questions

| # | Question | Blocks | Default if unanswered |
| --- | --- | --- | --- |

## Evidence

## Shipped
