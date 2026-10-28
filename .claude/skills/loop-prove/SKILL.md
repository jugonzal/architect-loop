---
name: loop-prove
description: The evidence gate for one concern. Proves whether its claims hold, or answers a spike's question, with the strongest evidence available (tests, a reproducer, an end-to-end smoke run, an A/B on identical inputs, a measurement on real data or a real environment), and records each verdict (HOLDS, CONTRADICTS or UNPROVEN) bound to the commit and environment it was made on. Before a merge the verdict goes in the pull request; after it, an evidence line goes in the concern file. CONTRADICTS sends only that concern back to design. Use after a build, after a deploy, to run a spike, to settle a choice empirically, to re-prove a stale concern, or when the owner says "prove it", "measure it", "does this actually work", or runs /loop-prove.
license: MIT
metadata:
  author: architect-loop
  version: "0.2"
---

# loop-prove

Decide with evidence whether a concern's claims hold, and bind the answer to what it was proven on.

An agent will confidently extend whatever the document says. This skill is the counterweight: every claim is a
hypothesis until something outside the author's head confirms it, and a confirmation is only good for the
commit and the environment it was made on.

## When it runs

- **Before the merge**, on the concern's branch: local runs, the smoke test, A/Bs, read-only checks. The
  verdict goes in the PR body ("How it was proven before the merge"), because loop documents only describe
  `main`. Output: whether the PR is ready for the owner to merge.
- **After the merge**, on each environment that serves the concern's work, up to its `ships-to`. This is
  usually the strongest proof available, and the only kind that makes a concern done.
- **For a spike** (`/loop-prove <loop>/<concern> Q<n>`): the only output is an answer to a question. Run the
  experiment and record the answer for `/loop-design` to turn into a decision.
- **For a stale concern**: code under its `touches`, or a decision it needs, changed after its last proof.
  Prove again on what is served now.

## Boundary

This skill runs tests, scripts and read-only checks, and may add a reproducer, a smoke script or an evaluation
harness through a normal code PR. It reads only environments that `LOOP.md` §3 allows, and never changes one.
It does not fix what it finds: fixing is `/loop-build`, and finding the cause is `/loop-diagnose`.

Evidence lines go in the concern file through a PR that changes only `docs/loops/`. Under `LOOP.md` §2.1 it
merges that PR itself once `scripts/check_loop_pr.sh` from the loop-status skill passes, which it will only if
every commit the lines cite is on `main`.

**Without `LOOP.md`:** use local runs and tests only, ask the owner before reading any shared environment, leave
the PR for the owner, and mention `/loop-init` once.

## Steps

1. **Find what to prove.** Run `/loop-status <loop>/<concern>`. It says which claims lack a current HOLDS, on
   which environment, at which commit. Prove those, unless the owner named others.

2. **State each claim so it can fail**, from the concern's Done when (or the question, for a spike). For example:
   "A report requested during peak load completes within 30 s on staging." Rewrite vague claims ("it works")
   until they can fail, and if the rewrite changes what the claim means, that is a question for `/loop-design`.

3. **Choose the strongest evidence you can get**, in this order, and say which rung you used:
   1. A real environment with real input (live traffic, production-like data, a real device)
   2. A real environment with synthetic input (a smoke run with generated input or fixtures)
   3. A local stack that matches the environment (same images, same config shape)
   4. An A/B: the same input through both versions or both candidates, compared on a stated metric
   5. Automated tests (CI on the commit counts here)
   6. Reading the code (the weakest; say so if it is all you have)

   When the owner must supply reality (a device, a real dataset, an account, a read of production), ask for
   exactly that rather than silently settling for a weaker rung.

4. **Pin what you prove it on.** Record the commit: the branch head before the merge, or the environment's served
   commit after it (from `LOOP.md` §3). A proof without a commit and an environment is not evidence.

5. **Run it and keep the raw evidence**: commands, outputs, numbers with units, sample sizes, dates. For
   measurements, run enough to see the variance, and report it. For A/Bs, fix everything except the variable,
   and choose the metric **before** looking at the results.

6. **Reach a verdict** per claim:
   - **HOLDS**: the evidence supports the claim, at the rung stated.
   - **CONTRADICTS**: the evidence disproves the claim, or the premise under it.
   - **UNPROVEN**: the evidence could not be obtained. Say what is missing and who can supply it, by ending the
     line with `· needs <who>: <what>`. `<who>` is the GitHub login of the person who has it, `owner` for the
     loop's owner, `gate:<key>` for the holder of a `LOOP.md` §2 gate, or `agent` when an agent can close the gap
     alone (a rerun, a harness that was down). `/loop-status` puts every gap but an agent's in that person's Needs
     you, and sends a line without the segment to the loop's owner as drift, so always write it.

7. **Write it down where the next session will look.**
   - Before the merge: in the PR body, one line per claim:
     `C1: HOLDS (rung 3, local, @<branch-sha>): <evidence>`.
   - After the merge: append one line per claim to the concern's Evidence, on a `docs/<loop>-proof-<date>`
     branch: `- YYYY-MM-DD · C1 · HOLDS · rung 1 · staging @<served-sha> · <one line of evidence, with numbers>`.
     An UNPROVEN line ends with its needs segment:
     `- YYYY-MM-DD · C2 · UNPROVEN · rung 1 · staging @<served-sha> · <what was and was not observed> · needs owner: <what>`.
     Never edit or delete an earlier line; a newer one supersedes it. Open the PR and merge it as described in
     Boundary.
   - A spike: `- YYYY-MM-DD · Q2 · HOLDS · rung 4 · local @<sha> · <the answer>`. It may cite a branch, because
     a spike's code may never merge.

8. **Act on the verdict:**
   - **HOLDS** everywhere it must: say so, and let `/loop-status` show the concern as done.
   - **HOLDS before the merge**: the PR is ready for the owner.
   - **CONTRADICTS**: stop going forward with this concern, and only this one. Name the claim or the statement in
     its design that the evidence contradicts, and recommend `/loop-design <loop>/<concern>`, or `/loop-diagnose`
     if the cause is unknown. If the contradiction falsifies a shared decision or another loop's published
     decision, say so in the evidence line ("contradicts <loop>/D2"), so `/loop-status` raises it with the owner.
     On a shared environment, also tell the owner whether users are affected and whether to roll back; that call
     is theirs. Do not patch forward on a false premise.
   - **UNPROVEN**: record it as a named gap, with who can close it in its needs segment. Never report it as passing.

9. **Report** in the format below, leading with the verdict.

## Report format

```text
Verdict:  HOLDS | CONTRADICTS | UNPROVEN
Concern:  <loop>/<concern>, C<n> (or Q<n> for a spike)
Claim:    <the falsifiable statement>
On:       <environment> @<sha>, rung <n>
Evidence:
  - <command or procedure> → <result, with numbers and units>
Contradicts: <the design text or shared decision that is now wrong, if any>
Recorded: PR #<n> body | evidence line in docs/loops/<loop>/<concern>.md (PR #<n>, merged | left for the owner)
Next:     /loop-status | /loop-design | /loop-diagnose | owner must supply X
```

## Traps

- A test that passes because it no longer exercises the path. Check that it fails without the change.
- Proving on your laptop what only matters in the environment: a different shell, missing codecs or libraries,
  another CPU architecture, no TLS. If the environment differs, say so in the verdict.
- One sample. A single real run is a case, not a calibration. Say how many you have.
- Crediting the last change for a result without an A/B on otherwise identical code.
- Recording an environment proof against a commit the environment does not actually serve. Read the served
  commit first, every time.
