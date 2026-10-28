---
needs: []
touches: [plugin/skills/loop-status/scripts/loop_status.py, plugin/skills/loop-status/scripts/addressing.py, plugin/skills/loop-status/scripts/status.schema.json, plugin/skills/loop-status/SKILL.md, plugin/skills/loop-prove/SKILL.md, tests/test_loop_status.py, tests/test_addressing.py, tests/test_status_schema.py, tests/fixtures/loop_status/, tests/fixtures/addressing/, tests/fixtures/status/, app/src/api/status.gen.ts, app/src/features/inbox/queue.ts, app/src/features/inbox/InboxScreen.tsx, app/src/features/inbox/__tests__/queue.test.ts]
effects: [a plugin release so that terminals print the same queue (the owner releases it per D17; gates: release), staging/status redeployed so that it serves it (the owner deploys it; gates: deploy)]
ships-to: staging/status
---
# Needs you is never empty while unfinished work waits on a person

## Done when

- **C1** An UNPROVEN line ending `· needs <who>: <what>` queues a proof item waiting on that person: the login, the
  loop's owner for `owner`, or the gate's holder for `gate:<key>`. An UNPROVEN line without the segment queues a
  proof item waiting on the loop's owner, with the line's text as what is missing, plus a drift line asking for a
  re-proof that names who (per D74, D75). `/loop-prove` says to write the segment. Prove: fixture cases for each
  form of `<who>` and for a line without the segment, in CI on main. Then, on staging/status, the served document's
  queue holds one proof item for each of today's 8 UNPROVEN claims, each with a `waits_on`.
- **C2** A `LOOP.md` §3 row that agents may not read, or whose command is `TODO(owner)`, gives a `fact` item when an
  unfinished concern's state rests on it. The item waits on the loop's owner and names the fact, its error and the
  concerns waiting on it. A row no unfinished concern rests on gives no item (per D76). Prove: fixture cases for a
  forbidden row with dependants, and for `TODO(owner)` rows without any, in CI on main. Then, on staging/status,
  one `fact` item for `staging/app` listing the app concerns that are `unknown` on it, and none for the
  `production/*` rows.
- **C3** Every concern that is neither done nor parked leads to a queue item, or to an "Agents can start" entry
  that no person has to unblock. A proof whose unproven claims all wait on a person is not in "Agents can start". A
  concern that still leads to no one gives a `stuck` item waiting on the loop's owner, naming why (per D77).
  Prove: a test that walks every fixture document and fails if any unfinished concern leads to no one, plus a
  fixture that forces `stuck`, in CI on main. Then, on staging/status, the served document: its queue is not empty,
  and no proof waiting on a person appears in `agents_can_start`.

## Design

### Where we are

- **Verified** (`loop_status.py --json` at main @41597ff, 2026-10-28):
  - The queue held 0 items. "Agents can start" held 14 proofs.
  - 8 claims' latest verdict was UNPROVEN, and none of them was queued.
  - 9 concerns were `unknown` because `staging/app`'s served commit cannot be read: app-agents, app-clients,
    app-documents, app-environments, app-inbox, app-loops-board, app-shell, app-threads and latest-release. Their
    next step, "Read what staging/app serves with the owner", went nowhere.
  - `app-served` would make `staging/app` readable (per D57). It was blocked on `status-service`, whose UNPROVEN
    claims need owner writes to staging. That was not queued either.
- **Verified** (`queue()` in `loop_status.py`): UNPROVEN lines are queued only when `NEEDS_ONLY_RE` or `ONLY_RE`
  matches their text. The lines on main say "The owner can run it" and "Needs the owner to run …", which neither
  pattern matches. A line that matches neither is skipped, with no drift line. `/loop-prove`'s SKILL.md only asks
  to "say what is missing and who can supply it". `agents()` lists a prove step for every shipped or stale
  concern, whoever its proof waits on.
- **Verified** (`addressing.py`, `address`): an item's `waits_on` is the holder of its gate, and otherwise the
  loop's owner. There is no way yet to name a login directly.
- **Verified** (`.github/workflows/app.yml`, `app/src/features/inbox/queue.ts`):
  - CI checks that `app/src/api/status.gen.ts` matches the schema.
  - `KIND_LABELS` is a `Record<QueueKind, string>`, so a new kind in the schema fails the app's typecheck unless
    the label is added in the same change.
  - `ItemBody`'s `switch` has no default, so an app built before this change shows a new kind's card with an
    empty body.
- **Verified** (`EVIDENCE_RE`): the needs segment sits inside the line's text field, so existing parsers read new
  lines unchanged. `environments` C1's 2026-10-27 line has `—` where its rung should be, so `EVIDENCE_RE` does not
  read it as evidence. Only `EVIDENCE_LIKE_RE`'s drift line shows it.

### Approach

- **Needs segment** (per D74, D75):
  - `loop_status.py` reads `· needs <who>: <what>` at the end of an UNPROVEN line's text with one strict pattern,
    and puts `who` and `what` in the proof item's `supplied_by` and `missing`.
  - `addressing.py` resolves `who` into `waits_on`:
    - a login is used as is;
    - `owner` is the loop's owner;
    - `gate:<key>` sets the item's `gate`, so its holder is used;
    - `agent` queues nothing, and the proof stays in Agents can start (per D2).
  - A line without the segment queues for the loop's owner, with its text as `missing`, and adds a drift line.
  - The old `NEEDS_ONLY_RE` and `ONLY_RE` fallbacks stay, so a line they matched keeps its named person.
  - `/loop-prove`'s SKILL.md gives the segment in its UNPROVEN step and in its evidence-line example.
- **Fact kind** (per D76):
  - A missing fact for a §3 row that agents may not read, or whose command is `TODO(owner)`, becomes a `fact`
    item, provided some unfinished concern's state is `unknown` because of it, or is blocked on a need whose proof
    environment it is.
  - Its detail carries `fact`, `error`, `supplied_by`, `concerns` and `command` (the `/loop-status` re-run).
  - The schema gains `fact_detail`, and `queue_kind` gains `fact`.
- **The invariant** (per D77):
  - After the queue and "Agents can start" are built, every concern that is neither done nor parked is checked. It
    counts as covered when it has a queue item, when "Agents can start" has an entry for it, or when it is blocked
    on a need that is covered.
  - Prove entries whose every unproven claim has a person-waiting item are removed from "Agents can start".
  - A concern that is still uncovered gets a `stuck` item. Its `stuck_detail` carries the concern, its state,
    its reason and `next`. The schema gains `stuck`.
  - `QUEUE_ORDER` places `fact` and `stuck` after `proof`.
- **App types** (per D1): regenerate `app/src/api/status.gen.ts`, add the two labels to `KIND_LABELS`, and add
  the two kinds to `READ_ONLY_KINDS` in `queue.ts`, and give each a summary line in `InboxScreen.tsx`'s
  `itemSummary` (per D3), so app CI on main stays green. Their cards are
  `app-owner-cards`.
- **Tests:** a fixture world reproduces today's case, with prose UNPROVEN lines, an unreadable row with
  dependants and quiet `TODO(owner)` rows, and expects the queue described in C1 to C3.

Rollback: revert the PR, and redeploy staging/status from the commit before it. The queue is derived on every
read, so no stored data changes. Evidence lines already written with the segment keep reading as plain text.

## Decisions

| # | Decision | Decided by, date | Closes |
| --- | --- | --- | --- |
| D1 | The schema change, the regenerated `status.gen.ts`, and the two new kinds' labels and read-only entries in `queue.ts` land in this concern's PR, because app CI fails main otherwise. The cards' bodies are `app-owner-cards`'. | agent, from `.github/workflows/app.yml` and `queue.ts`'s `Record<QueueKind, string>`, 2026-10-28 | — |
| D2 | D74's `<who>` also accepts `agent`, for a gap an agent can close alone, such as a rerun: it queues nothing, and the proof stays in Agents can start. A line without the segment still waits on the loop's owner (per D75), so `/loop-prove` ends every UNPROVEN line with one or the other. | Juan, 2026-10-28 | Raised by this concern's build: `test_a_proof_item_needs_something_only_a_person_has` expects such a gap to stay agent work |
| D3 | This concern's `touches` also cover `app/src/features/inbox/InboxScreen.tsx`, whose `itemSummary` switches over every kind and fails `npm run typecheck` once the types are regenerated; the two kinds get one summary line each there, so app CI stays green (per D1). They also cover `app/src/features/inbox/__tests__/queue.test.ts`, which pins the list of read-only kinds; `app-owner-cards` shares that folder, but it needs this concern, so the two are built one after the other. | agent, from `tsc --noEmit` on this concern's branch, 2026-10-28 | Raised by this concern's build |

## Questions

| # | Question | Blocks | Default if unanswered |
| --- | --- | --- | --- |

## Evidence

- 2026-10-28 · C1 · HOLDS · rung 1 · staging/status @363ed2a · One GET of the served document (200, 189,416 B, as_of 16:55:46 UTC, read with the owner's token, on the owner's yes): its queue holds a proof item for each of the 8 claims whose latest line is UNPROVEN (status-service C1, C2; environments C2, C3; notifications C1, C2, C3; runner-dispatch C3), each with `waits_on` jugonzal, and 8 drift lines for those lines lacking `· needs <who>: <what>`. The notifier's first tick on the new revision (15:42:29 UTC) pushed 7 of them; notifications C1's mark dates from 2026-10-25, so it was not pushed again
- 2026-10-28 · C2 · HOLDS · rung 1 · staging/status @363ed2a · Same read: one `fact` item, `fact/staging/app`, waiting on jugonzal with the 9 concerns that are unknown on it (app-agents, app-clients, app-documents, app-environments, app-inbox, app-loops-board, app-shell, app-threads, latest-release), and none for the four `production/*` rows nothing ships to. The notifier pushed it at 15:42:29 UTC
- 2026-10-28 · C3 · HOLDS · rung 1 · staging/status @363ed2a · Same read: the queue holds 9 items where 41597ff's held 0, none of kind `stuck`. None of the 15 entries in `agents_can_start` is a proof whose claims still to prove all wait on a person: notifications, whose C1 to C3 all do, is gone from it, while environments, runner-dispatch and status-service stay for their claims no item waits on

## Shipped
