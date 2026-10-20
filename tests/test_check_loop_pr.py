"""Tests for plugin/skills/loop-status/scripts/check_loop_pr.sh, the guard on the loop-document delegation.

Each case builds a branch in a throwaway repository and checks that the script lets an agent merge it
(exit 0) or leaves it for the owner (exit 1).
"""
import os
import shutil
import subprocess
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "plugin", "skills", "loop-status", "scripts", "check_loop_pr.sh")


def git(repo, *args):
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True).stdout.strip()


@unittest.skipUnless(shutil.which("git") and shutil.which("sh"), "needs git and sh")
class CheckLoopPrTest(unittest.TestCase):
    def setUp(self):
        self.repo = tempfile.mkdtemp(prefix="check-loop-pr-")
        git(self.repo, "init", "-q", "-b", "main")
        git(self.repo, "config", "user.email", "test@example.com")
        git(self.repo, "config", "user.name", "Test")
        git(self.repo, "config", "commit.gpgsign", "false")
        os.makedirs(os.path.join(self.repo, "docs", "loops", "rp"))
        os.makedirs(os.path.join(self.repo, "src"))
        self.write("src/app.txt", "a\n")
        self.write("docs/loops/rp/queue.md", "# Queue\n\n## Evidence\n\n")
        self.commit("base")
        self.main_sha = git(self.repo, "rev-parse", "--short", "HEAD")
        self.append("docs/loops/rp/queue.md",
                    "- 2026-01-01 · C1 · HOLDS · rung 5 · main @%s · first proof\n" % self.main_sha)
        self.commit("first evidence")
        self.main_sha = git(self.repo, "rev-parse", "--short", "HEAD")
        git(self.repo, "checkout", "-q", "-b", "feature/code")
        self.write("src/app.txt", "b\n")
        self.commit("code on a branch")
        self.branch_sha = git(self.repo, "rev-parse", "--short", "HEAD")
        git(self.repo, "checkout", "-q", "main")

    def tearDown(self):
        shutil.rmtree(self.repo, ignore_errors=True)

    def write(self, path, text):
        full = os.path.join(self.repo, path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as f:
            f.write(text)

    def append(self, path, text):
        with open(os.path.join(self.repo, path), "a", encoding="utf-8") as f:
            f.write(text)

    def commit(self, message):
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", message)

    def branch(self, name):
        git(self.repo, "checkout", "-q", "-b", name, "main")

    def check(self):
        run = subprocess.run(["sh", SCRIPT, "--base", "main"], cwd=self.repo, capture_output=True, text=True)
        return run.returncode, run.stdout + run.stderr

    def assertMergeable(self):
        code, out = self.check()
        self.assertEqual(code, 0, out)

    def assertForOwner(self, reason):
        code, out = self.check()
        self.assertEqual(code, 1, out)
        self.assertIn(reason, out)

    def test_evidence_citing_main_may_merge(self):
        self.branch("docs/proof")
        self.append("docs/loops/rp/queue.md",
                    "- 2026-02-01 · C1 · HOLDS · rung 1 · staging @%s · on staging\n" % self.main_sha)
        self.commit("proof")
        self.assertMergeable()

    def test_evidence_citing_a_branch_is_for_the_owner(self):
        self.branch("docs/proof")
        self.append("docs/loops/rp/queue.md",
                    "- 2026-02-01 · C1 · HOLDS · rung 3 · local @%s · local\n" % self.branch_sha)
        self.commit("proof")
        self.assertForOwner("is not on main")

    def test_spike_may_cite_a_branch(self):
        self.branch("docs/spike")
        self.append("docs/loops/rp/queue.md",
                    "- 2026-02-01 · Q2 · HOLDS · rung 4 · local @%s · the answer\n" % self.branch_sha)
        self.commit("spike")
        self.assertMergeable()

    def test_code_in_the_same_pr_is_for_the_owner(self):
        self.branch("docs/mixed")
        self.append("docs/loops/rp/queue.md",
                    "- 2026-02-01 · C1 · HOLDS · rung 1 · staging @%s · on staging\n" % self.main_sha)
        self.write("src/app.txt", "c\n")
        self.commit("mixed")
        self.assertForOwner("outside docs/loops/: src/app.txt")

    def test_editing_evidence_is_for_the_owner(self):
        self.branch("docs/edit")
        path = os.path.join(self.repo, "docs/loops/rp/queue.md")
        with open(path, encoding="utf-8") as f:
            text = f.read()
        self.write("docs/loops/rp/queue.md", text.replace("first proof", "rewritten"))
        self.commit("edit")
        self.assertForOwner("append-only")

    def test_renaming_a_concern_may_merge(self):
        self.branch("docs/rename")
        git(self.repo, "mv", "docs/loops/rp/queue.md", "docs/loops/rp/job-queue.md")
        self.commit("rename")
        self.assertMergeable()

    def test_abandoning_a_loop_is_for_the_owner(self):
        self.branch("docs/abandon")
        os.makedirs(os.path.join(self.repo, "docs", "proposals"))
        git(self.repo, "mv", "docs/loops/rp", "docs/proposals/rp")
        self.commit("abandon")
        self.assertForOwner("outside docs/loops/")

    def test_ship_line_without_a_commit_is_for_the_owner(self):
        self.branch("docs/ship")
        self.append("docs/loops/rp/queue.md", "- 2026-02-01 · ship · verified · staging · no sha\n")
        self.commit("ship")
        self.assertForOwner("cites no commit")

    def test_migrated_line_without_a_commit_may_merge(self):
        self.branch("docs/migrated")
        self.append("docs/loops/rp/queue.md",
                    "- 2026-02-01 · C1 · HOLDS · rung 1 · production @? · old proof"
                    " (migrated without a commit, so status does not count it)\n")
        self.commit("migrated")
        self.assertMergeable()

    def test_design_without_evidence_may_merge(self):
        self.branch("docs/design")
        self.write("docs/loops/rp/worker.md", "---\nneeds: [queue]\n---\n# Worker\n")
        self.commit("design")
        self.assertMergeable()

    def test_nothing_changed_is_for_the_owner(self):
        self.branch("docs/empty")
        code, out = self.check()
        self.assertEqual(code, 1, out)


if __name__ == "__main__":
    unittest.main()
