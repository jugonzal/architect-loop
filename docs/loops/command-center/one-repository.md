---
needs: []
touches: [architect-loop:plugin/, architect-loop:skills/, architect-loop:.claude-plugin/marketplace.json, architect-loop:scripts/install.sh, architect-loop:scripts/check.sh, architect-loop:tests/, architect-loop:README.md, architect-loop:docs/adopting.md, architect-loop:docs/upgrading.md, architect-loop:LOOP.md, architect-loop:docs/proposals/command-center.md, architect-loop:.github/workflows/check.yml]
effects: [a new LOOP.md in architect-loop carrying this project's contract with D14 and D17 as rules (a change to the contract; the owner merges it; gates: merge), the plugin marketplace source moving to ./plugin which changes how everyone installs (released by the owner as a new version per D17; gates: release), archiving jugonzal/loops once the loop has moved (the owner does it)]
ships-to: main
---
# The skills and the command center share one repository, and installing the plugin still ships only the skills

## Done when

- **C1** Installing from architect-loop gives exactly the `loop-*` skills and nothing from `app/` or `services/`,
  both through the plugin marketplace and through `scripts/install.sh --project` (per D16). Prove: install from
  main into an empty project both ways and list what arrived, on main.
- **C2** CI fails when anything under `plugin/` refers to `app/`, `services/` or the command center's runtime, and
  passes on main (per D14). Prove: a test that plants such a reference in a fixture and expects the check to
  fail, in CI on main.
- ~~**C3** `/loop-status`, run in architect-loop from an installed release, shows the `command-center` loop with
  the same state for every concern as a run in `jugonzal/loops` at the same moment. Prove: both runs side by
  side, on main, after the loop-document PR that moves `docs/loops/command-center/`.~~ Contradicted 2026-10-20,
  superseded by C4 (per D1).
- **C4** The loop arrived whole. `docs/loops/command-center/` on architect-loop's main at the move (4e7bf9a) is
  byte-identical to `jugonzal/loops`'s main (9e36bfa). No concern has work that lives only in `jugonzal/loops`: no
  pull request there links a concern, no branch there is named `command-center/<concern>`, and no commit on its
  main carries a `Concern:` trailer (per D1). Prove: `diff -r` of the two trees at those commits, and the pull
  requests, branches and trailers of `jugonzal/loops`, on main.

## Design

### Where we are

- Verified 2026-10-20, when this concern was designed: architect-loop is private with no forks, so moving the plugin's source
  breaks no one else's install. Its CI runs `scripts/check.sh` (`.github/workflows/check.yml`).
- Verified 2026-10-20 (`git ls-tree` on main @355dcb7): the skills are under `plugin/skills/`,
  and `skills/` is gone. The marketplace's source is `./plugin`, and the plugin's version is 0.2.0. `LOOP.md` and
  `docs/proposals/command-center.md` are committed. `scripts/check.sh` and `scripts/install.sh` read
  `plugin/skills/`, and `check.sh` holds the D14 check. (Corrected 2026-10-20: this section described the
  repository before the move.)
- Verified 2026-10-20 (Evidence below): C1 and C2 hold on main @4e7bf9a, and C3 is contradicted. The 0.2.0
  `loop-status` table has no rule for a pull request merged in another repository (D19 adds one), and the same
  run returned different boards on the same facts. The moved documents matched `jugonzal/loops` byte for byte.
- Correction to C3's evidence line, 2026-10-20 (`needs` in each concern's front matter on main @355dcb7): the line
  says the table leaves 3 cases open, but only the merge in another repository is missing from it. The other two
  rules are written clearly ("a concern in `needs` is not done", "a question that blocks a claim is
  unanswered"). app-shell, status-derivation and status-service also need `status-api`, so they are blocked
  under any reading. The report that showed them ready misread their `needs`; it was not reading the table
  differently. The verdict stands.
- Verified 2026-10-20 (a real `claude plugin marketplace add`, CLI 2.1.293): adding the marketplace clones the
  whole repository into the user's plugin config (808 KB). Nothing outside `plugin/` loads from it. With
  `--sparse .claude-plugin plugin`, the clone is partial and never downloads other files (484 KB). Accepted for
  now (per D20).

### Approach

Per D13 and D16, three pull requests in architect-loop, in this order:

1. **Code PR** (this concern, `Concern: command-center/one-repository`): `git mv skills plugin/skills`. Add
   `plugin/.claude-plugin/plugin.json` (the current `plugin.json` content), and set
   `.claude-plugin/marketplace.json`'s source to `./plugin`. Re-point `install.sh`, `check.sh`, the tests and the
   docs. Add the D14 check to `check.sh`: a grep over `plugin/` for `app/`, `services/` and the services' hosts,
   with a fixture test. Commit `docs/proposals/command-center.md`. Add `LOOP.md`, adapted from
   `jugonzal/loops`'s:
   - §2: replace the "vendored skills" gate with D17's release gate, and add D14 as a rule.
   - §3: `main` is architect-loop's main.
   - §5: skills under `plugin/skills/`, and the delegation's checker at
     `plugin/skills/loop-status/scripts/check_loop_pr.sh`.
   - §7: a trap, dated 2026-10-20: "drive work with an installed release, never the working tree you are
     editing" (per D17).
2. **Loop-document PR** (`docs/command-center-move`): copy `docs/loops/command-center/` from `jugonzal/loops` as
   it is on main there. It changes only `docs/loops/`, so the delegation in `LOOP.md` §2.1 covers it once the
   code PR has merged.
3. **Release** (the owner, per D17): bump to 0.3.0, tag, and update the marketplace. Then the owner archives
   `jugonzal/loops`, whose PRs #1 to #4 stay readable there as history.

Rollback: before the release, revert the code PR. After it, release 0.3.1 with the old layout. The archived
repository can be unarchived.

**Proving the move** (per D1). C4 checks that nothing was lost in the move: the two trees at the move, and
`jugonzal/loops`'s pull requests, branches and trailers. Archiving keeps them readable, so C4 can be proven before
or after it. This concern does not claim that the two repositories derive the same states. The prose table in
`loop-status` cannot promise that, and `status-derivation` C1 makes the derivation one script (per D15, D19).

## Decisions

| # | Decision | Decided by, date | Closes |
| --- | --- | --- | --- |
| D1 | Replace C3 with C4. The move is proven by the loop arriving whole (identical documents, no work left only in `jugonzal/loops`), not by two `/loop-status` runs agreeing. Status parity is `status-derivation` C1's job, where one script derives every state. | Juan, 2026-10-20 | C3's CONTRADICTS, 2026-10-20 |

## Questions

| # | Question | Blocks | Default if unanswered |
| --- | --- | --- | --- |

## Evidence

- 2026-10-20 · C1 · HOLDS · rung 1 · main @4e7bf9a · `claude plugin marketplace add jugonzal/architect-loop` and `claude plugin install architect-loop@architect-loop` (CLI 2.1.293, a throwaway config, an empty project) installed 24 files at gitCommitSha 4e7bf9a: the manifest and the 15 `loop-*` skills, byte-identical to `plugin/`, and nothing from `LOOP.md`, `docs/`, `scripts/` or `tests/`. `install.sh --project` gave the 23 files of `plugin/skills/`, byte-identical. With `app/` and `services/` planted on a local copy, main's layout installed none of their files, and the old `./` layout (3fdc759) installed them (48 files)
- 2026-10-20 · C2 · HOLDS · rung 5 · main @4e7bf9a · `check` run 39442727875 on 4e7bf9a passed with `ok independence` and `ok tests` (44 tests, including the 4 in `IndependenceCheckTest`, run verbosely on the same commit). With the pattern disabled, the two planted-reference tests fail (2 of 4). A `services/status/` line planted in a real skill makes `check.sh` exit 1. No service has a host yet to add to the pattern
- 2026-10-20 · C3 · CONTRADICTS · rung 1 · main @4e7bf9a · `/loop-status command-center` from the installed 0.2.0 skills, run in both repositories between 14:58 and 15:04 UTC (no commit on either main in between) on byte-identical loop documents (jugonzal/loops main 9e36bfa), read the same facts but gave 3 different boards across the 4 reports the two runs returned. one-repository was shipped in 3 and building in 1: from loops, its merge commit dc17f8f is never on that repository's main, and then no row of the table matches. app-shell, status-derivation, status-service and threads were ready or blocked (their need one-repository is shipped, not done), and session-runner was ready or open (its spike Q1 is unanswered). Two reports, one from each run, matched on all 14 concerns, so the move lost nothing. But the claim assumes a run gives one state per concern, and that is false while the table leaves these 3 cases open
- 2026-10-20 · C4 · HOLDS · rung 1 · main @273aafe · `docs/loops/command-center/` is the same git tree in both repositories at the move (da25027, 15 files: architect-loop 4e7bf9a, jugonzal/loops 9e36bfa, which is still its main), and `diff -r` of the two finds nothing. In jugonzal/loops, 0 of 4 pull requests link any of the 14 concerns (by head branch or `Concern:` line), no branch is `command-center/*` (its heads are main, docs/loop-init and revert-1-docs/loop-init), and its main has 0 trailers in 9 commits. Controls: the tree check catches #5 and #6 (3 files differ at 273aafe), and the same search in architect-loop finds PR #3 and its 2 trailer commits
- 2026-10-20 · C1 · HOLDS · rung 1 · main @fbd6d0b · Re-proved after c3e5647 (status-api's schema) and b9ecb4f (0.3.0) changed `plugin/`. With the repository now public, `claude plugin marketplace add jugonzal/architect-loop` and `claude plugin install architect-loop@architect-loop` (CLI 2.1.293, a throwaway config, an empty project) installed 0.3.0 at gitCommitSha fbd6d0b, which is tag v0.3.0: 25 files, the manifest and the 15 `loop-*` skills, byte-identical to `plugin/` there (`diff -r` differs only by the CLI's own empty `.in_use` directory), and nothing from `LOOP.md`, `docs/`, `scripts/` or `tests/`. `install.sh --project` gave the 24 files of `plugin/skills/`, byte-identical. With `app/` and `services/` planted in a local copy, main's layout installed the same 25 files and no planted one, and `install.sh` none. The same copy with the marketplace source set to `./` installed 75 files, both planted ones among them
- 2026-10-20 · C2 · HOLDS · rung 5 · main @fbd6d0b · `check` run 39494782628 on fbd6d0b passed with `ok independence` and `ok tests`, and the suite gives 74 tests, OK, on the same tree. With `runtime_refs` set to match nothing, the two planted-reference tests in `IndependenceCheckTest` fail (2 of 4). A `services/status/` line planted in `loop-status`'s SKILL.md makes `check.sh` exit 1, naming the line. No service has a host yet to add to the pattern
- 2026-10-20 · C4 · HOLDS · rung 1 · main @fbd6d0b · Re-proved after c3e5647 and b9ecb4f touched paths in `touches`. `docs/loops/command-center/` is git tree da25027 (15 entries) both at architect-loop 4e7bf9a and at jugonzal/loops 9e36bfa, read with `git rev-parse` and the GitHub trees API, and 9e36bfa is still that archived repository's main. In jugonzal/loops, 0 of 4 pull requests link a concern (heads `docs/loop-init`, `docs/command-center-plan`, `docs/command-center-design`, `docs/command-center-design-2`; no `Concern:` line), its branches are main, docs/loop-init and revert-1-docs/loop-init, and its main has 0 trailers in 9 commits. Controls: architect-loop's tree on main now differs (17 files), and the same search there finds PRs #3 and #11 and 3 trailer commits
- 2026-10-26 · C1 · HOLDS · rung 1 · main @aedfcf0 · Re-proved: `touches` changed since main @fbd6d0b. `claude plugin marketplace add jugonzal/architect-loop --scope project` and `claude plugin install architect-loop@architect-loop --scope project` (CLI 2.1.308, a scratch `CLAUDE_CONFIG_DIR`, an empty git project) installed 0.4.0 at gitCommitSha aedfcf0f222c: 28 files besides the CLI's own `.in_use` and `__pycache__`, the manifest and the 27 files of the 15 `loop-*` skills, and `diff -r` against `plugin/` at aedfcf0 finds nothing. None of `app/`, `services/`, `docs/`, `scripts/`, `tests/`, `LOOP.md`, `README.md` or `.github` arrived, though main really holds `app/` and `services/` (nothing was planted this time). `scripts/install.sh --project` into a second empty project gave the same 15 skills, 27 files, `diff -r` identical to `plugin/skills/`. One install each way
- 2026-10-26 · C2 · HOLDS · rung 5 · main @aedfcf0 · Re-proved: `touches` changed since main @fbd6d0b. The `check` workflow, run 40404908765 on aedfcf0, passed with `ok independence` and `ok tests`. In a throwaway checkout of aedfcf0, `IndependenceCheckTest` gives 7 tests OK. With `runtime_refs` in `check.sh` set to match nothing, 4 of the 7 fail (the app, services, service-host and hash-style-host tests), so they exercise the check. A line `See services/status/ for the service.` appended to `plugin/skills/loop-status/SKILL.md` makes `check.sh` print `FAIL independence: plugin/skills/loop-status/SKILL.md:264` and exit 1, and it exits 0 once the line is removed. No service host is in the pattern beyond `*.run.app`
- 2026-10-26 · C4 · HOLDS · rung 1 · main @aedfcf0 · Re-proved: `touches` changed since main @fbd6d0b. `docs/loops/command-center/` is git tree da25027 in both repositories at the move: architect-loop 4e7bf9a (`git rev-parse`) and jugonzal/loops 9e36bfa (the GitHub trees API), which is still that repository's main head, archived since its last push on 2026-10-20 14:30 UTC, so the two trees are byte-identical. In jugonzal/loops, 0 of its 4 pull requests link a concern (heads `docs/loop-init`, `docs/command-center-plan`, `docs/command-center-design`, `docs/command-center-design-2`; no `Concern:` line), its branches are `main`, `docs/loop-init` and `revert-1-docs/loop-init` (none named `command-center/*`), and 0 of the 9 commits on its main carry a `Concern:` trailer. Controls: architect-loop's own tree for that folder on main is now 3c646c0, so the tree check does see a difference, and the same pull request search finds a `Concern:` line in 36 of architect-loop's pull requests
- 2026-10-30 · C1 · UNPROVEN · rung 1 · main @ad0399b · Re-proof: `touches` changed since main @aedfcf0 (47cb36d, 81018ef, 4863263, 45c0585, b9b7b6d, bd99e12). The `install.sh` half holds: `sh scripts/install.sh --project .` from a clean worktree of ad0399b, run in an empty git project, installed the 15 `loop-*` skills, 27 files, all under `.claude/skills/`. `diff -r` against `plugin/skills/` finds nothing, and no installed file mentions `app/` or `services/`, though main holds both. The marketplace half was not run: this runner has no `claude` CLI and no node. All that was checked is that `.claude-plugin/marketplace.json` on ad0399b still points to `./plugin`, and that `plugin/` holds only `.claude-plugin/` and `skills/` (rung 6). One install, `install.sh` only · needs agent: run `claude plugin marketplace add jugonzal/architect-loop` and `claude plugin install architect-loop@architect-loop` with a scratch `CLAUDE_CONFIG_DIR` on a machine that has the CLI
- 2026-10-30 · C4 · UNPROVEN · rung 1 · main @ad0399b · Re-proof: `touches` changed since main @aedfcf0. The architect-loop half still holds: `git rev-parse 4e7bf9a:docs/loops/command-center` is da25027, the tree recorded at the move. The folder on main is now 0cda500, so a tree comparison would still see a change. The jugonzal/loops half could not be read. This runner's GitHub token gets 404 on that repository from the repos, branches, trees, commits and pull request APIs, and `gh repo list jugonzal` does not list it, so its main head, branches, pull requests and trailers went unchecked. Nothing here says it changed or was deleted · needs owner: give this runner read access to jugonzal/loops, or confirm it is still archived with main at 9e36bfa

## Shipped

2026-10-20, to `main`, its `ships-to`.

- **What shipped.** PR #3 (merge dc17f8f) did four things. It moved the skills to `plugin/` and set the
  marketplace's source to `./plugin`. It added the independence check to `check.sh`, with its tests. It gave this
  repository its `LOOP.md`, and it committed the founding proposal. PR #4 (merge 4e7bf9a) moved
  `docs/loops/command-center/` here from `jugonzal/loops`, byte for byte.
- **Departures from the design.** C3 asked two `/loop-status` runs, one in each repository, to agree. They did not,
  so D1 replaced C3 with C4: the loop arrived whole. The proof also produced D19 (a merge in another repository
  counts on that repository's main) and D20 (the marketplace's full clone is accepted for now). Two effects stay
  with the owner and are not part of done: the 0.3.0 release, and archiving `jugonzal/loops`.
- **Learned.** The 0.2.0 derivation is prose, and runs on the same facts can differ. One difference came from a gap
  in the table (merges in another repository), one from a misread `needs`, and one from a rule read loosely. The
  table also cannot order a decision made on the same day as the contradiction it answers. Comparing two runs
  proves little until `status-derivation` makes the derivation one script. Two things made the proof strong and
  cheap. A real marketplace install runs from the CLI with a throwaway config directory. An A/B with planted
  `app/` and `services/` folders turns an empty check ("nothing from `app/` arrived" when there is no `app/`)
  into a real one.
