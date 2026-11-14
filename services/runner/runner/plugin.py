"""The plugin's source: the repository that releases the skills, which need not be the project a runner serves
(plugin-source/plugin-repository).

It is read with git alone and no credentials (plugin-source/D1): the release tags with `git ls-remote`, and one
release with `git fetch` of its tag. So the repository must be public, nothing is installed or granted on it, and
no REST call is made about it. Every command refuses to prompt and has a timeout, so a repository that is private,
missing or slow fails instead of waiting.
"""

import os
import subprocess

from .github import GitHubError, newest_release

LS_REMOTE_TIMEOUT_S = 10.0
FETCH_TIMEOUT_S = 60.0


class PluginSourceError(GitHubError):
    """The plugin's repository did not answer git as expected. The dispatcher treats it as any upstream failure."""


class PluginSource:
    def __init__(self, url, env=None):
        self.url = url
        # No prompt and no credential helper: a read that would need credentials fails at once (D1).
        self.env = {**(os.environ if env is None else env), "GIT_TERMINAL_PROMPT": "0"}

    def _git(self, *args, cwd=None, timeout=LS_REMOTE_TIMEOUT_S):
        command = ["git", "-c", "credential.helper=", *args]
        try:
            result = subprocess.run(command, cwd=cwd, env=self.env, capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            raise PluginSourceError(f"git {args[0]} of the plugin's repository {self.url} did not answer in "
                                    f"{timeout:g} seconds") from None
        if result.returncode != 0:
            raise PluginSourceError(f"git {args[0]} of the plugin's repository {self.url} failed: "
                                    f"{result.stderr.strip() or f'exit {result.returncode}'}")
        return result.stdout

    def _tags(self, pattern):
        lines = self._git("ls-remote", "--tags", "--refs", self.url, pattern).splitlines()
        return [line.split("\trefs/tags/", 1)[1] for line in lines if "\trefs/tags/" in line]

    def latest_release(self):
        """The newest release tag of the plugin's repository, the one a start from the app runs, or None when it has
        none (latest-release C1). The same tags `release_exists` accepts."""
        return newest_release(self._tags("v*"))

    def release_exists(self, tag):
        return tag in self._tags(f"refs/tags/{tag}")

    def fetch(self, tag, into):
        """A repository at `into` that holds the release tag and nothing else of the plugin's repository."""
        os.makedirs(into)
        self._git("init", "--quiet", "--bare", into)
        if not self.release_exists(tag):
            raise PluginSourceError(f"{tag} is not a tag of the plugin's repository {self.url}")
        self._git("fetch", "--quiet", "--depth", "1", self.url, f"refs/tags/{tag}:refs/tags/{tag}", cwd=into,
                  timeout=FETCH_TIMEOUT_S)
        return into
