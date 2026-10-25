---
needs: []
touches: [services/runner/runner/api.py, services/runner/runner/dispatch.py, services/runner/runner/github.py, services/runner/openapi.yaml, services/runner/tests/fakes.py, services/runner/tests/test_api_contract.py, services/runner/tests/test_dispatch.py, services/runner/tests/test_github.py, app/src/api/runner.gen.ts, app/src/features/agents/, app/src/features/inbox/, app/src/features/threads/]
effects: []
ships-to: staging/app
---
# A session started from the app runs the newest release of the skills

## Done when

- **C1** The runner's estimate names the newest release tag on the project's main, and a dispatch that names a
  tag not on main is still refused. Prove: the runner's tests, by CI on main; then on local/runner, against the
  fake GitHub's tags (per command-center/D53).
- **C2** Each start sheet (Agents, a Needs you card, a thread's record sheet) shows the release the estimate named
  and dispatches exactly that tag, and no screen holds a release of its own. Prove: the app's tests, by CI on main;
  then on staging/app, a start from each sheet whose session reports the newest tag.

## Design

### Where we are

- **Verified** (`services/runner/runner/dispatch.py` on main @603742a, 2026-10-24): `plugin_release` is required,
  must look like `vX.Y.Z`, and is refused with `unknown-release` unless it is a tag on the project's main
  (`github.release_exists`). `GET /estimates` returns the skill, the model and the estimate, and no release.
- **Verified** (`app/src/features/` on main @603742a, 2026-10-24): `agents/starts.ts` and `inbox/dispatch.ts` each
  pin `PLUGIN_RELEASE = 'v0.4.0'`, and `threads/thread.ts` pins `SKILLS_RELEASE = 'v0.4.0'` as the record sheet's
  editable default. `v0.4.0` is the newest tag (`git tag -l`).
- `runner-dispatch`, `app-agents`, `app-inbox` and `app-threads` are merged and not proven on staging yet. Per
  command-center/D51 none is in `needs`: this concern builds on their code on main, and its staging proof waits
  until staging serves them.
- `session-narration` changes other files of the runner (`session.py`, `config.py`, `main.py`, `service.json`
  and its own test), so the two share no path.

### Approach

Per command-center/D68 and D17: the runner's GitHub client lists the project's tags on main and picks the highest
`vX.Y.Z`, and `GET /estimates` adds it as `plugin_release`. A dispatch still names its tag and is still checked
against main, so what the person was shown is what runs, even if a tag is cut in between. `openapi.yaml` documents
the field, and `app/src/api/runner.gen.ts` is regenerated with `app-clients`' generator. Each of the three screens
drops its constant, shows the tag its estimate named and sends it back. The thread's record sheet prefills its
release field with it. Rollback: redeploy the previous runner and ship the previous app build; the screens' old
pins still dispatch `v0.4.0`.

## Decisions

| # | Decision | Decided by, date | Closes |
| --- | --- | --- | --- |

## Questions

| # | Question | Blocks | Default if unanswered |
| --- | --- | --- | --- |

## Evidence

- 2026-10-25 · ship · verified · staging @633cbe4 · the owner ran `deploy.sh runner staging 633cbe4`; I then `served.sh https://runner-665570365697.us-east1.run.app/version 633cbe4` printed 633cbe477c987414bd151302c6a23728684f4e90 and exited 0, as did the threads (1eae0a3), status and notify reads. `gcloud run services describe runner` read back image tag 633cbe4, COMMIT_SHA 633cbe4, runtime identity runner@loops-512401, Ready True, and RUNNER_THREADS_URL https://threads-665570365697.us-east1.run.app; the `runner-session` job has the same image, COMMIT_SHA and RUNNER_THREADS_URL. The only WARNING in the last 2 hours was an unauthenticated GET /estimates (401) made while verifying. No session was dispatched, so the runner half of C1 (estimate naming the newest release) is not yet proven on staging; the app half ships to staging/app

## Shipped
