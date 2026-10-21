"""Tests for the repository layout: what an install ships, what the skills may refer to, and how the environments
are created and deployed to.

The skills and the command center share this repository (command-center/D13). Installing the plugin must still
ship only the skills (D16), and nothing under plugin/ may read, call or assume the app, the services or their
hosts, so a loop always runs from a terminal alone (D14).

The scripts in scripts/gcp/ create the environments and deploy to them (command-center/environments). The owner
runs them against GCP; these tests run them against fake gcloud, docker and curl executables placed first on
PATH, which keep a small model of the cloud and record every call, so a test can see what a first and a second
run would change. Git is real: a temporary repository with its own origin.

Run from the repository root: python3 -m unittest discover -s tests -v
"""

import fcntl
import json
import os
import re
import sys

# The fakes. Each shim in a test's bin directory runs this file as `test_layout.py fake <tool> <args>`. The model of
# the cloud lives in $FAKE_STATE/state.json, and every call is appended to $FAKE_STATE/calls.jsonl.

STAGING = "al-test-staging"
PRODUCTION = "al-test-production"
BILLING = "0A0A0A-0B0B0B-0C0C0C"
SERVICES = ("status", "runner", "threads", "notify")
# A gcloud call is a change when one of these is among its positional arguments. Everything else only reads.
GCLOUD_CHANGES = {"create", "link", "enable", "add-iam-policy-binding", "remove-iam-policy-binding",
                  "set-iam-policy", "update", "deploy", "delete"}


def positional(argv):
    return [a for a in argv if not a.startswith("-")]


def parse_flags(argv):
    flags = {}
    for a in argv:
        if a.startswith("--"):
            key, eq, value = a[2:].partition("=")
            flags.setdefault(key, []).append(value if eq else True)
    return flags


def fake(tool, argv):
    state_dir = os.environ["FAKE_STATE"]
    with open(os.path.join(state_dir, "lock"), "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        with open(os.path.join(state_dir, "state.json")) as f:
            state = json.load(f)
        entry = {"tool": tool, "argv": argv}
        code = {"gcloud": fake_gcloud, "docker": fake_docker, "curl": fake_curl}[tool](state, argv, entry)
        with open(os.path.join(state_dir, "state.json"), "w") as f:
            json.dump(state, f, indent=1, sort_keys=True)
        with open(os.path.join(state_dir, "calls.jsonl"), "a") as f:
            f.write(json.dumps(entry) + "\n")
    return code


def fake_gcloud(state, argv, entry):
    pos, flags = positional(argv), parse_flags(argv)

    def one(key):
        return flags.get(key, [None])[0]

    def fail(message, code=1):
        sys.stderr.write("ERROR: (gcloud) %s\n" % message)
        return code

    def say(*lines):
        for line in lines:
            sys.stdout.write(line + "\n")
        return 0

    projects = state["projects"]
    project = projects.get(one("project")) or next((projects[a] for a in pos[2:] if a in projects), None)
    if pos == ["config", "get-value", "account"]:
        return say(state["account"])
    if pos[:2] == ["auth", "print-access-token"]:
        return say("fake-access-token") if one("impersonate-service-account") else fail("no impersonation")
    if pos[:2] == ["projects", "create"]:
        if pos[2] in projects:
            return fail("The project ID you specified is already in use by another project.")
        projects[pos[2]] = {"number": str(100000000001 + len(projects)), "name": one("name"), "billing": "",
                            "services": [], "repos": {}, "accounts": {}, "policy": {}, "run": {}}
        return 0
    if pos[:3] == ["billing", "budgets", "list"]:
        return say(*["\t".join([b["displayName"], b["name"], b["units"], b["currency"]])
                     for b in state["budgets"] if b["account"] == one("billing-account")])
    if pos[:3] == ["billing", "budgets", "create"] or pos[:3] == ["billing", "budgets", "update"]:
        amount = re.fullmatch(r"(\d+)([A-Z]{3})?", one("budget-amount") or "")
        if not amount:
            return fail("bad --budget-amount")
        if pos[2] == "create":
            budget = {"account": one("billing-account"), "name": "billingAccounts/%s/budgets/b%d" % (
                one("billing-account"), len(state["budgets"]) + 1), "displayName": one("display-name"),
                "period": one("calendar-period"), "thresholds": flags.get("threshold-rule", []),
                "projects": flags.get("filter-projects", [])}
            state["budgets"].append(budget)
        else:
            [budget] = [b for b in state["budgets"] if b["name"] == pos[3]]
        budget["units"], budget["currency"] = amount.group(1), amount.group(2) or state["currency"]
        return 0
    if project is None:
        return fail("NOT_FOUND: project %s" % (one("project") or pos[2:3]))
    if pos[:2] == ["projects", "describe"]:
        return say(project["number"])
    if pos[:2] == ["projects", "get-iam-policy"]:
        member = one("filter").split(":", 1)[1]
        return say(*[role for role, members in sorted(project["policy"].items()) if member in members])
    if pos[:2] == ["projects", "add-iam-policy-binding"]:
        members = project["policy"].setdefault(one("role"), [])
        members += [one("member")] if one("member") not in members else []
        return 0
    if pos[:3] == ["billing", "projects", "describe"]:
        return say(project["billing"])
    if pos[:3] == ["billing", "projects", "link"]:
        project["billing"] = "billingAccounts/" + one("billing-account")
        return 0
    if pos[:2] == ["services", "list"] and one("enabled"):
        return say(*project["services"])
    if pos[:2] == ["services", "enable"]:
        project["services"] += [api for api in pos[2:] if api not in project["services"]]
        return 0
    if pos[:2] == ["artifacts", "repositories"]:
        key = "%s/%s" % (one("location"), pos[3])
        if pos[2] == "describe":
            return say(key) if key in project["repos"] else fail("NOT_FOUND: repository %s" % key)
        if pos[2] == "create" and key not in project["repos"]:
            project["repos"][key] = one("repository-format")
            return 0
    if pos[:2] == ["iam", "service-accounts"]:
        if pos[2] == "create":
            email = "%s@%s.iam.gserviceaccount.com" % (pos[3], one("project"))
            if email in project["accounts"]:
                return fail("already exists")
            project["accounts"][email] = {}
            return 0
        if pos[3] not in project["accounts"]:
            return fail("NOT_FOUND: service account %s" % pos[3])
        policy = project["accounts"][pos[3]]
        if pos[2] == "describe":
            return say(pos[3])
        if pos[2] == "get-iam-policy":
            return say(*policy.get(one("filter").split(":", 1)[1], []))
        if pos[2] == "add-iam-policy-binding":
            members = policy.setdefault(one("role"), [])
            members += [one("member")] if one("member") not in members else []
            return 0
    if pos[:2] == ["run", "deploy"]:
        service = project["run"].setdefault(pos[2], {"env": {}})
        service.update(image=one("image"), region=one("region"), public=bool(one("allow-unauthenticated")),
                       deployed_as=one("impersonate-service-account"))
        for pair in (one("update-env-vars") or "").split(","):
            if pair:
                key, _, value = pair.partition("=")
                service["env"][key] = value
        return 0
    if pos[:3] == ["run", "services", "describe"]:
        if pos[3] not in project["run"]:
            return fail("NOT_FOUND: service %s" % pos[3])
        return say("https://%s-%s.%s.run.app" % (pos[3], project["number"], one("region")))
    return fail("the fake gcloud does not model: %s" % " ".join(argv), 2)


def fake_docker(state, argv, entry):
    pos, flags = positional(argv), parse_flags(argv)
    if pos[:1] == ["build"]:
        with open(flags["file"][0]) as f:
            entry["dockerfile"] = f.read()
        entry["context"] = pos[1]
    elif pos[:1] == ["login"]:
        entry["password_given"] = bool(sys.stdin.read().strip())
    return 0


def fake_curl(state, argv, entry):
    url = [a for a in argv if a.startswith("http")][0]
    status, body = state["http"].get(url, (404, ""))
    match = re.fullmatch(r"https://([a-z0-9-]+)-(\d+)\.([a-z0-9-]+)\.run\.app/version", url)
    if url not in state["http"] and match:
        for project in state["projects"].values():
            service = project["run"].get(match.group(1))
            if project["number"] == match.group(2) and service and service["region"] == match.group(3):
                # The deployed probe answers the commit it was given, as scripts/gcp/probe/server.py does.
                status, body = 200, json.dumps({"commit": service["env"].get("COMMIT_SHA")})
    if status != 200:
        sys.stderr.write("curl: (22) The requested URL returned error: %d\n" % status)
        return 22
    sys.stdout.write(body)
    return 0


if __name__ == "__main__" and sys.argv[1:2] == ["fake"]:
    sys.exit(fake(sys.argv[2], sys.argv[3:]))

# The tests' own imports come after the fakes, so that each fake call starts in a few milliseconds.
import shutil  # noqa: E402
import subprocess  # noqa: E402
import tempfile  # noqa: E402
import time  # noqa: E402
import unittest  # noqa: E402
import urllib.error  # noqa: E402
import urllib.request  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLUGIN = os.path.join(ROOT, "plugin")
CHECK = os.path.join(ROOT, "scripts", "check.sh")
INSTALL = os.path.join(ROOT, "scripts", "install.sh")
GCP = os.path.join(ROOT, "scripts", "gcp")
IGNORED = {".DS_Store"}


def listdir(path):
    return sorted(name for name in os.listdir(path) if name not in IGNORED)


def write(root, rel, text):
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(text)


class PluginLayoutTest(unittest.TestCase):
    def test_marketplace_installs_the_plugin_folder(self):
        with open(os.path.join(ROOT, ".claude-plugin", "marketplace.json")) as f:
            market = json.load(f)
        self.assertEqual([p["source"] for p in market["plugins"]], ["./plugin"])
        self.assertFalse(os.path.exists(os.path.join(ROOT, ".claude-plugin", "plugin.json")),
                         "a root plugin.json would make the whole repository a plugin")

    def test_plugin_folder_holds_only_the_manifest_and_skills(self):
        self.assertEqual(listdir(PLUGIN), [".claude-plugin", "skills"])
        self.assertEqual(listdir(os.path.join(PLUGIN, ".claude-plugin")), ["plugin.json"])
        with open(os.path.join(PLUGIN, ".claude-plugin", "plugin.json")) as f:
            self.assertEqual(json.load(f)["name"], "architect-loop")

    def test_every_skill_is_a_loop_skill(self):
        skills = listdir(os.path.join(PLUGIN, "skills"))
        self.assertTrue(skills)
        for name in skills:
            self.assertTrue(name.startswith("loop-"), name)
            self.assertTrue(os.path.isfile(os.path.join(PLUGIN, "skills", name, "SKILL.md")), name)


@unittest.skipUnless(shutil.which("sh"), "needs sh")
class InstallTest(unittest.TestCase):
    def test_install_copies_exactly_the_skills(self):
        dest = tempfile.mkdtemp(prefix="install-")
        self.addCleanup(shutil.rmtree, dest)
        subprocess.run(["sh", INSTALL, "--dest", dest], check=True, capture_output=True, text=True)
        self.assertEqual(listdir(dest), listdir(os.path.join(PLUGIN, "skills")))


@unittest.skipUnless(shutil.which("sh"), "needs sh")
class IndependenceCheckTest(unittest.TestCase):
    """scripts/check.sh fails when a skill refers to the app or the services (D14)."""

    SKILL = "---\nname: loop-x\ndescription: A test skill.\n---\n# loop-x\n\n{body}\n"

    def run_check(self, body):
        root = tempfile.mkdtemp(prefix="check-")
        self.addCleanup(shutil.rmtree, root)
        os.makedirs(os.path.join(root, "scripts"))
        shutil.copy(CHECK, os.path.join(root, "scripts", "check.sh"))
        write(root, "plugin/skills/loop-x/SKILL.md", self.SKILL.format(body=body))
        return subprocess.run(["sh", os.path.join(root, "scripts", "check.sh")], capture_output=True, text=True)

    def test_a_clean_skill_passes(self):
        result = self.run_check("Read `docs/loops/` and the web-app/ folder named in touches.")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("ok   independence", result.stdout)

    def test_a_reference_to_the_app_fails(self):
        result = self.run_check("Then open app/src/features/inbox/ to show the card.")
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("FAIL independence", result.stdout)
        self.assertIn("plugin/skills/loop-x/SKILL.md", result.stdout)

    def test_a_reference_to_the_services_fails(self):
        result = self.run_check("Post the verdict to ../services/status/ when it runs.")
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("FAIL independence", result.stdout)

    def test_a_service_host_fails(self):
        # The services run on Cloud Run in us-east1 (D32), at https://<service>-<project number>.us-east1.run.app.
        result = self.run_check("Read the served commit from https://status-123456789012.us-east1.run.app/version.")
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("FAIL independence", result.stdout)
        self.assertIn("status-123456789012.us-east1.run.app", result.stdout)

    def test_a_hash_style_service_host_fails(self):
        # Cloud Run also gives every service a hash-style URL under run.app.
        result = self.run_check("Dispatch it with POST https://runner-x7k2q4abcd-ue.a.run.app/sessions.")
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("FAIL independence", result.stdout)

    def test_a_host_outside_the_services_passes(self):
        result = self.run_check("Read each served commit with the command in LOOP.md, e.g. GET https://staging.example.com/version.")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("ok   independence", result.stdout)

    def test_the_repository_itself_passes(self):
        result = subprocess.run(["sh", CHECK], capture_output=True, text=True, env={**os.environ, "CHECK_SKIP_TESTS": "1"})
        self.assertIn("ok   independence", result.stdout)
        self.assertEqual(result.returncode, 0, result.stdout)


@unittest.skipUnless(shutil.which("sh"), "needs sh")
class GcpHarness(unittest.TestCase):
    """A copy of scripts/gcp/ in a temporary root, with fake gcloud, docker and curl first on PATH."""

    def make_root(self, projects=None):
        root = tempfile.mkdtemp(prefix="gcp-root-")
        self.addCleanup(shutil.rmtree, root)
        shutil.copytree(GCP, os.path.join(root, "scripts", "gcp"),
                        ignore=shutil.ignore_patterns("__pycache__", *IGNORED))
        projects = {"staging": STAGING, "production": PRODUCTION} if projects is None else projects
        write(root, "scripts/gcp/projects.txt", "# test projects\n" + "".join(
            "%s %s\n" % pair for pair in projects.items()))
        self.fake_dir = tempfile.mkdtemp(prefix="gcp-fake-")
        self.addCleanup(shutil.rmtree, self.fake_dir)
        bindir = os.path.join(self.fake_dir, "bin")
        os.makedirs(bindir)
        for tool in ("gcloud", "docker", "curl"):
            path = os.path.join(bindir, tool)
            with open(path, "w") as f:
                f.write('#!/bin/sh\nexec "%s" -S "%s" fake %s "$@"\n' % (sys.executable, os.path.abspath(__file__), tool))
            os.chmod(path, 0o755)
        with open(os.path.join(self.fake_dir, "state.json"), "w") as f:
            json.dump({"account": "owner@example.com", "currency": "USD", "projects": {}, "budgets": [],
                       "http": {}}, f)
        gitconfig = os.path.join(self.fake_dir, "gitconfig")
        open(gitconfig, "w").close()
        self.env = {**os.environ, "PATH": bindir + os.pathsep + os.environ["PATH"], "FAKE_STATE": self.fake_dir,
                    "GIT_CONFIG_GLOBAL": gitconfig, "GIT_CONFIG_NOSYSTEM": "1",
                    "GIT_AUTHOR_NAME": "Test", "GIT_AUTHOR_EMAIL": "test@example.com",
                    "GIT_COMMITTER_NAME": "Test", "GIT_COMMITTER_EMAIL": "test@example.com"}
        return root

    def run_script(self, root, name, *args):
        return subprocess.run(["sh", os.path.join(root, "scripts", "gcp", name), *args], capture_output=True,
                              text=True, env=self.env, cwd=root, timeout=120)

    def bootstrap(self, root, env="staging", budget="25USD", billing=BILLING):
        return self.run_script(root, "bootstrap.sh", env, "--billing-account=" + billing, "--budget=" + budget)

    def state(self):
        with open(os.path.join(self.fake_dir, "state.json")) as f:
            return json.load(f)

    def set_state(self, state):
        with open(os.path.join(self.fake_dir, "state.json"), "w") as f:
            json.dump(state, f)

    def calls(self, tool=None):
        path = os.path.join(self.fake_dir, "calls.jsonl")
        if not os.path.exists(path):
            return []
        with open(path) as f:
            return [c for c in map(json.loads, f) if tool in (None, c["tool"])]

    def changes(self):
        """Every call that changes something: each gcloud call with a changing verb, and every docker call."""
        return [" ".join(positional(c["argv"])) for c in self.calls()
                if c["tool"] == "docker" or (c["tool"] == "gcloud" and GCLOUD_CHANGES & set(positional(c["argv"])))]

    def reset_calls(self):
        path = os.path.join(self.fake_dir, "calls.jsonl")
        if os.path.exists(path):
            os.remove(path)


class BootstrapTest(GcpHarness):
    """bootstrap.sh creates an environment's project and what it needs, and a second run changes nothing (C1)."""

    ACCOUNT = "deploy@%s.iam.gserviceaccount.com" % STAGING

    def test_a_first_run_creates_the_environment(self):
        root = self.make_root()
        result = self.bootstrap(root)
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertEqual(self.changes(), [
            "projects create " + STAGING,
            "billing projects link " + STAGING,
            "services enable run.googleapis.com artifactregistry.googleapis.com secretmanager.googleapis.com "
            "iamcredentials.googleapis.com billingbudgets.googleapis.com",
            "artifacts repositories create services",
            "iam service-accounts create deploy",
            "projects add-iam-policy-binding " + STAGING,
            "projects add-iam-policy-binding " + STAGING,
            "projects add-iam-policy-binding " + STAGING,
            "iam service-accounts add-iam-policy-binding " + self.ACCOUNT,
            "billing budgets create",
        ])
        state = self.state()
        project = state["projects"][STAGING]
        self.assertEqual(project["billing"], "billingAccounts/" + BILLING)
        self.assertEqual(project["repos"], {"us-east1/services": "docker"})
        self.assertEqual(sorted(role for role, members in project["policy"].items()
                                if "serviceAccount:" + self.ACCOUNT in members),
                         ["roles/artifactregistry.writer", "roles/iam.serviceAccountUser", "roles/run.admin"])
        self.assertEqual(project["accounts"][self.ACCOUNT],
                         {"roles/iam.serviceAccountTokenCreator": ["user:owner@example.com"]})
        [budget] = state["budgets"]
        self.assertEqual((budget["account"], budget["units"], budget["currency"], budget["period"]),
                         (BILLING, "25", "USD", "month"))
        self.assertEqual(budget["thresholds"], ["percent=0.5", "percent=0.9", "percent=1.0"])
        self.assertEqual(budget["projects"], ["projects/" + STAGING])
        self.assertIn("10 changes", result.stdout)
        for service in SERVICES:
            self.assertIn("https://%s-%s.us-east1.run.app/version" % (service, project["number"]), result.stdout)

    def test_a_second_run_changes_nothing(self):
        root = self.make_root()
        self.assertEqual(self.bootstrap(root).returncode, 0)
        before = self.state()
        self.reset_calls()
        result = self.bootstrap(root)
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertTrue(self.calls("gcloud"), "a second run must read the environment again, not skip it")
        self.assertEqual(self.changes(), [])
        self.assertEqual(self.state(), before)
        self.assertIn("0 changes", result.stdout)

    def test_each_environment_is_its_own_project(self):
        root = self.make_root()
        self.assertEqual(self.bootstrap(root, "staging").returncode, 0)
        result = self.bootstrap(root, "production")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        state = self.state()
        self.assertEqual(sorted(state["projects"]), [PRODUCTION, STAGING])
        self.assertEqual(sorted(b["projects"][0] for b in state["budgets"]),
                         ["projects/" + PRODUCTION, "projects/" + STAGING])

    def test_a_new_budget_amount_changes_only_the_budget(self):
        root = self.make_root()
        self.assertEqual(self.bootstrap(root).returncode, 0)
        self.reset_calls()
        result = self.bootstrap(root, budget="40USD")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        [budget] = self.state()["budgets"]
        self.assertEqual(self.changes(), ["billing budgets update " + budget["name"]])
        self.assertEqual(budget["units"], "40")

    def test_it_will_not_relink_billing_to_another_account(self):
        root = self.make_root()
        self.assertEqual(self.bootstrap(root, billing="0D0D0D-0E0E0E-0F0F0F").returncode, 0)
        self.reset_calls()
        result = self.bootstrap(root)
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("not changing it", result.stderr)
        self.assertEqual(self.changes(), [])
        self.assertEqual(self.state()["projects"][STAGING]["billing"], "billingAccounts/0D0D0D-0E0E0E-0F0F0F")

    def test_it_refuses_an_environment_whose_project_is_not_named(self):
        root = self.make_root({"staging": STAGING, "production": "TODO(owner)"})
        result = self.bootstrap(root, "production")
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("TODO(owner)", result.stderr)
        self.assertIn("scripts/gcp/projects.txt", result.stderr)
        self.assertEqual(self.calls(), [])

    def test_it_refuses_to_run_without_a_budget(self):
        root = self.make_root()
        result = self.run_script(root, "bootstrap.sh", "staging", "--billing-account=" + BILLING)
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertIn("--budget", result.stderr)
        self.assertEqual(self.calls(), [])

    def test_it_refuses_an_unknown_environment(self):
        root = self.make_root()
        result = self.bootstrap(root, "prod")
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("staging or production", result.stderr)
        self.assertEqual(self.calls(), [])


@unittest.skipUnless(shutil.which("git"), "needs git")
class DeployTest(GcpHarness):
    """deploy.sh builds a commit on origin/main and deploys it, and refuses any other commit (C2)."""

    bootstrapped = None

    def setUp(self):
        if DeployTest.bootstrapped is None:
            # Bootstrap once (BootstrapTest covers it), then start each test from the cloud it left.
            self.assertEqual(self.bootstrap(self.make_root()).returncode, 0)
            DeployTest.bootstrapped = self.state()
        self.root = self.make_root()
        self.set_state(DeployTest.bootstrapped)
        write(self.root, "services/status/Dockerfile", "FROM scratch\n")
        self.git("init", "-q", "-b", "main")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "First commit")
        origin = tempfile.mkdtemp(prefix="gcp-origin-")
        self.addCleanup(shutil.rmtree, origin)
        subprocess.run(["git", "init", "-q", "--bare", origin], check=True, env=self.env)
        self.git("remote", "add", "origin", origin)
        self.git("push", "-q", "origin", "main")
        self.main = self.git("rev-parse", "HEAD")
        self.number = self.state()["projects"][STAGING]["number"]

    def git(self, *args):
        return subprocess.run(["git", "-C", self.root, *args], check=True, capture_output=True, text=True,
                              env=self.env).stdout.strip()

    def commit(self, message):
        write(self.root, "notes/%s.txt" % message.replace(" ", "-"), message + "\n")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", message)
        return self.git("rev-parse", "HEAD")

    def deploy(self, service, sha, env="staging"):
        return self.run_script(self.root, "deploy.sh", service, env, sha)

    def test_it_deploys_a_commit_on_main_and_reads_it_back(self):
        result = self.deploy("probe", self.main[:7])
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        image = "us-east1-docker.pkg.dev/%s/services/probe:%s" % (STAGING, self.main)
        build, login, push = self.calls("docker")
        self.assertEqual(positional(build["argv"])[0], "build")
        flags = parse_flags(build["argv"])
        self.assertEqual(flags["platform"], ["linux/amd64"])
        self.assertEqual(flags["tag"], [image])
        # The repository root is the context, and the Dockerfile is the one in the commit (D32).
        self.assertEqual(flags["file"], [os.path.join(build["context"], "scripts/gcp/probe/Dockerfile")])
        with open(os.path.join(GCP, "probe", "Dockerfile")) as f:
            self.assertEqual(build["dockerfile"], f.read())
        self.assertEqual(positional(login["argv"]), ["login", "us-east1-docker.pkg.dev"])
        self.assertTrue(login["password_given"])
        self.assertEqual(positional(push["argv"]), ["push", image])
        service = self.state()["projects"][STAGING]["run"]["probe"]
        self.assertEqual(service["image"], image)
        self.assertEqual(service["region"], "us-east1")
        self.assertEqual(service["env"], {"COMMIT_SHA": self.main})
        self.assertTrue(service["public"], "/version must answer without credentials (D32)")
        self.assertEqual(service["deployed_as"], "deploy@%s.iam.gserviceaccount.com" % STAGING)
        url = "https://probe-%s.us-east1.run.app/version" % self.number
        self.assertIn(url, result.stdout)
        self.assertIn(self.main, result.stdout)
        self.assertEqual(self.calls("curl")[-1]["argv"][-1], url)

    def test_it_refuses_a_commit_that_is_only_on_a_branch(self):
        self.git("switch", "-q", "-c", "feature")
        sha = self.commit("on a branch")
        self.git("push", "-q", "origin", "feature")
        result = self.deploy("probe", sha)
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("not on origin/main", result.stderr)
        self.assertEqual(self.calls(), [], "nothing is built or deployed")

    def test_it_refuses_a_commit_on_local_main_that_was_never_pushed(self):
        sha = self.commit("not pushed")
        result = self.deploy("probe", sha)
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("not on origin/main", result.stderr)
        self.assertEqual(self.calls(), [])

    def test_it_refuses_a_sha_that_is_not_a_commit(self):
        result = self.deploy("probe", "0123456789abcdef0123456789abcdef01234567")
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("not a commit", result.stderr)
        self.assertEqual(self.calls(), [])

    def test_it_builds_the_commit_not_the_working_tree(self):
        with open(os.path.join(self.root, "scripts", "gcp", "probe", "Dockerfile"), "a") as f:
            f.write("RUN echo uncommitted\n")
        result = self.deploy("probe", self.main)
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        [build] = [c for c in self.calls("docker") if positional(c["argv"])[0] == "build"]
        self.assertNotIn("uncommitted", build["dockerfile"])

    def test_a_service_builds_from_its_own_folder_with_the_root_as_context(self):
        result = self.deploy("status", self.main)
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        [build] = [c for c in self.calls("docker") if positional(c["argv"])[0] == "build"]
        self.assertEqual(parse_flags(build["argv"])["file"],
                         [os.path.join(build["context"], "services/status/Dockerfile")])
        self.assertIn("https://status-%s.us-east1.run.app/version" % self.number, result.stdout)

    def test_it_refuses_a_service_with_no_dockerfile_in_the_commit(self):
        result = self.deploy("runner", self.main)
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("services/runner/Dockerfile", result.stderr)
        self.assertEqual(self.calls(), [])

    def test_it_fails_when_version_does_not_answer_the_commit(self):
        state = self.state()
        state["http"]["https://probe-%s.us-east1.run.app/version" % self.number] = [200, '{"commit": "1234567"}']
        self.set_state(state)
        result = self.deploy("probe", self.main)
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("1234567", result.stderr)

    def test_the_probe_answers_the_commit_that_deploy_gives_it(self):
        self.assertEqual(self.deploy("probe", self.main).returncode, 0)
        env = self.state()["projects"][STAGING]["run"]["probe"]["env"]
        with Probe(env) as probe:
            self.assertEqual(probe.get("/version"), (200, {"commit": self.main}))


class ServedTest(GcpHarness):
    """served.sh prints the commit a /version URL answers, which is what a LOOP.md §3 row runs (C3)."""

    URL = "https://status-100000000001.us-east1.run.app/version"
    SHA = "0f1e2d3c4b5a69788796a5b4c3d2e1f00f1e2d3c"

    def answer(self, status, body):
        self.root = self.make_root()
        state = self.state()
        state["http"][self.URL] = [status, body]
        self.set_state(state)

    def test_it_prints_the_served_commit(self):
        self.answer(200, json.dumps({"commit": self.SHA}))
        result = self.run_script(self.root, "served.sh", self.URL)
        self.assertEqual((result.returncode, result.stdout), (0, self.SHA + "\n"), result.stderr)

    def test_it_checks_an_expected_commit(self):
        self.answer(200, json.dumps({"commit": self.SHA}))
        self.assertEqual(self.run_script(self.root, "served.sh", self.URL, self.SHA[:7]).returncode, 0)
        result = self.run_script(self.root, "served.sh", self.URL, "abcdef0")
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("abcdef0", result.stderr)

    def test_a_service_not_deployed_is_unknown(self):
        self.answer(404, "")
        result = self.run_script(self.root, "served.sh", self.URL)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertIn(self.URL, result.stderr)

    def test_an_answer_without_a_commit_is_unknown(self):
        self.answer(200, "<html>Service Unavailable</html>")
        result = self.run_script(self.root, "served.sh", self.URL)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")


class Probe:
    """scripts/gcp/probe/server.py, run on a free local port with the given environment."""

    def __init__(self, env):
        import socket
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            self.port = s.getsockname()[1]
        self.env = {"PATH": os.environ["PATH"], "PORT": str(self.port), **env}

    def __enter__(self):
        self.process = subprocess.Popen([sys.executable, os.path.join(GCP, "probe", "server.py")], env=self.env,
                                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        deadline = time.time() + 10
        while time.time() < deadline:
            try:
                self.get("/version")
                return self
            except OSError:
                time.sleep(0.05)
        self.__exit__()
        raise RuntimeError("the probe did not start")

    def __exit__(self, *exc):
        self.process.terminate()
        self.process.wait(timeout=10)

    def get(self, path):
        try:
            with urllib.request.urlopen("http://127.0.0.1:%d%s" % (self.port, path), timeout=5) as r:
                return r.status, json.load(r)
        except urllib.error.HTTPError as e:
            return e.code, json.load(e)


class ProbeTest(unittest.TestCase):
    """The probe follows the convention every service follows: $PORT and GET /version (D32)."""

    def test_version_answers_the_commit(self):
        with Probe({"COMMIT_SHA": "0f1e2d3c4b5a69788796a5b4c3d2e1f00f1e2d3c"}) as probe:
            self.assertEqual(probe.get("/version"), (200, {"commit": "0f1e2d3c4b5a69788796a5b4c3d2e1f00f1e2d3c"}))
            self.assertEqual(probe.get("/version?fresh=1")[0], 200)
            self.assertEqual(probe.get("/")[0], 404)

    def test_without_a_commit_it_answers_unavailable_rather_than_guess(self):
        with Probe({}) as probe:
            status, body = probe.get("/version")
            self.assertEqual(status, 503)
            self.assertNotIn("commit", body)


class LoopContractTest(unittest.TestCase):
    """LOOP.md §3 has a row for each service in each environment, and §4 the commands (C3)."""

    def section(self, number):
        with open(os.path.join(ROOT, "LOOP.md")) as f:
            text = f.read()
        return re.search(r"^## %d\. .*?(?=^## )" % number, text, re.S | re.M).group(0)

    def rows(self, number):
        rows = {}
        for line in self.section(number).splitlines():
            cells = [c.strip() for c in re.split(r"(?<!\\)\|", line.strip())[1:-1]]
            if cells and not set(cells[0]) <= set("-: "):
                rows[cells[0].strip("`")] = cells
        return rows

    def test_every_service_has_a_row_in_each_environment(self):
        with open(os.path.join(GCP, "common.sh")) as f:
            services = re.search(r'^SERVICES="([^"]*)"', f.read(), re.M).group(1).split()
        self.assertEqual(services, list(SERVICES))
        rows = self.rows(3)
        for env in ("staging", "production"):
            for service in services:
                row = rows.get("%s/%s" % (env, service))
                self.assertIsNotNone(row, "no LOOP.md §3 row for %s/%s" % (env, service))
                self.assertIn("scripts/gcp/served.sh", row[5])
                self.assertIn("sh scripts/gcp/deploy.sh %s %s" % (service, env), row[4])

    def test_section_4_has_the_bootstrap_deploy_and_verify_commands(self):
        rows = self.rows(4)
        self.assertIn("sh scripts/gcp/bootstrap.sh", rows["Bootstrap an environment"][1])
        self.assertIn("sh scripts/gcp/deploy.sh", rows["Deploy"][1])
        self.assertIn("sh scripts/gcp/served.sh", rows["Verify a deploy"][1])


if __name__ == "__main__":
    unittest.main()
