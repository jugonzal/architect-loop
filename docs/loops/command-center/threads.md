---
needs: [one-repository]
touches: [services/threads/, .github/workflows/threads.yml]
effects: [a Cloud SQL Postgres instance in the staging and production GCP projects (spending; cloud IAM), messages written by project members (production data: deleting or expiring them is gated), threads' own read-only GitHub App with webhooks for pull request reviews and review comments (identity and access; per D27), its key and webhook secret in Secret Manager (secrets)]
ships-to: production
---
# Each loop, concern and agent session has a thread that project members can read, join and post to

## Done when

- **C1** Each loop, concern and session has one thread with a stable URL and a member list. A project member can
  read its whole history, post and watch it, and anyone else cannot read it. The runner posts to a session's
  thread as that session, labelled with its sponsor (per D28). The API is the one in
  `services/threads/openapi.yaml` (per D29). Prove: the API tests against `openapi.yaml`, in CI on main, then API
  tests with a member, a non-member and the runner's service identity, on staging.
- **C2** Nothing in a thread changes a loop's derived state. Any member can mark a message "record this?", no
  model classifies messages, and only the skill's write to the repository counts (per D36). Prove: mark a message
  and check that the status service's answer is unchanged, on staging.
- **C3** Review comments on a concern's PR appear in that concern's thread within a minute (per D6). Prove: a
  review comment on a test PR, on staging.

## Design

### Where we are

- Nothing exists (2026-10-20).

### Approach

A Cloud Run API over Cloud SQL Postgres (per D6, D8), keyed by project (per D18). Membership is the repository's
collaborators, checked with threads' own read-only GitHub App (per D27), and a caller is identified with
`GET /user` on their token (per D28). Each message has a kind: message, milestone or narration, so the app can
collapse a session thread to its milestones. `session-narration` and `app-threads` build on this API and change
nothing under `services/threads/` (per D29). Python 3.12, tests in `services/threads/tests/`, run by
`.github/workflows/threads.yml` (per D30), deployed by the convention in D32. A thread holds messages, not facts
(per D1). Wiping the store loses conversation, never a loop's state (G4). Rollback: redeploy the previous
revision. A schema migration on the thread store is a migration on shared data, so the owner runs it.

## Decisions

| # | Decision | Decided by, date | Closes |
| --- | --- | --- | --- |

## Questions

| # | Question | Blocks | Default if unanswered |
| --- | --- | --- | --- |

## Evidence

## Shipped
