---
needs: [one-repository]
touches: [plugin/skills/loop-status/scripts/status.schema.json, tests/test_status_schema.py, tests/fixtures/status/]
effects: []
ships-to: main
---
# The status script, the service and the app agree on one versioned JSON schema

## Done when

- **C1** A versioned JSON Schema describes the status of a project. That covers its loops; its concerns, each
  with its derived state, the reason, and the facts the state came from; queue items, each with its kind
  (question, review, ship, record), what it unblocks, and who it waits on; and "agents can start now". Prove: the
  schema validates the fixture documents and rejects a document missing a required field, in CI on main.
- **C2** The fixture documents cover every state in the derivation table, plus `unknown`, so the app can be
  built and tested without a running service. Prove: a test that lists the states found in the fixtures against
  the table in `loop-status` SKILL.md, in CI on main.

## Design

### Where we are

- Nothing exists. The repository's tests use `python3 -m unittest` with only the standard library
  (`scripts/check.sh`, line 60), so validation in tests must not need `jsonschema` from PyPI.
  Either keep a small validator in the test, or validate in the app's CI instead.

### Approach

A contract concern, designed and built first (per D15): the schema lives beside the script, and the script's
`--json` output carries `schema_version`. It is keyed by project (per D18). Every concern's state is one of the
derivation's states (per D5) plus a `reason` string and an `inputs` object. Queue items carry `waits_on` (one
person) and `visible_to` (the loop's members), which `addressed-to-people` fills (per D10, D15). Until then they
may be empty. The app generates its TypeScript types from the schema in the same commit (per D13, D15).

## Decisions

| # | Decision | Decided by, date | Closes |
| --- | --- | --- | --- |

## Questions

| # | Question | Blocks | Default if unanswered |
| --- | --- | --- | --- |

## Evidence

## Shipped
