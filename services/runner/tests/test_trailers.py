"""C1 (in part) and D4: a pull request with a runner commit that lacks `Sponsored-by:` fails the trailer check.

The runner's GitHub App does not exist yet, so its identity is configuration: the slug of the app, from which
GitHub derives the bot's login `<slug>[bot]` and its noreply address `<id>+<slug>[bot]@users.noreply.github.com`.
"""

import os
import subprocess
import sys
import unittest

import yaml

from runner import trailers
from tests.gitrepo import BOT, HUMAN, SLUG, Repo, git

HERE = os.path.dirname(os.path.abspath(__file__))
SERVICE = os.path.dirname(HERE)
ROOT = os.path.dirname(os.path.dirname(SERVICE))
SCRIPT = os.path.join(SERVICE, "runner", "trailers.py")

SPONSORED = "Record the marker\n\nWhy it changed.\n\nConcern: loop/x\nSponsored-by: juan\n"
UNSPONSORED = "Record the marker\n\nWhy it changed.\n\nConcern: loop/x\n"


class TrailerCheckTest(unittest.TestCase):
    def setUp(self):
        self.repo = Repo(self)

    def check(self, slug=SLUG):
        return trailers.check(self.repo.path, self.repo.base, self.repo.head(), slug)

    def test_human_commits_pass_without_a_sponsor(self):
        self.repo.commit("a.md", "a\n", UNSPONSORED, who=HUMAN)
        result = self.check()
        self.assertTrue(result.ok, result.lines)
        self.assertEqual(result.runner_commits, 0)

    def test_a_runner_commit_with_its_sponsor_passes(self):
        self.repo.commit("a.md", "a\n", SPONSORED, who=BOT)
        result = self.check()
        self.assertTrue(result.ok, result.lines)
        self.assertEqual(result.runner_commits, 1)

    def test_a_runner_commit_without_a_sponsor_fails_and_is_named(self):
        self.repo.commit("a.md", "a\n", SPONSORED, who=BOT)
        sha = self.repo.commit("b.md", "b\n", UNSPONSORED, who=BOT)
        result = self.check()
        self.assertFalse(result.ok)
        self.assertEqual(len(result.failures), 1)
        self.assertIn(sha[:12], "\n".join(result.lines))
        self.assertIn("Sponsored-by:", "\n".join(result.lines))

    def test_the_runner_is_recognised_by_its_address_alone(self):
        self.repo.commit("a.md", "a\n", UNSPONSORED, who=("someone else", BOT[1]))
        self.assertFalse(self.check().ok)

    def test_the_runner_is_recognised_as_committer(self):
        self.repo.commit("a.md", "a\n", UNSPONSORED, who=HUMAN, committer=BOT)
        self.assertFalse(self.check().ok)

    def test_a_sponsor_outside_the_trailer_block_does_not_count(self):
        message = "Record the marker\n\nSponsored-by: juan\n\nMore reasons after it.\n"
        self.repo.commit("a.md", "a\n", message, who=BOT)
        self.assertFalse(self.check().ok)

    def test_an_empty_sponsor_does_not_count(self):
        self.repo.commit("a.md", "a\n", "Record the marker\n\nConcern: loop/x\nSponsored-by:\n", who=BOT)
        self.assertFalse(self.check().ok)

    def test_the_trailer_key_is_case_insensitive(self):
        self.repo.commit("a.md", "a\n", "Record the marker\n\nsponsored-by: juan\n", who=BOT)
        self.assertTrue(self.check().ok)

    def test_commits_already_on_the_base_are_not_checked(self):
        self.repo.commit("a.md", "a\n", UNSPONSORED, who=BOT)
        self.repo.base = self.repo.head()
        self.repo.commit("b.md", "b\n", UNSPONSORED, who=HUMAN)
        self.assertTrue(self.check().ok)

    def test_a_runner_merge_commit_is_checked_too(self):
        git(self.repo.path, "switch", "-q", "-c", "side")
        self.repo.commit("side.md", "s\n", "Add a side file")
        git(self.repo.path, "switch", "-q", "main")
        self.repo.commit("main.md", "m\n", "Add a main file")
        git(self.repo.path, "merge", "-q", "--no-ff", "-m", "Merge side", "side", who=BOT)
        result = self.check()
        self.assertFalse(result.ok)
        self.assertEqual(result.runner_commits, 1)

    def test_without_an_app_slug_no_commit_is_the_runners_and_the_check_says_so(self):
        self.repo.commit("a.md", "a\n", UNSPONSORED, who=BOT)
        result = self.check(slug="")
        self.assertTrue(result.ok)
        self.assertTrue(any("RUNNER_APP_SLUG" in line for line in result.lines), result.lines)


class TrailerScriptTest(unittest.TestCase):
    """The workflow runs the file as a script with nothing installed, so it must run on the standard library."""

    def run_script(self, repo, slug):
        env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
        env["RUNNER_APP_SLUG"] = slug
        return subprocess.run([sys.executable, "-I", SCRIPT, "--repo", repo.path, "--base", repo.base,
                               "--head", repo.head()], capture_output=True, text=True, env=env)

    def test_the_script_fails_a_runner_commit_without_a_sponsor(self):
        repo = Repo(self)
        repo.commit("a.md", "a\n", UNSPONSORED, who=BOT)
        result = self.run_script(repo, SLUG)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("FAIL", result.stdout)

    def test_the_script_passes_a_sponsored_runner_commit(self):
        repo = Repo(self)
        repo.commit("a.md", "a\n", SPONSORED, who=BOT)
        result = self.run_script(repo, SLUG)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_the_script_imports_only_the_standard_library(self):
        with open(SCRIPT) as f:
            source = f.read()
        self.assertNotIn("from runner", source)
        self.assertNotIn("import runner", source)


class TrailerWorkflowTest(unittest.TestCase):
    """The workflow's job is the status check the owner makes required on main, so its name is part of the contract."""

    def setUp(self):
        with open(os.path.join(ROOT, ".github", "workflows", "trailers.yml")) as f:
            self.workflow = yaml.safe_load(f)

    def test_it_runs_on_pull_requests_as_the_trailers_check(self):
        triggers = self.workflow[True] if True in self.workflow else self.workflow["on"]  # YAML 1.1 reads `on` as True
        self.assertIn("pull_request", triggers)
        self.assertEqual(list(self.workflow["jobs"]), ["trailers"])

    def test_it_reads_the_app_slug_from_a_repository_variable(self):
        text = yaml.safe_dump(self.workflow)
        self.assertIn("vars.RUNNER_APP_SLUG", text)

    def test_it_runs_the_checker_from_the_base_commit_when_the_base_has_one(self):
        steps = self.workflow["jobs"]["trailers"]["steps"]
        script = "\n".join(step.get("run", "") for step in steps)
        self.assertIn('git show "$BASE:services/runner/runner/trailers.py"', script)
        checkout = next(step for step in steps if step.get("uses", "").startswith("actions/checkout@"))
        self.assertEqual(checkout["with"]["fetch-depth"], 0)


if __name__ == "__main__":
    unittest.main()
