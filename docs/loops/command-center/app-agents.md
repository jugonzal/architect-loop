---
needs: [one-repository, app-shell, session-runner, status-api]
touches: [app/src/app/(tabs)/agents/, app/src/features/agents/]
effects: [starting sessions that cost money: the person sees the estimate and the budget and confirms each start (spending)]
ships-to: production
---
# Anyone on the project can see every running agent, who sponsors it and what it costs

## Done when

- **C1** The Agents tab lists every running session with its skill, concern, sponsor, elapsed time, and spend
  against budget, refreshed within 10 seconds. A sponsor can stop their own session. Prove: two dispatched
  sessions and one stop, on staging.
- **C2** "Can start now" lists the concerns the status service marks as ready, shipped or stale, each with
  Start, an estimated cost, and a budget the person confirms. Start dispatches with them as sponsor. Prove: start
  one ready concern from a device, on staging.

## Design

### Approach

Follow the Agents artboard (per D4). Its "session slots" (a cap per sponsor) come from the runner. The cap's
value is a question for the runner's design, once the spike answers `session-runner` Q1.

## Decisions

| # | Decision | Decided by, date | Closes |
| --- | --- | --- | --- |

## Questions

| # | Question | Blocks | Default if unanswered |
| --- | --- | --- | --- |

## Evidence

## Shipped
