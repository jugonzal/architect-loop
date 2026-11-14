"""Tests that a skill which may merge its own loop-document PR waits for the PR's checks first
(command-center/merge-after-checks).

- C1: LOOP.md §2.1 lets an agent merge a loop-document PR once its checks pass. A PR's checks report nothing for
  the first seconds after it opens and take minutes to finish, so a skill that only says "merge" lets a session
  look once, see no result, and end without merging. Every skill under plugin/skills/ whose text allows it to
  merge under §2.1 must name the command that waits for the checks, say to give it time, and say not to end the
  turn before it answers. The skills are found by their text, not by a list, so a skill that gains the right to
  merge is caught the same way.

Run from the repository root: python3 -m unittest discover -s tests -v
"""

import glob
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILLS = os.path.join(ROOT, "plugin", "skills")

# The skills the concern was written for. The test does not stop at them: it only checks that the search for
# skills that may merge still finds them, so a change of wording cannot empty it without anyone noticing.
KNOWN = ["loop-design", "loop-plan", "loop-prove", "loop-ship", "loop-status"]

# How a skill says that it merges its own PR: "it may merge that PR itself", "merges that PR itself",
# "merge it yourself".
SELF_MERGE = re.compile(r"\bmerges? (?:that PR|the PR|it) (?:itself|yourself)\b")
DELEGATION = "§2.1"

# What a skill that may merge must say.
WAIT_COMMAND = re.compile(r"gh pr checks \S+ --watch")
TIME_TO_FINISH = re.compile(r"\bminutes\b")
STAY_IN_TURN = re.compile(r"\bnot end (?:the|your) turn\b")


def skill_text(name):
    """A skill's SKILL.md with every run of whitespace made one space, so a wrapped sentence reads as one."""
    with open(os.path.join(SKILLS, name, "SKILL.md"), encoding="utf-8") as f:
        return re.sub(r"\s+", " ", f.read())


def sentences(text):
    """The text cut after each full stop or semicolon that ends a clause. `LOOP.md` is not cut: no space follows."""
    return re.split(r"(?<=[.;])\s", text)


def may_merge(text):
    """Whether the text allows the skill to merge its own PR under LOOP.md §2.1: one sentence says both."""
    return any(DELEGATION in s and SELF_MERGE.search(s) for s in sentences(text))


def skills_that_may_merge():
    names = sorted(os.path.basename(os.path.dirname(p)) for p in glob.glob(os.path.join(SKILLS, "*", "SKILL.md")))
    return [n for n in names if may_merge(skill_text(n))]


class MergeAfterChecks(unittest.TestCase):
    def test_the_search_finds_the_skills_that_merge(self):
        found = skills_that_may_merge()
        for name in KNOWN:
            self.assertIn(name, found, "%s no longer reads as a skill that may merge under §2.1" % name)

    def test_the_search_tells_a_skill_that_merges_from_one_that_does_not(self):
        self.assertTrue(may_merge("Under `LOOP.md` §2.1 it may merge that PR itself once the script passes."))
        self.assertTrue(may_merge("If it passes, merge it yourself (`LOOP.md` §2.1)."))
        self.assertFalse(may_merge("It does not merge; code PRs are the owner's to merge."))
        self.assertFalse(may_merge("The owner does it, unless `LOOP.md` §2.1 delegates that exact action."))
        self.assertFalse(may_merge("Delegated by default (§2.1): merging a pull request that changes only docs."))

    def test_each_skill_that_may_merge_waits_for_the_checks(self):
        for name in skills_that_may_merge():
            text = skill_text(name)
            with self.subTest(skill=name):
                self.assertRegex(text, WAIT_COMMAND,
                                 "%s may merge a loop-document PR and does not name `gh pr checks <n> --watch`" % name)
                self.assertRegex(text, TIME_TO_FINISH,
                                 "%s does not say how long to give the checks" % name)
                self.assertRegex(text, STAY_IN_TURN,
                                 "%s does not say not to end the turn before the checks answer" % name)


if __name__ == "__main__":
    unittest.main()
