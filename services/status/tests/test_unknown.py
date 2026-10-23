"""C2: when GitHub is unreachable, the service answers unknown for the facts it could not read, and never serves an
older value as current.

What GitHub's API reports (pull requests, the runs on main) is unknown when it cannot be read, and so is every
state that rests on it. Main itself comes from git: when the service cannot fetch it, or its app cannot get a token
to fetch with, there is no current document to give, and it answers 503 instead of the one it gave before.
"""

import os

from support import ServiceTestCase, concern


class GitHubsApiUnreachableTest(ServiceTestCase):
    def setUp(self):
        super().setUp()
        files = {"src/alpha/a.py": "x = 1\n"}
        self.open_pr(1, "sandbox/alpha", files)
        self.assertEqual(concern(self.status(), "sandbox/alpha")["state"], "building")

    def test_pull_requests_that_cannot_be_read_are_unknown_and_so_is_what_rests_on_them(self):
        self.github.fail["/graphql"] = 502
        self.deliver("pull_request", self.pr_event(1, "synchronize"))
        doc = self.status()
        [missing] = [m for m in doc["missing"] if m["fact"] == "pull requests"]
        self.assertIn("502", missing["error"])
        # With no branch and no trailer, only the pull requests could say whether beta is built.
        beta = concern(doc, "sandbox/beta")
        self.assertEqual(beta["state"], "unknown")
        self.assertIn("cannot be read", beta["reason"])
        # Alpha's branch is read from the clone, so the derivation still calls it building, by its rule for
        # linking work without the host; the pull request it read before is not carried over.
        alpha = concern(doc, "sandbox/alpha")
        self.assertEqual(alpha["inputs"]["prs"], [])

    def test_the_runs_on_main_that_cannot_be_read_are_unknown(self):
        self.github.runs[self.world.project] = {self.world.main(): [
            {"name": "check", "status": "completed", "conclusion": "success"}]}
        self.deliver("workflow_run", self.push_event())
        self.assertEqual(self.status()["main"]["ci"], "success")
        self.github.fail["/repos/example/shop/actions"] = 500
        self.deliver("workflow_run", self.push_event())
        doc = self.status()
        self.assertEqual(doc["main"]["ci"], "unknown")
        [missing] = [m for m in doc["missing"] if m["fact"].startswith("checks on main")]
        self.assertIn("500", missing["error"])

    def test_it_reads_them_again_once_github_answers(self):
        self.github.fail["/graphql"] = 502
        self.deliver("push", self.push_event())
        self.assertEqual(concern(self.status(), "sandbox/beta")["state"], "unknown")
        del self.github.fail["/graphql"]
        self.deliver("push", self.push_event())
        doc = self.status()
        self.assertEqual(concern(doc, "sandbox/beta")["state"], "ready")
        self.assertEqual([p["number"] for p in concern(doc, "sandbox/alpha")["inputs"]["prs"]], [1])


class MainUnreachableTest(ServiceTestCase):
    # The caller's membership is reused for a minute, so the check of who is calling still passes and what is
    # tested is the gather itself.
    cache_seconds = 60.0

    def test_when_git_cannot_fetch_it_answers_503_and_not_the_document_before(self):
        before = self.status()
        event = self.push_event()
        moved = self.world.origin + ".away"
        os.rename(self.world.origin, moved)
        self.deliver("push", event)
        error = self.status(expect=503)
        self.assertEqual(error["error"], "unavailable")
        self.assertIn("git", error["message"])
        # Within max age of the earlier answer, and still not served: it was gathered before the delivery.
        error = self.status(expect=503)
        os.rename(moved, self.world.origin)
        self.assertEqual(self.status()["main"]["sha"], before["main"]["sha"])

    def test_a_revoked_app_reads_nothing_from_githubs_api_and_says_so(self):
        # This origin is a path, which git reads without a token; GitHub's would refuse the fetch too, and the
        # answer would be the 503 above.
        files = {"src/alpha/a.py": "x = 1\n"}
        self.open_pr(1, "sandbox/alpha", files)
        self.assertEqual(concern(self.status(), "sandbox/alpha")["state"], "building")
        self.github.revoke()
        self.deliver("push", self.push_event())
        doc = self.status()
        missing = {m["fact"]: m["error"] for m in doc["missing"]}
        self.assertIn("token", missing["pull requests"])
        self.assertEqual(doc["main"]["ci"], "unknown")
        self.assertEqual(concern(doc, "sandbox/beta")["state"], "unknown")
        self.assertEqual(concern(doc, "sandbox/alpha")["inputs"]["prs"], [])
        self.github.revoked = False
        self.deliver("push", self.push_event())
        doc = self.status()
        self.assertEqual(concern(doc, "sandbox/beta")["state"], "ready")
        self.assertEqual(concern(doc, "sandbox/alpha")["state"], "building")

    def test_an_app_that_cannot_sign_answers_503(self):
        self.status()
        self.restart(self.make_settings(github_private_key="not a key"))
        error = self.status(token="alice-token", expect=503)
        self.assertIn("cannot sign", error["message"])

    def test_a_failure_does_not_wait_for_max_age_to_end(self):
        self.status()
        event = self.push_event()
        moved = self.world.origin + ".away"
        os.rename(self.world.origin, moved)
        self.deliver("push", event)
        self.status(expect=503)
        os.rename(moved, self.world.origin)
        # Same instant, same generation: the failed gather left nothing, so this one gathers.
        self.assertEqual(self.status()["project"], "example/shop")
