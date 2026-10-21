"""The GitHub client against a fake transport: what each call sends, and with whose token (D27, D28).

No request leaves the process. The app key is generated here for the test and thrown away.
"""

import base64
import json
import os
import time
import unittest

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from runner.dispatch import ENVIRONMENT
from runner.github import (JOB_PERMISSIONS, SERVICE_PERMISSIONS, AppAuth, GitHubError, RestGitHub,
                           concern_pull_requests, environments_in)

KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
PEM = KEY.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                        serialization.NoEncryption()).decode()
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
NOW = 1_792_500_000  # 2026-10-20
EXPIRES = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(NOW + 3600))  # GitHub's tokens last an hour


class Transport:
    def __init__(self):
        self.requests = []
        self.answers = []

    def answer(self, status, body=None):
        self.answers.append((status, body))

    def __call__(self, method, url, headers, body=None):
        self.requests.append({"method": method, "url": url, "headers": headers,
                              "body": json.loads(body) if body else None})
        status, answer = self.answers.pop(0)
        return status, {}, json.dumps(answer).encode() if answer is not None else b""


def pull(n, head, body=""):
    return {"number": n, "html_url": f"https://github.com/jugonzal/architect-loop/pull/{n}", "head": {"ref": head},
            "body": body}


class GitHubTest(unittest.TestCase):
    def setUp(self):
        self.transport = Transport()
        self.auth = AppAuth("12345", "678", PEM, "architect-loop", transport=self.transport, clock=lambda: NOW)
        self.github = RestGitHub("jugonzal/architect-loop", self.auth, app_slug="architect-loop-runner",
                                 transport=self.transport)

    def token_answer(self, token="ghs_installation"):
        self.transport.answer(201, {"token": token, "expires_at": EXPIRES})

    def test_the_callers_token_goes_only_to_get_user(self):
        self.transport.answer(200, {"login": "juan"})
        self.assertEqual(self.github.login("gho_caller"), "juan")
        [request] = self.transport.requests
        self.assertEqual((request["method"], request["url"]), ("GET", "https://api.github.com/user"))
        self.assertEqual(request["headers"]["Authorization"], "Bearer gho_caller")

    def test_a_token_github_refuses_is_no_one(self):
        self.transport.answer(401, {"message": "Bad credentials"})
        self.assertIsNone(self.github.login("gho_bad"))

    def test_github_failing_is_an_error_not_a_refusal(self):
        self.transport.answer(500, {"message": "boom"})
        with self.assertRaises(GitHubError):
            self.github.login("gho_caller")

    def test_the_collaborator_check_uses_the_apps_own_token(self):
        self.token_answer()
        self.transport.answer(204)
        self.transport.answer(404, {"message": "Not Found"})
        self.assertTrue(self.github.is_collaborator("juan"))
        self.assertFalse(self.github.is_collaborator("outsider"))
        mint, check, _ = self.transport.requests
        self.assertEqual(mint["url"], "https://api.github.com/app/installations/678/access_tokens")
        self.assertEqual(mint["body"], {"repositories": ["architect-loop"], "permissions": SERVICE_PERMISSIONS})
        self.assertEqual(check["url"], "https://api.github.com/repos/jugonzal/architect-loop/collaborators/juan")
        self.assertEqual(check["headers"]["Authorization"], "Bearer ghs_installation")

    def test_the_app_jwt_is_signed_with_the_apps_key_and_names_the_app(self):
        self.token_answer()
        self.transport.answer(204)
        self.github.is_collaborator("juan")
        bearer = self.transport.requests[0]["headers"]["Authorization"].removeprefix("Bearer ")
        claims = jwt.decode(bearer, KEY.public_key(), algorithms=["RS256"], options={"verify_exp": False,
                                                                                     "verify_iat": False})
        self.assertEqual(claims["iss"], "12345")
        self.assertLessEqual(claims["exp"] - claims["iat"], 600)

    def test_installation_tokens_are_cached_per_permission_set_until_near_expiry(self):
        self.token_answer("ghs_service")
        self.token_answer("ghs_job")
        self.assertEqual(self.auth.token(SERVICE_PERMISSIONS), "ghs_service")
        self.assertEqual(self.auth.token(SERVICE_PERMISSIONS), "ghs_service")
        self.assertEqual(self.auth.token(JOB_PERMISSIONS), "ghs_job")
        self.assertEqual(len(self.transport.requests), 2)
        self.auth.clock = lambda: NOW + 3360  # within five minutes of the expiry
        self.token_answer("ghs_fresh")
        self.assertEqual(self.auth.token(SERVICE_PERMISSIONS), "ghs_fresh")

    def test_the_job_never_asks_for_the_workflows_permission(self):
        self.assertNotIn("workflows", JOB_PERMISSIONS)
        self.assertEqual(JOB_PERMISSIONS["contents"], "write")
        self.assertEqual(JOB_PERMISSIONS["pull_requests"], "write")

    def test_open_pull_requests_are_read_page_by_page(self):
        self.token_answer()
        self.transport.answer(200, [pull(n, f"b{n}") for n in range(100)])
        self.transport.answer(200, [pull(100, "last")])
        found = self.github.open_pull_requests()
        self.assertEqual(len(found), 101)
        self.assertEqual(found[-1], {"number": 100, "url": "https://github.com/jugonzal/architect-loop/pull/100",
                                     "head": "last", "body": ""})
        self.assertIn("page=2", self.transport.requests[-1]["url"])

    def test_a_concern_exists_when_its_file_is_on_main(self):
        self.token_answer()
        self.transport.answer(200, {"type": "file"})
        self.assertTrue(self.github.concern_exists("command-center", "session-runner"))
        self.assertTrue(self.transport.requests[-1]["url"].endswith(
            "/contents/docs/loops/command-center/session-runner.md?ref=main"))

    def test_a_release_exists_when_its_tag_does(self):
        self.token_answer()
        self.transport.answer(404, {"message": "Not Found"})
        self.assertFalse(self.github.release_exists("v9.9.9"))
        self.assertTrue(self.transport.requests[-1]["url"].endswith("/git/ref/tags/v9.9.9"))

    def test_a_loop_exists_when_its_readme_is_on_main(self):
        self.token_answer()
        self.transport.answer(200, {"type": "file"})
        self.assertTrue(self.github.loop_exists("command-center"))
        self.assertTrue(self.transport.requests[-1]["url"].endswith(
            "/contents/docs/loops/command-center/README.md?ref=main"))

    def test_the_environments_are_the_rows_of_loop_md_section_3_on_main(self):
        with open(os.path.join(ROOT, "LOOP.md"), "rb") as f:
            content = base64.encodebytes(f.read()).decode()  # GitHub wraps its base64 in lines, as this does
        self.token_answer()
        self.transport.answer(200, {"type": "file", "encoding": "base64", "content": content})
        names = self.github.environments()
        self.assertTrue(self.transport.requests[-1]["url"].endswith("/contents/LOOP.md?ref=main"))
        self.assertEqual(self.transport.requests[-1]["headers"]["Authorization"], "Bearer ghs_installation")
        self.assertIn("main", names)
        self.assertIn("staging/runner", names)
        self.assertIn("production/runner", names)
        self.assertTrue(all(ENVIRONMENT.match(name) for name in names), names)

    def test_without_loop_md_there_are_no_environments(self):
        self.token_answer()
        self.transport.answer(404, {"message": "Not Found"})
        self.assertEqual(self.github.environments(), [])

    def test_editing_a_body_patches_the_pull_request_with_the_jobs_token(self):
        self.token_answer("ghs_job")
        self.transport.answer(200, {"number": 7})
        self.github.set_pull_request_body(7, "text")
        mint, patch = self.transport.requests
        self.assertEqual(mint["body"]["permissions"], JOB_PERMISSIONS)
        self.assertEqual((patch["method"], patch["body"]), ("PATCH", {"body": "text"}))


class EnvironmentsInTest(unittest.TestCase):
    """The environments a `/loop-ship` dispatch may name: the first column of LOOP.md §3, and no other table's."""

    def test_only_the_environments_table_counts(self):
        text = "\n".join([
            "# LOOP.md", "", "## 2. Gates", "", "| Action | Scope |", "| --- | --- |", "| Merge | docs |", "",
            "## 3. Environments", "", "| Environment | Where | Verify with |", "| --- | --- | --- |",
            "| main | the main branch | `gh run list` |", "| `staging` | Cloud Run | `served.sh` |",
            "| **production** | Cloud Run | `served.sh` |", "", "Lowest first.", "", "### 3.1 Notes", "",
            "| Name | What |", "| --- | --- |", "| ignored | not an environment |", "",
            "## 4. Commands", "", "| Purpose | Command |", "| --- | --- |", "| Unit tests | `make test` |",
        ])
        self.assertEqual(environments_in(text), ["main", "staging", "production"])

    def test_a_heading_without_a_number_counts_too(self):
        self.assertEqual(environments_in("## Environments\n\n| Environment |\n|---|\n| staging/runner |\n"),
                         ["staging/runner"])

    def test_no_section_means_no_environments(self):
        self.assertEqual(environments_in("# Nothing here\n\n| a | b |\n| - | - |\n| c | d |\n"), [])


class ConcernPullRequestsTest(unittest.TestCase):
    def test_a_pull_request_belongs_to_a_concern_by_branch_or_by_trailer(self):
        pulls = [
            {"number": 1, "url": "u1", "head": "loop/x", "body": ""},
            {"number": 2, "url": "u2", "head": "docs/loop-x", "body": "Text\n\nConcern: loop/x\n"},
            {"number": 3, "url": "u3", "head": "loop/x-more", "body": "Concern: loop/x-more"},
            {"number": 4, "url": "u4", "head": "other", "body": "See Concern: loop/x inline"},
        ]
        self.assertEqual([p["number"] for p in concern_pull_requests(pulls, "loop/x")], [1, 2])


if __name__ == "__main__":
    unittest.main()
