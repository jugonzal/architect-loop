---
needs: [reports/scheduler]
touches: [src/alerts/]
effects: []
ships-to: production
---
# A requester hears when a scheduled report is late

Row: ready, through a need that is met below its ships-to (command-center/D50). reports/scheduler is merged, not
done, since production does not serve it, but its one claim holds on staging at a commit on main, and nothing under
its touches has changed since.

## Done when

- **C1** A report that is not queued by 09:05 for 09:00 sends one alert. Prove: 5 late schedules, on production.

## Decisions

| # | Decision | Decided by, date | Closes |
| --- | --- | --- | --- |

## Questions

| # | Question | Blocks | Default if unanswered |
| --- | --- | --- | --- |

## Evidence

## Shipped
