"""The local harness (command-center/local-harness, per command-center/D53): every service in services/, built from a
clean checkout's HEAD and run on this machine with its manifest's settings (command-center/D46), against Postgres,
the Firestore emulator and the fakes in scripts/local/fakes/. It costs nothing and crosses no gate: every secret it
hands a service is made up here, and the services and their jobs sit on a Docker network with no route off the
machine, which the host reaches only through the fakes' port forwards.

  python3 scripts/local/harness.py up            build and start everything at HEAD (up.sh)
  python3 scripts/local/harness.py smoke         up, then one session end to end and threads (smoke.sh, LOOP.md §4)
  python3 scripts/local/harness.py smoke --no-up the same checks against what up already started at HEAD
  python3 scripts/local/harness.py rows          read every local/<service> row of LOOP.md §3 with its own command
  python3 scripts/local/harness.py env <service> the environment a service runs with, keys elided
  python3 scripts/local/harness.py down          stop and remove everything it started (down.sh)

How a service is configured here, from its manifest, services/<name>/service.json:

- Its settings take staging's value, with {project} the demo project `demo-local`, {region} us-east1 and {number} 0.
  A setting that names a service's Cloud Run URL, https://<service>-{number}.{region}.run.app, names that service on
  the local network instead, http://<service>:8080, so a service's own audience and another's URL for it agree.
- Each of its secrets gets a made-up value: a new RSA key for one whose name ends in PRIVATE_KEY, the service's own
  database in the local Postgres for DATABASE_URL, and random text for the rest.
- A manifest with `firestore` gets FIRESTORE_EMULATOR_HOST, and one with `cloudsql` a database of its own, migrated
  with `python -m <service>.migrate` when the service has a migrations/ folder.
- POINT_AT_FAKES then sets what points it at the fakes, and its jobs get JOB_SETTINGS. A service without an entry
  there still builds, runs and answers /version; it needs one only to reach a fake.

Each service listens on 127.0.0.1:<8700 + its place in SERVICES in scripts/gcp/common.sh>, the URL its local row in
LOOP.md §3 reads. Standard library only; it needs docker, git and openssl.
"""

import importlib.util
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
STATE = os.environ.get("LOCAL_STATE_DIR") or os.path.join(tempfile.gettempdir(), "architect-loop-local")

PROJECT = "jugonzal/architect-loop"
LABEL = "architect-loop-local"
NETWORK = "architect-loop-local"  # the fakes only: it publishes their ports on 127.0.0.1
INTERNAL = "architect-loop-local-internal"  # everything else: created --internal, so nothing on it leaves the machine
GCP_PROJECT = "demo-local"  # a demo project: the emulator and the fakes treat it as nobody's
REGION = "us-east1"
NUMBER = "0"
SERVICE_PORT = 8080  # every service listens on $PORT (command-center/D32); the harness sets 8080
BASE_PORT = 8700
GITHUB_PORT, RUN_PORT, METADATA_PORT, FIRESTORE_PORT = 8711, 8712, 8713, 8721
POSTGRES_IMAGE = "postgres:16"  # as threads.yml tests against
FIRESTORE_IMAGE = "gcr.io/google.com/cloudsdktool/google-cloud-cli:587.0.0-emulators"

# Made-up people. The sponsor and the member collaborate on the project; the outsider does not.
SPONSOR, MEMBER, OUTSIDER = "local-sponsor", "local-member", "local-outsider"
TOKENS = {SPONSOR: "local-sponsor-token", MEMBER: "local-member-token", OUTSIDER: "local-outsider-token"}

FAKES = "http://fakes"
POINT_AT_FAKES = {
    "runner": {
        "RUNNER_GITHUB_API_URL": f"{FAKES}:{GITHUB_PORT}",
        "RUNNER_GIT_URL": f"{FAKES}:{GITHUB_PORT}/{PROJECT}.git",
        "RUNNER_RUN_API_URL": f"{FAKES}:{RUN_PORT}",
        "RUNNER_METADATA_URL": f"{FAKES}:{METADATA_PORT}",
    },
    "threads": {
        "THREADS_GITHUB_API_URL": f"{FAKES}:{GITHUB_PORT}",
        "THREADS_RUNNER_KEYS_URL": f"{FAKES}:{METADATA_PORT}/oauth2/v3/certs",
    },
    "status": {
        "STATUS_GITHUB_API_URL": f"{FAKES}:{GITHUB_PORT}",
        "STATUS_GITHUB_GIT_URL": f"{FAKES}:{GITHUB_PORT}",
    },
}
# A runner session's job runs the fake Agent SDK, which the fake Cloud Run adds at /opt/local (fakes/fakesdk.py).
JOB_SETTINGS = {"runner": {"RUNNER_SDK_CLIENT": "fakesdk:client", "FAKE_SDK_SECONDS": "8"}}
JOB_FILES = {"runner": {"/opt/local/fakesdk.py": "/srv/fakes/fakesdk.py"}}
JOB_PATH = "/opt/local"

CLOUD_RUN_URL = re.compile(r"https://([a-z0-9-]+)-\{number\}\.\{region\}\.run\.app")


class Refused(Exception):
    pass


def say(line=""):
    print(line, flush=True)


def run(argv, check=True, capture=True, data=None, cwd=None, timeout=1800):
    result = subprocess.run(argv, input=data, cwd=cwd or ROOT, capture_output=capture, timeout=timeout,
                            text=isinstance(data, str) or data is None)
    if check and result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip() if capture else ""
        raise Refused(f"{' '.join(argv[:4])} failed ({result.returncode}): {detail[-2000:]}")
    return result


def container(name):
    return f"{LABEL}-{name}"


def image(name, sha):
    return f"{LABEL}/{name}:{sha}"


# The checkout.

def head(root=ROOT):
    return run(["git", "-C", root, "rev-parse", "HEAD"]).stdout.strip()


def refuse_dirty(root=ROOT):
    """A tracked file that differs from HEAD refuses the run: the services are built from HEAD, and the harness and its
    fakes run from the working tree, so both must be HEAD. Untracked files cannot reach either and are left alone."""
    changed = run(["git", "-C", root, "status", "--porcelain", "--untracked-files=no"]).stdout.strip()
    if changed:
        raise Refused("the working tree is dirty, so it is not the commit /version would answer; commit or stash:\n"
                      + changed)


def on_main(root, sha):
    """Whether origin/main contains the commit, so an evidence line may cite a run of it; None when unknown."""
    known = run(["git", "-C", root, "rev-parse", "--verify", "--quiet", "refs/remotes/origin/main"], check=False)
    if known.returncode != 0:
        return None
    return run(["git", "-C", root, "merge-base", "--is-ancestor", sha, "origin/main"], check=False).returncode == 0


# Services and their config.

def service_order(tree):
    with open(os.path.join(tree, "scripts", "gcp", "common.sh")) as f:
        found = re.search(r'^SERVICES="([^"]*)"', f.read(), re.M)
    return found.group(1).split() if found else []


def services_in(tree):
    """Every folder in services/ with a Dockerfile and a manifest, as {name: port}, in SERVICES order then by name. A
    service in SERVICES has the port its LOOP.md row names; any other gets the next one after them."""
    names = sorted(n for n in os.listdir(os.path.join(tree, "services"))
                   if os.path.isfile(os.path.join(tree, "services", n, "Dockerfile"))
                   and os.path.isfile(os.path.join(tree, "services", n, "service.json")))
    order = service_order(tree)
    ports, extra = {}, len(order)
    for name in sorted(names, key=lambda n: (order.index(n) if n in order else len(order), n)):
        if name in order:
            ports[name] = BASE_PORT + order.index(name) + 1
        else:
            extra += 1
            ports[name] = BASE_PORT + extra
    return ports


def manifest_module(tree):
    spec = importlib.util.spec_from_file_location("manifest", os.path.join(tree, "scripts", "gcp", "manifest.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_manifest(tree, name):
    module = manifest_module(tree)
    try:
        return module.checked(os.path.join(tree, "services", name, "service.json"), f"services/{name}/service.json")
    except module.Refused as error:
        raise Refused(str(error))


def localize(value, services):
    """A manifest setting's value here: staging's, with a service's Cloud Run URL made its local address."""
    value = value["staging"] if isinstance(value, dict) else value
    value = CLOUD_RUN_URL.sub(lambda m: f"http://{m[1]}:{SERVICE_PORT}" if m[1] in services else m[0], value)
    return value.replace("{project}", GCP_PROJECT).replace("{region}", REGION).replace("{number}", NUMBER)


def new_key():
    return run(["openssl", "genrsa", "2048"]).stdout


class FakeSecrets:
    """Made-up values for every secret a manifest names, one per service and name, so a job shares its service's."""

    def __init__(self, postgres_password, make_key=new_key):
        self.postgres_password, self.make_key, self.values = postgres_password, make_key, {}

    def database_url(self, service):
        return f"postgresql://local:{self.postgres_password}@postgres:5432/{service}"

    def value(self, service, name):
        if (service, name) not in self.values:
            if name.endswith("PRIVATE_KEY"):
                made = self.make_key()
            elif name == "DATABASE_URL":
                made = self.database_url(service)
            else:
                made = "local-fake-" + secrets.token_hex(16)
            self.values[(service, name)] = made
        return self.values[(service, name)]


def service_env(name, manifest, services, fake, sha):
    env = {key: localize(value, services) for key, value in manifest.get("settings", {}).items()}
    env.update({key: fake.value(name, key) for key in manifest.get("secrets", {})})
    if manifest.get("firestore"):
        env["FIRESTORE_EMULATOR_HOST"] = f"firestore:{SERVICE_PORT}"
    env.update(POINT_AT_FAKES.get(name, {}))
    env.update({"COMMIT_SHA": sha, "PORT": str(SERVICE_PORT)})
    return env


def job_env(name, job, service, services, fake, python_path=""):
    env = dict(service)
    env.update({key: localize(value, services) for key, value in job.get("settings", {}).items()})
    env.update({key: fake.value(name, key) for key in job.get("secrets", {})})
    env.update(JOB_SETTINGS.get(name, {}))
    env.pop("PORT", None)  # Cloud Run gives a job no port
    if JOB_FILES.get(name):
        env["PYTHONPATH"] = f"{python_path}:{JOB_PATH}" if python_path else JOB_PATH
    return env


def webhooks(env_by_service):
    """Every service whose secrets hold a GitHub webhook secret receives GitHub's deliveries, signed with it."""
    return [{"url": f"http://{name}:{SERVICE_PORT}/webhooks/github", "secret": value}
            for name, env in sorted(env_by_service.items()) for key, value in sorted(env.items())
            if key.endswith("_GITHUB_WEBHOOK_SECRET")]


def identity_of(manifest):
    return f"{manifest['identity']['name']}@{GCP_PROJECT}.iam.gserviceaccount.com"


# HTTP, from the host.

def call(method, url, token=None, body=None, headers=None, timeout=15):
    data = None if body is None else json.dumps(body).encode()
    request = urllib.request.Request(url, data=data, method=method, headers={
        **({"Authorization": f"Bearer {token}"} if token else {}),
        **({"Content-Type": "application/json"} if data is not None else {}), **(headers or {})})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status, raw = response.status, response.read()
    except urllib.error.HTTPError as error:
        status, raw = error.code, error.read()
    except OSError as error:
        return 0, str(error)
    try:
        return status, json.loads(raw) if raw else None
    except ValueError:
        return status, raw.decode(errors="replace")


def wait_for(what, probe, seconds):
    deadline = time.monotonic() + seconds
    while True:
        result = probe()
        if result:
            return result
        if time.monotonic() > deadline:
            raise Refused(f"{what} did not happen within {seconds} s")
        time.sleep(0.5)


# Up and down.

def down(quiet=False):
    found = run(["docker", "ps", "-aq", "--filter", f"label={LABEL}=1"]).stdout.split()
    if found:
        run(["docker", "rm", "-f", *found])
    for network in (INTERNAL, NETWORK):
        if run(["docker", "network", "inspect", network], check=False).returncode == 0:
            run(["docker", "network", "rm", network])
    if not quiet:
        say(f"down: removed {len(found)} containers and the networks {NETWORK} and {INTERNAL}")


def build(tree, dockerfile, tag, sha, log, attempts=3):
    """Build an image as deploy.sh does, from the commit's own tree with the repository root as the context. A build
    is tried up to three times, since a dependency download can time out (docs/runbooks/local.md, Traps)."""
    for attempt in range(1, attempts + 1):
        with open(log, "w") as out:
            result = subprocess.run(["docker", "build", "--file", os.path.join(tree, dockerfile), "--build-arg",
                                     f"COMMIT_SHA={sha}", "--tag", tag, "--label", f"{LABEL}=1", tree],
                                    stdout=out, stderr=subprocess.STDOUT)
        if result.returncode == 0:
            say(f"ok   built {tag}")
            return
        if attempt < attempts:
            say(f"note building {tag} failed (attempt {attempt} of {attempts}); trying again")
    with open(log) as f:
        tail = f.read()[-3000:]
    raise Refused(f"building {tag} failed {attempts} times; the end of {log}:\n{tail}")


def python_path_of(tag):
    env = json.loads(run(["docker", "image", "inspect", "--format", "{{json .Config.Env}}", tag]).stdout)
    return next((item.split("=", 1)[1] for item in env if item.startswith("PYTHONPATH=")), "")


def up(root=ROOT, state=STATE):
    for tool in ("docker", "git", "openssl"):
        if shutil.which(tool) is None:
            raise Refused(f"{tool} is not installed; the harness needs docker, git and openssl")
    refuse_dirty(root)
    sha = head(root)
    main = on_main(root, sha)
    say(f"up: local at {sha}" + {True: ", a commit on origin/main", False: ", which is NOT on origin/main: an "
                                 "evidence line cannot cite this run", None: " (origin/main unknown)"}[main])
    down(quiet=True)
    if os.path.exists(state):
        shutil.rmtree(state)
    tree = os.path.join(state, "tree")
    os.makedirs(tree)
    archive = subprocess.run(["git", "-C", root, "archive", "--format=tar", sha], capture_output=True, check=True)
    subprocess.run(["tar", "-x", "-C", tree], input=archive.stdout, check=True)

    services = services_in(tree)
    manifests = {name: load_manifest(tree, name) for name in services}
    build(tree, "scripts/local/fakes/Dockerfile", image("fakes", sha), sha, os.path.join(state, "build-fakes.log"))
    for name in services:
        build(tree, f"services/{name}/Dockerfile", image(name, sha), sha, os.path.join(state, f"build-{name}.log"))

    # The project's repository, as the fake GitHub serves it: HEAD as main, and every release tag.
    repository = os.path.join(state, "git", *PROJECT.split("/")) + ".git"
    run(["git", "init", "--quiet", "--bare", "--initial-branch=main", repository])
    run(["git", "-C", root, "push", "--quiet", repository, f"{sha}:refs/heads/main", "refs/tags/*:refs/tags/*"])

    fake = FakeSecrets("local-" + secrets.token_hex(8))
    env = {name: service_env(name, manifests[name], services, fake, sha) for name in services}
    jobs = {}
    for name, manifest in manifests.items():
        for job_name, job in manifest.get("jobs", {}).items():
            jobs[job_name] = {"image": image(name, sha), "command": job["command"], "network": INTERNAL,
                              "env": job_env(name, job, env[name], services, fake, python_path_of(image(name, sha))),
                              "files": JOB_FILES.get(name, {})}
    runner = manifests.get("runner")
    forwards = {str(port): f"{name}:{SERVICE_PORT}" for name, port in services.items()}
    forwards[str(FIRESTORE_PORT)] = f"firestore:{SERVICE_PORT}"
    config = {"project": PROJECT, "users": {token: login for login, token in TOKENS.items()},
              "collaborators": [SPONSOR, MEMBER], "git_root": "/srv/git",
              "public_url": f"http://localhost:{GITHUB_PORT}", "webhooks": webhooks(env), "jobs": jobs,
              "identity": identity_of(runner) if runner else "", "forwards": forwards,
              "github_port": GITHUB_PORT, "run_port": RUN_PORT, "metadata_port": METADATA_PORT}

    run(["docker", "network", "create", "--label", f"{LABEL}=1", NETWORK])
    run(["docker", "network", "create", "--internal", "--label", f"{LABEL}=1", INTERNAL])
    labelled = ["--label", f"{LABEL}=1"]
    run(["docker", "run", "--detach", "--name", container("postgres"), *labelled, "--network", INTERNAL,
         "--network-alias", "postgres", "-e", "POSTGRES_USER=local", "-e",
         f"POSTGRES_PASSWORD={fake.postgres_password}", "-e", "POSTGRES_DB=local", POSTGRES_IMAGE])
    run(["docker", "run", "--detach", "--name", container("firestore"), *labelled, "--network", INTERNAL,
         "--network-alias", "firestore", FIRESTORE_IMAGE, "gcloud", "emulators", "firestore", "start",
         f"--host-port=0.0.0.0:{SERVICE_PORT}"])
    published = [str(p) for p in (*services.values(), GITHUB_PORT, RUN_PORT, METADATA_PORT, FIRESTORE_PORT)]
    run(["docker", "create", "--name", container("fakes"), *labelled, "--network", NETWORK,
         *[arg for port in published for arg in ("--publish", f"127.0.0.1:{port}:{port}")],
         "--volume", "/var/run/docker.sock:/var/run/docker.sock", "-e", f"FAKE_CONFIG={json.dumps(config)}",
         image("fakes", sha)])
    run(["docker", "network", "connect", "--alias", "fakes", INTERNAL, container("fakes")])
    run(["docker", "cp", os.path.join(state, "git"), f"{container('fakes')}:/srv/git"])
    run(["docker", "start", container("fakes")])
    wait_for("the fakes answering", lambda: call("GET", f"http://127.0.0.1:{GITHUB_PORT}/_local/calls")[0] == 200, 60)
    say(f"ok   fakes: GitHub on {GITHUB_PORT}, Cloud Run on {RUN_PORT}, the metadata server on {METADATA_PORT}")
    wait_for("Postgres accepting connections", lambda: run(
        ["docker", "exec", container("postgres"), "pg_isready", "-h", "127.0.0.1", "-U", "local", "-d", "local"],
        check=False).returncode == 0, 90)
    wait_for("the Firestore emulator answering",
             lambda: call("GET", f"http://127.0.0.1:{FIRESTORE_PORT}/")[0] == 200, 120)
    say(f"ok   Postgres, and the Firestore emulator on {FIRESTORE_PORT}")

    for name, manifest in manifests.items():
        if not manifest.get("cloudsql"):
            continue
        run(["docker", "exec", container("postgres"), "psql", "-h", "127.0.0.1", "-U", "local", "-d", "local",
             "--quiet", "-c", f'CREATE DATABASE "{name}"'])
        if os.path.isdir(os.path.join(tree, "services", name, "migrations")):
            migrated = run(["docker", "run", "--rm", *labelled, "--network", INTERNAL, "-e",
                            f"DATABASE_URL={env[name]['DATABASE_URL']}", image(name, sha), "python", "-m",
                            f"{name}.migrate"])
            say(f"ok   the {name} database: {' '.join(migrated.stdout.split()) or 'nothing to apply'}")

    for name in services:
        settings = [arg for key, value in sorted(env[name].items()) for arg in ("-e", f"{key}={value}")]
        run(["docker", "run", "--detach", "--name", container(name), *labelled, "--network", INTERNAL,
             "--network-alias", name, *settings, image(name, sha)])
    failed = []
    for name, port in services.items():
        url = f"http://localhost:{port}/version"
        try:
            wait_for(f"{url} answering {sha}",
                     lambda: (call("GET", f"http://127.0.0.1:{port}/version")[1] or {}) == {"commit": sha}, 90)
            say(f"ok   local/{name} answers {sha} at {url}")
        except Refused as error:
            logs = run(["docker", "logs", "--tail", "30", container(name)], check=False)
            say(f"FAIL local/{name}: {error}\n{logs.stdout}{logs.stderr}")
            failed.append(name)

    with open(os.path.join(state, "harness.json"), "w") as f:
        json.dump({"sha": sha, "services": services, "env": env}, f, indent=1)
    if failed:
        raise Refused(f"{', '.join(failed)} did not answer {sha}; sh scripts/local/down.sh stops the rest")
    say(f"up: {len(services)} services at {sha}; sh scripts/local/smoke.sh --no-up runs the smoke test against them, "
        "and sh scripts/local/down.sh stops them")
    return {"sha": sha, "services": services, "env": env}


def load_state(root=ROOT, state=STATE):
    try:
        with open(os.path.join(state, "harness.json")) as f:
            found = json.load(f)
    except OSError:
        raise Refused("nothing is up: run sh scripts/local/up.sh first")
    if found["sha"] != head(root):
        raise Refused(f"what is up is {found['sha']}, not HEAD {head(root)}: run sh scripts/local/up.sh again")
    return found


# The local rows of LOOP.md §3.

def loop_status_module(root=ROOT):
    path = os.path.join(root, "plugin", "skills", "loop-status", "scripts", "loop_status.py")
    spec = importlib.util.spec_from_file_location("loop_status", path)
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, os.path.dirname(path))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.remove(os.path.dirname(path))
    return module


def local_rows(root=ROOT):
    """LOOP.md §3's local/<service> rows, as loop-status parses them."""
    with open(os.path.join(root, "LOOP.md")) as f:
        rows = loop_status_module(root).environment_rows(f.read())
    return [row for row in rows if row["name"].startswith("local/")]


def rows(root=ROOT, sha=None, checks=None):
    """Run each local row's served-commit command, as /loop-status does. A row for a service in services/ must answer
    HEAD; a row for a service not built yet reads as unknown, which is true."""
    sha = sha or head(root)
    checks = checks or Checks()
    built = set(os.listdir(os.path.join(root, "services")))
    found = local_rows(root)
    checks.check("LOOP.md §3 has local rows", bool(found), "no row is named local/<service>")
    for row in found:
        service = row["name"].split("/", 1)[1]
        if row["error"]:
            checks.check(f"{row['name']} has a served-commit command", False, row["error"])
            continue
        result = subprocess.run(row["command"], shell=True, cwd=root, capture_output=True, text=True, timeout=60)
        served = result.stdout.strip()
        if service in built:
            checks.check(f"{row['name']} reads {sha[:7]} with `{row['command']}`", served == sha,
                         served or result.stderr.strip())
        else:
            say(f"note {row['name']} reads as unknown: services/{service} is not built yet "
                f"({result.stderr.strip() or served})")
    return checks


# The smoke test.

class Checks:
    def __init__(self):
        self.passed, self.failed = [], []

    def check(self, what, ok, detail=""):
        (self.passed if ok else self.failed).append(what)
        say(f"ok   {what}" if ok else f"FAIL {what}" + (f": {detail}" if detail else ""))
        return ok


def first_concern(root, sha):
    names = run(["git", "-C", root, "ls-tree", "-r", "--name-only", sha, "docs/loops"]).stdout.split()
    concerns = sorted(m.group(1) for m in (re.match(r"^docs/loops/([a-z0-9-]+/[a-z0-9-]+)\.md$", n) for n in names)
                      if m and not m.group(1).endswith("/README"))
    if not concerns:
        raise Refused("no concern is on this commit, so there is nothing to dispatch on")
    return concerns[0]


def latest_release(root, sha):
    found = run(["git", "-C", root, "describe", "--tags", "--abbrev=0", "--match", "v[0-9]*.[0-9]*.[0-9]*", sha],
                check=False)
    if found.returncode != 0:
        raise Refused("no release tag is reachable from HEAD, and a session installs the plugin from one; fetch the "
                      "tags (in CI, check out with fetch-depth: 0)")
    return found.stdout.strip()


# Run in a container on the internal network: it exits 0 only if neither a name nor an address off the machine answers.
UNREACHABLE = """
import socket
reached = []
for target in (("api.github.com", 443), ("1.1.1.1", 443)):
    try:
        socket.create_connection(target, 5).close()
        reached.append(target[0])
    except OSError as error:
        print(target[0], "unreachable:", error)
raise SystemExit("reached " + ", ".join(reached) if reached else 0)
"""


def labelled_containers():
    names = run(["docker", "ps", "-a", "--filter", f"label={LABEL}=1", "--format", "{{.Names}}"]).stdout.split()
    return {name: json.loads(run(["docker", "inspect", "--format", "{{json .}}", name]).stdout) for name in names}


def session_containers(sid):
    """The containers the fake Cloud Run started for one session's job."""
    return {name: d for name, d in labelled_containers().items()
            if d["Config"]["Labels"].get(f"{LABEL}.session") == sid}


def exited(sid):
    found = session_containers(sid)
    return found if found and all(d["State"]["Status"] == "exited" for d in found.values()) else None


def smoke(root=ROOT, state=STATE, no_up=False):
    found = load_state(root, state) if no_up else up(root, state)
    sha, services, env = found["sha"], found["services"], found["env"]
    checks = Checks()
    concern = os.environ.get("LOCAL_SMOKE_CONCERN") or first_concern(root, sha)
    release = latest_release(root, sha)
    runner = f"http://127.0.0.1:{services['runner']}"
    github = f"http://127.0.0.1:{GITHUB_PORT}"
    owner = PROJECT.split("/")[0]
    say(f"smoke: /loop-build on {concern}, plugin {release}, sponsored by {SPONSOR}, at local @{sha}")

    # C2: a dispatch to the local runner, claimed in the shared store.
    dispatch = {"project": PROJECT, "skill": "loop-build", "concern": concern, "budget_usd": 1.0,
                "plugin_release": release}
    status, session = call("POST", f"{runner}/sessions", TOKENS[SPONSOR], dispatch)
    if not checks.check("the runner accepts a dispatch from a collaborator", status == 201, f"{status} {session}"):
        return finish(checks, sha)
    sid = session["id"]
    status, refusal = call("POST", f"{runner}/sessions", TOKENS[SPONSOR], dispatch)
    checks.check("a second /loop-build on the concern is refused while the first holds it", status == 409 and
                 (refusal or {}).get("refused") == "running-session", f"{status} {refusal}")
    status, outsider = call("POST", f"{runner}/sessions", TOKENS[OUTSIDER], dispatch)
    checks.check("the runner refuses a dispatch from someone who does not collaborate", status == 403,
                 f"{status} {outsider}")
    status, claims = call("GET", f"http://127.0.0.1:{FIRESTORE_PORT}/v1/projects/{GCP_PROJECT}/databases/runner/"
                                 "documents/claims")
    holders = [value.get("stringValue") for doc in (claims or {}).get("documents", [])
               if doc["fields"].get("concern", {}).get("stringValue") == concern
               for value in doc["fields"].get("holders", {}).get("arrayValue", {}).get("values", [])]
    checks.check("the concern is claimed in the runner's Firestore database, which its jobs share", sid in holders,
                 f"{status} {claims}")

    seen_running, last = False, session
    deadline = time.monotonic() + 240
    while time.monotonic() < deadline:
        status, last = call("GET", f"{runner}/sessions/{sid}", TOKENS[SPONSOR])
        if status == 200 and last["state"] == "running" and last.get("spend"):
            seen_running = True
        if status == 200 and last["state"] == "ended":
            break
        time.sleep(0.5)
    checks.check("spend is published while the session runs", seen_running, f"last read: {last}")
    ended = isinstance(last, dict) and last.get("state") == "ended"
    checks.check("the session runs from start to end", ended and last.get("outcome") == "completed", f"{last}")
    spend = (last or {}).get("spend") or {}
    checks.check("its final spend is published, as the (fake) SDK's estimate",
                 spend.get("basis") == "sdk result" and spend.get("usd") == 0.0123, f"{spend}")
    checks.check("its final message is kept", "Opened pull request #" in ((last or {}).get("final_message") or ""),
                 f"{(last or {}).get('final_message')!r}")

    try:
        containers = wait_for("the session's job exiting", lambda: exited(sid), 60)
    except Refused:
        containers = session_containers(sid)
    job = next(iter(containers.values()), None)
    states = {name: (d["State"]["Status"], d["State"]["ExitCode"]) for name, d in containers.items()}
    checks.check("the session's job ran in its own container, apart from the runner's, and exited 0",
                 len(containers) == 1 and job["Name"].lstrip("/") != container("runner")
                 and job["State"]["ExitCode"] == 0, f"containers labelled with the session: {states}")

    status, pulls = call("GET", f"{github}/repos/{PROJECT}/pulls?state=open&head={owner}:{concern}",
                         TOKENS[SPONSOR])
    pull = (pulls or [None])[0] if status == 200 else None
    body = (pull or {}).get("body") or ""
    checks.check("the session opened a pull request on the fake GitHub, and the session lists it",
                 pull is not None and [p["number"] for p in last.get("pull_requests", [])] == [pull["number"]],
                 f"{status} {pulls}; session lists {last.get('pull_requests')}")
    checks.check("its pull request body carries Concern: and Sponsored-by:",
                 f"Concern: {concern}" in body and f"Sponsored-by: {SPONSOR}" in body, repr(body))
    with tempfile.TemporaryDirectory() as scratch:
        run(["git", "init", "--quiet", "--bare", scratch])
        run(["git", "-C", scratch, "fetch", "--quiet", f"{github}/{PROJECT}.git", concern])
        message = run(["git", "-C", scratch, "log", "-1", "--format=%B", "FETCH_HEAD"]).stdout
    checks.check("its commit carries Concern: and Sponsored-by: from the runner's hook",
                 f"Concern: {concern}" in message and f"Sponsored-by: {SPONSOR}" in message, repr(message))

    status, log = call("GET", f"{github}/_local/calls")
    calls = (log or {}).get("calls", [])
    asked = {(c["fake"], c["method"], c.get("caller")) for c in calls}
    paths = [c["path"] for c in calls]
    checks.check("the runner asked the fakes, not GitHub or Google: who calls, a collaborator check, installation "
                 "tokens, the concern, the release, a push and a job execution",
                 ("github", "GET", "user") in asked and any(p.endswith(f"/collaborators/{SPONSOR}") for p in paths)
                 and ("github", "MINT", None) in asked and any(p.endswith(f"/contents/docs/loops/{concern}.md")
                                                               for p in paths)
                 and any(f"/git/ref/tags/{release}" in p for p in paths) and ("github", "PUSH", None) in asked
                 and any(c["fake"] == "run" and c["method"] == "EXECUTE" and c.get("session") == sid for c in calls)
                 and any(c["fake"] == "metadata" and c["path"].endswith("/token") for c in calls), f"{sorted(asked)}")

    # Nothing leaves the machine: everything but the fakes is on the internal network, which has no route out.
    internal = json.loads(run(["docker", "network", "inspect", "--format", "{{json .Internal}}", INTERNAL]).stdout)
    outside = {name: sorted(d["NetworkSettings"]["Networks"]) for name, d in labelled_containers().items()
               if name != container("fakes") and sorted(d["NetworkSettings"]["Networks"]) != [INTERNAL]}
    checks.check(f"every service, job and store is on {INTERNAL} only, a network with no route off the machine",
                 internal is True and not outside, f"internal={internal}, elsewhere: {outside}")
    probe = run(["docker", "run", "--rm", "--label", f"{LABEL}=1", "--network", INTERNAL, image("runner", sha),
                 "python", "-c", UNREACHABLE], check=False)
    checks.check(f"a container on {INTERNAL} reaches neither api.github.com nor 1.1.1.1", probe.returncode == 0,
                 (probe.stdout + probe.stderr).strip())

    # Threads answers a member's read and post.
    if "threads" in services:
        threads_checks(checks, services, env, concern, sid, pull)
    rows(root, sha, checks)
    return finish(checks, sha)


def threads_checks(checks, services, env, concern, sid, pull):
    threads = f"http://127.0.0.1:{services['threads']}"
    loop, name = concern.split("/")
    thread = f"{threads}/projects/{PROJECT}/loops/{loop}/concerns/{name}/thread"
    status, view = call("GET", thread, TOKENS[MEMBER])
    checks.check("threads answers a member's read of the concern's thread",
                 status == 200 and {"login": MEMBER} in (view or {}).get("members", []), f"{status} {view}")
    text = f"A member's message from the local smoke test, {secrets.token_hex(4)}"
    status, posted = call("POST", f"{thread}/messages", TOKENS[MEMBER], {"body": text})
    checks.check("threads takes a member's post", status == 201 and (posted or {}).get("author") ==
                 {"type": "person", "login": MEMBER}, f"{status} {posted}")
    status, page = call("GET", f"{thread}/messages", TOKENS[MEMBER])
    checks.check("the member reads their post back", status == 200 and any(
        m["body"] == text for m in (page or {}).get("messages", [])), f"{status} {page}")
    status, refused = call("GET", thread, TOKENS[OUTSIDER])
    checks.check("threads refuses someone who is not a member", status == 403, f"{status} {refused}")

    if pull is not None:
        review = f"A review from the local smoke test, {secrets.token_hex(4)}"
        status, _ = call("POST", f"http://127.0.0.1:{GITHUB_PORT}/repos/{PROJECT}/pulls/{pull['number']}/reviews",
                         TOKENS[MEMBER], {"body": review, "event": "COMMENT"})

        def mirrored():
            found = call("GET", f"{thread}/messages", TOKENS[MEMBER])[1] or {}
            return any(m["body"] == review and m["author"]["type"] == "github" for m in found.get("messages", []))

        try:
            ok = status == 200 and wait_for("the review mirrored", mirrored, 20)
        except Refused as error:
            ok = False
            status = error
        checks.check("a review on the session's pull request reaches the concern's thread, by the fake GitHub's "
                     "webhook", ok, f"{status}")

    status, token = call("GET", f"http://127.0.0.1:{METADATA_PORT}/computeMetadata/v1/instance/service-accounts/"
                                f"default/identity?audience={urllib.parse.quote(env['threads']['THREADS_AUDIENCE'])}"
                                "&format=full", headers={"Metadata-Flavor": "Google"})
    session_thread = f"{threads}/projects/{PROJECT}/sessions/{sid}/thread/messages"
    milestone = f"A milestone posted with the runner's identity, {secrets.token_hex(4)}"
    posted = call("POST", session_thread, token if isinstance(token, str) else "", {
        "body": milestone, "kind": "milestone", "sponsor": SPONSOR}) if status == 200 else (status, token)
    checks.check("threads takes a post to the session's thread with the runner's ID token, checked against the "
                 "fake metadata server's keys", posted[0] == 201, f"{posted}")
    status, page = call("GET", session_thread, TOKENS[MEMBER])
    checks.check("a member reads it", status == 200 and any(m["body"] == milestone and m["author"] == {
        "type": "session", "session": sid, "sponsor": SPONSOR} for m in (page or {}).get("messages", [])),
                 f"{status} {page}")


def finish(checks, sha):
    total = len(checks.passed) + len(checks.failed)
    if checks.failed:
        say(f"smoke: {len(checks.failed)} of {total} checks failed at local @{sha}")
        return 1
    say(f"smoke: all {total} checks hold at local @{sha}; sh scripts/local/down.sh stops the harness")
    return 0


def show_env(name, root=ROOT, state=STATE):
    found = load_state(root, state)
    if name not in found["env"]:
        raise Refused(f"no service {name} is up; up started {', '.join(found['env'])}")
    for key, value in sorted(found["env"][name].items()):
        shown = "<made-up key>" if "-----BEGIN" in value else value
        say(f"{key}={shown}")
    return 0


def main(argv):
    command, args = (argv[1] if len(argv) > 1 else ""), argv[2:]
    try:
        if command == "up" and not args:
            up()
            return 0
        if command == "down" and not args:
            down()
            return 0
        if command == "smoke" and args in ([], ["--no-up"]):
            return smoke(no_up=bool(args))
        if command == "rows" and not args:
            return 1 if rows().failed else 0
        if command == "env" and len(args) == 1:
            return show_env(args[0])
    except Refused as error:
        say(f"{command or 'harness'}: {error}")
        return 1
    print(__doc__.split("\n\n")[1], file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
