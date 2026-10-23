"""Configuration, read from environment variables (command-center/D32).

| Variable | Meaning |
| --- | --- |
| `PORT` | The port to listen on; Cloud Run sets it. Read by the container's command, not here. |
| `COMMIT_SHA` | The commit the image was built from, answered by `GET /version`; `deploy.sh` sets it (D47). |
| `STATUS_PROJECTS` | The projects served, as comma-separated `owner/repo`. Phase 1: `jugonzal/architect-loop` (D18). |
| `STATUS_GITHUB_APP_ID` | The id of the status service's own read-only GitHub App (command-center/D27). |
| `STATUS_GITHUB_APP_PRIVATE_KEY` | That app's private key, PEM. A secret. |
| `STATUS_GITHUB_WEBHOOK_SECRET` | That app's webhook secret. A secret. Unset, every delivery is refused, and a push or a pull request event reaches the answer only once a document is `STATUS_MAX_AGE_SECONDS` old. |
| `STATUS_GITHUB_API_URL` | GitHub's REST API; GraphQL is at `<it>/graphql`. Default `https://api.github.com`. |
| `STATUS_GITHUB_GIT_URL` | Where the repositories are cloned from, as `<it>/<owner>/<repo>.git`. Default `https://github.com`. |
| `STATUS_CACHE_DIR` | Where the service keeps its clone of each project's repository: a cache. Default `/tmp/status`. |
| `STATUS_MAX_AGE_SECONDS` | How long a document is reused when GitHub delivers nothing. Default 20; under 30 (C1): a regather that cannot read an environment answers it unknown, and that answer is reused as long again, so even then a change is in the answer within a minute. |
| `STATUS_CACHE_SECONDS` | How long a caller's login and membership are reused before GitHub is asked again. Default 60. |
| `STATUS_SERVED_TIMEOUT_SECONDS` | How long a GET of an environment's `/version` may take before it reads as unknown. Default 5. |

The secrets reach the service as environment variables that Cloud Run fills from Secret Manager. A service missing
the project or its app still starts: `GET /version` answers, and every other request is refused with 503 naming
what is missing. Every outside endpoint is a setting, so a local harness can point the service at its fakes
(command-center/D53).
"""

import os
from dataclasses import dataclass

# Every variable the service reads, with what it is for.
VARIABLES = {
    "COMMIT_SHA": "the commit /version answers",
    "STATUS_PROJECTS": "the projects served",
    "STATUS_GITHUB_APP_ID": "the status service's GitHub App",
    "STATUS_GITHUB_APP_PRIVATE_KEY": "that app's private key",
    "STATUS_GITHUB_WEBHOOK_SECRET": "that app's webhook secret",
    "STATUS_GITHUB_API_URL": "GitHub's API",
    "STATUS_GITHUB_GIT_URL": "where repositories are cloned from",
    "STATUS_CACHE_DIR": "the clones",
    "STATUS_MAX_AGE_SECONDS": "how long a document is reused",
    "STATUS_CACHE_SECONDS": "how long a caller's membership is reused",
    "STATUS_SERVED_TIMEOUT_SECONDS": "how long a served-commit read may take",
}
# What every deployment sets, in services/status/service.json; COMMIT_SHA is deploy.sh's. The rest have defaults.
REQUIRED = ("STATUS_PROJECTS", "STATUS_GITHUB_APP_ID", "STATUS_GITHUB_APP_PRIVATE_KEY", "STATUS_GITHUB_WEBHOOK_SECRET")
SECRETS = ("STATUS_GITHUB_APP_PRIVATE_KEY", "STATUS_GITHUB_WEBHOOK_SECRET")


def _list(value):
    return [item.strip() for item in (value or "").split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    projects: frozenset
    commit: str = "unknown"
    github_app_id: str | None = None
    github_private_key: str | None = None
    webhook_secret: bytes | None = None
    github_api_url: str = "https://api.github.com"
    github_git_url: str = "https://github.com"
    cache_dir: str = "/tmp/status"
    max_age_seconds: float = 20.0
    cache_seconds: float = 60.0
    served_timeout_seconds: float = 5.0

    @classmethod
    def from_env(cls, environ=None):
        env = os.environ if environ is None else environ
        secret = env.get("STATUS_GITHUB_WEBHOOK_SECRET")
        return cls(
            projects=frozenset(_list(env.get("STATUS_PROJECTS"))),
            commit=env.get("COMMIT_SHA") or "unknown",
            github_app_id=env.get("STATUS_GITHUB_APP_ID") or None,
            github_private_key=env.get("STATUS_GITHUB_APP_PRIVATE_KEY") or None,
            webhook_secret=secret.encode() if secret else None,
            github_api_url=(env.get("STATUS_GITHUB_API_URL") or "https://api.github.com").rstrip("/"),
            github_git_url=(env.get("STATUS_GITHUB_GIT_URL") or "https://github.com").rstrip("/"),
            cache_dir=env.get("STATUS_CACHE_DIR") or "/tmp/status",
            max_age_seconds=float(env.get("STATUS_MAX_AGE_SECONDS") or 20),
            cache_seconds=float(env.get("STATUS_CACHE_SECONDS") or 60),
            served_timeout_seconds=float(env.get("STATUS_SERVED_TIMEOUT_SECONDS") or 5),
        )

    def problems(self):
        """What keeps the service from serving any status at all; empty when it can."""
        found = []
        if not self.projects:
            found.append("STATUS_PROJECTS names no project")
        for project in sorted(self.projects):
            owner, _, repo = project.partition("/")
            if not owner or not repo or "/" in repo:
                found.append("STATUS_PROJECTS: %r is not owner/repo" % project)
        if not self.github_app_id:
            found.append("STATUS_GITHUB_APP_ID is not set")
        if not self.github_private_key:
            found.append("STATUS_GITHUB_APP_PRIVATE_KEY is not set")
        if not 0 <= self.max_age_seconds < 30:
            found.append("STATUS_MAX_AGE_SECONDS must be under 30, so that even after a regather that cannot read an "
                         "environment, an answer is never a minute behind (C1)")
        return found
