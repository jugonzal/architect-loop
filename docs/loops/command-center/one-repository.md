---
needs: []
touches: [architect-loop:plugin/, architect-loop:skills/, architect-loop:.claude-plugin/marketplace.json, architect-loop:scripts/install.sh, architect-loop:scripts/check.sh, architect-loop:tests/, architect-loop:README.md, architect-loop:docs/adopting.md, architect-loop:docs/upgrading.md, architect-loop:LOOP.md, architect-loop:docs/proposals/command-center.md, architect-loop:.github/workflows/check.yml]
effects: [a new LOOP.md in architect-loop, carrying this project's contract with D14 and D17 as rules (a change to the contract; the owner merges it), the plugin marketplace source moving to ./plugin, which changes how everyone installs (released by the owner as a new version, per D17), archiving jugonzal/loops once the loop has moved (the owner does it)]
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
- **C3** `/loop-status`, run in architect-loop from an installed release, shows the `command-center` loop with
  the same state for every concern as a run in `jugonzal/loops` at the same moment. Prove: both runs side by
  side, on main, after the loop-document PR that moves `docs/loops/command-center/`.

## Design

### Where we are

- Verified 2026-10-20 (see the loop README, Where we are): architect-loop is private with no forks, so moving
  the plugin's source breaks no one else's install. Its `skills/` folder is identical to `jugonzal/loops`'s
  `.claude/skills/`. Its `docs/proposals/command-center.md` is identical but uncommitted. It has no `LOOP.md`. Its
  CI runs `scripts/check.sh` (`.github/workflows/check.yml`).
- `scripts/check.sh` and the tests refer to `skills/` by path. They move with the skills.

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
   `jugonzal/loops`, whose PRs #1 to #3 stay readable there as history.

Rollback: before the release, revert the code PR. After it, release 0.3.1 with the old layout. The archived
repository can be unarchived.

## Decisions

| # | Decision | Decided by, date | Closes |
| --- | --- | --- | --- |

## Questions

| # | Question | Blocks | Default if unanswered |
| --- | --- | --- | --- |

## Evidence

- 2026-10-20 · C1 · HOLDS · rung 1 · main @4e7bf9a · `claude plugin marketplace add jugonzal/architect-loop` and `claude plugin install architect-loop@architect-loop` (CLI 2.1.293, a throwaway config, an empty project) installed 24 files at gitCommitSha 4e7bf9a: the manifest and the 15 `loop-*` skills, byte-identical to `plugin/`, and nothing from `LOOP.md`, `docs/`, `scripts/` or `tests/`. `install.sh --project` gave the 23 files of `plugin/skills/`, byte-identical. With `app/` and `services/` planted on a local copy, main's layout installed none of their files, and the old `./` layout (3fdc759) installed them (48 files)
- 2026-10-20 · C2 · HOLDS · rung 5 · main @4e7bf9a · `check` run 39442727875 on 4e7bf9a passed with `ok independence` and `ok tests` (44 tests, including the 4 in `IndependenceCheckTest`, run verbosely on the same commit). With the pattern disabled, the two planted-reference tests fail (2 of 4). A `services/status/` line planted in a real skill makes `check.sh` exit 1. No service has a host yet to add to the pattern
- 2026-10-20 · C3 · CONTRADICTS · rung 1 · main @4e7bf9a · `/loop-status command-center` from the installed 0.2.0 skills, run in both repositories between 14:58 and 15:04 UTC (no commit on either main in between) on byte-identical loop documents (jugonzal/loops main 9e36bfa), read the same facts but gave 3 different boards across the 4 reports the two runs returned. one-repository was shipped in 3 and building in 1: from loops, its merge commit dc17f8f is never on that repository's main, and then no row of the table matches. app-shell, status-derivation, status-service and threads were ready or blocked (their need one-repository is shipped, not done), and session-runner was ready or open (its spike Q1 is unanswered). Two reports, one from each run, matched on all 14 concerns, so the move lost nothing. But the claim assumes a run gives one state per concern, and that is false while the table leaves these 3 cases open

## Shipped
