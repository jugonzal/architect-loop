# LOOP.md

How the owner and agents work in this repository. Every agent reads this before starting work.
Architect Loop, generation 2. Last reviewed: YYYY-MM-DD by <owner>.

## 1. Roles

- **Owner:** <name> (<GitHub login> on GitHub). Sets goals, answers questions, merges code, ships, and holds
  every gate in §2 that names no other holder.
- **Agents:** plan, design, build, prove and record. They build each concern on its own branch, in its own
  worktree, and open pull requests (§6). They never merge code to `<main>` and never deploy to a shared
  environment, unless §2.1 delegates that specific action.

## 2. Gates: always stop for the owner

An agent that reaches one of these stops, says exactly what it would do and why, and waits for an
explicit yes in the conversation. Each gate has a short key and one holder, by GitHub login: the person an item
that crosses it waits on. A gate with no holder waits on the loop's owner.

- **Never done by an agent, even after a yes** (the holder performs them), unless listed in §2.1:
  - **Merge** (key: merge; holder: <login>): merging to `<main>`
  - **Deploy** (key: deploy; holder: <login>): deploying or promoting to any shared environment
  - **Migration** (key: migration; holder: <login>): running migrations against shared data
  - **Release** (key: release; holder: <login>): releasing a version: a version bump, a tag, a package publish
  - **Store** (key: store; holder: <login>): submitting a build to an app store or a beta channel
- **Done by an agent only after a per-action yes** (approval covers that one action, not the next one of its kind):
  - **Money** (key: money; holder: <login>): prices, billing, tax, payment-provider settings
  - **Spending** (key: spending; holder: <login>): provisioning paid resources or starting paid sessions beyond
    what was already approved
  - **Identity** (key: identity; holder: <login>): auth providers, roles, admin grants, OAuth/SSO apps
  - **Secrets** (key: secrets; holder: <login>): creating, rotating, reading production values
  - **Legal** (key: legal; holder: <login>): privacy policy, terms, published pricing, store listings
  - **Infra** (key: infra; holder: <login>): DNS, certificates, firewall, cloud IAM
  - **Production data** (key: prod-data; holder: <login>): deleting or rewriting production data; expiring user
    content
  - **Send** (key: send; holder: <login>): sending anything to real users
  - <project-specific additions, each with its own key and holder>

A concern declares the gates it crosses in its `effects`, so they are visible before any work starts. Each effect
ends with the keys it crosses, as in `the API key rotated (the owner rotates it; gates: secrets)`, and a question
whose answer crosses a gate ends with `(gates: <key>)`. `/loop-status` sends each item to its gate's holder.

### 2.1 Delegated actions

Standing permissions the owner grants on purpose. Anything not listed here is not delegated.

| Action | Scope | Granted by, date |
| --- | --- | --- |
| Merge a loop-document PR: its base is `<main>`, every file it changes is under `docs/loops/`, every commit its new evidence lines cite is already on `<main>`, and its checks pass. Run loop-status's `scripts/check_loop_pr.sh` first; if it fails, leave the PR for the owner | `docs/loops/` only, never a PR that changes anything else | architect-loop default; delete this row to revoke |
| <e.g. merge to the `staging` branch, which CD deploys to staging> | <staging only> | <owner, YYYY-MM-DD> |

## 3. Environments

| Environment | Where | Agents may read | Agents may write | Deployed by | Served commit: a command that prints its SHA | Verify with |
| --- | --- | --- | --- | --- | --- | --- |
| main | the `<main>` branch | yes | `docs/loops/` only (§2.1) | owner, by merging | `git rev-parse origin/<main>` | CI on that commit |
| staging | `<host, URL, cluster or account>` | yes | no | owner | `<command or endpoint that prints the SHA>` | `<command>` |
| production | `<host, URL, cluster or account>` | yes | no | owner | `<command or endpoint that prints the SHA>` | `<command>` |

List environments from lowest to highest: a concern is proven on each one on its way to its `ships-to`.
`/loop-status` runs the served-commit command for every environment agents may read. Without that command it
cannot tell a merged concern from a shipped one, so fill it in first. What an environment serves is what the
command prints, not what a document says.

## 4. Commands

| Purpose | Command | Known quirks |
| --- | --- | --- |
| Unit tests | `<command>` | |
| Full suite | `<command>` | |
| Lint / types | `<command>` | |
| Smoke test (end to end, synthetic input) | `<command>` | the proof that the whole pipeline works |
| CI result for a commit | `<e.g. gh run list --commit <sha>>` | |
| Deploy | `<command>` | owner only (§2) |
| Verify a deploy | `<command>` | agents may run it against any environment they can read |

## 5. Where things live

- **Loops:** `docs/loops/<loop>/README.md`, plus one `<concern>.md` per concern. The loop skills track every
  folder here.
- **Proposals:** `docs/proposals/`, for people: free-form proposals and RFCs, generation 1 history, and loops
  that were abandoned or deprecated. Moving a loop here stops tracking it. The loop skills do not track this folder.
- **Runbooks:** `docs/runbooks/<topic>.md`, corrected after every real run.
- **Memory:** `docs/memory/<slug>.md`, shared by every person and agent tool. (Use an agent's private memory
  only for personal preferences; project facts go here.)
- **Reference docs** (API, config): `<path>`
- **Worktrees:** `<../<repo>-<concern> | the agent tool's own worktree isolation>`

## 6. Conventions

- **Branches.** A concern is built on `<loop>/<concern>`, in its own worktree, from an up-to-date `<main>`.
  Loop-document changes go on `docs/<loop>-<topic>`. Other work uses `feat/`, `fix/`, `perf/`, `chore/`, `docs/`.
- **Code and loop documents never share a pull request.** A code PR never changes `docs/loops/`. A
  loop-document PR changes nothing else, and only records what is already on `<main>`.
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
  `ship` line, cites a commit already on `<main>`. Only a spike's answer (`Q#`) may cite a branch.
- **No status lines.** Nothing under `docs/loops/` records whether something is claimed, built, merged,
  shipped or done. `/loop-status` derives it from git, pull requests, environments and evidence, every time.

## 7. Project traps

Facts that cost real time and would cost it again. Date each one.

- YYYY-MM-DD: <trap and how to avoid it>
