"""The real GitHub client, over HTTP against a fake GitHub (fakegithub.py): it identifies a caller with GET /user on
their token, and checks collaborators with threads' own app, signing the app's JWT and exchanging it for an
installation token (command-center/D27, D28). Nothing here talks to the real GitHub.

The last test wires the whole service to that client and shows that, whatever members do, the service sends GitHub
nothing but reads (C2: only a skill's write to the repository counts).
"""

import unittest

from fakegithub import APP_ID, FakeGitHubServer, new_key
from support import (
    PROJECT, RUNNER_TOKEN, ApiTestCase, ContractClient, base, concern_thread, review_comment_event, session_thread,
)
from threads.app import create_app
from threads.errors import InvalidCredentials, Unavailable
from threads.github import GitHubApp


class GitHubClientTest(unittest.TestCase):
    def setUp(self):
        key, pem = new_key()
        self.server = FakeGitHubServer(key.public_key())
        self.addCleanup(self.server.close)
        self.server.users = {"gho_alice": "alice", "gho_carol": "carol"}
        self.server.collaborators = ["alice", "bob"]
        self.github = GitHubApp(APP_ID, pem, api_url=self.server.url)

    def test_a_caller_is_identified_by_get_user_on_their_token(self):
        self.assertEqual(self.github.user_login("gho_alice"), "alice")
        with self.assertRaises(InvalidCredentials):
            self.github.user_login("gho_revoked")

    def test_collaborators_are_checked_with_the_apps_installation_token(self):
        self.assertTrue(self.github.is_collaborator(PROJECT, "alice"))
        self.assertFalse(self.github.is_collaborator(PROJECT, "carol"))
        self.assertEqual(self.server.installation_tokens, ["ghs_fake0"], "one installation token, reused")
        self.assertIn(("GET", f"/repos/{PROJECT}/installation"), self.server.requests)

    def test_the_member_list_follows_every_page(self):
        self.server.collaborators = [f"user{i}" for i in range(250)]
        self.assertEqual(self.github.collaborators(PROJECT), [f"user{i}" for i in range(250)])
        pages = [r for r in self.server.requests if r == ("GET", f"/repos/{PROJECT}/collaborators")]
        self.assertEqual(len(pages), 3)

    def test_an_expired_installation_token_is_replaced(self):
        self.github.is_collaborator(PROJECT, "alice")
        self.server.installation_tokens = []  # GitHub no longer accepts it
        self.github._token_expires = 0
        self.assertTrue(self.github.is_collaborator(PROJECT, "alice"))
        self.assertEqual(self.server.installation_tokens, ["ghs_fake0"])

    def test_an_outage_is_unavailable_not_a_refusal(self):
        self.server.fail_with = 502
        with self.assertRaises(Unavailable):
            self.github.user_login("gho_alice")
        with self.assertRaises(Unavailable):
            self.github.is_collaborator(PROJECT, "alice")
        nowhere = GitHubApp(APP_ID, "not a key", api_url="http://127.0.0.1:9")
        with self.assertRaises(Unavailable):
            nowhere.user_login("gho_alice")


class OnlyReadsFromGitHubTest(ApiTestCase):
    def test_the_service_sends_github_nothing_but_reads(self):
        key, pem = new_key()
        server = FakeGitHubServer(key.public_key())
        self.addCleanup(server.close)
        server.users = {"gho_alice": "alice", "gho_bob": "bob", "gho_carol": "carol"}
        server.collaborators = ["alice", "bob"]
        app = create_app(self.settings, store=self.store, github=GitHubApp(APP_ID, pem, api_url=server.url),
                         identity=self.identity, clock=self.clock)
        self.api = ContractClient(app, self)

        thread = concern_thread()
        self.assertEqual([m["login"] for m in self.api.get(thread, token="gho_alice").get_json()["members"]],
                         ["alice", "bob"])
        message = self.post_message(thread, body="Record the cap as 3?", token="gho_bob")
        self.api.put(f"{thread}/watchers/me", token="gho_alice")
        self.api.put(f"{base()}/messages/{message['id']}/record-marks/me", token="gho_alice")
        self.api.delete(f"{base()}/messages/{message['id']}/record-marks/me", token="gho_alice")
        self.api.put(f"{base()}/messages/{message['id']}/record-marks/me", token="gho_bob")
        self.post_message(session_thread(), body="started", token=RUNNER_TOKEN, kind="milestone", sponsor="bob")
        self.deliver("pull_request_review_comment", review_comment_event())
        self.assertEqual(self.api.get(thread, token="gho_carol").status_code, 403)

        writes = [r for r in server.requests if r[0] != "GET"]
        self.assertEqual(set(writes), {("POST", "/app/installations/42/access_tokens")},
                         "the only non-GET is exchanging the app's JWT for its read-only installation token")
        self.assertTrue(all(path in ("/user", f"/repos/{PROJECT}/installation", f"/repos/{PROJECT}/collaborators")
                            or path.startswith(f"/repos/{PROJECT}/collaborators/")
                            for method, path in server.requests if method == "GET"), server.requests)


if __name__ == "__main__":
    unittest.main()
