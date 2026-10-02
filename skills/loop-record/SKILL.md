---
name: loop-record
description: Close a turn of the architect loop by writing back what is now true. Updates the proposal's dated Status line, step statuses and met gates, writes "what shipped and where it departs from the proposal", corrects any claim the work disproved in a dedicated commit that names what was wrong, updates runbooks, and saves non-obvious facts to shared memory. Use after a change is proven on its environment, after a spike is answered, when the owner says "it's on staging now", "we shipped X", "write down what we learned", "close this out", or runs /loop-record.
license: MIT
metadata:
  author: architect-loop
  version: "0.1"
---

# loop-record

Leave the repository knowing what this turn learned, so the next session starts from the truth.

The next agent that picks up this work will have no memory of this conversation. Whatever is not
written down is lost, and whatever is written wrong will be trusted.

## Boundary

This skill edits documentation (proposals, runbooks, reference docs, `LOOP.md` §7 traps) and the
memory folder. It changes no code. It commits only on a `docs/<slug>` branch, per `LOOP.md` §6, never
on the main branch.

**Without `LOOP.md`:** use `docs/proposals/`, `docs/runbooks/` and `docs/memory/`, and mention
`/loop-init` once.

## Inputs

Written by earlier stages, so this skill does not depend on anyone's chat history:

- the steps' **Status** and **Proof** fields in the proposal (from `loop-build` and `loop-prove`)
- the promotion entries in the proposal's §11 (from `loop-promote`)
- PR bodies and comments, and the commits merged since the Status line's date

## Steps

1. **Gather what happened** from the inputs above, plus anything from this conversation that
   surprised anyone.

2. **Verify before you write.** Check every status you are about to record ("on staging", "done",
   "G2 met") against the environment or the main branch, not against another document or a chat
   message. If you cannot check it, write it as unverified.

3. **Update the proposal:**
   - **Status line:** state + date + one sentence, per the table in `LOOP.md` §6. For example,
     `In progress — YYYY-MM-DD. Steps 1–4 on staging (verified YYYY-MM-DD); Step 5 built, not merged; Q7 open.`
     Set `Done` only when every `G#` is met with evidence.
   - **Steps:** make each step's Status current (`merged #PR`, `on <env>, verified YYYY-MM-DD`, `done`).
   - **Gates:** mark a `G#` met only with its evidence and date.
   - **§11 What shipped, and where it departs:** list each deviation from the proposal's text, and add
     a short note at the section it affects, so a reader of that section is not misled.

4. **Correct what the work disproved.** When the evidence contradicted something written (in the
   proposal, a runbook, a README, or an earlier commit's claim), fix the text in a **separate commit**
   whose subject says so, for example "Correct the restore runbook against the sequence as actually
   run", with a body that lists each wrong claim, what is actually true, and how that was
   established. Corrections are the most valuable commits in the log; do not bury them in a feature commit.

5. **Update runbooks** touched this turn, via `/loop-runbook` if a procedure was run for real.

6. **Save memory**: only facts that are non-obvious, cost time to learn, and are not already in the
   repo, such as environment traps, decisions and their dates, what is deployed where, and who must
   do what. Write them to `docs/memory/` using [templates/memory-fact.md](templates/memory-fact.md),
   which every person and agent tool can read. Update an existing fact rather than adding a
   near-duplicate, and delete facts this turn proved wrong. Give every time-sensitive fact an absolute date.

7. **Report** what was recorded, what was corrected and why, and the next step in the loop.

## What not to record

- What the code or `git log` already says plainly.
- Chat-only context that will not matter next week.
- Guesses written as facts. Mark anything unverified as unverified.
