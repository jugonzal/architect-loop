"""Open loop-document pull requests are checked with check_loop_pr.sh, as the terminal checks them, so a refused one
is in the queue the same way (LOOP.md §2.1). The checker is the one in the service's own image, built from the same
commit as the derivation; nothing from the clone is run.
"""

import os
import subprocess
from unittest import mock

from support import SCRIPTS, ServiceTestCase


class LoopDocumentCheckTest(ServiceTestCase):
    def open_loop_pr(self, number, branch, files, draft=False):
        sha = self.world.commit(files, "Record something on %s" % branch, branch=branch)
        self.world.pull_head(number, sha)
        self.github.pr(number, branch, files=tuple(files), body="Records it.", draft=draft)
        self.deliver("pull_request", self.pr_event(number, "opened"))
        return sha

    def alpha_with(self, line):
        with open(os.path.join(self.world.work, "docs/loops/sandbox/alpha.md")) as f:
            return f.read().replace("## Evidence\n", "## Evidence\n\n%s\n" % line)

    def refused(self, doc):
        return {item["detail"]["pr"]["number"]: item for item in doc["queue"] if item["kind"] == "refused_pr"}

    def test_a_loop_document_pull_request_that_passes_is_not_in_the_queue(self):
        main = self.world.main()
        self.open_loop_pr(5, "docs/sandbox-notes", {
            "docs/loops/sandbox/alpha.md": self.alpha_with("- 2026-10-23 · C1 · HOLDS · rung 1 · main @%s · ran it" % main[:7])})
        self.assertEqual(self.refused(self.status()), {})

    def test_one_that_changes_a_file_outside_docs_loops_is_refused_with_the_checkers_lines(self):
        self.open_loop_pr(6, "docs/sandbox-oops", {"README.md": "A shop, changed.\n",
                                                   "docs/loops/sandbox/beta.md": None})
        item = self.refused(self.status())[6]
        self.assertEqual(item["loop"], "sandbox")
        self.assertIn("FAIL: changes a file outside docs/loops/: README.md", item["detail"]["failures"])

    def test_a_draft_or_another_branch_is_not_checked(self):
        self.open_loop_pr(7, "docs/sandbox-draft", {"README.md": "x\n"}, draft=True)
        self.open_loop_pr(8, "feat/sandbox-thing", {"README.md": "y\n"})
        self.assertEqual(self.refused(self.status()), {})

    def test_the_checker_is_the_images_and_runs_without_gh(self):
        self.open_loop_pr(6, "docs/sandbox-oops", {"README.md": "A shop, changed.\n"})
        ran = []
        real = subprocess.run

        def recording(argv, *args, **kwargs):
            ran.append(list(argv))
            return real(argv, *args, **kwargs)

        with mock.patch("subprocess.run", recording):
            self.status()
        checks = [argv for argv in ran if argv[0] != "git"]
        self.assertEqual(checks, [["sh", os.path.join(SCRIPTS, "check_loop_pr.sh"), "--base", "origin/main"]])
