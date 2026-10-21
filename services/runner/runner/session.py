"""One session's job: run a loop skill with the Agent SDK on the session's own clone, publish its spend while it
runs, stop it at its budget or when its sponsor asks, and record how it ended (session-runner C1, C4; D2, D3).

The job runs once per session, as one execution of a Cloud Run job (D2). It shares the runner's store with the
dispatching service, which is how its spend reaches the API and how a stop request reaches it.
"""

import asyncio
import logging
import re
import time

from claude_agent_sdk import AssistantMessage, ClaudeAgentOptions, ResultMessage

from .config import ALLOWED_TOOLS
from .github import JOB_PERMISSIONS
from .models import iso, utcnow
from .spend import Meter
from .workspace import trailers_for

log = logging.getLogger("runner.session")


def claude_client(options):
    """The real Agent SDK client, looked up when called so that the tests can keep it out of reach."""
    import claude_agent_sdk

    return claude_agent_sdk.ClaudeSDKClient(options=options)


def build_options(session, prepared, env):
    return ClaudeAgentOptions(
        cwd=prepared.clone,
        model=session.model,  # D5: from the runner's skill to model map
        max_budget_usd=session.budget_usd,  # D21: the SDK stops at the first response that crosses it
        permission_mode="dontAsk",  # D3: the container is the sandbox
        allowed_tools=list(ALLOWED_TOOLS),
        setting_sources=[],  # no user, project or local settings: the only skills are the release's
        plugins=[{"type": "local", "path": prepared.plugin_dir}],  # D17: the release, never the clone's plugin/
        env=env,
    )


def prompt_for(session, prepared):
    return " ".join(part for part in (f"/{prepared.plugin_name}:{session.skill}", session.concern,
                                      session.arguments.strip()) if part)


def with_trailers(body, concern, sponsor):
    """A pull request body with the session's trailers, or None when it already has them (C1).

    Like the commit-msg hook, it keeps a `Concern:` the skill wrote and adds `Sponsored-by:` beside it."""
    lines = (body or "").splitlines()
    concern_at = [i for i, line in enumerate(lines) if re.match(r"(?i)^concern:\s*\S", line)]
    sponsored = any(re.match(r"(?i)^sponsored-by:\s*\S", line) for line in lines)
    if sponsored and concern_at:
        return None
    if concern_at:
        lines.insert(concern_at[-1] + 1, f"Sponsored-by: {sponsor}")
        return "\n".join(lines)
    added = [f"Concern: {concern}"] + ([] if sponsored else [f"Sponsored-by: {sponsor}"])
    return "\n".join(lines + ([""] if lines else []) + added)


class SessionJob:
    def __init__(self, config, store, github, workspace, client_factory=claude_client, now=utcnow,
                 monotonic=time.monotonic):
        self.config, self.store, self.github, self.workspace = config, store, github, workspace
        self.client_factory, self.now, self.monotonic = client_factory, now, monotonic

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
        self._done = asyncio.Event()
        meter = Meter(self.config.prices[session.model], session.budget_usd, self.monotonic)
        publisher = asyncio.create_task(self._publish_every(meter))
        if session.stop_requested:
            self._interrupted = "sponsor"
        prepared, result, outcome, final = None, None, "error", None
        try:
            prepared = await asyncio.to_thread(self.workspace.prepare, session)
            if (await asyncio.to_thread(self.store.get, session_id)).stop_requested:
                self._interrupted = self._interrupted or "sponsor"
            if self._interrupted:
                outcome = self._interrupted
            else:
                token = await asyncio.to_thread(self.github.installation_token, JOB_PERMISSIONS)
                options = build_options(session, prepared, {"GH_TOKEN": token, "GITHUB_TOKEN": token})
                result = await self._converse(options, prompt_for(session, prepared), meter)
                outcome = self._outcome(result)
        except Exception:
            log.exception("session %s failed", session_id)
            outcome = "error"
        finally:
            self._done.set()
            await publisher
        now = iso(self.now())
        if result is not None and result.total_cost_usd is not None:
            final = meter.final(now, result.total_cost_usd, result.usage)
        else:
            final = meter.final(now)
        pulls = await asyncio.to_thread(self._sign_pull_requests, session, prepared) if prepared else []
        return self.store.finish(session_id, outcome, final, pulls, iso(self.now()))

    async def _converse(self, options, prompt, meter):
        result = None
        async with self.client_factory(options) as client:
            self._client = client
            await client.query(prompt)
            if self._interrupted:  # a stop that arrived while the client was starting
                await client.interrupt()
            async for message in client.receive_response():
                if isinstance(message, AssistantMessage):
                    meter.add(message.message_id, message.usage)
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
                body = with_trailers(pull.get("body"), trailers["Concern"], trailers["Sponsored-by"])
                if body is not None:
                    self.github.set_pull_request_body(pull["number"], body)
            return [{"number": p["number"], "url": p["url"], "head": p["head"]} for p in pulls]
        except Exception:
            log.exception("could not add the trailers to session %s's pull requests", session.id)
            return []
