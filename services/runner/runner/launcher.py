"""Starting a session's job: one execution of a Cloud Run job per session (session-runner D2).

The service calls the Cloud Run Admin API with its own service identity (command-center/D28), and passes the
session's id to the execution as RUNNER_SESSION_ID; the job reads everything else from the store. The Admin API and
the metadata server default to Google's; the local harness points both at its fakes, whose Cloud Run starts each
execution in a container of its own (command-center/D53).
"""

import json
from typing import Protocol

from .github import urllib_transport

RUN_API = "https://run.googleapis.com"
METADATA = "http://metadata.google.internal"
TOKEN_PATH = "/computeMetadata/v1/instance/service-accounts/default/token"


class Launcher(Protocol):
    def launch(self, session) -> str: ...


class LaunchError(Exception):
    pass


def metadata_token(transport=urllib_transport, metadata=METADATA):
    """The service identity's access token, from the metadata server Cloud Run provides."""
    status, _, data = transport("GET", metadata.rstrip("/") + TOKEN_PATH, {"Metadata-Flavor": "Google"})
    if status != 200:
        raise LaunchError(f"the metadata server answered {status}")
    return json.loads(data)["access_token"]


class CloudRunJobs:
    def __init__(self, gcp_project, region, job, transport=urllib_transport, token=None, api=RUN_API,
                 metadata=METADATA):
        self.gcp_project, self.region, self.job = gcp_project, region, job
        self.transport, self.api = transport, api.rstrip("/")
        self.token = token or (lambda: metadata_token(transport, metadata))

    @property
    def url(self):
        return f"{self.api}/v2/projects/{self.gcp_project}/locations/{self.region}/jobs/{self.job}:run"

    def launch(self, session):
        if not self.gcp_project:
            raise LaunchError("RUNNER_GCP_PROJECT is not set, so there is no job to run")
        body = {"overrides": {"containerOverrides": [{"env": [{"name": "RUNNER_SESSION_ID", "value": session.id}]}],
                              "taskCount": 1}}
        status, _, data = self.transport(
            "POST", self.url, {"Authorization": f"Bearer {self.token()}", "Content-Type": "application/json"},
            json.dumps(body).encode())
        if status != 200:
            raise LaunchError(f"running {self.job} answered {status}: {data[:200]!r}")
        operation = json.loads(data)
        return (operation.get("metadata") or {}).get("name") or operation.get("name", "")
