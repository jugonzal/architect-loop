---
needs: [one-repository]
touches: [plugin/skills/loop-status/scripts/status.schema.json, tests/test_status_schema.py, tests/fixtures/status/]
effects: []
ships-to: main
---
# The status script, the service and the app agree on one versioned JSON schema

## Done when

- ~~**C1** A versioned JSON Schema describes the status of a project. That covers its loops, whose state may be
  `unknown` (per D37); its concerns, each with its derived state, the reason, and the facts the state came from;
  queue items, each with its kind (one of the seven in D34), what it unblocks, who it waits on and the gate it
  crosses (per D38), and for a question its options and recommendation when the file records them (per D33);
  and "agents can start now". Prove: the schema validates the fixture
  documents and rejects a document missing a required field, in CI on main.~~ Split 2026-10-20: what PR #11
  delivered is C3, and the seven kinds and the question options are `queue-items` C1 and C2 (per D39).
- **C2** The fixture documents cover every state in the derivation table, plus `unknown`, so the app can be
  built and tested without a running service. Prove: a test that lists the states found in the fixtures against
  the table in `loop-status` SKILL.md, in CI on main.
- **C3** A versioned JSON Schema describes the status of a project. That covers its loops, whose state may be
  `unknown` (per D37); its concerns, each with its derived state, the reason, and the facts the state came from;
  queue items, each with what it unblocks, who it waits on and the gate it crosses (per D38); and "agents can
  start now". Prove: the schema validates the fixture documents and rejects a document missing a required field,
  in CI on main (per D39).

## Design

### Where we are

- Verified 2026-10-20 (main @f9a2817, from PR #11 @c3e5647):
  - `plugin/skills/loop-status/scripts/status.schema.json` exists at `schema_version` 1, with three fixtures and
    30 standard-library tests in `tests/test_status_schema.py`. Loops may be `unknown`, and queue items carry
    `gate`.
  - It has four queue kinds (question, review, ship, record), not D34's seven.
  - A question's options are plain text with no consequence, and its `recommendation` is "the recommended answer,
    or the default if unanswered", not kept apart from the default as D33 needs. `queue-items` closes both gaps
    (per D39).
  - It uses the JSON Schema keywords `type`, `required`, `enum`, `const`, `properties`, `additionalProperties`,
    `items`, `uniqueItems`, `oneOf`, `pattern`, `minLength`, `minimum`, `maximum` and `$ref`, all implemented by
    the tests' validator.
  - (Corrected 2026-10-20: this section said nothing exists, and that PR #11 was open.)
- The repository's tests use `python3 -m unittest` with only the standard library (`scripts/check.sh`, line 75), so
  validation in tests must not need `jsonschema` from PyPI. The tests keep a small validator of their own (per D1).
- Verified 2026-10-20 (PR #11's build): breaking any one of the validator's keywords made the suite fail. The
  validator also agreed with `jsonschema` 4.23 on 28,701 single-edit variations of the fixtures, though that
  library is not in CI.

### Approach

A contract concern, designed and built first (per D15): the schema lives beside the script, and the script's
`--json` output carries `schema_version`. It is keyed by project (per D18). Every concern's state is one of the
derivation's states (per D5) plus a `reason` string and an `inputs` object. Queue items carry `waits_on` (one
person) and `visible_to` (the loop's members), which `addressed-to-people` fills (per D10, D15). Until then they
may be empty. The seven kinds of queue item and the question options are `queue-items`' (per D39). The app
generates its TypeScript types from the schema in the same commit (per D13, D15).

The tests validate with a small standard-library validator, for the JSON Schema keywords listed above (per D1,
D2). A keyword outside that list needs the validator, and a test that fails without it, in the same change.

## Decisions

| # | Decision | Decided by, date | Closes |
| --- | --- | --- | --- |
| D1 | The tests validate the schema with a small standard-library validator, for the subset of JSON Schema the schema uses, inside the existing `check`. There is no `jsonschema` dependency and no second CI job. | Juan, 2026-10-20 | How to validate without PyPI |
| D2 | The subset is what the schema uses and the validator implements: `type`, `required`, `enum`, `const`, `properties`, `additionalProperties`, `items`, `uniqueItems`, `oneOf`, `pattern`, `minLength`, `minimum`, `maximum` and `$ref`. The Approach's earlier list of six was written before the build. | Juan, 2026-10-20 | The Approach's keyword list against PR #11 |

## Questions

| # | Question | Blocks | Default if unanswered |
| --- | --- | --- | --- |

## Evidence

## Shipped
