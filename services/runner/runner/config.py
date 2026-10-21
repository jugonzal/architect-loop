"""The runner's config, read from environment variables (command-center/D32).

Changing the cap or the skill to model map is a config change, not a design change (session-runner Approach).
"""

import json
import os
from dataclasses import dataclass, field

SKILLS = ("loop-design", "loop-build", "loop-prove", "loop-status")

# session-runner D5: /loop-status on Sonnet 5.5, every other skill on Opus 5.5.
DEFAULT_SKILL_MODELS = {
    "loop-status": "claude-sonnet-5-5",
    "loop-design": "claude-opus-5-5",
    "loop-build": "claude-opus-5-5",
    "loop-prove": "claude-opus-5-5",
}

# List prices in dollars per million tokens, used only for the running estimate while a session runs (D23); the
# final figure is the SDK's own estimate. Source: Anthropic's published model prices as of 2026-10-06 (input,
# output, cache reads), with cache writes at 1.25x input for the 5-minute cache and 2x for the 1-hour cache.
DEFAULT_PRICES = {
    "claude-opus-5-5": {"input": 4.00, "output": 20.00, "cache_write_5m": 5.00, "cache_write_1h": 8.00,
                        "cache_read": 0.20},
    "claude-sonnet-5-5": {"input": 2.00, "output": 10.00, "cache_write_5m": 2.50, "cache_write_1h": 4.00,
                          "cache_read": 0.20},
}

# The measured sessions that seed the first estimates (session-runner Approach): the Q1 spike's full
# /loop-status on Opus 5.5, about $0.44 over 75 s (one sample, an estimate). Its one-file commit was not a skill,
# so it seeds nothing.
DEFAULT_SEEDS = (
    {"skill": "loop-status", "model": "claude-opus-5-5", "usd": 0.44, "wall_clock_s": 75.0},
)

# The tools a session may use, in dontAsk mode (session-runner D3).
ALLOWED_TOOLS = ("Bash", "Read", "Write", "Edit", "Glob", "Grep", "Skill")

MAX_SPEND_INTERVAL_S = 10.0  # D23: at least every 10 seconds


@dataclass(frozen=True)
class Config:
    project: str = "jugonzal/architect-loop"
    main_branch: str = "main"
    cap_per_sponsor: int = 3
    skill_models: dict = field(default_factory=lambda: dict(DEFAULT_SKILL_MODELS))
    prices: dict = field(default_factory=lambda: {k: dict(v) for k, v in DEFAULT_PRICES.items()})
    seeds: tuple = DEFAULT_SEEDS
    spend_interval_s: float = 5.0
    lost_after_s: float = 300.0
    store_path: str = "/tmp/runner/runner.sqlite3"
    commit: str | None = None
    # The runner's own GitHub App (command-center/D27). It does not exist yet; the owner creates it and sets these.
    app_id: str = ""
    app_installation_id: str = ""
    app_slug: str = ""
    # Where sessions run: one Cloud Run job, executed once per session (session-runner D2).
    gcp_project: str = ""
    region: str = "us-east1"
    job: str = "runner-session"
    # Where a session's job clones from and works.
    git_url: str = ""
    workdir: str = "/tmp/runner/sessions"

    def __post_init__(self):
        if not 0 < self.spend_interval_s <= MAX_SPEND_INTERVAL_S:
            raise ValueError(f"spend_interval_s must be above 0 and at most {MAX_SPEND_INTERVAL_S} (D23), "
                             f"not {self.spend_interval_s}")
        if self.cap_per_sponsor < 1:
            raise ValueError(f"cap_per_sponsor must be at least 1, not {self.cap_per_sponsor}")
        missing = [s for s in SKILLS if s not in self.skill_models]
        if missing:
            raise ValueError(f"skill_models has no model for {', '.join(missing)}")
        unpriced = sorted({m for m in self.skill_models.values() if m not in self.prices})
        if unpriced:
            raise ValueError(f"prices has no list price for {', '.join(unpriced)}")
        if self.lost_after_s <= self.spend_interval_s * 3:
            raise ValueError("lost_after_s must leave room for at least three missed publications")

    @property
    def clone_url(self):
        return self.git_url or f"https://github.com/{self.project}.git"

    @property
    def bot_login(self):
        return f"{self.app_slug}[bot]" if self.app_slug else ""

    @classmethod
    def from_env(cls, env=None):
        env = os.environ if env is None else env
        values = {}
        plain = {
            "RUNNER_PROJECT": "project", "RUNNER_MAIN_BRANCH": "main_branch", "RUNNER_STORE": "store_path",
            "COMMIT_SHA": "commit", "RUNNER_APP_ID": "app_id", "RUNNER_APP_INSTALLATION_ID": "app_installation_id",
            "RUNNER_APP_SLUG": "app_slug", "RUNNER_GCP_PROJECT": "gcp_project", "RUNNER_REGION": "region",
            "RUNNER_JOB": "job", "RUNNER_GIT_URL": "git_url", "RUNNER_WORKDIR": "workdir",
        }
        for name, key in plain.items():
            if env.get(name):
                values[key] = env[name]
        numbers = {"RUNNER_CAP_PER_SPONSOR": ("cap_per_sponsor", int),
                   "RUNNER_SPEND_INTERVAL_S": ("spend_interval_s", float),
                   "RUNNER_LOST_AFTER_S": ("lost_after_s", float)}
        for name, (key, kind) in numbers.items():
            if env.get(name):
                values[key] = kind(env[name])
        if env.get("RUNNER_SKILL_MODELS"):
            values["skill_models"] = {**DEFAULT_SKILL_MODELS, **json.loads(env["RUNNER_SKILL_MODELS"])}
        if env.get("RUNNER_PRICES"):
            values["prices"] = {**DEFAULT_PRICES, **json.loads(env["RUNNER_PRICES"])}
        return cls(**values)
