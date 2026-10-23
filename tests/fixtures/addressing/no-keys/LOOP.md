# LOOP.md

How the owner and agents work in this repository. A fixture for tests/test_addressing.py: a LOOP.md written before
gates had keys. Its §2 names its gates in plain words only, so every item waits on its loop's owner, and the board
says once that §2 names no keys.

## 1. Roles

- **Owner:** Ana (ana on GitHub). Sets goals, answers questions, merges code, ships, and holds every gate in §2.

## 2. Gates: always stop for the owner

- **Never done by an agent, even after a yes** (the owner performs them), unless listed in §2.1:
  merging to `main`; deploying or promoting to any shared environment; running migrations against
  shared data.
- **Done by an agent only after a per-action yes** (approval covers that one action, not the next one of its kind):
  - Money: prices, billing, tax, payment-provider settings
  - Secrets: creating, rotating, reading production values

## 3. Environments

| Environment | Where | Agents may read | Agents may write | Deployed by | Served commit: a command that prints its SHA | Verify with |
| --- | --- | --- | --- | --- | --- | --- |
| main | main | yes | no | owner | `git rev-parse origin/main` | |
| staging | staging | yes | no | owner | `sh served.sh staging` | |
| production | production | yes | no | owner | `sh served.sh production` | |
