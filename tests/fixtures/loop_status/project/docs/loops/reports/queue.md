---
needs: [contract]
touches: [src/queue/]
effects: []
ships-to: staging
---
# Jobs wait in a durable queue and survive a restart

Row: shipped. Staging serves its merge, C1 has a current HOLDS there, and C2's latest line is UNPROVEN and names
something only the owner can supply, so it is a proof item.

## Done when

- **C1** A job queued before a restart runs after it. Prove: restart the queue with jobs pending, on staging.
- **C2** 10,000 queued jobs drain in under 10 minutes. Prove: a load run, on staging.

## Decisions

| # | Decision | Decided by, date | Closes |
| --- | --- | --- | --- |

## Questions

| # | Question | Blocks | Default if unanswered |
| --- | --- | --- | --- |

## Evidence

- 2026-10-15 · C1 · HOLDS · rung 1 · staging @{sha:queue-merge} · restarted the queue with 50 jobs pending; all 50 ran
- 2026-10-16 · C2 · UNPROVEN · rung 1 · staging @{sha:staging-build} · needs a 10,000-job load on staging, which only the owner can start

## Shipped
