"""Tests for plugin/skills/loop-status/scripts/questions.py, the one reader of the questions in a loop's files
(command-center/question-options).

- C1: the fixtures in tests/fixtures/questions/ fix the format. `export/` is a loop that follows it, with questions
  with and without options, open and answered, and export.json is what the reader must return for it, written by
  hand from the fixture. `broken/` breaks the format one way per question, and each break must be reported where
  it is. Every file in docs/loops/ must read without a problem, and every question row in it must be read.
- C2: the loop and concern templates of loop-plan carry an example, in their guidance comment, that the reader
  reads with options and a recommendation, and loop-plan and loop-design name the format and the reader.

Run from the repository root: python3 -m unittest discover -s tests -v
"""

import glob
import importlib.util
import json
import os
import re
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "plugin", "skills", "loop-status", "scripts", "questions.py")
FIXTURES = os.path.join(ROOT, "tests", "fixtures", "questions")
LOOPS = os.path.join(ROOT, "docs", "loops")
SKILLS = os.path.join(ROOT, "plugin", "skills")
TEMPLATES = os.path.join(SKILLS, "loop-plan", "templates")

_spec = importlib.util.spec_from_file_location("questions", SCRIPT)
questions = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(questions)

KEYS = ["ref", "file", "line", "number", "question", "open", "answer", "blocks", "default", "options",
        "recommendation"]


def relative(result, start):
    """The reader's result with every file path made relative to start, as the expected documents write them."""
    out = {"questions": [], "problems": []}
    for q in result["questions"]:
        out["questions"].append(dict(q, file=os.path.relpath(q["file"], start)))
    for p in result["problems"]:
        out["problems"].append(dict(p, file=os.path.relpath(p["file"], start)))
    return out


def by_ref(result):
    return {q["ref"]: q for q in result["questions"]}


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def check_shape(test, q):
    """What D41 asks of every question the reader returns, whatever file it came from."""
    test.assertEqual(list(q), KEYS, q["ref"])
    test.assertRegex(q["number"], r"^Q\d+$")
    test.assertTrue(q["question"], q["ref"])
    test.assertIsInstance(q["blocks"], list)
    for option in q["options"]:
        test.assertEqual(sorted(option), ["consequence", "text"], q["ref"])
        test.assertTrue(option["text"] and option["consequence"], q["ref"])
    if q["options"]:
        test.assertTrue(2 <= len(q["options"]) <= 4, q["ref"])
    texts = [o["text"] for o in q["options"]]
    if q["recommendation"] is not None:
        test.assertIn(q["recommendation"], texts, q["ref"])
    elif q["open"]:
        test.assertEqual(q["options"], [], "%s: an open question with options needs a recommendation" % q["ref"])
    if q["open"]:
        test.assertIsNone(q["answer"], q["ref"])


class FormatTest(unittest.TestCase):
    """C1: the export fixture loop reads exactly as export.json writes it down."""

    def setUp(self):
        self.result = questions.read_loop(os.path.join(FIXTURES, "export"))
        self.q = by_ref(self.result)

    def test_the_loop_reads_as_written_down(self):
        with open(os.path.join(FIXTURES, "export.json"), encoding="utf-8") as f:
            expected = json.load(f)
        self.assertEqual(relative(self.result, FIXTURES), expected)

    def test_every_question_has_the_shape(self):
        self.assertEqual(len(self.result["questions"]), 6)
        for q in self.result["questions"]:
            check_shape(self, q)

    def test_each_option_is_a_text_with_its_consequence(self):
        options = self.q["export/Q1"]["options"]
        self.assertEqual([o["text"] for o in options],
                         ["In the web process", "In a queue worker", "On the owner's device"])
        self.assertTrue(all(o["consequence"].endswith(".") for o in options))
        self.assertNotIn("(recommended)", json.dumps(self.result))

    def test_the_recommendation_names_an_option_and_the_default_is_kept_apart(self):
        q1 = self.q["export/Q1"]
        self.assertEqual(q1["recommendation"], "In a queue worker")
        self.assertEqual(q1["default"], "In the web process, behind a 30-second timeout")

    def test_an_answered_question_keeps_its_options(self):
        q2 = self.q["export/Q2"]
        self.assertFalse(q2["open"])
        self.assertEqual(q2["answer"], "D1")
        self.assertEqual(q2["question"], "CSV or JSON?")
        self.assertEqual(q2["recommendation"], "CSV")
        self.assertEqual(len(q2["options"]), 2)

    def test_a_question_written_before_the_format_has_no_options(self):
        prose = self.q["export/worker/Q1"]
        self.assertTrue(prose["open"])
        self.assertIn("Options:", prose["question"])
        self.assertEqual(prose["options"], [])
        self.assertIsNone(prose["recommendation"])
        self.assertEqual(prose["default"], "The database table")
        self.assertEqual(prose["blocks"], ["C1 (queue choice)", "C2"])
        answered = self.q["export/Q3"]
        self.assertEqual((answered["open"], answered["answer"], answered["options"]), (False, "D2", []))

    def test_a_wrapped_option_reads_as_one(self):
        q2 = self.q["export/worker/Q2"]
        self.assertEqual(q2["recommendation"], "7 days")
        self.assertEqual(q2["options"][2]["consequence"],
                         "never lost, but storage grows without bound and needs its own clean-up job.")

    def test_comments_and_other_sections_are_not_read(self):
        self.assertNotIn("export/Q7", self.q)
        self.assertEqual(self.result["problems"], [])

    def test_an_escaped_pipe_and_an_arrow_stay_in_an_open_question(self):
        q3 = self.q["export/worker/Q3"]
        self.assertEqual(q3["question"], "Does a retried export keep its `id | attempt` key, answered as `Q3 → <option>`?")
        self.assertTrue(q3["open"])
        self.assertEqual((q3["blocks"], q3["default"]), ([], None))

    def test_parse_reads_text_as_read_file_reads_the_file(self):
        path = os.path.join(FIXTURES, "export", "worker.md")
        from_text = questions.parse(read(path), source=path, ref_prefix="export/worker")
        self.assertEqual(from_text, questions.read_file(path))
        bare = questions.parse(read(path))
        self.assertEqual([q["ref"] for q in bare["questions"]], ["Q1", "Q2", "Q3"])

    def test_a_file_without_questions_reads_empty(self):
        result = questions.read_file(os.path.join(FIXTURES, "export", "quiet.md"))
        self.assertEqual(result, {"questions": [], "problems": []})


class BrokenFormatTest(unittest.TestCase):
    """C1: each way the broken fixture departs from the format is reported once, on its line."""

    EXPECTED = [
        (12, "Q5 is in the table twice"),
        (14, "not Q and a number"),
        (15, "Q8 has no question"),
        (21, "Q1 has 1 option"),
        (24, "Q2 marks 2 options (recommended)"),
        (31, "no consequence"),
        (33, "Q4 is open and has options, but none is marked (recommended)"),
        (37, "**Q<n> options**"),
        (41, "Q9 is not in the table"),
        (45, "Q10 has 5 options"),
        (53, "(recommended) goes at the end"),
        (59, "- **<option>**: <consequence>"),
        (63, "Q13 has two options that read \"Yes\""),
        (65, "a second list of options for Q4"),
    ]

    def setUp(self):
        self.path = os.path.join(FIXTURES, "broken", "README.md")
        self.result = questions.read_file(self.path)

    def test_each_break_is_reported_once_where_it_is(self):
        problems = self.result["problems"]
        self.assertEqual([p["line"] for p in problems], [line for line, _ in self.EXPECTED], problems)
        for problem, (line, words) in zip(problems, self.EXPECTED):
            self.assertEqual(problem["file"], self.path)
            self.assertIn(words, problem["message"], problem)

    def test_what_follows_the_format_still_reads(self):
        q = {x["number"]: x for x in self.result["questions"]}
        self.assertEqual(sorted(q, key=lambda n: int(n[1:])),
                         ["Q1", "Q2", "Q3", "Q4", "Q5", "Q6", "Q10", "Q11", "Q12", "Q13"])
        self.assertEqual(q["Q5"]["question"], "Asked twice?")
        self.assertEqual([o["text"] for o in q["Q3"]["options"]], ["Yes", "No"])
        self.assertEqual(q["Q3"]["recommendation"], "Yes")
        self.assertEqual([o["text"] for o in q["Q4"]["options"]], ["Yes", "No"])
        self.assertIsNone(q["Q4"]["recommendation"])
        self.assertIsNone(q["Q2"]["recommendation"])
        self.assertEqual(q["Q6"]["options"], [])
        self.assertEqual(q["Q11"]["recommendation"], "No")
        self.assertEqual([o["text"] for o in q["Q12"]["options"]], ["Yes", "No"])


class CommandLineTest(unittest.TestCase):
    def run_script(self, *args):
        return subprocess.run([sys.executable, SCRIPT] + list(args), cwd=FIXTURES, capture_output=True, text=True)

    def test_prints_what_it_reads(self):
        result = self.run_script("export")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        with open(os.path.join(FIXTURES, "export.json"), encoding="utf-8") as f:
            self.assertEqual(json.loads(result.stdout), json.load(f))

    def test_a_problem_exits_1_and_is_listed(self):
        result = self.run_script(os.path.join("broken", "README.md"))
        self.assertEqual(result.returncode, 1)
        printed = json.loads(result.stdout)
        self.assertEqual(len(printed["problems"]), len(BrokenFormatTest.EXPECTED))
        self.assertIn(os.path.join("broken", "README.md") + ":12: ", result.stderr)

    def test_a_folder_of_loops_reads_every_loop(self):
        result = self.run_script(".")
        refs = [q["ref"] for q in json.loads(result.stdout)["questions"]]
        self.assertIn("broken/Q1", refs)
        self.assertIn("export/worker/Q3", refs)
        self.assertEqual(result.returncode, 1)

    def test_a_missing_path_exits_2(self):
        result = self.run_script("no-such-loop")
        self.assertEqual(result.returncode, 2)
        self.assertIn("no-such-loop", result.stderr)


ROW = re.compile(r"^\|\s*(~~)?Q\d+(~~)?\s*\|")


class RepositoryLoopsTest(unittest.TestCase):
    """C1: every file in docs/loops/ reads, including the questions written before the format."""

    def setUp(self):
        self.files = sorted(glob.glob(os.path.join(LOOPS, "*", "*.md")))
        self.assertTrue(self.files, "no loops in docs/loops/")

    def test_every_file_reads_without_a_problem(self):
        result = questions.read_loops(LOOPS)
        self.assertEqual(result["problems"], [])
        self.assertEqual(sorted({q["file"] for q in result["questions"]} - set(self.files)), [])

    def test_every_question_row_is_read_once(self):
        for path in self.files:
            text = re.sub(r"<!--.*?-->", "", read(path), flags=re.S)
            rows = [line for line in text.splitlines() if ROW.match(line)]
            self.assertEqual(len(questions.read_file(path)["questions"]), len(rows), path)

    def test_every_question_has_the_shape_and_a_struck_row_is_answered(self):
        for path in self.files:
            lines = read(path).splitlines()
            for q in questions.read_file(path)["questions"]:
                check_shape(self, q)
                self.assertEqual(q["open"], not lines[q["line"] - 1].startswith("| ~~"), q["ref"])


class TemplateTest(unittest.TestCase):
    """C2: the templates show the format with an example the reader reads, and the skills name it."""

    def templates(self):
        return [os.path.join(TEMPLATES, name) for name in ("loop.md", "concern.md")]

    def test_a_file_written_from_a_template_reads_clean(self):
        for path in self.templates():
            self.assertEqual(questions.read_file(path), {"questions": [], "problems": []}, path)

    def test_the_example_in_each_template_reads_with_its_options(self):
        for path in self.templates():
            text = read(path)
            section = text[text.index("## Questions"):]
            section = section[:section.index("\n## ", 1)]
            self.assertIn("<!--", section, "%s: the example lives in the Questions section's comment" % path)
            example = questions.parse(text.replace("<!--", "").replace("-->", ""), source=path)
            self.assertEqual(example["problems"], [], path)
            open_ = [q for q in example["questions"] if q["open"]]
            answered = [q for q in example["questions"] if not q["open"]]
            self.assertTrue(open_ and answered, path)
            for q in example["questions"]:
                check_shape(self, q)
                self.assertTrue(2 <= len(q["options"]) <= 4, "%s %s" % (path, q["ref"]))
                self.assertIn(q["recommendation"], [o["text"] for o in q["options"]], path)
            for q in open_:
                self.assertTrue(q["blocks"] and q["default"], path)
                self.assertNotEqual(q["default"], q["recommendation"],
                                    "%s: the example should show that the default is not the recommendation" % path)
            for q in answered:
                self.assertRegex(q["answer"] or "", r"^D\d+$", path)

    def test_the_skills_that_write_questions_name_the_format_and_the_reader(self):
        for name in ("loop-plan", "loop-design"):
            text = read(os.path.join(SKILLS, name, "SKILL.md"))
            for words in ("**Q<n> options**", "(recommended)", "scripts/questions.py"):
                self.assertIn(words, text, "%s SKILL.md" % name)


if __name__ == "__main__":
    unittest.main()
