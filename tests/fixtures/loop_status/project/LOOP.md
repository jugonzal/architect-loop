# LOOP.md

How the owner and agents work in this repository. A fixture for tests/test_loop_status.py: only the parts that
loop_status.py reads are filled in.

## 1. Roles

- **Owner:** Ana (ana on the forge).

## 2. Gates: always stop for the owner

- **Done by an agent only after a per-action yes:**
  - Money: prices, billing, tax, payment-provider settings
  - Secrets: creating, rotating, reading production values

## 3. Environments

| Environment | Where | Agents may read | Agents may write | Deployed by | Served commit: a command that prints its SHA | Verify with |
| --- | --- | --- | --- | --- | --- | --- |
| main | the `main` branch | yes | `docs/loops/` only | owner, by merging | `git rev-parse origin/main` | the `check` workflow |
| staging | the staging host | yes | no | owner | `sh served.sh staging` | `sh served.sh staging` |
| production | the production host | yes | no | owner | `sh served.sh production` | `sh served.sh production` |
| sandbox | the sandbox host | yes | no | owner | TODO(owner): `sh served.sh <URL>` | |
| vault | the vault host | no | no | owner | `sh served.sh vault` | |

## 4. Commands

| Purpose | Command | Known quirks |
| --- | --- | --- |
| Unit tests | `python3 -m unittest` | |
