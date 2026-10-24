"""Fakes for everything outside the runner: GitHub, Cloud Run and the clock. No test reaches a network."""

import datetime
import itertools
import os
import shutil
import tempfile

from runner.config import Config
from runner.dispatch import Dispatcher
from runner.github import GitHubError, newest_release
from runner.store import SqliteStore

PROJECT = "jugonzal/architect-loop"
CONCERN = "command-center/session-runner"
OTHER = "command-center/threads"
LOOP = "command-center"
ENVIRONMENT = "staging/runner"

# What a session of each scope runs on, and the branch its clone starts on (runner-dispatch C3).
SCOPED = {
    "concern": {"concern": CONCERN, "branch": CONCERN},
    "loop": {"loop": LOOP, "branch": "main"},
    "environment": {"environment": ENVIRONMENT, "branch": "main"},
}

TOKENS = {"tok-juan": "juan", "tok-ana": "ana", "tok-out": "outsider"}


class FakeGitHub:
    """GitHub as the runner sees it, through its own app (for the project) and through a caller's token (/user)."""

    def __init__(self):
        self.tokens = dict(TOKENS)
        self.collaborators = {"juan", "ana"}
        self.concerns = {CONCERN, OTHER, "command-center/app-agents", "command-center/notifications",
                         "command-center/environments"}
        self.releases = {"v0.3.0"}
        self.loops = {LOOP}
        self.environment_names = ["main", "staging/runner", "production/runner"]
        self.pulls = []
        self.calls = []
        self.down = False
        self.bodies = {}

    def _call(self, name, *args):
        self.calls.append((name, *args))
        if self.down:
            raise GitHubError(f"{name}: GitHub answered 503")

    def login(self, token):
        self._call("login", token)
        return self.tokens.get(token)

    def is_collaborator(self, login):
        self._call("is_collaborator", login)
        return login in self.collaborators

    def concern_exists(self, loop, concern):
        self._call("concern_exists", loop, concern)
        return f"{loop}/{concern}" in self.concerns

    def release_exists(self, tag):
        self._call("release_exists", tag)
        return tag in self.releases

    def latest_release(self):
        self._call("latest_release")
        return newest_release(self.releases)

    def loop_exists(self, loop):
        self._call("loop_exists", loop)
        return loop in self.loops

    def environments(self):
        self._call("environments")
        return list(self.environment_names)

    def open_pull_requests(self):
        self._call("open_pull_requests")
        return [dict(p) for p in self.pulls]

    def pull_requests_for_heads(self, heads):
        self._call("pull_requests_for_heads", tuple(heads))
        return [dict(p, body=self.bodies.get(p["number"], p.get("body", ""))) for p in self.pulls
                if p["head"] in heads]

    def set_pull_request_body(self, number, body):
        self._call("set_pull_request_body", number)
        self.bodies[number] = body

    def installation_token(self, permissions):
        self._call("installation_token", tuple(sorted(permissions.items())))
        return "ghs_fake_installation_token"

    def bot_user_id(self):
        self._call("bot_user_id")
        return 1234

    def open_pr(self, number, head, body=""):
        self.pulls.append({"number": number, "url": f"https://github.com/{PROJECT}/pull/{number}", "head": head,
                           "body": body})


class FakeLauncher:
    def __init__(self):
        self.launched = []
        self.fail = False

    def launch(self, session):
        if self.fail:
            raise RuntimeError("Cloud Run answered 503")
        self.launched.append(session.id)
        return f"projects/p/locations/us-east1/jobs/runner-session/executions/{session.id[:8]}"


class Clock:
    """A clock the tests move by hand."""

    def __init__(self, start=datetime.datetime(2026, 10, 20, 12, 0, 0, tzinfo=datetime.timezone.utc)):
        self.now = start

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += datetime.timedelta(seconds=seconds)


def ids():
    counter = itertools.count(1)
    return lambda: f"{next(counter):032x}"


def scratch(testcase):
    path = tempfile.mkdtemp(prefix="runner-test-")
    testcase.addCleanup(shutil.rmtree, path, True)
    return path


def make_runner(testcase, **config):
    """A dispatcher over a fresh store, with fake GitHub, Cloud Run and clock."""
    path = scratch(testcase)
    cfg = Config(**{"store_path": os.path.join(path, "runner.sqlite3"), "commit": "eee8119", **config})
    store = SqliteStore(cfg.store_path, seeds=cfg.seeds)
    github, launcher, clock = FakeGitHub(), FakeLauncher(), Clock()
    dispatcher = Dispatcher(cfg, store, github, launcher, now=clock, new_id=ids())
    return dispatcher, store, github, launcher, clock


def dispatch_body(concern=CONCERN, skill="loop-build", **extra):
    """A dispatch on a concern, or on whatever `extra` names instead when `concern` is None; a None is left out."""
    body = {"project": PROJECT, "skill": skill, "concern": concern, "arguments": "", "budget_usd": 2.0,
            "plugin_release": "v0.3.0", **extra}
    return {k: v for k, v in body.items() if v is not None}


def scoped_body(scope, skill, **extra):
    """A dispatch of `skill` on the test concern, loop or environment."""
    target = {k: v for k, v in SCOPED[scope].items() if k != "branch"}
    return dispatch_body(**{"concern": None, **target}, skill=skill, **extra)
