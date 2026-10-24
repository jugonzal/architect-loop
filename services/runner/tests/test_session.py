"""A session's job with a fake Agent SDK: C4 (spend published at least every 10 s, the stop at the first response
that crosses the budget, the final estimate with its overshoot), the stop a sponsor asks for, the options the
SDK runs with (D3, D5, D17, D21), and the trailers on the pull requests a session opens (session-runner C5,
runner-dispatch C1).

The tests that bound timing run the job on a virtual clock (VirtualTimeLoop), so a stalled machine cannot fail them.
"""

import asyncio
import concurrent.futures
import os
import time
import unittest

from claude_agent_sdk import AssistantMessage, ResultMessage, TextBlock, ToolUseBlock

from runner.api import Api
from runner.config import ALLOWED_TOOLS, SCOPES, Config
from runner.dispatch import Dispatcher
from runner.models import Session
from runner.session import SessionJob, claude_client, with_trailers
from runner.store import SqliteStore
from runner.workspace import Prepared
from tests import RealSessionRefused
from tests.contract import ContractClient
from tests.fakes import CONCERN, ENVIRONMENT, LOOP, PROJECT, SCOPED, FakeGitHub, FakeLauncher, scratch

PRICE_PER_INPUT = 4.00 / 1_000_000  # Opus 5.5 list price


def assistant(n, input_tokens=1500, output_tokens=10, text=None, content=None, message_id=None, parent=None):
    return AssistantMessage(content=content if content is not None else [TextBlock(text=text or f"step {n}")],
                            model="claude-opus-5-5",
                            usage={"input_tokens": input_tokens, "output_tokens": output_tokens},
                            message_id=message_id or f"msg_{n}", parent_tool_use_id=parent)


def result(subtype="success", cost=0.05, usage=None, text=None):
    return ResultMessage(subtype=subtype, duration_ms=10, duration_api_ms=5, is_error=subtype != "success",
                         num_turns=1, session_id="sdk-session", total_cost_usd=cost, result=text,
                         usage=usage or {"input_tokens": 3000, "output_tokens": 400, "cache_creation_input_tokens": 0,
                                         "cache_read_input_tokens": 0})


class FakeClaude:
    """Stands in for ClaudeSDKClient: plays a script of (delay in seconds, message), and on an interrupt ends the
    turn with a result the way the SDK does."""

    def __init__(self, script, options, crash_after=None):
        self.script, self.options, self.crash_after = script, options, crash_after
        self.prompts, self.yielded, self.interrupted = [], [], False
        self._wake = asyncio.Event()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def query(self, prompt):
        self.prompts.append(prompt)

    async def interrupt(self):
        self.interrupted = True
        self._wake.set()

    async def receive_response(self):
        for delay, message in self.script:
            if delay:
                try:
                    await asyncio.wait_for(self._wake.wait(), delay)
                except asyncio.TimeoutError:
                    pass
            if self.interrupted:
                spent = sum(m.usage["input_tokens"] for m in self.yielded) * PRICE_PER_INPUT
                yield result("error_during_execution", cost=round(spent * 1.5, 6))
                return
            if self.crash_after is not None and len(self.yielded) >= self.crash_after:
                raise RuntimeError("the CLI exited")
            self.yielded.append(message)
            yield message
            if isinstance(message, ResultMessage):
                return


class FakeWorkspace:
    def __init__(self, root, pushed=()):
        self.root, self.pushed, self.prepared = root, list(pushed), []

    def prepare(self, session):
        self.prepared.append(session.id)
        clone = os.path.join(self.root, session.id, "clone")
        plugin = os.path.join(self.root, session.id, "release", session.plugin_release, "plugin")
        os.makedirs(clone)
        os.makedirs(plugin)
        return Prepared(os.path.join(self.root, session.id), clone, plugin, "architect-loop")

    def pushed_branches(self, clone):
        return list(self.pushed)


class RecordingStore(SqliteStore):
    """Records each publication with the job's clock. `stalls` maps a publication's number (from 1) to a real pause,
    in seconds, before it is written: the stall a busy machine causes."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.published, self.clock, self.stalls = [], time.monotonic, {}

    def publish(self, session_id, spend, now):
        self.published.append((self.clock(), spend))
        time.sleep(self.stalls.get(len(self.published), 0))
        return super().publish(session_id, spend, now)


class InlineExecutor(concurrent.futures.ThreadPoolExecutor):
    """Runs each `asyncio.to_thread` call at once, on the loop's own thread, so a virtual clock never waits on a
    real one."""

    def submit(self, fn, /, *args, **kwargs):
        future = concurrent.futures.Future()
        try:
            future.set_result(fn(*args, **kwargs))
        except BaseException as error:
            future.set_exception(error)
        return future


class JumpingSelector:
    """Wraps a loop's selector: where the loop would sleep until its next timer, it moves the loop's clock there."""

    def __init__(self, selector, loop):
        self._selector, self._loop = selector, loop

    def select(self, timeout=None):
        if time.monotonic() > self._loop.real_deadline:
            raise RuntimeError("the job ran for 10 s of real time on a virtual clock")
        events = self._selector.select(0)
        if events or timeout == 0:
            return events
        if timeout is None:
            raise RuntimeError("nothing is ready and no timer is set: the job would wait forever")
        self._loop.virtual_now += timeout
        return events

    def __getattr__(self, name):
        return getattr(self._selector, name)


class VirtualTimeLoop(asyncio.SelectorEventLoop):
    """An event loop on a virtual clock. Time passes only by jumping to the next timer, never while code runs, so
    a test's timing depends on the job's timers alone and a stalled machine cannot change it."""

    def __init__(self):
        self.virtual_now, self.real_deadline = 0.0, time.monotonic() + 10
        super().__init__()
        self._selector = JumpingSelector(self._selector, self)
        self.set_default_executor(InlineExecutor())

    def time(self):
        return self.virtual_now

    async def shutdown_default_executor(self, timeout=None):
        """Nothing ran on a thread, so there is nothing to join."""


class JobTest(unittest.TestCase):
    interval = 0.05

    def setUp(self):
        root = scratch(self)
        self.config = Config(store_path=os.path.join(root, "runner.sqlite3"), spend_interval_s=self.interval,
                             app_slug="architect-loop-runner")
        self.store = RecordingStore(self.config.store_path, seeds=self.config.seeds)
        self.github = FakeGitHub()
        self.workspace = FakeWorkspace(os.path.join(root, "work"))
        self.clients = []

    def claimed(self, budget=1.0, skill="loop-build", arguments="", sponsor="juan", scope="concern"):
        session = Session(id="c" * 32, project=PROJECT, skill=skill, arguments=arguments,
                          model=self.config.skill_models[skill], sponsor=sponsor, budget_usd=budget,
                          plugin_release="v0.3.0", created_at="2026-10-20T12:00:00Z", **SCOPED[scope])
        self.assertIsNone(self.store.claim(session, 3, session.created_at, 300))
        return session

    virtual_time = False  # the tests that bound timing set it, so their job runs on a VirtualTimeLoop

    def run_job(self, session, script, crash_after=None, during=None):
        def factory(options):
            client = FakeClaude(script, options, crash_after)
            self.clients.append(client)
            return client

        async def main(job):
            task = asyncio.create_task(job.run(session.id))
            if during:
                await during()
            return await asyncio.wait_for(task, 10)

        with asyncio.Runner(loop_factory=VirtualTimeLoop if self.virtual_time else None) as runner:
            clock = runner.get_loop().time
            self.store.clock = clock
            job = SessionJob(self.config, self.store, self.github, self.workspace, factory, monotonic=clock)
            started = clock()
            ended = runner.run(main(job))
            self.elapsed = clock() - started
        return ended


class SpendPublicationTest(JobTest):
    virtual_time = True

    def test_spend_is_published_at_least_every_interval_even_while_the_model_is_silent(self):
        session = self.claimed()
        self.run_job(session, [(0.01, assistant(1)), (0.6, assistant(2)), (0.01, result())])
        times = [t for t, spend in self.store.published if spend]
        self.assertGreaterEqual(len(times), 8, "the 0.6 s silence must still see publications")
        gaps = [b - a for a, b in zip(times, times[1:])]
        self.assertAlmostEqual(max(gaps), self.interval, places=6, msg=gaps)  # on the virtual clock, no slack

    def test_a_stalled_machine_cannot_fail_the_timing_tests(self):
        """CI's machines sometimes stall for hundreds of milliseconds. A real pause in the middle of the silence must
        change nothing the test above sees."""
        session = self.claimed()
        self.store.stalls = {4: 0.3}
        self.run_job(session, [(0.01, assistant(1)), (0.6, assistant(2)), (0.01, result())])
        times = [t for t, spend in self.store.published if spend]
        self.assertGreaterEqual(len(times), 8)
        gaps = [b - a for a, b in zip(times, times[1:])]
        self.assertAlmostEqual(max(gaps), self.interval, places=6, msg=gaps)

    def test_every_published_figure_is_labelled_an_estimate(self):
        session = self.claimed()
        ended = self.run_job(session, [(0.01, assistant(1)), (0.2, assistant(2)), (0.01, result())])
        running = [spend for _, spend in self.store.published if spend]
        self.assertTrue(running)
        self.assertTrue(all(s["kind"] == "estimate" and s["basis"] == "per-step usage" for s in running))
        self.assertTrue(all(s["overshoot_usd"] is None for s in running))
        self.assertEqual((ended.spend["kind"], ended.spend["basis"]), ("estimate", "sdk result"))

    def test_the_running_estimate_follows_each_response(self):
        session = self.claimed()
        self.run_job(session, [(0.01, assistant(1)), (0.3, assistant(2)), (0.3, result())])
        figures = sorted({round(s["usd"], 6) for _, s in self.store.published if s})
        self.assertEqual(figures, [0.0, round(1500 * PRICE_PER_INPUT + 10 * 20 / 1e6, 6),
                                   round(2 * (1500 * PRICE_PER_INPUT + 10 * 20 / 1e6), 6)])


class BudgetTest(JobTest):
    virtual_time = True

    def test_the_sdks_budget_stop_ends_it_with_outcome_budget_and_reports_the_overshoot(self):
        session = self.claimed(budget=0.10)
        ended = self.run_job(session, [(0.01, assistant(1)), (0.3, result("error_max_budget_usd", cost=0.1118))])
        self.assertEqual((ended.state, ended.outcome), ("ended", "budget"))
        self.assertAlmostEqual(ended.spend["usd"], 0.1118)
        self.assertAlmostEqual(ended.spend["overshoot_usd"], 0.0118)
        self.assertEqual(ended.spend["tokens"]["output"], 400)
        self.assertAlmostEqual(ended.spend["wall_clock_s"], self.elapsed, delta=0.05)  # it is rounded to 0.1 s

    def test_it_stops_at_the_first_response_that_crosses_even_if_the_sdk_does_not(self):
        session = self.claimed(budget=0.01)  # each response costs about $0.0062, so the second crosses
        script = [(0.01, assistant(n)) for n in range(1, 6)] + [(0.01, result())]
        ended = self.run_job(session, script)
        client = self.clients[0]
        self.assertTrue(client.interrupted)
        self.assertEqual([m.message_id for m in client.yielded], ["msg_1", "msg_2"])
        self.assertEqual(ended.outcome, "budget")
        self.assertGreater(ended.spend["overshoot_usd"], 0)

    def test_the_budget_goes_to_the_sdk_as_max_budget_usd(self):
        session = self.claimed(budget=0.37)
        self.run_job(session, [(0, result())])
        self.assertEqual(self.clients[0].options.max_budget_usd, 0.37)


class StopTest(JobTest):
    virtual_time = True

    def test_a_sponsor_stop_interrupts_the_model_within_one_publication(self):
        session = self.claimed()

        async def stop_soon():
            await asyncio.sleep(0.15)
            self.store.request_stop(session.id)

        ended = self.run_job(session, [(0.01, assistant(1)), (5, assistant(2)), (0, result())], during=stop_soon)
        self.assertLessEqual(self.elapsed, 0.15 + self.interval)  # the first publication after the stop sees it
        self.assertTrue(self.clients[0].interrupted)
        self.assertEqual((ended.state, ended.outcome), ("ended", "sponsor"))
        self.assertEqual(ended.spend["basis"], "sdk result")

    def test_a_stop_before_the_model_starts_never_starts_it(self):
        session = self.claimed()
        self.store.request_stop(session.id)
        ended = self.run_job(session, [(0, result())])
        self.assertEqual(self.clients, [])
        self.assertEqual(ended.outcome, "sponsor")
        self.assertEqual(ended.spend["basis"], "per-step usage")

    def test_a_session_whose_job_already_started_is_never_started_twice(self):
        session = self.claimed()
        self.store.mark_running(session.id, "2026-10-20T12:00:05Z")  # a first task started, then died
        with self.assertLogs("runner.session", "ERROR"):
            ended = self.run_job(session, [(0, result())])
        self.assertEqual((self.clients, self.workspace.prepared), ([], []))
        self.assertEqual((ended.state, ended.outcome), ("ended", "error"))

    def test_a_session_that_already_ended_is_not_run(self):
        session = self.claimed()
        self.store.finish(session.id, "lost", None, [], "2026-10-20T12:10:00Z")
        ended = self.run_job(session, [(0, result())])
        self.assertEqual((self.clients, self.workspace.prepared), ([], []))
        self.assertEqual(ended.outcome, "lost")


class OutcomeTest(JobTest):
    def test_a_finished_skill_ends_completed_and_measures_the_pairing(self):
        session = self.claimed()
        ended = self.run_job(session, [(0.01, assistant(1)), (0.01, result(cost=0.2345))])
        self.assertEqual(ended.outcome, "completed")
        self.assertIsNotNone(ended.started_at)
        estimate = Dispatcher(self.config, self.store, self.github, None).estimate("loop-build")
        self.assertEqual(estimate["estimate"]["usd"], 0.2345)
        self.assertEqual(estimate["estimate"]["sessions"], 1)

    def test_an_error_result_ends_it_with_outcome_error(self):
        session = self.claimed()
        ended = self.run_job(session, [(0.01, result("error_during_execution", cost=0.01))])
        self.assertEqual(ended.outcome, "error")

    def test_a_crash_ends_it_with_outcome_error_and_the_running_estimate(self):
        session = self.claimed()
        with self.assertLogs("runner.session", "ERROR") as logged:
            ended = self.run_job(session, [(0.01, assistant(1)), (0.01, assistant(2))], crash_after=1)
        self.assertIn("the CLI exited", "\n".join(logged.output))
        self.assertEqual(ended.outcome, "error")
        self.assertEqual(ended.spend["basis"], "per-step usage")
        self.assertGreater(ended.spend["usd"], 0)


class OptionsTest(JobTest):
    def test_the_sdk_runs_in_dont_ask_mode_with_the_d3_tools_and_no_settings(self):
        session = self.claimed(skill="loop-status")
        self.run_job(session, [(0, result())])
        options = self.clients[0].options
        self.assertEqual(options.permission_mode, "dontAsk")
        self.assertEqual(list(options.allowed_tools), list(ALLOWED_TOOLS))
        self.assertEqual(options.setting_sources, [])
        self.assertEqual(options.model, "claude-sonnet-5-5")  # D5
        prepared_root = os.path.join(self.workspace.root, session.id)
        self.assertEqual(options.cwd, os.path.join(prepared_root, "clone"))
        self.assertEqual(options.plugins, [{"type": "local",
                                            "path": os.path.join(prepared_root, "release", "v0.3.0", "plugin")}])

    def test_the_session_gets_an_installation_token_for_its_pushes_and_never_the_apps_key(self):
        session = self.claimed()
        self.run_job(session, [(0, result())])
        env = self.clients[0].options.env
        self.assertEqual(env["GH_TOKEN"], "ghs_fake_installation_token")
        self.assertNotIn("RUNNER_APP_PRIVATE_KEY", env)
        self.assertIn(("installation_token", (("contents", "write"), ("metadata", "read"),
                                              ("pull_requests", "write"))), self.github.calls)

    def test_the_prompt_runs_the_installed_plugins_skill_on_the_concern(self):
        session = self.claimed(arguments="--ready")
        self.run_job(session, [(0, result())])
        self.assertEqual(self.clients[0].prompts, [f"/architect-loop:loop-build {CONCERN} --ready"])

    def test_a_loop_or_environment_session_runs_its_skill_on_that_name(self):
        """runner-dispatch C3: `/loop-status <loop>`, `/loop-design <loop>`, `/loop-ship <environment>`."""
        for scope, skill, arguments, prompt in (
                ("loop", "loop-status", "--json", f"/architect-loop:loop-status {LOOP} --json"),
                ("loop", "loop-design", "", f"/architect-loop:loop-design {LOOP}"),
                ("environment", "loop-ship", "", f"/architect-loop:loop-ship {ENVIRONMENT}")):
            with self.subTest(scope=scope, skill=skill):
                self.setUp()
                self.run_job(self.claimed(skill=skill, scope=scope, arguments=arguments), [(0, result())])
                self.assertEqual(self.clients[0].prompts, [prompt])

    def test_the_real_sdk_client_is_out_of_reach_of_the_tests(self):
        with self.assertRaises(RealSessionRefused):
            claude_client(None)


class PullRequestTrailerTest(JobTest):
    """C1: the job puts the same trailers in the bodies of the pull requests the session opened."""

    def test_a_pull_request_from_a_pushed_branch_gets_the_sponsor_beside_its_concern(self):
        self.workspace.pushed = [CONCERN]
        body = f"## What this changes\n\nText.\n\nConcern: {CONCERN}\n\n🤖 Generated with Claude Code"
        self.github.open_pr(21, CONCERN, body=body)
        self.github.open_pr(22, "someone-else", body="Not ours")
        ended = self.run_job(self.claimed(sponsor="ana"), [(0, result())])
        new = self.github.bodies[21].splitlines()
        self.assertEqual(new[new.index(f"Concern: {CONCERN}") + 1], "Sponsored-by: ana")
        self.assertNotIn(22, self.github.bodies)
        self.assertEqual(ended.pull_requests, [{"number": 21, "url": f"https://github.com/{PROJECT}/pull/21",
                                                "head": CONCERN}])

    def test_a_body_that_already_carries_both_is_left_alone(self):
        self.workspace.pushed = [CONCERN]
        self.github.open_pr(21, CONCERN, body=f"Text\n\nConcern: {CONCERN}\nSponsored-by: juan\n")
        self.run_job(self.claimed(), [(0, result())])
        self.assertNotIn(21, self.github.bodies)

    def test_a_design_sessions_pull_request_gets_its_sponsor_and_no_concern(self):
        self.workspace.pushed = ["docs/command-center-runner"]
        self.github.open_pr(23, "docs/command-center-runner", body="## What this records\n\nText.")
        self.run_job(self.claimed(skill="loop-design", sponsor="ana"), [(0, result())])
        self.assertEqual(self.github.bodies[23], "## What this records\n\nText.\n\nSponsored-by: ana")

    def test_only_a_build_sessions_pull_requests_get_the_concern_whatever_the_skill(self):
        pairs = [(scope, skill) for scope, skills in SCOPES.items() for skill in skills]
        for n, (scope, skill) in enumerate(pairs, 1):
            with self.subTest(scope=scope, skill=skill):
                self.setUp()
                self.workspace.pushed = [f"docs/x-{n}"]
                self.github.open_pr(30 + n, f"docs/x-{n}", body="Text")
                self.run_job(self.claimed(skill=skill, sponsor="ana", scope=scope), [(0, result())])
                lines = self.github.bodies[30 + n].splitlines()
                self.assertIn("Sponsored-by: ana", lines)
                self.assertEqual([line for line in lines if line.startswith("Concern:")],
                                 [f"Concern: {CONCERN}"] if skill == "loop-build" else [])


class FinalMessageTest(JobTest):
    """runner-dispatch C3 (app-inbox D1): the job keeps the session's last assistant message with how it ended, and
    the session resource serves it, so a dispatched `/loop-ship`'s brief can be read back from the runner."""

    BRIEF = "## Ship brief: staging/runner\n\nTwo concerns go out. Run `sh scripts/gcp/deploy.sh runner staging <sha>`."

    def test_the_last_assistant_message_is_kept_and_served_with_the_session(self):
        session = self.claimed(skill="loop-ship", scope="environment")
        ended = self.run_job(session, [(0.01, assistant(1, text="Reading the board.")),
                                       (0.01, assistant(2, text=self.BRIEF)), (0.01, result())])
        self.assertEqual(ended.final_message, self.BRIEF)
        client = ContractClient(self, Api(Dispatcher(self.config, self.store, self.github, FakeLauncher())))
        self.assertEqual(client.call("GET", f"/sessions/{session.id}", token="tok-juan").json["final_message"],
                         self.BRIEF)
        listed = client.call("GET", "/sessions", token="tok-juan", query={"state": "all"}).json["sessions"]
        self.assertEqual([s["final_message"] for s in listed], [self.BRIEF])

    def test_one_response_that_arrives_as_several_messages_is_kept_whole(self):
        ended = self.run_job(self.claimed(), [
            (0.01, assistant(1, text="Earlier.")),
            (0.01, assistant(2, text="First part.", message_id="msg_last")),
            (0.01, assistant(3, text="Second part.", message_id="msg_last")),
            (0.01, result())])
        self.assertEqual(ended.final_message, "First part.\n\nSecond part.")

    def test_a_last_response_with_only_a_tool_call_keeps_the_text_before_it(self):
        tool = [ToolUseBlock(id="t1", name="Bash", input={"command": "git status"})]
        ended = self.run_job(self.claimed(), [(0.01, assistant(1, text="Said last.")),
                                              (0.01, assistant(2, content=tool)), (0.01, result())])
        self.assertEqual(ended.final_message, "Said last.")

    def test_a_subagents_message_is_not_the_sessions(self):
        ended = self.run_job(self.claimed(), [(0.01, assistant(1, text="The session's.")),
                                              (0.01, assistant(2, text="A subagent's.", parent="toolu_1")),
                                              (0.01, result())])
        self.assertEqual(ended.final_message, "The session's.")

    def test_without_any_text_the_results_text_is_the_final_message(self):
        ended = self.run_job(self.claimed(), [(0.01, result(text="Done."))])
        self.assertEqual(ended.final_message, "Done.")

    def test_a_session_stopped_at_its_budget_keeps_what_it_said_last(self):
        session = self.claimed(budget=0.01)  # the second response crosses
        script = [(0.01, assistant(n, text=f"said {n}")) for n in range(1, 6)] + [(0.01, result())]
        ended = self.run_job(session, script)
        self.assertEqual((ended.outcome, ended.final_message), ("budget", "said 2"))

    def test_a_crash_keeps_what_it_said_last(self):
        with self.assertLogs("runner.session", "ERROR"):
            ended = self.run_job(self.claimed(), [(0.01, assistant(1, text="said 1")), (0.01, assistant(2))],
                                 crash_after=1)
        self.assertEqual((ended.outcome, ended.final_message), ("error", "said 1"))

    def test_a_session_stopped_before_the_model_started_has_none(self):
        session = self.claimed()
        self.store.request_stop(session.id)
        self.assertIsNone(self.run_job(session, [(0, result(text="never"))]).final_message)


class WithTrailersTest(unittest.TestCase):
    def test_both_are_appended_when_neither_is_there(self):
        self.assertEqual(with_trailers("Text", "loop/x", "ana"), "Text\n\nConcern: loop/x\nSponsored-by: ana")

    def test_an_existing_concern_is_kept_even_if_it_names_another(self):
        self.assertEqual(with_trailers("Text\n\nConcern: loop/y", "loop/x", "ana"),
                         "Text\n\nConcern: loop/y\nSponsored-by: ana")

    def test_nothing_to_add_is_none(self):
        self.assertIsNone(with_trailers("Concern: loop/x\nSponsored-by: ana", "loop/x", "ana"))

    def test_an_empty_body_gets_both(self):
        self.assertEqual(with_trailers("", "loop/x", "ana"), "Concern: loop/x\nSponsored-by: ana")

    def test_without_a_concern_only_the_sponsor_is_appended(self):
        self.assertEqual(with_trailers("Text", None, "ana"), "Text\n\nSponsored-by: ana")
        self.assertEqual(with_trailers("", None, "ana"), "Sponsored-by: ana")

    def test_without_a_concern_a_body_with_its_sponsor_is_left_alone(self):
        self.assertIsNone(with_trailers("Text\n\nSponsored-by: ana", None, "ana"))


if __name__ == "__main__":
    unittest.main()
