"""One session's job: run a loop skill with the Agent SDK on the session's own clone, publish its spend while it
runs, stop it at its budget or when its sponsor asks, and record how it ended (session-runner C4, C5; D2, D3).

The job runs once per session, as one execution of a Cloud Run job (D2). It shares the runner's store with the
dispatching service, which is how its spend reaches the API and how a stop request reaches it.

When the runner's config names the threads service, the job also narrates the session to the session's own thread
there, and relays the members' messages into it (session-narration C1, C2; see Narration).
"""

import asyncio
import json
import logging
import os
import re
import time
import urllib.parse

from claude_agent_sdk import (AssistantMessage, ClaudeAgentOptions, HookMatcher, ResultMessage, TextBlock,
                              ToolResultBlock, ToolUseBlock, UserMessage)

from .config import ALLOWED_TOOLS
from .github import JOB_PERMISSIONS, urllib_transport
from .launcher import METADATA
from .models import iso, utcnow
from .spend import Meter
from .workspace import trailers_for

log = logging.getLogger("runner.session")


def claude_client(options):
    """The real Agent SDK client, looked up when called so that the tests can keep it out of reach."""
    import claude_agent_sdk

    return claude_agent_sdk.ClaudeSDKClient(options=options)


def build_options(session, prepared, env, hooks=None):
    return ClaudeAgentOptions(
        cwd=prepared.clone,
        model=session.model,  # D5: from the runner's skill to model map
        max_budget_usd=session.budget_usd,  # D21: the SDK stops at the first response that crosses it
        permission_mode="dontAsk",  # D3: the container is the sandbox
        allowed_tools=list(ALLOWED_TOOLS),
        setting_sources=[],  # no user, project or local settings: the only skills are the release's
        plugins=[{"type": "local", "path": prepared.plugin_dir}],  # D17: the release, never the clone's plugin/
        env=env,
        hooks=hooks,  # session-narration C2: the relay of the members' messages, when the session narrates
    )


def prompt_for(session, prepared):
    return " ".join(part for part in (f"/{prepared.plugin_name}:{session.skill}", session.target,
                                      session.arguments.strip()) if part)


class FinalMessage:
    """The session's last assistant message (runner-dispatch C3; app-inbox D1): the text of the last model response
    of the session itself, not of a subagent, that said anything. One response can arrive as several messages that
    share its id, so their text is kept together."""

    def __init__(self):
        self._id, self._parts = None, []

    def add(self, message):
        if message.parent_tool_use_id is not None:
            return
        texts = [block.text for block in message.content if isinstance(block, TextBlock) and block.text.strip()]
        if not texts:
            return
        if message.message_id is None or message.message_id != self._id:
            self._id, self._parts = message.message_id, []
        self._parts += texts

    @property
    def text(self):
        return "\n\n".join(self._parts) if self._parts else None


def with_trailers(body, concern, sponsor):
    """A pull request body with the session's trailers, or None when it already has them (runner-dispatch C1).

    `concern` is None except in a /loop-build session (command-center/D45), so only that one adds `Concern:`. Like
    the commit-msg hook, it keeps a `Concern:` the skill wrote and adds `Sponsored-by:` beside it."""
    lines = (body or "").splitlines()
    concern_at = [i for i, line in enumerate(lines) if re.match(r"(?i)^concern:\s*\S", line)]
    sponsored = any(re.match(r"(?i)^sponsored-by:\s*\S", line) for line in lines)
    if sponsored and (concern_at or concern is None):
        return None
    if concern_at:
        lines.insert(concern_at[-1] + 1, f"Sponsored-by: {sponsor}")
        return "\n".join(lines)
    added = ([f"Concern: {concern}"] if concern else []) + ([] if sponsored else [f"Sponsored-by: {sponsor}"])
    return "\n".join(lines + ([""] if lines else []) + added)


# Narration (session-narration, per command-center/D1, D6, D28). The job posts to the session's thread on the threads
# service (services/threads/openapi.yaml) as the session, labelled with its sponsor, and reads the members' messages
# there. Milestones carry the kind `milestone`, so a client collapses the rest, `narration`, by default; the session's
# answer to a member is a `message`.

IDENTITY_PATH = "/computeMetadata/v1/instance/service-accounts/default/identity"
MAX_BODY = 65536  # threads' NewMessage body is at most this long

# A Bash command that runs a project's tests or checks, as LOOP.md §4 and the usual tools name them.
TEST_COMMAND = re.compile(r"\b(unittest|pytest|tox|nox|check\.sh|smoke\.sh|jest|vitest|"
                          r"(npm|pnpm|yarn|bun)\s+(run\s+)?(test|check)|(go|cargo|mix|dotnet)\s+test|"
                          r"make\s+(test|check))\b")
PR_CREATE = re.compile(r"\bgh\s+pr\s+create\b")
GIT_PUSH = re.compile(r"\bgit\b[^\n;&|]*\bpush\b")
PR_URL = re.compile(r"https?://\S+?/pull/(\d+)\b")
# What a test run says of its result: unittest's `Ran 41 tests` and `OK` or `FAILED (...)`, and pytest's and most
# others' `41 passed, 2 failed`.
TEST_SUMMARY = re.compile(r"(\bRan \d+ tests?\b.*|^(OK|FAILED)\b.*|\b\d+ (passed|failed|errors?|skipped)\b.*)",
                          re.MULTILINE)
# A gate as LOOP.md §2 lists it, `(key: deploy; holder: jugonzal)`, and as a session names it, `(gates: deploy)`.
GATE_KEY = re.compile(r"\(key:\s*([a-z][a-z-]*)\s*;\s*holder:\s*([^)]+?)\s*\)")
GATES_NOTATION = re.compile(r"\bgates?:\s*([a-z][a-z-]*(?:\s*,\s*[a-z][a-z-]*)*)", re.IGNORECASE)

ENDINGS = {
    "completed": "Finished",
    "budget": "Stopped at its budget",
    "sponsor": "Stopped by its sponsor",
    "error": "Stopped by an error",
    "lost": "Stopped: the runner lost track of it",
}
BASES = {"sdk result": "the Agent SDK's estimate", "per-step usage": "summed from each step at list price"}


class ThreadsError(Exception):
    pass


def identity_token(audience, transport=urllib_transport, metadata=METADATA):
    """An ID token for the job's service identity with `audience` as its audience, from the metadata server Cloud Run
    provides. Google signs it, and threads checks it (command-center/D28)."""
    query = urllib.parse.urlencode({"audience": audience, "format": "full"})
    status, _, data = transport("GET", f"{metadata.rstrip('/')}{IDENTITY_PATH}?{query}", {"Metadata-Flavor": "Google"})
    if status != 200:
        raise ThreadsError(f"the metadata server answered {status} for an ID token")
    return data.decode().strip()


class SessionThread:
    """One session's thread on the threads service, as that session. Its URL is threads' own, which is also the
    audience of the ID token it sends (command-center/D28, D46)."""

    TOKEN_REUSE_S = 1800.0  # Google's ID tokens last an hour; one is reused for half of it

    def __init__(self, url, session, transport=urllib_transport, token=None, metadata=METADATA,
                 clock=time.monotonic, timeout=5.0):
        self.audience = url.rstrip("/")
        self.url = (f"{self.audience}/projects/{session.project}/sessions/"
                    f"{urllib.parse.quote(session.id)}/thread/messages")
        self.sponsor, self.transport, self.clock, self.timeout = session.sponsor, transport, clock, timeout
        self._mint = token or (lambda: identity_token(self.audience, transport, metadata))
        self._token, self._minted = None, 0.0

    def _bearer(self):
        if self._token is None or self.clock() - self._minted > self.TOKEN_REUSE_S:
            self._token, self._minted = self._mint(), self.clock()
        return self._token

    def _call(self, method, url, body=None):
        headers = {"Authorization": f"Bearer {self._bearer()}", "Accept": "application/json"}
        data = None
        if body is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(body).encode()
        status, _, raw = self.transport(method, url, headers, data, timeout=self.timeout)
        if status == 401:
            self._token = None  # the next call mints a new one
        return status, raw

    def post(self, body, kind):
        """Post as the session, naming its sponsor, and return the message as threads stored it."""
        if len(body) > MAX_BODY:
            body = body[:MAX_BODY - 1] + "…"
        status, raw = self._call("POST", self.url, {"body": body, "kind": kind, "sponsor": self.sponsor})
        if status != 201:
            raise ThreadsError(f"posting to the session's thread answered {status}: {raw[:200]!r}")
        return json.loads(raw)

    def messages_after(self, after):
        """The thread's messages of kind `message` whose `seq` is above `after`, oldest first, and the `seq` to read
        after next time."""
        found = []
        while True:
            query = urllib.parse.urlencode({"after": after, "kind": "message", "limit": 100})
            status, raw = self._call("GET", f"{self.url}?{query}")
            if status != 200:
                raise ThreadsError(f"reading the session's thread answered {status}: {raw[:200]!r}")
            page = json.loads(raw)
            found += page["messages"]
            after = max([after] + [m["seq"] for m in page["messages"]])
            if page.get("next_after") is None:
                return found, after
            after = max(after, page["next_after"])


def result_text(block):
    content = block.content
    if isinstance(content, list):
        return "\n".join(part.get("text", "") for part in content if isinstance(part, dict))
    return content or ""


def one_line(text, limit=160):
    text = " ".join(text.split())
    return text if len(text) <= limit else text[:limit - 1] + "…"


def tests_milestone(command, failed, output):
    summary = [one_line(m.group(0), 120) for m in TEST_SUMMARY.finditer(output)][-2:]
    said = f" {'; '.join(summary)}." if summary else ""
    return f"Tests run, {'failed' if failed else 'passed'}: `{one_line(command)}`.{said}"


def gates_in(loop_md):
    """The gates LOOP.md §2 lists, as {key: holder}."""
    return dict(GATE_KEY.findall(loop_md or ""))


def gates_named(text, gates):
    """The gates a session's last message says it stopped at: those it names in LOOP.md's own notation,
    `(gates: deploy)`, or in a sentence that says it stopped at a gate. Only a gate LOOP.md lists counts."""
    named = []
    for found in GATES_NOTATION.finditer(text or ""):
        named += [key.strip().lower() for key in found.group(1).split(",")]
    for sentence in re.split(r"(?<=[.!?])\s+|\n+", text or ""):
        if re.search(r"\bstop", sentence, re.IGNORECASE) and re.search(r"\bgates?\b", sentence, re.IGNORECASE):
            named += [key for key in gates if re.search(rf"\b{re.escape(key)}\b", sentence, re.IGNORECASE)]
    return [key for key in dict.fromkeys(named) if key in gates]


def dollars(usd):
    return f"${usd:,.2f}" if usd >= 1 else f"${usd:.4f}"


def relay_text(messages):
    said = "\n\n".join(f"From @{m['author']['login']}, at {m['created_at']}:\n{m['body']}" for m in messages)
    return ("Members of the project wrote to this session's thread, where what you say is posted for them. Read their "
            "messages before your next step, answer them in your next message, and take their direction as far as "
            f"LOOP.md and your skill let you:\n\n{said}")


def read_loop_md(clone):
    try:
        with open(os.path.join(clone, "LOOP.md")) as f:
            return f.read()
    except OSError:
        return ""


class Narration:
    """What a session tells its thread as it happens (session-narration C1), and the members' messages it reads from
    there before each of its steps (C2). Without a thread it does nothing.

    The milestones: started; a branch opened (pushed); tests run, with their result; a pull request opened; stopped at
    a gate, naming it; and how it ended, with what it spent (command-center/D23: the final estimate). The job knows the
    first and the last itself. It learns of tests and of `gh pr create` from the session's own tool calls, and of
    pushed branches and pull requests opened any other way by looking every `poll_s` seconds (at most 5, per
    MAX_NARRATION_POLL_S). Posts go out one at a time and in order, beside the session, so a slow thread never slows
    the session; a post that fails is logged and dropped, since narration must never end a session.
    """

    def __init__(self, thread, session, poll_s=5.0):
        self.thread, self.session, self.poll_s = thread, session, poll_s
        self._queue, self._poster, self._looker = asyncio.Queue(), None, None
        self._look_now = asyncio.Event()
        self._tools, self._branches, self._pulls, self._heads_with_pulls = {}, set(), set(), set()
        self._seen, self._answering = 0, False

    @property
    def on(self):
        return self.thread is not None

    def _say(self, kind, body):
        if self.on and body and body.strip():
            if self._poster is None:
                self._poster = asyncio.create_task(self._post_each())
            self._queue.put_nowait((kind, body))

    async def _post_each(self):
        while True:
            kind, body = await self._queue.get()
            if kind is None:
                return
            try:
                await asyncio.to_thread(self.thread.post, body, kind)
            except Exception:
                log.exception("could not post a %s to session %s's thread", kind, self.session.id)

    def started(self):
        s = self.session
        self._say("milestone", f"Started /{s.skill} on {s.target}, on {s.model} with a budget of "
                               f"{dollars(s.budget_usd)} and plugin release {s.plugin_release}, sponsored by "
                               f"@{s.sponsor}.")

    def observe(self, message):
        """Each message the session streams. Its text is narration, or its answer to a member; its tool calls are
        kept until their results say whether they ran tests or opened a pull request."""
        if not self.on:
            return
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, ToolUseBlock):
                    self._tools[block.id] = (block.name, block.input or {})
                elif (isinstance(block, TextBlock) and block.text.strip()
                      and message.parent_tool_use_id is None):  # a subagent's text is not the session's
                    self._say("message" if self._answering else "narration", block.text)
                    self._answering = False
        elif isinstance(message, UserMessage) and isinstance(message.content, list):
            for block in message.content:
                if isinstance(block, ToolResultBlock):
                    self._tool_result(block)

    def _tool_result(self, block):
        name, given = self._tools.pop(block.tool_use_id, (None, {}))
        command = given.get("command") if name == "Bash" else None
        if not isinstance(command, str):
            return
        failed, output = bool(block.is_error), result_text(block)
        if TEST_COMMAND.search(command):
            self._say("milestone", tests_milestone(command, failed, output))
        if PR_CREATE.search(command) and not failed:
            found = PR_URL.search(output)
            if found:
                self._pull_opened(int(found.group(1)), found.group(0), None)
        if GIT_PUSH.search(command):
            self._look_now.set()

    def _pull_opened(self, number, url, head):
        if head:
            self._heads_with_pulls.add(head)
        if number in self._pulls:
            return
        self._pulls.add(number)
        self._say("milestone", f"Pull request #{number} opened: {url}")

    def pulls_opened(self, pulls):
        """Pull requests the job found the session opened, announcing any it has not announced yet."""
        for pull in pulls:
            self._pull_opened(pull["number"], pull["url"], pull.get("head"))

    def watch(self, workspace, clone, github):
        if self.on and self._looker is None:
            self._looker = asyncio.create_task(self._look_every(workspace, clone, github))

    async def _look_every(self, workspace, clone, github):
        while True:
            self._look_now.clear()
            await self._look(workspace, clone, github)
            try:
                await asyncio.wait_for(self._look_now.wait(), self.poll_s)
            except asyncio.TimeoutError:
                pass

    async def _look(self, workspace, clone, github):
        try:
            pushed = await asyncio.to_thread(workspace.pushed_branches, clone)
            for branch in pushed:
                if branch not in self._branches:
                    self._branches.add(branch)
                    self._say("milestone", f"Branch {branch} opened: pushed to GitHub.")
            waiting = [b for b in pushed if b not in self._heads_with_pulls]
            if waiting:
                self.pulls_opened(await asyncio.to_thread(github.pull_requests_for_heads, waiting))
        except Exception:
            log.exception("could not look for session %s's branches and pull requests", self.session.id)

    async def stop_watching(self, workspace, clone, github):
        """Stop looking, after one last look, so that a branch pushed at the very end is still announced."""
        if self._looker is None:
            return
        self._looker.cancel()
        try:
            await self._looker
        except asyncio.CancelledError:
            pass
        self._looker = None
        await self._look(workspace, clone, github)

    def hooks(self):
        """The SDK hooks that relay the members' messages (C2): after each tool call, before the model's next step;
        and when the session would stop, which keeps it going to answer a message that has just arrived."""
        if not self.on:
            return None
        return {"PostToolUse": [HookMatcher(hooks=[self._relay])], "Stop": [HookMatcher(hooks=[self._relay])]}

    async def _relay(self, data, tool_use_id, context):
        if data.get("agent_id"):  # a subagent's step: the session hears its members at its own steps
            return {}
        try:
            messages, self._seen = await asyncio.to_thread(self.thread.messages_after, self._seen)
        except Exception:
            log.exception("could not read session %s's thread", self.session.id)
            return {}
        from_members = [m for m in messages if (m.get("author") or {}).get("type") == "person"]
        if not from_members:
            return {}
        self._answering = True
        return {"hookSpecificOutput": {"hookEventName": data.get("hook_event_name") or "PostToolUse",
                                       "additionalContext": relay_text(from_members)}}

    def gates(self, final_message, loop_md):
        gates = gates_in(loop_md)
        named = gates_named(final_message, gates)
        if named:
            held = ", ".join(f"{key} (held by {gates[key]})" for key in named)
            self._say("milestone", f"Stopped at {'a gate' if len(named) == 1 else 'gates'}: {held}.")

    def ended(self, session):
        if session is None:
            return
        spend = session.spend or {}
        said = ENDINGS.get(session.outcome, f"Ended: {session.outcome}")
        if spend.get("usd") is not None:
            said += (f". It spent about {dollars(spend['usd'])} over {spend.get('wall_clock_s') or 0:.0f} s, an "
                     f"estimate ({BASES.get(spend.get('basis'), spend.get('basis'))})")
        self._say("milestone", said + ".")

    async def close(self, timeout=20.0):
        """Post what is still queued, for at most `timeout` seconds."""
        if self._poster is None:
            return
        self._queue.put_nowait((None, None))
        try:
            await asyncio.wait_for(self._poster, timeout)
        except asyncio.TimeoutError:
            log.error("session %s's thread took over %s s; %d posts were dropped", self.session.id, timeout,
                      self._queue.qsize())


class SessionJob:
    def __init__(self, config, store, github, workspace, client_factory=claude_client, now=utcnow,
                 monotonic=time.monotonic, threads=None):
        self.config, self.store, self.github, self.workspace = config, store, github, workspace
        self.client_factory, self.now, self.monotonic = client_factory, now, monotonic
        # session-narration: a session's thread, as `threads(session)`, or None when the session narrates nowhere.
        self.threads = threads

    async def run(self, session_id):
        session = self.store.get(session_id)
        if session is None or not session.active:
            return session
        if session.started_at is not None:
            # Its job already started once: a retried task would run the skill again from nothing and spend twice.
            log.error("session %s already started at %s; it is not started again", session_id, session.started_at)
            return self.store.finish(session_id, "error", None, [], iso(self.now()))
        session = self.store.mark_running(session_id, iso(self.now()))
        self._id, self._client, self._interrupted = session_id, None, None
        self._done, self._said = asyncio.Event(), FinalMessage()
        meter = Meter(self.config.prices[session.model], session.budget_usd, self.monotonic)
        publisher = asyncio.create_task(self._publish_every(meter))
        if session.stop_requested:
            self._interrupted = "sponsor"
        self._narration = narration = Narration(self._thread_for(session), session, self.config.narration_poll_s)
        narration.started()
        prepared, result, outcome, final = None, None, "error", None
        try:
            prepared = await asyncio.to_thread(self.workspace.prepare, session)
            narration.watch(self.workspace, prepared.clone, self.github)
            if (await asyncio.to_thread(self.store.get, session_id)).stop_requested:
                self._interrupted = self._interrupted or "sponsor"
            if self._interrupted:
                outcome = self._interrupted
            else:
                token = await asyncio.to_thread(self.github.installation_token, JOB_PERMISSIONS)
                options = build_options(session, prepared, {"GH_TOKEN": token, "GITHUB_TOKEN": token},
                                        hooks=narration.hooks())
                result = await self._converse(options, prompt_for(session, prepared), meter)
                outcome = self._outcome(result)
        except Exception:
            log.exception("session %s failed", session_id)
            outcome = "error"
        finally:
            self._done.set()
            await publisher
            if prepared is not None:
                await narration.stop_watching(self.workspace, prepared.clone, self.github)
        now = iso(self.now())
        if result is not None and result.total_cost_usd is not None:
            final = meter.final(now, result.total_cost_usd, result.usage)
        else:
            final = meter.final(now)
        pulls = await asyncio.to_thread(self._sign_pull_requests, session, prepared) if prepared else []
        narration.pulls_opened(pulls)
        said = self._said.text or (result.result if result is not None else None)
        ended = self.store.finish(session_id, outcome, final, pulls, iso(self.now()), final_message=said)
        if narration.on and prepared is not None and outcome == "completed":
            narration.gates(said, await asyncio.to_thread(read_loop_md, prepared.clone))
        narration.ended(ended)
        await narration.close()
        return ended

    def _thread_for(self, session):
        if self.threads is None:
            return None
        try:
            return self.threads(session)
        except Exception:  # narration must never keep a session from running
            log.exception("session %s cannot narrate to its thread", session.id)
            return None

    async def _converse(self, options, prompt, meter):
        result = None
        async with self.client_factory(options) as client:
            self._client = client
            await client.query(prompt)
            if self._interrupted:  # a stop that arrived while the client was starting
                await client.interrupt()
            async for message in client.receive_response():
                self._narration.observe(message)
                if isinstance(message, AssistantMessage):
                    meter.add(message.message_id, message.usage)
                    self._said.add(message)
                    if meter.crossed:
                        # D21: stop at the first response that crosses the budget, even if the SDK has not.
                        await self._interrupt("budget")
                elif isinstance(message, ResultMessage):
                    result = message
            self._client = None
        return result

    async def _interrupt(self, reason):
        if self._interrupted:
            return
        self._interrupted = reason
        if self._client is not None:
            await self._client.interrupt()

    def _outcome(self, result):
        if result is not None and result.subtype == "error_max_budget_usd":
            return "budget"
        if self._interrupted:
            return self._interrupted
        if result is None or result.is_error or result.subtype != "success":
            return "error"
        return "completed"

    async def _publish_every(self, meter):
        """D23: publish the running estimate at least every spend_interval_s (at most 10 s), and pick up a stop."""
        while True:
            now = iso(self.now())
            try:
                stop = await asyncio.to_thread(self.store.publish, self._id, meter.snapshot(now), now)
                if stop and not self._interrupted:
                    current = await asyncio.to_thread(self.store.get, self._id)
                    await self._interrupt("sponsor" if current and current.stop_requested else "lost")
            except Exception:  # a missed publication must not end the session; the next one may succeed
                log.exception("could not publish session %s's spend", self._id)
            try:
                await asyncio.wait_for(self._done.wait(), self.config.spend_interval_s)
                return
            except asyncio.TimeoutError:
                continue

    def _sign_pull_requests(self, session, prepared):
        """Put the session's trailers in the bodies of the pull requests it opened, from the branches it pushed."""
        try:
            heads = self.workspace.pushed_branches(prepared.clone)
            if not heads:
                return []
            pulls = self.github.pull_requests_for_heads(heads)
            trailers = dict(trailers_for(session))
            for pull in pulls:
                body = with_trailers(pull.get("body"), trailers.get("Concern"), trailers["Sponsored-by"])
                if body is not None:
                    self.github.set_pull_request_body(pull["number"], body)
            return [{"number": p["number"], "url": p["url"], "head": p["head"]} for p in pulls]
        except Exception:
            log.exception("could not add the trailers to session %s's pull requests", session.id)
            return []
