---
needs: []
touches: [worker/]
effects: []
ships-to: staging
---
# Exports run in a worker and survive a restart

## Done when

- **C1** An export interrupted by a restart finishes once the worker is back. Prove: kill it mid-export, on
  staging.
- **C2** A finished export stays downloadable for as long as the owner was told. Prove: a test, in CI.

## Design

### Options

**Q2 options** outside the Questions section are prose, and are not read.

## Questions

| # | Question | Blocks | Default if unanswered |
| --- | --- | --- | --- |
| Q1 | Which queue? Options: the database table (no new service); a hosted queue (needs an account). | C1 (queue choice), C2 | The database table |
| Q2 | How long does a finished export stay downloadable? | C2 | 7 days |
| Q3 | Does a retried export keep its `id \| attempt` key, answered as `Q3 → <option>`? | | |

**Q2 options**

- **24 hours**: the least storage, but an owner who exports on a Friday has lost it by Monday.
- **7 days**: covers a weekend and a holiday, and storage grows by about a week of exports.
  (recommended)
- **Until the owner deletes it**: never lost, but storage grows without bound and needs its own clean-up
  job.

**Q3 options**
- **Yes**: retries are idempotent, so a crash mid-export never writes a row twice. (recommended)
- **No**: simpler keys, but a retry can write a second copy.

## Evidence

## Shipped
