"""Starting a session's job: one execution of a Cloud Run job per session (session-runner D2).

The service calls the Cloud Run Admin API with its own service identity (command-center/D28), and passes the
session's id to the execution as RUNNER_SESSION_ID; the job reads everything else from the store.
"""

import json
from typing import Protocol

from .github import urllib_transport

METADATA_TOKEN = "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token"


class Launcher(Protocol):
    def launch(self, session) -> str: ...


class LaunchError(Exception):
    pass


def metadata_token(transport=urllib_transport):
    """The service identity's access token, from the metadata server Cloud Run provides."""
    status, _, data = transport("GET", METADATA_TOKEN, {"Metadata-Flavor": "Google"})
    if status != 200:
        raise LaunchError(f"the metadata server answered {status}")
    return json.loads(data)["access_token"]


class CloudRunJobs:
    def __init__(self, gcp_project, region, job, transport=urllib_transport, token=None):
        self.gcp_project, self.region, self.job = gcp_project, region, job
        self.transport = transport
        self.token = token or (lambda: metadata_token(transport))

    @property
    def url(self):
        return (f"https://run.googleapis.com/v2/projects/{self.gcp_project}/locations/{self.region}"
                f"/jobs/{self.job}:run")

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
