"""Configuration comes from environment variables (command-center/D32), and services/notify/service.json declares the
ones the service cannot work without, in the format scripts/gcp/manifest.py reads (command-center/D46)."""

import ast
import glob
import importlib.util
import os
import unittest

from notify import config
from notify.app import create_app
from notify.config import Settings

from support import ROOT, SERVICE

_spec = importlib.util.spec_from_file_location("gcp_manifest", os.path.join(ROOT, "scripts", "gcp", "manifest.py"))
manifest = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(manifest)
MANIFEST_PATH = os.path.join(SERVICE, "service.json")


class SettingsTest(unittest.TestCase):
    def test_everything_is_read_from_the_environment(self):
        settings = Settings.from_env({
            "NOTIFY_PROJECTS": "jugonzal/architect-loop, example/other",
            "COMMIT_SHA": "abc123",
            "NOTIFY_STORE": "firestore:notify",
            "NOTIFY_GCP_PROJECT": "demo-notify",
            "NOTIFY_STATUS_URL": "https://status.example/",
            "NOTIFY_AUDIENCE": "https://notify.example/",
            "NOTIFY_TICK_SERVICE_ACCOUNTS": "notify@p.iam.gserviceaccount.com, other@p.iam.gserviceaccount.com",
            "NOTIFY_TICK_KEYS_URL": "http://127.0.0.1:9/keys",
            "NOTIFY_GITHUB_API_URL": "http://127.0.0.1:9/api/",
            "NOTIFY_EXPO_PUSH_URL": "http://127.0.0.1:9/push",
            "NOTIFY_EXPO_ACCESS_TOKEN": "expo-test-token",
            "NOTIFY_METADATA_URL": "http://127.0.0.1:9/",
            "NOTIFY_CACHE_SECONDS": "30",
        })
        self.assertEqual(settings.projects, frozenset({"jugonzal/architect-loop", "example/other"}))
        self.assertEqual(settings.commit, "abc123")
        self.assertEqual(settings.store, "firestore:notify")
        self.assertEqual(settings.gcp_project, "demo-notify")
        self.assertEqual(settings.status_url, "https://status.example")
        self.assertEqual(settings.audience, "https://notify.example")
        self.assertEqual(settings.tick_service_accounts,
                         ("notify@p.iam.gserviceaccount.com", "other@p.iam.gserviceaccount.com"))
        self.assertEqual(settings.tick_keys_url, "http://127.0.0.1:9/keys")
        self.assertEqual(settings.github_api_url, "http://127.0.0.1:9/api")
        self.assertEqual(settings.expo_push_url, "http://127.0.0.1:9/push")
        self.assertEqual(settings.expo_access_token, "expo-test-token")
        self.assertEqual(settings.metadata_url, "http://127.0.0.1:9")
        self.assertEqual(settings.cache_seconds, 30.0)
        self.assertEqual(settings.problems(), [])

    def test_the_defaults_are_githubs_expos_googles_and_trust_no_tick(self):
        settings = Settings.from_env({})
        self.assertEqual(settings.commit, "unknown")
        self.assertEqual(settings.github_api_url, "https://api.github.com")
        self.assertEqual(settings.expo_push_url, "https://exp.host/--/api/v2/push/send")
        self.assertIsNone(settings.expo_access_token)
        self.assertEqual(settings.metadata_url, "http://metadata.google.internal")
        self.assertEqual(settings.tick_keys_url, "https://www.googleapis.com/oauth2/v3/certs")
        self.assertIsNone(settings.audience)
        self.assertEqual(settings.tick_service_accounts, ())

    def test_the_projects_a_store_and_the_status_service_must_be_named(self):
        self.assertEqual(Settings.from_env({}).problems(), [
            "NOTIFY_PROJECTS names no project",
            "NOTIFY_STORE is not set: firestore:<database>, or memory",
            "NOTIFY_STATUS_URL is not set",
            "NOTIFY_AUDIENCE is not set, so no tick can be checked",
            "NOTIFY_TICK_SERVICE_ACCOUNTS names no identity whose tick is accepted",
        ])
        good = {"NOTIFY_PROJECTS": "a/b", "NOTIFY_STORE": "memory", "NOTIFY_STATUS_URL": "https://s",
                "NOTIFY_AUDIENCE": "https://n", "NOTIFY_TICK_SERVICE_ACCOUNTS": "notify@p.iam.gserviceaccount.com"}
        self.assertEqual(Settings.from_env(good).problems(), [])
        for name, value, reason in (("NOTIFY_PROJECTS", "a/b/c", "is not owner/repo"),
                                    ("NOTIFY_STORE", "firestore:", "neither"),
                                    ("NOTIFY_STORE", "sqlite:/tmp/x", "neither"),
                                    ("NOTIFY_AUDIENCE", "", "NOTIFY_AUDIENCE"),
                                    ("NOTIFY_TICK_SERVICE_ACCOUNTS", " , ", "NOTIFY_TICK_SERVICE_ACCOUNTS")):
            with self.subTest(name=name, value=value):
                problems = Settings.from_env({**good, name: value}).problems()
                self.assertTrue(any(reason in p for p in problems), problems)

    def test_an_unconfigured_service_answers_version_and_refuses_the_rest(self):
        app = create_app(Settings.from_env({"COMMIT_SHA": "abc123"}))
        client = app.test_client()
        self.assertEqual(client.get("/version").get_json(), {"commit": "abc123"})
        response = client.get("/projects/jugonzal/architect-loop/devices", headers={"Authorization": "Bearer gho_x"})
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.get_json()["error"], "unavailable")
        self.assertIn("NOTIFY_STORE", response.get_json()["message"])

    def test_an_unconfigured_service_refuses_a_tick_and_reads_nothing(self):
        app = create_app(Settings.from_env({"COMMIT_SHA": "abc123"}))
        response = app.test_client().post("/tick", headers={"Authorization": "Bearer a.b.c"})
        self.assertEqual(response.status_code, 503)
        self.assertIn("NOTIFY_AUDIENCE", response.get_json()["message"])

    def test_every_variable_the_code_reads_is_listed(self):
        read = set()
        for path in glob.glob(os.path.join(SERVICE, "notify", "*.py")):
            with open(path) as f:
                tree = ast.parse(f.read())
            for node in ast.walk(tree):
                if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "get"
                        and node.args and isinstance(node.args[0], ast.Constant)
                        and isinstance(node.args[0].value, str) and node.args[0].value.isupper()):
                    read.add(node.args[0].value)
        self.assertEqual(read, set(config.VARIABLES))


class ManifestTest(unittest.TestCase):
    """services/notify/service.json, the notifier's deploy config (command-center/D46)."""

    def setUp(self):
        self.manifest = manifest.load(MANIFEST_PATH)

    def test_it_fits_the_manifest_format(self):
        self.assertEqual(manifest.problems(self.manifest), [])
        manifest.checked(MANIFEST_PATH, env="staging")
        manifest.checked(MANIFEST_PATH, env="production")

    def test_it_declares_every_variable_the_service_requires(self):
        declared = set(self.manifest.get("settings", {})) | set(self.manifest.get("secrets", {}))
        self.assertLessEqual(set(config.REQUIRED), declared)
        self.assertLessEqual(declared, set(config.VARIABLES), "no code reads these")
        for name in config.SECRETS:
            self.assertNotIn(name, self.manifest.get("settings", {}), "a secret is never set by value")

    def test_it_keeps_its_store_in_a_firestore_database_of_its_own(self):
        # command-center/D44: one database per service, in its environment's project, which bootstrap.sh creates.
        settings = self.manifest["settings"]
        self.assertEqual(settings["NOTIFY_STORE"], "firestore:notify")
        self.assertEqual(self.manifest["firestore"], ["notify"])
        self.assertEqual(settings["NOTIFY_GCP_PROJECT"], "{project}")
        self.assertIn("firestore.googleapis.com", self.manifest["apis"])
        self.assertEqual(self.manifest["identity"], {"name": "notify", "roles": ["roles/datastore.user"]})
        self.assertNotIn("cloudsql", self.manifest)
        self.assertNotIn("jobs", self.manifest)

    def test_it_reads_the_status_service_at_its_cloud_run_url(self):
        # Cloud Run's URL for it, as in LOOP.md §3 (command-center/D32), which is also the ID token's audience.
        self.assertEqual(self.manifest["settings"]["NOTIFY_STATUS_URL"], "https://status-{number}.{region}.run.app")
        config = manifest.render(self.manifest, "staging",
                                 {"project": "loops-512401", "number": "665570365697", "region": "us-east1"}, "abc",
                                 service_name="notify")
        self.assertEqual(config["service"]["env"]["NOTIFY_STATUS_URL"],
                         "https://status-665570365697.us-east1.run.app")
        self.assertEqual(config["identity"], "notify@loops-512401.iam.gserviceaccount.com")

    def test_it_ticks_every_minute_as_its_own_identity(self):
        # notifications D3, command-center/D67: the Cloud Scheduler job notify-tick POSTs /tick every minute with an
        # OIDC token for notify@, whose audience is the notifier's URL, and the notifier trusts exactly that.
        self.assertEqual(self.manifest["schedules"],
                         {"tick": {"cron": "* * * * *", "time_zone": "Etc/UTC", "path": "/tick"}})
        settings = self.manifest["settings"]
        self.assertEqual(settings["NOTIFY_AUDIENCE"], "https://notify-{number}.{region}.run.app")
        self.assertEqual(settings["NOTIFY_TICK_SERVICE_ACCOUNTS"],
                         "%s@{project}.iam.gserviceaccount.com" % self.manifest["identity"]["name"])
        facts = {"project": "loops-512401", "number": "665570365697", "region": "us-east1"}
        config = manifest.render(self.manifest, "staging", facts, "abc", service_name="notify")
        [job] = config["schedules"]
        self.assertEqual((job["id"], job["cron"], job["uri"], job["audience"]),
                         ("notify-tick", "* * * * *", "https://notify-665570365697.us-east1.run.app/tick",
                          config["service"]["env"]["NOTIFY_AUDIENCE"]))

    def test_the_status_service_trusts_this_identity_at_its_own_url(self):
        # command-center/D66: the identity status-callers names in the status service's manifest is this one, and
        # the audience it checks is the URL this service mints its ID token for.
        status = manifest.load(os.path.join(ROOT, "services", "status", "service.json"))["settings"]
        self.assertEqual(status["STATUS_CALLER_SERVICE_ACCOUNTS"], self.manifest["settings"]["NOTIFY_TICK_SERVICE_ACCOUNTS"])
        self.assertEqual(status["STATUS_AUDIENCE"], self.manifest["settings"]["NOTIFY_STATUS_URL"])

    def test_it_serves_the_one_project_and_names_no_github_app(self):
        self.assertEqual(self.manifest["settings"]["NOTIFY_PROJECTS"], "jugonzal/architect-loop")
        self.assertEqual(self.manifest.get("secrets", {}), {})


if __name__ == "__main__":
    unittest.main()
