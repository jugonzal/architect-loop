"""C1, before the merge: the runner's API is the one in services/runner/openapi.yaml (command-center/D29).

Every operation the spec lists is routed and every route is in the spec; every response the spec documents is
produced by some scenario here, and every answer any test gets is checked against the spec's schema for that
status. The app clients (app-agents, app-inbox, app-threads) generate their code from the same file.
"""

import unittest

from openapi_spec_validator import validate

from runner.api import Api
from runner.config import SCOPES, SKILLS
from tests.contract import SPEC, ContractClient, documented, request_errors
from tests.fakes import CONCERN, ENVIRONMENT, LOOP, OTHER, PROJECT, dispatch_body, make_runner, scoped_body

SID = "0" * 31 + "1"


def runner(testcase, **config):
    dispatcher, store, github, launcher, clock = make_runner(testcase, **config)
    client = ContractClient(testcase, Api(dispatcher))
    return client, dispatcher, store, github, launcher, clock


def dispatched(testcase, **config):
    client, dispatcher, store, github, launcher, clock = runner(testcase, **config)
    response = client.call("POST", "/sessions", dispatch_body(), token="tok-juan")
    testcase.assertEqual(response.status, 201, response)
    return client, response.json["id"], github, store, launcher


def ended(testcase):
    client, sid, github, store, launcher = dispatched(testcase)
    store.finish(sid, "completed", None, [], store.get(sid).created_at)
    return client, sid


# One scenario per documented (method, path, status). Each returns the response it got.
SCENARIOS = {
    ("GET", "/version", 200): lambda t: runner(t)[0].call("GET", "/version"),
    ("GET", "/version", 503): lambda t: runner(t, commit=None)[0].call("GET", "/version"),

    ("POST", "/sessions", 201): lambda t: runner(t)[0].call("POST", "/sessions", dispatch_body(), token="tok-juan"),
    ("POST", "/sessions", 400): lambda t: runner(t)[0].call(
        "POST", "/sessions", dispatch_body(budget_usd=0), token="tok-juan"),
    ("POST", "/sessions", 401): lambda t: runner(t)[0].call("POST", "/sessions", dispatch_body()),
    ("POST", "/sessions", 403): lambda t: runner(t)[0].call("POST", "/sessions", dispatch_body(), token="tok-out"),
    ("POST", "/sessions", 409): lambda t: _open_pr_then_dispatch(t),
    ("POST", "/sessions", 422): lambda t: runner(t)[0].call(
        "POST", "/sessions", dispatch_body(concern="command-center/nothing-here"), token="tok-juan"),
    ("POST", "/sessions", 502): lambda t: _launch_fails(t),

    ("GET", "/sessions", 200): lambda t: dispatched(t)[0].call("GET", "/sessions", token="tok-ana"),
    ("GET", "/sessions", 400): lambda t: runner(t)[0].call("GET", "/sessions", token="tok-juan",
                                                          query={"state": "sideways"}),
    ("GET", "/sessions", 401): lambda t: runner(t)[0].call("GET", "/sessions", token="tok-nobody"),
    ("GET", "/sessions", 403): lambda t: runner(t)[0].call("GET", "/sessions", token="tok-out"),
    ("GET", "/sessions", 502): lambda t: _github_down(t, "GET", "/sessions"),

    ("GET", "/sessions/{id}", 200): lambda t: _get(t),
    ("GET", "/sessions/{id}", 401): lambda t: runner(t)[0].call("GET", f"/sessions/{SID}"),
    ("GET", "/sessions/{id}", 403): lambda t: runner(t)[0].call("GET", f"/sessions/{SID}", token="tok-out"),
    ("GET", "/sessions/{id}", 404): lambda t: runner(t)[0].call("GET", f"/sessions/{SID}", token="tok-juan"),
    ("GET", "/sessions/{id}", 502): lambda t: _github_down(t, "GET", f"/sessions/{SID}"),

    ("POST", "/sessions/{id}/stop", 202): lambda t: _stop(t, "tok-juan"),
    ("POST", "/sessions/{id}/stop", 401): lambda t: runner(t)[0].call("POST", f"/sessions/{SID}/stop"),
    ("POST", "/sessions/{id}/stop", 403): lambda t: _stop(t, "tok-ana"),
    ("POST", "/sessions/{id}/stop", 404): lambda t: runner(t)[0].call("POST", f"/sessions/{SID}/stop",
                                                                      token="tok-juan"),
    ("POST", "/sessions/{id}/stop", 409): lambda t: _stop_ended(t),
    ("POST", "/sessions/{id}/stop", 502): lambda t: _github_down(t, "POST", f"/sessions/{SID}/stop"),

    ("GET", "/estimates", 200): lambda t: runner(t)[0].call("GET", "/estimates", token="tok-juan",
                                                           query={"skill": "loop-build"}),
    ("GET", "/estimates", 400): lambda t: runner(t)[0].call("GET", "/estimates", token="tok-juan"),
    ("GET", "/estimates", 401): lambda t: runner(t)[0].call("GET", "/estimates", query={"skill": "loop-build"}),
    ("GET", "/estimates", 403): lambda t: runner(t)[0].call("GET", "/estimates", token="tok-out",
                                                           query={"skill": "loop-build"}),
    ("GET", "/estimates", 502): lambda t: _github_down(t, "GET", "/estimates", query={"skill": "loop-build"}),
}


def _open_pr_then_dispatch(t):
    client, _, _, github, _, _ = runner(t)
    github.open_pr(17, CONCERN)
    return client.call("POST", "/sessions", dispatch_body(), token="tok-juan")


def _launch_fails(t):
    client, _, _, _, launcher, _ = runner(t)
    launcher.fail = True
    return client.call("POST", "/sessions", dispatch_body(), token="tok-juan")


def _github_down(t, method, path, query=None):
    client, _, _, github, _, _ = runner(t)
    github.down = True
    return client.call(method, path, token="tok-juan", query=query)


def _get(t):
    client, sid, *_ = dispatched(t)
    return client.call("GET", f"/sessions/{sid}", token="tok-ana")


def _stop(t, token):
    client, sid, *_ = dispatched(t)
    return client.call("POST", f"/sessions/{sid}/stop", token=token)


def _stop_ended(t):
    client, sid = ended(t)
    return client.call("POST", f"/sessions/{sid}/stop", token="tok-juan")


class SpecTest(unittest.TestCase):
    def test_the_spec_is_valid_openapi_3_1(self):
        self.assertEqual(SPEC["openapi"], "3.1.0")
        validate(SPEC)

    def test_every_operation_in_the_spec_is_routed_and_every_route_is_in_the_spec(self):
        in_spec = {(method.upper(), template) for template, item in SPEC["paths"].items() for method in item}
        self.assertEqual(in_spec, {(method, template) for method, template, _ in Api.ROUTES})

    def test_every_documented_response_has_a_scenario(self):
        self.assertEqual(set(documented()), set(SCENARIOS))

    def test_every_scenario_answers_its_status_with_a_body_that_matches_the_spec(self):
        for (method, template, status), scenario in sorted(SCENARIOS.items()):
            with self.subTest(f"{method} {template} {status}"):
                response = scenario(self)
                self.assertEqual(response.status, status, response)
                self.assertIn((method, template, status), ContractClient.exercised)

    def test_every_error_names_its_kind(self):
        response = SCENARIOS[("POST", "/sessions", 401)](self)
        self.assertEqual(response.json["error"], "unauthenticated")
        response = SCENARIOS[("POST", "/sessions", 403)](self)
        self.assertEqual(response.json["error"], "not-a-collaborator")


class RequestContractTest(unittest.TestCase):
    """What the spec accepts as a dispatch is what the runner accepts."""

    VALID = [
        dispatch_body(),
        dispatch_body(skill="loop-status", arguments="--json"),
        dispatch_body(concern=OTHER, budget_usd=0.05),
        {k: v for k, v in dispatch_body().items() if k != "arguments"},
        dispatch_body(concern=None, skill="loop-ship", environment=ENVIRONMENT),
        dispatch_body(concern=None, skill="loop-ship", environment="main", arguments="--verify"),
        dispatch_body(concern=None, skill="loop-status", loop=LOOP, arguments="--json"),
        dispatch_body(concern=None, skill="loop-design", loop=LOOP),
    ]
    INVALID = [
        dispatch_body(skill="loop-ship"),
        dispatch_body(skill="/loop-build"),
        dispatch_body(concern="session-runner"),
        dispatch_body(concern="Command-Center/x"),
        dispatch_body(budget_usd=0),
        dispatch_body(budget_usd=-1),
        dispatch_body(budget_usd="2"),
        dispatch_body(plugin_release="main"),
        dispatch_body(plugin_release="0.3.0"),
        dispatch_body(project="not a project"),
        dispatch_body(arguments="x" * 2001),
        dispatch_body(sponsor="ana"),
        {k: v for k, v in dispatch_body().items() if k != "budget_usd"},
        {k: v for k, v in dispatch_body().items() if k != "plugin_release"},
        {k: v for k, v in dispatch_body().items() if k != "project"},
        [],
        "loop-build",
        dispatch_body(concern=None),
        dispatch_body(loop=LOOP),
        dispatch_body(environment=ENVIRONMENT),
        dispatch_body(concern=None, skill="loop-status", loop=LOOP, environment=ENVIRONMENT),
        dispatch_body(concern=None, skill="loop-build", loop=LOOP),
        dispatch_body(concern=None, skill="loop-prove", loop=LOOP),
        dispatch_body(concern=None, skill="loop-ship", loop=LOOP),
        dispatch_body(concern=None, skill="loop-status", environment=ENVIRONMENT),
        dispatch_body(concern=None, skill="loop-design", environment=ENVIRONMENT),
        dispatch_body(concern=None, skill="loop-ship", environment="Staging/Runner"),
        dispatch_body(concern=None, skill="loop-ship", environment="staging/runner/x"),
        dispatch_body(concern=None, skill="loop-ship", environment=""),
        dispatch_body(concern=None, skill="loop-status", loop="command-center/x"),
        dispatch_body(concern=None, skill="loop-status", loop=""),
        dispatch_body(concern=None, skill="loop-status", loop=7),
    ]

    def test_valid_dispatches_match_the_spec_and_start(self):
        for body in self.VALID:
            with self.subTest(body=body):
                self.assertEqual(request_errors("POST", "/sessions", body), [])
                client = runner(self)[0]
                self.assertEqual(client.call("POST", "/sessions", body, token="tok-juan").status, 201)

    def test_invalid_dispatches_fail_the_spec_and_are_refused_with_400(self):
        for body in self.INVALID:
            with self.subTest(body=body):
                self.assertNotEqual(request_errors("POST", "/sessions", body), [])
                response = runner(self)[0].call("POST", "/sessions", body, token="tok-juan")
                self.assertEqual(response.status, 400, response)
                self.assertEqual(response.json["error"], "invalid-request")

    def test_the_spec_and_the_runner_agree_on_every_skill_and_target(self):
        """runner-dispatch C3: `loop-design`, `loop-build`, `loop-prove` and `loop-status` on a concern,
        `loop-design` and `loop-status` on a loop, `loop-ship` on an environment, and nothing else."""
        for scope in SCOPES:
            for skill in SKILLS:
                with self.subTest(scope=scope, skill=skill):
                    body = scoped_body(scope, skill)
                    allowed = skill in SCOPES[scope]
                    self.assertEqual(request_errors("POST", "/sessions", body) == [], allowed)
                    status = runner(self)[0].call("POST", "/sessions", body, token="tok-juan").status
                    self.assertEqual(status, 201 if allowed else 400)
        self.assertEqual(set(SPEC["components"]["schemas"]["Skill"]["enum"]), set(SKILLS))

    def test_a_budget_above_the_ceiling_is_a_valid_request_refused_as_a_refusal(self):
        """The ceiling is config (session-runner D8), so the spec leaves it out of the request and documents the
        refusal instead."""
        body = dispatch_body(budget_usd=25.0)
        self.assertEqual(request_errors("POST", "/sessions", body), [])
        response = runner(self)[0].call("POST", "/sessions", body, token="tok-juan")
        self.assertEqual((response.status, response.json["refused"], response.json["ceiling_usd"]),
                         (409, "budget-ceiling", 10.0))

    def test_a_body_that_is_not_json_is_a_400(self):
        response = runner(self)[0].call("POST", "/sessions", raw=b"{not json", token="tok-juan")
        self.assertEqual(response.status, 400)


class RoundTripTest(unittest.TestCase):
    def test_a_dispatched_session_reads_back_the_same_and_is_listed(self):
        client, sid, *_ = dispatched(self)
        one = client.call("GET", f"/sessions/{sid}", token="tok-juan").json
        listed = client.call("GET", "/sessions", token="tok-juan").json
        self.assertEqual([s["id"] for s in listed["sessions"]], [sid])
        self.assertEqual(listed["sessions"][0], one)
        self.assertEqual(one["project"], PROJECT)
        self.assertEqual(one["branch"], CONCERN)
        self.assertEqual(one["state"], "starting")
        self.assertIsNone(one["outcome"])
        self.assertEqual(listed["cap_per_sponsor"], 3)

    def test_a_session_on_a_loop_or_an_environment_reads_back_the_same(self):
        client = runner(self)[0]
        for scope, skill in (("loop", "loop-status"), ("environment", "loop-ship")):
            with self.subTest(scope=scope):
                created = client.call("POST", "/sessions", scoped_body(scope, skill), token="tok-juan").json
                one = client.call("GET", f"/sessions/{created['id']}", token="tok-ana").json
                self.assertEqual(one, created)
                self.assertEqual((one["concern"], one["branch"], one["final_message"]), (None, "main", None))
                self.assertEqual(one[scope], LOOP if scope == "loop" else ENVIRONMENT)

    def test_the_estimate_names_a_release_a_dispatch_accepts(self):
        """latest-release C1: what the estimate names is what the app sends back, so the two schemas agree."""
        schemas = SPEC["components"]["schemas"]
        self.assertIn("plugin_release", schemas["EstimateAnswer"]["required"])
        self.assertEqual(schemas["EstimateAnswer"]["properties"]["plugin_release"]["pattern"],
                         schemas["DispatchRequest"]["properties"]["plugin_release"]["pattern"])
        client, _, _, github, _, _ = runner(self)
        github.releases = {"v0.3.0", "v0.4.0"}
        answer = client.call("GET", "/estimates", token="tok-juan", query={"skill": "loop-build"}).json
        body = dispatch_body(plugin_release=answer["plugin_release"])
        self.assertEqual(request_errors("POST", "/sessions", body), [])
        self.assertEqual(client.call("POST", "/sessions", body, token="tok-juan").json["plugin_release"], "v0.4.0")

    def test_the_location_header_names_the_session(self):
        client = runner(self)[0]
        response = client.call("POST", "/sessions", dispatch_body(), token="tok-juan")
        self.assertEqual(response.headers["Location"], f"/sessions/{response.json['id']}")

    def test_version_answers_the_commit_without_a_token(self):
        client = runner(self, commit="eee811990d7216fbc792c1e5eee32cb2bb4f82fb")[0]
        response = client.call("GET", "/version")
        self.assertEqual(response.json, {"commit": "eee811990d7216fbc792c1e5eee32cb2bb4f82fb"})

    def test_unknown_paths_and_methods_are_problems_not_crashes(self):
        client = runner(self)[0]
        self.assertEqual(client.call("GET", "/nowhere", token="tok-juan").status, 404)
        self.assertEqual(client.call("DELETE", "/sessions", token="tok-juan").status, 405)


if __name__ == "__main__":
    unittest.main()
