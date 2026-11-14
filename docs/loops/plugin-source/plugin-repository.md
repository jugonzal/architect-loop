---
needs: [command-center/D17, plugin-source/D1, plugin-source/D3]
touches: [services/runner/runner/config.py, services/runner/runner/plugin.py, services/runner/runner/github.py, services/runner/runner/dispatch.py, services/runner/runner/workspace.py, services/runner/runner/main.py, services/runner/README.md, services/runner/tests/, scripts/local/, docs/runbooks/local.md]
effects: [staging/runner redeployed so that it serves this concern (the owner deploys it; gates: deploy), one dispatched session on a sandbox concern for the staging proof of C3 at an estimated $0.25 (the owner starts it; gates: spending)]
ships-to: staging/runner
---
# The runner takes the skills' release from the plugin's repository, whichever project it serves

## Done when

- **C1** On a runner whose plugin repository is not its project, the estimate names the newest release tag of the
  plugin repository, a dispatch that names a tag the plugin repository lacks is refused with `unknown-release`,
  the project's own tags change neither answer, and the runner sends GitHub's REST API no request about tags (per
  D1). Prove: the runner's tests, by CI on main; then on local/runner, against a fake GitHub that serves a project
  with no tags beside a plugin repository with two, with the fake's list of calls read after it.
- **C2** A session's job on such a runner runs the skills extracted from the plugin repository at the dispatched
  tag, read-only and outside the clone, and the project's clone gains no tag and no file from the plugin
  repository. Prove: the runner's tests, by CI on main; then on local/runner, one dispatched session whose job
  reports the tag it ran, with the clone's tags and tree listed after it.
- **C3** A runner with no plugin repository set takes the release from `jugonzal/architect-loop` (per D3), by the
  same code as any other (per D1 below). Serving that repository, it names the same newest tag and refuses the
  same unknown tag as before this concern. Prove: the runner's tests, by CI on main; then on staging/runner, an
  estimate that names the newest tag `git ls-remote` shows, a dispatch of a made-up tag refused with
  `unknown-release`, and one dispatched session that runs the newest tag.

## Design

### Where we are

- Verified (`services/runner/runner/github.py` on main @ff263cc, 2026-11-14): `RestGitHub.release_exists` and
  `latest_release` are REST reads of the project (`/repos/<project>/git/ref/tags/<tag>`, `/repos/<project>/tags`)
  with the App's token, and `newest_release` picks the newest `vX.Y.Z` among names. Both are in the `GitHub`
  protocol the dispatcher takes.
- Verified (`services/runner/runner/dispatch.py` on main @ff263cc, 2026-11-14): `dispatch` calls `release_exists`
  and `estimate` calls `latest_release`, each through `_github`, which turns a `GitHubError` into 502
  `upstream-failed`.
- Verified (`services/runner/runner/workspace.py` on main @ff263cc, 2026-11-14): `_install_release(clone, root,
  tag)` verifies `refs/tags/<tag>` in the project's clone, runs `git archive` of `plugin` there, extracts it to
  `<root>/release/<tag>/plugin` and makes it read-only. `Workspace` is given the clone's URL, and a credential
  helper that answers with the App's token.
- Verified (`services/runner/runner/config.py` on main @ff263cc, 2026-11-14): `RUNNER_GIT_URL` overrides the
  project's clone URL, which is how the local harness points the runner at its fake. Nothing names a plugin
  repository.
- Verified (`scripts/local/harness.py` and `scripts/local/fakes/server.py` on main @ff263cc, 2026-11-14): the
  fake GitHub serves one repository, the project's, over REST and git's smart HTTP. The harness pushes HEAD as
  `main` with every release tag into it, and its smoke test expects a REST read of `/git/ref/tags/<release>`.
- Verified (`git ls-remote --tags --refs https://github.com/jugonzal/architect-loop.git 'v*'`, 2026-11-14, no
  credentials): it lists the release tags, `v0.7.0` the newest.

### Options

Settled by the loop's D1 and D3 and by D1 below. The options weighed are under the loop README's Q1.

### Approach

1. **Config.** `RUNNER_PLUGIN_REPOSITORY` (`plugin_repository`, default `jugonzal/architect-loop`, per D3), checked
   as `owner/repo`, and `RUNNER_PLUGIN_GIT_URL` (`plugin_git_url`), which overrides its git URL as `RUNNER_GIT_URL`
   does the project's, for the local harness. The URL is `https://github.com/<plugin repository>.git` otherwise.
   `services/runner/README.md`'s settings gain both.
2. **`plugin.py`: the plugin's source.** A small class given the git URL. `latest_release()` runs
   `git ls-remote --tags --refs <url> 'v*'` and picks with `newest_release`. `release_exists(tag)` asks
   `ls-remote` for `refs/tags/<tag>`. `fetch(tag, into)` makes an empty repository at `into` and runs
   `git fetch --depth 1 <url> refs/tags/<tag>:refs/tags/<tag>`. Every command runs with `GIT_TERMINAL_PROMPT=0`,
   no credential helper and a timeout of 10 seconds for `ls-remote` and 60 for `fetch`, so a repository that is
   private, missing or slow fails instead of waiting (per D1 of the loop).
3. **Dispatcher.** It takes the plugin source beside `github` and asks it, not `github`, for `release_exists` and
   `latest_release`. A failure there is the same 502 `upstream-failed`, and its message names the plugin
   repository. `unknown-release` names the plugin repository too. `release_exists` and `latest_release` leave
   `RestGitHub` and the `GitHub` protocol.
4. **Workspace.** `_install_release` fetches the tag with the plugin source into `<root>/release/<tag>/source`,
   outside the clone, archives `plugin` from there, and extracts and locks it as now. The project's clone is not
   read or written for it (C2). A tag the plugin repository lacks, or one with no
   `plugin/.claude-plugin/plugin.json`, ends the session as now, before the model runs, so it spends nothing.
5. **One path** (per D1 below). The runner on the plugin's own repository runs the same code: nothing compares the
   two repositories.
6. **Local harness.** The fake GitHub serves a second repository over git's smart HTTP. The harness pushes HEAD's
   tree with every release tag into that one, pushes the project's `main` with no tags, and sets
   `RUNNER_PLUGIN_REPOSITORY` and `RUNNER_PLUGIN_GIT_URL`. So the harness always runs the case where the two
   differ, and its smoke test expects the session's release and no REST read of tags. `docs/runbooks/local.md`
   says so.

**Who decides what runs.** A session runs whatever the plugin repository's tag holds, with the project's App
token and the runner's API key. That was already true of the project's own tags. The setting lives in the
runner's manifest, which only the owner deploys.

**Failure.** GitHub or the plugin repository down: estimates and dispatches answer 502 and no session starts. A
session already dispatched ends at its install step with the reason in its record.

**Rollback.** Revert the pull request and redeploy the previous commit. Nothing is stored or migrated, and a
session already running keeps the release it extracted.

**Proof order.** C1 and C2 on CI and then local/runner, where nothing is gated. C3 on staging/runner after the
owner's deploy, with one dispatched session, which is this concern's two effects.

## Decisions

| # | Decision | Decided by, date | Closes |
| --- | --- | --- | --- |
| D1 | One path always: the runner takes the release through the plugin's source even when the plugin repository is its own project. Staging's release no longer comes from the session's clone, and staging's proof exercises the code another project runs. | Juan, 2026-11-14 | |

## Questions

| # | Question | Blocks | Default if unanswered |
| --- | --- | --- | --- |

## Evidence

## Shipped
