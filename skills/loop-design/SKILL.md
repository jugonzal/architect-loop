---
name: loop-design
description: Work out how a loop, or one of its concerns, will actually be built, by grilling the owner on open decisions and on the constraints a fresh read of the code turns up. Reads the code and environments, challenges every claim, gate and assumption, asks one question at a time with options and a recommendation, records numbered decisions (shared ones in the loop README, private ones in the concern), and reshapes concerns so they can be built in parallel. Planning only; never implements, never answers for the owner. Use when the owner wants to start a loop from the backlog, decide how something gets built, answer open questions, add a constraint, record a decision made in passing, revise a concern the evidence contradicted, or runs /loop-design.
license: MIT
metadata:
  author: architect-loop
  version: "0.2"
---

# loop-design

Turn a loop's intent into contracts that agents can build in parallel, by asking the owner every question
that matters before anyone writes code.

The owner decides. This skill makes each decision cheap and hard to dodge: it reads the code first, finds what
the plan has not faced yet, and asks about it one question at a time, with the options and a recommendation
already laid out. Questions it can answer from the repository are not asked; questions only the owner can
answer are never answered for them.

## Boundary

**This skill designs; it does not build.** It edits the loop's README and its concerns' files, and nothing
else: no code, no config, no other loop's files. It does not start `/loop-build` in the same turn.

It commits on a `docs/<loop>-design` branch and opens a PR that changes only `docs/loops/<loop>/`. Under
`LOOP.md` §2.1 it may merge that PR itself once `scripts/check_loop_pr.sh` from the loop-status skill passes;
otherwise the owner merges. Decisions count only if the owner made them in this conversation.

**Without `LOOP.md`:** use the default gates from `loop-init`, treat every non-local environment as read-only
and ask before reading it, leave the PR for the owner, and mention `/loop-init` once.

## Scope

- `/loop-design <loop>`: the whole loop. Its concerns' shape, shared decisions, relations, and then each
  concern's open questions.
- `/loop-design <loop>/<concern>`: one concern, for example one that `/loop-status` shows as open or
  contradicted.

## Steps

1. **Load the facts.** Run `/loop-status <loop>` first and work from its board, not from the documents' prose.
   Read `LOOP.md` (gates, environments, traps), the loop's README and concerns, the relations' other loops, and
   the memory facts about the area. A loop migrated from generation 1 links its history file in `docs/proposals/`.
   Read that file's plan, decisions and questions too: when the migration could not cut concerns from it, cutting
   them is this session's first job, and each one starts from what the history file says is still open.

2. **Establish where we are, from the code.** For the loop's area, or the concern's `touches`: read the code
   that implements each claim the documents make, check deployed state where `LOOP.md` allows, and sort what you
   find into *verified* (with evidence), *assumed* (and how to check it) and *missing*. When you rely on outside
   sources, open them, and record each URL and the date you read it. Anything here that the plan did not know is a
   **new constraint**, and every new constraint becomes a question or a confirmation in step 4.

3. **Shape the concerns** (loop scope). Check each concern and the set as a whole:
   - **Size:** one branch, at most three claims, no "and" in the title. Split anything bigger.
   - **Independence:** compare `touches` across every pair of concerns in this loop and against active concerns in
     other loops. Resolve each overlap by declaring a `needs`, by extracting the shared part into a small contract
     concern that both need (decided and built first), or by merging the two.
   - **Hidden interfaces:** where two concerns must agree on a schema, an API or an event, that agreement is a
     contract concern or a shared decision, never an assumption.
   - **Coupling:** relations to other loops stay at the loosest level that works (relates, then a published
     decision, then a concern); see `loop-plan`. A decision another concern or loop must rely on is published in
     the README's Shared decisions; one that only this concern needs stays private in the concern.

4. **Grill.** List what needs the owner, blocking items first, and say how many there are. That covers the open
   `Q#`s, the new constraints from step 2, and the gaps the checklist below turns up. Then ask **one at a time**,
   or in a batch of up to four when they are small and independent. For each:
   - the question in one sentence, and why it matters now;
   - two to four options, each with its main consequence;
   - your recommendation and why, in one or two sentences;
   - what it blocks, and what happens if it stays open.

   What to probe, for every concern:
   - **Claims:** can each one fail? Who checks it, how, and on which environment? "It works" is not a claim.
   - **Premise:** which beliefs about the current system is this resting on, and are they verified?
   - **Effects:** does it touch shared data, money, identity, secrets, legal text or real users? Is each one in
     `effects`, and who performs it?
   - **Reversibility:** how does it roll back, and what does not roll back (data written, messages sent)?
   - **Failure:** what happens when its dependency is down, slow, or wrong? What would a user see?
   - **Unknowns:** which question would a cheap experiment answer better than an argument? Propose a spike
     (`/loop-prove <loop>/<concern> Q<n>`) and leave the question open rather than forcing it.

   If a question is already answered somewhere in the repository, cite where and ask the owner to confirm rather
   than asking it again.

5. **Record each answer as it comes in.**
   - A shared decision goes in the README: `D# | the decision in the owner's terms | <owner>, YYYY-MM-DD | the Q#
     it closes, anything it supersedes`. A private one goes in the concern, the same way.
   - Strike the answered question through with `→ D#`. Never renumber. A decision that reverses an earlier one
     strikes it through with `superseded by D#, YYYY-MM-DD`.
   - "You pick" is recorded as `agent, delegated by <owner>, YYYY-MM-DD`, so the provenance is honest. A gated or
     irreversible choice (`LOOP.md` §2) is never delegated silently: ask even if the owner said "you pick" earlier.
   - Decisions made in passing ("let's just use Postgres") count. Offer to record them.

6. **Propagate.** Update what each decision changes: the concern's Options and **Approach** (what will be built,
   citing the decisions), its contract (`needs`, `touches`, `effects`, `ships-to`), the claims. Mark each edit
   `(per D#)`. If a concern that is already building has its contract changed, say so plainly in the report, so the
   agent building it can be told; if a superseded decision is in some concern's `needs`, that concern is now stale
   or open, and `/loop-status` will show it.

7. **Write the files** and open the PR (see Boundary). Keep every section a reader needs and nothing more. Never
   add a status line or a "ready" marker: whether a concern is ready is derived from its open questions and its
   `needs`.

8. **Report** in a few lines: what was decided, which concerns are now ready (from `/loop-status`), what is still
   open and what it blocks, and the next command, usually `/loop-build <loop> --ready` to build every ready
   concern in parallel, or `/loop-prove` for a spike.

## Revising after a contradiction

When `/loop-status` shows a concern as contradicted, quote the CONTRADICTS line, re-establish where we are for its
`touches`, and design again from there: change the claims, the approach or the contract, and record why as a
decision. If the contradiction falsifies a shared decision or a loop-level assumption, raise it as a question for
the owner in the README, because other concerns rely on it. Do not quietly patch around it.

## Quality bar

- Every number has a source: a measurement, a file you read, a page you opened. Label estimates as estimates.
- Every claim can be checked by someone other than the author, on a named environment.
- No concern silently crosses a gate: every gate is in `effects`, with who performs it.
- Two concerns that will be built at the same time never share a path in `touches`.
