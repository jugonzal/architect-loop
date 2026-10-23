"""The status API (../openapi.yaml): a project's status document, for the project's collaborators.

Run it with `gunicorn 'status.app:create_app()'`; configuration is in config.py.
"""

import hashlib
import hmac
import json
import logging
import re
import threading
import time

from flask import Flask, jsonify, request

from . import derivation
from .board import Board
from .config import Settings
from .errors import InvalidCredentials, Unavailable
from .facts import Gatherer, utcnow

LOGIN = re.compile(r"[A-Za-z0-9][A-Za-z0-9-]{0,38}")
REPO = re.compile(r"[A-Za-z0-9._-]{1,100}")


class ApiError(Exception):
    def __init__(self, status, error, message):
        super().__init__(message)
        self.status, self.error, self.message = status, error, message


class Access:
    """Who is calling and whether they collaborate on the project, with GitHub's answers reused for `ttl` seconds."""

    def __init__(self, github, ttl, clock):
        self.github, self.ttl, self.clock = github, ttl, clock
        self._cache = {}
        self._lock = threading.Lock()

    def login(self, header):
        scheme, _, token = (header or "").partition(" ")
        token = token.strip()
        if scheme.lower() != "bearer" or not token:
            raise InvalidCredentials("send Authorization: Bearer <token>")
        key = ("user", hashlib.sha256(token.encode()).hexdigest())  # the cache keeps no token
        return self._cached(key, lambda: self.github.user_login(token))

    def is_member(self, project, login):
        return self._cached(("member", project, login), lambda: self.github.is_collaborator(project, login))

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


def signature_ok(secret, body, header):
    """True when `header` is GitHub's X-Hub-Signature-256 for `body` under `secret`."""
    if not secret or not header or not header.startswith("sha256="):
        return False
    expected = "sha256=" + hmac.new(secret, body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header)


def create_app(settings=None, *, github=None, ls=None, clock=time.monotonic, now=utcnow):
    """The WSGI app. Tests pass their own settings, clock and time; on Cloud Run everything comes from the
    environment."""
    if settings is None:
        settings = Settings.from_env()
    problems = settings.problems()
    if github is None:
        from .github import GitHubApp
        github = GitHubApp(settings.github_app_id, settings.github_private_key, api_url=settings.github_api_url)
    if ls is None:
        ls = derivation.load()

    app = Flask(__name__)
    app.json.sort_keys = False
    app.logger.setLevel(logging.INFO)
    access = Access(github, settings.cache_seconds, clock)
    boards = {}

    def board_for(project):
        gatherer = Gatherer(project, settings=settings, github=github, ls=ls, now=now)

        def gather():
            started = time.monotonic()
            facts = gatherer.facts()
            doc = ls.derive(facts)
            app.logger.info("gathered %s at main %s in %.1f s; %d fact(s) unknown", project, doc["main"]["sha"][:12],
                            time.monotonic() - started, len(doc["missing"]))
            return doc

        return Board(gather, settings.max_age_seconds, clock)

    if problems:
        # Started without its configuration: answer /version, refuse the rest.
        app.logger.error("not configured: %s", "; ".join(problems))

        @app.before_request
        def not_configured():
            if request.path != "/version":
                return jsonify(error="unavailable", message="not configured: " + "; ".join(problems)), 503
    else:
        boards.update({project: board_for(project) for project in settings.projects})

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

    @app.get("/projects/<owner>/<repo>/status")
    def get_status(owner, repo):
        if not LOGIN.fullmatch(owner) or not REPO.fullmatch(repo):
            raise ApiError(400, "bad_request", "the project is not owner/repo")
        project = "%s/%s" % (owner, repo)
        if project not in boards:
            raise ApiError(404, "not_found", "%s is not served here" % project)
        login = access.login(request.headers.get("Authorization"))
        if not access.is_member(project, login):
            raise ApiError(403, "forbidden", "%s is not a collaborator on %s" % (login, project))
        response = jsonify(boards[project].current())
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.post("/webhooks/github")
    def github_webhook():
        raw = request.get_data()
        if not signature_ok(settings.webhook_secret, raw, request.headers.get("X-Hub-Signature-256")):
            raise InvalidCredentials("the delivery's signature does not match the status service's webhook secret")
        try:
            payload = json.loads(raw)
        except ValueError:
            raise ApiError(400, "bad_request", "the delivery is not JSON") from None
        repository = payload.get("repository") if isinstance(payload, dict) else None
        project = repository.get("full_name") if isinstance(repository, dict) else None
        project = project if isinstance(project, str) else None
        stale = project in boards
        if stale:
            boards[project].stale()
        app.logger.info("delivery %s: %s on %s%s", request.headers.get("X-GitHub-Delivery"),
                        request.headers.get("X-GitHub-Event"), project, "" if stale else " (not served here)")
        return jsonify(project=project, stale=stale)

    # The deploy convention (command-center/D32).

    @app.get("/version")
    def version():
        return jsonify(commit=settings.commit)

    return app
