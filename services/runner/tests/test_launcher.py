"""Starting a session's job on Cloud Run, against a fake transport: nothing reaches Google."""

import json
import unittest

from runner.launcher import CloudRunJobs, LaunchError, metadata_token
from tests.test_github import Transport


class Session:
    id = "d" * 32


class LauncherTest(unittest.TestCase):
    def setUp(self):
        self.transport = Transport()
        self.jobs = CloudRunJobs("architect-loop-staging", "us-east1", "runner-session", transport=self.transport,
                                 token=lambda: "ya29.service-identity")

    def test_it_runs_one_execution_of_the_job_with_the_sessions_id(self):
        self.transport.answer(200, {"name": "operations/1", "metadata": {
            "name": "projects/architect-loop-staging/locations/us-east1/jobs/runner-session/executions/e1"}})
        execution = self.jobs.launch(Session())
        [request] = self.transport.requests
        self.assertEqual(request["url"], "https://run.googleapis.com/v2/projects/architect-loop-staging/locations/"
                                         "us-east1/jobs/runner-session:run")
        self.assertEqual(request["headers"]["Authorization"], "Bearer ya29.service-identity")
        self.assertEqual(request["body"]["overrides"], {
            "containerOverrides": [{"env": [{"name": "RUNNER_SESSION_ID", "value": "d" * 32}]}], "taskCount": 1})
        self.assertTrue(execution.endswith("/executions/e1"))

    def test_a_refusal_is_an_error(self):
        self.transport.answer(403, {"error": {"message": "permission denied"}})
        with self.assertRaises(LaunchError):
            self.jobs.launch(Session())

    def test_without_a_project_nothing_is_called(self):
        jobs = CloudRunJobs("", "us-east1", "runner-session", transport=self.transport, token=lambda: "t")
        with self.assertRaises(LaunchError):
            jobs.launch(Session())
        self.assertEqual(self.transport.requests, [])

    def test_the_token_comes_from_the_metadata_server(self):
        self.transport.answer(200, {"access_token": "ya29.x", "expires_in": 3599})
        self.assertEqual(metadata_token(self.transport), "ya29.x")
        self.assertEqual(self.transport.requests[0]["headers"], {"Metadata-Flavor": "Google"})


if __name__ == "__main__":
    unittest.main()
