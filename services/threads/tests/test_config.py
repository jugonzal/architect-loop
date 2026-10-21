"""Configuration comes from environment variables (command-center/D32); see threads/config.py for each one."""

import unittest

from threads.app import create_app
from threads.config import Settings


class SettingsTest(unittest.TestCase):
    def test_everything_is_read_from_the_environment(self):
        settings = Settings.from_env({
            "THREADS_PROJECTS": "jugonzal/architect-loop, example/other",
            "COMMIT_SHA": "abc123",
            "THREADS_GITHUB_WEBHOOK_SECRET": "s3cret",
            "THREADS_CACHE_SECONDS": "30",
            "DATABASE_URL": "postgresql:///threads",
            "THREADS_GITHUB_APP_ID": "99",
            "THREADS_GITHUB_APP_PRIVATE_KEY": "-----BEGIN PRIVATE KEY-----",
            "THREADS_AUDIENCE": "https://threads.example.run.app",
            "THREADS_RUNNER_SERVICE_ACCOUNTS": "runner@p.iam.gserviceaccount.com",
        })
        self.assertEqual(settings.projects, frozenset({"jugonzal/architect-loop", "example/other"}))
        self.assertEqual(settings.commit, "abc123")
        self.assertEqual(settings.webhook_secret, b"s3cret")
        self.assertEqual(settings.cache_seconds, 30.0)
        self.assertEqual(settings.github_api_url, "https://api.github.com")
        self.assertEqual(settings.runner_service_accounts, ("runner@p.iam.gserviceaccount.com",))

    def test_defaults_trust_nothing(self):
        settings = Settings.from_env({"THREADS_PROJECTS": "jugonzal/architect-loop"})
        self.assertEqual(settings.commit, "unknown")
        self.assertIsNone(settings.webhook_secret)
        self.assertIsNone(settings.audience)
        self.assertEqual(settings.runner_service_accounts, ())

    def test_a_project_and_a_store_must_be_named(self):
        for value in (None, "", "architect-loop", "a/b/c", "/x"):
            with self.subTest(value=value):
                env = {"DATABASE_URL": "postgresql:///threads"}
                if value is not None:
                    env["THREADS_PROJECTS"] = value
                self.assertTrue(Settings.from_env(env).problems())
        self.assertEqual(Settings.from_env({"THREADS_PROJECTS": "a/b"}).problems(), ["DATABASE_URL is not set"])
        self.assertEqual(Settings.from_env({"THREADS_PROJECTS": "a/b", "DATABASE_URL": "x"}).problems(), [])

    def test_an_unconfigured_service_answers_version_and_refuses_the_rest(self):
        # What a first deploy by scripts/gcp/deploy.sh starts: only COMMIT_SHA is set.
        app = create_app(Settings.from_env({"COMMIT_SHA": "abc123"}))
        client = app.test_client()
        self.assertEqual(client.get("/version").get_json(), {"commit": "abc123"})
        for method, path in (("GET", "/projects/jugonzal/architect-loop/loops/command-center/thread"),
                             ("POST", "/webhooks/github")):
            response = client.open(path, method=method, headers={"Authorization": "Bearer gho_x"})
            self.assertEqual(response.status_code, 503)
            self.assertEqual(response.get_json()["error"], "unavailable")
            self.assertIn("THREADS_PROJECTS", response.get_json()["message"])
            self.assertIn("DATABASE_URL", response.get_json()["message"])


if __name__ == "__main__":
    unittest.main()
