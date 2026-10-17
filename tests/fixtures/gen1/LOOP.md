# LOOP.md

How the owner and agents work in this repository.
Last reviewed: 2026-09-01 by the owner.

## 1. Roles

- **Owner:** the owner. Merges and promotes.
- **Agents:** draft proposals, build, prove and record.

## 2. Gates: always stop for the owner

- Merging to `main`; deploying to any shared environment.

### 2.1 Delegated actions

| Action | Scope | Granted by, date |
| --- | --- | --- |
| None | | owner, 2026-09-01 |

## 3. Environments

| Environment | Where | Agents may read | Agents may write | Deployed by | Deployed version: how to see it | Verify with |
| --- | --- | --- | --- | --- | --- | --- |
| local | laptop | yes | yes | anyone | `git rev-parse HEAD` | `make test` |
| staging | `staging.example.test` | yes | no | owner | `<command or endpoint>` | `make verify` |
| production | `example.test` | yes | no | owner | `<command or endpoint>` | `make verify` |

## 4. Commands

| Purpose | Command | Known quirks |
| --- | --- | --- |
| Unit tests | `make test` | |

## 5. Where things live

- Proposals: `docs/proposals/<slug>.md`: living documents, one per initiative, updated in place
- Runbooks: `docs/runbooks/<topic>.md`

## 6. Conventions

- **Numbering.** Decisions `D#`, open questions `Q#`, goals and gates `G#`, plan steps `Step n`.
- **Proposal Status.** The first line under the title is `**Status:** <state> — <date>. <one sentence>`.

  | State | Meaning | Set by |
  | --- | --- | --- |
  | Proposed | Written, not yet decided | `loop-frame` |
  | In progress | At least one step built or promoted | `loop-build` |
  | Done | All goals met, with evidence | `loop-record` |

- **Plan step status** (inside the proposal): `not started` → `in progress on <branch> (#PR)` →
  `built, merged #PR` → `on <environment>, verified YYYY-MM-DD` → `done`.

## 7. Project traps

- 2026-09-02: the export cache survives a deploy.
