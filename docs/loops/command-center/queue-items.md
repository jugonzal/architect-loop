---
needs: [status-api]
touches: [plugin/skills/loop-status/scripts/status.schema.json, tests/test_status_schema.py, tests/fixtures/status/]
effects: []
ships-to: main
---
# Every item the status board can queue for a person fits the status schema

## Done when

- **C1** The schema carries all seven kinds of queue item (per D34). A proof that needs something only the person
  has, a contradiction that needs a call, and a refused loop-document PR each carry the command to run and their
  facts (per D40). The fixtures hold at least one item of every kind. Prove: the fixtures validate; a test compares
  the kinds in the schema and the fixtures with the items `loop-status` SKILL.md queues in step 6 and its Record
  step; and an item of a new kind without its `command` is rejected, in CI on main.
- **C2** A question item carries its options, each a text with its consequence, a recommendation that names one
  of them or is null, and its default, kept apart (per D33, D41). A question written before the format validates
  with no options and no recommendation. Prove: fixtures with both kinds of question; an option without a
  consequence is rejected; and a test fails any fixture whose recommendation matches none of its options, in CI on
  main.

## Design

### Where we are

- Verified 2026-10-20 (main @f9a2817): `status.schema.json` has four queue kinds (question, review, ship, record),
  one detail definition each. A question's `options` is a list of plain text, and its `recommendation` is "the
  recommended answer, or the default if unanswered".
- Verified 2026-10-20 (`plugin/skills/loop-status/SKILL.md`): step 6 lists open questions, PRs ready for review,
  merged concerns waiting to ship, UNPROVEN claims that need something only the owner has, contradictions that
  need a call, and loop-document PRs the checker refused. The Record step offers records. Together those are D34's
  seven kinds.
- Verified 2026-10-20: nothing produces or reads status documents yet. `status-derivation`, `status-service` and
  the app are not built, so changing a question's options breaks no consumer. (Superseded 2026-10-22, main
  @18b866b: `loop_status.py` writes status documents since PR #27 (964d370), and the app's status client
  generates its types from the schema in `app/src/api/`, so a change to the schema now has two consumers.)

### Approach

Per D39: this concern works in `status-api`'s three paths, whose work is already on `main`, so nothing collides.
- **Kinds:** `queue_kind` gains `proof`, `contradiction` and `refused_pr`, each with a detail definition (per D40):
  - `proof`: the claim (concern and `C#`), the environment, what is missing, and who can supply it;
  - `contradiction`: the claim, its CONTRADICTS evidence line, what it contradicts (design text or a shared
    decision), and whether it escalates to the loop as a question;
  - `refused_pr`: the PR (number and URL) and the checker's failure lines.

  All three carry `command`, which the app shows read-only (per D34).
- **Questions** (per D41): `question_detail.options` becomes a list of `{text, consequence}`. `recommendation` is
  the text of one option, or null. `default` is the table's "Default if unanswered", or null. A question written
  before the format has an empty list of options and a null recommendation. JSON Schema cannot tie the
  recommendation to an option, so a test does, and the schema's description says so.
- **Tests:** C1's test reads the item list from SKILL.md, so the kinds and the skill cannot drift, the same way
  `status-api` C2 reads the states. The fixtures gain one item of each new kind and a question of each sort.
- **Validator:** it keeps to `status-api`'s keywords (per `status-api` D2). Using any other keyword means adding it
  to the validator, with a test that fails without it, in the same change.
- **Rollback:** revert the PR; nothing reads the schema yet.

## Decisions

| # | Decision | Decided by, date | Closes |
| --- | --- | --- | --- |
| D1 | `schema_version` stays 1. PR #17 merged at version 1, and nothing reads the schema yet. | Juan, 2026-10-20 | Q1 |

## Questions

| # | Question | Blocks | Default if unanswered |
| --- | --- | --- | --- |
| ~~Q1~~ | ~~Does `schema_version` change with this concern?~~ → D1 | | |

## Evidence

- 2026-10-20 · C1 · HOLDS · rung 5 · main @5fd6435 · `check` run 39525302878 on 5fd6435 (PR #17's merge) passed with `ok tests`, and on the same tree `tests.test_status_schema` gives 47 tests, OK (91 in the suite). The test reads 7 kinds from `loop-status` SKILL.md (step 6's six bullets and the Record step), and they equal the schema's `queue_kind` and the kinds in the fixtures, which hold at least one item of each. A proof, contradiction or refused-PR item without `command` is rejected. Breaking each rule in a copy of the tree fails the suite: an 8th bullet in step 6 (4 failures); `command` not required on proof, contradiction or refused PR (2 each); `refused_pr` dropped from the enum (12); the fixtures' proof or refused-PR item dropped (4 failures and 1 error each); the schema as it was at eee8119 (13 failures, 3 errors)
- 2026-10-20 · C2 · HOLDS · rung 5 · main @5fd6435 · Same run and tree. The fixtures hold a question with 2 options as `{text, consequence}`, a recommendation that names one of them and a separate default, and two questions written before the format (no options, null recommendation), one with a default and one with none. An option without a consequence is rejected, and the tests' recommendation check refuses 4 documents the schema accepts, among them a recommendation that names no option. Breaking each rule in a copy fails the suite: `consequence` not required (2 failures); `default` not required (2); a fixture recommendation that names no option (1)

## Shipped

2026-10-20, to `main`, its `ships-to`.

- **What shipped.** PR #17 (merge 5fd6435) gave the status schema all seven kinds of queue item (per D34). Beside
  question, review, ship and record it added `proof`, `contradiction` and `refused_pr`, each with its own facts
  and the `command` to run (per D40). A question item keeps its options as `{text, consequence}`, a
  recommendation that names one of them or is null, and its default, apart (per D33, D41). A question written
  before the format still validates. The fixtures hold an item of every kind and both sorts of question, and
  `tests/test_status_schema.py` has 47 tests, 17 of them new. `schema_version` stayed 1 (D1).
- **Departures from the design.** None in what the claims ask. Three readings were left to the reviewer, not
  recorded as decisions: a refused PR carries the whole `pr` object, not only its number and URL; a proof's or
  contradiction's claim is one `<loop>/<concern>/C<n>` ref, not a concern plus a `C#`; and a question's `ref` must
  be a `Q#`, since contradictions now have a kind of their own. JSON Schema cannot tie a recommendation to an
  option, so a test does (`recommendation_problems`), as the Approach planned.
- **Learned.** Reading the kinds from `loop-status`'s own step 6 and Record step keeps the schema and the skill
  from drifting, as `status-api` C2 does for the states: an eighth bullet in step 6 fails the suite. The small
  validator stayed trustworthy by being checked against the real one. It agreed with `jsonschema` 4.23 on all
  34,550 single-edit mutations of the fixtures. Changing the schema was free only while nothing read it. Since
  `status-derivation` and the app's status client, it has two consumers.
