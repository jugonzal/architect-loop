---
owner: ben
members: [ana, carla]
---
# Reports are generated in the background and emailed when ready

**Intent.** A fixture loop for tests/test_loop_status.py. It holds one concern for each row of the derivation
table, and for each definition under it. Commits are written `{sha:<name>}`, which the test replaces with the
commit of that name in the world it builds from world.json. Ben owns it and Ana and Carla are its members, so
its items wait on Ben, and Ana and Carla see them; LOOP.md §2 names no keys, so even gated items wait on Ben.

## Goals

- **G1** A report requested at 09:00 arrives by 09:05. Prove: 20 timed requests, on production.

## Relations

- None.

## Where we are

- A fixture.

## Shared decisions

| # | Decision | Decided by, date | Notes |
| --- | --- | --- | --- |
| D1 | One worker process renders each report, so no pool of workers is needed. | Ana, 2026-10-01 | |
| ~~D2~~ | ~~Reports are kept forever.~~ | Ana, 2026-10-02 | Superseded by D3, 2026-10-05 |
| D3 | Reports are kept until the retention question is answered. | Ana, 2026-10-05 | Supersedes D2 |

## Questions

| # | Question | Blocks | Default if unanswered |
| --- | --- | --- | --- |
| Q2 | How long are generated reports kept? (gates: prod-data) | | 90 days |

## Evidence

## Shipped
