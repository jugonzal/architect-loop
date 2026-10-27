---
needs: []
touches: [plugin/skills/loop-plan/templates/loop.md, plugin/skills/loop-plan/templates/concern.md, plugin/skills/loop-plan/SKILL.md, plugin/skills/loop-design/SKILL.md, plugin/skills/loop-status/scripts/questions.py, tests/test_questions.py, tests/fixtures/questions/]
effects: [a plugin release so that terminals write the new format (the owner releases it per D17; gates: release)]
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

- 2026-10-26 · C2 · HOLDS · rung 5 · main @577c456 · Two parts, as Prove says. (1) Tests: `python3 -m unittest tests.test_questions` passes, 23 tests, with `test_the_example_in_each_template_reads_with_its_options`, `test_a_file_written_from_a_template_reads_clean`, `test_a_question_written_before_the_format_has_no_options` and `test_the_skills_that_write_questions_name_the_format_and_the_reader`. With the two templates and the two SKILL.md files as they were before the concern (the parent of efd9a0f), exactly two fail, the template-example test and the skills test, so they exercise the change. (2) Runs from a release: `/loop-plan sandbox` and `/loop-design sandbox` were run on 2026-10-25 from the installed copy of the skills, which is identical to the v0.4.0 tag (checked with `diff -r` for loop-plan, loop-design, loop-status, loop-build and loop-prove). They wrote four open questions on the sandbox loop, not a fixture (`sandbox/Q1` to `Q3` and `design-target/Q1`), each with its options and a recommendation; the design run then answered Q2 and Q3 and left Q1 open with its options updated. The files read clean (`problems []`) with `questions.py` from v0.4.0 and from main @577c456, which give the same four questions, two open (3 and 2 options) and two answered (2 and 3 options, kept). Across all of `docs/loops/` main's `questions.py` reads 97 questions with no problem: the 2 open ones all have options, and the 78 answered ones written before the format read with no options, so older questions still read. Two runs of the skills, on one loop

## Shipped

2026-10-21, to `main`, its `ships-to`. Terminals have it since release v0.4.0 (18b866b).

- **What shipped.** PR #18 (merge 03513ac) gave the loop and concern templates a `**Q# options**` list under the
  Questions table, with 2 to 4 options, a consequence for each and `(recommended)` on one. `questions.py` reads
  every question into its number, text, blocks, default, options and recommendation, and exits 1 naming each line
  it cannot read. `/loop-plan` and `/loop-design` write the options for any question they leave open (per D33).
- **Departures from the design.** None. A question written before the format reads with no options, as C2 asks.
- **Learned.** C2 holds at rung 5 on 577c456: `tests.test_questions` passes 23 tests, with the pre-concern
  templates and skills, exactly the two tests about them fail, and two real skill runs left questions that read
  clean. Across `docs/loops/`, the 78 answered questions written before the format read with none.
