# LOOP.md

How the owner and agents work in this repository. Every agent reads this before starting work.
Last reviewed: YYYY-MM-DD by <owner>.

## 1. Roles

- **Owner:** <name>. Sets goals, answers open questions, merges, promotes, and holds every gate in §2.
- **Agents:** draft proposals, build, prove, diagnose and record. They commit on their own branches
  and open pull requests (§6). They never merge to `<main>` and never deploy to a shared environment,
  unless §2.1 delegates that specific action.

## 2. Gates: always stop for the owner

An agent that reaches one of these stops, says exactly what it would do and why, and waits for an
explicit yes in the conversation.

- **Never done by an agent, even after a yes** (the owner performs them), unless listed in §2.1:
  merging to `<main>`; deploying or promoting to any shared environment; running migrations against
  shared data.
- **Done by an agent only after a per-action yes** (approval covers that one action, not the next one of its kind):
  - Money: prices, billing, tax, payment-provider settings
  - Identity and access: auth providers, roles, admin grants, OAuth/SSO apps
  - Secrets: creating, rotating, reading production values
  - Legal and public text: privacy policy, terms, published pricing, store listings
  - DNS, certificates, firewall, cloud IAM
  - Deleting or rewriting production data; expiring user content
  - Sending anything to real users
  - <project-specific additions>

### 2.1 Delegated actions

Standing permissions the owner grants on purpose. Anything not listed here is not delegated.

| Action | Scope | Granted by, date |
| --- | --- | --- |
| <e.g. merge to `staging` branch, which CD deploys to staging> | <staging only> | <owner, YYYY-MM-DD> |

## 3. Environments

| Environment | Where | Agents may read | Agents may write | Deployed by | Deployed version: how to see it | Verify with |
| --- | --- | --- | --- | --- | --- | --- |
| local | laptop / containers | yes | yes | anyone | `git rev-parse HEAD` | `<command>` |
| staging | `<host, URL, cluster or account>` | yes | no | owner | `<command or endpoint>` | `<command>` |
| production | `<host, URL, cluster or account>` | yes | no | owner | `<command or endpoint>` | `<command>` |

The deployed state of an environment is what the environment serves, not what a document says.
Check it there before writing it down.

## 4. Commands

| Purpose | Command | Known quirks |
| --- | --- | --- |
| Unit tests | `<command>` | |
| Full suite | `<command>` | |
| Lint / types | `<command>` | |
| Smoke test (end to end, synthetic input) | `<command>` | the proof that the whole pipeline works |
| Deploy | `<command>` | owner only (§2) |
| Verify a deploy | `<command>` | agents may run it against any environment they can read |

## 5. Where things live

- Proposals: `docs/proposals/<slug>.md`: living documents, one per initiative, updated in place
- Runbooks: `docs/runbooks/<topic>.md`: corrected after every real run
- Memory: `docs/memory/<slug>.md`, shared by every person and agent tool. (Use an agent's private
  memory only for personal preferences; project facts go here.)
- Reference docs (API, config): `<path>`

## 6. Conventions

- **Branches and commits.** Agents commit only on their own branch, never on `<main>`: `feat/`,
  `fix/`, `perf/`, `chore/` for code, `docs/` for documentation-only changes. Pull requests: <yes,
  every change | only for code; docs may be pushed by the owner directly>.
- **Commit subjects** state the outcome as a sentence in the imperative, readable in a changelog:
  "Stop retrying failed uploads forever", not "upload fix".
- **Commit bodies** carry the reasoning and the evidence: what was wrong, how it was measured or
  reproduced, what was ruled out. A correction says what the earlier text or commit got wrong.
- **PR bodies** cite the proposal section they implement, say how the change was proven, and list
  what is still to prove on a real environment.
- **Numbering.** Decisions `D#`, open questions `Q#`, goals and gates `G#`, weak assumptions `A#`,
  plan steps `Step n`. Numbers are never reused or renumbered. Superseded items are struck through
  with a pointer to their replacement.
- **Proposal Status.** The first line under the title is `**Status:** <state> — <date>. <one sentence>`.

  | State | Meaning | Set by |
  | --- | --- | --- |
  | Proposed | Written, not yet decided | `loop-frame` |
  | Accepted | Blocking questions answered; the plan may be built | `loop-decide` |
  | In progress | At least one step built or promoted | `loop-build`, `loop-record` |
  | Done | All goals met, with evidence | `loop-record` |
  | Parked | Deliberately paused; says what would unpark it | owner |
  | Superseded | Replaced; links the replacement | `loop-frame`, owner |

  `loop-reconcile` may correct any Status line that does not match reality. Every Status change is
  verified against the environment or `<main>` first.
- **Plan step status** (inside the proposal): `not started` → `in progress on <branch> (#PR)` →
  `built, merged #PR` → `on <environment>, verified YYYY-MM-DD` → `done`. A step's latest proof
  verdict is recorded next to it.

## 7. Project traps

Facts that cost real time and would cost it again. Date each one.

- YYYY-MM-DD: <trap and how to avoid it>
