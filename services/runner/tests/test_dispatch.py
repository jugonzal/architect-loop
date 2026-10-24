"""Who may dispatch, on what, what is refused, and that each refusal names what exists: runner-dispatch C2
(session-runner C6, D6, D8), C3 (a concern, a loop or an environment) and command-center/D22, D28.

Every call goes through the WSGI app and is checked against openapi.yaml as well.
"""

import threading
import unittest

from runner.api import Api
from runner.config import SCOPES, SKILLS
from runner.github import GitHubError
from tests.contract import ContractClient
from tests.fakes import CONCERN, ENVIRONMENT, LOOP, OTHER, PROJECT, dispatch_body, make_runner, scoped_body

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

    def scoped(self, scope, skill, token="tok-juan", **extra):
        return self.client.call("POST", "/sessions", scoped_body(scope, skill, **extra), token=token)

    def started_on(self, scope, skill, token="tok-juan", **extra):
        response = self.scoped(scope, skill, token, **extra)
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
                               "loop-build": "claude-sonnet-5-5", "loop-prove": "claude-opus-5-5",
                               "loop-ship": "claude-opus-5-5"}}

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

    def test_a_design_dispatch_is_refused_too(self):
        self.github.open_pr(17, CONCERN)
        response = self.dispatch(skill="loop-design")
        self.assertEqual((response.status, response.json["refused"]), (409, "open-pull-request"))
        self.assertIn("#17", response.json["message"])

    def test_prove_and_status_are_admitted_beside_an_open_pull_request(self):
        """session-runner D6: so a proof can go into the open pull request's body."""
        self.github.open_pr(17, CONCERN)
        self.assertEqual(self.started(skill="loop-prove")["concern"], CONCERN)
        self.assertEqual(self.started(skill="loop-status")["concern"], CONCERN)
        self.assertEqual(len(self.launcher.launched), 2)


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

    def test_a_design_and_a_build_hold_the_concern_against_each_other(self):
        for running, second in (("loop-build", "loop-design"), ("loop-design", "loop-build")):
            with self.subTest(running=running, second=second):
                self.setUp()
                first = self.started("tok-juan", skill=running)
                response = self.dispatch("tok-ana", skill=second)
                self.assertEqual((response.status, response.json["refused"]), (409, "running-session"))
                self.assertEqual([s["id"] for s in response.json["sessions"]], [first["id"]])
                self.assertIn(first["id"], response.json["message"])

    def test_prove_and_status_run_beside_a_build(self):
        build = self.started("tok-juan", skill="loop-build")
        prove = self.started("tok-ana", skill="loop-prove")
        status = self.started("tok-ana", skill="loop-status")
        self.assertEqual(self.launcher.launched, [build["id"], prove["id"], status["id"]])

    def test_prove_and_status_hold_nothing(self):
        self.started("tok-juan", skill="loop-prove")
        self.started("tok-juan", skill="loop-status")
        self.started("tok-ana", skill="loop-prove")
        self.assertEqual(self.started("tok-ana", skill="loop-build")["skill"], "loop-build")

    def test_the_refusal_names_only_the_sessions_that_hold_the_concern(self):
        build = self.started("tok-juan", skill="loop-build")
        self.started("tok-ana", skill="loop-prove")
        response = self.dispatch("tok-ana", skill="loop-design")
        self.assertEqual([s["id"] for s in response.json["sessions"]], [build["id"]])


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

    def test_every_running_session_counts_whatever_its_skill(self):
        running = [self.started(skill=s)["id"] for s in ("loop-build", "loop-prove", "loop-status")]
        response = self.dispatch(skill="loop-prove", concern=OTHER)
        self.assertEqual((response.status, response.json["refused"]), (409, "sponsor-cap"))
        self.assertEqual(sorted(s["id"] for s in response.json["sessions"]), sorted(running))


class LoweredCapTest(Base):
    config = {"cap_per_sponsor": 1}

    def test_a_cap_lowered_to_one_refuses_the_second_session(self):
        first = self.started(concern=CONCERN)
        response = self.dispatch(concern=OTHER)
        self.assertEqual((response.status, response.json["refused"], response.json["cap"]), (409, "sponsor-cap", 1))
        self.assertEqual([s["id"] for s in response.json["sessions"]], [first["id"]])


class BudgetCeilingTest(Base):
    """session-runner D8: a budget above the ceiling in the runner's config, $10 by default, is refused, naming it."""

    def test_a_budget_above_the_ceiling_is_refused_naming_the_ceiling(self):
        response = self.dispatch(budget_usd=10.01)
        self.assertEqual(response.status, 409)
        self.assertEqual((response.json["refused"], response.json["ceiling_usd"]), ("budget-ceiling", 10.0))
        self.assertIn("$10.00", response.json["message"])
        self.assertIn("$10.01", response.json["message"])
        self.assertEqual((response.json["pull_requests"], response.json["sessions"]), ([], []))
        self.assertEqual(self.launcher.launched, [])
        self.assertEqual(self.store.list(state="all"), [])

    def test_a_budget_at_the_ceiling_is_admitted(self):
        self.assertEqual(self.started(budget_usd=10)["budget_usd"], 10.0)

    def test_the_ceiling_holds_for_every_skill(self):
        for skill in ("loop-design", "loop-build", "loop-prove", "loop-status"):
            with self.subTest(skill=skill):
                self.assertEqual(self.dispatch(skill=skill, budget_usd=50).json["refused"], "budget-ceiling")


class ScopeTest(Base):
    """runner-dispatch C3: a dispatch names exactly one of a concern, a loop or an environment, and one on a loop or
    an environment holds no concern and works from main."""

    def test_loop_ship_runs_on_an_environment_from_main(self):
        session = self.started_on("environment", "loop-ship", arguments="--verify")
        self.assertEqual((session["concern"], session["loop"], session["environment"], session["branch"]),
                         (None, None, ENVIRONMENT, "main"))
        self.assertEqual((session["model"], session["arguments"]), ("claude-opus-5-5", "--verify"))  # D5
        self.assertEqual(self.launcher.launched, [session["id"]])

    def test_loop_status_and_loop_design_run_on_a_loop_from_main(self):
        status = self.started_on("loop", "loop-status")
        design = self.started_on("loop", "loop-design")
        self.assertEqual((status["concern"], status["loop"], status["environment"], status["branch"]),
                         (None, LOOP, None, "main"))
        self.assertEqual((status["model"], design["model"]), ("claude-sonnet-5-5", "claude-opus-5-5"))

    def test_each_skill_runs_on_what_c3_lists_and_nothing_else(self):
        for scope in SCOPES:
            for skill in SKILLS:
                with self.subTest(scope=scope, skill=skill):
                    self.setUp()
                    response = self.scoped(scope, skill)
                    if skill in SCOPES[scope]:
                        self.assertEqual(response.status, 201, response)
                    else:
                        self.assertEqual((response.status, response.json["error"]), (400, "invalid-request"))
                        self.assertIn(skill, response.json["message"])
                        self.assertEqual(self.store.list(state="all"), [])

    def test_a_dispatch_names_exactly_one_target(self):
        for body in (dispatch_body(concern=None), dispatch_body(loop=LOOP),
                     dispatch_body(concern=None, skill="loop-status", loop=LOOP, environment=ENVIRONMENT)):
            with self.subTest(body=body):
                response = self.client.call("POST", "/sessions", body, token="tok-juan")
                self.assertEqual((response.status, response.json["error"]), (400, "invalid-request"))
                self.assertIn("exactly one", response.json["message"])

    def test_an_unknown_loop_is_refused_naming_it(self):
        response = self.client.call("POST", "/sessions",
                                    dispatch_body(concern=None, skill="loop-status", loop="nowhere"), token="tok-juan")
        self.assertEqual((response.status, response.json["error"]), (422, "unknown-loop"))
        self.assertIn("docs/loops/nowhere/README.md", response.json["message"])

    def test_an_unknown_environment_is_refused_naming_the_ones_loop_md_lists(self):
        response = self.client.call("POST", "/sessions", dispatch_body(concern=None, skill="loop-ship",
                                                                       environment="staging/runnr"), token="tok-juan")
        self.assertEqual((response.status, response.json["error"]), (422, "unknown-environment"))
        self.assertIn("staging/runnr", response.json["message"])
        self.assertIn("staging/runner", response.json["message"])
        self.assertEqual(self.launcher.launched, [])

    def test_a_loop_or_environment_dispatch_holds_no_concern(self):
        self.github.open_pr(17, CONCERN, body=f"Concern: {CONCERN}\n")
        self.started_on("loop", "loop-design", "tok-juan")
        self.started_on("loop", "loop-design", "tok-ana")
        self.started_on("environment", "loop-ship", "tok-juan")
        self.started_on("environment", "loop-ship", "tok-ana")
        self.assertNotIn(("open_pull_requests",), self.github.calls)  # nothing they could defer to
        self.github.pulls = []
        self.assertEqual(self.started("tok-juan", skill="loop-build")["concern"], CONCERN)

    def test_the_ceiling_holds_for_a_loop_or_an_environment_too(self):
        for scope, skill in (("loop", "loop-status"), ("loop", "loop-design"), ("environment", "loop-ship")):
            with self.subTest(scope=scope, skill=skill):
                self.assertEqual(self.scoped(scope, skill, budget_usd=11).json["refused"], "budget-ceiling")


class ScopedCapTest(Base):
    config = {"cap_per_sponsor": 2}

    def test_a_loop_or_environment_session_counts_toward_the_sponsor_cap(self):
        running = [self.started_on("loop", "loop-status")["id"], self.started_on("environment", "loop-ship")["id"]]
        response = self.dispatch(skill="loop-prove")
        self.assertEqual((response.status, response.json["refused"], response.json["cap"]), (409, "sponsor-cap", 2))
        self.assertEqual(sorted(s["id"] for s in response.json["sessions"]), sorted(running))
        self.assertEqual(self.scoped("loop", "loop-design").json["refused"], "sponsor-cap")


class LoweredCeilingTest(Base):
    config = {"budget_ceiling_usd": 1.0}

    def test_the_ceiling_is_a_config_change(self):
        response = self.dispatch(budget_usd=1.5)
        self.assertEqual((response.status, response.json["refused"], response.json["ceiling_usd"]),
                         (409, "budget-ceiling", 1.0))
        self.assertIn("$1.00", response.json["message"])
        self.assertEqual(self.started(budget_usd=1.0)["budget_usd"], 1.0)


class AtomicClaimTest(Base):
    """Two dispatches at once cannot both start: the claim is one transaction in the store."""

    def race(self, bodies, tokens):
        # Every dispatch checks its release, a /loop-prove included, so that is where they all meet before claiming.
        barrier = threading.Barrier(len(bodies))
        original = self.github.release_exists

        def all_pass_the_checks_before_the_claim(tag):
            result = original(tag)
            barrier.wait(timeout=5)
            return result

        self.github.release_exists = all_pass_the_checks_before_the_claim
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

    def test_a_build_and_a_design_at_once_on_one_concern_start_one(self):
        statuses, _ = self.race([dispatch_body(skill="loop-build"), dispatch_body(skill="loop-design")],
                                ["tok-juan", "tok-ana"])
        self.assertEqual(statuses, [201, 409])
        self.assertEqual(len(self.launcher.launched), 1)

    def test_a_build_and_a_prove_at_once_on_one_concern_both_start(self):
        statuses, _ = self.race([dispatch_body(skill="loop-build"), dispatch_body(skill="loop-prove")],
                                ["tok-juan", "tok-ana"])
        self.assertEqual(statuses, [201, 201])

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


class LatestReleaseTest(Base):
    """latest-release C1 (command-center/D68): the estimate names the newest release tag, the one a start from the
    app shows and dispatches, and a dispatch is still checked against the project's tags."""

    def estimate(self, skill="loop-build"):
        response = self.client.call("GET", "/estimates", token="tok-juan", query={"skill": skill})
        self.assertEqual(response.status, 200, response)
        return response.json

    def test_the_estimate_names_the_newest_release_tag(self):
        self.github.releases = {"v0.3.0", "v0.4.0", "v0.10.0", "v0.9.1"}
        self.assertEqual(self.estimate()["plugin_release"], "v0.10.0")
        self.assertEqual(self.estimate("loop-status")["plugin_release"], "v0.10.0")

    def test_the_release_the_estimate_names_is_one_a_dispatch_may_run(self):
        self.github.releases = {"v0.3.0", "v0.4.0"}
        release = self.estimate()["plugin_release"]
        self.assertEqual(self.started(plugin_release=release)["plugin_release"], "v0.4.0")

    def test_a_tag_cut_after_the_estimate_does_not_change_what_was_dispatched(self):
        self.github.releases = {"v0.3.0", "v0.4.0"}
        shown = self.estimate()["plugin_release"]
        self.github.releases.add("v0.5.0")
        self.assertEqual(self.started(plugin_release=shown)["plugin_release"], "v0.4.0")
        self.assertEqual(self.estimate()["plugin_release"], "v0.5.0")

    def test_a_dispatch_naming_a_tag_the_project_does_not_have_is_still_refused(self):
        self.github.releases = {"v0.3.0", "v0.4.0"}
        response = self.dispatch(plugin_release="v0.5.0")
        self.assertEqual((response.status, response.json["error"]), (422, "unknown-release"))
        self.assertEqual(self.launcher.launched, [])
        self.assertIn(("release_exists", "v0.5.0"), self.github.calls)

    def test_a_project_without_a_release_tag_has_none_to_name(self):
        self.github.releases = set()
        self.assertIsNone(self.estimate()["plugin_release"])

    def test_github_failing_while_reading_the_tags_is_a_502(self):
        original = self.github.latest_release

        def failing():
            original()
            raise GitHubError("listing tags answered 500")

        self.github.latest_release = failing
        response = self.client.call("GET", "/estimates", token="tok-juan", query={"skill": "loop-build"})
        self.assertEqual((response.status, response.json["error"]), (502, "upstream-failed"))


if __name__ == "__main__":
    unittest.main()
