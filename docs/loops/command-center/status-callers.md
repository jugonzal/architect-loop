---
needs: []
touches: [services/status/status/identity.py, services/status/status/app.py, services/status/status/config.py, services/status/tests/test_callers.py, services/status/service.json, services/status/openapi.yaml]
effects: [the notifier's service account trusted by staging's status service through its manifest (per command-center/D66; the owner deploys it; gates: deploy)]
ships-to: staging/status
---
# A service the status service trusts can read the status document with its own Cloud Run identity

## Done when

- **C1** The status service answers a Google ID token for a service account its manifest trusts, with its own URL
  as the audience, with the same document a member gets, and refuses with 401 a token from any other account, for
  another audience, expired, or not signed by Google. A person's GitHub token works as before. Prove: the tests
  in `services/status/tests/test_callers.py`, by CI on main; then on staging/status, an ID token for the
  notifier's identity and one for another service account (`gcloud auth print-identity-token
  --impersonate-service-account=<account> --audiences=<the status URL>`, which needs the owner's credentials).

## Design

### Where we are

- **Verified** (`services/status/status/app.py` on main @603742a, 2026-10-24): `get_status` names the caller with
  `access.login()` on a GitHub token and then checks collaborator access, so a service identity is refused.
- **Verified** (`services/threads/threads/identity.py` and `config.py` on main @603742a, 2026-10-24): threads checks
  the runner's Google ID token against Google's keys, the issuer, its own URL as the audience, the expiry, and a
  list of trusted service accounts, with the keys' URL configurable so the local harness can sign its own.
- `status-service` is merged and not proven on staging yet. Per command-center/D51 it is not in `needs`: this
  concern builds on its code on main, and its staging proof waits until staging/status serves both.
- `app-served` shares `service.json` and `openapi.yaml` and needs this concern, so the two are never built at once.

### Approach

Per command-center/D66, D28 and D32: a `services/status/status/identity.py` that checks a Google ID token the way
threads does, configured by the status service's own URL as the audience, the trusted service accounts and the
keys' URL, all settings in `services/status/service.json` (per D46). `app.py` tries a bearer token as an ID token
only when its trust is configured and the token is a JWT, and otherwise as a GitHub token, as today. A trusted
identity skips the collaborator check, since it is no person, and gets the whole document. `openapi.yaml`
documents the second credential. Staging trusts `notify@<project>`. Rollback: redeploy the previous revision, which
trusts no service.

## Decisions

| # | Decision | Decided by, date | Closes |
| --- | --- | --- | --- |

## Questions

| # | Question | Blocks | Default if unanswered |
| --- | --- | --- | --- |

## Evidence

- 2026-10-25 · C1 · HOLDS · rung 1 · staging/status @633cbe4 · The status service's request log shows `architect-loop-notify` reading `/projects/jugonzal/architect-loop/status` with 200 on each of the notifier's first 3 ticks (13:44:00 to 13:46:05 UTC), and the notifier logged each read `ok=True` as `notify@loops-512401.iam.gserviceaccount.com`. On the same service an unsigned JWT naming `notify@` with the right audience got 401, and so did no token. Departure from Prove: no Google-signed token for another service account was tried, since minting one needs the owner's credentials; that refusal, and the wrong-audience and expired cases, rest on `test_callers.py` in CI

## Shipped

Shipped 2026-10-27. The status service accepts a Google ID token for a service account its manifest trusts
(jugonzal/architect-loop#66, merge bf2bea1, commit 4d8aad2) and staging/status serves it (`/version` answers
633cbe4, which contains the merge). The notifier's identity `notify@loops-512401.iam.gserviceaccount.com` reads the
status document with 200 on each of its first 3 ticks (C1 HOLDS, rung 1, 2026-10-25), and an unsigned JWT and no
token get 401.

Departures from the design: none in the approach. C1's Prove asked for a Google-signed token from another service
account on staging, which needs the owner's credentials, so that refusal and the wrong-audience and expired cases
rest on `test_callers.py` in CI.

Learned: the notifier's own scheduled reads were the cheapest proof of the trusted path, with no impersonation needed.
