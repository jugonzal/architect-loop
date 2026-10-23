"""The service reads git the way the terminal does, and answers exactly what the derivation derives from its facts
(command-center/D15, status-derivation C3). Toward G3: the app shows the state /loop-status shows.

The terminal's facts come from loop_status.py gather on a clone of the same origin. Without gh on PATH, it reads
no pull requests or runs, so what is compared here is what both read from git: the loop documents and LOOP.md on
main, main's head, the branches, the commits with a Concern trailer, the merge commits, and the answers to the
derivation's git questions.
"""

import os
import shutil

from status import derivation
from status.facts import Gatherer
from status.github import GitHubApp

from support import APP_ID, APP_PEM, NOW, PROJECT, ServiceTestCase, git

LS = derivation.load()


class ParityTest(ServiceTestCase):
    def setUp(self):
        super().setUp()
        files = {"src/alpha/a.py": "x = 1\n"}
        self.open_pr(1, "sandbox/alpha", files)
        self.merge_pr(1, "sandbox/alpha", files)
        self.world.commit({"src/beta/b.py": "y = 1\n"}, "Start beta\n\nConcern: sandbox/beta", branch="sandbox/beta")
        self.world.commit({"src/c.py": "z = 1\n"}, "Fix a typo")

    def service_facts(self):
        github = GitHubApp(APP_ID, APP_PEM, api_url=self.github.url)
        return Gatherer(PROJECT, settings=self.settings, github=github, ls=LS, now=lambda: NOW).facts()

    def terminal_facts(self):
        clone = os.path.join(self.tmp, "terminal")
        git("clone", "--quiet", self.world.origin, clone)
        bin_dir = os.path.join(self.tmp, "bin")
        os.makedirs(bin_dir)
        os.symlink(shutil.which("git"), os.path.join(bin_dir, "git"))
        os.symlink(shutil.which("sh"), os.path.join(bin_dir, "sh"))
        env = {"PATH": bin_dir, "HOME": self.tmp, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}
        return LS.gather(root=clone, project=PROJECT, as_of="2026-10-23T09:00:00Z", env=env), clone, env

    def test_both_read_the_same_facts_from_git(self):
        service = self.service_facts()
        terminal, clone, env = self.terminal_facts()
        self.assertEqual(service["files"], terminal["files"])
        self.assertEqual(service["main"], terminal["main"])
        self.assertEqual(service["branches"], terminal["branches"])
        self.assertEqual(service["trailers"], terminal["trailers"])
        self.assertEqual(service["merges"], terminal["merges"])
        self.assertEqual(set(service["branches"]["heads"]), {"main", "sandbox/alpha", "sandbox/beta"})
        self.assertTrue(service["trailers"]["commits"])
        self.assertTrue(service["merges"]["commits"])

    def test_both_answer_the_derivations_git_questions_alike(self):
        service = self.service_facts()
        self.assertTrue(service["answers"])
        self.assertEqual(LS.pending_queries(service), [])
        _, clone, env = self.terminal_facts()
        runner = LS.Runner(clone, env)
        for answer in service["answers"]:
            with self.subTest(query=answer["query"]):
                self.assertEqual(LS.answer(runner, answer["query"], PROJECT), answer)

    def test_the_answer_is_what_the_derivation_derives_from_the_services_facts(self):
        self.assertEqual(self.status(), LS.derive(self.service_facts()))
