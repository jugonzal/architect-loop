---
name: loop-reconcile
description: Audit a repository's documents against reality. Finds every status line, "done" marker, runbook step, README claim and memory fact that no longer matches the code, the git history or what the environments actually serve, and produces a corrections list for the owner to approve. Use when adopting the loop on an existing project, before planning on top of old docs, when a status line looks stale or two docs disagree, periodically, or when the owner asks "are the docs right?", "what's actually deployed?", or runs /loop-reconcile.
license: MIT
metadata:
  author: architect-loop
  version: "0.1"
---

# loop-reconcile

Status lines go stale. This skill finds where the written record and reality have drifted apart.

## Boundary

Read-only until the owner approves corrections. Reads docs, code, git history and any environment
`LOOP.md` lets agents read. Never changes an environment. After approval, applies documentation
corrections as their own commit on a `docs/<slug>` branch, per `LOOP.md` §6.

**Without `LOOP.md`:** check documents against the code and git history only, ask the owner before
reading any shared environment, and mention `/loop-init` once.

## Steps

1. **Pick the scope**: one proposal, one runbook, all of `docs/`, or memory. Default: every proposal
   whose Status date is older than the most recent commit touching the paths on its `Area:` line
   (`git log -1 --format=%cs -- <paths>`), plus every file in `docs/memory/`.

2. **Extract checkable claims.** From each document, list the statements that can be true or false
   today: "X is on staging", "Step 3 done", "G2 met", "the backup job is scheduled", "the verify
   script runs 12 checks", "unsigned requests get 403", "not yet deployed". Ignore opinions and plans.

3. **Check each claim against the strongest source available**, and record which you used:
   - the environment (read-only commands, HTTP checks, versions served, crontabs, configs)
   - the main branch (does the code exist, is it wired in, is it behind a flag that is off?)
   - git history and merged PRs (when did it land, was it reverted?)
   - another document (the weakest source; flag it as such)

4. **Classify** each claim: **true**, **stale** (was true, no longer), **wrong** (never true),
   **ahead** (the doc understates: done but not recorded), or **uncheckable** (and what would check it).
   Also flag **self-contradictions**: the same fact stated differently in two places.

5. **Present the corrections list** to the owner, most consequential first. Consequential means a
   future agent or person would act wrongly on the current text: a diagnostic that is actually
   silent, a gate recorded as unmet that was met, a "deployed" that is not.

   ```text
   docs/proposals/x.md §5.1   "TLS is not built"       → wrong: served on staging since YYYY-MM-DD (checked: curl -vI …)
   docs/runbooks/y.md step 4  "optional"               → wrong: skipping it leaves callback URLs on http (checked: …)
   docs/memory/z.md           "PR #42 not on staging"  → stale: deployed YYYY-MM-DD (checked: version endpoint)
   ```

6. **Apply approved corrections** in one commit per document or one commit overall, with a subject
   like "Bring <doc> back in line with <env/tree>, and correct N claims the work disproved" and a
   body that lists each claim, the truth, and how it was checked. Update the Status line date.

7. **Suggest a cadence** if drift was large: reconcile before each `/loop-frame` on an area, and after
   each promotion.
