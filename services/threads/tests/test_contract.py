"""C1: the API is the one in services/threads/openapi.yaml (command-center/D29).

Every API test in this folder goes through support.ContractClient, which fails a test whose response, or whose
request when it is meant to be valid, does not match openapi.yaml. These tests add that the document is valid
OpenAPI, that the service routes exactly the operations it documents, and that one call to each operation answers
as documented.
"""

import json
import re
import unittest

from openapi_core import OpenAPI

from support import (
    EXERCISED, RUNNER_TOKEN, SPEC_PATH, ApiTestCase, base, concern_thread, loop_thread, review_comment_event,
    session_thread, sign, spec_operations,
)


def routed_operations(app):
    ops = set()
    for rule in app.url_map.iter_rules():
        if rule.endpoint == "static":
            continue
        path = re.sub(r"<(?:[^:>]+:)?([^>]+)>", r"{\1}", rule.rule)
        for method in rule.methods - {"HEAD", "OPTIONS"}:
            ops.add((method, path))
    return ops


class ContractTest(ApiTestCase):
    def test_the_document_is_valid_openapi(self):
        OpenAPI.from_file_path(SPEC_PATH).check_spec()

    def test_the_service_routes_exactly_the_documented_operations(self):
        self.assertEqual(routed_operations(self.app), spec_operations())

    def test_every_operation_answers_as_documented(self):
        calls = []

        def call(method, path, expect, **kw):
            response = self.api.call(method, path, **kw)
            self.assertEqual(response.status_code, expect, (method, path, response.get_json()))
            calls.append(method)
            return response.get_json()

        call("GET", "/version", 200)
        for thread in (loop_thread(), concern_thread(), session_thread()):
            call("GET", thread, 200, token="alice-token")
            call("POST", f"{thread}/messages", 201, token="alice-token", json_body={"body": "hi"})
            call("GET", f"{thread}/messages", 200, token="alice-token")
            call("PUT", f"{thread}/watchers/me", 200, token="alice-token")
            call("DELETE", f"{thread}/watchers/me", 200, token="alice-token")
        posted = call("POST", f"{session_thread()}/messages", 201, token=RUNNER_TOKEN,
                      json_body={"body": "started", "kind": "milestone", "sponsor": "alice"})
        call("GET", f"{session_thread()}/messages?after=1&kind=milestone", 200, token=RUNNER_TOKEN)
        call("GET", session_thread(), 200, token=RUNNER_TOKEN)
        call("PUT", f"{base()}/messages/{posted['id']}/record-marks/me", 200, token="alice-token")
        call("GET", f"{base()}/messages/{posted['id']}", 200, token="alice-token")
        call("DELETE", f"{base()}/messages/{posted['id']}/record-marks/me", 200, token="alice-token")
        result = call("POST", "/webhooks/github", 200, **self.signed("pull_request_review_comment",
                                                                     review_comment_event()))
        self.assertEqual(len(result["mirrored"]), 1)
        self.assertTrue(spec_operations() <= EXERCISED, spec_operations() - EXERCISED)

    def test_version_needs_no_credentials_and_names_the_commit(self):
        response = self.api.get("/version")
        self.assertEqual(response.get_json(), {"commit": "0123456789abcdef0123456789abcdef01234567"})

    def test_an_unknown_path_answers_json(self):
        response = self.app.test_client().get("/nowhere")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.get_json()["error"], "not_found")
        response = self.app.test_client().patch(concern_thread())
        self.assertEqual(response.status_code, 405)
        self.assertEqual(response.get_json()["error"], "bad_request")

    def signed(self, event, payload):
        raw = json.dumps(payload).encode()
        return {"data": raw, "content_type": "application/json",
                "headers": {"X-GitHub-Event": event, "X-GitHub-Delivery": "d-1", "X-Hub-Signature-256": sign(raw)}}


if __name__ == "__main__":
    unittest.main()
