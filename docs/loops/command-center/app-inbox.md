---
needs: [one-repository, app-shell, status-api, session-runner, addressed-to-people]
touches: [app/src/app/(tabs)/inbox/, app/src/features/inbox/]
effects: [push notifications to real users]
ships-to: production
---
# The owner can finish a question, review, ship or record card from the phone's inbox

## Done when

- **C1** "Needs you" lists every item waiting on the signed-in person, sorted by how many concerns it unblocks.
  Each one is a card: question (options and recommendation, none pre-selected), review (evidence before the
  diff), ship (the brief and its manual steps) or record (the proposed text). Items that wait on someone else
  show read-only to the loop's members (per D10). Prove: app tests against the status fixtures, in CI on main,
  and a recording on a device against staging.
- **C2** Finishing a card dispatches the matching skill through the runner, with the person as sponsor, and its
  write lands in `docs/loops/`. Answering a question records a `D#` through `/loop-design`. "Deployed" runs
  `/loop-ship` verification. Approving a record runs `/loop-status`'s record step. Prove: one card of each kind on
  a test loop, with the resulting commits, on staging.
- **C3** A push notification goes out only for blocking items waiting on that person, and everything else waits
  for the digest. Prove: two accounts with one blocking and one non-blocking item, on staging.

## Design

### Where we are

- The design's Inbox, Question and Review artboards are the reference (per D4). Their supply-reality and
  objection cards, and the rule that comments must be answered before a merge, are out of this loop.

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

## Evidence

## Shipped
