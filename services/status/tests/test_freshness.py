"""C1: after a push, a pull request event or a change in an environment's served commit, the answer reflects it
within 60 seconds and names the commits it read.

The service reuses a document for at most STATUS_MAX_AGE_SECONDS (30), and never after a signed delivery from
GitHub about the project. So a push or a pull request event is in the very next answer once GitHub has delivered
it, and any change, delivered or not (a deploy has no delivery), is in every answer gathered after
STATUS_MAX_AGE_SECONDS. How long GitHub takes to deliver, and a whole refresh on the real repository, are for
local and staging/status to measure (per command-center/D53, D54).
"""

import threading
import time
import unittest

from status.board import Board

from support import ServiceTestCase, concern, environment


class PushTest(ServiceTestCase):
    def test_a_push_is_in_the_next_answer_once_it_is_delivered(self):
        before = self.status()
        self.assertEqual(before["main"]["sha"], self.world.main())
        pushed_at = time.monotonic()
        sha = self.world.commit({"src/other.py": "x = 1\n"}, "Add something")
        self.assertEqual(self.status()["main"]["sha"], before["main"]["sha"])  # not delivered yet: reused
        self.deliver("push", self.push_event())
        after = self.status()
        elapsed = time.monotonic() - pushed_at
        self.assertEqual(after["main"]["sha"], sha)
        self.assertEqual(environment(after, "main")["served"], sha)
        self.assertLess(elapsed, 60)

    def test_an_undelivered_push_is_in_the_answer_once_the_document_is_max_age_old(self):
        first = self.status()["main"]["sha"]
        sha = self.world.commit({"src/other.py": "x = 2\n"}, "Change something")
        self.clock.now += self.max_age_seconds
        self.assertEqual(self.status()["main"]["sha"], first)  # exactly max age: still reused
        self.clock.now += 0.001
        self.assertEqual(self.status()["main"]["sha"], sha)

    def test_the_answer_names_the_commits_it_read(self):
        main = self.world.main()
        doc = self.status()
        self.assertEqual(doc["main"]["sha"], main)
        self.assertEqual(doc["as_of"], "2026-10-23T09:00:00Z")
        self.assertEqual(environment(doc, "staging/web")["served"], main)
        alpha = concern(doc, "sandbox/alpha")
        self.assertEqual(alpha["inputs"]["main"], main)
        self.assertEqual(alpha["inputs"]["served"]["commit"], main)


class PullRequestTest(ServiceTestCase):
    def gathers(self):
        """How many times the service has read the pull requests: once per gather."""
        return sum(1 for _, path in self.github.requests if path == "/graphql")

    def test_a_pull_request_opened_merged_and_closed_is_in_the_next_answer(self):
        self.assertEqual(concern(self.status(), "sandbox/alpha")["state"], "ready")
        self.assertEqual(concern(self.status(), "sandbox/beta")["state"], "ready")

        files = {"src/alpha/a.py": "x = 1\n"}
        self.open_pr(1, "sandbox/alpha", files)
        alpha = concern(self.status(), "sandbox/alpha")
        self.assertEqual(alpha["state"], "building")
        self.assertEqual([p["number"] for p in alpha["inputs"]["prs"]], [1])

        merge = self.merge_pr(1, "sandbox/alpha", files)
        alpha = concern(self.status(), "sandbox/alpha")
        self.assertEqual(alpha["state"], "merged")
        self.assertEqual(alpha["inputs"]["prs"][0]["merge_commit"], merge)
        self.assertTrue(alpha["inputs"]["prs"][0]["on_main"])

        self.open_pr(2, "sandbox/beta", {"src/beta/b.py": "y = 1\n"})
        self.assertEqual(concern(self.status(), "sandbox/beta")["state"], "building")
        self.github.pr(2, "sandbox/beta", state="CLOSED", files=("src/beta/b.py",))
        self.world.delete_branch("sandbox/beta")
        self.deliver("pull_request", self.pr_event(2, "closed"))
        beta = concern(self.status(), "sandbox/beta")
        # A closed, unmerged pull request and no branch: nothing is built.
        self.assertEqual(beta["state"], "ready")
        self.assertEqual(beta["inputs"]["prs"][0]["state"], "closed")

    def test_any_signed_delivery_about_the_project_makes_the_next_answer_gather_again(self):
        self.status()
        gathered = self.gathers()
        self.status()
        self.assertEqual(self.gathers(), gathered, "reused within max age, so nothing was gathered")
        for event in ("push", "pull_request", "create", "delete", "workflow_run", "check_suite", "status", "ping"):
            with self.subTest(event=event):
                before = len(self.github.requests)
                response = self.deliver(event, self.push_event())
                self.assertEqual(response.get_json(), {"project": "example/shop", "stale": True})
                self.status()
                self.assertTrue(any(path == "/graphql" for _, path in self.github.requests[before:]))

    def test_a_delivery_about_another_repository_changes_nothing(self):
        self.status()
        response = self.deliver("push", self.push_event(project="example/elsewhere"))
        self.assertEqual(response.get_json(), {"project": "example/elsewhere", "stale": False})
        before = self.gathers()
        self.status()
        self.assertEqual(self.gathers(), before)


class DeployTest(ServiceTestCase):
    def test_a_change_in_a_served_commit_is_in_the_answer_once_the_document_is_max_age_old(self):
        files = {"src/alpha/a.py": "x = 1\n"}
        self.open_pr(1, "sandbox/alpha", files)
        merge = self.merge_pr(1, "sandbox/alpha", files)
        self.assertEqual(concern(self.status(), "sandbox/alpha")["state"], "merged")
        self.version.serve("/staging/version", merge)  # the owner deploys; GitHub delivers nothing
        self.clock.now += self.max_age_seconds + 1
        doc = self.status()
        self.assertEqual(environment(doc, "staging/web")["served"], merge)
        alpha = concern(doc, "sandbox/alpha")
        self.assertEqual(alpha["state"], "shipped")
        self.assertEqual(alpha["inputs"]["served"], {"environment": "staging/web", "commit": merge, "error": None,
                                                     "serves": True})


class BoardTest(unittest.TestCase):
    """The cache in front of the derivation: at most one gather at a time, and none of it lost to a delivery."""

    def setUp(self):
        self.now = 0.0
        self.calls = 0
        self.release = threading.Event()
        self.started = threading.Event()
        self.block = False

    def gather(self):
        self.calls += 1
        self.started.set()
        if self.block:
            self.release.wait(5)
        return {"n": self.calls}

    def board(self, max_age=30):
        return Board(self.gather, max_age=max_age, clock=lambda: self.now)

    def test_a_document_is_reused_until_it_is_max_age_old_or_stale(self):
        board = self.board()
        self.assertEqual(board.current(), {"n": 1})
        self.now = 30
        self.assertEqual(board.current(), {"n": 1})
        self.now = 30.5
        self.assertEqual(board.current(), {"n": 2})
        board.stale()
        self.assertEqual(board.current(), {"n": 3})
        self.assertEqual(board.current(), {"n": 3})

    def test_readers_at_the_same_time_share_one_gather(self):
        board = self.board()
        self.block = True
        results = []
        readers = [threading.Thread(target=lambda: results.append(board.current())) for _ in range(5)]
        for reader in readers:
            reader.start()
        self.started.wait(5)
        time.sleep(0.05)
        self.release.set()
        for reader in readers:
            reader.join(5)
        self.assertEqual(self.calls, 1)
        self.assertEqual(results, [{"n": 1}] * 5)

    def test_a_delivery_during_a_gather_makes_the_next_answer_gather_again(self):
        board = self.board()
        self.block = True
        first = []
        reader = threading.Thread(target=lambda: first.append(board.current()))
        reader.start()
        self.started.wait(5)
        board.stale()  # GitHub delivers while the facts are being read: they may predate it
        self.release.set()
        reader.join(5)
        self.assertEqual(first, [{"n": 1}])
        self.block = False
        self.assertEqual(board.current(), {"n": 2})

    def test_a_failed_gather_leaves_nothing_to_reuse(self):
        board = self.board()
        self.assertEqual(board.current(), {"n": 1})
        board.stale()

        def failing():
            raise RuntimeError("GitHub is down")

        board.gather = failing
        with self.assertRaises(RuntimeError):
            board.current()
        with self.assertRaises(RuntimeError):
            board.current()  # still within max age of the first answer, which is never served again
        board.gather = self.gather
        self.assertEqual(board.current(), {"n": 2})


if __name__ == "__main__":
    unittest.main()
