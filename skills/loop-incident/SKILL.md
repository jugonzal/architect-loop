---
name: loop-incident
description: Turn production pain into a written account, a proposal and a fix, fast. Establishes the timeline from logs and alerts, separates what the system believed from what was true, names the weak assumptions that let it happen, and proposes changes ordered by how much recurrence they prevent, handing off to loop-frame, loop-build and loop-record. Use during or after an outage, a storm of false alerts, a build broken by an upstream change, a security finding, or when the owner asks for a postmortem, "what just happened?", or runs /loop-incident.
license: MIT
metadata:
  author: architect-loop
  version: "0.1"
---

# loop-incident

Pain is information. Capture it while it is fresh and turn it into a change the same day.

## Boundary

During an active incident: read-only investigation plus recommendations to the owner. Mitigations
that touch a shared environment (restart, rollback, silence, firewall change) are performed by the
owner, unless `LOOP.md` §2.1 delegates that exact action to agents. After the incident: the account
and the proposed changes go into one proposal through `/loop-frame`, and fixes are built through
`/loop-build`.

**Without `LOOP.md`:** investigation is read-only and every mitigation is the owner's. Mention
`/loop-init` once.

## Steps

1. **Stabilise first, if it is still happening.** Tell the owner the fastest safe mitigation and its
   side effects, and wait for a go-ahead. Record what was done and when.

2. **Build the timeline** from primary sources: alert messages, logs, deploy history, commits, chat
   times. Absolute timestamps with time zone. Mark each entry *observed* or *inferred*.

3. **Separate belief from truth.** For each alert, dashboard or message: what did it claim, and
   what was actually happening? False alarms and silent failures are both findings. Identify the
   source of every signal: which process, which host, which environment. (A monitor running on a
   laptop can page as production.)

4. **Name the weak assumptions** (`A1, A2, …`): the beliefs the design relied on that the incident
   disproved, e.g. "the process knows which environment it is in", "a stale heartbeat means the
   component is down", "the monitor can report its own death".

5. **Propose changes** (`P1, P2, …`), each tied to the assumptions it removes, ordered by how much
   recurrence it prevents per unit of effort. Include at least one change to *detection*, not only
   to the failing component.

6. **Write it down** as a proposal via `/loop-frame`, at `docs/proposals/incident-YYYY-MM-DD-<slug>.md`
   (or as a revision of the proposal that owns the failing area), mapped onto the template: the
   timeline and belief-versus-truth table go in §1 "Where we actually are", the `A#`s in §3, and the
   proposed changes become §9 plan steps (keep their `P#` labels in the step titles so the account
   can refer to them). Put any urgent, obvious fix straight into `/loop-build` as its own PR.

7. **Close the loop** via `/loop-record`: update runbooks with the traps, `LOOP.md` §7, and memory.
   Record the incident's cost (duration, users affected, false pages) so the owner can weigh the fixes.

## Tone

Blameless and specific. The subject is the system and its assumptions. A laptop monitor, a missing
flag and a stale document are all system parts.
