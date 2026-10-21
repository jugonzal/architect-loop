"""The threads API (../openapi.yaml): one thread per loop, concern and session, for the project's members.

Run it with `gunicorn 'threads.app:create_app()'`; configuration is in config.py.
"""

import hashlib
import json
import logging
import threading
import time
from dataclasses import dataclass
from datetime import timezone

from flask import Flask, jsonify, request

from . import webhooks
from .config import Settings
from .errors import InvalidCredentials, Unavailable
from .names import valid
from .store import SponsorConflict

KINDS = ("message", "milestone", "narration")
MAX_BODY = 65536
MAX_ID = 2**63 - 1

THREAD_RULES = {
    "loop": "/projects/<owner>/<repo>/loops/<loop>/thread",
    "concern": "/projects/<owner>/<repo>/loops/<loop>/concerns/<concern>/thread",
    "session": "/projects/<owner>/<repo>/sessions/<session>/thread",
}


class ApiError(Exception):
    def __init__(self, status, error, message):
        super().__init__(message)
        self.status, self.error, self.message = status, error, message


def bad_request(message):
    return ApiError(400, "bad_request", message)


def forbidden(message):
    return ApiError(403, "forbidden", message)


@dataclass(frozen=True)
class Person:
    login: str


@dataclass(frozen=True)
class Runner:
    service_account: str


class Access:
    """Who is calling and who the members are, with GitHub's answers reused for `ttl` seconds."""

    def __init__(self, github, identity, ttl, clock):
        self.github, self.identity, self.ttl, self.clock = github, identity, ttl, clock
        self._cache = {}
        self._lock = threading.Lock()

    def caller(self, header):
        scheme, _, token = (header or "").partition(" ")
        token = token.strip()
        if scheme.lower() != "bearer" or not token:
            raise InvalidCredentials("send Authorization: Bearer <token>")
        if token.count(".") == 2:
            # A JWT: the runner's Google-signed ID token. It is never sent to GitHub.
            return Runner(self.identity.verify(token))
        key = ("user", hashlib.sha256(token.encode()).hexdigest())  # the cache keeps no token
        return Person(self._cached(key, lambda: self.github.user_login(token)))

    def is_member(self, project, login):
        return self._cached(("member", project, login), lambda: self.github.is_collaborator(project, login))

    def members(self, project):
        return self._cached(("members", project), lambda: sorted(self.github.collaborators(project), key=str.lower))

    def _cached(self, key, fetch):
        now = self.clock()
        with self._lock:
            hit = self._cache.get(key)
            if hit and now < hit[1]:
                return hit[0]
        value = fetch()
        if self.ttl > 0:
            with self._lock:
                self._cache[key] = (value, now + self.ttl)
                if len(self._cache) > 10_000:
                    self._cache = {k: v for k, v in self._cache.items() if now < v[1]}
        return value


def timestamp(value):
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def thread_url(project, scope, name):
    if scope == "loop":
        return f"/projects/{project}/loops/{name}/thread"
    if scope == "concern":
        loop, concern = name.split("/", 1)
        return f"/projects/{project}/loops/{loop}/concerns/{concern}/thread"
    return f"/projects/{project}/sessions/{name}/thread"


def message_json(project, row):
    if row["author_type"] == "person":
        author = {"type": "person", "login": row["author"]}
    elif row["author_type"] == "session":
        author = {"type": "session", "session": row["author"], "sponsor": row["author_label"]}
    else:
        author = {"type": "github", "login": row["author"], "association": row["author_label"]}
    source = None
    if row["source_type"]:
        source = {"type": row["source_type"], "url": row["source_url"], "pull_request": row["source_pr"],
                  "path": row["source_path"], "review_state": row["source_state"]}
    return {
        "id": row["id"],
        "seq": row["seq"],
        "thread": thread_url(project, row["thread_scope"], row["thread_name"]),
        "kind": row["kind"],
        "author": author,
        "body": row["body"],
        "created_at": timestamp(row["created_at"]),
        "record_marks": [{"login": m["login"], "marked_at": timestamp(m["marked_at"])} for m in row["record_marks"]],
        "source": source,
    }


def create_app(settings=None, *, store=None, github=None, identity=None, clock=time.monotonic):
    """The WSGI app. Tests pass fakes; on Cloud Run everything comes from the environment."""
    if settings is None:
        settings = Settings.from_env()
    problems = [] if store is not None else settings.problems()
    if store is None and not problems:
        from .store import Store
        store = Store(settings.database_url)
    if github is None:
        from .github import GitHubApp
        github = GitHubApp(settings.github_app_id, settings.github_private_key, api_url=settings.github_api_url)
    if identity is None:
        from .identity import GoogleIdentity
        identity = GoogleIdentity(settings.audience, settings.runner_service_accounts)

    app = Flask(__name__)
    app.json.sort_keys = False
    app.logger.setLevel(logging.INFO)
    access = Access(github, identity, settings.cache_seconds, clock)

    if problems:
        # Started without its configuration (a first deploy sets only COMMIT_SHA): answer /version, refuse the rest.
        app.logger.error("not configured: %s", "; ".join(problems))

        @app.before_request
        def not_configured():
            if request.path != "/version":
                return jsonify(error="unavailable", message="not configured: " + "; ".join(problems)), 503

    @app.errorhandler(ApiError)
    def api_error(error):
        return jsonify(error=error.error, message=error.message), error.status

    @app.errorhandler(InvalidCredentials)
    def invalid_credentials(error):
        return jsonify(error="unauthorized", message=str(error)), 401

    @app.errorhandler(Unavailable)
    def unavailable(error):
        app.logger.warning("unavailable: %s", error)
        return jsonify(error="unavailable", message=str(error)), 503

    @app.errorhandler(404)
    def not_found(error):
        return jsonify(error="not_found", message="no such path"), 404

    @app.errorhandler(405)
    def not_allowed(error):
        return jsonify(error="bad_request", message="method not allowed here"), 405

    @app.errorhandler(500)
    def internal(error):
        return jsonify(error="internal", message="the service failed; see its logs"), 500

    # Checks shared by every operation.

    def project_of(owner, repo):
        if not valid("login", owner) or not valid("repo", repo):
            raise bad_request("the project is not owner/repo")
        project = f"{owner}/{repo}"
        if project not in settings.projects:
            raise ApiError(404, "not_found", f"{project} is not served here")
        return project

    def thread_of(scope, kw):
        if scope == "session":
            if not valid("session", kw["session"]):
                raise bad_request("not a session id")
            return kw["session"]
        names = [kw["loop"]] + ([kw["concern"]] if scope == "concern" else [])
        if not all(valid("name", n) for n in names):
            raise bad_request("not a loop or concern name")
        return "/".join(names)

    def admit(project, runner_may=False):
        """The caller, if they may do this in the project; otherwise raise."""
        caller = access.caller(request.headers.get("Authorization"))
        if isinstance(caller, Runner):
            if not runner_may:
                raise forbidden("the runner may only read and post to session threads")
            return caller
        if not access.is_member(project, caller.login):
            raise forbidden(f"{caller.login} is not a member of {project}")
        return caller

    def thread_json(project, scope, name):
        view = store.thread(project, scope, name)
        loop = name.split("/", 1)[0] if scope in ("loop", "concern") else None
        return {
            "project": project,
            "scope": scope,
            "url": thread_url(project, scope, name),
            "loop": loop,
            "concern": name.split("/", 1)[1] if scope == "concern" else None,
            "session": name if scope == "session" else None,
            "sponsor": view["sponsor"],
            "members": [{"login": login} for login in access.members(project)],
            "watchers": [{"login": w["login"], "since": timestamp(w["since"])} for w in view["watchers"]],
            "last_seq": view["last_seq"],
        }

    def json_body():
        try:
            body = json.loads(request.get_data(as_text=True) or "null")
        except ValueError:
            raise bad_request("the body is not JSON") from None
        if not isinstance(body, dict):
            raise bad_request("the body must be a JSON object")
        return body

    def int_arg(name, default, low, high):
        raw = request.args.get(name)
        if raw is None:
            return default
        try:
            value = int(raw)
        except ValueError:
            raise bad_request(f"{name} must be an integer") from None
        if not low <= value <= high:
            raise bad_request(f"{name} must be between {low} and {high}")
        return value

    # Threads.

    def make_thread_views(scope, rule):
        def get_thread(owner, repo, **kw):
            project = project_of(owner, repo)
            name = thread_of(scope, kw)
            admit(project, runner_may=scope == "session")
            return jsonify(thread_json(project, scope, name))

        def list_messages(owner, repo, **kw):
            project = project_of(owner, repo)
            name = thread_of(scope, kw)
            admit(project, runner_may=scope == "session")
            after = int_arg("after", 0, 0, MAX_ID)
            limit = int_arg("limit", 100, 1, 500)
            kinds = request.args.getlist("kind")
            if any(kind not in KINDS for kind in kinds):
                raise bad_request(f"kind must be one of {', '.join(KINDS)}")
            rows, more = store.messages(project, scope, name, after=after, limit=limit, kinds=kinds or None)
            return jsonify(messages=[message_json(project, r) for r in rows],
                           next_after=rows[-1]["seq"] if more else None)

        def post_message(owner, repo, **kw):
            project = project_of(owner, repo)
            name = thread_of(scope, kw)
            caller = admit(project, runner_may=scope == "session")
            fields = json_body()
            unknown = set(fields) - {"body", "kind", "sponsor"}
            if unknown:
                raise bad_request(f"unknown fields: {', '.join(sorted(unknown))}")
            body, kind = fields.get("body"), fields.get("kind", "message")
            if not isinstance(body, str) or not 1 <= len(body) <= MAX_BODY:
                raise bad_request(f"body must be a string of 1 to {MAX_BODY} characters")
            if kind not in KINDS:
                raise bad_request(f"kind must be one of {', '.join(KINDS)}")
            if isinstance(caller, Runner):
                sponsor = fields.get("sponsor")
                if not valid("login", sponsor):
                    raise bad_request("the runner must name the session's sponsor as a GitHub login")
                try:
                    row = store.post(project, scope, name, kind=kind, author_type="session", author=name,
                                     author_label=sponsor, body=body)
                except SponsorConflict as conflict:
                    raise ApiError(409, "conflict", str(conflict)) from None
            else:
                if "sponsor" in fields:
                    raise bad_request("only the runner names a sponsor")
                if kind != "message":
                    raise forbidden("only a session posts milestones and narration")
                row = store.post(project, scope, name, kind=kind, author_type="person", author=caller.login, body=body)
            return jsonify(message_json(project, row)), 201

        def watch(owner, repo, **kw):
            project = project_of(owner, repo)
            name = thread_of(scope, kw)
            caller = admit(project)
            store.watch(project, scope, name, caller.login)
            return jsonify(thread_json(project, scope, name))

        def unwatch(owner, repo, **kw):
            project = project_of(owner, repo)
            name = thread_of(scope, kw)
            caller = admit(project)
            store.unwatch(project, scope, name, caller.login)
            return jsonify(thread_json(project, scope, name))

        app.add_url_rule(rule, f"get_{scope}_thread", get_thread, methods=["GET"])
        app.add_url_rule(f"{rule}/messages", f"list_{scope}_messages", list_messages, methods=["GET"])
        app.add_url_rule(f"{rule}/messages", f"post_{scope}_message", post_message, methods=["POST"])
        app.add_url_rule(f"{rule}/watchers/me", f"watch_{scope}_thread", watch, methods=["PUT"])
        app.add_url_rule(f"{rule}/watchers/me", f"unwatch_{scope}_thread", unwatch, methods=["DELETE"])

    for scope, rule in THREAD_RULES.items():
        make_thread_views(scope, rule)

    # Messages and "record this?" marks.

    def message_id(raw):
        if not raw.isdigit() or not 1 <= int(raw) <= MAX_ID:
            raise bad_request("a message id is a positive integer")
        return int(raw)

    def found(project, ident):
        row = store.message(project, ident)
        if row is None:
            raise ApiError(404, "not_found", f"{project} has no message {ident}")
        return jsonify(message_json(project, row))

    @app.get("/projects/<owner>/<repo>/messages/<message>")
    def get_message(owner, repo, message):
        project = project_of(owner, repo)
        ident = message_id(message)
        admit(project)
        return found(project, ident)

    @app.put("/projects/<owner>/<repo>/messages/<message>/record-marks/me")
    def mark_message(owner, repo, message):
        project = project_of(owner, repo)
        ident = message_id(message)
        caller = admit(project)
        if not store.mark(project, ident, caller.login):
            raise ApiError(404, "not_found", f"{project} has no message {ident}")
        return found(project, ident)

    @app.delete("/projects/<owner>/<repo>/messages/<message>/record-marks/me")
    def unmark_message(owner, repo, message):
        project = project_of(owner, repo)
        ident = message_id(message)
        caller = admit(project)
        if not store.unmark(project, ident, caller.login):
            raise ApiError(404, "not_found", f"{project} has no message {ident}")
        return found(project, ident)

    # GitHub's deliveries.

    @app.post("/webhooks/github")
    def github_webhook():
        raw = request.get_data()
        if not webhooks.signature_ok(settings.webhook_secret, raw, request.headers.get("X-Hub-Signature-256")):
            raise InvalidCredentials("the delivery's signature does not match threads' webhook secret")
        try:
            payload = json.loads(raw)
        except ValueError:
            raise bad_request("the delivery is not JSON") from None
        event = request.headers.get("X-GitHub-Event", "")
        wanted = webhooks.mirrors(event, payload)
        mirrored = []
        if wanted and wanted[0] in settings.projects:
            project, concerns, message = wanted
            for loop, concern in concerns:
                row = store.post(project, "concern", f"{loop}/{concern}", kind="message", author_type="github",
                                 author=message["login"], author_label=message["association"],
                                 body=message["body"], source=message["source"])
                if row is not None:
                    mirrored.append(row["id"])
            app.logger.info("delivery %s: %s on %s#%s mirrored as %s", request.headers.get("X-GitHub-Delivery"),
                            event, project, message["source"]["pull_request"], mirrored)
        return jsonify(mirrored=mirrored)

    # The deploy convention (command-center/D32).

    @app.get("/version")
    def version():
        return jsonify(commit=settings.commit)

    return app
