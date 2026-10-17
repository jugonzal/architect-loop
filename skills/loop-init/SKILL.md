---
name: loop-init
description: Set up a project for the Architect Loop, or upgrade one that started on generation 1. Interviews the owner and writes LOOP.md, the contract that says who decides, what agents may do alone, which environments exist and how each reports the commit it serves, how to test and deploy, and where loops, runbooks and memory live. On a generation 1 project it runs the migration script as a dry run, shows the plan, and on the owner's yes turns in-progress proposals into loops of concerns. Use when adopting the architect loop, upgrading from generation 1 (docs/proposals with Status lines and numbered steps), when the user runs /loop-init or asks to "set up the architect loop", "write a LOOP.md", "upgrade the loop", or "define what agents may do here".
license: MIT
metadata:
  author: architect-loop
  version: "0.2"
---

# loop-init

Write the project's contract, `LOOP.md`, and the folders the other loop skills use. On a generation 1 project,
upgrade both.

`LOOP.md` exists so that every agent session, including one that has never seen this project, starts knowing
three things: what it may do alone, what it must stop and ask about, and where the shared memory lives. Without
it, agents guess, and a guessed gate is a gate that does not exist.

## Boundary

This skill writes `LOOP.md` and creates `docs/loops/`, `docs/proposals/`, `docs/runbooks/` and `docs/memory/`
(each with a `.gitkeep`) when missing. In upgrade mode it also runs the migration script, which writes
`docs/loops/` and marks the migrated proposals as history. It changes no code, config or CI. Everything goes on
a `docs/loop-init` (or `docs/upgrade-to-loop-gen2`) branch in a PR for the owner, because `LOOP.md` is the
contract and the owner reviews it before it takes effect.

## Steps

1. **Check what exists.** If `LOOP.md` is already there, read it. Look for existing conventions before asking:
   `CLAUDE.md`, `AGENTS.md`, `CONTRIBUTING.md`, `docs/`, CI workflows, package scripts, `Makefile`, container and
   deploy config, and the last 50 commit subjects (`git log --format=%s -50`). Existing practice wins over this
   skill's defaults. Then pick a mode:
   - **New:** no `LOOP.md`.
   - **Update:** a generation 2 `LOOP.md`. Ask only about sections that are empty, marked `TODO(owner)`, or
     contradicted by the repo.
   - **Upgrade:** a generation 1 project: `LOOP.md` has the proposal Status table or the "Plan step status"
     convention, or `docs/proposals/` holds files with a `**Status:**` line and `Step n` plan headings, and there
     is no `docs/loops/`. Go to "Upgrading from generation 1" below, then come back to step 2.

2. **Draft from the repo first, then ask.** Fill everything you can infer: test and lint commands, environments
   named in deploy scripts or CI, how each environment reports the commit it serves, branch naming seen in
   history, whether changes go through PRs. Then ask the owner only what the repo cannot answer, in one batch of at
   most four questions:
   - Who is the owner (the person who decides and ships)?
   - Which environments exist, and for each: may agents read it, and what command prints the commit it serves?
   - Beyond the defaults below, what must always stop for a human? Is any action delegated to agents on a standing
     basis (for example "merging to `staging` is fine; CD deploys it")?
   - Is the default delegation right, so agents merge pull requests that change only `docs/loops/` and only
     record what is on `main`? (If not, delete that row from §2.1.)

3. **Write `LOOP.md`** from [templates/LOOP.md](templates/LOOP.md). Keep every section, and write `TODO(owner)` for
   anything unanswered rather than inventing it. Mark inferred values `(inferred)` so the owner can confirm them.
   The served-commit command for each environment matters most: without it, `/loop-status` cannot tell a merged
   concern from a shipped one.

4. **Create the folders** that do not exist yet, each with a `.gitkeep`.

5. **Point other agent entry files at it.** If `CLAUDE.md` or `AGENTS.md` exists, propose (do not silently make)
   a one-line addition: `Read LOOP.md before starting work; it defines gates and conventions.`

6. **Report** in five lines or fewer: what was written, what was inferred, the `TODO(owner)` items, and the next
   step. That is usually `/loop-plan` for the first loop, `/loop-status` after an upgrade, or `/loop-status audit`
   on an existing project whose docs may already be stale.

## Upgrading from generation 1

Generation 1 kept one living proposal per initiative, with numbered steps and hand-written Status lines.
Generation 2 keeps one folder per loop under `docs/loops/`, with one file per concern and no status written
anywhere. [scripts/migrate_gen1.py](scripts/migrate_gen1.py) does the mechanical part. It needs Python 3 and
nothing else.

1. **Dry run.** From the project root, run `python3 <this skill's directory>/scripts/migrate_gen1.py`. It writes
   nothing. It prints, for each proposal, whether it becomes a loop (Proposed, Accepted, In progress) or stays in
   `docs/proposals/` as history (Done, Superseded, Parked), and for each plan step, whether it becomes a concern
   or stays as history because it is done, and why. It also lists the evidence lines it could parse, the pull
   requests it found, the `touches` it could infer from them, its warnings, a checklist for `LOOP.md`, and any
   generation 1 copies of retired skills still installed.

2. **Show the owner the plan** and the warnings. They decide which proposals to migrate (`--only <slug>`, which
   also forces a parked one) and whether done steps should come along too (`--include-done`). The classification
   is a heuristic. A step wrongly called done would stop being tracked, so say which ones were close calls.

3. **Apply** on the owner's yes: on a `docs/upgrade-to-loop-gen2` branch, run the script again with `--apply`.
   It creates `docs/loops/<slug>/` for each migrated proposal and marks the proposal as history. It never edits
   `LOOP.md`, never deletes anything, never commits, and running it twice changes nothing.

4. **Upgrade `LOOP.md`** with the owner, working through the checklist the script printed: remove the proposal
   Status table and the plan-step status chain from §6, add the concern conventions and the evidence-line format,
   add `docs/loops/` and the new role of `docs/proposals/` to §5, add the loop-document delegation row to §2.1 (if
   the owner wants it), and fill in each environment's served-commit command in §3. Take the wording from
   [templates/LOOP.md](templates/LOOP.md), and keep every project-specific gate, delegation and trap.

5. **Open one PR** with the migrated loops and the new `LOOP.md`, for the owner to merge. It changes `LOOP.md`
   and `docs/proposals/`, so the loop-document delegation does not cover it.

6. **Then run `/loop-status`.** Migrated concerns carry their old pull requests in `prs`, so status can derive
   their state straight away. Expect drift about missing `touches` (and `open` for unbuilt concerns that lack them),
   and evidence marked `@?` that does not count, because generation 1 proofs did not always name a commit. Those are the next
   `/loop-design` sessions, one loop at a time, starting with the active one.

7. **Retire the old skills.** If the script found generation 1 copies of `loop-frame`, `loop-decide`,
   `loop-promote`, `loop-record` or `loop-reconcile`, reinstall the skills (see the README) to replace them.
   Version 0.2 ships those five as stubs that point at their replacements; the next version removes them.

## Default gates

These are the defaults in the template. The owner may add to them; remove items only on the owner's explicit
say-so.

- **Never done by an agent, even after a yes, unless delegated in §2.1:** merging to the main branch; deploying
  or promoting to any shared environment; migrations against shared data.
- **Done by an agent only after a per-action yes:** money (prices, billing, tax, payment settings); identity and
  access (auth providers, roles, admin grants, OAuth/SSO); secrets; legal and public text; DNS, certificates,
  firewall, cloud IAM; deleting or rewriting production data or expiring user content; sending anything to real
  users.
- **Delegated by default (§2.1):** merging a pull request that changes only `docs/loops/` and records only what is
  on the main branch, checked by loop-status's `scripts/check_loop_pr.sh`. The owner may delete this row.

Other loop skills use these defaults when a project has no `LOOP.md`, except the delegation, which needs a
`LOOP.md` that grants it.

## Existing projects

On a brownfield repo that never used the loop, recommend `/loop-status audit` right after this skill. Existing
docs almost always claim things the code or the environment no longer supports, and the first `/loop-plan`
should not build on them.
