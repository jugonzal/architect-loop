"""The runner's HTTP API, as services/runner/openapi.yaml describes it (command-center/D29). A plain WSGI app."""

import json
import re
import urllib.parse

from .dispatch import ApiError, Refused

COMMIT = re.compile(r"^[0-9a-f]{7,40}$")
SESSION = "(?P<id>[0-9a-f]{32})"


class Api:
    # (method, path template in openapi.yaml, handler name); the contract tests compare this with the spec.
    ROUTES = (
        ("GET", "/version", "version"),
        ("POST", "/sessions", "dispatch"),
        ("GET", "/sessions", "list_sessions"),
        ("GET", "/sessions/{id}", "get_session"),
        ("POST", "/sessions/{id}/stop", "stop_session"),
        ("GET", "/estimates", "estimate"),
    )

    def __init__(self, dispatcher):
        self.dispatcher = dispatcher
        self.routes = [(method, re.compile("^" + template.replace("{id}", SESSION) + "$"), getattr(self, name))
                       for method, template, name in self.ROUTES]

    def __call__(self, environ, start_response):
        try:
            status, body, headers = self.route(environ)
        except ApiError as error:
            status, body, headers = error.status, {"error": error.error, "message": error.message}, {}
        except Refused as refused:
            status, body, headers = 409, refused.refusal.public(), {}
        data = json.dumps(body).encode()
        start_response(f"{status} {REASONS.get(status, '')}".strip(),
                       [("Content-Type", "application/json"), ("Content-Length", str(len(data))), *headers.items()])
        return [data]

    def route(self, environ):
        method, path = environ["REQUEST_METHOD"], environ.get("PATH_INFO") or "/"
        allowed = []
        for route_method, pattern, handler in self.routes:
            match = pattern.match(path)
            if match:
                if route_method == method:
                    return handler(environ, **match.groupdict())
                allowed.append(route_method)
        if allowed:
            raise ApiError(405, "method-not-allowed", f"{path} answers {', '.join(sorted(set(allowed)))}")
        raise ApiError(404, "not-found", f"nothing is at {path}")

    def _caller(self, environ):
        return self.dispatcher.caller(environ.get("HTTP_AUTHORIZATION"))

    @staticmethod
    def _query(environ):
        return {k: v[-1] for k, v in urllib.parse.parse_qs(environ.get("QUERY_STRING", "")).items()}

    @staticmethod
    def _body(environ):
        try:
            length = int(environ.get("CONTENT_LENGTH") or 0)
            return json.loads(environ["wsgi.input"].read(length) or b"null")
        except (ValueError, UnicodeDecodeError) as error:
            raise ApiError(400, "invalid-request", f"the body is not JSON: {error}") from error

    def version(self, environ):
        commit = self.dispatcher.config.commit
        if not commit or not COMMIT.match(commit):
            raise ApiError(503, "no-commit", "this deployment was not told which commit it serves (COMMIT_SHA)")
        return 200, {"commit": commit}, {}

    def dispatch(self, environ):
        sponsor = self._caller(environ)
        session = self.dispatcher.dispatch(sponsor, self._body(environ))
        return 201, session.public(), {"Location": f"/sessions/{session.id}"}

    def list_sessions(self, environ):
        self._caller(environ)
        query = self._query(environ)
        sessions = self.dispatcher.sessions(query.get("state", "active"), query.get("sponsor"), query.get("project"))
        return 200, {"sessions": [s.public() for s in sessions],
                     "cap_per_sponsor": self.dispatcher.config.cap_per_sponsor}, {}

    def get_session(self, environ, id):
        self._caller(environ)
        return 200, self.dispatcher.session(id).public(), {}

    def stop_session(self, environ, id):
        caller = self._caller(environ)
        return 202, self.dispatcher.stop(caller, id).public(), {}

    def estimate(self, environ):
        self._caller(environ)
        query = self._query(environ)
        return 200, self.dispatcher.estimate(query.get("skill"), query.get("model")), {}


REASONS = {200: "OK", 201: "Created", 202: "Accepted", 400: "Bad Request", 401: "Unauthorized", 403: "Forbidden",
           404: "Not Found", 405: "Method Not Allowed", 409: "Conflict", 422: "Unprocessable Content",
           502: "Bad Gateway", 503: "Service Unavailable"}
