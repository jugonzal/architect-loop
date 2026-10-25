"""Configuration, read from environment variables (command-center/D32).

| Variable | Meaning |
| --- | --- |
| `PORT` | The port to listen on; Cloud Run sets it. Read by the container's command, not here. |
| `COMMIT_SHA` | The commit the image was built from, answered by `GET /version`; `deploy.sh` sets it (D47). |
| `NOTIFY_PROJECTS` | The projects served, as comma-separated `owner/repo`. Phase 1: `jugonzal/architect-loop` (D18). |
| `NOTIFY_STORE` | Where devices, settings and what was pushed are kept: `firestore:<database>`, the notifier's own Firestore database (command-center/D44), or `memory`, which forgets everything on restart (tests and local runs). |
| `NOTIFY_GCP_PROJECT` | The GCP project of that Firestore database. Unset, the client library finds it from Cloud Run. |
| `NOTIFY_STATUS_URL` | The status service the queue is read from, `https://status-<project number>.us-east1.run.app`. It is also the audience of the ID token the notifier sends it (command-center/D28). |
| `NOTIFY_AUDIENCE` | This service's own URL, `https://notify-<project number>.us-east1.run.app`: the audience of the OIDC token a tick must carry (D3, command-center/D67). |
| `NOTIFY_TICK_SERVICE_ACCOUNTS` | The service accounts whose tick is accepted, comma-separated: the notifier's own identity, which its Cloud Scheduler job sends as. |
| `NOTIFY_TICK_KEYS_URL` | The keys a tick's token is checked against. Default Google's; a local harness's own. |
| `NOTIFY_GITHUB_API_URL` | GitHub's REST API, where a caller is identified with `GET /user`. Default `https://api.github.com`. |
| `NOTIFY_EXPO_PUSH_URL` | Expo's push service. Default `https://exp.host/--/api/v2/push/send`. |
| `NOTIFY_EXPO_ACCESS_TOKEN` | Optional. A secret: Expo's access token, needed only once the Expo project turns on enhanced push security. The manifest does not name it yet. |
| `NOTIFY_METADATA_URL` | Cloud Run's metadata server, which mints the ID token. Default `http://metadata.google.internal`. |
| `NOTIFY_CACHE_SECONDS` | How long a caller's login is reused before GitHub is asked again. Default 60. |

A service missing any of the required ones still starts: `GET /version` answers, every other request (a tick
included) is refused with 503 naming what is missing, and nothing is read or pushed. Every outside endpoint is a setting, so a
local harness can point the service at its fakes (command-center/D53).
"""

import os
from dataclasses import dataclass, field

# Every variable the service reads, with what it is for.
VARIABLES = {
    "COMMIT_SHA": "the commit /version answers",
    "NOTIFY_PROJECTS": "the projects served",
    "NOTIFY_STORE": "where devices, settings and what was pushed are kept",
    "NOTIFY_GCP_PROJECT": "the Firestore database's project",
    "NOTIFY_STATUS_URL": "the status service",
    "NOTIFY_AUDIENCE": "the audience a tick's token names",
    "NOTIFY_TICK_SERVICE_ACCOUNTS": "the identities whose tick is accepted",
    "NOTIFY_TICK_KEYS_URL": "the keys a tick's token is checked against",
    "NOTIFY_GITHUB_API_URL": "GitHub's API",
    "NOTIFY_EXPO_PUSH_URL": "Expo's push service",
    "NOTIFY_EXPO_ACCESS_TOKEN": "Expo's access token, for enhanced push security",
    "NOTIFY_METADATA_URL": "the metadata server",
    "NOTIFY_CACHE_SECONDS": "how long a caller's login is reused",
}
# What every deployment sets, in services/notify/service.json; COMMIT_SHA is deploy.sh's. The rest have defaults or
# are optional.
REQUIRED = ("NOTIFY_PROJECTS", "NOTIFY_STORE", "NOTIFY_STATUS_URL", "NOTIFY_AUDIENCE", "NOTIFY_TICK_SERVICE_ACCOUNTS")
SECRETS = ("NOTIFY_EXPO_ACCESS_TOKEN",)
FIRESTORE = "firestore:"
MEMORY = "memory"
GOOGLE_CERTS = "https://www.googleapis.com/oauth2/v3/certs"


def _list(value):
    return [item.strip() for item in (value or "").split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    projects: frozenset
    commit: str = "unknown"
    store: str | None = None
    gcp_project: str | None = None
    status_url: str | None = None
    audience: str | None = None
    tick_service_accounts: tuple = field(default_factory=tuple)
    tick_keys_url: str = GOOGLE_CERTS
    github_api_url: str = "https://api.github.com"
    expo_push_url: str = "https://exp.host/--/api/v2/push/send"
    expo_access_token: str | None = None
    metadata_url: str = "http://metadata.google.internal"
    cache_seconds: float = 60.0

    @classmethod
    def from_env(cls, environ=None):
        env = os.environ if environ is None else environ
        return cls(
            projects=frozenset(_list(env.get("NOTIFY_PROJECTS"))),
            commit=env.get("COMMIT_SHA") or "unknown",
            store=env.get("NOTIFY_STORE") or None,
            gcp_project=env.get("NOTIFY_GCP_PROJECT") or None,
            status_url=(env.get("NOTIFY_STATUS_URL") or "").rstrip("/") or None,
            audience=(env.get("NOTIFY_AUDIENCE") or "").rstrip("/") or None,
            tick_service_accounts=tuple(_list(env.get("NOTIFY_TICK_SERVICE_ACCOUNTS"))),
            tick_keys_url=env.get("NOTIFY_TICK_KEYS_URL") or GOOGLE_CERTS,
            github_api_url=(env.get("NOTIFY_GITHUB_API_URL") or "https://api.github.com").rstrip("/"),
            expo_push_url=env.get("NOTIFY_EXPO_PUSH_URL") or "https://exp.host/--/api/v2/push/send",
            expo_access_token=env.get("NOTIFY_EXPO_ACCESS_TOKEN") or None,
            metadata_url=(env.get("NOTIFY_METADATA_URL") or "http://metadata.google.internal").rstrip("/"),
            cache_seconds=float(env.get("NOTIFY_CACHE_SECONDS") or 60),
        )

    def problems(self):
        """What keeps the service from keeping devices or pushing anything; empty when it can."""
        found = []
        if not self.projects:
            found.append("NOTIFY_PROJECTS names no project")
        for project in sorted(self.projects):
            owner, _, repo = project.partition("/")
            if not owner or not repo or "/" in repo:
                found.append("NOTIFY_PROJECTS: %r is not owner/repo" % project)
        if not self.store:
            found.append("NOTIFY_STORE is not set: firestore:<database>, or memory")
        elif self.store != MEMORY and not (self.store.startswith(FIRESTORE) and self.store[len(FIRESTORE):]):
            found.append("NOTIFY_STORE=%s is neither firestore:<database> nor memory" % self.store)
        if not self.status_url:
            found.append("NOTIFY_STATUS_URL is not set")
        if not self.audience:
            found.append("NOTIFY_AUDIENCE is not set, so no tick can be checked")
        if not self.tick_service_accounts:
            found.append("NOTIFY_TICK_SERVICE_ACCOUNTS names no identity whose tick is accepted")
        return found
