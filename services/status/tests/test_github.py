"""The service's GitHub client, against a fake GitHub over real HTTP: it reads pull requests in the shape
`gh pr list --json` prints them, so the derivation normalizes them the same way for the service as for the terminal.
"""

import unittest

from status import derivation
from status.errors import InvalidCredentials, Unavailable
from status.github import GitHubApp

from support import APP_ID, APP_KEY, APP_PEM, PROJECT, FakeGitHubServer

LS = derivation.load()


class GitHubAppTest(unittest.TestCase):
    def setUp(self):
        self.fake = FakeGitHubServer(APP_KEY.public_key(), [PROJECT])
        self.addCleanup(self.fake.close)
        self.github = GitHubApp(APP_ID, APP_PEM, api_url=self.fake.url)

    def test_pull_requests_read_as_gh_prints_them(self):
        self.fake.pr(3, "sandbox/alpha", state="MERGED", merge="a" * 40, files=("src/alpha/a.py", "README.md"))
        self.fake.pr(4, "docs/sandbox-notes", draft=True, body="Notes.", checks=[
            {"__typename": "StatusContext", "context": "ci/legacy", "state": "PENDING"},
            {"__typename": "CheckRun", "name": "check", "status": "IN_PROGRESS", "conclusion": None}])
        self.fake.pr(5, "sandbox/beta", state="CLOSED", checks=[])
        read = self.github.pull_requests(PROJECT)
        self.assertEqual(read, self.fake.gh_prs())
        normalized = {p["number"]: p for p in (LS.normalize_pr(raw, PROJECT) for raw in read)}
        self.assertEqual(normalized[3]["state"], "merged")
        self.assertEqual(normalized[3]["merge_commit"], "a" * 40)
        self.assertEqual(normalized[3]["files"], ["src/alpha/a.py", "README.md"])
        self.assertEqual(normalized[3]["checks"], "success")
        self.assertEqual(normalized[4]["checks"], "pending")
        self.assertTrue(normalized[4]["draft"])
        self.assertEqual(normalized[5]["checks"], "none")

    def test_pull_requests_are_read_page_by_page_up_to_the_limit(self):
        for number in range(1, 8):
            self.fake.pr(number, "sandbox/thing-%d" % number)
        self.assertEqual([p["number"] for p in self.github.pull_requests(PROJECT, page=3)], [7, 6, 5, 4, 3, 2, 1])
        self.assertEqual(sum(1 for _, path in self.fake.requests if path == "/graphql"), 3)
        self.assertEqual([p["number"] for p in self.github.pull_requests(PROJECT, limit=4, page=3)], [7, 6, 5, 4])

    def test_one_pull_request_is_read_by_its_number(self):
        self.fake.pr(9, "sandbox/alpha")
        self.assertEqual(self.github.pull_request(PROJECT, 9)["number"], 9)
        self.assertIsNone(self.github.pull_request(PROJECT, 10))

    def test_a_repository_graphql_cannot_resolve_is_unavailable(self):
        with self.assertRaises(Unavailable):
            self.github.pull_requests("example/missing")

    def test_the_runs_on_a_commit_are_read_for_their_state(self):
        sha = "b" * 40
        self.fake.runs[PROJECT] = {sha: [{"name": "check", "status": "completed", "conclusion": "success"},
                                         {"name": "runner", "status": "in_progress", "conclusion": None}]}
        runs = self.github.workflow_runs(PROJECT, sha)
        self.assertEqual(LS.runs_state(runs), "pending")
        self.assertEqual(self.github.workflow_runs(PROJECT, "c" * 40), [])

    def test_an_installation_token_is_reused_and_replaced_when_github_stops_accepting_it(self):
        self.github.pull_requests(PROJECT)
        self.github.pull_requests(PROJECT)
        self.assertEqual(len(self.fake.installation_tokens), 1)
        self.fake.installation_tokens = []  # GitHub forgets it
        self.github.pull_requests(PROJECT)
        self.assertEqual(len(self.fake.installation_tokens), 1)
        self.assertEqual(self.github.installation_token(PROJECT), self.fake.installation_tokens[0])

    def test_a_revoked_app_cannot_get_a_token(self):
        self.fake.revoke()
        with self.assertRaises(Unavailable) as raised:
            self.github.pull_requests(PROJECT)
        self.assertIn("token", str(raised.exception))

    def test_who_is_calling_and_whether_they_collaborate(self):
        self.fake.users["t"] = "alice"
        self.fake.collaborators[PROJECT] = {"alice"}
        self.assertEqual(self.github.user_login("t"), "alice")
        self.assertTrue(self.github.is_collaborator(PROJECT, "alice"))
        self.assertFalse(self.github.is_collaborator(PROJECT, "carol"))
        with self.assertRaises(InvalidCredentials):
            self.github.user_login("forged")

    def test_another_repositorys_default_branch_and_comparisons(self):
        self.fake.projects.add("example/tools")  # the app is installed there too
        self.fake.default_branches["example/tools"] = "trunk"
        self.fake.compare[("example/tools", "d" * 40, "trunk")] = "ahead"
        self.assertEqual(self.github.default_branch("example/tools"), "trunk")
        self.assertEqual(self.github.compare_status("example/tools", "d" * 40, "trunk"), "ahead")

    def test_an_outage_is_unavailable(self):
        self.fake.fail["/graphql"] = 503
        with self.assertRaises(Unavailable):
            self.github.pull_requests(PROJECT)
        self.fake.close()
        with self.assertRaises(Unavailable):
            self.github.user_login("t")


if __name__ == "__main__":
    unittest.main()
