---
needs: [command-center/D17]
touches: [services/runner/runner/config.py, services/runner/runner/github.py, services/runner/runner/dispatch.py, services/runner/runner/workspace.py, services/runner/runner/main.py, services/runner/README.md, services/runner/tests/, scripts/local/]
effects: [staging/runner redeployed so that it serves this concern (the owner deploys it; gates: deploy), one dispatched session on a sandbox concern for the staging proof of C3 at about $0.25 (the owner starts it; gates: spending)]
ships-to: staging/runner
---
# The runner takes the skills' release from the plugin's repository, whichever project it serves

## Done when

- **C1** On a runner whose plugin repository is set to a repository other than its project, the estimate names
  the newest release tag of the plugin repository, a dispatch that names a tag the plugin repository lacks is
  refused with `unknown-release`, and the project's own tags change neither answer. Prove: the runner's tests, by
  CI on main; then on local/runner, against a fake GitHub that serves a project with no tags beside a plugin
  repository with two.
- **C2** A session's job on such a runner runs the skills extracted from the plugin repository at the dispatched
  tag, read-only and outside the clone, and the project's clone gains no tag and no file from the plugin
  repository. Prove: the runner's tests, by CI on main; then on local/runner, one dispatched session whose job
  reports the tag it ran, with the clone's tags and tree listed after it.
- **C3** A runner with no plugin repository set, serving the plugin's own repository, answers the same estimate
  and refuses the same dispatches as before this concern. Prove: the runner's existing tests unchanged, by CI on
  main; then on staging/runner, an estimate that names the newest tag and one dispatched session that runs it.

## Design

### Where we are

### Options

### Approach

## Decisions

| # | Decision | Decided by, date | Closes |
| --- | --- | --- | --- |

## Questions

| # | Question | Blocks | Default if unanswered |
| --- | --- | --- | --- |

## Evidence

## Shipped
