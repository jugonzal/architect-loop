---
name: loop-diagnose
description: Find the root cause of a bug or a surprising result with evidence rather than plausibility. Reproduces the symptom, forms competing hypotheses, isolates with A/B runs on otherwise identical inputs, credits a cause only when the evidence discriminates, and retracts earlier wrong diagnoses in writing. Use when something fails, flakes, is slow, behaves differently across environments, when loop-prove returns CONTRADICTS with an unknown cause, when a fix "worked" but nobody knows why, or when the owner asks for a root cause, "why is this happening?", or runs /loop-diagnose.
license: MIT
metadata:
  author: architect-loop
  version: "0.2"
---

# loop-diagnose

Find the cause that the evidence supports, not the first one that sounds right.

The most expensive failure in agent-assisted debugging is a plausible cause that is real but not
responsible: it gets fixed, the symptom goes away for an unrelated reason, and the wrong explanation
is written down and trusted.

## Boundary

May add instrumentation, reproducers and tests on a branch, and run read-only checks on environments
`LOOP.md` allows. Changes to shared environments go through the owner. The fix itself is built with
`/loop-build` once the cause is established (small, obvious fixes may be included, labelled as such).

**Without `LOOP.md`:** investigate locally, ask the owner before reading any shared environment, and
mention `/loop-init` once.

## Steps

1. **Pin the symptom.** Exact observable behaviour, where (environment, device, commit), since when,
   how often. Get the first bad and last good version if there is one (`git bisect` when practical).

2. **Reproduce it**, as cheaply as possible, and keep the reproducer. If it will not reproduce
   locally, list what differs between the places it does and does not happen: that list is usually
   the shortlist.

3. **Write competing hypotheses**, at least two, each with a prediction that would distinguish it:
   "If H1 (the new query plan is slow), the old build will also be slow on today's data. If H2 (the
   cache is cold after deploy), the new build will be fast on a second run and the old build slow on a first run."

4. **Discriminate.** Run the cheapest test that splits the hypotheses. Prefer an **A/B on identical
   code or input** that changes exactly one thing. Useful moves:
   - Take your code out of the loop: open the artifact with a reference client (the platform's own
     viewer, `curl`, the vendor's CLI). If it fails there, the fault is not in your UI.
   - Make hidden state visible: render internal status on screen or in logs where a screenshot or a
     grep can read it.
   - Change the environment, not the code: fresh process, full reload, clean container, other shell
     (`/bin/sh` is not always bash).

5. **Credit a cause only when the evidence discriminates.** Say what would still be true if you were
   wrong. If two causes are both real, say which one produced *this* symptom and record the other
   separately.

6. **Retract in writing.** If an earlier commit, PR, doc or memory credited a different cause, correct
   it explicitly: "Correct the root cause: X, not Y", with why Y was plausible, why it was not
   responsible, and the A/B that showed it. Keep anything from the earlier fix that is still
   independently correct, and say so.

7. **Record the cause where the next session will look.** If the symptom belongs to a concern, append an
   evidence line to the claim it explains, citing the commit on `main` where the cause was shown:
   `- YYYY-MM-DD · C2 · CONTRADICTS · rung 4 · staging @<sha> · cause: <X>, shown by <the A/B>`, through a PR that
   changes only `docs/loops/` (see `loop-prove`), and point `/loop-design` at the concern. Record the technique
   that ended the guessing, if it is reusable, in memory or `LOOP.md` §7, through `/loop-status`'s record step.

8. **Report**: symptom → cause (with the discriminating evidence) → fix (or hand-off to `/loop-build` for the
   concern, or `/loop-design` if the cause changes its design) → what was retracted.
