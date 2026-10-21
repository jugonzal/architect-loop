"""A session, as the store keeps it and the API shows it."""

import datetime
import uuid
from dataclasses import dataclass, field

from .config import HOLDING_SKILLS

ACTIVE = ("starting", "running", "stopping")
OUTCOMES = ("completed", "budget", "sponsor", "error", "lost")


def utcnow():
    return datetime.datetime.now(datetime.timezone.utc)


def iso(moment):
    return moment.astimezone(datetime.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def parse_iso(text):
    return datetime.datetime.fromisoformat(text.replace("Z", "+00:00"))


def new_session_id():
    return uuid.uuid4().hex


def holds(skill, concern):
    """Whether a session of `skill` on `concern` holds that concern (session-runner D6): a /loop-build or
    /loop-design on a concern. A session on a loop or an environment holds nothing (runner-dispatch C3)."""
    return concern is not None and skill in HOLDING_SKILLS


@dataclass
class Session:
    """What it runs on is exactly one of `concern`, `loop` and `environment` (runner-dispatch C3)."""

    id: str
    project: str
    skill: str
    arguments: str
    model: str
    sponsor: str
    budget_usd: float
    plugin_release: str
    branch: str
    created_at: str
    concern: str | None = None
    loop: str | None = None
    environment: str | None = None
    state: str = "starting"
    outcome: str | None = None
    started_at: str | None = None
    ended_at: str | None = None
    heartbeat_at: str | None = None
    spend: dict | None = None
    pull_requests: list = field(default_factory=list)
    stop_requested: bool = False
    execution: str | None = None
    final_message: str | None = None  # runner-dispatch C3: its last assistant message, kept when it ends

    @property
    def active(self):
        return self.state in ACTIVE

    @property
    def holds(self):
        return holds(self.skill, self.concern)

    @property
    def target(self):
        """The concern, loop or environment it runs on, as the skill is given it."""
        return self.concern or self.loop or self.environment

    def public(self):
        """The Session object of openapi.yaml."""
        return {
            "id": self.id, "project": self.project, "skill": self.skill, "concern": self.concern,
            "loop": self.loop, "environment": self.environment,
            "arguments": self.arguments, "model": self.model, "sponsor": self.sponsor, "budget_usd": self.budget_usd,
            "plugin_release": self.plugin_release, "branch": self.branch, "state": self.state,
            "outcome": self.outcome, "created_at": self.created_at, "started_at": self.started_at,
            "ended_at": self.ended_at, "spend": self.spend, "pull_requests": list(self.pull_requests),
            "final_message": self.final_message,
        }

    def describe(self):
        return f"{self.id} ({self.skill} on {self.target}, sponsored by {self.sponsor}, {self.state})"


@dataclass
class Refusal:
    """Why a dispatch was refused, naming what already exists or the limit it passed (runner-dispatch C2)."""

    refused: str  # open-pull-request | running-session | sponsor-cap | budget-ceiling
    message: str
    pull_requests: list = field(default_factory=list)
    sessions: list = field(default_factory=list)
    cap: int | None = None
    ceiling_usd: float | None = None

    def public(self):
        body = {"refused": self.refused, "message": self.message, "pull_requests": list(self.pull_requests),
                "sessions": [s.public() for s in self.sessions]}
        if self.cap is not None:
            body["cap"] = self.cap
        if self.ceiling_usd is not None:
            body["ceiling_usd"] = self.ceiling_usd
        return body
