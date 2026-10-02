---
name: loop-promote
description: Prepare a promotion to a shared environment (staging, production) for the owner to perform, then check what the environment actually serves afterwards. Writes a promotion brief (what changes, proof so far, manual steps, risks, rollback, verify commands), stops for the owner, and after the owner deploys runs read-only verification, records the promotion in the proposal, and hands the remaining claims to loop-prove. Use when work is merged or ready to ship, before a deploy, right after one, or when the owner says "ready to ship", "deploy to staging/prod", "what's going out", "check the deploy", or runs /loop-promote.
license: MIT
metadata:
  author: architect-loop
  version: "0.1"
---

# loop-promote

Make promotion a short, well-informed human act, then check that it really happened.

## Boundary

**Promotion belongs to the owner.** This skill never merges to the main branch, deploys, runs
migrations against a shared environment, changes secrets or flips production flags, even if it
technically could and even if the owner says yes in passing. It prepares, stops, and verifies. The
only exception is an action listed in `LOOP.md` §2.1 (Delegated actions), followed exactly as written
and no further.

**Without `LOOP.md`:** nothing is delegated. Ask the owner how each environment reports its deployed
version, and mention `/loop-init` once.

## Steps

### Before: the promotion brief

1. **Collect what is going out.** Find the version the target environment serves (`LOOP.md` §3) and
   diff it against the candidate (`git log <deployed>..<candidate>`, merged PRs). If you cannot learn
   the deployed version, say so; that is a finding in itself.

2. **Write the brief.** Put it in the promotion PR's body if the project promotes through PRs,
   otherwise in chat, and always as a dated entry in each affected proposal's §11:

   ```text
   Promote: <env> ← <branch/sha>   (<n> PRs)
   Changes:  - #<pr> <outcome sentence>  …
   Proven:   <loop-prove verdicts, with rung>; UNPROVEN items listed
   Manual steps (owner): migrations, secrets, settings, in order
   Risks:    <what could break, who would notice, how fast>
   Rollback: <exact steps; what does NOT roll back: data, sent messages, external state>
   Verify:   <commands to run after the deploy, and what each should print>
   ```

3. **Flag anything that should block**: an UNPROVEN claim that matters, a migration without a
   rollback, a change that crosses a gate nobody approved, a deploy script changed in the same batch
   as the code it deploys. Recommend splitting when it would reduce the blast radius.

4. **Stop** and wait for the owner. Do not proceed on silence.

### After: verify what the environment serves

5. When the owner says it is deployed, **run the verify commands** from the brief and `LOOP.md` §3
   against the environment, read-only. Check what users depend on, not only a health endpoint: the
   version served, the feature's actual behaviour, TLS, background workers, and the logs for new
   errors since the deploy.

6. **Compare against the brief.** Report every difference plainly, with the command and its output.
   Do not redeploy or "fix it quickly": hand off to `/loop-diagnose`, and if users are affected,
   recommend a rollback to the owner.

7. **Record and hand off.** Mark the brief's §11 entry `verified YYYY-MM-DD` (or what failed), set
   each shipped step's Status to `on <env>, verified YYYY-MM-DD`, then hand the PR's "still to prove"
   items to `/loop-prove` (after-promotion pass). When those hold, `/loop-record` closes the turn.

## Notes

- A deploy that succeeded is not a feature that works. Step 5 exists because the two diverge.
- If verification needs something only the owner has (a real device, a store build, a vendor
  dashboard), list it as an owner check that says exactly what to look at.
