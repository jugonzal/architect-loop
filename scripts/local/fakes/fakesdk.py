"""The local harness's stand-in for the Agent SDK's client (command-center/local-harness, per command-center/D53).

`RUNNER_SDK_CLIENT=fakesdk:client` makes a session's job run this instead of the SDK. It plays a session without a
model, on the session's own clone, so the runner's wiring runs end to end and nothing is spent: on a branch of its
own (a /loop-build on a concern) it commits one file, which the runner's commit-msg hook gives its trailers, pushes
the branch to the fake GitHub, and opens a pull request there with the job's installation token. Along the way it
reports made-up usage, so the job publishes a running estimate, and it ends with a made-up cost and a last message
that says what it did. It takes FAKE_SDK_SECONDS (default 8), so the session is seen running.

The fake Cloud Run puts this file on the job container's import path, so it runs inside the runner's own image,
which has the SDK's message types.
"""

import asyncio
import json
import os
import subprocess
import urllib.parse
import urllib.request

from claude_agent_sdk import AssistantMessage, ResultMessage, TextBlock

MODEL = "claude-opus-5-5"
COST_USD = 0.0123  # made up: the result reports it as the SDK's estimate, and nothing was spent
STEP_USAGE = {"input_tokens": 2000, "output_tokens": 50, "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0}
FILE = "local-harness-session.md"


def client(options):
    return FakeClient(options)


def final_text(target, pull):
    if pull is None:
        return f"Ran on {target} with the local harness's fake Agent SDK: no model was called and nothing was spent."
    return (f"Opened pull request #{pull['number']} ({pull['html_url']}) for {target}, from the local harness's "
            f"fake Agent SDK: no model was called and nothing was spent.")


class FakeClient:
    def __init__(self, options):
        self.options, self.prompt = options, ""
        self.seconds = float(os.environ.get("FAKE_SDK_SECONDS") or 8)
        self._stop = asyncio.Event()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def query(self, prompt):
        self.prompt = prompt

    async def interrupt(self):
        self._stop.set()

    async def _wait(self, seconds):
        """False when the session was interrupted while it waited."""
        try:
            await asyncio.wait_for(self._stop.wait(), seconds)
            return False
        except asyncio.TimeoutError:
            return True

    def _said(self, n, text):
        return AssistantMessage(content=[TextBlock(text=text)], model=MODEL, usage=dict(STEP_USAGE),
                                message_id=f"local_msg_{n}")

    def _result(self, subtype, text=None, turns=1):
        return ResultMessage(subtype=subtype, duration_ms=int(self.seconds * 1000), duration_api_ms=0,
                             is_error=subtype != "success", num_turns=turns, session_id="local-fake-sdk",
                             total_cost_usd=COST_USD, result=text,
                             usage={key: value * turns for key, value in STEP_USAGE.items()})

    async def receive_response(self):
        words = self.prompt.split()
        skill = words[0].rsplit(":", 1)[-1] if words else ""
        target = words[1] if len(words) > 1 else ""
        yield self._said(1, f"Running {skill} on {target} with the local harness's fake Agent SDK.")
        if not await self._wait(self.seconds / 3):
            yield self._result("error_during_execution")
            return
        pull = await asyncio.to_thread(self._build, target)
        yield self._said(2, f"Pushed {pull['head']['ref']}." if pull else "Nothing to push from main.")
        if not await self._wait(self.seconds / 3):
            yield self._result("error_during_execution", turns=2)
            return
        text = final_text(target, pull)
        yield self._said(3, text)
        if not await self._wait(self.seconds / 3):
            yield self._result("error_during_execution", turns=3)
            return
        yield self._result("success", text, turns=3)

    def _git(self, *args):
        env = {**os.environ, **(self.options.env or {})}
        return subprocess.run(["git", *args], cwd=self.options.cwd, env=env, check=True, capture_output=True,
                              text=True).stdout.strip()

    def _build(self, target):
        """On the session's own branch: commit, push, and open a pull request on the fake GitHub."""
        branch = self._git("rev-parse", "--abbrev-ref", "HEAD")
        if branch in ("main", "HEAD"):
            return None
        with open(os.path.join(self.options.cwd, FILE), "w") as f:
            f.write(f"A session on {target}, played by the local harness's fake Agent SDK.\n")
        self._git("add", FILE)
        self._git("commit", "--quiet", "-m", f"Record a local harness session on {target}",
                  "-m", "Written by the local harness's fake Agent SDK; no model ran.")
        self._git("push", "--quiet", "--set-upstream", "origin", branch)
        project = urllib.parse.urlsplit(self._git("remote", "get-url", "origin")).path.strip("/").removesuffix(".git")
        token = (self.options.env or {}).get("GH_TOKEN", "")
        pull = {"title": f"Build {target} (local harness)", "head": branch, "base": "main",
                "body": f"A pull request the local harness's fake Agent SDK opened for {target}."}
        request = urllib.request.Request(
            f"{os.environ['RUNNER_GITHUB_API_URL'].rstrip('/')}/repos/{project}/pulls", method="POST",
            data=json.dumps(pull).encode(), headers={"Authorization": f"Bearer {token}",
                                                     "Content-Type": "application/json",
                                                     "Accept": "application/vnd.github+json"})
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read())
