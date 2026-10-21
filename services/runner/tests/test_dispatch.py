"""C3 and command-center/D22, D28: who may dispatch, what is refused, and that each refusal names what exists.

Every call goes through the WSGI app and is checked against openapi.yaml as well.
"""

import threading
import unittest

from runner.api import Api
from tests.contract import ContractClient
from tests.fakes import CONCERN, OTHER, PROJECT, dispatch_body, make_runner

THIRD = "command-center/app-agents"
FOURTH = "command-center/notifications"


class Base(unittest.TestCase):
    config = {}

    def setUp(self):
        self.dispatcher, self.store, self.github, self.launcher, self.clock = make_runner(self, **self.config)
        self.client = ContractClient(self, Api(self.dispatcher))

    def dispatch(self, token="tok-juan", **body):
        return self.client.call("POST", "/sessions", dispatch_body(**body), token=token)

    def started(self, token="tok-juan", **body):
        response = self.dispatch(token, **body)
        self.assertEqual(response.status, 201, response)
        return response.json


class SponsorTest(Base):
    """The sponsor is the caller, read with GET /user on their token, and a collaborator (D28)."""

    def test_the_sponsor_is_the_login_behind_the_token(self):
        self.assertEqual(self.started("tok-ana")["sponsor"], "ana")

    def test_the_callers_token_is_used_only_to_ask_github_who_they_are(self):
        self.started("tok-juan")
        with_token = [call for call in self.github.calls if "tok-juan" in call]
        self.assertEqual(with_token, [("login", "tok-juan")])
        self.assertIn(("is_collaborator", "juan"), self.github.calls)

    def test_a_sponsor_in_the_body_is_refused_not_believed(self):
        response = self.dispatch("tok-juan", sponsor="ana")
        self.assertEqual(response.status, 400)
        self.assertEqual(self.store.list(state="all"), [])

    def test_an_unknown_token_is_401_and_a_non_collaborator_403_and_neither_starts_anything(self):
        self.assertEqual(self.dispatch("tok-forged").status, 401)
        self.assertEqual(self.dispatch("tok-out").status, 403)
        self.assertEqual(self.launcher.launched, [])
        self.assertEqual(self.store.list(state="all"), [])

    def test_every_read_needs_a_collaborator_too(self):
        sid = self.started()["id"]
        for path in ("/sessions", f"/sessions/{sid}"):
            self.assertEqual(self.client.call("GET", path, token="tok-out").status, 403)
        self.assertEqual(self.client.call("GET", "/estimates", token="tok-out", query={"skill": "loop-build"}).status,
                         403)


class ValidationTest(Base):
    def test_only_the_configured_project_is_served(self):
        response = self.dispatch(project="someone/elsewhere")
        self.assertEqual((response.status, response.json["error"]), (422, "unknown-project"))

    def test_the_concern_must_exist_on_main(self):
        response = self.dispatch(concern="command-center/nothing-here")
        self.assertEqual((response.status, response.json["error"]), (422, "unknown-concern"))
        self.assertIn("command-center/nothing-here", response.json["message"])

    def test_the_plugin_release_must_be_a_tag(self):
        response = self.dispatch(plugin_release="v9.9.9")
        self.assertEqual((response.status, response.json["error"]), (422, "unknown-release"))
        self.assertIn("v9.9.9", response.json["message"])

    def test_the_model_comes_from_the_skill_to_model_map(self):
        self.assertEqual(self.started(skill="loop-status")["model"], "claude-sonnet-5-5")
        self.assertEqual(self.started(skill="loop-build", concern=OTHER)["model"], "claude-opus-5-5")

    def test_the_session_records_what_was_dispatched(self):
        session = self.started(arguments="--ready", budget_usd=1.5)
        self.assertEqual((session["skill"], session["concern"], session["arguments"], session["budget_usd"],
                          session["plugin_release"], session["branch"]),
                         ("loop-build", CONCERN, "--ready", 1.5, "v0.3.0", CONCERN))
        self.assertEqual(self.launcher.launched, [session["id"]])


class SkillModelOverrideTest(Base):
    config = {"skill_models": {"loop-status": "claude-opus-5-5", "loop-design": "claude-opus-5-5",
                               "loop-build": "claude-sonnet-5-5", "loop-prove": "claude-opus-5-5"}}

    def test_changing_the_map_is_a_config_change(self):
        self.assertEqual(self.started(skill="loop-build")["model"], "claude-sonnet-5-5")


class OpenPullRequestTest(Base):
    """C3: a concern with an open pull request is refused, and the refusal names the pull request."""

    def test_a_pull_request_from_the_concerns_branch_refuses_the_dispatch(self):
        self.github.open_pr(17, CONCERN)
        response = self.dispatch()
        self.assertEqual(response.status, 409)
        self.assertEqual(response.json["refused"], "open-pull-request")
        self.assertEqual([p["number"] for p in response.json["pull_requests"]], [17])
        self.assertIn("#17", response.json["message"])
        self.assertIn(f"https://github.com/{PROJECT}/pull/17", response.json["message"])
        self.assertEqual(self.launcher.launched, [])

    def test_a_pull_request_whose_body_carries_the_concern_trailer_refuses_it_too(self):
        self.github.open_pr(18, "docs/command-center-runner", body=f"Some work.\n\nConcern: {CONCERN}\n")
        response = self.dispatch()
        self.assertEqual((response.status, response.json["refused"]), (409, "open-pull-request"))
        self.assertEqual(response.json["pull_requests"][0]["head"], "docs/command-center-runner")

    def test_another_concerns_pull_request_does_not(self):
        self.github.open_pr(19, OTHER, body=f"Concern: {OTHER}\nMentions {CONCERN}-extra in passing.\n")
        self.github.open_pr(20, f"{CONCERN}-extra", body=f"Concern: {CONCERN}-extra\n")
        self.assertEqual(self.dispatch().status, 201)


class RunningSessionTest(Base):
    """C3: a concern with a running session is refused, whoever sponsors it, and the refusal names the session."""

    def test_a_second_dispatch_on_the_same_concern_is_refused_naming_the_session(self):
        first = self.started("tok-juan")
        response = self.dispatch("tok-ana")
        self.assertEqual(response.status, 409)
        self.assertEqual(response.json["refused"], "running-session")
        self.assertEqual([s["id"] for s in response.json["sessions"]], [first["id"]])
        self.assertIn(first["id"], response.json["message"])
        self.assertIn("juan", response.json["message"])
        self.assertEqual(self.launcher.launched, [first["id"]])

    def test_a_stopping_session_still_holds_the_concern(self):
        first = self.started()
        self.client.call("POST", f"/sessions/{first['id']}/stop", token="tok-juan")
        self.assertEqual(self.dispatch().json["refused"], "running-session")

    def test_once_it_ends_the_concern_can_be_dispatched_again(self):
        first = self.started()
        self.store.finish(first["id"], "completed", None, [], self.clock().isoformat())
        self.assertEqual(self.dispatch().status, 201)

    def test_a_session_whose_job_stopped_publishing_is_given_up_and_frees_the_concern(self):
        first = self.started()
        self.clock.advance(self.dispatcher.config.lost_after_s + 1)
        second = self.dispatch()
        self.assertEqual(second.status, 201, second)
        old = self.client.call("GET", f"/sessions/{first['id']}", token="tok-juan").json
        self.assertEqual((old["state"], old["outcome"]), ("ended", "lost"))

    def test_a_session_that_publishes_keeps_its_claim(self):
        first = self.started()
        for _ in range(4):
            self.clock.advance(self.dispatcher.config.lost_after_s / 2)
            self.store.publish(first["id"], None, self.clock().isoformat())
        self.assertEqual(self.dispatch().json["refused"], "running-session")


class SponsorCapTest(Base):
    """C3 and D22: a sponsor may run at most the cap in the runner's config, 3 by default."""

    def test_the_fourth_running_session_is_refused_naming_the_three(self):
        running = [self.started(concern=c)["id"] for c in (CONCERN, OTHER, THIRD)]
        response = self.dispatch(concern=FOURTH)
        self.assertEqual(response.status, 409)
        self.assertEqual(response.json["refused"], "sponsor-cap")
        self.assertEqual(response.json["cap"], 3)
        self.assertEqual(sorted(s["id"] for s in response.json["sessions"]), sorted(running))
        for sid in running:
            self.assertIn(sid, response.json["message"])

    def test_the_cap_is_per_sponsor(self):
        for c in (CONCERN, OTHER, THIRD):
            self.started("tok-juan", concern=c)
        self.assertEqual(self.dispatch("tok-ana", concern=FOURTH).status, 201)

    def test_ended_sessions_do_not_count(self):
        sessions = [self.started(concern=c)["id"] for c in (CONCERN, OTHER, THIRD)]
        self.store.finish(sessions[0], "budget", None, [], self.clock().isoformat())
        self.assertEqual(self.dispatch(concern=FOURTH).status, 201)

    def test_the_list_reports_the_cap(self):
        self.assertEqual(self.client.call("GET", "/sessions", token="tok-juan").json["cap_per_sponsor"], 3)


class LoweredCapTest(Base):
    config = {"cap_per_sponsor": 1}

    def test_a_cap_lowered_to_one_refuses_the_second_session(self):
        first = self.started(concern=CONCERN)
        response = self.dispatch(concern=OTHER)
        self.assertEqual((response.status, response.json["refused"], response.json["cap"]), (409, "sponsor-cap", 1))
        self.assertEqual([s["id"] for s in response.json["sessions"]], [first["id"]])


class AtomicClaimTest(Base):
    """Two dispatches at once cannot both start: the claim is one transaction in the store."""

    def race(self, bodies, tokens):
        barrier = threading.Barrier(len(bodies))
        original = self.github.open_pull_requests

        def both_pass_the_pull_request_check():
            result = original()
            barrier.wait(timeout=5)
            return result

        self.github.open_pull_requests = both_pass_the_pull_request_check
        results = [None] * len(bodies)

        def go(i):
            results[i] = self.client.call("POST", "/sessions", bodies[i], token=tokens[i])

        threads = [threading.Thread(target=go, args=(i,)) for i in range(len(bodies))]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)
        return sorted(r.status for r in results), results

    def test_two_dispatches_on_one_concern_at_once_start_one_session(self):
        statuses, results = self.race([dispatch_body(), dispatch_body()], ["tok-juan", "tok-ana"])
        self.assertEqual(statuses, [201, 409])
        self.assertEqual(len(self.store.list()), 1)
        self.assertEqual(len(self.launcher.launched), 1)

    def test_two_dispatches_at_the_cap_at_once_start_one(self):
        self.started(concern=CONCERN)
        self.started(concern=OTHER)
        statuses, _ = self.race([dispatch_body(concern=THIRD), dispatch_body(concern=FOURTH)], ["tok-juan"] * 2)
        self.assertEqual(statuses, [201, 409])
        self.assertEqual(len(self.store.list(sponsor="juan")), 3)


class LaunchFailureTest(Base):
    def test_a_job_that_cannot_start_ends_the_session_and_frees_the_concern(self):
        self.launcher.fail = True
        response = self.dispatch()
        self.assertEqual((response.status, response.json["error"]), (502, "launch-failed"))
        [session] = self.store.list(state="all")
        self.assertEqual((session.state, session.outcome), ("ended", "error"))
        self.launcher.fail = False
        self.assertEqual(self.dispatch().status, 201)


class StopTest(Base):
    def test_the_sponsor_stops_their_session_and_it_is_stopping(self):
        sid = self.started()["id"]
        response = self.client.call("POST", f"/sessions/{sid}/stop", token="tok-juan")
        self.assertEqual((response.status, response.json["state"]), (202, "stopping"))
        self.assertTrue(self.store.publish(sid, None, self.clock().isoformat()))

    def test_no_one_else_may_stop_it(self):
        sid = self.started("tok-juan")["id"]
        response = self.client.call("POST", f"/sessions/{sid}/stop", token="tok-ana")
        self.assertEqual((response.status, response.json["error"]), (403, "not-the-sponsor"))
        self.assertEqual(self.store.get(sid).state, "starting")

    def test_an_ended_session_cannot_be_stopped(self):
        sid = self.started()["id"]
        self.store.finish(sid, "completed", None, [], self.clock().isoformat())
        self.assertEqual(self.client.call("POST", f"/sessions/{sid}/stop", token="tok-juan").status, 409)


class ListTest(Base):
    def test_every_sponsors_running_sessions_are_listed_with_filters(self):
        a = self.started("tok-juan", concern=CONCERN)["id"]
        b = self.started("tok-ana", concern=OTHER)["id"]
        listed = lambda **q: [s["id"] for s in self.client.call("GET", "/sessions", token="tok-juan", query=q)
                              .json["sessions"]]
        self.assertEqual(sorted(listed()), sorted([a, b]))
        self.assertEqual(listed(sponsor="ana"), [b])
        self.assertEqual(listed(project="someone/elsewhere"), [])
        self.store.finish(a, "completed", None, [], self.clock().isoformat())
        self.assertEqual(listed(), [b])
        self.assertEqual(sorted(listed(state="all")), sorted([a, b]))


if __name__ == "__main__":
    unittest.main()
