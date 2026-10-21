"""The runner's tests. None of them may start a real Agent SDK session or reach the Anthropic API
(LOOP.md §2, spending): the key is dropped from the environment and the SDK's entry points refuse to run."""

import os

os.environ.pop("ANTHROPIC_API_KEY", None)
os.environ.pop("RUNNER_APP_PRIVATE_KEY", None)

try:
    import claude_agent_sdk
except ImportError:  # the trailer check's tests run without the SDK
    claude_agent_sdk = None


class RealSessionRefused(AssertionError):
    pass


def _refuse(*args, **kwargs):
    raise RealSessionRefused("a test tried to start a real Agent SDK session")


if claude_agent_sdk is not None:
    claude_agent_sdk.ClaudeSDKClient = _refuse
    claude_agent_sdk.query = _refuse
