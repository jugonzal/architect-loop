"""The API is the one in services/status/openapi.yaml (command-center/D55), and its status document is the one
plugin/skills/loop-status/scripts/status.schema.json describes (command-center/D15, D48).

Every API test in this folder goes through support.ContractClient, which fails a test whose response, or whose
request when it is meant to be valid, does not match openapi.yaml; a 200 from the status operation is checked
against the status schema itself. These tests add that the document is valid OpenAPI, that the service routes
exactly the operations it documents, and that one call to each operation answers as documented.
"""

import re
import unittest

from openapi_core import OpenAPI

from support import EXERCISED, PROJECT, SPEC_PATH, ServiceTestCase, spec_operations, status_path


def routed_operations(app):
    ops = set()
    for rule in app.url_map.iter_rules():
        if rule.endpoint == "static":
            continue
        path = re.sub(r"<(?:[^:>]+:)?([^>]+)>", r"{\1}", rule.rule)
        for method in rule.methods - {"HEAD", "OPTIONS"}:
            ops.add((method, path))
    return ops


class ContractTest(ServiceTestCase):
    def test_the_document_is_valid_openapi(self):
        OpenAPI.from_file_path(SPEC_PATH).check_spec()

    def test_the_service_routes_exactly_the_documented_operations(self):
        self.assertEqual(routed_operations(self.app), spec_operations())

    def test_every_operation_answers_as_documented(self):
        self.assertEqual(self.api.get("/version").status_code, 200)
        response = self.api.get(status_path(), token="alice-token")
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        self.assertEqual(self.deliver("push", self.push_event()).status_code, 200)
        self.assertTrue(spec_operations() <= EXERCISED, spec_operations() - EXERCISED)

    def test_the_status_document_is_the_projects_and_validates_against_the_status_schema(self):
        # ContractClient has already validated it against status.schema.json, through openapi.yaml's $ref.
        doc = self.status()
        self.assertEqual(doc["schema_version"], 1)
        self.assertEqual(doc["project"], PROJECT)
        self.assertEqual([loop["id"] for loop in doc["loops"]], ["sandbox"])

    def test_version_needs_no_credentials_and_names_the_commit(self):
        response = self.api.get("/version")
        self.assertEqual(response.get_json(), {"commit": "0123456789abcdef0123456789abcdef01234567"})

    def test_an_unknown_path_answers_json(self):
        client = self.app.test_client()
        response = client.get("/nowhere")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.get_json()["error"], "not_found")
        response = client.post(status_path())
        self.assertEqual(response.status_code, 405)
        self.assertEqual(response.get_json()["error"], "bad_request")


if __name__ == "__main__":
    unittest.main()
