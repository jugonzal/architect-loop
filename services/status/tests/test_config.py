"""Configuration comes from environment variables (command-center/D32), and services/status/service.json declares
the ones the service cannot work without, in the format scripts/gcp/manifest.py reads (command-center/D46)."""

import importlib.util
import json
import os
import unittest

from status import config
from status.app import create_app
from status.config import Settings

from support import ROOT, SERVICE

_spec = importlib.util.spec_from_file_location("gcp_manifest", os.path.join(ROOT, "scripts", "gcp", "manifest.py"))
manifest = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(manifest)
MANIFEST_PATH = os.path.join(SERVICE, "service.json")


class SettingsTest(unittest.TestCase):
    def test_everything_is_read_from_the_environment(self):
        settings = Settings.from_env({
            "STATUS_PROJECTS": "jugonzal/architect-loop, example/other",
            "COMMIT_SHA": "abc123",
            "STATUS_GITHUB_APP_ID": "99",
            "STATUS_GITHUB_APP_PRIVATE_KEY": "-----BEGIN PRIVATE KEY-----",
            "STATUS_GITHUB_WEBHOOK_SECRET": "s3cret",
            "STATUS_GITHUB_API_URL": "http://127.0.0.1:9/api",
            "STATUS_GITHUB_GIT_URL": "http://127.0.0.1:9/git",
            "STATUS_CACHE_DIR": "/var/cache/status",
            "STATUS_MAX_AGE_SECONDS": "12",
            "STATUS_CACHE_SECONDS": "30",
            "STATUS_SERVED_TIMEOUT_SECONDS": "3",
        })
        self.assertEqual(settings.projects, frozenset({"jugonzal/architect-loop", "example/other"}))
        self.assertEqual(settings.commit, "abc123")
        self.assertEqual(settings.github_app_id, "99")
        self.assertEqual(settings.webhook_secret, b"s3cret")
        self.assertEqual(settings.github_api_url, "http://127.0.0.1:9/api")
        self.assertEqual(settings.github_git_url, "http://127.0.0.1:9/git")
        self.assertEqual(settings.cache_dir, "/var/cache/status")
        self.assertEqual(settings.max_age_seconds, 12.0)
        self.assertEqual(settings.cache_seconds, 30.0)
        self.assertEqual(settings.served_timeout_seconds, 3.0)
        self.assertEqual(settings.problems(), [])

    def test_defaults_are_githubs_and_twenty_seconds(self):
        settings = Settings.from_env({"STATUS_PROJECTS": "a/b"})
        self.assertEqual(settings.commit, "unknown")
        self.assertIsNone(settings.webhook_secret)
        self.assertEqual(settings.github_api_url, "https://api.github.com")
        self.assertEqual(settings.github_git_url, "https://github.com")
        # C1: a document is reused for at most this long. A regather that cannot read an environment answers it
        # unknown, and that answer is reused as long again, so twice this, and two gathers, must fit in a minute.
        self.assertEqual(settings.max_age_seconds, 20.0)
        self.assertLess(2 * settings.max_age_seconds, 60)

    def test_a_project_and_the_app_must_be_named(self):
        for value in (None, "", "architect-loop", "a/b/c", "/x"):
            with self.subTest(value=value):
                env = {"STATUS_GITHUB_APP_ID": "1", "STATUS_GITHUB_APP_PRIVATE_KEY": "k"}
                if value is not None:
                    env["STATUS_PROJECTS"] = value
                self.assertTrue(Settings.from_env(env).problems())
        self.assertEqual(Settings.from_env({"STATUS_PROJECTS": "a/b"}).problems(),
                         ["STATUS_GITHUB_APP_ID is not set", "STATUS_GITHUB_APP_PRIVATE_KEY is not set"])

    def test_a_max_age_of_half_a_minute_or_more_is_refused(self):
        env = {"STATUS_PROJECTS": "a/b", "STATUS_GITHUB_APP_ID": "1", "STATUS_GITHUB_APP_PRIVATE_KEY": "k"}
        self.assertEqual(Settings.from_env(dict(env, STATUS_MAX_AGE_SECONDS="29")).problems(), [])
        for value in ("30", "60", "-1"):
            with self.subTest(value=value):
                self.assertTrue(Settings.from_env(dict(env, STATUS_MAX_AGE_SECONDS=value)).problems())

    def test_an_unconfigured_service_answers_version_and_refuses_the_rest(self):
        # What a first deploy by scripts/gcp/deploy.sh would start if the manifest were not applied.
        app = create_app(Settings.from_env({"COMMIT_SHA": "abc123"}))
        client = app.test_client()
        self.assertEqual(client.get("/version").get_json(), {"commit": "abc123"})
        for method, path in (("GET", "/projects/jugonzal/architect-loop/status"), ("POST", "/webhooks/github")):
            response = client.open(path, method=method, headers={"Authorization": "Bearer gho_x"})
            self.assertEqual(response.status_code, 503)
            self.assertEqual(response.get_json()["error"], "unavailable")
            self.assertIn("STATUS_PROJECTS", response.get_json()["message"])


class ManifestTest(unittest.TestCase):
    """services/status/service.json, which deploy.sh applies on every deploy (command-center/D46)."""

    def setUp(self):
        self.manifest = manifest.load(MANIFEST_PATH)

    def test_it_fits_the_manifest_format(self):
        self.assertEqual(manifest.problems(self.manifest), [])

    def test_it_declares_every_variable_the_service_cannot_work_without(self):
        declared = set(self.manifest.get("settings", {})) | set(self.manifest.get("secrets", {}))
        self.assertEqual(declared, set(config.REQUIRED))

    def test_its_secrets_are_named_never_given(self):
        self.assertEqual(set(self.manifest.get("secrets", {})), set(config.SECRETS))
        with open(MANIFEST_PATH) as f:
            text = f.read()
        self.assertNotIn("BEGIN", text)
        for name in config.SECRETS:
            self.assertNotIn(name, self.manifest.get("settings", {}))

    def test_it_serves_this_repository_and_leaves_the_app_id_to_the_owner(self):
        settings = self.manifest["settings"]
        self.assertEqual(settings["STATUS_PROJECTS"], "jugonzal/architect-loop")
        self.assertEqual(settings["STATUS_GITHUB_APP_ID"], manifest.TODO)
        # So deploy.sh refuses to deploy it until the owner names the app in a pull request.
        with self.assertRaises(manifest.Refused):
            manifest.checked(MANIFEST_PATH, env="staging")

    def test_it_runs_as_its_own_identity_and_needs_no_cloud_role(self):
        self.assertEqual(self.manifest["identity"], {"name": "status", "roles": []})
        self.assertNotIn("cloudsql", self.manifest)
        self.assertNotIn("firestore", self.manifest)
        self.assertNotIn("jobs", self.manifest)

    def test_every_variable_it_names_is_one_the_service_reads(self):
        declared = set(self.manifest.get("settings", {})) | set(self.manifest.get("secrets", {}))
        self.assertLessEqual(declared, set(config.VARIABLES))
        self.assertEqual(json.loads(json.dumps(self.manifest)), self.manifest)


if __name__ == "__main__":
    unittest.main()
