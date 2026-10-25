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
- Assumed: a loop's concerns that never merge stay open in `/loop-status` for good, since their PRs are closed
  unmerged. Check by reading the board once a concern exists (Q3).

## Shared decisions

| # | Decision | Decided by, date | Notes |
| --- | --- | --- | --- |

## Questions

| # | Question | Blocks | Default if unanswered |
| --- | --- | --- | --- |
| Q1 | Who is the second person: which GitHub login signs in as the holder of the sandbox gate? | `gated-target`, G2 | No second login, so `gated-target` cannot be dispatched and G2 stays unproven |
| Q2 | Which gate key does `gated-target` cross, since §2's keys all name the owner as holder? | `gated-target`, G2 | The proposed key `sandbox`, which `addressing.py` reads as drift until `LOOP.md` §2 defines it |
| Q3 | How do the sandbox's concerns show in `/loop-status`, given their PRs never merge? | G1 | Left as open backlog, which shows them as work agents may start |

**Q1 options**
- **A second GitHub account of the owner's**: no one else is involved and it is a real separate login, but it proves the routing and not a real colleague's phone. (recommended)
- **A collaborator**: proves the real thing, but needs them invited to the repository and the staging app.
- **A machine account**: easy to keep, but the app signs in with a person's GitHub login, so it may not sign in at all.

**Q2 options**
- **A new `sandbox` key in `LOOP.md` §2**: no real gate changes holder, but the owner has to merge a contract change first. (recommended)
- **Reuse an existing key**: no contract change, but a real gate then has a second holder in the sandbox only, which blurs it.

**Q3 options**
- **Park the loop**: keeps them off the owner's queue and the ready list, but the runner may refuse a parked concern, which is not verified.
- **Leave them open**: dispatch always works, but they show as ready work until someone filters them out. (recommended)
- **Give each an evidence line from its closed PR**: they could finish, but `LOOP.md` §6 ties every line to a commit on `main`, so it breaks that rule.

## Evidence

## Shipped
