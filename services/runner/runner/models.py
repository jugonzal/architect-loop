"""A session, as the store keeps it and the API shows it."""

import datetime
import uuid
from dataclasses import dataclass, field

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


@dataclass
class Session:
    id: str
    project: str
    skill: str
    concern: str
    arguments: str
    model: str
    sponsor: str
    budget_usd: float
    plugin_release: str
    branch: str
    created_at: str
    state: str = "starting"
    outcome: str | None = None
    started_at: str | None = None
    ended_at: str | None = None
    heartbeat_at: str | None = None
    spend: dict | None = None
    pull_requests: list = field(default_factory=list)
    stop_requested: bool = False
    execution: str | None = None

    @property
    def active(self):
        return self.state in ACTIVE

    def public(self):
        """The Session object of openapi.yaml."""
        return {
            "id": self.id, "project": self.project, "skill": self.skill, "concern": self.concern,
            "arguments": self.arguments, "model": self.model, "sponsor": self.sponsor, "budget_usd": self.budget_usd,
            "plugin_release": self.plugin_release, "branch": self.branch, "state": self.state,
            "outcome": self.outcome, "created_at": self.created_at, "started_at": self.started_at,
            "ended_at": self.ended_at, "spend": self.spend, "pull_requests": list(self.pull_requests),
        }

    def describe(self):
        return f"{self.id} ({self.skill} on {self.concern}, sponsored by {self.sponsor}, {self.state})"


@dataclass
class Refusal:
    """Why a dispatch was refused, and what already exists (C3)."""

    refused: str  # open-pull-request | running-session | sponsor-cap
    message: str
    pull_requests: list = field(default_factory=list)
    sessions: list = field(default_factory=list)
    cap: int | None = None

    def public(self):
        body = {"refused": self.refused, "message": self.message, "pull_requests": list(self.pull_requests),
                "sessions": [s.public() for s in self.sessions]}
        if self.cap is not None:
            body["cap"] = self.cap
        return body
