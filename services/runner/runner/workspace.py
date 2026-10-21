"""A session's workspace: a fresh clone of the project on `<loop>/<concern>`, with the runner's commit-msg hook,
and the plugin release named in the dispatch beside it, read-only (session-runner Approach, D4; D17)."""

import io
import json
import os
import shlex
import shutil
import stat
import subprocess
import tarfile
from dataclasses import dataclass

HOOK = """#!/bin/sh
# Installed by the architect-loop runner in this session's clone (session-runner D4): every commit names its
# concern and its sponsor. `git commit --no-verify` skips this hook; the trailers check fails such a commit.
exec git interpret-trailers --in-place --if-exists doNothing {trailers} "$1"
"""


class WorkspaceError(Exception):
    pass


@dataclass
class Prepared:
    root: str
    clone: str
    plugin_dir: str
    plugin_name: str


def trailers_for(session):
    """The trailers a session's commits and pull requests carry (C1)."""
    return [("Concern", session.concern), ("Sponsored-by", session.sponsor)]


class Workspace:
    def __init__(self, git_url, workdir, identity, main_branch="main", credential_helper=None, env=None):
        self.git_url, self.workdir, self.identity = git_url, workdir, identity
        self.main_branch, self.credential_helper = main_branch, credential_helper
        self.env = env

    def _git(self, cwd, *args, binary=False):
        result = subprocess.run(["git", *args], cwd=cwd, env=self.env, capture_output=True, text=not binary)
        if result.returncode != 0:
            error = result.stderr if not binary else result.stderr.decode(errors="replace")
            raise WorkspaceError(f"git {' '.join(args)}: {error.strip()}")
        return result.stdout

    def prepare(self, session):
        root = os.path.join(self.workdir, session.id)
        if os.path.exists(root):
            raise WorkspaceError(f"{root} already exists: a session never reuses a clone")
        os.makedirs(root)
        clone = os.path.join(root, "clone")
        self._git(root, "clone", "--quiet", "--no-hardlinks", self.git_url, clone)
        self._branch(clone, session.branch)
        name, email = self.identity
        self._git(clone, "config", "user.name", name)
        self._git(clone, "config", "user.email", email)
        if self.credential_helper:
            self._git(clone, "config", "--add", "credential.helper", "")
            self._git(clone, "config", "--add", "credential.helper", self.credential_helper)
        self._install_hook(clone, session)
        plugin_dir = self._install_release(clone, root, session.plugin_release)
        with open(os.path.join(plugin_dir, ".claude-plugin", "plugin.json")) as f:
            plugin_name = json.load(f)["name"]
        return Prepared(root, clone, plugin_dir, plugin_name)

    def _branch(self, clone, branch):
        remote = f"refs/remotes/origin/{branch}"
        exists = subprocess.run(["git", "rev-parse", "--verify", "--quiet", remote], cwd=clone, env=self.env,
                                capture_output=True).returncode == 0
        if exists:
            self._git(clone, "switch", "--quiet", "--track", f"origin/{branch}")
        else:
            self._git(clone, "switch", "--quiet", "--no-track", "-c", branch, f"origin/{self.main_branch}")

    def _install_hook(self, clone, session):
        hooks = os.path.join(clone, ".git", "hooks")
        os.makedirs(hooks, exist_ok=True)
        arguments = " ".join(f"--trailer {shlex.quote(f'{key}: {value}')}" for key, value in trailers_for(session))
        path = os.path.join(hooks, "commit-msg")
        with open(path, "w") as f:
            f.write(HOOK.format(trailers=arguments))
        os.chmod(path, 0o755)
        # The clone's own config names its hooks, so a user-level core.hooksPath cannot send them elsewhere.
        self._git(clone, "config", "core.hooksPath", hooks)

    def _install_release(self, clone, root, tag):
        """The plugin as it is at the release tag, extracted outside the clone and made read-only (D17)."""
        verified = subprocess.run(["git", "rev-parse", "--verify", "--quiet", f"refs/tags/{tag}"], cwd=clone,
                                  env=self.env, capture_output=True)
        if verified.returncode != 0:
            raise WorkspaceError(f"{tag} is not a tag of {self.git_url}")
        archive = self._git(clone, "archive", "--format=tar", f"refs/tags/{tag}", "plugin", binary=True)
        target = os.path.join(root, "release", tag)
        os.makedirs(target)
        with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
            tar.extractall(target, filter="data")
        plugin_dir = os.path.join(target, "plugin")
        if not os.path.isfile(os.path.join(plugin_dir, ".claude-plugin", "plugin.json")):
            raise WorkspaceError(f"{tag} has no plugin/.claude-plugin/plugin.json")
        for dirpath, dirnames, filenames in os.walk(plugin_dir, topdown=False):
            for name in filenames:
                os.chmod(os.path.join(dirpath, name), 0o444)
            os.chmod(dirpath, 0o555)
        return plugin_dir

    def pushed_branches(self, clone):
        """Branches this clone pushed: their remote-tracking refs were updated by a push, not by a fetch."""
        refs = self._git(clone, "for-each-ref", "--format=%(refname)", "refs/remotes/origin").split()
        pushed = []
        for ref in refs:
            if ref == "refs/remotes/origin/HEAD":
                continue
            log = subprocess.run(["git", "reflog", "show", "--format=%gs", ref, "--"], cwd=clone, env=self.env,
                                 capture_output=True, text=True).stdout
            if any(line.startswith("update by push") for line in log.splitlines()):
                pushed.append(ref.removeprefix("refs/remotes/origin/"))
        return pushed

    def cleanup(self, session_id):
        root = os.path.join(self.workdir, session_id)
        if not os.path.exists(root):
            return
        for dirpath, dirnames, filenames in os.walk(root):
            os.chmod(dirpath, os.stat(dirpath).st_mode | stat.S_IWUSR)
        shutil.rmtree(root, ignore_errors=True)
