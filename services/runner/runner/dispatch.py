"""Dispatch: who is calling, whether they may start a session, and claiming the concern (C1, C3, D22, D28)."""

import math
import re

from .config import SKILLS
from .github import GitHubError, concern_pull_requests
from .models import Refusal, Session, iso, new_session_id, utcnow
from .spend import estimate_from

PROJECT = re.compile(r"^[A-Za-z0-9-]+/[A-Za-z0-9._-]+$")
CONCERN = re.compile(r"^[a-z0-9][a-z0-9-]*/[a-z0-9][a-z0-9-]*$")
RELEASE = re.compile(r"^v[0-9]+\.[0-9]+\.[0-9]+$")
FIELDS = {"project", "skill", "concern", "arguments", "budget_usd", "plugin_release"}
REQUIRED = FIELDS - {"arguments"}


class ApiError(Exception):
    def __init__(self, status, error, message):
        super().__init__(message)
        self.status, self.error, self.message = status, error, message


class Refused(Exception):
    def __init__(self, refusal):
        super().__init__(refusal.message)
        self.refusal = refusal


def invalid(message):
    return ApiError(400, "invalid-request", message)


def validate(body):
    """The dispatch body, as openapi.yaml's DispatchRequest describes it, or a 400 saying what is wrong."""
    if not isinstance(body, dict):
        raise invalid("a dispatch is a JSON object")
    extra = sorted(set(body) - FIELDS)
    if extra:
        # The sponsor in particular is never taken from the request (D28).
        raise invalid(f"a dispatch has no field {', '.join(extra)}; the sponsor is always the caller")
    missing = sorted(REQUIRED - set(body))
    if missing:
        raise invalid(f"a dispatch needs {', '.join(missing)}")
    checks = [
        ("project", lambda v: isinstance(v, str) and PROJECT.match(v), "a repository as owner/name"),
        ("skill", lambda v: v in SKILLS, f"one of {', '.join(SKILLS)}"),
        ("concern", lambda v: isinstance(v, str) and CONCERN.match(v), "loop/concern"),
        ("plugin_release", lambda v: isinstance(v, str) and RELEASE.match(v), "a release tag such as v0.3.0"),
        ("budget_usd", lambda v: isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) and v > 0,
         "a number of dollars above 0"),
        ("arguments", lambda v: isinstance(v, str) and len(v) <= 2000, "text of at most 2000 characters"),
    ]
    for name, ok, expected in checks:
        if name in body and not ok(body[name]):
            raise invalid(f"{name} must be {expected}")
    return {**body, "arguments": body.get("arguments", ""), "budget_usd": float(body["budget_usd"])}


class Dispatcher:
    def __init__(self, config, store, github, launcher, now=utcnow, new_id=new_session_id):
        self.config, self.store, self.github, self.launcher = config, store, github, launcher
        self.now, self.new_id = now, new_id

    def _github(self, call, *args):
        try:
            return call(*args)
        except GitHubError as error:
            raise ApiError(502, "upstream-failed", f"GitHub did not answer as expected: {error}") from error

    def caller(self, authorization):
        """The caller's GitHub login, from GET /user on their token, if they collaborate on the project (D28)."""
        scheme, _, token = (authorization or "").partition(" ")
        if scheme.lower() not in ("bearer", "token") or not token.strip():
            raise ApiError(401, "unauthenticated", "send your GitHub token as `Authorization: Bearer <token>`")
        login = self._github(self.github.login, token.strip())
        if not login:
            raise ApiError(401, "unauthenticated", "GitHub did not accept the token")
        if not self._github(self.github.is_collaborator, login):
            raise ApiError(403, "not-a-collaborator", f"{login} is not a collaborator on {self.config.project}")
        return login

    def _expire(self):
        self.store.expire_lost(iso(self.now()), self.config.lost_after_s)

    def dispatch(self, sponsor, body):
        request = validate(body)
        if request["project"] != self.config.project:
            raise ApiError(422, "unknown-project", f"this runner serves {self.config.project}, "
                                                   f"not {request['project']}")
        loop, concern = request["concern"].split("/")
        if not self._github(self.github.concern_exists, loop, concern):
            raise ApiError(422, "unknown-concern", f"{request['concern']} is not a concern on "
                                                   f"{self.config.main_branch}: no docs/loops/{loop}/{concern}.md")
        if not self._github(self.github.release_exists, request["plugin_release"]):
            raise ApiError(422, "unknown-release", f"{request['plugin_release']} is not a release tag of "
                                                   f"{self.config.project}")
        pulls = concern_pull_requests(self._github(self.github.open_pull_requests), request["concern"])
        if pulls:
            raise Refused(Refusal(
                "open-pull-request",
                f"{request['concern']} already has an open pull request: "
                + "; ".join(f"#{p['number']} {p['url']} from {p['head']}" for p in pulls),
                pull_requests=pulls))
        now = iso(self.now())
        session = Session(
            id=self.new_id(), project=request["project"], skill=request["skill"], concern=request["concern"],
            arguments=request["arguments"], model=self.config.skill_models[request["skill"]], sponsor=sponsor,
            budget_usd=request["budget_usd"], plugin_release=request["plugin_release"], branch=request["concern"],
            created_at=now)
        refusal = self.store.claim(session, self.config.cap_per_sponsor, now, self.config.lost_after_s)
        if refusal:
            raise Refused(refusal)
        try:
            execution = self.launcher.launch(session)
        except Exception as error:
            self.store.finish(session.id, "error", None, [], iso(self.now()))
            raise ApiError(502, "launch-failed", f"the session's job could not be started, so it ended and "
                                                 f"{session.concern} is free again: {error}") from error
        self.store.set_execution(session.id, execution)
        return self.store.get(session.id)

    def sessions(self, state="active", sponsor=None, project=None):
        if state not in ("active", "all"):
            raise invalid("state must be active or all")
        self._expire()
        return self.store.list(state=state, sponsor=sponsor, project=project)

    def session(self, session_id):
        self._expire()
        found = self.store.get(session_id)
        if not found:
            raise ApiError(404, "no-such-session", f"no session has the id {session_id}")
        return found

    def stop(self, caller, session_id):
        found = self.session(session_id)
        if found.sponsor != caller:
            raise ApiError(403, "not-the-sponsor", f"only {found.sponsor}, its sponsor, may stop {session_id}")
        stopped = self.store.request_stop(session_id)
        if not stopped:
            raise ApiError(409, "already-ended", f"{session_id} has already ended ({found.outcome})")
        return stopped

    def estimate(self, skill, model=None):
        if skill not in SKILLS:
            raise invalid(f"skill must be one of {', '.join(SKILLS)}")
        model = model or self.config.skill_models[skill]
        return {"skill": skill, "model": model, "estimate": estimate_from(self.store.measurements(skill, model, 10))}
