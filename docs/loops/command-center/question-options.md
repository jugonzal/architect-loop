---
needs: [one-repository]
touches: [plugin/skills/loop-plan/templates/loop.md, plugin/skills/loop-plan/templates/concern.md, plugin/skills/loop-plan/SKILL.md, plugin/skills/loop-design/SKILL.md, plugin/skills/loop-status/scripts/questions.py, tests/test_questions.py, tests/fixtures/questions/]
effects: [a plugin release so that terminals write the new format (the owner releases, per D17)]
ships-to: main
---
# Every open question carries its options and a recommendation in the file that raises it

## Done when

- **C1** The loop and concern templates show how a question records 2 to 4 options, each with its main
  consequence, and one recommendation. `questions.py` reads every question in a loop's files into its number,
  text, what it blocks, its default, its options and its recommendation (per D33). Prove: fixture tests over
  questions with and without options, answered and open, and a test that reads every file in `docs/loops/`, in
  CI on main.
- **C2** `/loop-plan` and `/loop-design` write the options and the recommendation for every question they leave
  open, and a question written before the format still reads, with no options. Prove: a test that reads the
  templates' examples, and a `/loop-design` run from a release that leaves a question open on a fixture loop,
  whose file `questions.py` reads with its options, on main.

## Design

### Where we are

- Verified 2026-10-20 (`plugin/skills/loop-plan/templates/loop.md` and `concern.md`): the Questions table has
  three columns, Question, Blocks and Default if unanswered. Nothing records options or a recommendation.
- Verified 2026-10-20 (`plugin/skills/loop-design/SKILL.md`, step 4): the skill already lays out 2 to 4 options
  and a recommendation for each question it asks, but writes down only the decision.
- Verified 2026-10-20 (`plugin/skills/loop-status/SKILL.md`, step 6): the board shows each open question "with its
  recommendation", which a script can read only once the files hold it.
- Proposal §5 (question card): two to four options with consequences, a recommendation, what it blocks and the
  default if unanswered. Proposal §2 (Why-Record): decision cards keep the options and the recommendation beside
  the answer.

### Approach

Per D33: the Questions table keeps its columns, so every existing file still reads. A question with options gets
them in a form a script can read and a person can still scan, for example a short list under the table headed by
its number, with the recommended option marked. An answered question keeps its options, so the reasoning stays
beside the decision. The format is fixed by C1's fixtures before the skills' text changes.

`questions.py` uses only the standard library, like the other scripts. `status-derivation` imports it rather than
parsing questions itself, so the format has one reader, and `queue-items`' question item carries what it returns: each option as a text with its
consequence, the recommendation, and the default kept apart (per D41).
`loop-plan` and `loop-design` say to write the options whenever a question stays open, and the templates show an
example.

## Decisions

| # | Decision | Decided by, date | Closes |
| --- | --- | --- | --- |

## Questions

| # | Question | Blocks | Default if unanswered |
| --- | --- | --- | --- |

## Evidence

## Shipped
