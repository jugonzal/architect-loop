"""Tests for the services' manifests (command-center/service-manifests): the format that scripts/gcp/manifest.py
reads, how deploy.sh applies the manifest of the commit it deploys (C1), what bootstrap.sh creates from the
manifests (C2), and whether the runner's and threads' manifests declare what their code reads (C3).

The scripts run against the fake gcloud, docker and curl of test_layout.py, first on PATH; git is real. Nothing here
reaches Google Cloud.

Run from the repository root: python3 -m unittest discover -s tests -v
"""

import ast
import copy
import glob
import importlib.util
import json
import os
import re
import shutil
import tempfile
import unittest

from test_layout import GCP, ROOT, STAGING, GcpHarness, write

spec = importlib.util.spec_from_file_location("gcp_manifest", os.path.join(GCP, "manifest.py"))
manifest = importlib.util.module_from_spec(spec)
spec.loader.exec_module(manifest)

IDENTITY = "fixture-runtime@%s.iam.gserviceaccount.com" % STAGING
# A manifest with every field of the format.
FULL = {
    "identity": {"name": "fixture-runtime", "roles": ["roles/cloudsql.client", "roles/datastore.user"]},
    "apis": ["sqladmin.googleapis.com", "sql-component.googleapis.com", "firestore.googleapis.com"],
    "settings": {
        "FIXTURE_PROJECT": "{project}",
        "FIXTURE_URL": "https://fixture-{number}.{region}.run.app",
        "FIXTURE_LIST": "a,b, with spaces=and equals",
        "FIXTURE_APP_ID": {"staging": "111", "production": "222"},
    },
    "secrets": {"FIXTURE_APP_PRIVATE_KEY": "fixture-app-private-key", "DATABASE_URL": "fixture-database-url"},
    "cloudsql": "fixture-sql",
    "firestore": ["fixture-store"],
    "jobs": {
        "fixture-job": {
            "command": ["python", "-m", "fixture", "job"],
            "tasks": 1,
            "max_retries": 0,
            "task_timeout_s": 3600,
            "settings": {"FIXTURE_JOB_ONLY": "yes"},
            "secrets": {"FIXTURE_API_KEY": "fixture-api-key"},
        },
    },
}
FULL_SECRETS = ("fixture-app-private-key", "fixture-database-url", "fixture-api-key")


def full(**changes):
    """FULL with some of its fields replaced; a field given as None is removed."""
    m = copy.deepcopy(FULL)
    for key, value in changes.items():
        if value is None:
            m.pop(key, None)
        else:
            m[key] = value
    return m


class FormatTest(unittest.TestCase):
    """A manifest that does not fit the format is refused, with every reason (C1)."""

    def test_a_manifest_with_every_field_fits(self):
        self.assertEqual(manifest.problems(FULL), [])

    def test_the_smallest_manifest_names_only_an_identity(self):
        self.assertEqual(manifest.problems({"identity": {"name": "probe-runtime"}}), [])

    def test_the_probes_manifest_fits(self):
        self.assertEqual(manifest.problems(manifest.load(os.path.join(GCP, "probe", "service.json"))), [])

    def test_each_misfit_is_refused_with_its_reason(self):
        job = FULL["jobs"]["fixture-job"]
        cases = [
            ([], "a JSON object"),
            (full(setting={}), "setting: not a field"),
            (full(identity=None), "identity: missing"),
            (full(identity={"name": "rt"}), "identity.name: a service account ID"),
            (full(identity={"name": "deploy"}), "deploy is the deploy identity"),
            (full(identity={"name": "fixture-runtime", "roles": ["owner"]}), "identity.roles"),
            (full(identity={"name": "fixture-runtime", "email": "x"}), "identity:"),
            (full(apis=["sqladmin"]), "apis:"),
            (full(settings={"lower_case": "x"}), "settings.lower_case"),
            (full(settings={"COMMIT_SHA": "x"}), "deploy.sh sets it"),
            (full(settings={"PORT": "8080"}), "Cloud Run sets it"),
            (full(settings={"FIXTURE_APP_PRIVATE_KEY_X": "x"}), "its name says it holds a secret"),
            (full(settings={"FIXTURE_NOTE": "-----BEGIN RSA PRIVATE KEY-----"}), "holds a key"),
            (full(settings={"FIXTURE_COUNT": 3}), "a value is a string"),
            (full(settings={"FIXTURE_APP_ID": {"staging": "1"}}), "names both"),
            (full(settings={"FIXTURE_URL": "https://{projetc}.example"}), "{projetc} is not a placeholder"),
            (full(settings={"DATABASE_NAME": "x"}, secrets={"DATABASE_NAME": "fixture-database-name"}),
             "secrets.DATABASE_NAME: already declared in settings"),
            (full(secrets={"FIXTURE_TOKEN": "not a name"}), "the name of a secret"),
            (full(cloudsql="Fixture_SQL"), "cloudsql:"),
            (full(apis=["firestore.googleapis.com"]), "cloudsql: needs sqladmin.googleapis.com"),
            (full(apis=["sqladmin.googleapis.com", "sql-component.googleapis.com"]),
             "firestore: needs firestore.googleapis.com"),
            (full(firestore=["db"]), "firestore: a list of database IDs"),
            (full(jobs={"fixture-job": dict(job, command="python -m fixture job")}), "command: a list"),
            (full(jobs={"fixture-job": dict(job, command=["python", "-m,fixture"])}), "command: a list"),
            (full(jobs={"fixture-job": {k: v for k, v in job.items() if k != "task_timeout_s"}}),
             "task_timeout_s: missing"),
            (full(jobs={"fixture-job": dict(job, max_retries=11)}), "max_retries: a whole number from 0 to 10"),
            (full(jobs={"fixture-job": dict(job, tasks=True)}), "tasks: a whole number"),
            (full(jobs={"fixture-job": dict(job, task_timeout_s=0)}), "task_timeout_s: whole seconds"),
            (full(jobs={"fixture-job": dict(job, image="x")}), "jobs.fixture-job.image: not a field of a job"),
            (full(jobs={"fixture-job": dict(job, settings={"FIXTURE_LIST": "again"})}),
             "jobs.fixture-job.settings.FIXTURE_LIST: already declared in settings"),
            (full(jobs={"Fixture_Job": job}), "a job's name"),
        ]
        for m, reason in cases:
            with self.subTest(reason=reason):
                found = manifest.problems(m)
                self.assertTrue(any(reason in p for p in found), found)

    def test_every_problem_is_reported_at_once(self):
        found = manifest.problems(full(identity=None, settings=[], cloudsql=7))
        for field in ("identity:", "settings:", "cloudsql:"):
            self.assertTrue(any(p.startswith(field) for p in found), found)

    def test_a_key_given_twice_is_refused(self):
        path = os.path.join(self.tmp(), "service.json")
        write(os.path.dirname(path), "service.json", '{"identity": {"name": "fixture-runtime"}, "identity": {}}')
        with self.assertRaisesRegex(manifest.Refused, "appears twice"):
            manifest.checked(path)

    def test_a_value_left_todo_is_refused_only_where_it_is_todo(self):
        m = full(settings={"FIXTURE_APP_ID": {"staging": "111", "production": "TODO(owner)"}})
        self.assertEqual(manifest.problems(m), [], "TODO(owner) fits the format; only a deploy refuses it")
        self.assertEqual(manifest.todos(m, "staging"), [])
        self.assertEqual(manifest.todos(m, "production"), ["settings.FIXTURE_APP_ID"])

    def tmp(self):
        path = tempfile.mkdtemp(prefix="manifest-")
        self.addCleanup(shutil.rmtree, path)
        return path


class RenderTest(unittest.TestCase):
    """What a manifest means in one environment: the values deploy.sh sets there."""

    FACTS = {"project": STAGING, "number": "100000000001", "region": "us-east1"}

    def test_placeholders_and_per_environment_values_resolve(self):
        config = manifest.render(FULL, "production", dict(self.FACTS, project="al-test-production"), "abc1234")
        env = config["service"]["env"]
        self.assertEqual(env["FIXTURE_PROJECT"], "al-test-production")
        self.assertEqual(env["FIXTURE_URL"], "https://fixture-100000000001.us-east1.run.app")
        self.assertEqual(env["FIXTURE_APP_ID"], "222")
        self.assertEqual(env["COMMIT_SHA"], "abc1234")
        self.assertEqual(config["identity"], "fixture-runtime@al-test-production.iam.gserviceaccount.com")
        self.assertEqual(config["service"]["cloudsql"], "al-test-production:us-east1:fixture-sql")

    def test_a_job_has_the_services_config_and_its_own(self):
        config = manifest.render(FULL, "staging", self.FACTS, "abc1234")
        service, job = config["service"], config["jobs"]["fixture-job"]
        self.assertEqual(job["env"], dict(service["env"], FIXTURE_JOB_ONLY="yes"))
        self.assertEqual(job["secrets"], dict(service["secrets"], FIXTURE_API_KEY="fixture-api-key"))
        self.assertEqual(job["cloudsql"], service["cloudsql"])

    def test_a_placeholder_without_its_fact_is_refused(self):
        with self.assertRaisesRegex(manifest.Refused, r"settings.FIXTURE_URL uses \{number\}"):
            manifest.render(FULL, "staging", dict(self.FACTS, number=""), "abc1234")


class ManifestDeployHarness(GcpHarness):
    """A repository with one service whose manifest is FULL, in a staging project bootstrapped from it, whose
    secrets the owner has created. deploy.sh then deploys commits of it."""

    bootstrapped = None

    def setUp(self):
        if ManifestDeployHarness.bootstrapped is None:
            root = self.make_root()
            self.add_service(root, "fixture", FULL)
            self.assertEqual(self.bootstrap(root).returncode, 0)
            for name in FULL_SECRETS:
                self.add_secret(name)
            result = self.bootstrap(root)
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            ManifestDeployHarness.bootstrapped = self.state()
        self.root = self.make_root()
        self.set_state(ManifestDeployHarness.bootstrapped)
        self.add_service(self.root, "fixture", FULL)
        self.main = self.init_repo()
        self.number = self.state()["projects"][STAGING]["number"]

    def commit_manifest(self, m, message):
        """Commit a new manifest for the fixture on main and push it; return the commit."""
        if m is None:
            os.remove(os.path.join(self.root, "services", "fixture", "service.json"))
        else:
            write(self.root, "services/fixture/service.json", json.dumps(m, indent=1) + "\n")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", message)
        self.git("push", "-q", "origin", "main")
        return self.git("rev-parse", "HEAD")

    def deployed(self):
        project = self.state()["projects"][STAGING]
        return project["run"].get("fixture"), project.get("jobs", {}).get("fixture-job")

    def expected_env(self, commit):
        return {"FIXTURE_PROJECT": STAGING, "FIXTURE_URL": "https://fixture-%s.us-east1.run.app" % self.number,
                "FIXTURE_LIST": "a,b, with spaces=and equals", "FIXTURE_APP_ID": "111", "COMMIT_SHA": commit}


@unittest.skipUnless(shutil.which("git"), "needs git")
class DeployAppliesTheManifestTest(ManifestDeployHarness):
    """deploy.sh reads the manifest at the commit it deploys and applies all of it (C1)."""

    def test_a_deploy_applies_the_whole_manifest_of_its_commit(self):
        result = self.deploy("fixture", self.main)
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        service, job = self.deployed()
        secrets = {"FIXTURE_APP_PRIVATE_KEY": "fixture-app-private-key:latest",
                   "DATABASE_URL": "fixture-database-url:latest"}
        cloudsql = ["%s:us-east1:fixture-sql" % STAGING]
        self.assertEqual(service["identity"], IDENTITY)
        self.assertEqual(service["env"], self.expected_env(self.main))
        self.assertEqual(service["secrets"], secrets)
        self.assertEqual(service["cloudsql"], cloudsql)
        self.assertTrue(service["public"], "/version must answer without credentials (D32)")
        self.assertEqual(job["image"], service["image"], "the job runs the service's image")
        self.assertEqual(job["identity"], IDENTITY)
        self.assertEqual(job["env"], dict(self.expected_env(self.main), FIXTURE_JOB_ONLY="yes"))
        self.assertEqual(job["secrets"], dict(secrets, FIXTURE_API_KEY="fixture-api-key:latest"))
        self.assertEqual(job["cloudsql"], cloudsql)
        self.assertEqual((job["command"], job["args"], job["tasks"], job["max_retries"], job["task_timeout"]),
                         (["python"], ["-m", "fixture", "job"], "1", "0", "3600s"))
        # The jobs go first, so a service at this commit never starts a job left at an earlier one.
        self.assertEqual([c for c in self.changes() if " deploy " in " %s " % c],
                         ["run jobs deploy fixture-job", "run deploy fixture"])
        self.assertIn("config from services/fixture/service.json: runs as " + IDENTITY, result.stdout)
        self.assertIn("deployed fixture to staging", result.stdout)

    def test_deploying_an_earlier_commit_restores_that_commits_config(self):
        self.assertEqual(self.deploy("fixture", self.main).returncode, 0)
        first = self.deployed()
        later = full(cloudsql=None, apis=["firestore.googleapis.com"])
        later["settings"]["FIXTURE_LIST"] = "changed"
        del later["settings"]["FIXTURE_URL"]
        later["settings"]["FIXTURE_NEW"] = "added"
        del later["secrets"]["DATABASE_URL"]
        later["jobs"]["fixture-job"]["task_timeout_s"] = 600
        second = self.commit_manifest(later, "Change the fixture's config")
        result = self.deploy("fixture", second)
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        service, job = self.deployed()
        env = dict(self.expected_env(second), FIXTURE_LIST="changed", FIXTURE_NEW="added")
        del env["FIXTURE_URL"]
        self.assertEqual(service["env"], env, "a variable the manifest dropped is gone")
        self.assertEqual(service["secrets"], {"FIXTURE_APP_PRIVATE_KEY": "fixture-app-private-key:latest"})
        self.assertEqual(service["cloudsql"], [])
        self.assertEqual(job["task_timeout"], "600s")
        # Cloud Run jobs have no flag that clears a Cloud SQL instance, so a job keeps one its manifest drops.
        self.assertEqual(job["cloudsql"], first[1]["cloudsql"])

        result = self.deploy("fixture", self.main)
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertEqual(self.deployed(), first, "deploying the earlier commit restores all of its config")
        self.assertEqual(self.deployed()[0]["env"]["COMMIT_SHA"], self.main)

    def test_the_manifest_is_read_from_the_commit_not_the_working_tree(self):
        write(self.root, "services/fixture/service.json", json.dumps(full(settings={"FIXTURE_X": "uncommitted"})))
        result = self.deploy("fixture", self.main)
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertEqual(self.deployed()[0]["env"], self.expected_env(self.main))

    def test_a_malformed_manifest_is_refused_before_any_call(self):
        sha = self.commit_manifest(full(setting={"FIXTURE_X": "y"}), "Break the fixture's manifest")
        result = self.deploy("fixture", sha)
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("services/fixture/service.json does not fit the manifest format", result.stderr)
        self.assertIn("setting: not a field", result.stderr)
        self.assertEqual(self.calls(), [], "nothing is built, pushed or deployed, and gcloud is never called")

    def test_a_manifest_that_is_not_json_is_refused_before_any_call(self):
        write(self.root, "services/fixture/service.json", "{\"identity\": ")
        self.git("commit", "-qam", "Truncate the fixture's manifest")
        self.git("push", "-q", "origin", "main")
        result = self.deploy("fixture", self.git("rev-parse", "HEAD"))
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("not JSON", result.stderr)
        self.assertEqual(self.calls(), [])

    def test_a_value_left_todo_is_refused_before_any_call(self):
        m = full()
        m["settings"]["FIXTURE_APP_ID"] = {"staging": "TODO(owner)", "production": "222"}
        sha = self.commit_manifest(m, "Leave the fixture's staging app to the owner")
        result = self.deploy("fixture", sha)
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("leaves settings.FIXTURE_APP_ID TODO(owner) for staging", result.stderr)
        self.assertEqual(self.calls(), [])

    def test_a_commit_without_a_manifest_is_refused_before_any_call(self):
        sha = self.commit_manifest(None, "Remove the fixture's manifest")
        result = self.deploy("fixture", sha)
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("has no services/fixture/service.json", result.stderr)
        self.assertEqual(self.calls(), [])


class BootstrapCreatesWhatManifestsDeclareTest(GcpHarness):
    """bootstrap.sh enables the manifests' APIs, creates their Firestore databases and runtime identities, lets each
    identity read its own secrets, and a second run changes nothing (C2)."""

    def test_a_first_run_creates_what_the_manifests_declare(self):
        root = self.make_root()
        self.add_service(root, "fixture", FULL)
        result = self.bootstrap(root)
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        changes = self.changes()
        self.assertIn("services enable run.googleapis.com artifactregistry.googleapis.com secretmanager.googleapis.com"
                      " iamcredentials.googleapis.com billingbudgets.googleapis.com sqladmin.googleapis.com"
                      " sql-component.googleapis.com firestore.googleapis.com", changes)
        self.assertIn("iam service-accounts create fixture-runtime", changes)
        self.assertIn("firestore databases create", changes)
        project = self.state()["projects"][STAGING]
        self.assertIn(IDENTITY, project["accounts"])
        self.assertEqual(sorted(role for role, members in project["policy"].items()
                                if "serviceAccount:" + IDENTITY in members),
                         ["roles/cloudsql.client", "roles/datastore.user"])
        self.assertEqual(project["firestore"], {"fixture-store": {"location": "us-east1", "type": "firestore-native"}})
        # The owner creates the secrets and their values; the bootstrap only says which are missing.
        self.assertEqual(project.get("secrets", {}), {})
        for name in FULL_SECRETS:
            self.assertIn("missing  secret %s, which fixture names" % name, result.stdout)

    def test_a_second_run_changes_nothing(self):
        root = self.make_root()
        self.add_service(root, "fixture", FULL)
        self.assertEqual(self.bootstrap(root).returncode, 0)
        before = self.state()
        self.reset_calls()
        result = self.bootstrap(root)
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertTrue([c for c in self.calls("gcloud") if c["argv"][:3] == ["firestore", "databases", "describe"]],
                        "a second run must look for the database again, not skip it")
        self.assertEqual(self.changes(), [])
        self.assertEqual(self.state(), before)
        self.assertIn("staging: 0 changes.", result.stdout)

    def test_once_the_secrets_exist_each_identity_may_read_only_its_own(self):
        root = self.make_root()
        self.add_service(root, "fixture", FULL)
        self.add_service(root, "other", {"identity": {"name": "other-runtime"},
                                         "secrets": {"OTHER_SECRET": "other-secret"}})
        self.assertEqual(self.bootstrap(root).returncode, 0)
        for name in FULL_SECRETS + ("other-secret",):
            self.add_secret(name)
        self.reset_calls()
        result = self.bootstrap(root)
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertEqual(sorted(self.changes()), sorted(
            ["secrets add-iam-policy-binding " + name for name in FULL_SECRETS + ("other-secret",)]))
        secrets = self.state()["projects"][STAGING]["secrets"]
        other = "serviceAccount:other-runtime@%s.iam.gserviceaccount.com" % STAGING
        for name in FULL_SECRETS:
            self.assertEqual(secrets[name]["policy"], {"roles/secretmanager.secretAccessor": ["serviceAccount:" + IDENTITY]})
        self.assertEqual(secrets["other-secret"]["policy"], {"roles/secretmanager.secretAccessor": [other]})
        self.assertNotIn("missing  secret", result.stdout)
        self.reset_calls()
        result = self.bootstrap(root)
        self.assertEqual(self.changes(), [])
        self.assertIn("staging: 0 changes.", result.stdout)

    def test_a_malformed_manifest_stops_it_before_any_call(self):
        root = self.make_root()
        self.add_service(root, "fixture", FULL)
        self.add_service(root, "broken", {"identity": {"name": "broken-runtime"}, "setting": {}})
        result = self.bootstrap(root)
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("services/broken/service.json does not fit the manifest format", result.stderr)
        self.assertEqual(self.calls(), [], "gcloud is never called")

    def test_two_services_may_not_share_an_identity(self):
        root = self.make_root()
        self.add_service(root, "fixture", FULL)
        self.add_service(root, "twin", {"identity": {"name": "fixture-runtime"}})
        result = self.bootstrap(root)
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("identity fixture-runtime is already services/fixture/service.json's", result.stderr)
        self.assertEqual(self.calls(), [])


# The repository's own manifests, and the code whose config they hold (C3).

SERVICE_CODE = {"runner": "services/runner/runner", "threads": "services/threads/threads"}
# Read without a default, but never from a manifest, each with where its value comes from instead.
SET_BY_DEPLOY = {"COMMIT_SHA": "deploy.sh sets it on every deploy (command-center/D47)"}
SET_PER_EXECUTION = {"runner": {"RUNNER_SESSION_ID": "runner/launcher.py passes it to each session's execution"}}
# Declared in a manifest and read by a library rather than by the service's own code.
READ_BY_LIBRARIES = {"runner": {"ANTHROPIC_API_KEY": "the Agent SDK, in a session's job (services/runner/README.md)"}}
# The variables each service's code or README documents as secrets.
DOCUMENTED_SECRETS = {
    "runner": {"RUNNER_APP_PRIVATE_KEY", "ANTHROPIC_API_KEY"},
    "threads": {"DATABASE_URL", "THREADS_GITHUB_APP_PRIVATE_KEY", "THREADS_GITHUB_WEBHOOK_SECRET"},
}
ENV_NAME = re.compile(r"^[A-Z][A-Z0-9_]*$")


def _real(node):
    """Whether a default written in the code is a value: not missing, None or the empty string."""
    if node is None:
        return False
    if isinstance(node, ast.Constant):
        return node.value not in (None, "")
    return True


def _environment(node):
    """`env` or `os.environ`, the two names the services read their environment through."""
    return (isinstance(node, ast.Name) and node.id == "env") or (
        isinstance(node, ast.Attribute) and node.attr == "environ"
        and isinstance(node.value, ast.Name) and node.value.id == "os")


class EnvReads:
    """The environment variables a service's code reads, and whether the code has a default for each.

    It reads the code, it does not run it. A variable is read by `env.get(...)`, `env.pop(...)` or `env[...]` (or
    through `os.environ`), with the name written out or in a module constant; or it is a key of a table in a config
    class that maps names to the fields they fill. It has a default when the read gives one (`env.get(X, "v")`,
    `env.get(X) or "v"`), or when the field it fills has a dataclass default that is not "" or None, or a method
    falls back from it (`self.field or ...`).
    """

    def __init__(self, sources):
        trees = [ast.parse(source) for source in sources]
        self.fields, self.fallbacks, self.mapped, self.direct = {}, set(), {}, {}
        for tree in trees:
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef) and any(
                        isinstance(item, ast.FunctionDef) and item.name == "from_env" for item in node.body):
                    self._config_class(node)
        for tree in trees:
            self._reads(tree)

    def _config_class(self, node):
        for item in node.body:
            if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                self.fields[item.target.id] = _real(item.value)
        for sub in ast.walk(node):
            if isinstance(sub, ast.BoolOp) and isinstance(sub.op, ast.Or):
                first = sub.values[0]
                if (isinstance(first, ast.Attribute) and isinstance(first.value, ast.Name)
                        and first.value.id == "self" and any(_real(v) for v in sub.values[1:])):
                    self.fallbacks.add(first.attr)

    def _reads(self, tree):
        consts = {}
        for node in tree.body:
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        consts[target.id] = node.value.value

        def name_of(node):
            if isinstance(node, getattr(ast, "Index", ())):  # Python 3.8 wraps a subscript
                node = node.value
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                return node.value
            if isinstance(node, ast.Name):
                return consts.get(node.id)
            return None

        def get_call(node):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and node.func.attr in ("get", "pop") and _environment(node.func.value) and node.args):
                name = name_of(node.args[0])
                return name if name and ENV_NAME.match(name) else None
            return None

        parents = {child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}
        for node in ast.walk(tree):
            name = get_call(node)
            if name:
                default = len(node.args) > 1 and _real(node.args[1])
                parent = parents.get(node)
                if isinstance(parent, ast.BoolOp) and isinstance(parent.op, ast.Or) and parent.values[0] is node:
                    default = default or any(_real(v) for v in parent.values[1:])
                self.direct.setdefault(name, []).append(default)
            elif isinstance(node, ast.Subscript) and _environment(node.value):
                name = name_of(node.slice)
                if name and ENV_NAME.match(name):
                    self.direct.setdefault(name, []).append(False)
            elif isinstance(node, ast.Dict):
                for key, value in zip(node.keys, node.values):
                    field = name_of(value.elts[0]) if isinstance(value, ast.Tuple) and value.elts else name_of(value)
                    name = name_of(key) if key is not None else None
                    if name and ENV_NAME.match(name) and field in self.fields:
                        self.mapped[name] = field
            elif isinstance(node, ast.If):
                guards = [get_call(n) for n in ast.walk(node.test)]
                fields = [name_of(target.slice) for stmt in node.body if isinstance(stmt, ast.Assign)
                          for target in stmt.targets if isinstance(target, ast.Subscript)]
                for name in filter(None, guards):
                    for field in fields:
                        if field in self.fields:
                            self.mapped[name] = field

    def variables(self):
        return set(self.direct) | set(self.mapped)

    def has_default(self, name):
        if name in self.mapped:
            field = self.mapped[name]
            return self.fields[field] or field in self.fallbacks
        return all(self.direct[name])

    def required(self):
        return {name for name in self.variables() if not self.has_default(name)}


def code_of(service):
    sources = []
    for path in sorted(glob.glob(os.path.join(ROOT, SERVICE_CODE[service], "*.py"))):
        with open(path) as f:
            sources.append(f.read())
    return EnvReads(sources)


def declared(m):
    """Every variable the manifest declares for the service itself, and for any of its jobs."""
    service = set(m.get("settings", {})) | set(m.get("secrets", {}))
    jobs = set()
    for job in m.get("jobs", {}).values():
        jobs |= set(job.get("settings", {})) | set(job.get("secrets", {}))
    return service, jobs


def not_declared(m, reads, service):
    """The variables the code requires without a default that the manifest does not declare for the service."""
    required = reads.required() - set(SET_BY_DEPLOY) - set(SET_PER_EXECUTION.get(service, {}))
    return sorted(required - declared(m)[0])


def load_manifest(service):
    return manifest.load(os.path.join(ROOT, "services", service, "service.json"))


class ManifestsMatchTheCodeTest(unittest.TestCase):
    """The runner's and threads' manifests declare every setting and secret their code requires without a default,
    and no secret's value (C3)."""

    def test_the_runner_and_threads_manifests_fit_the_format(self):
        for service in SERVICE_CODE:
            with self.subTest(service=service):
                self.assertEqual(manifest.problems(load_manifest(service)), [])

    def test_each_manifest_declares_every_variable_its_code_requires_without_a_default(self):
        for service in SERVICE_CODE:
            with self.subTest(service=service):
                self.assertEqual(not_declared(load_manifest(service), code_of(service), service), [],
                                 "services/%s/service.json must name these, in settings or secrets" % service)

    def test_each_manifest_names_only_variables_its_service_reads(self):
        for service in SERVICE_CODE:
            with self.subTest(service=service):
                read = code_of(service).variables() | set(READ_BY_LIBRARIES.get(service, {}))
                service_vars, job_vars = declared(load_manifest(service))
                self.assertEqual(sorted((service_vars | job_vars) - read), [],
                                 "no code reads these: a typo, or a variable the code no longer has")

    def test_no_manifest_holds_a_secrets_value(self):
        for service, secrets in DOCUMENTED_SECRETS.items():
            m = load_manifest(service)
            names = dict(m.get("secrets", {}))
            for job in m.get("jobs", {}).values():
                names.update(job.get("secrets", {}))
            for variable in secrets:
                with self.subTest(service=service, variable=variable):
                    self.assertIn(variable, names, "a secret is named in secrets, never set by value")
            for name, value in names.items():
                self.assertRegex(value, r"^[a-z0-9-]+$", "%s names a secret, it does not hold one" % name)

    def test_the_reader_sees_what_the_code_requires_and_what_it_defaults(self):
        # Without this, an empty reading would make the comparison above pass by finding nothing.
        runner, threads = code_of("runner"), code_of("threads")
        self.assertLessEqual({"RUNNER_APP_ID", "RUNNER_APP_SLUG", "RUNNER_GCP_PROJECT", "RUNNER_APP_PRIVATE_KEY"},
                             runner.required())
        self.assertLessEqual({"DATABASE_URL", "THREADS_PROJECTS", "THREADS_GITHUB_WEBHOOK_SECRET"}, threads.required())
        for name in ("RUNNER_CAP_PER_SPONSOR", "RUNNER_SKILL_MODELS", "RUNNER_STORE", "RUNNER_GIT_URL", "RUNNER_JOB"):
            self.assertIn(name, runner.variables())
            self.assertNotIn(name, runner.required(), "%s has a default in the runner's code" % name)
        for name in ("THREADS_CACHE_SECONDS", "THREADS_GITHUB_API_URL"):
            self.assertNotIn(name, threads.required())

    def test_a_new_required_variable_fails_until_the_manifest_names_it(self):
        config = (
            "import os\n"
            "from dataclasses import dataclass\n"
            "@dataclass\n"
            "class Config:\n"
            "    cap: int = 3\n"
            "    ceiling: float = 10.0\n"
            "    app_id: str = ''\n"
            "    new_thing: str = ''\n"
            "    @classmethod\n"
            "    def from_env(cls, env=None):\n"
            "        env = os.environ if env is None else env\n"
            "        plain = {'X_APP_ID': 'app_id', 'X_NEW_THING': 'new_thing'}\n"
            "        numbers = {'X_CAP': ('cap', int), 'X_CEILING': ('ceiling', float)}\n"
            "        values = {}\n"
            "        for name, key in plain.items():\n"
            "            if env.get(name):\n"
            "                values[key] = env[name]\n"
            "        return cls(**values)\n")
        reads = EnvReads([config])
        self.assertEqual(reads.required(), {"X_APP_ID", "X_NEW_THING"}, "a new variable with a default is not")
        m = {"identity": {"name": "x-runtime"}, "settings": {"X_APP_ID": "1"}}
        self.assertEqual(not_declared(m, reads, "x"), ["X_NEW_THING"])
        m["settings"]["X_NEW_THING"] = "named"
        self.assertEqual(not_declared(m, reads, "x"), [])

    def test_what_is_set_elsewhere_is_set_there(self):
        # COMMIT_SHA: DeployAppliesTheManifestTest checks that deploy.sh sets it.
        with open(os.path.join(ROOT, "services", "runner", "runner", "launcher.py")) as f:
            self.assertRegex(f.read(), r'containerOverrides.*"RUNNER_SESSION_ID"')
        with open(os.path.join(ROOT, "services", "runner", "requirements.txt")) as f:
            self.assertIn("claude-agent-sdk", f.read())

    def test_the_runners_job_is_the_one_the_runner_runs(self):
        m = load_manifest("runner")
        with open(os.path.join(ROOT, "services", "runner", "runner", "config.py")) as f:
            config = f.read()
        job_name = m.get("settings", {}).get("RUNNER_JOB") or re.search(r'^\s+job: str = "([^"]+)"', config, re.M).group(1)
        self.assertEqual(list(m["jobs"]), [job_name])
        job = m["jobs"][job_name]
        self.assertEqual(job["command"], ["python", "-m", "runner", "job"], "runner/__main__.py runs a session")
        # At most one task and no retries (services/runner/README.md): a retry could only spend twice.
        self.assertEqual((job["tasks"], job["max_retries"]), (1, 0))
        self.assertEqual(m["settings"]["RUNNER_GCP_PROJECT"], "{project}", "the job runs in the service's project")
        self.assertNotIn("ANTHROPIC_API_KEY", m.get("secrets", {}), "only the job holds the Anthropic key")

    def test_threads_trusts_the_runners_identity_at_its_own_url(self):
        runner, threads = load_manifest("runner"), load_manifest("threads")
        settings = threads["settings"]
        self.assertEqual(settings["THREADS_RUNNER_SERVICE_ACCOUNTS"],
                         "%s@{project}.iam.gserviceaccount.com" % runner["identity"]["name"])
        # Cloud Run's URL for it, as in LOOP.md §3 (command-center/D32).
        self.assertEqual(settings["THREADS_AUDIENCE"], "https://threads-{number}.{region}.run.app")


@unittest.skipUnless(shutil.which("git"), "needs git")
class RepositoryManifestsTest(GcpHarness):
    """The runner's and threads' own manifests, bootstrapped and deployed with the fakes (C1, C2)."""

    def make_repository_root(self, fill_todos):
        root = self.make_root()
        for service in SERVICE_CODE:
            with open(os.path.join(ROOT, "services", service, "service.json")) as f:
                text = f.read()
            if fill_todos:
                text = text.replace("TODO(owner)", "12345")
            write(root, "services/%s/service.json" % service, text)
            write(root, "services/%s/Dockerfile" % service, "FROM scratch\n")
        return root

    def secrets(self):
        names = set()
        for service in SERVICE_CODE:
            m = load_manifest(service)
            names |= set(m.get("secrets", {}).values())
            for job in m.get("jobs", {}).values():
                names |= set(job.get("secrets", {}).values())
        return sorted(names)

    def test_their_bootstrap_creates_each_identity_and_a_second_run_changes_nothing(self):
        root = self.make_repository_root(fill_todos=False)
        result = self.bootstrap(root)
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        project = self.state()["projects"][STAGING]
        for name in ("runner", "threads", "probe-runtime"):
            self.assertIn("%s@%s.iam.gserviceaccount.com" % (name, STAGING), project["accounts"])
        for name in self.secrets():
            self.assertIn("missing  secret " + name, result.stdout)
        for name in self.secrets():
            self.add_secret(name)
        self.assertEqual(self.bootstrap(root).returncode, 0)
        self.reset_calls()
        result = self.bootstrap(root)
        self.assertEqual(self.changes(), [])
        self.assertIn("staging: 0 changes.", result.stdout)

    def test_staging_names_their_github_apps_and_production_waits_for_its_own(self):
        # The owner named staging's apps (deploy.md step 11); production's belong to a later loop (command-center/D54),
        # so a production deploy is refused until they are named too. The refusal itself is tested above.
        wanted = {"runner": ["settings.RUNNER_APP_ID", "settings.RUNNER_APP_INSTALLATION_ID", "settings.RUNNER_APP_SLUG"],
                  "threads": ["settings.THREADS_GITHUB_APP_ID"], "status": ["settings.STATUS_GITHUB_APP_ID"]}
        for service, settings in wanted.items():
            m = manifest.load(os.path.join(ROOT, "services", service, "service.json"))
            self.assertEqual(manifest.todos(m, "staging"), [], service)
            self.assertEqual(manifest.todos(m, "production"), settings, service)

    def test_once_named_they_deploy_with_their_manifests(self):
        self.root = self.make_repository_root(fill_todos=True)
        self.assertEqual(self.bootstrap(self.root).returncode, 0)
        for name in self.secrets():
            self.add_secret(name)
        self.assertEqual(self.bootstrap(self.root).returncode, 0)
        sha = self.init_repo()
        for service in SERVICE_CODE:
            result = self.deploy(service, sha)
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        project = self.state()["projects"][STAGING]
        number = project["number"]
        runner, threads, job = project["run"]["runner"], project["run"]["threads"], project["jobs"]["runner-session"]
        self.assertEqual(runner["identity"], "runner@%s.iam.gserviceaccount.com" % STAGING)
        self.assertEqual(runner["env"]["RUNNER_GCP_PROJECT"], STAGING)
        self.assertEqual(runner["env"]["COMMIT_SHA"], sha)
        self.assertNotIn("ANTHROPIC_API_KEY", runner["secrets"])
        self.assertEqual(job["identity"], runner["identity"])
        self.assertIn("ANTHROPIC_API_KEY", job["secrets"])
        self.assertIn("RUNNER_APP_PRIVATE_KEY", job["secrets"])
        self.assertEqual((job["command"], job["args"], job["max_retries"]), (["python"], ["-m", "runner", "job"], "0"))
        self.assertEqual(threads["identity"], "threads@%s.iam.gserviceaccount.com" % STAGING)
        self.assertEqual(threads["cloudsql"], ["%s:us-east1:threads" % STAGING])
        self.assertEqual(threads["env"]["THREADS_AUDIENCE"], "https://threads-%s.us-east1.run.app" % number)
        self.assertEqual(threads["env"]["THREADS_RUNNER_SERVICE_ACCOUNTS"], runner["identity"])
        self.assertEqual(sorted(threads["secrets"]),
                         ["DATABASE_URL", "THREADS_GITHUB_APP_PRIVATE_KEY", "THREADS_GITHUB_WEBHOOK_SECRET"])


if __name__ == "__main__":
    unittest.main()
