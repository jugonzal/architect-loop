"""Who may read a project's status: a collaborator on its repository, identified by GitHub (command-center/D27, D28).
And who may make a document stale: GitHub, with a delivery signed by the app's webhook secret."""

import json

from support import OTHER_PROJECT, PROJECT, ServiceTestCase, sign, status_path


class ReadersTest(ServiceTestCase):
    def test_a_collaborator_reads_the_status(self):
        self.assertEqual(self.status()["project"], PROJECT)

    def test_a_caller_without_a_token_is_refused(self):
        for headers in ({}, {"Authorization": "Basic YWxpY2U6eA=="}, {"Authorization": "Bearer "}):
            with self.subTest(headers=headers):
                response = self.api.get(status_path(), headers=headers, valid_request=False)
                self.assertEqual(response.status_code, 401)
                self.assertEqual(response.get_json()["error"], "unauthorized")

    def test_a_token_github_does_not_accept_is_refused(self):
        self.assertEqual(self.status(token="gho_forged", expect=401)["error"], "unauthorized")

    def test_someone_who_is_not_a_collaborator_is_refused(self):
        error = self.status(token="carol-token", expect=403)
        self.assertEqual(error["error"], "forbidden")
        self.assertIn("carol", error["message"])

    def test_a_project_not_served_here_is_not_found(self):
        self.assertEqual(self.status(project=OTHER_PROJECT, expect=404)["error"], "not_found")

    def test_a_malformed_project_is_a_bad_request(self):
        response = self.api.get("/projects/-bad/repo/status", token="alice-token", valid_request=False)
        self.assertEqual(response.status_code, 400)

    def test_when_github_cannot_say_who_is_calling_it_answers_503(self):
        self.github.fail["/user"] = 502
        self.assertEqual(self.status(expect=503)["error"], "unavailable")

    def test_the_callers_token_is_never_sent_anywhere_but_github(self):
        self.status()
        # The service's own requests to GitHub use the app's tokens; only GET /user carries the caller's.
        self.assertIn(("GET", "/user"), self.github.requests)
        self.assertFalse(any("alice-token" in path for _, path in self.version.requests))


class DeliveriesTest(ServiceTestCase):
    def test_a_delivery_with_a_wrong_or_missing_signature_is_refused(self):
        raw = json.dumps(self.push_event()).encode()
        for signature in ("sha256=" + "0" * 64, sign(raw, b"another-secret"), "sha1=abc"):
            with self.subTest(signature=signature):
                response = self.deliver("push", self.push_event(), signature=signature)
                self.assertEqual(response.status_code, 401)

    def test_without_a_webhook_secret_every_delivery_is_refused(self):
        self.restart(self.make_settings(webhook_secret=None))
        self.assertEqual(self.deliver("push", self.push_event()).status_code, 401)

    def test_a_delivery_that_is_not_json_is_a_bad_request(self):
        raw = b"not json"
        response = self.api.post("/webhooks/github", data=raw, content_type="application/json", valid_request=False,
                                 headers={"X-GitHub-Event": "push", "X-Hub-Signature-256": sign(raw)})
        self.assertEqual(response.status_code, 400)

    def test_a_delivery_that_names_no_repository_marks_nothing(self):
        response = self.deliver("ping", {"zen": "Keep it logically awesome."})
        self.assertEqual(response.get_json(), {"project": None, "stale": False})
