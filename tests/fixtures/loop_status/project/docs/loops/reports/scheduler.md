---
needs: [queue]
touches: [src/scheduler/]
effects: [the SMTP password in production's secret store (the owner sets it; gates: secrets)]
ships-to: production
---
# Reports scheduled for a time are queued at that time

Row: merged. Its work is on main, and production serves an older commit, so a ship item for deploy, and one for
the secrets gate its effect crosses, with the effect as its manual step.

## Done when

- **C1** A report scheduled for 09:00 is queued between 09:00 and 09:01. Prove: 20 schedules, on staging and
  production.

## Decisions

| # | Decision | Decided by, date | Closes |
| --- | --- | --- | --- |

## Questions

| # | Question | Blocks | Default if unanswered |
| --- | --- | --- | --- |

## Evidence

- 2026-10-19 · C1 · HOLDS · rung 1 · staging @{sha:staging-build} · 20 of 20 schedules queued within 40 s of their time

## Shipped
