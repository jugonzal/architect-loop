---
needs: [one-repository, app-shell, status-api, queue-items, session-runner, addressed-to-people]
touches: [app/src/app/(tabs)/inbox/, app/src/features/inbox/]
effects: [starting sessions that cost money, each card's dispatch naming the person as sponsor with its budget shown before it starts (spending)]
ships-to: production
---
# The owner can finish a question, review, ship or record card from the phone's inbox

## Done when

- **C1** "Needs you" lists every item waiting on the signed-in person, sorted by how many concerns it unblocks.
  Each one is a card: question (options and recommendation, none pre-selected), review (evidence before the
  diff), ship (the brief and its manual steps) or record (the proposed text). The other three kinds of item
  show read-only, with the command to run (per D34). Items that wait on someone else
  show read-only to the loop's members (per D10). Prove: app tests against the status fixtures, in CI on main,
  and a recording on a device against staging.
- **C2** Finishing a card dispatches the matching skill through the runner, with the person as sponsor, and its
  write lands in `docs/loops/`. Answering a question records a `D#` through `/loop-design`. "Deployed" runs
  `/loop-ship` verification. Approving a record runs `/loop-status`'s record step. Prove: one card of each kind on
  a test loop, with the resulting commits, on staging.
- ~~**C3** A push notification goes out only for blocking items waiting on that person, and everything else waits
  for the digest. Prove: two accounts with one blocking and one non-blocking item, on staging.~~ Moved to
  `notifications` C2 (per D35).

## Design

### Where we are

- The design's Inbox, Question and Review artboards are the reference (per D4). Their supply-reality and
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

### Approach

Screens follow the Inbox, Question and Review artboards. Merging a PR stays on the forge: the review card links
to it, because the app never merges (`LOOP.md` §2). A question card's recommendation is never pre-selected, and
the decision records who tapped it.

## Decisions

| # | Decision | Decided by, date | Closes |
| --- | --- | --- | --- |

## Questions

| # | Question | Blocks | Default if unanswered |
| --- | --- | --- | --- |
| Q1 | Where does a dispatched `/loop-ship` leave its brief, so the ship card can show it? Options: post it to the loop's thread (needs `threads`); open a draft promotion PR that holds it; have the skill write it to a file under `docs/`. | C1 (ship card) | Post it to the loop's thread, and the card shows the latest brief there |
| Q2 | When does a person see a record's text, when the record step merges its own PR after the yes? Options: the session opens the PR and waits, and the card shows the diff and approving merges it; approve first and read the text after; the card shows only what will be recorded. | C1 (record card), C2 | The session opens the PR without merging. The card shows its diff, and approving dispatches the merge under `LOOP.md` §2.1 |
| Q3 | How does a dispatched `/loop-design` take the person's answer as theirs? Options: pass `Q<n> → <option>` and the sponsor as the skill's arguments, and the skill records only that; open a session thread where the skill asks and the person answers; change loop-design to read an answer file. | C2 (question card) | Pass the answer as arguments. The skill records it as decided by the sponsor and asks nothing else, which may need a change to loop-design |
| Q4 | Is proposal §5's typed reason for gated questions in this loop? Options: yes, and the reason goes in the D# notes; no, a later loop adds it. | C1 (question card) | Yes, and the reason goes in the decision's notes |

## Evidence

## Shipped
