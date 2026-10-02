---
name: loop-build
description: Implement one step of a decided proposal as one branch and one pull request, with tests, an outcome-sentence commit subject, a commit body that carries the reasoning, and a PR body that cites the proposal section and says how it was proven. Use when the owner asks to build or implement a decided plan step, to fix a bug with a known cause, to make a small change in the loop's style, or runs /loop-build.
license: MIT
metadata:
  author: architect-loop
  version: "0.1"
---

# loop-build

Build one intent, leave behind a PR that explains itself.

## Boundary

This skill writes code, tests and docs on a branch and may open a pull request. It does not merge,
deploy or promote, and it stops at any gate listed in `LOOP.md` §2. It builds only what was decided:
if the step depends on an open `Q#`, stop and point at `/loop-decide`.

**Without `LOOP.md`:** branch as `feat/` or `fix/` + slug, find the test commands in the repo's
scripts, apply the default gates from `loop-init`, and mention `/loop-init` once.

## Steps

1. **Load context.** Read `LOOP.md` (commands, conventions, gates, project traps). Read the
   proposal and the step being built, including its **done when** and any decisions it cites. Read
   the project's memory for traps relevant to the files you will touch.

2. **Confirm the slice.** One step, one intent. If the step is really three changes (for example a
   model change, an API change and a UI change that can land separately), propose splitting it and
   build the first. Independent slices can be built in parallel in separate worktrees or sessions.

3. **Branch and claim the step.** Branch from the up-to-date main branch using the naming in
   `LOOP.md` §6. Set the step's Status in the proposal to `in progress on <branch>` in your first
   commit, and if the project uses PRs, open the PR as a draft as soon as that commit exists. Other
   sessions see the claim through the open PR list. If a draft PR for the step already exists,
   stop: someone else has claimed it.

4. **Build with the test first where you can.** For a bug, write the failing test or reproducer
   before the fix and keep it. For a feature, write the tests that express the step's **done when**.
   Follow the surrounding code's style; do not reformat unrelated code.

5. **Run the checks** from `LOOP.md`: unit tests, lint and types, and the smoke test if the change
   touches the pipeline it covers. Report failures faithfully, including ones you believe are
   pre-existing or environmental. Say which, and how you know.

6. **Keep docs in the same PR.** If the change alters an API, a command, a config key or a
   procedure, update the reference doc or runbook in the same branch. In the proposal, touch only
   this step's Status (and set the proposal's state to `In progress` if it was `Accepted`); the rest
   of the Status line, departures and gates belong to `loop-record` after the change is proven.

7. **Commit** with:
   - a subject that states the outcome as an imperative sentence, readable in a changelog
     ("Stop retrying failed uploads forever"), not a label ("upload fix");
   - a body with the reasoning: what was wrong or missing, why this approach, what was measured or
     reproduced, what was ruled out, and anything the reviewer should distrust.

8. **Finish the PR** (per `LOOP.md` §6) with the body from
   [templates/pr-body.md](templates/pr-body.md) and mark it ready for review. Cite the proposal and
   step. Do not merge. If the project does not use PRs, put the same text in the final commit body.

9. **Report** in a few lines: the branch, the PR, what was proven locally, what still needs proving
   on a real environment (hand-off to `/loop-prove`), and anything that needs the owner.

## Stop conditions

- The step needs a decision that is not recorded.
- The work would cross a gate (a migration on shared data, a secret, a DNS change, a price).
- The code contradicts the proposal's picture of "where we are". Stop, report the contradiction, and
  suggest `/loop-frame` to revise the proposal. Do not quietly build to a false premise.
- The step is a spike (its only output is an answer). That is `/loop-prove`'s job.
