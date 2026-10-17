# Ten collaboration patterns

These are the habits the method was distilled from. Each was observed repeatedly in the commit
history of a five-month, one-architect build of a live video platform: 196 commits, 138 pull requests,
15 proposals, 9 runbooks and 28 memory facts. The examples are paraphrased commit subjects.

Generation 2 keeps every one of them. What changed is where state lives; see
[proposals/concerns-as-functions.md](proposals/concerns-as-functions.md).

## 1. Document-first: the proposal is the contract

Nearly every large change began as a proposal drafted by an agent from a read of the code. Each
carries a dated Status line, numbered decisions, questions and gates, and a phased plan with a
definition of done. Implementation PRs cite sections ("§7.4 reproducer", "Step 3").

In generation 2 the loop and its concerns are the contract, and a PR cites the concern it builds.

*Skills:* `loop-plan`, `loop-design`

## 2. The agent proposes, the human decides

Agents lay out options with a recommendation; the human answers the open questions, often in a
commit of their own. "Propose what Free, Athletes and Teams each unlock" (agent) was followed the
same day by "Answered pending questions in paywall plan" (human). An evaluation of seven ingest
servers ended in one recommendation; the human chose the path.

*Skill:* `loop-design`

## 3. Reality corrects the document

When the work disproves the plan, the plan is rewritten, and the commit says what was wrong. This is
the single most distinctive habit in the log: "Record M0 as complete, and correct four claims the
work disproved"; "Correct the issuance runbook against the sequence as actually run"; "Record the
iOS build path as executed, not as documented"; "Write down what shipped, and where it departs from the proposal".

*Skill:* `loop-status` (its record step, and `audit`)

## 4. Measure or spike before committing

Uncertain choices were settled by experiment, not argument: a spike to settle whether branded video
could be spliced at all; a detector A/B on a real game (one won 5/5, the other 3/5); per-event CPU
measured before sizing the box; a ranker graded against four real games; a synthetic stream proving
the pipeline end to end.

*Skill:* `loop-prove`

## 5. Root cause, stated and retracted in the open

Agents write the reasoning into the commit body, including when a previous diagnosis was wrong:
"Correct the player root cause: stale native views, not the HLS spec violation". The earlier fix
was real but unrelated, and the commit says so.

*Skill:* `loop-diagnose`

## 6. One intent per PR, subject written as an outcome

138 PRs in five months, often five to ten a day. Subjects read as sentences about behaviour ("Stop a
laptop from paging as production"), so the log is itself a readable changelog. In generation 2 the
unit is the concern: one branch and usually one PR each.

*Skill:* `loop-build`

## 7. The human holds the gates

Agents can read servers and open PRs; promotion is a human act. A third of all PRs were short,
human-titled promotions to staging or production. Store accounts, payment-provider settings, legal
sign-off and production secrets stayed with the human.

*Skills:* `loop-init` (writes the gates down), `loop-ship`

## 8. Memory outside the chat

Facts that cost time to learn were written to persistent memory: environment traps (the local
encoder lacks a codec; the container's `/bin/sh` is dash; iOS builds need a UTF-8 locale), decisions
and their dates, and what is deployed where. A new session starts where the last one stopped. (Generation 2 no longer
writes down what is deployed where: `loop-status` reads it from the environments.)

*Skill:* `loop-status` (its record step)

## 9. Runbooks agents can execute

Runbooks for staging, secrets, alerts, disk-full, database restore, mobile builds and billing were
written as steps an agent or a person can follow, and corrected after each real run.

*Skill:* `loop-runbook`

## 10. Incident → proposal → fix, in one day

Production pain became a written proposal, then a PR, usually the same day. A day of false
production alerts produced a monitoring-revamp proposal and its implementation on the same date. An
upstream base image reaching end of life produced a dependency-risk evaluation and a rebase.

*Skill:* `loop-incident`
