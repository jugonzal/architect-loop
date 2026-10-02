---
name: loop-decide
description: Walk the owner through a proposal's open questions and record their answers as numbered, dated decisions. Presents each question with the options, the trade-off and a recommendation, never answers on the owner's behalf, and afterwards says which plan steps are unblocked. Use after loop-frame, when a proposal has open Q#s, when the owner wants to answer questions, choose between options, veto a default, or record a decision made in passing, or runs /loop-decide.
license: MIT
metadata:
  author: architect-loop
  version: "0.1"
---

# loop-decide

Get decisions from the owner and write them where every later session will find them.

Deciding is the owner's job. The agent's job is to make each decision cheap: one question at a
time, the options and trade-off already laid out, a recommendation, and a record that outlives the
conversation.

## Boundary

This skill edits the proposal's Decisions, Open questions, Defaults and Status sections, and marks
plan steps as blocked or unblocked. It does not edit code, and it does not treat a question as
answered unless the owner answered it in this conversation. Commit only on a `docs/<slug>` branch,
per `LOOP.md` §6.

**Without `LOOP.md`:** use `docs/proposals/` and the proposal template's numbering, and mention
`/loop-init` once.

## Steps

1. **Pick the proposal.** Use the one named, or the one discussed in this conversation. If there are
   several with open questions, list them with their counts and ask which.

2. **List the open questions** that block the next unstarted plan step first, then the rest. Say how
   many there are. If a question is already answered by something in the repo (a later commit, a
   newer proposal, `LOOP.md`), say so and ask the owner to confirm rather than asking the question again.

3. **Ask one at a time**, or in a batch of up to four when they are independent and small. For each:
   - the question in one sentence
   - the options (two to four), each with its main consequence
   - your recommendation and why, in one or two sentences
   - what it blocks, and what happens if it stays open

   When a question turns out to depend on facts nobody has, do not force it: propose a spike step in
   the plan that would answer it, and leave the question open.

4. **Record each answer** as it comes in, as a row in the Decisions table:
   `D# | the decision in the owner's terms | <owner>, YYYY-MM-DD | the Q# it closes, anything it supersedes`.
   Move the answered `Q#` out of Open questions (strike it through with `→ D#`). Never renumber.
   If a decision reverses an earlier one, strike the earlier `D#` through with `superseded by D#, YYYY-MM-DD`.

5. **Propagate.** A decision often changes text elsewhere in the proposal: the recommendation, a
   plan step, a default. Update those places and mark each edit `(per D#)`. If a decision
   invalidates the plan's shape, say so and suggest `loop-frame` to revise it rather than patching
   around it.

6. **Handle vetoes of defaults.** If the owner overturns a default from "Defaults this plan assumes",
   record it as a decision like any other.

7. **Update the Status line.** When every `Q#` that blocks the first unstarted step is answered, set
   the state to `Accepted`: `Accepted — YYYY-MM-DD. D1–D4 decided; Q5 open (blocks Step 3).`
   Otherwise keep the state and update the sentence. A proposal already `In progress` stays so.

8. **Report** which steps are now unblocked and the next command (usually `/loop-build step N`, or `/loop-prove` for a spike).

## Notes

- Decisions the owner makes in passing ("let's just use Postgres") count. Offer to record them.
- If the owner delegates ("you pick"), record it as `D# | <choice> | agent, delegated by <owner>, YYYY-MM-DD`
  so the provenance is honest.
- Irreversible or gated choices (`LOOP.md` §2) are never delegated silently. Ask even if the owner said "you pick" earlier.
