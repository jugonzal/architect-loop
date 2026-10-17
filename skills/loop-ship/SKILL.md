---
name: loop-ship
description: Prepare a deploy to a shared environment (staging, production) for the owner to perform, then check what the environment actually serves afterwards. Finds every merged concern the environment does not serve yet, writes a brief (what goes out, proof so far, the manual steps the concerns declared as effects, risks, rollback, verify commands), stops for the owner, and after the deploy runs read-only verification and records a ship line in each concern. Use when work is merged and ready to go out, before a deploy, right after one, or when the owner says "ready to ship", "deploy to staging/prod", "what's going out", "check the deploy", or runs /loop-ship.
license: MIT
metadata:
  author: architect-loop
  version: "0.2"
---

# loop-ship

Make shipping a short, well-informed human act, then check that it really happened.

## Boundary

**Shipping belongs to the owner.** This skill never merges code, deploys, runs migrations against a shared
environment, changes secrets or flips production flags, even if it technically could and even if the owner says
yes in passing. It prepares, stops, and verifies. The only exception is an action listed in `LOOP.md` §2.1,
followed exactly as written and no further.

After a verified deploy it appends `ship` lines to the concerns' Evidence through a PR that changes only
`docs/loops/`, and merges that PR itself under `LOOP.md` §2.1 once `scripts/check_loop_pr.sh` from the
loop-status skill passes. It will pass only if the served commit is on `main`. If an environment serves
something that is not on `main` (a hotfix branch, say), that is a finding for the owner, not something to record.

**Without `LOOP.md`:** nothing is delegated. Ask the owner how each environment reports its served commit, leave
every PR for the owner, and mention `/loop-init` once.

## Steps

### Before: the brief

1. **Find what goes out.** Run `/loop-status`. Read the environment's served commit (`LOOP.md` §3), take the
   candidate (usually `origin/<main>`), and list every concern, across all loops, whose work is in
   `<served>..<candidate>`, plus any commits there that belong to no concern. If you cannot learn the served
   commit, say so; that is a finding in itself.

2. **Write the brief.** Put it in the promotion PR's body if the project ships through PRs, otherwise in chat:

   ```text
   Ship: <env> ← <sha>   (<n> concerns, <m> PRs)
   Concerns:  - <loop>/<concern>: <title> (#<pr>, …)
   Unowned:   - <commits on main that belong to no concern, if any>
   Proven:    <each concern's verdicts so far, with rung and where>; UNPROVEN claims listed
   Manual steps (owner), in order: <every effect the concerns declare: migrations, secrets, settings>
   Risks:     <what could break, who would notice, how fast>
   Rollback:  <exact steps; what does NOT roll back: data, sent messages, external state>
   Verify:    <commands to run after the deploy, and what each should print>
   ```

   The manual steps come from each concern's `effects`. A gate that appears in a PR but in no concern's
   `effects` is a finding: flag it.

3. **Flag anything that should block**: an UNPROVEN claim that matters on this environment, a contradicted
   concern in the batch, a migration without a rollback, an undeclared effect, a deploy script changed in the
   same batch as the code it deploys. Recommend splitting the batch when it would reduce the blast radius.

4. **Stop** and wait for the owner. Do not proceed on silence.

### After: verify what the environment serves

5. When the owner says it is deployed, **read the served commit** and check it is the one in the brief. Then
   **run the verify commands** from the brief and `LOOP.md` §3, read-only. Check what users depend on, not only
   a health endpoint: the served version, each concern's actual behaviour, TLS, background workers, and the logs
   for new errors since the deploy.

6. **Compare against the brief.** Report every difference plainly, with the command and its output. Do not
   redeploy or "fix it quickly": hand off to `/loop-diagnose`, and if users are affected, recommend a rollback to
   the owner.

7. **Record and hand off.** Append one line to the Evidence of each concern that shipped:
   `- YYYY-MM-DD · ship · verified · <env> @<served-sha> · <what was checked>` (or `FAILED`, with what failed), on a
   `docs/ship-<env>-<date>` branch. Open the PR and merge it as described in Boundary. Then hand off to `/loop-prove <loop>/<concern> <env>` for each
   claim that should now be proven there.

## Notes

- A deploy that succeeded is not a claim that holds. Step 5 exists because the two diverge, and `/loop-status`
  keeps "shipped" and "done" apart for the same reason.
- If verification needs something only the owner has (a real device, a store build, a vendor dashboard), list it
  as an owner check that says exactly what to look at.
