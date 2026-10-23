# LOOP.md

How the owner and agents work in this repository. A fixture for tests/test_addressing.py: only the parts that
loop_status.py and addressing.py read are filled in. Each gate in §2 names its key and its one holder, by GitHub
login. Store names no holder, and Money's holder is still the template's placeholder, so both wait on the owner.
Hardware is a key of this project's own.

## 1. Roles

- **Owner:** Ana (ana on GitHub). Sets goals, answers questions, and holds every gate in §2 that names no holder.
- **Agents:** plan, design, build, prove and record.

## 2. Gates: always stop for the owner

<!-- A guidance comment is never read: (key: comment; holder: nobody) -->

- **Never done by an agent, even after a yes** (the owner performs them), unless listed in §2.1:
  - **Merge** (key: merge; holder: ana): merging to `main`
  - **Deploy** (key: deploy; holder: ben): deploying or promoting to any shared environment
  - **Store** (key: store): submitting a build to a store or a beta channel
- **Done by an agent only after a per-action yes** (approval covers that one action, not the next one of its kind):
  - **Secrets** (key: secrets; holder: carla): creating, rotating, reading production values
  - **Infra** (key: infra; holder: @dan): DNS, certificates, firewall, cloud IAM
  - **Money** (key: money; holder: <login>): prices, billing, tax, payment-provider settings
  - **Hardware** (key: hardware; holder: erin): the test devices in the lab

### 2.1 Delegated actions

| Action | Scope | Granted by, date |
| --- | --- | --- |

## 3. Environments

| Environment | Where | Agents may read | Agents may write | Deployed by | Served commit: a command that prints its SHA | Verify with |
| --- | --- | --- | --- | --- | --- | --- |
| main | main | yes | no | owner | `git rev-parse origin/main` | |
| staging | staging | yes | no | owner | `sh served.sh staging` | |
| production | production | yes | no | owner | `sh served.sh production` | |
