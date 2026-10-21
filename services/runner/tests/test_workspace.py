"""A session's workspace: its own fresh clone on `<loop>/<concern>`, the trailer hook, and the plugin release.

session-runner C5 and D4, runner-dispatch C1: the hook adds `Sponsored-by:` to every session's commits and
`Concern:` only to a `/loop-build` session's (command-center/D45), `--no-verify` skips it, and the trailers check
fails the commit that skipped it, whatever the skill. D17: the session runs the release named in the dispatch,
never the clone's own `plugin/`. Everything runs against a local bare repository standing in for GitHub.
"""

import json
import os
import subprocess
import unittest

from runner import trailers
from runner.config import SCOPES
from runner.models import Session
from runner.workspace import Workspace, WorkspaceError, trailers_for
from tests.gitrepo import BOT, SLUG, Repo, clean_env, git
from tests.fakes import CONCERN, PROJECT, SCOPED, scratch

PAIRS = [(scope, skill) for scope, skills in SCOPES.items() for skill in skills]

PLUGIN_JSON = '{"name": "architect-loop", "version": "%s"}\n'


def session(concern=CONCERN, release="v0.3.0", sponsor="juan", sid="a" * 32, skill="loop-build", scope=None):
    on = SCOPED[scope] if scope else {"concern": concern, "branch": concern}
    return Session(id=sid, project=PROJECT, skill=skill, arguments="", model="m", sponsor=sponsor, budget_usd=1.0,
                   plugin_release=release, created_at="2026-10-20T12:00:00Z", **on)


class Origin:
    """A bare repository with a tagged release whose plugin differs from main's working tree."""

    def __init__(self, testcase):
        work = Repo(testcase)
        work.commit("plugin/.claude-plugin/plugin.json", PLUGIN_JSON % "0.3.0", "Release the plugin")
        work.commit("plugin/skills/loop-status/SKILL.md", "released copy\n", "Write the released skill")
        git(work.path, "tag", "v0.3.0")
        work.commit("plugin/skills/loop-status/SKILL.md", "working tree copy\n", "Edit the skill after the release")
        work.commit(f"docs/loops/{CONCERN}.md", "# concern\n", "Add the concern")
        self.path = os.path.join(scratch(testcase), "origin.git")
        git(work.path, "clone", "-q", "--bare", work.path, self.path)
        self.work = work


class WorkspaceTest(unittest.TestCase):
    def setUp(self):
        self.origin = Origin(self)
        self.workdir = scratch(self)
        self.workspace = Workspace(self.origin.path, self.workdir, BOT, env=clean_env())

    def prepare(self, s=None):
        s = s or session()
        prepared = self.workspace.prepare(s)
        self.addCleanup(self.workspace.cleanup, s.id)
        return prepared

    def test_each_session_gets_its_own_fresh_clone_on_the_concerns_branch(self):
        prepared = self.prepare()
        self.assertEqual(git(prepared.clone, "branch", "--show-current"), CONCERN)
        self.assertEqual(git(prepared.clone, "rev-parse", "HEAD"), git(self.origin.path, "rev-parse", "main"))
        self.assertTrue(prepared.clone.startswith(self.workdir))
        with self.assertRaises(WorkspaceError):
            self.workspace.prepare(session())  # the same session never reuses a clone

    def test_an_existing_branch_on_the_origin_is_resumed(self):
        git(self.origin.work.path, "switch", "-q", "-c", CONCERN)
        sha = self.origin.work.commit("work.md", "started\n", "Start the work")
        git(self.origin.work.path, "push", "-q", self.origin.path, CONCERN)
        prepared = self.prepare()
        self.assertEqual(git(prepared.clone, "rev-parse", "HEAD"), sha)
        self.assertEqual(git(prepared.clone, "rev-parse", "--abbrev-ref", "@{upstream}"), f"origin/{CONCERN}")

    def test_a_loop_or_environment_session_works_on_main_and_makes_no_branch(self):
        """runner-dispatch C3: it clones main and pushes no branch of its own unless its skill opens a PR."""
        for n, scope in enumerate(("loop", "environment"), 1):
            with self.subTest(scope=scope):
                prepared = self.prepare(session(scope=scope, skill="loop-status" if scope == "loop" else "loop-ship",
                                                sid=f"{n:032x}"))
                self.assertEqual(git(prepared.clone, "branch", "--show-current"), "main")
                self.assertEqual(git(prepared.clone, "rev-parse", "HEAD"), git(self.origin.path, "rev-parse", "main"))
                self.assertEqual(git(prepared.clone, "branch", "--format=%(refname:short)"), "main")
                self.assertEqual(self.workspace.pushed_branches(prepared.clone), [])

    def test_commits_are_the_bots(self):
        prepared = self.prepare()
        self.assertEqual(git(prepared.clone, "config", "user.name"), BOT[0])
        self.assertEqual(git(prepared.clone, "config", "user.email"), BOT[1])

    def test_the_plugin_is_the_named_release_not_the_clones_own(self):
        prepared = self.prepare()
        with open(os.path.join(prepared.plugin_dir, "skills", "loop-status", "SKILL.md")) as f:
            self.assertEqual(f.read(), "released copy\n")
        with open(os.path.join(prepared.clone, "plugin", "skills", "loop-status", "SKILL.md")) as f:
            self.assertEqual(f.read(), "working tree copy\n")
        self.assertFalse(os.path.commonpath([prepared.plugin_dir, prepared.clone]) == prepared.clone)
        self.assertEqual(prepared.plugin_name, "architect-loop")

    def test_the_release_is_read_only(self):
        prepared = self.prepare()
        skill = os.path.join(prepared.plugin_dir, "skills", "loop-status", "SKILL.md")
        self.assertFalse(os.access(skill, os.W_OK))
        self.assertFalse(os.access(os.path.dirname(skill), os.W_OK))

    def test_a_release_that_is_not_a_tag_is_refused(self):
        with self.assertRaises(WorkspaceError):
            self.prepare(session(release="v9.9.9", sid="b" * 32))


class HookTest(unittest.TestCase):
    """The commit-msg hook the runner installs, and what the trailers check makes of a commit that skipped it."""

    def setUp(self):
        self.origin = Origin(self)
        self.workspace = Workspace(self.origin.path, scratch(self), BOT, env=clean_env())
        self.prepared = self.workspace.prepare(session(sponsor="ana"))
        self.addCleanup(self.workspace.cleanup, session().id)
        self.base = git(self.prepared.clone, "rev-parse", "HEAD")

    def commit(self, message, *flags):
        path = os.path.join(self.prepared.clone, "work.md")
        with open(path, "a") as f:
            f.write("more\n")
        subprocess.run(["git", "add", "work.md"], cwd=self.prepared.clone, check=True, env=clean_env())
        subprocess.run(["git", "commit", "-q", *flags, "-m", message], cwd=self.prepared.clone, check=True,
                       env=clean_env(), capture_output=True)
        return git(self.prepared.clone, "log", "-1", "--format=%B")

    def test_the_hook_adds_the_concern_and_the_sponsor(self):
        message = self.commit("Write the work\n\nBecause.")
        self.assertIn(f"Concern: {CONCERN}", message)
        self.assertIn("Sponsored-by: ana", message)
        self.assertTrue(message.rstrip().endswith("Sponsored-by: ana"))

    def test_the_hook_keeps_a_concern_trailer_the_skill_wrote(self):
        message = self.commit(f"Write the work\n\nConcern: {CONCERN}\nCo-Authored-By: Claude <noreply@anthropic.com>")
        self.assertEqual(message.count("Concern:"), 1)
        self.assertIn("Sponsored-by: ana", message)

    def test_a_no_verify_commit_skips_the_hook_and_fails_the_trailers_check(self):
        self.commit("Write the sponsored work")
        self.assertTrue(trailers.check(self.prepared.clone, self.base, "HEAD", SLUG).ok)
        message = self.commit("Write the work without a sponsor", "--no-verify")
        self.assertNotIn("Sponsored-by", message)
        result = trailers.check(self.prepared.clone, self.base, "HEAD", SLUG)
        self.assertFalse(result.ok)
        self.assertEqual(result.runner_commits, 2)
        self.assertEqual(len(result.failures), 1)

    def test_the_hook_runs_even_when_a_global_config_points_hooks_elsewhere(self):
        global_config = os.path.join(scratch(self), "gitconfig")
        with open(global_config, "w") as f:
            f.write(f"[core]\n\thooksPath = {scratch(self)}\n")
        env = {**clean_env(), "GIT_CONFIG_GLOBAL": global_config}
        with open(os.path.join(self.prepared.clone, "x.md"), "w") as f:
            f.write("x\n")
        subprocess.run(["git", "add", "x.md"], cwd=self.prepared.clone, check=True, env=env)
        subprocess.run(["git", "commit", "-q", "-m", "Add x"], cwd=self.prepared.clone, check=True, env=env)
        self.assertIn("Sponsored-by: ana", git(self.prepared.clone, "log", "-1", "--format=%B"))


class TrailersPerSkillTest(unittest.TestCase):
    """runner-dispatch C1, for each skill the job can run: `Sponsored-by:` on every commit, and `Concern:` only on a
    `/loop-build` session's (command-center/D45). The trailers check passes each, so it stays true for every skill."""

    def setUp(self):
        self.origin = Origin(self)
        self.workspace = Workspace(self.origin.path, scratch(self), BOT, env=clean_env())

    def prepared(self, skill, n, scope="concern"):
        s = session(skill=skill, sponsor="ana", sid=f"{n:032x}", scope=scope)
        prepared = self.workspace.prepare(s)
        self.addCleanup(self.workspace.cleanup, s.id)
        return prepared

    def commit(self, clone, message, *flags):
        with open(os.path.join(clone, "work.md"), "a") as f:
            f.write("more\n")
        subprocess.run(["git", "add", "work.md"], cwd=clone, check=True, env=clean_env())
        subprocess.run(["git", "commit", "-q", *flags, "-m", message], cwd=clone, check=True, env=clean_env(),
                       capture_output=True)
        return git(clone, "log", "-1", "--format=%B")

    def parsed(self, clone, message):
        return trailers.trailers(clone, message)

    def test_only_a_loop_build_sessions_trailers_name_the_concern(self):
        for scope, skill in PAIRS:
            with self.subTest(scope=scope, skill=skill):
                expected = [("Sponsored-by", "juan")]
                if skill == "loop-build":
                    expected = [("Concern", CONCERN)] + expected
                self.assertEqual(trailers_for(session(skill=skill, scope=scope)), expected)

    def test_each_skills_commits_carry_the_sponsor_and_only_a_builds_the_concern(self):
        for n, (scope, skill) in enumerate(PAIRS, 1):
            with self.subTest(scope=scope, skill=skill):
                clone = self.prepared(skill, n, scope).clone
                base = git(clone, "rev-parse", "HEAD")
                found = self.parsed(clone, self.commit(clone, "Record the work\n\nBecause."))
                self.assertIn(("Sponsored-by", "ana"), found)
                self.assertEqual([v for k, v in found if k == "Concern"], [CONCERN] if skill == "loop-build" else [])
                self.assertTrue(trailers.check(clone, base, "HEAD", SLUG).ok)

    def test_a_no_verify_commit_fails_the_trailers_check_whatever_the_skill(self):
        for n, (scope, skill) in enumerate(PAIRS, 1):
            with self.subTest(scope=scope, skill=skill):
                clone = self.prepared(skill, n, scope).clone
                base = git(clone, "rev-parse", "HEAD")
                self.commit(clone, "Record the work without a sponsor", "--no-verify")
                result = trailers.check(clone, base, "HEAD", SLUG)
                self.assertFalse(result.ok)
                self.assertEqual(len(result.failures), 1)


class PushedBranchesTest(unittest.TestCase):
    """The job finds the pull requests a session opened from the branches it pushed, and only those."""

    def setUp(self):
        self.origin = Origin(self)
        self.workspace = Workspace(self.origin.path, scratch(self), BOT, env=clean_env())
        self.prepared = self.workspace.prepare(session())
        self.addCleanup(self.workspace.cleanup, session().id)

    def test_nothing_pushed_means_no_branches(self):
        self.assertEqual(self.workspace.pushed_branches(self.prepared.clone), [])

    def test_a_pushed_branch_is_found_and_a_fetched_one_is_not(self):
        clone = self.prepared.clone
        self.origin.work.commit("other.md", "o\n", "Someone else's work")
        git(self.origin.work.path, "push", "-q", self.origin.path, "main:refs/heads/someone-else")
        git(clone, "fetch", "-q", "origin")
        with open(os.path.join(clone, "w.md"), "w") as f:
            f.write("w\n")
        git(clone, "add", "w.md")
        git(clone, "commit", "-q", "-m", "Work", who=BOT)
        git(clone, "push", "-q", "-u", "origin", CONCERN)
        git(clone, "switch", "-q", "-c", "docs/command-center-design")
        git(clone, "push", "-q", "origin", "docs/command-center-design")
        self.assertEqual(sorted(self.workspace.pushed_branches(clone)), sorted([CONCERN, "docs/command-center-design"]))


if __name__ == "__main__":
    unittest.main()
