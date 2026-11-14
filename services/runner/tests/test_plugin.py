"""The plugin's source, read with git alone and no credentials (plugin-source/D1; plugin-repository C1, C2).

Every test runs real git against a local bare repository standing in for the plugin's repository; none reaches a
network. What is the newest release is `newest_release`'s rule (latest-release C1), tested in test_github.
"""

import os
import subprocess
import unittest
from unittest import mock

from runner.github import GitHubError
from runner.plugin import PluginSource, PluginSourceError
from tests.fakes import scratch
from tests.gitrepo import Repo, clean_env, git


def origin(testcase, tags=("v0.9.0", "v0.10.0", "v1.0.0-rc.1", "nightly")):
    """A bare repository whose history carries `tags`, oldest first, and the work tree it was pushed from."""
    work = Repo(testcase)
    for tag in tags:
        work.commit("plugin/.claude-plugin/plugin.json", '{"name": "architect-loop", "at": "%s"}\n' % tag, f"Cut {tag}")
        git(work.path, "tag", tag)
    path = os.path.join(scratch(testcase), "plugin.git")
    git(work.path, "clone", "-q", "--bare", work.path, path)
    return path, work


class PluginSourceTest(unittest.TestCase):
    def setUp(self):
        self.path, self.work = origin(self)
        self.plugin = PluginSource(self.path, env=clean_env())

    def test_the_latest_release_is_the_highest_release_tag_by_number(self):
        self.assertEqual(self.plugin.latest_release(), "v0.10.0")

    def test_a_repository_with_no_release_tag_has_no_latest_release(self):
        path, _ = origin(self, tags=("nightly", "0.4.0"))
        self.assertIsNone(PluginSource(path, env=clean_env()).latest_release())

    def test_a_release_exists_when_its_tag_does(self):
        self.assertTrue(self.plugin.release_exists("v0.9.0"))
        self.assertFalse(self.plugin.release_exists("v9.9.9"))
        self.assertFalse(self.plugin.release_exists("v0.9"))  # never a tag it only resembles

    def test_an_annotated_tag_is_a_release_too(self):
        git(self.work.path, "tag", "-a", "v2.0.0", "-m", "Release 2.0.0")
        git(self.work.path, "push", "-q", self.path, "v2.0.0")
        self.assertEqual(self.plugin.latest_release(), "v2.0.0")
        into = os.path.join(scratch(self), "source")
        self.plugin.fetch("v2.0.0", into)
        self.assertIn('"at": "nightly"', git(into, "show", "refs/tags/v2.0.0:plugin/.claude-plugin/plugin.json"))

    def test_a_fetch_holds_the_tag_and_nothing_else(self):
        into = os.path.join(scratch(self), "source")
        self.assertEqual(self.plugin.fetch("v0.9.0", into), into)
        self.assertEqual(git(into, "for-each-ref", "--format=%(refname)"), "refs/tags/v0.9.0")
        self.assertIn('"at": "v0.9.0"', git(into, "show", "refs/tags/v0.9.0:plugin/.claude-plugin/plugin.json"))

    def test_fetching_a_tag_the_repository_lacks_says_so(self):
        with self.assertRaises(PluginSourceError) as refused:
            self.plugin.fetch("v9.9.9", os.path.join(scratch(self), "source"))
        self.assertIn("v9.9.9 is not a tag of the plugin's repository", str(refused.exception))

    def test_a_repository_that_cannot_be_read_is_an_upstream_failure(self):
        missing = PluginSource(os.path.join(scratch(self), "nowhere.git"), env=clean_env())
        for read in (missing.latest_release, lambda: missing.release_exists("v0.9.0")):
            with self.assertRaises(GitHubError) as failed:  # what the dispatcher turns into a 502
                read()
            self.assertIn("nowhere.git", str(failed.exception))

    def test_a_repository_that_does_not_answer_in_time_fails_instead_of_waiting(self):
        with mock.patch("runner.plugin.subprocess.run", side_effect=subprocess.TimeoutExpired("git", 10)):
            with self.assertRaises(PluginSourceError) as failed:
                self.plugin.latest_release()
        self.assertIn("did not answer in 10 seconds", str(failed.exception))

    def test_git_is_never_allowed_to_ask_for_credentials(self):
        """D1: no prompt and no credential helper, so a private repository fails at once instead of waiting."""
        ran = []
        real = subprocess.run

        def recording(command, **kwargs):
            ran.append((command, kwargs["env"]))
            return real(command, **kwargs)

        with mock.patch("runner.plugin.subprocess.run", side_effect=recording):
            self.plugin.latest_release()
            self.plugin.fetch("v0.9.0", os.path.join(scratch(self), "source"))
        self.assertTrue(ran)
        for command, env in ran:
            self.assertEqual(command[:3], ["git", "-c", "credential.helper="])
            self.assertEqual(env["GIT_TERMINAL_PROMPT"], "0")
            self.assertIsNotNone(command)


if __name__ == "__main__":
    unittest.main()
