---
needs: []
touches: [services/runner/runner/session.py, services/runner/tests/test_narration.py]
effects: []
ships-to: staging/runner
---
# A tests milestone appears only for a command that runs tests

## Done when

- **C1** A Bash command whose heredoc body mentions a test tool (`check.sh`, `unittest`, `pytest`) but whose own
  text does not run one posts no tests milestone, and a command that runs tests still posts one with its result.
  Prove: the runner's tests, with the two commands seen on staging as fixtures (`git commit -q -F - <<'EOF'` with a
  body naming `sh scripts/check.sh`, and `cat > /tmp/prbody.md <<'EOF'` with a body naming `unittest`) beside
  `pytest -q`, `sh scripts/check.sh` and `python3 -m unittest discover`, by CI on main (rung 5).
- **C2** In a staging session whose commit message and PR body name `check.sh`, the thread shows a tests milestone
  for each test command the session reports running and for no other command. Prove: a dispatched `/loop-build`
  on a sandbox target (per command-center/D61), reading its thread beside its final message, on staging/runner.

## Design

### Where we are

- Verified (`services/runner/runner/session.py` on main @82764b6, 2026-10-26): `TEST_COMMAND` is a regular expression
  over a Bash command's whole text, and `_tool_result` posts a tests milestone when `TEST_COMMAND.search(command)`
  matches. A heredoc body is part of that text. `tests_milestone` then words the post with `failed` or `passed` from
  the tool result, so a `git commit` that exits 0 reads as "Tests run, passed".
- Verified (staging/runner @633cbe4, session c79c36c, 2026-10-26): the thread showed "Tests run, passed" for
  `git add sandbox/build-target-3/hello.txt && git commit -q -F - <<'EOF'` and for `cat > /tmp/prbody.md <<'EOF'`,
  neither of which runs tests. Both carry a heredoc whose body names a test tool.
- Verified: `services/runner/tests/test_narration.py` tests `tests_milestone`'s wording and the real test commands,
  and has no case where a test tool is only mentioned.
- Missing: the false posts have not been reproduced by running the matching on those two commands. C1 does that
  first.

### Approach

Before matching `TEST_COMMAND`, remove each heredoc body from the command: a `<<` or `<<-` followed by a word, bare or
quoted, takes everything from the next line up to the line that is only that word. Match the rest. The `PR_CREATE` and
`GIT_PUSH` matches are left on the whole text (per D1). Add the two observed commands as failing tests first, then the
change. Quoted arguments are not stripped (per D1): `sh -c "pytest"` still counts, and a quoted
`git commit -m "run check.sh"` would still post one, which no run has shown.

## Decisions

| # | Decision | Decided by, date | Closes |
| --- | --- | --- | --- |
| D1 | The tests milestone ignores heredoc bodies, and only them. Quoted text is still matched, so `sh -c "pytest"` counts and a quoted mention of a test tool may still post one. | Juan, 2026-10-26 | How the false posts of session c79c36c are fixed |

## Questions

| # | Question | Blocks | Default if unanswered |
| --- | --- | --- | --- |

## Evidence

- 2026-10-26 · C1 · HOLDS · rung 5 · main @b2fbcfb · The `runner` workflow, `python -m unittest discover -s tests -t .` on Python 3.12, succeeded on b2fbcfb (the merge of #88): `HeredocTest` and `TestsMilestoneTest` pass, with the two commands seen on staging @633cbe4 as fixtures (a `git commit -F - <<'EOF'` and a `cat > /tmp/prbody.md <<'EOF'` whose bodies name `check.sh` and `unittest`) posting no tests milestone, and `pytest -q`, `sh scripts/check.sh`, `python3 -m unittest discover`, `sh -c "pytest -q"` and a test run beside a heredoc still posting one. Before the change, 3 of these tests failed against the old matching on the same fixtures; the PR body has that run. A quoted `git commit -m "run check.sh"` still matches, as its D1 says
- 2026-10-26 · ship · verified · staging @b2fbcfb · the owner ran `deploy.sh runner staging b2fbcfb`; I then read it: `served.sh https://runner-665570365697.us-east1.run.app/version b2fbcfb` printed b2fbcfb8b17a909974eab83f3bfd2d3196ae9b90 and exited 0, threads still serves 1eae0a3, and `gcloud run services describe runner` read back image tag and COMMIT_SHA b2fbcfb, identity runner@loops-512401, Ready True (revision runner-00003-rmb) and RUNNER_THREADS_URL https://threads-665570365697.us-east1.run.app; the `runner-session` job has the same image, COMMIT_SHA and RUNNER_THREADS_URL; the runner logged no warning or error in the last 2 hours; no session was dispatched, so C2 is not yet proven
- 2026-10-26 · C2 · HOLDS · rung 2 · staging @b2fbcfb · Session a8982fd, started by the owner from the app at 20:31:48Z on sandbox/build-target-3 with a $3.00 budget (job `runner-session-jbnw9`, ended `completed` at 20:35:34.93Z, opened PR #90; the app shows about $0.29 spent over 211 s, an estimate); served commit re-read as b2fbcfb before. Nobody wrote to the thread. The PR body the session wrote names both `python3 -m unittest discover -s tests` and `CHECK_SKIP_TESTS=1 sh scripts/check.sh`, the text that made the first run post "Tests run, passed" for a `cat` and a `git commit`. This time the thread has exactly one tests milestone, for a chained command that begins `git log -1 --format=%B | git interpret-trailers … | git commit -q --amend -F - && git log -1 …` and whose output is "Ran 299 tests in 149.512s; OK", so it ran tests; no tests milestone for the commands that wrote the commit message or the PR body. Not shown: that no second test command ran separately. The post cuts the command at 160 characters, and the session's own account (299 tests and check.sh both pass) fits one chained command but cannot confirm it. A real test run posting a milestone beside a heredoc is C1's CI proof. One run
## Shipped
