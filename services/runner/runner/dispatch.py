"""Dispatch: who is calling, what they may start it on, whether they may start it, and claiming the concern
(runner-dispatch C2, C3; session-runner C5, C6, D6, D8; command-center/D22, D28)."""

import math
import re

from .config import SCOPES, SKILLS
from .github import GitHubError, concern_pull_requests
from .models import Refusal, Session, holds, iso, new_session_id, utcnow
from .spend import estimate_from

PROJECT = re.compile(r"^[A-Za-z0-9-]+/[A-Za-z0-9._-]+$")
CONCERN = re.compile(r"^[a-z0-9][a-z0-9-]*/[a-z0-9][a-z0-9-]*$")
LOOP = re.compile(r"^[a-z0-9][a-z0-9-]*$")
ENVIRONMENT = re.compile(r"^[a-z0-9][a-z0-9-]*(/[a-z0-9][a-z0-9-]*)?$")  # a LOOP.md §3 row, such as staging/runner
RELEASE = re.compile(r"^v[0-9]+\.[0-9]+\.[0-9]+$")
TARGETS = tuple(SCOPES)  # concern, loop, environment: a dispatch names exactly one (runner-dispatch C3)
FIELDS = {"project", "skill", *TARGETS, "arguments", "budget_usd", "plugin_release"}
REQUIRED = {"project", "skill", "budget_usd", "plugin_release"}
A = {"concern": "a concern", "loop": "a loop", "environment": "an environment"}


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
        ("loop", lambda v: isinstance(v, str) and LOOP.match(v), "a loop's name, such as command-center"),
        ("environment", lambda v: isinstance(v, str) and ENVIRONMENT.match(v),
         "an environment as LOOP.md names it, such as staging/runner"),
        ("plugin_release", lambda v: isinstance(v, str) and RELEASE.match(v), "a release tag such as v0.3.0"),
        ("budget_usd", lambda v: isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) and v > 0,
         "a number of dollars above 0"),
        ("arguments", lambda v: isinstance(v, str) and len(v) <= 2000, "text of at most 2000 characters"),
    ]
    for name, ok, expected in checks:
        if name in body and not ok(body[name]):
            raise invalid(f"{name} must be {expected}")
    named = [t for t in TARGETS if t in body]
    if len(named) != 1:
        raise invalid("a dispatch names exactly one of concern, loop and environment"
                      + (f", not {' and '.join(named)}" if named else ""))
    scope = named[0]
    if body["skill"] not in SCOPES[scope]:
        on = " or ".join(A[s] for s in SCOPES if body["skill"] in SCOPES[s])
        raise invalid(f"{body['skill']} runs on {on}, not on {A[scope]}")
    return {**body, "scope": scope, "target": body[scope], "arguments": body.get("arguments", ""),
            "budget_usd": float(body["budget_usd"])}


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
        ceiling = self.config.budget_ceiling_usd
        if request["budget_usd"] > ceiling:
            raise Refused(Refusal(
                "budget-ceiling",
                f"a budget of ${request['budget_usd']:,.2f} is above the runner's ceiling of ${ceiling:,.2f} "
                f"(session-runner D8)", ceiling_usd=ceiling))
        self._check_target(request["scope"], request["target"])
        if not self._github(self.github.release_exists, request["plugin_release"]):
            raise ApiError(422, "unknown-release", f"{request['plugin_release']} is not a release tag of "
                                                   f"{self.config.project}")
        if holds(request["skill"], request.get("concern")):
            # D6: an open pull request holds its concern against another /loop-build or /loop-design; a /loop-prove
            # or /loop-status runs beside it, so a proof can go into that pull request's body.
            pulls = concern_pull_requests(self._github(self.github.open_pull_requests), request["concern"])
            if pulls:
                raise Refused(Refusal(
                    "open-pull-request",
                    f"{request['concern']} already has an open pull request: "
                    + "; ".join(f"#{p['number']} {p['url']} from {p['head']}" for p in pulls),
                    pull_requests=pulls))
        now = iso(self.now())
        # A session on a concern starts on its branch; one on a loop or an environment works from main and pushes no
        # branch of its own unless its skill opens a pull request (runner-dispatch C3).
        branch = request["concern"] if request["scope"] == "concern" else self.config.main_branch
        session = Session(
            id=self.new_id(), project=request["project"], skill=request["skill"], concern=request.get("concern"),
            loop=request.get("loop"), environment=request.get("environment"), arguments=request["arguments"],
            model=self.config.skill_models[request["skill"]], sponsor=sponsor, budget_usd=request["budget_usd"],
            plugin_release=request["plugin_release"], branch=branch, created_at=now)
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

    def _check_target(self, scope, target):
        """The concern, loop or environment exists on main, so no session starts, and spends, on a typo."""
        main = self.config.main_branch
        if scope == "concern":
            loop, concern = target.split("/")
            if not self._github(self.github.concern_exists, loop, concern):
                raise ApiError(422, "unknown-concern", f"{target} is not a concern on {main}: "
                                                       f"no docs/loops/{loop}/{concern}.md")
        elif scope == "loop":
            if not self._github(self.github.loop_exists, target):
                raise ApiError(422, "unknown-loop", f"{target} is not a loop on {main}: "
                                                    f"no docs/loops/{target}/README.md")
        else:
            known = self._github(self.github.environments)
            if target not in known:
                raise ApiError(422, "unknown-environment",
                               f"{target} is not an environment in LOOP.md §3 on {main}, which lists "
                               + (", ".join(known) if known else "none"))

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
