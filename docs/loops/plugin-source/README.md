---
owner: jugonzal
members: []
---
# A runner can work on a project that does not release the skills

**Intent.** Today the runner takes the skills from the project it works on: it reads that project's tags to find
the release, and extracts `plugin/` from the project's own clone. That is true of one repository only, the one
that releases the plugin. A runner set to any other project refuses every dispatch, because that project has no
release tag and no `plugin/`. This loop lets the runner take the skills' release from the plugin's repository,
whichever project it serves, so the command center can run a loop in a project other than its own. Why now: the
owner wants to point a deployment at a second, real project, and this is the one change in code that stands in
the way.

**Non-goals.**
- A runner that serves more than one project at once. One runner still serves one project (per
  command-center/D18).
- Any change to the app, or to the status, threads or notify services. They already key everything by project.
- Pointing staging, or any environment, at another project. That is the owner's configuration and deploy, done
  after this loop.
- Keeping a project's name out of the committed manifests. A private project needs that, and it is its own loop.
- Releasing the plugin from more than one repository, or running skills that are not a tagged release (per
  command-center/D17).

## Goals

- **G1** A runner whose project is not the plugin's repository estimates, dispatches and runs a session with the
  newest release of the skills, though its project has no release tag and no `plugin/`. Prove: on local/runner,
  with the harness's fake GitHub serving a project with no tags beside a plugin repository that has them, a
  dispatched session whose job reports the tag it ran.
- **G2** A runner whose project is the plugin's repository behaves as it does today, with nothing new to set.
  Prove: on staging/runner, an estimate that names the newest tag and one dispatched session that runs it.

## Relations

- **command-center**: relates. This loop changes `services/runner/`, which that loop built and still owns
  concerns in (`latest-release`, `needs-proven`, `session-waits`, `question-options` and others list the same
  files). None has an open pull request on 2026-11-14, so nothing collides today; a build here checks again
  before it starts, and this loop edits none of that loop's files.
- **command-center/D17**: needs a decision. `plugin-repository` relies on a session running a tagged release
  extracted outside the clone, never the clone's own `plugin/`. It is in that concern's `needs`.
- **command-center/D68**: in tension, raised here as Q2. D68 says a start runs "the newest release tag on the
  project's main". Once the project and the plugin's repository can differ, the tag is the plugin repository's.
  This loop does not edit D68.
- **command-center/D18**: relates. D18 keeps phase 1 to one project and says more can be added later. This loop
  adds none; it removes the assumption that the one project is the plugin's home.
- **sandbox**: relates. G2's staging proof dispatches one session, and it does so on a sandbox concern, as that
  loop exists for. Whether the sandbox is parked at that time is that loop's decision.

## Where we are

- Verified (`services/runner/runner/github.py` on main @9a687e9, 2026-11-14): `release_exists` and
  `latest_release` read `/repos/<project>/git/ref/tags/<tag>` and `/repos/<project>/tags`, with the runner's
  GitHub App token for the project.
- Verified (`services/runner/runner/workspace.py` on main @9a687e9, 2026-11-14): `_install_release` checks the
  tag in the project's clone and runs `git archive refs/tags/<tag> plugin` there. A project without the tag ends
  the session with "is not a tag of".
- Verified (`services/runner/runner/dispatch.py` on main @9a687e9, 2026-11-14): a dispatch whose tag
  `release_exists` does not find is refused with `unknown-release`, and the estimate's `plugin_release` is
  `latest_release`, which is null for a project with no release tag. The app then says the project has no
  release of the skills and starts nothing.
- Verified (`services/runner/runner/github.py`, `AppAuth.token`, on main @9a687e9, 2026-11-14): each installation
  token is minted for the project's repository only.
- Assumed: the plugin's repository is public, so its tags and its release can be read without the runner's App
  being installed on it. Q1 checks it.
- Missing: any setting that names the plugin's repository, and a second repository in the local harness's fake
  GitHub.

## Shared decisions

| # | Decision | Decided by, date | Notes |
| --- | --- | --- | --- |

## Questions

| # | Question | Blocks | Default if unanswered |
| --- | --- | --- | --- |
| Q1 | With what credentials does the runner read the plugin repository's tags and fetch its release, when its GitHub App is installed only on the project? | `plugin-repository`, G1 | Without credentials, until a proof shows GitHub's rate limit refusing a read |
| Q2 | How is command-center/D68's "the project's main" reconciled with a plugin repository that is not the project? | `plugin-repository` C1 | This loop reads D68's "the project" as the plugin's repository wherever the two differ, and says so in a shared decision here |

**Q1 options**
- **No credentials**: nothing to install or grant, and it works for any project, but GitHub allows an anonymous
  caller 60 API reads an hour for each address, which Cloud Run shares with others.
- **The runner's App token for the project**: a higher limit with nothing new to install, if GitHub lets a token
  scoped to one repository read another public one. A spike settles that. (recommended)
- **Install the runner's App on the plugin's repository too**: certain to work, but it only works where the App's
  owner controls both repositories, and it adds an identity step for each new account.

**Q2 options**
- **A new decision in command-center supersedes D68**: one place says where the release comes from, at the cost of
  a `/loop-design` pass on that loop. (recommended)
- **A shared decision here refines it**: no edit to the other loop, but a reader of D68 alone gets the old rule.

## Evidence

## Shipped
