---
needs: [one-repository]
touches: [services/threads/, .github/workflows/threads.yml]
effects: [a Cloud SQL Postgres instance in the staging and production GCP projects (spending; cloud IAM), messages written by project members (production data: deleting or expiring them is gated), threads' own read-only GitHub App with webhooks for pull request reviews and review comments (identity and access; per command-center/D27), its key and webhook secret in Secret Manager (secrets)]
ships-to: production/threads
---
# Each loop, concern and agent session has a thread that project members can read, join and post to

## Done when

- **C1** Each loop, concern and session has one thread with a stable URL and a member list. A project member can
  read its whole history, post and watch it, and anyone else cannot read it. The runner posts to a session's
  thread as that session, labelled with its sponsor (per command-center/D28). The API is the one in
  `services/threads/openapi.yaml` (per command-center/D29). Prove: the API tests against `openapi.yaml`, in CI on main, then API
  tests with a member, a non-member and the runner's service identity, on staging.
- **C2** Nothing in a thread changes a loop's derived state. Any member can mark a message "record this?", no
  model classifies messages, and only the skill's write to the repository counts (per command-center/D36). Prove: mark a message
  and check that the status service's answer is unchanged, on staging.
- **C3** Review comments on a concern's PR appear in that concern's thread within a minute (per command-center/D6). Prove: a
  review comment on a test PR, on staging.

## Design

### Where we are

- Nothing exists (2026-10-20). (Superseded by the next bullet, 2026-10-20.)
- Verified 2026-10-20 (main @a9fde89, PR #21): the API in `services/threads/openapi.yaml` (20 operations, paths
  under `/projects/{owner}/{repo}/`, per command-center/D48), a Postgres store with its first migration in
  `services/threads/migrations/`, run only by the owner with `python -m threads.migrate`, and 77 tests run by
  `threads.yml` against a throwaway Postgres. The service reads its commit from `COMMIT_SHA` (per command-center/D47). It starts
  unconfigured, answering only `/version` until its settings, secrets and Cloud SQL instance are attached, which
  `service-manifests` does from its manifest (per command-center/D46). The runner may post only to session threads.

### Approach

A Cloud Run API over Cloud SQL Postgres (per command-center/D6, D8), keyed by project (per command-center/D18). Membership is the repository's
collaborators, checked with threads' own read-only GitHub App (per command-center/D27), and a caller is identified with
`GET /user` on their token (per command-center/D28). Each message has a kind: message, milestone or narration, so the app can
collapse a session thread to its milestones. `session-narration` and `app-threads` build on this API and change
nothing under `services/threads/` (per command-center/D29). Python 3.12, tests in `services/threads/tests/`, run by
`.github/workflows/threads.yml` (per command-center/D30), deployed by the convention in command-center/D32. A thread holds messages, not facts
(per command-center/D1). Wiping the store loses conversation, never a loop's state (G4). Its deploy config is `services/threads/service.json`, from
`service-manifests` (per command-center/D46). Rollback: redeploy the previous
revision. A schema migration on the thread store is a migration on shared data, so the owner runs it.

## Decisions

| # | Decision | Decided by, date | Closes |
| --- | --- | --- | --- |
| D1 | Every collaborator on the repository, at any permission level, is a member: they can read, post and watch. Acting on an item is still per command-center/D10. | Juan, 2026-10-20 | Confirms PR #21 |
| D2 | Membership answers are cached for 60 seconds, so a person whose access is revoked keeps it for up to a minute. | Juan, 2026-10-20 | Confirms PR #21 |
| D3 | A session thread's sponsor is fixed by the runner's first post to it. A later post naming another sponsor is refused (409). | Juan, 2026-10-20 | Confirms PR #21 |
| D4 | People post only messages of kind `message`. `milestone` and `narration` are a session's. | Juan, 2026-10-20 | Confirms PR #21 |
| D5 | A review comment is mirrored to a concern's thread only when the PR body has a `Concern:` line, not from the head branch's name. | Juan, 2026-10-20 | Confirms PR #21 |
| D6 | Threads stay thin. Thread names are not checked against `docs/loops/`, and a "record this?" mark has no taken-up or dismissed state. | Juan, 2026-10-20 | Confirms PR #21 |

## Questions

| # | Question | Blocks | Default if unanswered |
| --- | --- | --- | --- |

## Evidence

## Shipped
