"""The wiring: the service starts from its environment, and a session's job never hands the app's key on."""

import os
import unittest
from unittest import mock

from runner import main
from tests.contract import ContractClient
from tests.fakes import scratch
from tests.test_github import PEM


class ServiceTest(unittest.TestCase):
    def test_the_service_starts_from_its_environment_and_answers_its_version(self):
        env = {"RUNNER_STORE": os.path.join(scratch(self), "runner.sqlite3"), "COMMIT_SHA": "eee8119"}
        api = main.service_from_env(env)
        response = ContractClient(self, api).call("GET", "/version")
        self.assertEqual(response.json, {"commit": "eee8119"})
        self.assertEqual(api.dispatcher.config.cap_per_sponsor, 3)


class JobWiringTest(unittest.TestCase):
    def env(self, **extra):
        return {"RUNNER_STORE": os.path.join(scratch(self), "runner.sqlite3"), "RUNNER_SESSION_ID": "e" * 32,
                "RUNNER_APP_ID": "12345", "RUNNER_APP_INSTALLATION_ID": "678",
                "RUNNER_APP_SLUG": "architect-loop-runner", "RUNNER_APP_PRIVATE_KEY": PEM, **extra}

    def test_the_job_takes_the_apps_key_out_of_the_environment_the_session_inherits(self):
        env = self.env()
        with mock.patch.object(main.RestGitHub, "bot_user_id", return_value=4321):
            job, session_id = main.job_from_env(env)
        self.assertNotIn("RUNNER_APP_PRIVATE_KEY", env)
        self.assertEqual(session_id, "e" * 32)
        self.assertEqual(job.workspace.identity, ("architect-loop-runner[bot]",
                                                  "4321+architect-loop-runner[bot]@users.noreply.github.com"))
        self.assertEqual(job.github.app_auth.private_key, PEM)

    def test_the_job_refuses_to_start_without_the_app(self):
        env = self.env(RUNNER_APP_SLUG="")
        with self.assertRaises(SystemExit):
            main.job_from_env(env)

    def test_the_job_needs_a_session(self):
        env = self.env(RUNNER_SESSION_ID="")
        with self.assertRaises(SystemExit):
            main.job_from_env(env)


if __name__ == "__main__":
    unittest.main()
