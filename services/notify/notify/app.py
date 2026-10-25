"""The notifier's API (../openapi.yaml): a person's devices and settings, a test notification to their own devices,
and the tick its Cloud Scheduler job sends every minute, on which it reads the queue and pushes (notifications D3,
command-center/D67). Only a tick from a trusted service identity pushes anything but a test.

Run it with `gunicorn 'notify.app:create_app()'`; configuration is in config.py.
"""

import hashlib
import json
import logging
import re
import threading
import time
from datetime import datetime, timezone

from flask import Flask, jsonify, request

from .config import FIRESTORE, MEMORY, Settings
from .errors import InvalidCredentials, Unavailable
from .notifier import Notifier, timestamp
from .schedule import Invalid, PersonSettings
from .store import PLATFORMS, Device, device_id, settings_or_default

LOGIN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9-]{0,38}$")
REPO = re.compile(r"^[A-Za-z0-9._-]{1,100}$")
DEVICE = re.compile(r"^[0-9a-f]{32}$")
# An Expo push token, as expo-notifications' getExpoPushTokenAsync answers it.
PUSH_TOKEN = re.compile(r"^Expo(nent)?PushToken\[[A-Za-z0-9_-]{1,200}\]$")
MAX_NAME = 100


class ApiError(Exception):
    def __init__(self, status, error, message):
        super().__init__(message)
        self.status, self.error, self.message = status, error, message


def bad_request(message):
    return ApiError(400, "bad_request", message)


class Access:
    """Who is calling, with GitHub's answer reused for `ttl` seconds."""

    def __init__(self, github, ttl, clock):
        self.github, self.ttl, self.clock = github, ttl, clock
        self._cache = {}
        self._lock = threading.Lock()

    def login(self, header):
        scheme, _, token = (header or "").partition(" ")
        token = token.strip()
        if scheme.lower() != "bearer" or not token:
            raise InvalidCredentials("send Authorization: Bearer <token>")
        key = hashlib.sha256(token.encode()).hexdigest()  # the cache keeps no token
        now = self.clock()
        with self._lock:
            hit = self._cache.get(key)
            if hit and now < hit[1]:
                return hit[0]
        login = self.github.user_login(token)
        if self.ttl > 0:
            with self._lock:
                self._cache[key] = (login, now + self.ttl)
                if len(self._cache) > 10_000:
                    self._cache = {k: v for k, v in self._cache.items() if now < v[1]}
        return login


def store_from(settings):
    """The store NOTIFY_STORE names: `firestore:<database>`, or `memory`."""
    if settings.store == MEMORY:
        from .store import MemoryStore

        logging.getLogger(__name__).warning("NOTIFY_STORE=memory: devices and settings are lost on restart")
        return MemoryStore()
    from .firestore_store import FirestoreStore  # only a store on Firestore needs Firestore's client

    return FirestoreStore(settings.store[len(FIRESTORE):], project=settings.gcp_project)


def notifier_from(settings, store):
    from .expo import Expo
    from .status import MetadataIdentity, StatusService

    status = StatusService(settings.status_url, MetadataIdentity(settings.metadata_url))
    return Notifier(settings.projects, store, status, Expo(settings.expo_push_url, settings.expo_access_token))


def create_app(settings=None, *, store=None, github=None, notifier=None, identity=None, clock=time.monotonic,
               now=None):
    """The WSGI app. Tests pass fakes; on Cloud Run everything comes from the environment."""
    if settings is None:
        settings = Settings.from_env()
    now = now or (lambda: datetime.now(timezone.utc))
    problems = [] if store is not None else settings.problems()
    if store is None and not problems:
        store = store_from(settings)
    if github is None:
        from .github import GitHub
        github = GitHub(settings.github_api_url)
    if notifier is None and store is not None:
        notifier = notifier_from(settings, store)
    if identity is None:
        from .identity import GoogleIdentity
        identity = GoogleIdentity(settings.audience, settings.tick_service_accounts, certs_url=settings.tick_keys_url)

    app = Flask(__name__)
    app.json.sort_keys = False
    app.logger.setLevel(logging.INFO)
    access = Access(github, settings.cache_seconds, clock)

    if problems:
        # Started without its configuration: answer /version, refuse the rest, and read nothing.
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
        if not LOGIN.match(owner) or not REPO.match(repo):
            raise bad_request("the project is not owner/repo")
        project = f"{owner}/{repo}"
        if project not in settings.projects:
            raise ApiError(404, "not_found", f"{project} is not served here")
        return project

    def caller():
        return access.login(request.headers.get("Authorization"))

    def json_body():
        try:
            body = json.loads(request.get_data(as_text=True) or "null")
        except ValueError:
            raise bad_request("the body is not JSON") from None
        if not isinstance(body, dict):
            raise bad_request("the body must be a JSON object")
        return body

    # Devices (C1).

    @app.get("/projects/<owner>/<repo>/devices")
    def list_devices(owner, repo):
        project = project_of(owner, repo)
        login = caller()
        return jsonify(devices=[d.to_json() for d in store.devices_of(project, login)])

    @app.post("/projects/<owner>/<repo>/devices")
    def register_device(owner, repo):
        project = project_of(owner, repo)
        login = caller()
        body = json_body()
        unknown = sorted(set(body) - {"token", "platform", "name", "timezone"})
        if unknown:
            raise bad_request(f"unknown fields: {', '.join(unknown)}")
        token, platform, name = body.get("token"), body.get("platform"), body.get("name")
        if not isinstance(token, str) or not PUSH_TOKEN.match(token):
            raise bad_request("token must be an Expo push token, ExponentPushToken[...]")
        if platform not in PLATFORMS:
            raise bad_request(f"platform must be one of {', '.join(PLATFORMS)}")
        if name is not None and (not isinstance(name, str) or not 1 <= len(name) <= MAX_NAME):
            raise bad_request(f"name must be a string of 1 to {MAX_NAME} characters, or null")
        # command-center/D69: only a person the status document names as a loop's owner or member registers a device.
        if not notifier.is_member(project, login):
            raise ApiError(403, "forbidden", f"{login} is not an owner or member of any loop in {project}")
        first = None
        if "timezone" in body and store.settings_of(project, login) is None:
            try:
                first = PersonSettings.from_json({**PersonSettings().to_json(), "timezone": body["timezone"]})
            except Invalid as error:
                raise bad_request(str(error)) from None
        device = store.register(project, Device(id=device_id(token), login=login, token=token, platform=platform,
                                                name=name, registered_at=timestamp(now())))
        if first is not None:
            store.put_settings(project, login, first)
        app.logger.info("%s: %s registered a %s device", project, login, platform)
        return jsonify(device.to_json())

    @app.delete("/projects/<owner>/<repo>/devices/<device>")
    def unregister_device(owner, repo, device):
        project = project_of(owner, repo)
        if not DEVICE.match(device):
            raise bad_request("a device id is 32 hexadecimal digits")
        login = caller()
        found = store.device(project, device)
        # Another person's device answers as missing, so an id says nothing about whose it is.
        if found is None or found.login != login:
            raise ApiError(404, "not_found", f"you have no device {device} in {project}")
        store.remove(project, device)
        return "", 204

    @app.post("/projects/<owner>/<repo>/test-notification")
    def send_test(owner, repo):
        project = project_of(owner, repo)
        login = caller()
        at = now()
        if not store.mark(project, f"test|{login}|{at:%Y-%m-%dT%H:%M}", timestamp(at)):
            raise ApiError(429, "too_many_requests", "one test notification a minute; try again shortly")
        delivery = notifier.test(project, login)
        app.logger.info("%s: test notification to %s: %s", project, login, delivery)
        return jsonify(devices=delivery.devices, accepted=delivery.accepted, gone=delivery.gone)

    # The tick (C2, C3): the Cloud Scheduler job's call, every minute, as the notifier's own identity.

    @app.post("/tick")
    def tick():
        scheme, _, token = (request.headers.get("Authorization") or "").partition(" ")
        token = token.strip()
        if scheme.lower() != "bearer" or token.count(".") != 2:
            raise InvalidCredentials("a tick sends Authorization: Bearer <an OIDC token for a trusted identity>")
        caller = identity.verify(token)  # a Google token, never sent to GitHub
        reads = notifier.tick()
        for read in reads:
            app.logger.info("tick by %s: %s", caller, read)
        return jsonify(reads=[{"project": r.project, "read": r.ok, "error": r.error, "baseline": r.baseline,
                               "pushed": len(r.pushed), "deferred": len(r.deferred), "digests": len(r.digests)}
                              for r in reads])

    # Settings (C3).

    @app.get("/projects/<owner>/<repo>/settings/me")
    def get_settings(owner, repo):
        project = project_of(owner, repo)
        login = caller()
        saved = store.settings_of(project, login)
        return jsonify({**(saved or PersonSettings()).to_json(), "saved": saved is not None})

    @app.put("/projects/<owner>/<repo>/settings/me")
    def put_settings(owner, repo):
        project = project_of(owner, repo)
        login = caller()
        try:
            chosen = PersonSettings.from_json(json_body())
        except Invalid as error:
            raise bad_request(str(error)) from None
        store.put_settings(project, login, chosen)
        return jsonify({**settings_or_default(store, project, login).to_json(), "saved": True})

    # The deploy convention (command-center/D32).

    @app.get("/version")
    def version():
        return jsonify(commit=settings.commit)

    return app
