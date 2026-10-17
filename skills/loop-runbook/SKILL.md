---
name: loop-runbook
description: Write or correct an operational runbook as actually run, not as imagined. Captures each step with its command, expected output and failure signature, and after every real execution corrects the steps that were wrong and records each trap with the date it cost time. Use when a procedure (deploy, provision, restore, rotate secrets, issue certificates, cut a release) is about to be run for the first time or has just been run, or when the owner asks to "write a runbook", "document how to do X", "fix the runbook", or runs /loop-runbook.
license: MIT
metadata:
  author: architect-loop
  version: "0.2"
---

# loop-runbook

A runbook is only trustworthy after it has been run. This skill writes it, then fixes it against
the first real execution, and every one after that.

## Boundary

Writes and edits files in the runbooks folder from `LOOP.md` (default `docs/runbooks/`). It does not
execute steps against shared environments: the owner does, or an agent acting within `LOOP.md` §2
(a per-action yes) or §2.1 (a delegated action). This skill records what happened. Commit only on a
`docs/<slug>` branch, per `LOOP.md` §6.

**Without `LOOP.md`:** use `docs/runbooks/`, and mention `/loop-init` once.

## Modes

### Draft (before the first run)

1. Build the steps from the scripts and config that actually exist, not from memory of how such
   things usually work. Read each script you cite.
2. Use [templates/runbook.md](templates/runbook.md). For every step: the exact command, what success
   prints, what failure looks like, and whether it is safe to re-run.
3. Mark the runbook `Status: draft — not yet run`. A reader must be able to tell it is untested.

### Correct (after a real run)

1. Walk the run with the person who did it, or from the session's commands and outputs. For each step,
   note: ran as written / ran with changes / skipped / failed.
2. Rewrite every step that differed, **as it was actually run**. Add steps that turned out to be
   needed; remove or mark steps that were not.
3. For each surprise, add a **trap** with the date: what happened, why, how to avoid it. The traps
   are the most valuable part: a step that fails silently or looks like a different problem.
4. Look for the same trap elsewhere: other runbooks and scripts with the same shape (a `grep -q`
   under `pipefail`, a check that cannot see a file owned by root, a packaging step that ships committed
   state rather than the working tree). Fix other runbooks; **flag** scripts and code in the report
   for `/loop-build`, and do not edit them here.
5. Update `Last run as written:` with the date, the environment and who ran it.
6. Commit as its own change: "Correct the <topic> runbook against the sequence as actually run", with
   a body listing each correction.

## Quality bar

- Every command can be copied and run; placeholders are obvious (`<HOST>`), never plausible-looking fakes.
- Every "verify" step says what output means success.
- Steps that do not roll back (data written, email sent, DNS changed) say so.
- The quick reference at the top fits on one screen.
