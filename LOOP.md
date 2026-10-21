# LOOP.md

How the owner and agents work in this repository. Every agent reads this before starting work.
Architect Loop, generation 2. Last reviewed: 2026-10-20 by Juan.

This repository holds the Architect Loop itself and the command center built on it. The skills and the method
docs are in `plugin/` and `docs/`. The command center (a status service, a runner, threads and a mobile app) is
planned in `docs/loops/command-center/`, from [docs/proposals/command-center.md](docs/proposals/command-center.md).
The two live together so that one pull request can change a format, its derivation and the screen that shows
it (command-center/D13).

## 1. Roles

- **Owner:** Juan (jugonzal on GitHub). Sets goals, answers questions, merges code, ships, releases the plugin,
  and holds every gate in §2.
- **Agents:** plan, design, build, prove and record. They build each concern on its own branch, in its own
  worktree, and open pull requests (§6). They never merge code to `main` and never deploy to a shared
  environment, unless §2.1 delegates that specific action.

## 2. Gates: always stop for the owner

An agent that reaches one of these stops, says exactly what it would do and why, and waits for an
explicit yes in the conversation.

- **Never done by an agent, even after a yes** (the owner performs them), unless listed in §2.1:
  - merging to `main`; deploying or promoting to any shared environment; running migrations against
    shared data
  - releasing the plugin: bumping the version in `plugin/.claude-plugin/plugin.json`, tagging a release, or
    changing what the marketplace in `.claude-plugin/marketplace.json` serves (command-center/D17). A pull
    request may propose a marketplace change, but the owner's merge is the release.
  - submitting a build to the App Store, Google Play, TestFlight or any other store or beta channel
- **Done by an agent only after a per-action yes** (approval covers that one action, not the next one of its kind):
  - Money: prices, billing, tax, payment-provider settings
  - Spending: starting hosted agent sessions or runner workers, or provisioning paid cloud resources (databases,
    push services, hosting), beyond what the owner has already approved for the current task. State the
    expected cost before asking.
  - Identity and access: auth providers, roles, admin grants, OAuth/SSO apps, forge (GitHub) app permissions
  - Secrets: creating, rotating, reading production values
  - Legal and public text: privacy policy, terms, published pricing, store listings
  - DNS, certificates, firewall, cloud IAM
  - Deleting or rewriting production data; expiring user content
  - Sending anything to real users, including push notifications and digests

Changes to the skills under `plugin/skills/` are ordinary concerns, built and reviewed like any code
(command-center/D17). They are not gated, but they must keep the skills standalone (§6).

A concern declares the gates it crosses in its `effects`, so they are visible before any work starts.

### 2.1 Delegated actions

Standing permissions the owner grants on purpose. Anything not listed here is not delegated.

| Action | Scope | Granted by, date |
| --- | --- | --- |
| Merge a loop-document PR: its base is `main`, every file it changes is under `docs/loops/`, every commit its new evidence lines cite is already on `main`, and its checks pass. Run loop-status's `scripts/check_loop_pr.sh` from the installed release first (§5); if it fails, leave the PR for the owner | `docs/loops/` only, never a PR that changes anything else | architect-loop default, confirmed by Juan, 2026-10-19; delete this row to revoke |

## 3. Environments

| Environment | Where | Agents may read | Agents may write | Deployed by | Served commit: a command that prints its SHA | Verify with |
| --- | --- | --- | --- | --- | --- | --- |
| main | the `main` branch of [jugonzal/architect-loop](https://github.com/jugonzal/architect-loop) | yes | `docs/loops/` only (§2.1) | owner, by merging | `git fetch -q origin && git rev-parse origin/main` | `gh run list --repo jugonzal/architect-loop --commit <sha>` (the `check` workflow) |
| staging/status | Cloud Run service `status`, us-east1, staging's GCP project | yes | no | owner: `sh scripts/gcp/deploy.sh status staging <sha>` | TODO(owner): `sh scripts/gcp/served.sh <URL>`, with the URL `bootstrap.sh staging` prints | `sh scripts/gcp/served.sh <URL> <sha>` |
| staging/runner | Cloud Run service `runner`, us-east1, staging's GCP project | yes | no | owner: `sh scripts/gcp/deploy.sh runner staging <sha>` | TODO(owner): `sh scripts/gcp/served.sh <URL>`, with the URL `bootstrap.sh staging` prints | `sh scripts/gcp/served.sh <URL> <sha>` |
| staging/threads | Cloud Run service `threads`, us-east1, staging's GCP project | yes | no | owner: `sh scripts/gcp/deploy.sh threads staging <sha>` | TODO(owner): `sh scripts/gcp/served.sh <URL>`, with the URL `bootstrap.sh staging` prints | `sh scripts/gcp/served.sh <URL> <sha>` |
| staging/notify | Cloud Run service `notify`, us-east1, staging's GCP project | yes | no | owner: `sh scripts/gcp/deploy.sh notify staging <sha>` | TODO(owner): `sh scripts/gcp/served.sh <URL>`, with the URL `bootstrap.sh staging` prints | `sh scripts/gcp/served.sh <URL> <sha>` |
| staging/app | EAS builds of profile `staging` in `app/eas.json`, installed from TestFlight and Google Play internal testing; they use staging's services | TODO(owner): no, until agents can read EAS builds, which needs an Expo login or `EXPO_TOKEN` | no | owner: from a clean checkout of a commit on `origin/main`, `cd app && eas build --profile staging --platform all`, then `eas submit --profile staging --platform all --latest` | `cd app && eas build:list --build-profile staging --status finished --limit 50 --json --non-interactive \| node src/shell/release/served.js staging` | the same command, with `<sha>` after `served.js staging` |
| production/status | Cloud Run service `status`, us-east1, production's GCP project | yes | no | owner: `sh scripts/gcp/deploy.sh status production <sha>` | TODO(owner): `sh scripts/gcp/served.sh <URL>`, with the URL `bootstrap.sh production` prints | `sh scripts/gcp/served.sh <URL> <sha>` |
| production/runner | Cloud Run service `runner`, us-east1, production's GCP project | yes | no | owner: `sh scripts/gcp/deploy.sh runner production <sha>` | TODO(owner): `sh scripts/gcp/served.sh <URL>`, with the URL `bootstrap.sh production` prints | `sh scripts/gcp/served.sh <URL> <sha>` |
| production/threads | Cloud Run service `threads`, us-east1, production's GCP project | yes | no | owner: `sh scripts/gcp/deploy.sh threads production <sha>` | TODO(owner): `sh scripts/gcp/served.sh <URL>`, with the URL `bootstrap.sh production` prints | `sh scripts/gcp/served.sh <URL> <sha>` |
| production/notify | Cloud Run service `notify`, us-east1, production's GCP project | yes | no | owner: `sh scripts/gcp/deploy.sh notify production <sha>` | TODO(owner): `sh scripts/gcp/served.sh <URL>`, with the URL `bootstrap.sh production` prints | `sh scripts/gcp/served.sh <URL> <sha>` |
| production/app | EAS builds of profile `production` in `app/eas.json`, installed from TestFlight and Google Play internal testing; they use production's services | TODO(owner): no, until agents can read EAS builds, which needs an Expo login or `EXPO_TOKEN` | no | owner: from a clean checkout of a commit on `origin/main`, `cd app && eas build --profile production --platform all`, then `eas submit --profile production --platform all --latest` | `cd app && eas build:list --build-profile production --status finished --limit 50 --json --non-interactive \| node src/shell/release/served.js production` | the same command, with `<sha>` after `served.js production` |

List environments from lowest to highest: a concern is proven on each one on its way to its `ships-to`.
`/loop-status` runs the served-commit command for every environment agents may read. Without that command it
cannot tell a merged concern from a shipped one, so fill it in first. What an environment serves is what the
command prints, not what a document says.

The command center has more than one deployable, so staging and production each have one row per service, named
`<environment>/<service>` after the service's folder in `services/` (command-center/environments). Each
environment is its own GCP project, named in `scripts/gcp/projects.txt` and created by `scripts/gcp/bootstrap.sh`
(§4). A service's served-commit command reads its unauthenticated `/version` at
`https://<service>-<project number>.us-east1.run.app/version`, Cloud Run's URL for it, which is also the URL the
status service reads over HTTP (command-center/D9, D32). A project's number exists only once the owner has run its
bootstrap, which prints each row's command; until then the rows say TODO(owner) and read as unknown. A service
not deployed yet answers 404 and reads as unknown too, which is true.

The app has one row per channel, `staging/app` and `production/app`, each named after the EAS build profile in
`app/eas.json` that makes its builds (command-center/D43). EAS records the commit each build was made from (its
`gitCommitHash`, the `git rev-parse HEAD` where `eas build` ran), and `app/eas.json` sets `cli.requireCommit`, so
EAS refuses to build uncommitted work and that commit describes the build. A row's command prints the commit that
the channel's latest finished iOS and Android builds were both made from; while they differ, or one platform has
no build yet, it fails and the channel reads as unknown. Reading EAS's build list needs an Expo login or
`EXPO_TOKEN`, and the rows have no URL for the status service to GET (command-center/D9), so until that changes
agents cannot read these rows and they read as unknown (TODO(owner)). The latest finished build is taken to be
the one testers get, so build a profile only to submit it.

The plugin is not an environment: a release is a tagged commit on `main` that the owner cuts (§2).

## 4. Commands

| Purpose | Command | Known quirks |
| --- | --- | --- |
| Unit tests | `python3 -m unittest discover -s tests -v` | standard library only; no packages to install |
| Full suite | `sh scripts/check.sh` | validates every skill, checks that the skills stand alone (§6), then runs the unit tests. `CHECK_SKIP_TESTS=1` skips the tests |
| Lint / types | `sh scripts/check.sh` | the same script; there is no separate linter yet |
| Smoke test (end to end, synthetic input) | TODO(owner) | the proof that the whole pipeline works |
| CI result for a commit | `gh run list --repo jugonzal/architect-loop --commit <sha>` | |
| Install the skills from a checkout | `sh scripts/install.sh --user`, or `--project <dir>` | copies `plugin/skills/loop-*` |
| Release the plugin | owner only (§2) | |
| Bootstrap an environment | `sh scripts/gcp/bootstrap.sh <staging\|production> --billing-account=<ID> --budget=<amount>` | owner only (§2: spending, cloud IAM). Idempotent: it prints each change, and a second run prints `0 changes`. Needs the project ID in `scripts/gcp/projects.txt`. See `docs/runbooks/deploy.md` |
| Deploy | `sh scripts/gcp/deploy.sh <service> <staging\|production> <sha>` | owner only (§2). Refuses a commit not on `origin/main`, builds that commit (not the working tree) for linux/amd64, and fails unless `/version` then answers it. `probe` deploys `scripts/gcp/probe/`. Roll back by deploying the previous commit. See `docs/runbooks/deploy.md` |
| Verify a deploy | `sh scripts/gcp/served.sh <the row's /version URL> <sha>` | needs no credentials, so agents may run it against any environment they can read. Prints the served commit, and exits 1 if it is not `<sha>` |
| App tests and types | `cd app && npm install --no-package-lock && npm test && npm run typecheck` | the app's own packages, not the root's; Node 20.19.4 or 22. `npm run check:status` fails when `app/src/api/status.gen.ts` no longer matches the status schema, and `npm run generate:status` rewrites it. CI runs these in `.github/workflows/app.yml` |
| Build and submit the app | `cd app && eas build --profile <staging\|production> --platform all`, then `eas submit --profile <staging\|production> --platform all --latest` | owner only (§2: store and beta submissions; it needs the Expo account). Build from a clean checkout of a commit on `origin/main`: `cli.requireCommit` refuses uncommitted work. A store build cannot be recalled: roll back by building and submitting the previous commit |

## 5. Where things live

- **Loops:** `docs/loops/<loop>/README.md`, plus one `<concern>.md` per concern. The loop skills track every
  folder here.
- **Proposals:** `docs/proposals/`, for people: free-form proposals and RFCs, generation 1 history, and loops
  that were abandoned or deprecated. Moving a loop here stops tracking it. The loop skills do not track this folder.
  `concerns-as-functions.md` is the proposal behind generation 2, and `command-center.md` is the founding proposal
  of the `command-center` loop.
- **Skills (source):** `plugin/skills/`, packaged with `plugin/.claude-plugin/plugin.json`. The marketplace serves
  `./plugin`, so installs ship nothing else (command-center/D16).
- **Skills (installed, to drive work):** an installed release, never the working tree (§7). Install it with
  `/plugin install architect-loop@architect-loop`, or `sh scripts/install.sh --user` from a checkout of a release
  tag.
- **Method docs:** `README.md` and `docs/*.md` (method, patterns, failure modes, adopting, upgrading).
- **Runbooks:** `docs/runbooks/<topic>.md`, corrected after every real run.
- **Environments:** `scripts/gcp/` creates the GCP projects and deploys to them, and `docs/runbooks/deploy.md`
  says how. The owner runs both (§2).
- **Memory:** `docs/memory/<slug>.md`, shared by every person and agent tool. (Use an agent's private memory
  only for personal preferences; project facts go here.)
- **Command center code:** `services/` and `app/`, once their concerns are built. Nothing in `plugin/` may refer
  to them (§6).
- **Worktrees:** the agent tool's own worktree isolation, or `../architect-loop-<concern>` beside the main checkout
  (inferred)

## 6. Conventions

- **The skills stand alone** (command-center/D14). Nothing under `plugin/` reads, calls or assumes the app or
  the services. The app and the services read only what the skills write to the repository. A loop always runs
  from a terminal with nothing else installed. `scripts/check.sh` fails on any reference to `app/` or
  `services/` under `plugin/`.
- **Branches.** A concern is built on `<loop>/<concern>`, in its own worktree, from an up-to-date `main`.
  Loop-document changes go on `docs/<loop>-<topic>`. Other work uses `feat/`, `fix/`, `perf/`, `chore/`, `docs/`.
- **Code and loop documents never share a pull request.** A code PR never changes `docs/loops/`. A
  loop-document PR changes nothing else, and only records what is already on `main`.
- **Concern trailer.** Every commit for a concern ends with `Concern: <loop>/<concern>`, and so does its PR body.
  That is how status finds the work.
- **Commit subjects** state the outcome as a sentence in the imperative, readable in a changelog:
  "Stop retrying failed uploads forever", not "upload fix".
- **Commit bodies** carry the reasoning and the evidence: what was wrong, how it was measured or
  reproduced, what was ruled out. A correction says what the earlier text or commit got wrong.
- **PR bodies** cite the concern, say how the change was proven before the merge, list its declared effects,
  and list what is still to prove and where.
- **Numbering.** In a loop's README: goals `G#`, shared decisions `D#`, questions `Q#`. In a concern: claims
  `C#`, decisions `D#`, questions `Q#`. From outside their file they are written `<loop>/D3` or
  `<loop>/<concern>/C2`. Numbers are never reused or renumbered, and superseded rows are struck through with a
  pointer to their replacement.
- **Evidence lines** are appended to the file whose claim they prove, never edited:
  `- YYYY-MM-DD · C1 · HOLDS · rung 1 · staging @<sha> · <evidence>`, or
  `- YYYY-MM-DD · ship · verified · staging @<sha> · <checks>`. Every line about a `C#` or `G#`, and every
  `ship` line, cites a commit already on `main`. Only a spike's answer (`Q#`) may cite a branch.
- **No status lines.** Nothing under `docs/loops/` records whether something is claimed, built, merged,
  shipped or done. `/loop-status` derives it from git, pull requests, environments and evidence, every time.

## 7. Project traps

Facts that cost real time and would cost it again. Date each one.

- 2026-10-20: Drive work with an installed release of the skills, never with `plugin/skills/` in the working
  tree you are editing. A session that loads the skills it is changing follows half-edited instructions, and its
  evidence no longer says which version of the method produced it (command-center/D17).
- 2026-10-20: `python3 -m unittest` runs `tests/test_layout.py`, which runs `scripts/check.sh`, which runs the
  unit tests. The test sets `CHECK_SKIP_TESTS=1` to break that loop. A new test that calls `check.sh` must do the
  same, or the suite recurses until it is killed. It cost a hung run while this layout was built.
