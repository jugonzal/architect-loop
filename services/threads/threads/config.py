"""Configuration, read from environment variables (command-center/D32).

| Variable | Meaning |
| --- | --- |
| `PORT` | The port to listen on; Cloud Run sets it. Read by the container's command, not here. |
| `COMMIT_SHA` | The commit the image was built from, answered by `GET /version`. `unknown` when unset. |
| `DATABASE_URL` | The thread store, as a libpq URL or conninfo. A secret: it holds the database password. |
| `THREADS_PROJECTS` | The projects served, as comma-separated `owner/repo`. Phase 1: `jugonzal/architect-loop`. |
| `THREADS_GITHUB_APP_ID` | The id of threads' own read-only GitHub App (command-center/D27). |
| `THREADS_GITHUB_APP_PRIVATE_KEY` | That app's private key, PEM. A secret. |
| `THREADS_GITHUB_WEBHOOK_SECRET` | That app's webhook secret. A secret. Unset, every delivery is refused. |
| `THREADS_GITHUB_API_URL` | GitHub's REST API. Default `https://api.github.com`. |
| `THREADS_AUDIENCE` | This service's own URL, the audience the runner's ID token must name. Unset, no runner is trusted. |
| `THREADS_RUNNER_SERVICE_ACCOUNTS` | The service accounts trusted as the runner, comma-separated. Unset, none is. |
| `THREADS_CACHE_SECONDS` | How long a caller's login and membership are reused before GitHub is asked again. Default 60. |

The secrets reach the service as environment variables that Cloud Run fills from Secret Manager. A first deploy
by `scripts/gcp/deploy.sh` sets only `COMMIT_SHA`, so a service missing `THREADS_PROJECTS` or `DATABASE_URL` still
starts: `GET /version` answers, and every other request is refused with 503 naming what is missing.
"""

import os
from dataclasses import dataclass, field


def _list(value):
    return [item.strip() for item in (value or "").split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    projects: frozenset
    commit: str = "unknown"
    webhook_secret: bytes | None = None
    cache_seconds: float = 60.0
    database_url: str | None = None
    github_app_id: str | None = None
    github_private_key: str | None = None
    github_api_url: str = "https://api.github.com"
    audience: str | None = None
    runner_service_accounts: tuple = field(default_factory=tuple)

    @classmethod
    def from_env(cls, environ=None):
        env = os.environ if environ is None else environ
        projects = frozenset(_list(env.get("THREADS_PROJECTS")))
        secret = env.get("THREADS_GITHUB_WEBHOOK_SECRET")
        return cls(
            projects=projects,
            commit=env.get("COMMIT_SHA") or "unknown",
            webhook_secret=secret.encode() if secret else None,
            cache_seconds=float(env.get("THREADS_CACHE_SECONDS") or 60),
            database_url=env.get("DATABASE_URL"),
            github_app_id=env.get("THREADS_GITHUB_APP_ID"),
            github_private_key=env.get("THREADS_GITHUB_APP_PRIVATE_KEY"),
            github_api_url=env.get("THREADS_GITHUB_API_URL") or "https://api.github.com",
            audience=env.get("THREADS_AUDIENCE"),
            runner_service_accounts=tuple(_list(env.get("THREADS_RUNNER_SERVICE_ACCOUNTS"))),
        )

    def problems(self):
        """What keeps the service from serving threads at all; empty when it can."""
        found = []
        if not self.projects:
            found.append("THREADS_PROJECTS names no project")
        for project in sorted(self.projects):
            owner, _, repo = project.partition("/")
            if not owner or not repo or "/" in repo:
                found.append(f"THREADS_PROJECTS: {project!r} is not owner/repo")
        if not self.database_url:
            found.append("DATABASE_URL is not set")
        return found
