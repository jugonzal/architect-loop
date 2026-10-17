# Upgrading from generation 1

Generation 1 kept one living proposal per initiative in `docs/proposals/`, with numbered plan steps and
Status lines that every skill updated by hand. Generation 2 keeps one folder per loop in `docs/loops/`, one
file per concern, and no status written anywhere: `/loop-status` derives it. This page covers moving a project
across. It takes one session, and nothing is lost: generation 1 proposals stay where they are, as history.

## What changes

| Generation 1 | Generation 2 |
| --- | --- |
| `docs/proposals/<slug>.md`, one per initiative | `docs/loops/<slug>/README.md` plus one `<concern>.md` per concern |
| Numbered steps (`Step 3`, `11a`) | Named concerns, independent unless one `needs` another |
| Status lines and step statuses, written by hand | Nothing written; `/loop-status` derives the state from git, PRs, environments and evidence |
| Proof fields | Append-only evidence lines, each citing a commit on `main` |
| `G#` goals and gates | `G#` goals for the loop, `C#` claims for each concern, gates in each concern's `effects` |
| `/loop-frame` | `/loop-plan` (a new loop) and `/loop-design` (how it gets built) |
| `/loop-decide` | `/loop-design` |
| `/loop-promote` | `/loop-ship` |
| `/loop-record`, `/loop-reconcile` | `/loop-status` (its record step, and `audit`) |
| Agents never merge | Agents may merge PRs that change only `docs/loops/` and cite only commits on `main` (`LOOP.md` §2.1) |

## Steps

1. **Reinstall the skills** (see the README). Version 0.2 ships the five retired names as stubs that point at
   their replacements, so a copy of generation 1 left in a skills folder is overwritten. The plugin replaces them
   on update.

2. **Run `/loop-init`** in the project. It detects generation 1 and runs the migration as a dry run first:

   ```bash
   python3 <path to the loop-init skill>/scripts/migrate_gen1.py
   ```

   The dry run writes nothing. For each proposal it says whether it becomes a loop (Proposed, Accepted, In progress)
   or stays as history (Done, Superseded, Parked). For each plan step it says whether it becomes a concern or stays
   as history because it is done, and why. It lists the evidence lines it could parse, the pull requests it found,
   and the `touches` it inferred from those pull requests' merged commits. It ends with a checklist for `LOOP.md`.

3. **Review the plan.** The step classification is a heuristic: a step whose Status starts with "done", or says it
   is on your top environment and verified, counts as done. Anything else becomes a concern. Useful options:

   ```bash
   python3 <path>/migrate_gen1.py --only launch-plan      # just these proposals (repeatable; forces a parked one)
   python3 <path>/migrate_gen1.py --include-done          # bring done steps along as concerns too
   python3 <path>/migrate_gen1.py --no-mark               # do not add a "Migrated" line to the old proposals
   ```

4. **Apply** on a branch, with `--apply`. The script creates the loop folders and adds a "Migrated" line under each
   old proposal's Status line. It never edits `LOOP.md`, never deletes anything and never commits. Running it again
   changes nothing.

5. **Upgrade `LOOP.md`** with `/loop-init`, following the checklist. Remove the proposal Status table and the plan-step
   status chain, add the concern conventions and the evidence-line format, add `docs/loops/` and the new role of
   `docs/proposals/`, decide on the loop-document delegation, and give each environment a served-commit command.

6. **Open one PR** with the migrated loops and the new `LOOP.md`, and merge it yourself. It touches `LOOP.md` and
   `docs/proposals/`, so no delegation covers it.

7. **Run `/loop-status`**, and expect some loose ends:
   - concerns whose `touches` could not be inferred. Their old pull requests are in `prs`, so their history is
     linked, but status cannot check staleness or overlap without a boundary: it flags built ones as drift and shows
     unbuilt ones as `open`;
   - evidence marked `@?`, because a generation 1 proof did not name a commit. Status does not count it, so the claim
     shows as unproven until it is proven again;
   - titles that describe a task rather than an outcome, and Done when text that holds several claims at once;
   - loops with no concerns at all, where the generation 1 plan was a table, a list or prose rather than `Step`,
     `Phase` or `Wave` headings. Status shows them as `open`, and `/loop-design <loop>` cuts their concerns from
     the history file's plan. If you would rather not track those yet, migrate the others with `--only`.

   Each of these is a `/loop-design` session, one loop at a time, starting with the one you are working on.

## What the migration keeps

- Every `D#`, `Q#` and `G#` keeps its number, in the loop's README.
- Every unfinished step becomes a concern whose Approach is the step's "Does" text and whose `C1` is its "Done when",
  verbatim, with a note of where it came from and what its status said.
- Every pull request a step mentioned is listed in the concern's `prs`, so `/loop-status` can find the work.
- The generation 1 proposal stays in `docs/proposals/` as history, including its done steps and its "What shipped"
  section, and the loop's README links to it.
