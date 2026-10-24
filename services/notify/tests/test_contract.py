"""The API is the one in services/notify/openapi.yaml (command-center/D55).

Every API test in this folder goes through support.ContractClient, which fails a test whose response, or whose
request when it is meant to be valid, does not match openapi.yaml. These tests add that the document is valid
OpenAPI, that the service routes exactly the operations it documents, and that one call to each operation answers
as documented.
"""

import re
import unittest

from openapi_core import OpenAPI

from support import COMMIT, EXERCISED, SPEC_PATH, Harness, base, push_token, spec_operations


def routed_operations(app):
    ops = set()
    for rule in app.url_map.iter_rules():
        if rule.endpoint == "static":
            continue
        path = re.sub(r"<(?:[^:>]+:)?([^>]+)>", r"{\1}", rule.rule)
        for method in rule.methods - {"HEAD", "OPTIONS"}:
            ops.add((method, path))
    return ops


class ContractTest(Harness, unittest.TestCase):
    def setUp(self):
        self.make()

    def test_the_document_is_valid_openapi(self):
        OpenAPI.from_file_path(SPEC_PATH).check_spec()

    def test_the_service_routes_exactly_the_documented_operations(self):
        self.assertEqual(routed_operations(self.app), spec_operations())

    def test_every_operation_answers_as_documented(self):
        def call(method, path, expect, **kw):
            response = self.api.call(method, path, **kw)
            self.assertEqual(response.status_code, expect, (method, path, response.get_json()))
            return response.get_json()

        call("GET", "/version", 200)
        device = call("POST", f"{base()}/devices", 200, token="alice-token",
                      json_body={"token": push_token("phone"), "platform": "android", "timezone": "Europe/Lisbon"})
        call("GET", f"{base()}/devices", 200, token="alice-token")
        call("POST", f"{base()}/test-notification", 200, token="alice-token")
        call("POST", f"{base()}/test-notification", 429, token="alice-token")
        call("GET", f"{base()}/settings/me", 200, token="alice-token")
        call("PUT", f"{base()}/settings/me", 200, token="alice-token",
             json_body={"timezone": "UTC", "digest_time": None, "quiet_hours": {"start": "22:00", "end": "07:00"}})
        call("PUT", f"{base()}/settings/me", 400, token="alice-token", valid_request=False,
             json_body={"timezone": "Mars/Olympus", "digest_time": "9", "quiet_hours": None})
        call("DELETE", f"{base()}/devices/{device['id']}", 204, token="alice-token")
        call("DELETE", f"{base()}/devices/{device['id']}", 404, token="alice-token")
        call("GET", f"{base()}/devices", 401, valid_request=False)
        call("GET", f"{base('example/unknown')}/devices", 404, token="alice-token")
        self.assertTrue(spec_operations() <= EXERCISED, spec_operations() - EXERCISED)

    def test_version_needs_no_credentials_and_names_the_commit(self):
        self.assertEqual(self.api.get("/version").get_json(), {"commit": COMMIT})

    def test_no_answer_holds_a_push_token(self):
        self.register("alice", "phone")
        for path in ("/devices",):
            body = self.api.get(f"{base()}{path}", token="alice-token").get_data(as_text=True)
            self.assertNotIn("ExponentPushToken", body)

    def test_an_unknown_path_answers_json(self):
        response = self.app.test_client().get("/nowhere")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.get_json()["error"], "not_found")
        response = self.app.test_client().patch(f"{base()}/devices")
        self.assertEqual(response.status_code, 405)
        self.assertEqual(response.get_json()["error"], "bad_request")


if __name__ == "__main__":
    unittest.main()
