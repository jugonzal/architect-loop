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
| staging | TODO(owner): GCP, not built yet (command-center/D8) | TODO(owner) | no | owner | TODO(owner): each service's `/version` URL | TODO(owner) |
| production | TODO(owner): GCP, not built yet (command-center/D8) | TODO(owner) | no | owner | TODO(owner): each service's `/version` URL | TODO(owner) |

List environments from lowest to highest: a concern is proven on each one on its way to its `ships-to`.
`/loop-status` runs the served-commit command for every environment agents may read. Without that command it
cannot tell a merged concern from a shipped one, so fill it in first. What an environment serves is what the
command prints, not what a document says.

The command center has more than one deployable (status service, runner, thread store, mobile app). Give each its
own row here once it exists, with a `/version` URL that the status service can read over HTTP
(command-center/D9). A mobile build reports the commit it was built from.

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
| Deploy | TODO(owner) | owner only (§2) |
| Verify a deploy | TODO(owner) | agents may run it against any environment they can read |

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
