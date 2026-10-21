"""Shared test fixtures: a throwaway database schema, a fake GitHub, a fake service identity, and a test client that
checks every request and response against openapi.yaml.

The API tests need Postgres. Point THREADS_TEST_DATABASE_URL at a throwaway database (CI starts one as a service
container). Each test class creates its own schema in it, applies the migrations there, and drops it afterwards, so
the tests never touch other tables in that database. Without the variable the database tests are skipped, unless
THREADS_REQUIRE_DB=1, which turns the skip into a failure (CI sets it, so a missing database cannot pass as green).
"""

import hashlib
import hmac
import json
import os
import re
import secrets
import unittest

import psycopg
import yaml
from psycopg.conninfo import make_conninfo
from openapi_core import OpenAPI
from openapi_core.contrib.werkzeug import WerkzeugOpenAPIRequest, WerkzeugOpenAPIResponse

from threads import migrate
from threads.app import create_app
from threads.config import Settings
from threads.errors import InvalidCredentials, Unavailable
from threads.store import Store

HERE = os.path.dirname(os.path.abspath(__file__))
SERVICE = os.path.dirname(HERE)
SPEC_PATH = os.path.join(SERVICE, "openapi.yaml")
SPEC = OpenAPI.from_file_path(SPEC_PATH)

PROJECT = "jugonzal/architect-loop"
OTHER_PROJECT = "example/other"
WEBHOOK_SECRET = b"made-up-test-secret"
RUNNER_EMAIL = "runner@threads-test.iam.gserviceaccount.com"
# Shaped like a JWT, so the service checks it as a service identity and never sends it to GitHub.
RUNNER_TOKEN = "eyJhbGciOiJSUzI1NiJ9.eyJydW5uZXIiOnRydWV9.c2lnbmF0dXJl"
UNTRUSTED_JWT = "eyJhbGciOiJSUzI1NiJ9.eyJzb21lb25lIjoiZWxzZSJ9.c2lnbmF0dXJl"

DB_URL = os.environ.get("THREADS_TEST_DATABASE_URL")
REQUIRE_DB = os.environ.get("THREADS_REQUIRE_DB") == "1"


def spec_operations():
    """Every (METHOD, path template) that openapi.yaml documents."""
    with open(SPEC_PATH) as f:
        paths = yaml.safe_load(f)["paths"]
    ops = set()
    for path, item in paths.items():
        for method in ("get", "put", "post", "delete", "patch"):
            if method in item:
                ops.add((method.upper(), path))
    return ops


def _template_regex(template):
    return re.compile("^" + re.sub(r"\{[^}]+\}", "[^/]+", template) + "$")


_TEMPLATES = sorted(((m, p, _template_regex(p)) for m, p in spec_operations()), key=lambda t: -len(t[1]))
EXERCISED = set()


def operation_for(method, path):
    for m, template, regex in _TEMPLATES:
        if m == method and regex.match(path):
            return (m, template)
    return None


class Database:
    """A schema of its own in the throwaway test database, with the migrations applied."""

    def __init__(self):
        if not DB_URL:
            if REQUIRE_DB:
                raise RuntimeError("THREADS_REQUIRE_DB=1 but THREADS_TEST_DATABASE_URL is not set")
            raise unittest.SkipTest("set THREADS_TEST_DATABASE_URL to a throwaway Postgres to run the database tests")
        self.schema = "threads_test_" + secrets.token_hex(6)
        with psycopg.connect(DB_URL, autocommit=True) as conn:
            conn.execute(f'CREATE SCHEMA "{self.schema}"')
        self.conninfo = make_conninfo(DB_URL, options=f"-c search_path={self.schema}")

    def migrate(self):
        return migrate.apply(self.conninfo)

    def truncate(self):
        with psycopg.connect(self.conninfo, autocommit=True) as conn:
            conn.execute("TRUNCATE record_marks, watchers, messages, threads RESTART IDENTITY CASCADE")

    def rows(self, sql, *params):
        with psycopg.connect(self.conninfo, autocommit=True) as conn:
            return conn.execute(sql, params).fetchall()

    def drop(self):
        with psycopg.connect(DB_URL, autocommit=True) as conn:
            conn.execute(f'DROP SCHEMA "{self.schema}" CASCADE')


class FakeGitHub:
    """Stands in for threads' read-only GitHub App and for GET /user. Records every call it gets."""

    def __init__(self):
        self.users = {}
        self.members = {}
        self.calls = []
        self.down = False

    def add(self, token, login, *projects):
        self.users[token] = login
        for project in projects:
            self.members.setdefault(project, set()).add(login)

    def user_login(self, token):
        self.calls.append(("user_login", token))
        if self.down:
            raise Unavailable("GitHub is unreachable (test)")
        if token not in self.users:
            raise InvalidCredentials("GitHub does not accept this token")
        return self.users[token]

    def is_collaborator(self, project, login):
        self.calls.append(("is_collaborator", project, login))
        if self.down:
            raise Unavailable("GitHub is unreachable (test)")
        return login in self.members.get(project, set())

    def collaborators(self, project):
        self.calls.append(("collaborators", project))
        if self.down:
            raise Unavailable("GitHub is unreachable (test)")
        return sorted(self.members.get(project, set()))


class FakeIdentity:
    """Stands in for the Google ID token check of the runner's Cloud Run service identity."""

    def __init__(self, tokens):
        self.tokens = dict(tokens)
        self.calls = []

    def verify(self, token):
        self.calls.append(token)
        if token not in self.tokens:
            raise InvalidCredentials("not a service identity this deployment trusts")
        return self.tokens[token]


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


class ContractClient:
    """A Flask test client whose every response, and every request not marked invalid, must match openapi.yaml."""

    def __init__(self, app, test):
        self.client = app.test_client()
        self.test = test

    def call(self, method, path, token=None, json_body=None, valid_request=True, headers=None, **kwargs):
        headers = dict(headers or {})
        if token is not None:
            headers["Authorization"] = f"Bearer {token}"
        if json_body is not None:
            kwargs["data"] = json.dumps(json_body)
            kwargs["content_type"] = "application/json"
        response = self.client.open(path, method=method, headers=headers, **kwargs)
        request = WerkzeugOpenAPIRequest(response.request)
        op = operation_for(method, response.request.path)
        self.test.assertIsNotNone(op, f"{method} {path} is not in openapi.yaml")
        EXERCISED.add(op)
        if valid_request:
            SPEC.validate_request(request)
        SPEC.validate_response(request, WerkzeugOpenAPIResponse(response))
        return response

    def get(self, path, **kw):
        return self.call("GET", path, **kw)

    def post(self, path, **kw):
        return self.call("POST", path, **kw)

    def put(self, path, **kw):
        return self.call("PUT", path, **kw)

    def delete(self, path, **kw):
        return self.call("DELETE", path, **kw)


def base(project=PROJECT):
    return f"/projects/{project}"


def concern_thread(loop="command-center", concern="threads", project=PROJECT):
    return f"{base(project)}/loops/{loop}/concerns/{concern}/thread"


def loop_thread(loop="command-center", project=PROJECT):
    return f"{base(project)}/loops/{loop}/thread"


def session_thread(session="s-1", project=PROJECT):
    return f"{base(project)}/sessions/{session}/thread"


def sign(raw, secret=WEBHOOK_SECRET):
    return "sha256=" + hmac.new(secret, raw, hashlib.sha256).hexdigest()


def pull_request(number=17, body="Builds it.\n\nConcern: command-center/threads\n", repo=PROJECT):
    return {
        "number": number,
        "body": body,
        "html_url": f"https://github.com/{repo}/pull/{number}",
        "head": {"ref": "command-center/threads"},
    }


def review_comment_event(comment_id=101, body="Is this cached?", login="dave", association="NONE",
                         pr=None, repo=PROJECT, action="created", path="services/threads/threads/app.py"):
    pr = pr or pull_request(repo=repo)
    return {
        "action": action,
        "comment": {
            "id": comment_id,
            "body": body,
            "path": path,
            "html_url": f"https://github.com/{repo}/pull/{pr['number']}#discussion_r{comment_id}",
            "user": {"login": login},
            "author_association": association,
        },
        "pull_request": pr,
        "repository": {"full_name": repo},
    }


def review_event(review_id=201, body="Looks right to me.", state="approved", login="erin",
                 association="COLLABORATOR", pr=None, repo=PROJECT, action="submitted"):
    pr = pr or pull_request(repo=repo)
    return {
        "action": action,
        "review": {
            "id": review_id,
            "body": body,
            "state": state,
            "html_url": f"https://github.com/{repo}/pull/{pr['number']}#pullrequestreview-{review_id}",
            "user": {"login": login},
            "author_association": association,
        },
        "pull_request": pr,
        "repository": {"full_name": repo},
    }


class ApiTestCase(unittest.TestCase):
    """A fresh store per test, an app wired to fakes, and members alice and bob; carol is not a member."""

    cache_seconds = 0

    @classmethod
    def setUpClass(cls):
        cls.db = Database()
        try:
            cls.db.migrate()
            cls.store = Store(cls.db.conninfo)
        except Exception:
            cls.db.drop()
            raise

    @classmethod
    def tearDownClass(cls):
        cls.store.close()
        cls.db.drop()

    def setUp(self):
        self.db.truncate()
        self.github = FakeGitHub()
        self.github.add("alice-token", "alice", PROJECT, OTHER_PROJECT)
        self.github.add("bob-token", "bob", PROJECT)
        self.github.add("carol-token", "carol")
        self.identity = FakeIdentity({RUNNER_TOKEN: RUNNER_EMAIL})
        self.clock = FakeClock()
        self.settings = Settings(
            projects=frozenset({PROJECT, OTHER_PROJECT}),
            commit="0123456789abcdef0123456789abcdef01234567",
            webhook_secret=WEBHOOK_SECRET,
            cache_seconds=self.cache_seconds,
        )
        self.app = create_app(self.settings, store=self.store, github=self.github, identity=self.identity,
                              clock=self.clock)
        self.api = ContractClient(self.app, self)

    def post_message(self, thread, body="hello", token="alice-token", **fields):
        response = self.api.post(f"{thread}/messages", token=token, json_body={"body": body, **fields})
        self.assertEqual(response.status_code, 201, response.get_json())
        return response.get_json()

    def runner_post(self, body, kind="milestone", session="s-1", sponsor="alice"):
        return self.post_message(session_thread(session), body=body, token=RUNNER_TOKEN, kind=kind, sponsor=sponsor)

    def messages(self, thread, token="alice-token", query=""):
        response = self.api.get(f"{thread}/messages{query}", token=token)
        self.assertEqual(response.status_code, 200, response.get_json())
        return response.get_json()

    def deliver(self, event, payload, secret=WEBHOOK_SECRET, signature=None, valid_request=True):
        raw = json.dumps(payload).encode()
        headers = {"X-GitHub-Event": event, "X-GitHub-Delivery": secrets.token_hex(8),
                   "X-Hub-Signature-256": signature or sign(raw, secret)}
        return self.api.post("/webhooks/github", data=raw, content_type="application/json", headers=headers,
                             valid_request=valid_request)

    def store_snapshot(self):
        """Everything in the store except the record marks, to show what marking leaves alone."""
        return {
            "threads": self.db.rows("SELECT id, project, scope, name, sponsor, last_seq, created_at FROM threads ORDER BY id"),
            "messages": self.db.rows("SELECT * FROM messages ORDER BY id"),
            "watchers": self.db.rows("SELECT * FROM watchers ORDER BY thread_id, login"),
        }
