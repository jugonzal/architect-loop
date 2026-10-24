"""The local harness's config (command-center/local-harness): how each service's manifest becomes its local
environment, and what refuses a run. Standard library only, and nothing here starts Docker; smoke.sh runs the rest.

Run from the repository root: python3 -m unittest discover -s scripts/local/tests -v
"""

import importlib.util
import json
import os
import shutil
import subprocess
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


harness = load("harness", os.path.join(ROOT, "scripts", "local", "harness.py"))
OUTSIDE = ("github.com", "googleapis.com", "run.app", "anthropic.com", "metadata.google.internal")


def fake_secrets():
    key = "-----BEGIN PRIVATE KEY-----\nmade up\n-----END PRIVATE KEY-----\n"
    return harness.FakeSecrets("pw", make_key=lambda: key)


def write(root, path, text):
    path = os.path.join(root, path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(text)


class ServicesTest(unittest.TestCase):
    def test_ports_follow_services_in_common_sh_and_others_come_after(self):
        tree = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tree)
        write(tree, "scripts/gcp/common.sh", 'SERVICES="status runner threads notify"\n')
        for name in ("threads", "runner", "extra"):
            write(tree, f"services/{name}/Dockerfile", "FROM scratch\n")
            write(tree, f"services/{name}/service.json", "{}\n")
        write(tree, "services/notes/README.md", "not a service\n")
        self.assertEqual(harness.services_in(tree), {"runner": 8702, "threads": 8703, "extra": 8705})

    def test_this_repository_runs_every_service_folder(self):
        found = harness.services_in(ROOT)
        folders = sorted(n for n in os.listdir(os.path.join(ROOT, "services"))
                         if os.path.isfile(os.path.join(ROOT, "services", n, "service.json")))
        self.assertEqual(sorted(found), folders)


class LocalizeTest(unittest.TestCase):
    def test_staging_values_with_local_placeholders(self):
        services = {"threads": 8703}
        self.assertEqual(harness.localize({"staging": "5447412", "production": "TODO(owner)"}, services), "5447412")
        self.assertEqual(harness.localize("runner@{project}.iam.gserviceaccount.com", services),
                         "runner@demo-local.iam.gserviceaccount.com")

    def test_a_services_cloud_run_url_becomes_its_local_address(self):
        services = {"threads": 8703}
        self.assertEqual(harness.localize("https://threads-{number}.{region}.run.app", services), "http://threads:8080")
        self.assertEqual(harness.localize("https://threads-{number}.{region}.run.app/x", services),
                         "http://threads:8080/x")
        # Not a service here: left as the manifest says, with its placeholders filled.
        self.assertEqual(harness.localize("https://other-{number}.{region}.run.app", services),
                         "https://other-0.us-east1.run.app")


class EnvironmentTest(unittest.TestCase):
    def setUp(self):
        self.services = harness.services_in(ROOT)
        self.manifests = {n: harness.load_manifest(ROOT, n) for n in self.services}
        self.fake = fake_secrets()
        self.env = {n: harness.service_env(n, self.manifests[n], self.services, self.fake, "a" * 40)
                    for n in self.services}

    def test_every_secret_is_made_up_here(self):
        for name, manifest in self.manifests.items():
            for key in manifest.get("secrets", {}):
                value = self.env[name][key]
                with self.subTest(service=name, secret=key):
                    if key.endswith("PRIVATE_KEY"):
                        self.assertIn("made up", value)
                    elif key == "DATABASE_URL":
                        self.assertEqual(value, f"postgresql://local:pw@postgres:5432/{name}")
                    else:
                        self.assertTrue(value.startswith("local-fake-"))

    def test_nothing_points_off_the_machine(self):
        for name, env in self.env.items():
            for key, value in env.items():
                with self.subTest(service=name, setting=key):
                    self.assertFalse(any(host in value for host in OUTSIDE), value)

    def test_the_runner_reaches_the_fakes_and_its_store_is_the_emulator(self):
        env = self.env["runner"]
        self.assertEqual(env["RUNNER_STORE"], "firestore:runner")
        self.assertEqual(env["RUNNER_GCP_PROJECT"], "demo-local")
        self.assertEqual(env["FIRESTORE_EMULATOR_HOST"], "firestore:8080")
        self.assertEqual(env["RUNNER_GITHUB_API_URL"], "http://fakes:8711")
        self.assertEqual(env["RUNNER_GIT_URL"], "http://fakes:8711/jugonzal/architect-loop.git")
        self.assertEqual(env["RUNNER_RUN_API_URL"], "http://fakes:8712")
        self.assertEqual(env["RUNNER_METADATA_URL"], "http://fakes:8713")
        self.assertEqual((env["COMMIT_SHA"], env["PORT"]), ("a" * 40, "8080"))
        self.assertNotIn("RUNNER_SDK_CLIENT", env)  # only the job runs the fake SDK

    def test_threads_trusts_the_runner_by_the_fake_metadata_servers_keys(self):
        env = self.env["threads"]
        self.assertEqual(env["THREADS_AUDIENCE"], "http://threads:8080")
        self.assertEqual(env["THREADS_RUNNER_SERVICE_ACCOUNTS"], harness.identity_of(self.manifests["runner"]))
        self.assertEqual(env["THREADS_RUNNER_KEYS_URL"], "http://fakes:8713/oauth2/v3/certs")
        self.assertEqual(env["THREADS_GITHUB_API_URL"], "http://fakes:8711")

    def test_a_session_job_inherits_its_service_and_runs_the_fake_sdk(self):
        job = self.manifests["runner"]["jobs"]["runner-session"]
        env = harness.job_env("runner", job, self.env["runner"], self.services, self.fake, "/opt/runner")
        self.assertEqual(env["RUNNER_SDK_CLIENT"], "fakesdk:client")
        self.assertEqual(env["PYTHONPATH"], "/opt/runner:/opt/local")
        self.assertEqual(env["RUNNER_APP_PRIVATE_KEY"], self.env["runner"]["RUNNER_APP_PRIVATE_KEY"])
        self.assertTrue(env["ANTHROPIC_API_KEY"].startswith("local-fake-"))
        self.assertNotIn("PORT", env)

    def test_each_service_with_a_webhook_secret_receives_githubs_deliveries(self):
        hooks = harness.webhooks(self.env)
        self.assertIn({"url": "http://threads:8080/webhooks/github",
                       "secret": self.env["threads"]["THREADS_GITHUB_WEBHOOK_SECRET"]}, hooks)
        self.assertNotIn("runner", json.dumps(hooks))


class DirtyTreeTest(unittest.TestCase):
    def setUp(self):
        self.repo = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.repo)
        git = ["git", "-C", self.repo, "-c", "user.name=t", "-c", "user.email=t@example.com"]
        subprocess.run([*git, "init", "--quiet"], check=True)
        write(self.repo, "a.txt", "one\n")
        subprocess.run([*git, "add", "a.txt"], check=True)
        subprocess.run([*git, "commit", "--quiet", "-m", "one"], check=True)

    def test_a_clean_tree_runs_and_an_untracked_file_is_left_alone(self):
        harness.refuse_dirty(self.repo)
        write(self.repo, "untracked.txt", "cannot reach an image\n")
        harness.refuse_dirty(self.repo)

    def test_a_changed_tracked_file_refuses_the_run(self):
        write(self.repo, "a.txt", "two\n")
        with self.assertRaises(harness.Refused) as refused:
            harness.refuse_dirty(self.repo)
        self.assertIn("a.txt", str(refused.exception))

    def test_a_staged_change_refuses_the_run(self):
        write(self.repo, "b.txt", "new\n")
        subprocess.run(["git", "-C", self.repo, "add", "b.txt"], check=True)
        with self.assertRaises(harness.Refused):
            harness.refuse_dirty(self.repo)


class LoopContractTest(unittest.TestCase):
    """LOOP.md §3 has a local row for each service in SERVICES, read as loop-status reads it, at the harness's port."""

    def test_every_service_has_a_local_row_at_its_port(self):
        rows = {row["name"]: row for row in harness.local_rows(ROOT)}
        order = harness.service_order(ROOT)
        self.assertTrue(order)
        for place, service in enumerate(order, start=1):
            row = rows.get(f"local/{service}")
            with self.subTest(service=service):
                self.assertIsNotNone(row, f"no LOOP.md §3 row for local/{service}")
                self.assertIsNone(row["error"])
                self.assertEqual(row["command"],
                                 f"sh scripts/gcp/served.sh http://localhost:{harness.BASE_PORT + place}/version")

    def test_local_rows_come_first(self):
        with open(os.path.join(ROOT, "LOOP.md")) as f:
            names = [row["name"] for row in harness.loop_status_module(ROOT).environment_rows(f.read())]
        local = [n for n in names if n.startswith("local/")]
        self.assertEqual(names[:len(local)], local)

    def test_section_4_names_the_smoke_script(self):
        with open(os.path.join(ROOT, "LOOP.md")) as f:
            text = f.read()
        self.assertIn("| Smoke test (end to end, synthetic input) | `sh scripts/local/smoke.sh` |", text)


if __name__ == "__main__":
    unittest.main()
