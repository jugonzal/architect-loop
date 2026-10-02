---
name: loop-prove
description: The evidence gate. Proves whether a change, a plan's premise or a spike's question holds, using the strongest evidence available (tests, a reproducer, an end-to-end smoke run, an A/B on identical inputs, or a measurement on real data or a real environment), then writes the verdict (HOLDS, CONTRADICTS or UNPROVEN) into the proposal and the PR. On CONTRADICTS it sends the work back to framing instead of forward. Use after a build and again after a promotion, to run a spike, to settle a choice empirically, to check a claim before relying on it, or when the owner says "prove it", "measure it", "does this actually work", or runs /loop-prove.
license: MIT
metadata:
  author: architect-loop
  version: "0.1"
---

# loop-prove

Decide with evidence whether the plan still holds.

An agent will confidently extend whatever the document says. This skill is the counterweight: it
treats every claim as a hypothesis until something outside the author's head confirms it.

## When it runs

- **Before promotion:** on the branch, with local runs, the smoke test, A/Bs, and read-only checks of
  any environment `LOOP.md` lets agents read. Output: go or no-go for `/loop-promote`.
- **After promotion:** on the environment the change now runs in, against the PR's "still to prove"
  list and the step's **done when**. This is usually the strongest proof available, and the only one
  that counts for a `G#`.
- **For a spike:** the step's only output is an answer to a `Q#`. Run the experiment, and write the
  answer and its evidence into the proposal for `/loop-decide`.

## Boundary

This skill runs tests, scripts and read-only checks, and may add a reproducer, a smoke script or an
evaluation harness on a branch. It reads only environments `LOOP.md` §3 allows, and never changes one.
It does not fix what it finds: fixing is `/loop-build`, finding the cause is `/loop-diagnose`. It
writes verdicts into the proposal (step **Proof** field) and the PR, committing only on a branch per
`LOOP.md` §6.

**Without `LOOP.md`:** use local runs and tests only, ask the owner before reading any shared
environment, and mention `/loop-init` once.

## Steps

1. **State what is being proven**, as falsifiable claims copied from the step's **done when**, a
   `G#`, a `Q#` (for a spike) or the PR's "still to prove" list. For example: "A report requested
   during peak load completes within 30 s on staging." Rewrite vague claims ("it works") until they can fail.

2. **Choose the strongest evidence you can get**, in this order, and say which rung you used:
   1. A real environment with real input (live traffic, production-like data, a real device)
   2. A real environment with synthetic input (a smoke run with generated input or fixtures)
   3. A local stack that matches the environment (same images, same config shape)
   4. An A/B: the same input through both versions or both candidates, compared on a stated metric
   5. Automated tests
   6. Reading the code (the weakest; say so if it is all you have)

   When the owner must supply reality (a device, a real dataset, an account, a read of production),
   ask for exactly that rather than silently settling for a weaker rung.

3. **Run it and keep the raw evidence**: commands, outputs, numbers with units, sample sizes, dates,
   the commit and the environment. For measurements, run enough to see the variance, and report it.
   For A/Bs, fix everything except the variable, and choose the metric **before** looking at results.

4. **Reach a verdict** per claim:
   - **HOLDS**: the evidence supports the claim, at the rung stated.
   - **CONTRADICTS**: the evidence disproves the claim, or the premise under it.
   - **UNPROVEN**: the evidence could not be obtained. Say what is missing and who can supply it.

5. **Write it down where the next session will look.** One line in the step's **Proof** field:
   `HOLDS (rung 2, staging, YYYY-MM-DD): <one-line evidence>`. For a spike, also write the answer
   under its `Q#`. If there is a PR, add the full report as a comment or in the body's "How it was
   proven" section.

6. **Act on the verdict:**
   - **HOLDS, before promotion:** hand off to `/loop-promote`.
   - **HOLDS, after promotion:** hand off to `/loop-record`.
   - **CONTRADICTS:** stop going forward. Name the statement in the proposal, runbook or PR that the
     evidence contradicts. Recommend `/loop-frame` to revise the plan, or `/loop-diagnose` if the
     cause is unknown. After promotion, also tell the owner whether users are affected and whether to
     roll back; that call is theirs. Do not patch forward on a false premise.
   - **UNPROVEN:** record it as a named gap. Never report it as passing.

7. **Report** in the format below, leading with the verdict.

## Report format

```text
Verdict: HOLDS | CONTRADICTS | UNPROVEN
Claim:   <the falsifiable statement>
When:    before promotion | after promotion to <env> | spike for Q#
Rung:    <evidence level from step 2>
Evidence:
  - <command or procedure> → <result, with numbers and units>
Contradicts: <doc/section or PR text that is now wrong, if any>
Next:    /loop-promote | /loop-record | /loop-frame | /loop-diagnose | owner must supply X
```

## Traps

- A test that passes because it no longer exercises the path. Check that it fails without the change.
- Proving on your laptop what only matters in the environment: a different shell, missing codecs or
  libraries, another CPU architecture, no TLS. If the environment differs, say so in the verdict.
- One sample. A single real run is a case, not a calibration. Say how many you have.
- Crediting the last change for a result without an A/B on otherwise identical code.
