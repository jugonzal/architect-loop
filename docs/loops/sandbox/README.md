---
parked: D6
---
# Staging proofs have somewhere safe to dispatch real sessions

**Intent.** Several concerns of `command-center` are proven on staging by dispatching a real session on "a test
concern" and watching what it does (command-center/D61). That needs concerns that exist for being worked on, whose
build PRs are closed unmerged and whose design and record writes land only under `docs/loops/sandbox/`. This loop
holds them, so a staging proof never dispatches on real work. It is wanted now because
`command-center/session-narration` C1 and C2 are the first staging proofs that cannot run without it.
**Non-goals.** Real work, production, a second repository, and anything the sandbox's sessions merge to `main`.

## Goals

- **G1** Every staging proof of `command-center` that names a test concern can dispatch on a concern in this
  loop, and what those sessions leave behind is contained. Prove: list the pull requests of sessions dispatched on
  `sandbox/*` concerns, all closed unmerged, and `git log origin/main` shows no commit from them outside
  `docs/loops/sandbox/`, on staging.
- **G2** A concern here can declare an effect on a gate that only the sandbox crosses, held by a second signed-in
  person, so that `command-center` G2 can be proven. Prove: the app, signed in as that person on staging, shows
  the card in their inbox and not in the owner's (per command-center/D58, D62).

## Relations

- **command-center**: relates. Its concerns `session-narration`, `session-runner`, `runner-dispatch`, `threads`,
  `app-threads`, `app-inbox`, `status-service` and goal G2 prove themselves on concerns here (per
  command-center/D61). Nothing in `command-center` needs this loop to build, and this loop edits none of its files.
  The paths here (`sandbox/`, `docs/loops/sandbox/`) overlap no `touches` there.
- **command-center/D58 and D62**: needs a decision. `gated-target` relies on how gates are keyed and on a person
  being a GitHub login.

## Where we are

- Verified (main @633cbe4, 2026-10-25): `docs/loops/` holds only `command-center`, so no test concern exists, and
  a dispatch on staging/runner has nothing safe to target.
- Verified (`LOOP.md` §2): every gate's holder is `jugonzal`. A gate held by a second person does not exist yet,
  and adding one changes `LOOP.md`, which only the owner merges.
- Verified (`services/runner/runner/dispatch.py` on main @c4895ff, 2026-10-25): the runner never reads `parked`.
  It refuses a dispatch only when the concern is not on `main` (`unknown-concern`, line 155), or the sponsor is not a
  collaborator on the repository (`not-a-collaborator`, line 96). So parking this loop does not stop a dispatch
  (per D1), and the second person must also be invited to `jugonzal/architect-loop` as a collaborator.
- Verified (`plugin/skills/loop-status/scripts/addressing.py`): who sees an item comes from the README's `owner:`
  and `members:` front matter. This loop has neither, so no third signed-in member can be shown the card yet.
- Assumed: concerns that never merge would stay open in `/loop-status` for good. Parking avoids it, and the board
  shows whether it does once a concern exists.

## Shared decisions

| # | Decision | Decided by, date | Notes |
| --- | --- | --- | --- |
| ~~D1~~ | ~~The loop is parked, so its concerns stay off the owner's queue and the ready list. Parking does not stop a dispatch (the runner never reads it).~~ superseded by D5, 2026-10-26 | Juan, 2026-10-25 | Closes Q3 |
| D2 | `gated-target` crosses a new gate key `sandbox`. A PR will propose it in `LOOP.md` §2 with the second person as holder, and the owner's merge makes it real. No existing gate changes holder. | Juan, 2026-10-25 | Closes Q2 |
| D3 | A build target is used once. A merged build, even a reverted one, leaves its merge commit on `main`, so `/loop-status` derives the concern as shipped and `/loop-build` refuses it. The next staging build proof dispatches on a fresh target (`build-target-2`), and later ones add another. | Juan, 2026-10-25 | Adds `build-target-2` |
| D4 | A docs commit that adds or edits a sandbox target carries no `Concern:` trailer (per command-center/D45), because `/loop-status` counts any commit with it as the concern's work and derives the concern as shipped. `build-target-2` was lost that way, so `build-target-3` replaces it as the target. | agent, delegated by Juan, 2026-10-25 | Refines D3 |
| ~~D5~~ | ~~The loop is not parked while a staging proof dispatches on its concerns, and is parked again once that proof is recorded. The runner ignores `parked`, but the app's Agents tab lists only what `agents_can_start` offers, and the derivation leaves a parked loop's concerns out of it (`loop_status.py`, verified 2026-10-26), so a parked loop cannot be dispatched from the app.~~ superseded by D6, 2026-10-26 | Juan, 2026-10-26 | Supersedes D1 |
| D6 | The loop is parked again, so its concerns leave the owner's queue and the ready list. The staging proofs of `session-narration` and `narration-tests-milestone` are recorded, and the owner chose no further run for now. A parked loop cannot be dispatched from the app (verified 2026-10-26), so a later proof unparks it again with a new decision. | Juan, 2026-10-26 | Supersedes D5 |

## Questions

| # | Question | Blocks | Default if unanswered |
| --- | --- | --- | --- |
| Q1 | Who is the second person: which GitHub login, invited as a collaborator on the repository, signs in as the holder of the sandbox gate? (deferred by Juan, 2026-10-25: none for now) | `gated-target`, G2, D2's `LOOP.md` change | No second login, so `gated-target` cannot be dispatched, D2's key has no holder and G2 stays unproven |
| ~~Q2~~ | ~~Which gate key does `gated-target` cross, since §2's keys all name the owner as holder?~~ → D2 | | |
| ~~Q3~~ | ~~How do the sandbox's concerns show in `/loop-status`, given their PRs never merge?~~ → D1 | | |

**Q1 options**
- **A second GitHub account of the owner's**: no one else is involved and it is a real separate login, but it needs inviting as a collaborator (the runner refuses any other sponsor) and proves the routing, not a real colleague's phone. (recommended)
- **A collaborator**: proves the real thing, but needs them invited to the repository and the staging app.
- **A machine account**: easy to keep, but the app signs in with a person's GitHub login, so it may not sign in at all.

**Q2 options**
- **A new `sandbox` key in `LOOP.md` §2**: no real gate changes holder, but the owner has to merge a contract change first. (recommended)
- **Reuse an existing key**: no contract change, but a real gate then has a second holder in the sandbox only, which blurs it.

**Q3 options**
- **Park the loop**: keeps them off the owner's queue and the ready list, and the runner never reads `parked`, so dispatch still works (verified 2026-10-25). (recommended)
- **Leave them open**: dispatch always works, but they show as ready work until someone filters them out.
- **Give each an evidence line from its closed PR**: they could finish, but `LOOP.md` §6 ties every line to a commit on `main`, so it breaks that rule.

## Evidence

## Shipped
