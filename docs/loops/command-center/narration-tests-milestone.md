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

## Shipped
