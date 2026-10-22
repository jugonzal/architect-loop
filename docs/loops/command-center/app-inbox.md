---
needs: [app-shell, status-api, queue-items, addressed-to-people, runner-dispatch, session-narration]
touches: [app/src/app/(tabs)/inbox/, app/src/features/inbox/]
effects: [starting sessions that cost money, each card's dispatch naming the person as sponsor with its budget shown before it starts (spending)]
ships-to: production/app
---
# The owner can finish a question, review, ship or record card from the phone's inbox

## Done when

- **C1** "Needs you" lists every item waiting on the signed-in person, sorted by how many concerns it unblocks.
  Each one is a card: question (options and recommendation, none pre-selected), review (evidence before the
  diff), ship (the brief and its manual steps) or record (the proposed text). The other three kinds of item
  show read-only, with the command to run (per command-center/D34). Items that wait on someone else
  show read-only to the loop's members (per command-center/D10). Prove: app tests against the status fixtures, in CI on main,
  and a recording on a device against staging.
- **C2** Finishing a card dispatches the matching skill through the runner, with the person as sponsor, and its
  write lands in `docs/loops/`. Answering a question records a `D#` through `/loop-design`. "Deployed" runs
  `/loop-ship` verification. Approving a record runs `/loop-status`'s record step. The person answers a question
  in the dispatched session's thread (per D3). Prove: one card of each kind on
  a test loop, with the resulting commits, on staging.
- ~~**C3** A push notification goes out only for blocking items waiting on that person, and everything else waits
  for the digest. Prove: two accounts with one blocking and one non-blocking item, on staging.~~ Moved to
  `notifications` C2 (per command-center/D35).

## Design

### Where we are

- The design's Inbox, Question and Review artboards are the reference (per command-center/D4). Their supply-reality and
  objection cards, and the rule that comments must be answered before a merge, are out of this loop.
- Verified 2026-10-20 (`plugin/skills/loop-ship/SKILL.md` step 2): `/loop-ship` writes its brief in the promotion
  PR's body, or in chat when the project does not ship through PRs. Deploys here are commands the owner runs, not
  PRs, so a dispatched session has nowhere to leave the brief for the card yet (Q1).
- Verified 2026-10-20 (`plugin/skills/loop-status/SKILL.md`, "Record, on the owner's yes"): after the yes, the
  record step writes its PR and merges it itself under `LOOP.md` §2.1, so no one sees the text before it merges
  (Q2).
- Verified 2026-10-20 (`plugin/skills/loop-design/SKILL.md`, Boundary): decisions count only if the owner made them
  in the session's conversation, and the skill asks its questions one at a time. A dispatched session carries
  the answer only in its arguments (Q3).
- Proposal §5 (question card): a gated question needs a typed reason before it can be answered (Q4).
- Verified 2026-10-20 (the runner on main @a9fde89): a dispatch must name a concern and one of `loop-design`,
  `loop-build`, `loop-prove` and `loop-status`, so neither `/loop-ship` on an environment nor a loop's record step
  can be dispatched yet, and the runner keeps no session's final message. `runner-dispatch` C3 adds both (per D1,
  D2). Nothing in the runner posts to a thread yet; `session-narration` adds that and the relay of a member's
  reply into a running session (per D3).
- Verified 2026-10-20 (`status.schema.json` on main @a9fde89): a record item carries the proposed text and its
  path (`record_detail`), which is what the record card shows (per D2).

### Approach

Screens follow the Inbox, Question and Review artboards. Merging a PR stays on the forge: the review card links
to it, because the app never merges (`LOOP.md` §2). A question card's recommendation is never pre-selected, and
the decision records who tapped it.

- **Ship card** (per D1): it dispatches `/loop-ship <environment>` and shows the brief, which is that session's
  final report, as the runner serves it. "Deployed" dispatches `/loop-ship`'s verification the same way.
- **Record card** (per D2): it shows the record item's proposed text from the status document, and approving
  dispatches the record step, which writes and merges its own PR under `LOOP.md` §2.1, as from a terminal.
- **Question card** (per D3): it dispatches `/loop-design` on the question's concern or loop, and opens that
  session's thread, where the skill asks the question and the person answers. The decision is the person's because
  they gave it in the session's conversation, which reaches the session through `session-narration`'s relay.
- **Gated questions** (per D4): when a question item's `gate` is set, the card asks for a typed reason before it
  sends the answer, and the reason goes into the decision's notes.

## Decisions

| # | Decision | Decided by, date | Closes |
| --- | --- | --- | --- |
| D1 | A dispatched `/loop-ship`'s brief is that session's final report. The runner keeps each session's final message and serves it with the session, and the ship card shows it. No change to `loop-ship` or to threads. | Juan, 2026-10-20 | Q1 |
| D2 | The record card shows what will be recorded, from the record item in the status document. Approving dispatches the record step as it is, and it merges its own PR. The person approves the proposed text, not the PR's exact diff. No skill changes. | Juan, 2026-10-20 | Q2 |
| D3 | A dispatched `/loop-design` asks its question in the session's thread, and the person answers there. No skill changes, but the question card needs `session-narration`'s relay of a member's message into a running session (its C2). | Juan, 2026-10-20 | Q3 |
| D4 | A gated question needs a typed reason before it can be answered, and the reason goes in the decision's notes. | Juan, 2026-10-20 | Q4 |

## Questions

| # | Question | Blocks | Default if unanswered |
| --- | --- | --- | --- |
| ~~Q1~~ | ~~Where does a dispatched `/loop-ship` leave its brief, so the ship card can show it?~~ → D1 | | |
| ~~Q2~~ | ~~When does a person see a record's text, when the record step merges its own PR after the yes?~~ → D2 | | |
| ~~Q3~~ | ~~How does a dispatched `/loop-design` take the person's answer as theirs?~~ → D3 | | |
| ~~Q4~~ | ~~Is proposal §5's typed reason for gated questions in this loop?~~ → D4 | | |

## Evidence

## Shipped
