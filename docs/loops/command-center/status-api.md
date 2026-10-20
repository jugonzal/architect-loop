---
needs: [one-repository]
touches: [plugin/skills/loop-status/scripts/status.schema.json, tests/test_status_schema.py, tests/fixtures/status/]
effects: []
ships-to: main
---
# The status script, the service and the app agree on one versioned JSON schema

## Done when

- **C1** A versioned JSON Schema describes the status of a project. That covers its loops; its concerns, each
  with its derived state, the reason, and the facts the state came from; queue items, each with its kind (one of
  the seven in D34), what it unblocks, and who it waits on, and for a question its options and recommendation
  when the file records them (per D33); and "agents can start now". Prove: the schema validates the fixture
  documents and rejects a document missing a required field, in CI on main.
- **C2** The fixture documents cover every state in the derivation table, plus `unknown`, so the app can be
  built and tested without a running service. Prove: a test that lists the states found in the fixtures against
  the table in `loop-status` SKILL.md, in CI on main.

## Design

### Where we are

- Nothing exists. The repository's tests use `python3 -m unittest` with only the standard library
  (`scripts/check.sh`, line 75), so validation in tests must not need `jsonschema` from PyPI. The tests keep a
  small validator of their own (per D1). (Corrected 2026-10-20: this said line 60. The independence check that
  ee7be83 added moved the call, checked with `grep -n` on main @d4312cb.)
- Verified 2026-10-20 (`plugin/skills/loop-status/SKILL.md`, step 6): the queue has seven kinds of item, not the
  four this concern first listed (per command-center/D34).

### Approach

A contract concern, designed and built first (per D15): the schema lives beside the script, and the script's
`--json` output carries `schema_version`. It is keyed by project (per D18). Every concern's state is one of the
derivation's states (per D5) plus a `reason` string and an `inputs` object. Queue items carry `waits_on` (one
person) and `visible_to` (the loop's members), which `addressed-to-people` fills (per D10, D15). Until then they
may be empty. Queue items carry one of D34's seven kinds. A question item carries its options, each with its
consequence, and its recommendation, as `question-options` defines them, or none for a question written before
the format (per D33). The schema fixes the fields, so this concern does not need `question-options`. The app
generates its TypeScript types from the schema in the same commit (per D13, D15).

The tests validate with a small standard-library validator for the subset of JSON Schema the schema uses: `type`,
`required`, `enum`, `properties`, `items` and `$ref` (per D1). The schema uses nothing outside that subset.

## Decisions

| # | Decision | Decided by, date | Closes |
| --- | --- | --- | --- |
| D1 | The tests validate the schema with a small standard-library validator, for the subset of JSON Schema the schema uses, inside the existing `check`. There is no `jsonschema` dependency and no second CI job. | Juan, 2026-10-20 | How to validate without PyPI |

## Questions

| # | Question | Blocks | Default if unanswered |
| --- | --- | --- | --- |

## Evidence

## Shipped
