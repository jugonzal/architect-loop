---
needs: [one-repository, app-shell, threads, session-runner]
touches: [app/src/app/threads/, app/src/features/threads/]
effects: []
ships-to: production
---
# A project member can read and post in a concern's or a session's thread from the phone

## Done when

- **C1** The concern thread and the session thread show their history, members and who is watching. A member
  can post as themselves, and the session thread collapses narration to milestones. Prove: app tests against
  the threads API on staging, and a device check.
- **C2** Accepting a "record this?" offer on a decision-like message dispatches `/loop-design` through the runner,
  with the person as sponsor, and the `D#` lands in the loop's files. Prove: one recorded decision on a test loop,
  on staging.

## Design

### Approach

Follow the Session thread artboard (per D4), without its objection block, which belongs to a later loop.

## Decisions

| # | Decision | Decided by, date | Closes |
| --- | --- | --- | --- |

## Questions

| # | Question | Blocks | Default if unanswered |
| --- | --- | --- | --- |

## Evidence

## Shipped
