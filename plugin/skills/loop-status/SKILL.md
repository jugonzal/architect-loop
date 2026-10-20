---
name: loop-status
description: Work out what is true right now for every loop and concern in docs/loops/, from facts instead of documents. It reads git, pull requests, what each environment serves and the evidence lines, derives each concern's state, shows the owner's queue and what agents can start now, flags drift, and records Shipped notes, corrections and memory on the owner's yes. Read-only until then. Use whenever anyone asks where things stand, "is this done?", "what's next?", "what's deployed?", "are the docs right?", before planning on top of old docs, after a deploy, to close out finished work, or runs /loop-status.
license: MIT
metadata:
  author: architect-loop
  version: "0.2"
---

# loop-status

Compute where everything stands, every time, and say what to run next.

Nothing in `docs/loops/` records whether a concern is claimed, built, merged, shipped or done. This skill
derives it from facts: branches, pull requests, commits on `main`, what each environment serves, and the
evidence lines that record what no command can re-observe. A missed event changes nothing, because each run
reads the current state of the world instead of a stored flag. If you remember one command, remember this one.

## Boundary

**Read-only until the owner says yes.** It runs only read commands: `git` (including `git fetch`), `gh`, and
the served-commit and verify commands in `LOOP.md` §3 for environments agents may read. It never reruns an
expensive proof (it says "re-prove" instead), never changes an environment, and never edits a file before the
record step. Running it twice with nothing changed in between prints the same board.

**Without `LOOP.md`:** use git and pull requests only, treat `main` as the only environment, say that merged
and shipped cannot be told apart, and mention `/loop-init` once. **Without `docs/loops/`** but with generation 1
proposals (a `**Status:**` line and `Step n` headings in `docs/proposals/`), say so and suggest `/loop-init`,
which upgrades the project.

## Scope

- `/loop-status`: every loop. Active loops in full, backlog and parked loops one line each.
- `/loop-status <loop>`: that loop's board.
- `/loop-status <loop>/<concern>`: one concern, showing every fact and the command that produced it.
- `/loop-status audit [<path>]`: a full audit of documents outside `docs/loops/` (runbooks, memory, READMEs);
  see "Audit" below.

## Steps

1. **Gather facts once, read-only.**
   - `git fetch --prune`, then the main branch's SHA (`git rev-parse origin/<main>`).
   - For each environment in `LOOP.md` §3 that agents may read, its served commit, using its command. If the
     command fails or is missing, the environment's state is *unknown*. Say so, and never guess.
   - Pull requests, in one call: `gh pr list --state all --limit 300 --json number,title,headRefName,baseRefName,state,isDraft,mergeCommit,body,url,statusCheckRollup`.
     Repeat for any other repository named in a `touches` or `prs` entry, and fetch any PR listed in a `prs`
     entry that the list did not return with `gh pr view <n> --json <same fields>`.
   - Commits on main that carry a trailer: `git log origin/<main> --format='%H%x09%(trailers:key=Concern,valueonly,separator=%x2C)'`.
   - CI for the main branch's head, from `LOOP.md` §4 or `gh run list --commit <sha>`.

2. **Read every loop.** Each folder in `docs/loops/` is a loop: `README.md` plus one file per concern. Parse
   each concern's front matter (`needs`, `touches`, `effects`, `ships-to`, `prs`, `parked`), its claims
   (`C#` under Done when), its decisions and questions, and its evidence lines.

3. **Link work to each concern.** Its work is the union of: pull requests whose head branch is
   `<loop>/<concern>`, or whose body carries `Concern: <loop>/<concern>`; commits on main with that trailer; and
   anything listed in `prs`. For a merged PR, the commit that counts is its merge commit (`mergeCommit`), and a PR
   counts as merged only if that commit is on main (`git merge-base --is-ancestor <sha> origin/<main>`). GitHub's
   "merged" is not enough: a stacked PR can merge into another branch, where nothing deploys.

   Without `gh` (not installed, not authenticated, or a host other than GitHub), link from git alone: a PR's work
   on main is the commit whose subject ends `(#N)` (a squash merge) or starts `Merge pull request #N` (a merge
   commit), branches come from `git branch -r`, and anything only the host knows (open PRs, drafts, CI) is
   `unknown`. Say which facts came from git alone.

4. **Derive each concern's state.** Check the rows from top to bottom; the first that matches wins.

   | State | When (facts) | Next |
   | --- | --- | --- |
   | parked | Front matter has `parked: D<n>` | Nothing. Show what the decision says would unpark it |
   | contradicted | A claim's latest verdict is CONTRADICTS, and no decision is dated after it | `/loop-design <loop>/<concern>` (or `/loop-diagnose` when the cause is unknown) |
   | open | A question that blocks a claim is unanswered, or a decision in `needs` has been superseded; or nothing is built yet and the contract lacks Done when, `touches` or `ships-to` | `/loop-design`. The owner answers |
   | blocked | Nothing is built yet, and a concern in `needs` is not done | That concern's next action |
   | ready | Nothing is built yet: no linked PR, no `<loop>/<concern>` branch, no commit with its trailer | `/loop-build <loop>/<concern>` |
   | building | A linked PR is open, or the branch exists, and none of its work is on main | The PR's next step: build, review, or the owner merges once the proof in its body holds and CI is green |
   | merged | Its work is on main, and its `ships-to` environment does not serve it yet | Prove on any lower environment that serves it, then `/loop-ship <env>` |
   | shipped | `ships-to` serves its work, and some claim has no current HOLDS there | `/loop-prove <loop>/<concern> <env>` |
   | stale | Every claim had a current HOLDS there, but code under `touches` or a decision in `needs` has changed since | `/loop-prove` again |
   | done | Every claim has a current HOLDS on `ships-to` | Offer a Shipped note if it has none |

   A concern that is already built is never shown as open or blocked because of a gap in its contract or its
   `needs`. Those gaps are drift (step 8), so the board never hides how far the work has got.

   Definitions:
   - **Serves:** the environment's served commit has every one of the concern's merge commits as an ancestor.
     For `ships-to: main`, the main branch's head serves whatever is on main.
   - **Current HOLDS for a claim on an environment:** its latest evidence line is HOLDS there, its commit is an
     ancestor of the served commit, and `git log --format=%h <proof>..<served> -- <touches>` prints nothing.
     A claim whose Prove says CI holds at rung 5 when CI is green on the main branch's head, with no line needed.
   - A line marked `@?` (migrated without a commit) never counts as a HOLDS, but a CONTRADICTS still counts,
     with or without a commit: a contradiction is a reason to stop, wherever it was seen. A claim with only
     UNPROVEN lines is not proven.
   - **Unknown is a state too.** If a fact cannot be read (the environment is unreachable, `gh` is not
     authenticated), show `unknown`, name the missing fact, and never fill the gap from a document.
   - **Code reading is the weakest rung.** If `touches` changed but no evidence covers the change, read the code
     and report what you infer at rung 6 ("C1 may already hold; prove it"). Never count an inference as a HOLDS.

5. **Derive each loop's state.** **parked** if its README has `parked: D<n>`. **open** if it has no concerns at
   all (a migrated loop whose generation 1 plan had no step headings, say); next: `/loop-design <loop>` cuts them.
   **backlog** while none of its
   concerns has a decision, linked work or evidence; shared decisions recorded while planning do not count, so a
   loop stays in the backlog until someone designs or builds one of its concerns. **done** when every concern is
   done and every `G#` has a current HOLDS. Otherwise **active**.

6. **Find what needs the owner**, across every loop in scope, and sort it by how many concerns each item
   unblocks (counting through `needs`, across loops too):
   - open questions, each with its recommendation and what it blocks;
   - PRs that are ready for review, with CI green and the proof in their body;
   - concerns that are merged and waiting to ship, with their declared `effects` as manual steps;
   - UNPROVEN claims that need something only the owner has: a device, an account, a production read;
   - contradictions that need a call (redesign, or roll back), and any evidence line that says it contradicts a
     shared decision, which escalates to the loop as a question;
   - loop-document PRs that `scripts/check_loop_pr.sh` refused.

7. **Find what agents can start now**: `ready` concerns (build), `shipped` and `stale` ones (prove), and
   concerns with an incomplete contract (design can draft and gather questions). Several of these can run at
   once, one agent and one worktree each.

8. **Look for drift**, cheaply. Flag:
   - "Where we are" text in a loop or concern that the code under its `touches` now contradicts;
   - two concerns that are both not yet merged (open, blocked, ready or building), in this loop or across active
     loops, with overlapping `touches` and no `needs` between them. Concerns already on `main` cannot collide;
   - a linked PR that changes files outside its concern's `touches`;
   - a concern built against a contract that changed after its branch started;
   - a built concern whose contract lacks `touches` (staleness and overlap cannot be checked) or `ships-to`, or
     that was built ahead of a concern it `needs`;
   - memory facts and runbooks that cite a file changed since their `verified` or `Last run` date.

9. **Report**, leading with the board:

   ```text
   <loop> · <n> concerns · main <sha> · <env> serves <sha> · … · <date time>

   concern        state         evidence                                       next
   job-contract   done          C1 HOLDS rung 5, CI on main @7a1e0c2           —
   queue          merged        staging serves it; C1 HOLDS rung 1; C2 UNPROVEN /loop-prove report-pipeline/queue staging
   worker         contradicted  C2 CONTRADICTS rung 1: p95 41 s, needs ≤ 30 s   /loop-design report-pipeline/worker

   Needs you (n), most unblocking first
     1. …
   Agents can start now (n)
     /loop-…
   Drift (n)
     <file> <where>: "<claim>" → <what is actually true> (checked: <command>)
   Record (n), on your yes
     <what would be written, and where>
   ```

   Keep it to one screen. For `/loop-status <loop>/<concern>`, list each fact with the command that produced it.

## Record, on the owner's yes

Offer, never assume. When the owner agrees:

1. **Loop documents** go on a `docs/<loop>-record-<date>` branch, in one PR that changes nothing outside
   `docs/loops/`:
   - a **Shipped** note for each concern (or loop) that is done and has none: what shipped (PRs, environments),
     where it departs from its design, and what was learned;
   - corrections to "Where we are" text the facts contradict, each saying what was wrong and how it was checked.

   Run [scripts/check_loop_pr.sh](scripts/check_loop_pr.sh) `--pr <n>`. If it passes and the PR's checks are
   green, merge it yourself (`LOOP.md` §2.1). If it fails, leave it for the owner and say why.
2. **Everything else** goes in a separate PR for the owner to merge: memory facts (use
   [templates/memory-fact.md](templates/memory-fact.md) in `docs/memory/`, update rather than duplicate, delete
   facts proved wrong), runbook traps (via `/loop-runbook`), `LOOP.md` §7 traps, and corrections to READMEs or
   reference docs. Correction commits say so in their subject ("Correct …"), and their body lists each wrong
   claim, the truth, and how it was established.

Record only what no command can re-observe. Never record that something is built, merged, shipped or done.

## Audit

`/loop-status audit` checks the documents outside `docs/loops/`, which generation 1 called reconciling:

1. Extract every claim that can be true or false today: "X is on staging", "the backup job is scheduled",
   "unsigned requests get 403".
2. Check each claim against the strongest source available, and record which: the environment (read-only),
   the main branch, git history, another document (the weakest; flag it).
3. Classify each claim as **true**, **stale**, **wrong**, **ahead** (done but not recorded) or **uncheckable**
   (and what would check it), and flag self-contradictions.
4. List corrections, most consequential first (a future reader would act wrongly on the current text), and apply
   them through the record step.

## Notes

- A deploy that succeeded is not a claim that holds. Shipped and done are different states for that reason.
- If two runs on the same facts ever disagree, the derivation table above is what to fix, not the facts.
