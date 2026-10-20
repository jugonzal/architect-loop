---
needs: [one-repository]
touches: [services/threads/]
effects: [a Cloud SQL Postgres instance in the staging and production GCP projects (spending; cloud IAM), messages written by project members (production data: deleting or expiring them is gated), a GitHub webhook for pull request review comments (identity and access)]
ships-to: production
---
# Each loop, concern and agent session has a thread that project members can read, join and post to

## Done when

- **C1** Each loop, concern and session has one thread with a stable URL and a member list. A project member can
  read its whole history and post, and anyone else cannot read it. Prove: API tests with a member and a
  non-member, on staging.
- **C2** Nothing in a thread changes a loop's derived state. A message that looks like a decision is marked
  "record this?", and only the skill's write to the repository counts. Prove: post a decision-like message and
  check that the status service's answer is unchanged, on staging.
- **C3** Review comments on a concern's PR appear in that concern's thread within a minute (per D6). Prove: a
  review comment on a test PR, on staging.

## Design

### Where we are

- Nothing exists (2026-10-20).

### Approach

A Cloud Run API over Cloud SQL Postgres (per D6, D8), keyed by project (per D18). Membership is the repository's
collaborators. A thread holds messages, not facts (per D1). Wiping the store loses conversation, never a loop's
state (G4). Rollback: redeploy the previous revision. A schema migration on the thread store is a migration on
shared data, so the owner runs it.

## Decisions

| # | Decision | Decided by, date | Closes |
| --- | --- | --- | --- |

## Questions

| # | Question | Blocks | Default if unanswered |
| --- | --- | --- | --- |

## Evidence

## Shipped
