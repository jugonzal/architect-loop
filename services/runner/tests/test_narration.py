"""A session narrates to its own thread on the threads service, and hears the members who write there
(session-narration C1, C2).

C1: each milestone (started, branch opened, tests run with their result, pull request opened, stopped at a gate, and
how it ended with what it spent) reaches the thread within 10 seconds of it. C2: a member's message reaches the session
before its next step, and the session's answer is posted back. The job runs with a fake Agent SDK that calls the
session's hooks the way the CLI does, and a fake thread, on the virtual clock of test_session, so the timing bounds
hold on a stalled machine. The posts and reads themselves are checked against services/threads/openapi.yaml.
"""

import asyncio
import json
import os
import unittest
import urllib.parse
from unittest import mock

import yaml
from claude_agent_sdk import ResultMessage, TextBlock, ToolResultBlock, ToolUseBlock, UserMessage
from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

from runner import main
from runner.config import Config
from runner.session import (Narration, SessionJob, SessionThread, ThreadsError, gates_in, gates_named, runs_tests,
                            tests_milestone, without_heredocs)
from tests.fakes import CONCERN, scratch
from tests.test_github import PEM
from tests.test_session import FakeWorkspace, JobTest, VirtualTimeLoop, assistant, result

SERVICES = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
with open(os.path.join(SERVICES, "threads", "openapi.yaml")) as _f:
    THREADS_SPEC = yaml.safe_load(_f)
_URN = "urn:architect-loop:threads-openapi"
_REGISTRY = Registry().with_resource(_URN, Resource.from_contents(THREADS_SPEC, default_specification=DRAFT202012))
SESSION_MESSAGES = "/projects/{owner}/{repo}/sessions/{session}/thread/messages"

THREADS_URL = "https://threads-665570365697.us-east1.run.app"
LOOP_MD = """## 2. Gates
- **Merge** (key: merge; holder: jugonzal): merging to `main`
- **Deploy** (key: deploy; holder: jugonzal): deploying
- **Spending** (key: spending; holder: ana): starting hosted agent sessions
"""


def schema(name):
    return Draft202012Validator({"$ref": f"{_URN}#/components/schemas/{name}"}, registry=_REGISTRY)


def bash(n, command, message_id=None):
    return assistant(n, content=[ToolUseBlock(id=f"tool_{n}", name="Bash", input={"command": command})],
                     message_id=message_id)


def tool_result(n, output, is_error=False, parent=None):
    return UserMessage(content=[ToolResultBlock(tool_use_id=f"tool_{n}", content=output, is_error=is_error)],
                       parent_tool_use_id=parent)


STOP = "the model would stop here"


class HookedClaude:
    """Stands in for ClaudeSDKClient, as the CLI runs a session's hooks: PostToolUse after each tool's result and before
    the model's next step, and Stop where the model would stop, which goes on only if a hook gives it something to
    answer. It records what each hook told the model, with the time it did."""

    def __init__(self, script, options, clock):
        self.script, self.options, self.clock = script, options, clock
        self.contexts, self.prompts = [], []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def query(self, prompt):
        self.prompts.append(prompt)

    async def interrupt(self):
        pass

    async def _hook(self, event, data):
        for matcher in (self.options.hooks or {}).get(event, []):
            for hook in matcher.hooks:
                said = await hook({"hook_event_name": event, **data}, data.get("tool_use_id"), {"signal": None})
                context = ((said or {}).get("hookSpecificOutput") or {}).get("additionalContext")
                if context:
                    self.contexts.append((self.clock(), event, context))
                    return True
        return False

    async def receive_response(self):
        for delay, message in self.script:
            await asyncio.sleep(delay)
            if message is STOP:
                if await self._hook("Stop", {"stop_hook_active": False}):
                    continue
                yield result()
                return
            yield message
            if isinstance(message, UserMessage):
                for block in message.content:
                    data = {"tool_name": "Bash", "tool_input": {}, "tool_response": {}, "tool_use_id": block.tool_use_id}
                    if message.parent_tool_use_id:
                        data["agent_id"] = "subagent-1"
                    await self._hook("PostToolUse", data)
            if isinstance(message, ResultMessage):
                return


class FakeThread:
    """A session's thread as SessionThread reads and writes it, recording each post with the job's clock."""

    def __init__(self):
        self.clock, self.posts, self.messages, self.down, self.reads = None, [], [], False, 0

    def post(self, body, kind):
        if self.down:
            raise ThreadsError("posting to the session's thread answered 503")
        self.posts.append((self.clock(), kind, body))
        self.messages.append({"seq": len(self.messages) + 1, "kind": kind, "body": body,
                              "author": {"type": "session", "session": "s", "sponsor": "juan"}})
        return self.messages[-1]

    def member_says(self, login, body):
        self.messages.append({"seq": len(self.messages) + 1, "kind": "message", "body": body,
                              "author": {"type": "person", "login": login}, "created_at": "2026-10-24T12:00:00Z"})

    def messages_after(self, after):
        self.reads += 1
        if self.down:
            raise ThreadsError("reading the session's thread answered 503")
        found = [m for m in self.messages if m["seq"] > after and m["kind"] == "message"]
        return found, max([after] + [m["seq"] for m in self.messages])

    def milestones(self):
        return [(at, body) for at, kind, body in self.posts if kind == "milestone"]


class WorkspaceWithLoop(FakeWorkspace):
    def prepare(self, session):
        prepared = super().prepare(session)
        with open(os.path.join(prepared.clone, "LOOP.md"), "w") as f:
            f.write(LOOP_MD)
        return prepared


class NarrationTest(JobTest):
    virtual_time = True
    interval = 1.0

    def setUp(self):
        super().setUp()
        self.config = Config(store_path=self.config.store_path, spend_interval_s=1.0, app_slug="architect-loop-runner")
        self.workspace = WorkspaceWithLoop(os.path.join(scratch(self), "work"))
        self.thread = FakeThread()

    def run_narrated(self, session, script, during=None, threads=True):
        async def go(job):
            task = asyncio.create_task(job.run(session.id))
            if during:
                await during()
            return await asyncio.wait_for(task, 120)

        with asyncio.Runner(loop_factory=VirtualTimeLoop) as runner:
            clock = runner.get_loop().time
            self.store.clock = self.thread.clock = clock

            def factory(options):
                self.options = options
                client = HookedClaude(script, options, clock)
                self.clients.append(client)
                return client

            job = SessionJob(self.config, self.store, self.github, self.workspace, factory, monotonic=clock,
                             threads=(lambda s: self.thread) if threads else None)
            return runner.run(go(job))

    def assertWithin(self, milestones, starts, at, seconds=10.0):
        found = [t for t, body in milestones if body.startswith(starts)]
        self.assertEqual(len(found), 1, f"one milestone starting {starts!r} in {milestones}")
        self.assertGreaterEqual(found[0], at - 1e-6, f"{starts!r} was posted before it happened")
        self.assertLessEqual(found[0] - at, seconds, f"{starts!r} took {found[0] - at:.1f} s to reach the thread")


class MilestoneTest(NarrationTest):
    def test_each_milestone_reaches_the_thread_within_ten_seconds_of_it(self):
        session = self.claimed(budget=2.0)
        script = [
            (1.0, assistant(1, text="Reading the concern.")),
            (2.0, bash(2, "cd services/runner && python -m unittest discover -s tests -v")),  # t=3
            (30.0, tool_result(2, "...\nRan 41 tests in 3.2s\n\nFAILED (failures=2)", is_error=True)),  # t=33
            (5.0, bash(3, "python -m unittest discover -s tests")),  # t=38
            (20.0, tool_result(3, "Ran 41 tests in 3.1s\n\nOK")),  # t=58
            (2.0, bash(4, "git push -u origin command-center/session-runner")),  # t=60
            (3.0, tool_result(4, "branch 'command-center/session-runner' set up to track")),  # t=63
            (4.0, bash(5, "gh pr create --draft --title 'Build it' --body-file body.md")),  # t=67
            (6.0, tool_result(5, "https://github.com/jugonzal/architect-loop/pull/77\n")),  # t=73
            (5.0, assistant(6, text="Opened #77. It needs a deploy, which is the owner's: I stop at the deploy gate "
                                    "(gates: deploy).")),  # t=78
            (1.0, STOP),
        ]

        async def during():
            await asyncio.sleep(61.0)  # the push lands while its tool runs
            self.workspace.pushed.append(CONCERN)
            await asyncio.sleep(10.0)  # t=71: GitHub lists the pull request before gh prints its URL
            self.github.open_pr(77, CONCERN)

        ended = self.run_narrated(session, script, during)
        self.assertEqual(ended.outcome, "completed")
        milestones = self.thread.milestones()
        self.assertWithin(milestones, "Started /loop-build on command-center/session-runner", 0.0)
        self.assertWithin(milestones, "Tests run, failed: `cd services/runner && python -m unittest", 33.0)
        self.assertWithin(milestones, "Tests run, passed: `python -m unittest discover -s tests`", 58.0)
        self.assertWithin(milestones, f"Branch {CONCERN} opened", 61.0)
        self.assertWithin(milestones, "Pull request #77 opened", 71.0)
        self.assertWithin(milestones, "Stopped at a gate: deploy (held by jugonzal)", 79.0)
        self.assertWithin(milestones, "Finished. It spent about $0.0500", 79.0)
        bodies = [body for _, body in milestones]
        self.assertIn("Ran 41 tests in 3.2s; FAILED (failures=2).", bodies[1])
        self.assertIn("https://github.com/jugonzal/architect-loop/pull/77", bodies[4])
        self.assertIn("an estimate (the Agent SDK's estimate)", bodies[-1])
        self.assertEqual([body.split(" ")[0] for body in bodies],
                         ["Started", "Tests", "Tests", "Branch", "Pull", "Stopped", "Finished."], bodies)

    def test_a_pull_request_opened_with_gh_is_announced_from_its_output_at_once(self):
        session = self.claimed()
        script = [(1.0, bash(1, "gh pr create --fill")),
                  (2.0, tool_result(1, "https://github.com/jugonzal/architect-loop/pull/9")),  # t=3
                  (1.0, assistant(2, text="Done.")), (0.0, STOP)]
        self.run_narrated(session, script)
        self.assertWithin(self.thread.milestones(), "Pull request #9 opened", 3.0, seconds=0.5)

    def test_a_pull_request_opened_any_other_way_is_found_within_one_look(self):
        session = self.claimed()
        script = [(1.0, assistant(1, text="Working.")), (40.0, assistant(2, text="Done.")), (0.0, STOP)]

        async def during():
            await asyncio.sleep(10.0)
            self.workspace.pushed.append(CONCERN)  # pushed by a script, not by `git push` in Bash
            await asyncio.sleep(10.0)
            self.github.open_pr(12, CONCERN)  # t=20: opened through the API, not with gh

        self.run_narrated(session, script, during)
        milestones = self.thread.milestones()
        self.assertWithin(milestones, f"Branch {CONCERN} opened", 10.0, seconds=self.config.narration_poll_s)
        self.assertWithin(milestones, "Pull request #12 opened", 20.0, seconds=self.config.narration_poll_s)
        asked = [c for c in self.github.calls if c[0] == "pull_requests_for_heads"]
        # It asks GitHub only while a pushed branch has no pull request: from t=10 to t=20, and not for the 21 s after.
        self.assertTrue(asked)
        self.assertLessEqual(len(asked), 10 / self.config.narration_poll_s + 2)

    def test_how_it_ended_names_the_outcome_and_the_final_estimate(self):
        session = self.claimed(budget=0.10)
        self.run_narrated(session, [(1.0, assistant(1)), (2.0, result("error_max_budget_usd", cost=0.1118))])
        last = self.thread.milestones()[-1][1]
        self.assertEqual(last, "Stopped at its budget. It spent about $0.1118 over 3 s, an estimate (the Agent "
                               "SDK's estimate).")

    def test_no_gate_is_named_when_the_session_does_not_say_it_stopped_at_one(self):
        session = self.claimed()
        script = [(1.0, assistant(1, text="Built it; the merge is the owner's.")), (0.0, STOP)]
        self.run_narrated(session, script)
        self.assertFalse([b for _, b in self.thread.milestones() if b.startswith("Stopped at")])

    def test_the_rest_is_narration_and_a_subagents_text_is_not_posted(self):
        session = self.claimed()
        script = [(1.0, assistant(1, text="Reading the concern.")),
                  (1.0, assistant(2, text="a subagent thinking aloud", parent="tool_x")),
                  (1.0, assistant(3, text="Writing the tests first.")), (0.0, STOP)]
        self.run_narrated(session, script)
        narration = [body for _, kind, body in self.thread.posts if kind == "narration"]
        self.assertEqual(narration, ["Reading the concern.", "Writing the tests first."])
        for _, kind, body in self.thread.posts:
            self.assertEqual(list(schema("NewMessage").iter_errors({"body": body, "kind": kind, "sponsor": "juan"})),
                             [])

    def test_a_thread_that_is_down_never_ends_the_session(self):
        session = self.claimed()
        self.thread.down = True
        script = [(1.0, bash(1, "python -m unittest")), (1.0, tool_result(1, "OK")),
                  (1.0, assistant(2, text="Done.")), (0.0, STOP)]
        with self.assertLogs("runner.session", "ERROR"):
            ended = self.run_narrated(session, script)
        self.assertEqual((ended.state, ended.outcome), ("ended", "completed"))
        self.assertEqual(ended.final_message, "Done.")

    def test_without_threads_a_session_narrates_nowhere_and_has_no_hooks(self):
        session = self.claimed()
        ended = self.run_narrated(session, [(1.0, assistant(1, text="Done.")), (0.0, STOP)], threads=False)
        self.assertEqual(ended.outcome, "completed")
        self.assertIsNone(self.options.hooks)
        self.assertEqual(self.thread.posts, [])


class RelayTest(NarrationTest):
    def test_a_members_message_reaches_the_session_before_its_next_step_and_its_answer_is_posted(self):
        session = self.claimed()
        script = [(1.0, bash(1, "ls")), (9.0, tool_result(1, "README.md")),  # t=10: the step after the message
                  (2.0, assistant(2, text="Understood: I will leave the API alone.")),  # t=12
                  (2.0, assistant(3, text="Now the tests.")), (0.0, STOP)]

        async def during():
            await asyncio.sleep(4.0)
            self.thread.member_says("ana", "Please don't change the API in this PR.")

        self.run_narrated(session, script, during)
        contexts = self.clients[0].contexts
        self.assertEqual(len(contexts), 1, contexts)
        at, event, context = contexts[0]
        self.assertEqual((at, event), (10.0, "PostToolUse"))  # at the first step after it, before the model's next
        self.assertIn("From @ana", context)
        self.assertIn("Please don't change the API in this PR.", context)
        kinds = [(kind, body) for _, kind, body in self.thread.posts if kind != "milestone"]
        self.assertEqual(kinds, [("message", "Understood: I will leave the API alone."), ("narration", "Now the tests.")])

    def test_each_message_is_relayed_once_and_the_sessions_own_posts_never(self):
        session = self.claimed()
        script = [(1.0, bash(1, "ls")), (1.0, tool_result(1, "a")), (1.0, assistant(2, text="Thinking.")),
                  (1.0, bash(3, "ls")), (1.0, tool_result(3, "b")), (1.0, assistant(4, text="Answer.")),
                  (1.0, bash(5, "ls")), (1.0, tool_result(5, "c")), (0.0, STOP)]

        async def during():
            await asyncio.sleep(3.5)
            self.thread.member_says("ana", "One question.")

        self.run_narrated(session, script, during)
        contexts = self.clients[0].contexts
        self.assertEqual([at for at, _, _ in contexts], [5.0])
        self.assertIn(("message", "Answer."), [(k, b) for _, k, b in self.thread.posts])

    def test_a_message_that_arrives_as_the_session_would_stop_keeps_it_going_to_answer(self):
        session = self.claimed()
        script = [(1.0, assistant(1, text="All done.")), (5.0, STOP),
                  (1.0, assistant(2, text="Yes: the tests cover the refusal.")), (0.0, STOP)]

        async def during():
            await asyncio.sleep(2.0)
            self.thread.member_says("ana", "Did you test the refusal?")

        ended = self.run_narrated(session, script, during)
        self.assertEqual([event for _, event, _ in self.clients[0].contexts], ["Stop"])
        self.assertIn(("message", "Yes: the tests cover the refusal."), [(k, b) for _, k, b in self.thread.posts])
        self.assertEqual(ended.final_message, "Yes: the tests cover the refusal.")

    def test_a_subagents_step_does_not_take_the_members_messages(self):
        session = self.claimed()
        script = [(1.0, bash(1, "ls")), (1.0, tool_result(1, "a", parent="tool_task")),
                  (1.0, bash(2, "ls")), (1.0, tool_result(2, "b")), (0.0, STOP)]

        async def during():
            await asyncio.sleep(1.5)
            self.thread.member_says("ana", "Hello.")

        self.run_narrated(session, script, during)
        self.assertEqual([at for at, _, _ in self.clients[0].contexts], [4.0])


class FakeHttp:
    """The metadata server and threads, as SessionThread's transport sees them."""

    def __init__(self, pages=None, post_status=201):
        self.calls, self.pages, self.post_status, self.tokens = [], list(pages or []), post_status, 0
        self.unauthorized_once = False

    def __call__(self, method, url, headers, body=None, timeout=30):
        self.calls.append((method, url, headers, body, timeout))
        parts = urllib.parse.urlsplit(url)
        if parts.path.endswith("/service-accounts/default/identity"):
            self.tokens += 1
            return 200, {}, f"eyJ.header-{self.tokens}.sig".encode()
        if self.unauthorized_once:
            self.unauthorized_once = False
            return 401, {}, b'{"error": "expired"}'
        if method == "POST":
            sent = json.loads(body)
            return self.post_status, {}, json.dumps({"seq": 1, **sent}).encode()
        return 200, {}, json.dumps(self.pages.pop(0)).encode()


class SessionThreadTest(unittest.TestCase):
    def session(self):
        from runner.models import Session

        return Session(id="a" * 32, project="jugonzal/architect-loop", skill="loop-build", arguments="",
                       model="claude-opus-5-5", sponsor="juan", budget_usd=1.0, plugin_release="v0.4.0",
                       branch=CONCERN, created_at="2026-10-24T12:00:00Z", concern=CONCERN)

    def test_it_posts_as_the_session_with_an_id_token_whose_audience_is_threads(self):
        http = FakeHttp()
        thread = SessionThread(THREADS_URL + "/", self.session(), transport=http, metadata="http://fakes:8713")
        thread.post("Started.", "milestone")
        (_, token_url, token_headers, _, _), (method, url, headers, body, timeout) = http.calls
        parts = urllib.parse.urlsplit(token_url)
        self.assertEqual(f"{parts.scheme}://{parts.netloc}{parts.path}",
                         "http://fakes:8713/computeMetadata/v1/instance/service-accounts/default/identity")
        self.assertEqual(urllib.parse.parse_qs(parts.query), {"audience": [THREADS_URL], "format": ["full"]})
        self.assertEqual(token_headers, {"Metadata-Flavor": "Google"})
        self.assertEqual(method, "POST")
        self.assertEqual(url, f"{THREADS_URL}/projects/jugonzal/architect-loop/sessions/{'a' * 32}/thread/messages")
        self.assertEqual(headers["Authorization"], "Bearer eyJ.header-1.sig")
        sent = json.loads(body)
        self.assertEqual(sent, {"body": "Started.", "kind": "milestone", "sponsor": "juan"})
        self.assertEqual(list(schema("NewMessage").iter_errors(sent)), [])
        self.assertLessEqual(timeout, 5.0)  # a slow thread fails fast, inside C1's 10 s

    def test_the_path_and_query_are_threads_own(self):
        operation = THREADS_SPEC["paths"][SESSION_MESSAGES]
        self.assertIn("runner", [next(iter(s)) for s in operation["post"]["security"]])
        self.assertIn("runner", [next(iter(s)) for s in operation["get"]["security"]])
        documented = {p["$ref"].rsplit("/", 1)[-1] for p in operation["get"]["parameters"]}
        page = {"messages": [], "next_after": None}
        self.assertEqual(list(schema("MessagePage").iter_errors(page)), [])
        http = FakeHttp(pages=[page])
        SessionThread(THREADS_URL, self.session(), transport=http).messages_after(0)
        query = urllib.parse.parse_qs(urllib.parse.urlsplit(http.calls[-1][1]).query)
        self.assertLessEqual(set(query), documented)
        self.assertEqual(query["kind"], ["message"])

    def test_it_reads_every_page_and_returns_the_seq_to_read_after(self):
        def message(seq, kind="message"):
            return {"seq": seq, "kind": kind, "body": f"m{seq}", "author": {"type": "person", "login": "ana"}}

        http = FakeHttp(pages=[{"messages": [message(3), message(5)], "next_after": 5},
                               {"messages": [message(8)], "next_after": None}])
        found, after = SessionThread(THREADS_URL, self.session(), transport=http).messages_after(2)
        self.assertEqual([m["seq"] for m in found], [3, 5, 8])
        self.assertEqual(after, 8)
        afters = [urllib.parse.parse_qs(urllib.parse.urlsplit(c[1]).query)["after"] for c in http.calls[1:]]
        self.assertEqual(afters, [["2"], ["5"]])

    def test_a_token_is_reused_and_minted_again_after_a_401(self):
        http = FakeHttp()
        thread = SessionThread(THREADS_URL, self.session(), transport=http)
        thread.post("one", "narration")
        thread.post("two", "narration")
        self.assertEqual(http.tokens, 1)
        http.unauthorized_once = True
        with self.assertRaises(ThreadsError):
            thread.post("three", "narration")
        thread.post("four", "narration")
        self.assertEqual(http.tokens, 2)

    def test_a_refused_post_raises(self):
        http = FakeHttp(post_status=409)
        with self.assertRaises(ThreadsError):
            SessionThread(THREADS_URL, self.session(), transport=http).post("x", "milestone")


class WordingTest(unittest.TestCase):
    def test_a_test_run_says_what_it_ran_and_how_it_ended(self):
        self.assertEqual(tests_milestone("pytest -q", False, "....\n12 passed, 1 skipped in 0.4s\n"),
                         "Tests run, passed: `pytest -q`. 12 passed, 1 skipped in 0.4s.")
        self.assertEqual(tests_milestone("sh scripts/check.sh", True, "nothing it recognises"),
                         "Tests run, failed: `sh scripts/check.sh`.")

    def test_only_gates_loop_md_lists_count(self):
        gates = gates_in(LOOP_MD)
        self.assertEqual(gates, {"merge": "jugonzal", "deploy": "jugonzal", "spending": "ana"})
        self.assertEqual(gates_named("A dispatch would cost $3 (gates: spending, made-up).", gates), ["spending"])
        self.assertEqual(gates_named("I stopped at the deploy gate.", gates), ["deploy"])
        self.assertEqual(gates_named("The merge is the owner's. All tests pass.", gates), [])

    def test_the_wording_of_each_ending_carries_the_estimate(self):
        from runner.models import Session

        thread = FakeThread()
        thread.clock = lambda: 0.0
        session = Session(id="b" * 32, project="p/r", skill="loop-status", arguments="", model="m", sponsor="juan",
                          budget_usd=1.0, plugin_release="v0.4.0", branch="main", created_at="", loop="command-center",
                          outcome="sponsor", spend={"usd": 1.5, "wall_clock_s": 61.2, "basis": "per-step usage"})

        async def go():
            narration = Narration(thread, session)
            narration.ended(session)
            await narration.close()

        asyncio.run(go())
        self.assertEqual(thread.posts[0][2], "Stopped by its sponsor. It spent about $1.50 over 61 s, an estimate "
                                             "(summed from each step at list price).")


class WiringTest(unittest.TestCase):
    def test_the_config_reads_the_threads_url_and_bounds_the_looks(self):
        config = Config.from_env({"RUNNER_THREADS_URL": THREADS_URL, "RUNNER_NARRATION_POLL_S": "2"})
        self.assertEqual((config.threads_url, config.narration_poll_s), (THREADS_URL, 2.0))
        self.assertEqual(Config().threads_url, "")
        self.assertLessEqual(Config().narration_poll_s, 5.0)
        for poll in (0, 5.5):
            with self.subTest(poll=poll), self.assertRaises(ValueError):
                Config(narration_poll_s=poll)

    def test_the_job_narrates_to_the_thread_its_config_names(self):
        env = {"RUNNER_STORE": os.path.join(scratch(self), "runner.sqlite3"), "RUNNER_SESSION_ID": "e" * 32,
               "RUNNER_APP_ID": "12345", "RUNNER_APP_INSTALLATION_ID": "678",
               "RUNNER_APP_SLUG": "architect-loop-runner", "RUNNER_APP_PRIVATE_KEY": PEM,
               "RUNNER_THREADS_URL": THREADS_URL, "RUNNER_METADATA_URL": "http://fakes:8713"}
        with mock.patch.object(main.RestGitHub, "bot_user_id", return_value=4321):
            job, _ = main.job_from_env(env)
            silent, _ = main.job_from_env({**env, "RUNNER_THREADS_URL": "", "RUNNER_APP_PRIVATE_KEY": PEM})
        thread = job.threads(SessionThreadTest().session())
        self.assertIsInstance(thread, SessionThread)
        self.assertEqual(thread.audience, THREADS_URL)
        self.assertIsNone(silent.threads)

    def test_the_manifest_names_threads_by_the_url_threads_checks_tokens_against(self):
        with open(os.path.join(SERVICES, "runner", "service.json")) as f:
            runner = json.load(f)
        with open(os.path.join(SERVICES, "threads", "service.json")) as f:
            threads = json.load(f)
        self.assertEqual(runner["settings"]["RUNNER_THREADS_URL"], threads["settings"]["THREADS_AUDIENCE"])
        self.assertIn("runner@{project}.iam.gserviceaccount.com",
                      threads["settings"]["THREADS_RUNNER_SERVICE_ACCOUNTS"])
        self.assertEqual(runner["identity"]["name"], "runner")  # the job runs as the service's identity


# The two commands session c79c36c ran on staging @633cbe4 (2026-10-26) that posted "Tests run, passed" without running
# any test: each carries a heredoc whose body names a test tool (narration-tests-milestone C1).
COMMIT_WITH_HEREDOC = """git add sandbox/build-target-3/hello.txt && git commit -q -F - <<'EOF'
Add the hello file that the third sandbox build target asks for

sandbox/build-target-3 C1 asks for the file. Checked with sh scripts/check.sh before and after.

Concern: sandbox/build-target-3
EOF"""
PR_BODY_HEREDOC = """cat > /tmp/prbody.md <<'EOF'
**Do not merge.** This is a sandbox target.

The runner's python3 -m unittest discover and sh scripts/check.sh both pass.
EOF"""


class HeredocTest(unittest.TestCase):
    def test_a_command_that_only_mentions_a_test_tool_in_a_heredoc_runs_no_tests(self):
        self.assertFalse(runs_tests(COMMIT_WITH_HEREDOC))
        self.assertFalse(runs_tests(PR_BODY_HEREDOC))
        self.assertFalse(runs_tests("cat <<EOF > notes.md\npytest\nEOF"))

    def test_a_command_that_runs_tests_still_does_whatever_follows_it(self):
        for command in ("pytest -q", "sh scripts/check.sh", "python3 -m unittest discover -s tests",
                        "cd services/runner && python -m unittest discover -s tests -v",
                        'sh -c "pytest -q"', "npm run test", "make check"):
            self.assertTrue(runs_tests(command), command)
        self.assertTrue(runs_tests("sh scripts/check.sh && cat > out.md <<'EOF'\nthe body\nEOF"))
        self.assertTrue(runs_tests("cat > out.md <<'EOF'\nthe body\nEOF\nsh scripts/check.sh"))

    def test_a_heredoc_ends_at_its_own_word_and_a_here_string_is_not_one(self):
        self.assertEqual(without_heredocs("cat <<'EOF'\nbody\nEOF\necho done"), "cat <<'EOF'\necho done")
        self.assertEqual(without_heredocs("cat <<-END\n\tbody\n\tEND\npwd"), "cat <<-END\npwd")
        self.assertEqual(without_heredocs("cat <<A <<B\none\nA\ntwo\nB\nls"), "cat <<A <<B\nls")
        self.assertEqual(without_heredocs("cat <<< 'x'\npytest -q"), "cat <<< 'x'\npytest -q")
        self.assertEqual(without_heredocs("echo $((1<<3))\npytest"), "echo $((1<<3))\npytest")
        self.assertEqual(without_heredocs("cat<<EOF\nbody\nEOF\nls"), "cat<<EOF\nls")

    def test_a_quoted_mention_is_still_matched_as_the_design_decided(self):
        # command-center/narration-tests-milestone D1 strips heredoc bodies and nothing else.
        self.assertTrue(runs_tests('git commit -m "run check.sh before merging"'))


class TestsMilestoneTest(NarrationTest):
    def test_only_a_command_that_runs_tests_posts_a_tests_milestone(self):
        session = self.claimed(budget=2.0)
        script = [
            (1.0, bash(1, "sh scripts/check.sh")), (20.0, tool_result(1, "ok  skills\nok  independence")),  # t=21
            (1.0, bash(2, COMMIT_WITH_HEREDOC)), (1.0, tool_result(2, "")),
            (1.0, bash(3, PR_BODY_HEREDOC)), (1.0, tool_result(3, "")),
            (1.0, assistant(4, text="Done.")), (0.0, STOP),
        ]
        self.run_narrated(session, script)
        tests = [body for _, body in self.thread.milestones() if body.startswith("Tests run")]
        self.assertEqual(len(tests), 1, tests)
        self.assertIn("sh scripts/check.sh", tests[0])


if __name__ == "__main__":
    unittest.main()
