---
name: loop-frame
description: Frame a piece of work as a written proposal before anyone builds it. Reads the code, the environments and outside sources, then writes or revises docs/proposals/<slug>.md with where things actually stand, options with a recommendation, numbered open questions for the owner, and a phased plan whose steps each say what evidence proves them done. Use when the user wants to plan, scope, weigh options, evaluate a dependency, write an RFC, design doc or proposal, revise a plan that the evidence contradicted, or runs /loop-frame. Planning only; never implements.
license: MIT
metadata:
  author: architect-loop
  version: "0.1"
---

# loop-frame

Turn an intent into a proposal the owner can decide on and agents can build from.

## Boundary

**This skill plans; it does not build.** Even if the request that brought you here says "build X" or
"fix Y", this skill writes or revises a proposal and stops. It does not edit code, config or
infrastructure, and it does not start `loop-build` in the same turn. The owner starts building by
asking for it.

Skip the proposal for work under about a day that has no open question and no irreversible step: say
so, and suggest `/loop-build` directly.

Commit only on a `docs/<slug>` branch, per `LOOP.md` §6. Never commit on the main branch.

**Without `LOOP.md`:** use `docs/proposals/`, the conventions in the proposal template, the default
gates from `loop-init`, and treat every non-local environment as read-only and ask before reading
it. Mention `/loop-init` once.

## Steps

1. **Read `LOOP.md`** for where proposals live, the numbering and Status conventions, and the gates.

2. **Check for an existing proposal.** Search the proposals folder for the topic. If one covers it,
   *revise* it instead of creating a near-duplicate. Keep its Status state unless the revision changes
   it, append to its **Revisions** line (`YYYY-MM-DD: <what changed and why>`), and keep every
   existing `D#`/`Q#`/`G#` number. If the revision exists because `loop-prove` contradicted the plan,
   quote the verdict in the revision note.

3. **Establish where things actually are.** This section carries the proposal, and it is where
   agents most often go wrong by trusting docs. For every claim:
   - Read the code that implements it, not only the docs that describe it.
   - If `LOOP.md` lets you read an environment, check the deployed state there.
   - Sort findings into three lists: *shipped and verified* (with the evidence), *documented or
     assumed but not verified*, and *missing*.
   - When you rely on outside sources (vendor docs, pricing, upstream repositories), open the pages,
     and record each URL and the date you read it in the Sources section.

4. **Name the weak assumptions** (optional, for incidents and redesigns): the beliefs the current
   design rests on that the facts now contradict. Number them `A1, A2, …`.

5. **Lay out options.** For any real choice, at least two options, including "do nothing" or "stay"
   when it is viable. For each option: what it is, what it costs, what it breaks, how reversible it
   is, and what is uncertain about it. Use a comparison table when there are three or more.

6. **Recommend one**, with the reason in two or three sentences. A proposal without a recommendation
   hands the owner the analysis as well as the decision.

7. **Write the open questions** as `Q#` entries: the question, which steps it blocks, and the default
   you will assume if it goes unanswered. Keep them separate from **defaults the plan assumes**, which
   are the low-stakes calls you made yourself and the owner can veto. A question that would change
   scope, the chosen approach or the plan must be a `Q#` for the owner, never a silent default.

8. **Write the plan** as numbered steps, each small enough to be one PR or a short run of PRs. For
   each step: what it does, **done when** (observable: a test, a command's output, a measurement, a
   behaviour on a named environment), and whether it crosses a gate in `LOOP.md` §2. Put risky or
   uncertain work first, as a **spike**: a step whose only output is an answer to a `Q#`. Spikes are
   run by `loop-prove`, which writes the answer back into the proposal.

9. **Write the file** from [templates/proposal.md](templates/proposal.md) at
   `docs/proposals/<kebab-slug>.md`. A new proposal's Status is
   `Proposed — YYYY-MM-DD. Written from a read of <paths/sources>; nothing here is implemented.`
   Fill the `Area:` line with the paths the proposal governs, which `loop-reconcile` uses to spot drift.
   Keep the document as short as the decision allows. Optional sections may be deleted; **required
   sections stay, even if empty**, because other loop skills write into them.

10. **Stop and hand over.** Report in a few lines: the recommendation, the `Q#`s that block the first
    step, and the next command (`/loop-decide`). Do not begin implementation.

## Quality bar

- Every number has a source: a measurement you ran, a file you read, or a page you opened. Label
  estimates as estimates.
- Every "done when" can be checked by someone other than the author.
- No step silently crosses a gate. Gated steps say who performs them.
- The Summary states the recommendation and what the owner must decide. It never says "This document outlines…".
