"""Shared test fixtures: fakes for GitHub, the status service and Expo, a clock, status documents built from queue
items, and a test client that checks every request and response against openapi.yaml.

No test reaches a network: the fakes here stand in for every outside service, and test_clients.py runs the real
clients against fake servers on 127.0.0.1. Expo is never called, so nothing reaches a real device.
"""

import json
import os
import re
from datetime import datetime, timedelta, timezone

import yaml
from openapi_core import OpenAPI
from openapi_core.contrib.werkzeug import WerkzeugOpenAPIRequest, WerkzeugOpenAPIResponse
from werkzeug.test import EnvironBuilder
from werkzeug.wrappers import Request

from notify.app import create_app
from notify.config import Settings
from notify.errors import InvalidCredentials, Unavailable
from notify.expo import Ticket
from notify.notifier import Notifier
from notify.store import MemoryStore

HERE = os.path.dirname(os.path.abspath(__file__))
SERVICE = os.path.dirname(HERE)
ROOT = os.path.dirname(os.path.dirname(SERVICE))
SPEC_PATH = os.path.join(SERVICE, "openapi.yaml")
SPEC = OpenAPI.from_file_path(SPEC_PATH)

PROJECT = "jugonzal/architect-loop"
OTHER_PROJECT = "example/other"
COMMIT = "0123456789abcdef0123456789abcdef01234567"
NOTIFY_IDENTITY = "notify@notify-test.iam.gserviceaccount.com"
# Shaped like a JWT, so the service checks it as a tick's token and never sends it to GitHub.
TICK_TOKEN = "eyJhbGciOiJSUzI1NiJ9.eyJ0aWNrIjp0cnVlfQ.c2lnbmF0dXJl"
UNTRUSTED_JWT = "eyJhbGciOiJSUzI1NiJ9.eyJzb21lb25lIjoiZWxzZSJ9.c2lnbmF0dXJl"
# The loop the documents describe: alice owns it, bob and carol are members, and dave is neither (D69).
LOOP = {"id": "command-center", "state": "active", "owner": "alice", "members": ["bob", "carol"]}
# Monday 2026-10-26, 14:00 UTC: 10:00 in New York, 15:00 in Lisbon's winter time.
NOON = datetime(2026, 10, 26, 14, 0, tzinfo=timezone.utc)


def push_token(name):
    return f"ExponentPushToken[{name}]"


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


class FakeGitHub:
    """Stands in for GET /user. Records every token it is asked about."""

    def __init__(self):
        self.users = {}
        self.calls = []
        self.down = False

    def add(self, token, login):
        self.users[token] = login

    def user_login(self, token):
        self.calls.append(token)
        if self.down:
            raise Unavailable("GitHub is unreachable (test)")
        if token not in self.users:
            raise InvalidCredentials("GitHub does not accept this token")
        return self.users[token]


class FakeStatus:
    """Stands in for the status service: answers each project's current document, or fails."""

    def __init__(self):
        self.documents = {}
        self.down = False
        self.reads = []

    def document(self, project):
        self.reads.append(project)
        if self.down or project not in self.documents:
            raise Unavailable("the status service answered 503 (test)")
        return json.loads(json.dumps(self.documents[project]))


class FakeExpo:
    """Stands in for Expo's push service: records every message it is sent, and answers a ticket for each. A token
    in `gone` answers DeviceNotRegistered; while `down`, nothing is taken."""

    def __init__(self):
        self.sent = []
        self.gone = set()
        self.refused = set()
        self.down = False

    def send(self, messages):
        if self.down:
            raise Unavailable("Expo answered 503 (test)")
        tickets = []
        for message in messages:
            if message["to"] in self.gone:
                tickets.append(Ticket(ok=False, error="DeviceNotRegistered", message="gone (test)"))
            elif message["to"] in self.refused:
                tickets.append(Ticket(ok=False, error="MessageRateExceeded", message="slow down (test)"))
            else:
                self.sent.append(message)
                tickets.append(Ticket(ok=True))
        return tickets

    def to(self, token):
        """The messages Expo took for one push token."""
        return [m for m in self.sent if m["to"] == token]


class FakeIdentity:
    """Stands in for the Google OIDC token check of a tick: accepts only the tokens it was given."""

    def __init__(self, tokens):
        self.tokens = dict(tokens)
        self.calls = []

    def verify(self, token):
        self.calls.append(token)
        if token not in self.tokens:
            raise InvalidCredentials("not a service identity this deployment trusts to tick")
        return self.tokens[token]


class FakeClock:
    """An aware UTC time that tests move on."""

    def __init__(self, now=NOON):
        self.now = now

    def __call__(self):
        return self.now

    def advance(self, **delta):
        self.now += timedelta(**delta)


def item(ident, waits_on="alice", unblocks=(), loop="command-center", kind="question", title=None):
    """A queue item as the status schema shapes it, with only what the notifier reads filled in for real."""
    return {
        "id": ident,
        "kind": kind,
        "title": title or f"Answer {ident}",
        "why": "it is open",
        "loop": loop,
        "concerns": [],
        "unblocks": list(unblocks),
        "waits_on": waits_on,
        "visible_to": [],
        "gate": None,
        "detail": {},
    }


def document(*items, project=PROJECT, loops=None):
    """A status document whose queue holds these items; every other field is as small as the schema allows."""
    loops = loops if loops is not None else [LOOP]
    return {"schema_version": 1, "project": project, "as_of": "2026-10-26T14:00:00Z",
            "main": {}, "environments": [], "loops": loops, "queue": list(items), "agents_can_start": [],
            "drift": [], "missing": []}


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
        copy = Request(EnvironBuilder(path=path, method=method, headers=headers, **kwargs).get_environ())
        request = WerkzeugOpenAPIRequest(copy)
        op = operation_for(method, copy.path)
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


class Harness:
    """A service wired to fakes on one MemoryStore, with alice, bob, carol and dave signed in to GitHub; the status
    documents name the first three as the loop's owner and members (D69), and dave as neither. The notifier is
    the one the API uses; tests call its tick() as POST /tick does."""

    def make(self, store=None):
        self.github = FakeGitHub()
        for login in ("alice", "bob", "carol", "dave"):
            self.github.add(f"{login}-token", login)
        self.status = FakeStatus()
        for project in (PROJECT, OTHER_PROJECT):
            self.status.documents[project] = document(project=project)
        self.identity = FakeIdentity({TICK_TOKEN: NOTIFY_IDENTITY})
        self.expo = FakeExpo()
        self.clock = FakeClock()
        self.store = store if store is not None else MemoryStore()
        self.settings = Settings(projects=frozenset({PROJECT, OTHER_PROJECT}), commit=COMMIT, store="memory",
                                 status_url="https://status.example", audience="https://notify.example",
                                 tick_service_accounts=(NOTIFY_IDENTITY,))
        self.notifier = Notifier(self.settings.projects, self.store, self.status, self.expo, clock=self.clock)
        self.app = create_app(self.settings, store=self.store, github=self.github, notifier=self.notifier,
                              identity=self.identity, clock=lambda: 0.0, now=self.clock)
        self.api = ContractClient(self.app, self)

    def register(self, login, device, project=PROJECT, **fields):
        """Register the device named `device`, whose push token is push_token(device), for the login."""
        body = {"token": push_token(device), "platform": "ios", "name": f"{login}'s {device}", **fields}
        response = self.api.post(f"{base(project)}/devices", token=f"{login}-token", json_body=body)
        self.assertEqual(response.status_code, 200, response.get_json())
        return response.get_json()

    def save_settings(self, login, timezone="UTC", digest_time="09:00", quiet_hours=None, project=PROJECT):
        body = {"timezone": timezone, "digest_time": digest_time, "quiet_hours": quiet_hours}
        response = self.api.put(f"{base(project)}/settings/me", token=f"{login}-token", json_body=body)
        self.assertEqual(response.status_code, 200, response.get_json())
        return response.get_json()

    def queue(self, *items, project=PROJECT, loops=None):
        self.status.documents[project] = document(*items, project=project, loops=loops)

    def first_read(self, *items):
        """The read that records the project's baseline, so the tests after it see what is new."""
        self.queue(*items)
        [read] = [r for r in self.notifier.tick() if r.project == PROJECT]
        self.assertTrue(read.baseline)
        return read

    def tick(self):
        return {r.project: r for r in self.notifier.tick()}[PROJECT]
