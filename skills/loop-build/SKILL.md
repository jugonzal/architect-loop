---
name: loop-build
description: Build one concern of a loop in its own worktree and branch, as a pull request that explains itself. Tests first where possible, changes only the paths the concern's contract lists in touches, never edits docs/loops/, commits with outcome-sentence subjects and a Concern trailer, and puts the proof from before the merge in the PR body. With --ready it builds every ready concern of a loop in parallel, one agent and one worktree each. Use when the owner asks to build or implement a concern, to build everything that is ready, to fix a bug with a known cause, or runs /loop-build.
license: MIT
metadata:
  author: architect-loop
  version: "0.2"
---

# loop-build

Build one concern, in isolation, and leave behind a PR that explains itself.

## Boundary

This skill writes code, tests and reference docs inside the concern's `touches`, on the concern's own branch
and worktree, and opens a pull request. It does not merge, deploy or ship; code PRs are the owner's to merge.
It never edits `docs/loops/`: loop documents describe only what is on `main`, and they change in their own PRs
(by `loop-design`, `loop-prove`, `loop-ship` and `loop-status`). It stops at any gate in `LOOP.md` §2 that the
concern's `effects` do not already put in the owner's hands.

**Without `LOOP.md`:** branch as `<loop>/<concern>`, find the test commands in the repo's scripts, apply the
default gates from `loop-init`, and mention `/loop-init` once.

## Steps

1. **Check it is buildable.** Run `/loop-status <loop>/<concern>`. Build only a concern that is `ready`, or
   resume one that is `building`. If it is `open` or `contradicted`, stop and point at `/loop-design`. If it is
   `blocked`, name what it waits for. If its contract has no `touches`, stop: design must say where the work goes.

2. **Load context.** Read `LOOP.md` (commands, conventions, gates, traps), the concern file (Done when,
   Approach, Decisions, `needs`, `effects`), the shared decisions it needs, and the memory facts for the paths in
   `touches`. Nothing else in the loop is yours to change.

3. **Isolate.** Create a worktree on a new branch `<loop>/<concern>` from an up-to-date `origin/<main>`, using
   the agent tool's own worktree isolation if it has one, otherwise
   `git worktree add <path from LOOP.md §5> -b <loop>/<concern> origin/<main>`. If the branch or an open PR for it
   already exists, resume that one instead of starting another; if someone else's session holds it, stop.

4. **Claim it by opening a draft PR** as soon as the first commit exists, with the body from
   [templates/pr-body.md](templates/pr-body.md). The open PR is the claim; there is no claim commit and no status
   to write anywhere. Every commit ends with the trailer `Concern: <loop>/<concern>`, and so does the PR body.

5. **Build with the test first where you can.** For a bug, write the failing test or reproducer before the fix
   and keep it. For a feature, write tests that express the concern's claims. Follow the surrounding code's style;
   do not reformat unrelated code.

6. **Stay inside `touches`.** If the work needs a path outside it, stop and report which path and why. If no other
   concern owns that path, `/loop-design` can widen this contract; if another concern does, the two are coupled,
   and that is design's call (a `needs`, a contract concern, or a merge), not yours.

7. **Run the checks** from `LOOP.md` §4: unit tests, lint and types, and the smoke test if the change touches the
   pipeline it covers. Report failures faithfully, including ones you believe are pre-existing or environmental;
   say which, and how you know.

8. **Keep reference docs in the same PR.** If the change alters an API, a command, a config key or a procedure,
   update the reference doc or runbook in the same branch, if it is inside `touches`; otherwise say it needs
   updating in the report.

9. **Commit** with:
   - a subject that states the outcome as an imperative sentence, readable in a changelog ("Stop retrying failed
     uploads forever"), not a label ("upload fix");
   - a body with the reasoning: what was wrong or missing, why this approach, what was measured or reproduced,
     what was ruled out, and anything the reviewer should distrust;
   - the `Concern:` trailer.

10. **Finish the PR.** Fill in how each claim was proven so far (that is the proof before the merge, and it lives
    here, not in the concern file), the declared effects the owner must perform, and what is still to prove after
    the merge and where. Check its base is `<main>`, not another PR's branch. Mark it ready for review. Do not
    merge.

11. **Report** in a few lines: the branch, the PR, what was proven locally, what still needs proving and where
    (hand-off to `/loop-prove` once an environment serves it), and anything that needs the owner.

## Building in parallel

`/loop-build <loop> --ready` builds every `ready` concern in the loop at once:

1. Run `/loop-status <loop>` and list the `ready` concerns. Check that no two of them share a path in `touches`;
   if two do, build only one of them and report the overlap for `/loop-design`.
2. Start one agent per concern, each in its own worktree, each following the steps above for its concern alone
   (in Claude Code, a subagent with worktree isolation per concern).
3. The coordinating session launches and collects. It edits nothing itself, and merges nothing.
4. Report one line per concern: its PR, its local proof, and what needs the owner. Merge order is the owner's
   call; `/loop-status` shows which are mergeable.

## Stop conditions

- The concern is not `ready` or `building`.
- The work needs a decision that is not recorded, or a path outside `touches`.
- The work would cross a gate that the concern's `effects` do not declare.
- The code contradicts the concern's "Where we are". Stop, report the contradiction, and suggest `/loop-design`.
  Do not quietly build to a false premise.
- The task is a spike: its only output is an answer to a question. That is `/loop-prove`'s job.
