---
needs: []
touches: [plugin/skills/loop-status/SKILL.md, plugin/skills/loop-status/scripts/loop_status.py, tests/test_loop_status.py, tests/fixtures/loop_status/, plugin/skills/loop-plan/SKILL.md, plugin/skills/loop-plan/templates/concern.md]
effects: [a plugin release so that terminals and agents derive needs by the new rule (the owner releases it; gates: release)]
ships-to: main
---
# A concern waits on a need only until that need is proven on some environment

## Done when

- **C1** A concern that nothing has been built for yet is blocked while one of its needs is not met, and a need is
  met as D50 says. Its work is on `main`, and each of its claims has a HOLDS line on some `LOOP.md` §3
  environment, local included, at a commit on `main` with nothing under its `touches` changed since. A claim whose
  Prove names CI holds on `main` while CI is green. The terminal and a supplied facts document give the same
  answer. Prove: fixture tests in CI on main, with a need proven only on a local row, one proven only by CI on
  main, one proven on staging, one whose `touches` changed after its HOLDS, and one with a claim unproven.
- **C2** A blocked concern's reason names each unmet need, the claims of that need that have no current HOLDS
  anywhere, and the command that would prove one (`/loop-prove <loop>/<need> <environment>`), when one of the
  need's own rows serves it (per D1, D2; see C3). That command joins "agents can start now". Prove: fixture tests
  and a text-output test of the board, in CI on main.
- **C3** The board names only a need's own rows as the place to prove it (per D1): `main` for `ships-to: main`,
  and otherwise the rows other than `main`, listed no higher than its `ships-to`, whose names have the same part
  after the `/`. It names the lowest of them that serves the need's work, never another service's row, though
  every row built from this repository serves every concern by ancestry. When none serves it, the blocked
  concern's next step is the need's own, and nothing joins "agents can start now" (per D2). Prove: fixture tests
  in CI on main, with two service rows where one serves a commit that holds the other service's need, and a need
  that none of its own rows serves.

## Design

### Where we are

- Verified 2026-10-22 (`plugin/skills/loop-status/SKILL.md` step 4 and `loop_status.py` on main @e63f06b): the
  table's blocked row says "a concern in `needs` is not done", and done means every claim holds on the need's own
  `ships-to`. With every service and app row unreadable today, that leaves nothing ready (README, Where we are).
- Verified 2026-10-22 (`loop_status.py` on main @e63f06b): the script already reads every evidence line with its
  environment and commit, and asks git which paths changed between two commits. So the rule needs no new facts,
  only a new answer for the blocked row.
- Verified 2026-10-22 (`plugin/skills/loop-plan/templates/concern.md`, line 16): the template says `needs` is "what
  this concern needs first". It does not say what makes a need met, or that what only a concern's proofs rely on
  is not a need (D51).
- Verified 2026-10-23 (`/loop-status` from the installed release, and `prove_environment` in `loop_status.py`,
  on main @1eae0a3): the command a blocked concern's reason names for a need proves it on the first `LOOP.md` §3
  row after `main` whose served commit has every one of the need's merge commits as an ancestor. That row may run
  another service, or sit above the need's `ships-to`. Every service in this repository is built from the same
  `main`, so ancestry is true of every row that serves a recent commit. The board names `staging/runner`, which
  serves 1eae0a3, as the place to prove `status-service`, which ships to `staging/status` (it answers 404). The
  table's merged row ("any lower environment that serves it") has the same gap, although the script names only
  `/loop-ship` there. The table's definition of serves is right for a concern's own `ships-to`, which names its
  own row.

### Approach

Per D50 and D51: the blocked row in the skill's table, and its definitions, state the rule. `loop_status.py`
implements it as `need_met(need)`, from the evidence lines and the CI state already in the facts document, so
nothing is read live and the status service gets the same answer from its own facts (per D15, `status-derivation`
C3). A need's state never changes because of the environment the consumer ships to. The `loop-plan` skill and its
concern template say what `needs` lists (D50, D51). Done keeps its meaning: every claim holds on the concern's own
`ships-to` (per D54).

This concern goes first. `addressed-to-people` changes the same script and skill, so it needs this one. Until a
release carries this change, agents run the installed release and see the old rule (per D17).

Per D1 and D2: the table gains a definition of a concern's own rows, the only rows the board names to prove it,
and the blocked and merged rows use it. The definition of serves keeps its meaning for a concern's own
`ships-to`, which names its own row. `prove_environment` in `loop_status.py` looks only at the need's own rows,
from the lowest up, and returns none when none serves its work, so the blocked concern's next step falls to the
need's own and `prove_needs` stays empty for it. It reads only the row names and served commits already in the
facts document. A fixture case has two service rows, one serving a commit that holds the other's need (C3).

Rollback: revert the PR. Needs then read by the old rule again, and no data is written.

## Decisions

| # | Decision | Decided by, date | Closes |
| --- | --- | --- | --- |
| D1 | The board names a `LOOP.md` §3 row as the place to prove a concern only when it is one of the concern's own rows: the part of its name after the `/` matches the concern's `ships-to` (or neither has one), and it is listed no higher than `ships-to`. `main` counts only for `ships-to: main`. The definition of serves stays as it is for a concern's own `ships-to`. | Juan, 2026-10-24 | Q1 |
| D2 | When none of a need's own rows serves its work, the blocked concern's next step is the need's own next step, and no proof of that need joins "agents can start now". | Juan, 2026-10-24 | Q2 |

## Questions

| # | Question | Blocks | Default if unanswered |
| --- | --- | --- | --- |
| ~~Q1~~ | ~~Which `LOOP.md` §3 rows may the board name as the place to prove a concern, when every row built from this repository serves every commit on `main` by ancestry? (raised by `/loop-status` on main @1eae0a3, which names `staging/runner` to prove `status-service`)~~ → D1 | | |
| ~~Q2~~ | ~~When no such row serves a need's work, what does the blocked concern's next step name?~~ → D2 | | |

**Q1 options**
- **Rows of its own service**: a row counts only when the part of its name after the `/` matches the concern's
  `ships-to` (or neither has one, in a project with one row per environment) and it is listed no higher than
  `ships-to`; `main` counts only for `ships-to: main`. No new front matter, it follows §3's
  `<environment>/<service>` names, and command-center/D53's `local/<service>` rows come first once they exist. A
  concern whose code runs in two services is proven only on its own service's rows. (recommended)
- **A `proves-on:` list in front matter**: each concern names the rows that run its code. Exact across services,
  but every concern and the `loop-plan` template gain a field, and a concern without one falls back to today's
  rule.
- **Its own `ships-to` only**: never look lower. Simplest, but it never names `local/<service>` rows, and a project
  with `staging` and `production` rows is told to prove on production.
- **Rows whose service folder it touches**: match `touches` against `services/<service>/`. Exact here, but it
  writes this repository's layout into a skill that must stand alone (command-center/D14, `LOOP.md` §6).

**Q2 options**
- **The need's own next step**: `/loop-ship staging/status` while the need is merged, or "Check that
  staging/status answers" while that row reads unknown, and nothing joins "Agents can start now", since no agent
  can prove what no row runs. The merged row already works this way. (recommended)
- **Its `ships-to`, as today**: `/loop-prove <need> <ships-to>` is listed for agents, and a run there finds
  nothing served and records at most UNPROVEN.

## Evidence

- 2026-10-26 · C1 · HOLDS · rung 5 · main @e022011 · Run on e022011 (`python3 -m unittest tests.test_loop_status`, 73 tests, OK; the `check` workflow, which runs them, is green on that commit). Against the same tests with `loop_status.py` as it was before the concern (the parent of #32's merge, 3b1d975), 16 of the 73 fail, each of the tests named here among them, so they exercise the new rule and not a path that no longer matters. C1's five cases each have a test: a need proven only on a local row (`test_a_need_proven_only_on_a_local_row_is_met`, and unmet once LOOP.md no longer lists local), only by CI on main (`..._by_ci_on_main_is_met_while_ci_is_green`, blocked when CI is failure, unknown when it cannot be read), on a lower environment, one whose `touches` changed after its HOLDS (`..._whose_touches_changed_after_its_holds_is_not_met`), and one with a claim unproven (`..._with_a_claim_unproven_is_not_met_and_says_how_to_prove_it`). The terminal and a supplied facts document give the same document in `test_supplied_facts_give_the_same_document`, `test_a_facts_document_derives_the_same_after_a_round_trip` and `test_the_command_line_gives_the_same_document_every_way`. One commit, and the tests run on Python 3.11 locally and 3.12 in CI
- 2026-10-26 · C3 · HOLDS · rung 5 · main @e022011 · Run on e022011 (`python3 -m unittest tests.test_loop_status`, 73 tests, OK; the `check` workflow, which runs them, is green on that commit). Against the same tests with `loop_status.py` as it was before the concern (the parent of #32's merge, 3b1d975), 16 of the 73 fail, each of the tests named here among them, so they exercise the new rule and not a path that no longer matters. `test_a_need_is_proven_only_on_its_own_services_rows` has four rows, with `staging/runner` serving a commit that holds the status service's need, and asserts the board never names it: with `staging/status` unreadable the next step is the need's own, nothing joins agents can start, then `/loop-ship staging/status`, then `/loop-prove loop/base local/status` as the lowest of its own rows that serves it, a row above its `ships-to` is not its own, and the runner's row is the place only for the runner's own concern. `test_the_table_proves_a_concern_only_on_its_own_rows` pins the same rule in SKILL.md's table. One commit

## Shipped
