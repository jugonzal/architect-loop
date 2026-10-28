"""Shared test fixtures: a project with a real git origin, a fake GitHub over HTTP, a fake /version server for the
environments, and a test client that checks every request and response against openapi.yaml.

Nothing here reaches a network. The origin is a bare repository in a temporary folder, which the service clones
by path (STATUS_GITHUB_GIT_URL). GitHub's API is FakeGitHubServer on 127.0.0.1, which checks the app's signed JWT
and its installation tokens the way GitHub does. Each environment's /version is VersionServer on 127.0.0.1.
"""

import hashlib
import hmac
import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
import unittest
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import jwt
import yaml
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from openapi_core import OpenAPI
from openapi_core.contrib.werkzeug import WerkzeugOpenAPIRequest, WerkzeugOpenAPIResponse
from werkzeug.test import EnvironBuilder
from werkzeug.wrappers import Request

from status.app import create_app
from status.config import Settings

HERE = os.path.dirname(os.path.abspath(__file__))
SERVICE = os.path.dirname(HERE)
ROOT = os.path.dirname(os.path.dirname(SERVICE))
SCRIPTS = os.path.join(ROOT, "plugin", "skills", "loop-status", "scripts")
SPEC_PATH = os.path.join(SERVICE, "openapi.yaml")
SPEC = OpenAPI.from_file_path(SPEC_PATH)

PROJECT = "example/shop"
OTHER_PROJECT = "example/elsewhere"
COMMIT = "0123456789abcdef0123456789abcdef01234567"
APP_ID = "424242"
INSTALLATION_ID = 7
WEBHOOK_SECRET = b"made-up-test-secret"
NOW = datetime(2026, 10, 23, 9, 0, 0, tzinfo=timezone.utc)
AS_OF = "2026-10-23T09:00:00Z"


def _new_key():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                            serialization.NoEncryption()).decode()
    return key, pem


# One key for the whole run: generating one takes long enough to slow every test down.
APP_KEY, APP_PEM = _new_key()


# --- The loop documents ---------------------------------------------------------------------------------------------

def loop_md(version_url, marker):
    """LOOP.md with one row of each kind the service must tell apart (command-center/D9, D56)."""
    return f"""# LOOP.md

## 3. Environments

| Environment | Where | Agents may read | Agents may write | Deployed by | Served commit: a command that prints its SHA | Verify with |
| --- | --- | --- | --- | --- | --- | --- |
| main | the main branch | yes | `docs/loops/` only | owner, by merging | `git fetch -q origin && git rev-parse origin/main` | |
| staging/web | Cloud Run | yes | no | owner | `sh scripts/served.sh {version_url}/staging/version` | `sh scripts/served.sh {version_url}/staging/version <sha>` |
| staging/api | Cloud Run | yes | no | owner | `sh scripts/served.sh {version_url}/api/version` then {version_url}/second/version | |
| staging/cmd | a box | yes | no | owner | `touch {marker} && cat served.txt` | |
| staging/app | EAS | TODO(owner): no | no | owner | `eas build:list \\| node served.js staging` | |
| production/web | Cloud Run | yes | no | owner | TODO(owner): `sh scripts/served.sh <URL>` | |
"""


def concern_md(touches="[src/x/]", ships_to="staging/web", claims=None, evidence=()):
    claims = ["- **C1** It works. Prove: a run, on staging/web."] if claims is None else list(claims)
    lines = ["---", "needs: []", "touches: %s" % touches, "effects: []", "ships-to: %s" % ships_to, "---",
             "# A concern that does one thing", "", "## Done when", ""] + claims
    lines += ["", "## Decisions", "", "| # | Decision | Decided by, date | Closes |", "| --- | --- | --- | --- |"]
    lines += ["", "## Questions", "", "| # | Question | Blocks | Default if unanswered |", "| --- | --- | --- | --- |"]
    lines += ["", "## Evidence", ""] + list(evidence) + ["", "## Shipped", ""]
    return "\n".join(lines) + "\n"


def readme_md(title="A loop to try things in"):
    lines = ["# %s" % title, "", "## Goals", "", "## Shared decisions", "",
             "| # | Decision | Decided by, date | Notes |", "| --- | --- | --- | --- |", "", "## Questions", "",
             "| # | Question | Blocks | Default if unanswered |", "| --- | --- | --- | --- |", "", "## Evidence", "",
             "## Shipped", ""]
    return "\n".join(lines) + "\n"


def initial_files(version_url, marker):
    return {
        "README.md": "A shop.\n",
        "LOOP.md": loop_md(version_url, marker),
        "docs/loops/sandbox/README.md": readme_md(),
        "docs/loops/sandbox/alpha.md": concern_md(touches="[src/alpha/]", ships_to="staging/web"),
        "docs/loops/sandbox/beta.md": concern_md(touches="[src/beta/]", ships_to="main",
                                                 claims=["- **C1** It works. Prove: a run, on main."]),
    }


# --- A project with a real git origin -------------------------------------------------------------------------------

GIT_ENV = {
    "GIT_AUTHOR_NAME": "Test Author", "GIT_AUTHOR_EMAIL": "author@example.com",
    "GIT_COMMITTER_NAME": "Test Author", "GIT_COMMITTER_EMAIL": "author@example.com",
    "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1", "GIT_TERMINAL_PROMPT": "0",
}


def git(*args, cwd=None, check=True):
    env = dict(os.environ, **GIT_ENV)
    result = subprocess.run(["git", *args], cwd=cwd, env=env, capture_output=True, text=True)
    if check and result.returncode:
        raise AssertionError("git %s failed: %s" % (" ".join(args), result.stderr))
    return result.stdout.strip()


class World:
    """A project's repository: a bare origin, as GitHub holds it, and a work tree that commits and pushes to it.

    The service clones `<git_root>/<owner>/<repo>.git`, so STATUS_GITHUB_GIT_URL is `git_root`.
    """

    def __init__(self, root, project, files):
        self.project = project
        self.git_root = os.path.join(root, "git")
        self.origin = os.path.join(self.git_root, project + ".git")
        os.makedirs(os.path.dirname(self.origin))
        git("init", "--quiet", "--bare", "--initial-branch=main", self.origin)
        self.work = os.path.join(root, "work")
        git("init", "--quiet", "--initial-branch=main", self.work)
        git("remote", "add", "origin", self.origin, cwd=self.work)
        self.commit(files, "Start the shop")

    def _write(self, files):
        for path, text in files.items():
            full = os.path.join(self.work, path)
            if text is None:
                if os.path.exists(full):
                    os.remove(full)
                continue
            os.makedirs(os.path.dirname(full), exist_ok=True)
            with open(full, "w", encoding="utf-8") as f:
                f.write(text)

    def commit(self, files, message, branch="main"):
        """A commit on branch (made from main if it does not exist yet), pushed; returns its sha."""
        if git("rev-parse", "--verify", "--quiet", "HEAD", cwd=self.work, check=False):
            known = git("branch", "--list", branch, cwd=self.work)
            git("checkout", "--quiet", *([branch] if known else ["-b", branch, "main"]), cwd=self.work)
        self._write(files)
        git("add", "-A", cwd=self.work)
        git("commit", "--quiet", "--allow-empty", "-m", message, cwd=self.work)
        git("push", "--quiet", "origin", branch, cwd=self.work)
        git("checkout", "--quiet", "main", cwd=self.work)
        return git("rev-parse", branch, cwd=self.work)

    def merge(self, branch, number):
        """Merge branch into main the way GitHub's merge button does; returns the merge commit's sha."""
        git("checkout", "--quiet", "main", cwd=self.work)
        owner = self.project.split("/")[0]
        git("merge", "--quiet", "--no-ff", "-m", "Merge pull request #%d from %s/%s" % (number, owner, branch), branch,
            cwd=self.work)
        git("push", "--quiet", "origin", "main", cwd=self.work)
        return git("rev-parse", "main", cwd=self.work)

    def delete_branch(self, branch):
        git("push", "--quiet", "origin", "--delete", branch, cwd=self.work)
        git("branch", "--quiet", "-D", branch, cwd=self.work)

    def pull_head(self, number, sha):
        """GitHub's refs/pull/<n>/head, which the service fetches to check a loop-document pull request."""
        git("push", "--quiet", "origin", "%s:refs/pull/%d/head" % (sha, number), cwd=self.work)

    def main(self):
        return git("--git-dir", self.origin, "rev-parse", "main")


# --- Fake servers ---------------------------------------------------------------------------------------------------

class _Server:
    def __init__(self):
        server = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                server.handle(self, "GET")

            def do_POST(self):
                server.handle(self, "POST")

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = "http://127.0.0.1:%d" % self.httpd.server_address[1]
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()

    @staticmethod
    def send(h, status, payload, headers=None, raw=None):
        data = raw if raw is not None else (b"" if payload is None else json.dumps(payload).encode())
        try:
            h.send_response(status)
            for name, value in (headers or {}).items():
                h.send_header(name, value)
            if payload is not None and raw is None:
                h.send_header("Content-Type", "application/json")
            h.send_header("Content-Length", str(len(data)))
            h.end_headers()
            h.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            pass


class VersionServer(_Server):
    """Each environment's /version: a path answers what the test set, and anything else answers 404."""

    def __init__(self):
        self.answers = {}
        self.requests = []
        super().__init__()

    def serve(self, path, commit):
        self.answers[path] = (200, json.dumps({"commit": commit}).encode(), 0)

    def answer(self, path, status, raw, delay=0):
        self.answers[path] = (status, raw if isinstance(raw, bytes) else raw.encode(), delay)

    def handle(self, h, method):
        self.requests.append((method, h.path))
        status, raw, delay = self.answers.get(h.path, (404, b"", 0))
        if delay:
            time.sleep(delay)
        self.send(h, status, None, {"Content-Type": "application/json"}, raw=raw)


class FakeGitHubServer(_Server):
    """GitHub's REST and GraphQL APIs, as the status service's app and its callers see them. Records each request.

    Pull requests are kept in the shape `gh pr list --json` prints them, and served over GraphQL the way GitHub
    answers the service's query, so a test can compare the service's reading with what gh would give.
    """

    def __init__(self, public_key, projects):
        self.public_key = public_key
        self.projects = set(projects)
        self.users = {}
        self.collaborators = {}
        self.prs = {}
        self.runs = {}
        self.default_branches = {}
        self.compare = {}
        self.requests = []
        self.installation_tokens = []
        self.revoked = False
        self.fail = {}
        super().__init__()

    def pr(self, number, head, state="OPEN", base="main", body=None, merge=None, files=("src/x/a.py",),
           checks=None, draft=False, project=PROJECT):
        """Add or replace a pull request. merge is its merge commit's sha, for a merged one."""
        body = "Builds it.\n\nConcern: %s\n" % head if body is None else body
        checks = [{"__typename": "CheckRun", "name": "check", "status": "COMPLETED", "conclusion": "SUCCESS"}] \
            if checks is None else checks
        item = {"number": number, "title": "Pull request %d" % number,
                "url": "https://github.com/%s/pull/%d" % (project, number), "headRefName": head,
                "baseRefName": base, "state": state, "isDraft": draft, "body": body,
                "mergeCommit": {"oid": merge} if merge else None, "files": list(files), "checks": list(checks)}
        items = [p for p in self.prs.setdefault(project, []) if p["number"] != number]
        self.prs[project] = sorted(items + [item], key=lambda p: -p["number"])
        return item

    def revoke(self):
        """The app is uninstalled or its key revoked: its tokens stop working and no new one is issued."""
        self.revoked = True
        self.installation_tokens = []

    def handle(self, h, method):
        length = int(h.headers.get("Content-Length") or 0)
        body = h.rfile.read(length) if length else b""
        path, _, query = h.path.partition("?")
        self.requests.append((method, path))
        for prefix, status in self.fail.items():
            if path.startswith(prefix):
                return self.send(h, status, {"message": "fake outage"})
        if h.headers.get("Accept") != "application/vnd.github+json":
            return self.send(h, 415, {"message": "wrong Accept"})
        auth = h.headers.get("Authorization", "")
        token = auth[len("Bearer "):] if auth.startswith("Bearer ") else None

        if method == "GET" and path == "/user":
            if token in self.users:
                return self.send(h, 200, {"login": self.users[token], "id": 1})
            return self.send(h, 401, {"message": "Bad credentials"})

        match = re.fullmatch(r"/repos/([^/]+/[^/]+)/installation", path)
        if match and method == "GET":
            if not self.app_jwt_ok(token):
                return self.send(h, 401, {"message": "A JSON web token could not be decoded"})
            if match.group(1) not in self.projects:
                return self.send(h, 404, {"message": "Not Found"})
            return self.send(h, 200, {"id": INSTALLATION_ID})

        if path == "/app/installations/%d/access_tokens" % INSTALLATION_ID and method == "POST":
            if not self.app_jwt_ok(token):
                return self.send(h, 401, {"message": "A JSON web token could not be decoded"})
            issued = "ghs_fake%d" % len(self.installation_tokens)
            self.installation_tokens.append(issued)
            expires = (datetime.now(timezone.utc) + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
            return self.send(h, 201, {"token": issued, "expires_at": expires})

        if token not in self.installation_tokens:
            return self.send(h, 401, {"message": "Bad credentials"})

        match = re.fullmatch(r"/repos/([^/]+/[^/]+)/collaborators/([^/]+)", path)
        if match and method == "GET":
            return self.send(h, 204 if match.group(2) in self.collaborators.get(match.group(1), set()) else 404, None)

        if path == "/graphql" and method == "POST":
            return self.graphql(h, json.loads(body or b"{}"))

        match = re.fullmatch(r"/repos/([^/]+/[^/]+)/actions/runs", path)
        if match and method == "GET":
            params = dict(p.split("=", 1) for p in query.split("&") if "=" in p)
            runs = self.runs.get(match.group(1), {}).get(params.get("head_sha"), [])
            return self.send(h, 200, {"total_count": len(runs), "workflow_runs": runs})

        match = re.fullmatch(r"/repos/([^/]+/[^/]+)/compare/([0-9a-f]+)\.\.\.([0-9A-Za-z._/-]+)", path)
        if match and method == "GET":
            status = self.compare.get((match.group(1), match.group(2), match.group(3)))
            if status is None:
                return self.send(h, 404, {"message": "Not Found"})
            return self.send(h, 200, {"status": status})

        match = re.fullmatch(r"/repos/([^/]+/[^/]+)", path)
        if match and method == "GET" and match.group(1) in self.default_branches:
            return self.send(h, 200, {"full_name": match.group(1), "default_branch": self.default_branches[match.group(1)]})

        return self.send(h, 404, {"message": "Not Found"})

    def node(self, item):
        rollup = None
        if item["checks"]:
            rollup = {"contexts": {"nodes": item["checks"]}}
        return {k: item[k] for k in ("number", "title", "url", "headRefName", "baseRefName", "state", "isDraft",
                                     "body", "mergeCommit")} | {
            "files": {"nodes": [{"path": p} for p in item["files"]]},
            "commits": {"nodes": [{"commit": {"statusCheckRollup": rollup}}]},
        }

    def graphql(self, h, request):
        variables = request.get("variables") or {}
        project = "%s/%s" % (variables.get("owner"), variables.get("name"))
        if project not in self.prs and project not in self.projects:
            return self.send(h, 200, {"data": {"repository": None}, "errors": [
                {"type": "NOT_FOUND", "message": "Could not resolve to a Repository with the name '%s'." % project}]})
        items = self.prs.get(project, [])
        if "pullRequests(" in request.get("query", ""):
            first = int(variables.get("first") or 100)
            start = int(variables.get("after") or 0)
            page = items[start:start + first]
            more = start + first < len(items)
            return self.send(h, 200, {"data": {"repository": {"pullRequests": {
                "pageInfo": {"hasNextPage": more, "endCursor": str(start + first) if more else None},
                "nodes": [self.node(p) for p in page]}}}})
        if "pullRequest(number" in request.get("query", ""):
            found = next((p for p in items if p["number"] == variables.get("number")), None)
            return self.send(h, 200, {"data": {"repository": {"pullRequest": self.node(found) if found else None}}})
        return self.send(h, 200, {"errors": [{"message": "the fake does not answer this query"}]})

    def app_jwt_ok(self, token):
        if self.revoked or not token:
            return False
        try:
            claims = jwt.decode(token, self.public_key, algorithms=["RS256"])
        except jwt.PyJWTError:
            return False
        now = time.time()
        return str(claims.get("iss")) == APP_ID and claims["iat"] <= now and claims["exp"] - claims["iat"] <= 600

    def gh_prs(self, project=PROJECT):
        """The pull requests as `gh pr list --json` would print them."""
        out = []
        for item in self.prs.get(project, []):
            raw = {k: item[k] for k in ("number", "title", "url", "headRefName", "baseRefName", "state", "isDraft",
                                        "body", "mergeCommit")}
            raw["files"] = [{"path": p} for p in item["files"]]
            raw["statusCheckRollup"] = list(item["checks"])
            out.append(raw)
        return out


# --- The client -----------------------------------------------------------------------------------------------------

EAS_PROJECT_ID = "f0000000-0000-4000-8000-000000000001"
EXPO_TOKEN = "made-up-robot-token"


class FakeExpoServer(_Server):
    """EAS's GraphQL API (`POST /graphql`), as eas-cli 22.4.0 calls it for `eas build:list`: an app's builds, filtered
    by platform, status and build profile. It answers only the robot token the test gave the service."""

    def __init__(self, project_id=EAS_PROJECT_ID, token=EXPO_TOKEN):
        self.project_id, self.token = project_id, token
        self.builds = []
        self.requests = []
        self.failure = None  # (status, raw body) to answer instead
        super().__init__()

    def build(self, platform, commit, created_at, profile="staging", status="FINISHED"):
        self.builds.append({"id": "b%d" % len(self.builds), "platform": platform, "status": status,
                            "buildProfile": profile, "gitCommitHash": commit, "createdAt": created_at})

    def handle(self, h, method):
        body = json.loads(h.rfile.read(int(h.headers.get("Content-Length") or 0)) or b"{}")
        self.requests.append({"method": method, "path": h.path, "authorization": h.headers.get("Authorization"),
                              "body": body})
        if self.failure:
            return self.send(h, self.failure[0], None, {"Content-Type": "application/json"}, raw=self.failure[1])
        if method != "POST" or h.path != "/graphql":
            return self.send(h, 404, {"errors": [{"message": "no such path"}]})
        if h.headers.get("Authorization") != "Bearer %s" % self.token:
            return self.send(h, 401, {"errors": [{"message": "unauthorized"}]})
        variables = body.get("variables") or {}
        if variables.get("appId") != self.project_id:
            return self.send(h, 200, {"data": None, "errors": [{"message": "app not found"}]})
        wanted = variables.get("filter") or {}
        builds = [b for b in self.builds if all(b[k] == v for k, v in (
            ("platform", wanted.get("platform")), ("status", wanted.get("status")),
            ("buildProfile", wanted.get("buildProfile"))) if v is not None)]
        builds.sort(key=lambda b: b["createdAt"], reverse=True)
        start = variables.get("offset") or 0
        page = builds[start:start + (variables.get("limit") or 50)]
        self.send(h, 200, {"data": {"app": {"byId": {"id": self.project_id, "builds": page}}}})

def spec_operations():
    """Every (METHOD, path template) that openapi.yaml documents."""
    with open(SPEC_PATH) as f:
        paths = yaml.safe_load(f)["paths"]
    return {(method.upper(), path) for path, item in paths.items()
            for method in ("get", "put", "post", "delete", "patch") if method in item}


def _template_regex(template):
    return re.compile("^" + re.sub(r"\{[^}]+\}", "[^/]+", template) + "$")


_TEMPLATES = sorted(((m, p, _template_regex(p)) for m, p in spec_operations()), key=lambda t: -len(t[1]))
EXERCISED = set()


def operation_for(method, path):
    for m, template, regex in _TEMPLATES:
        if m == method and regex.match(path):
            return (m, template)
    return None


class ContractClient:
    """A Flask test client whose every response, and every request not marked invalid, must match openapi.yaml."""

    def __init__(self, app, test):
        self.client = app.test_client()
        self.test = test

    def call(self, method, path, token=None, json_body=None, valid_request=True, headers=None, **kwargs):
        headers = dict(headers or {})
        if token is not None:
            headers["Authorization"] = "Bearer %s" % token
        if json_body is not None:
            kwargs["data"] = json.dumps(json_body)
            kwargs["content_type"] = "application/json"
        response = self.client.open(path, method=method, headers=headers, **kwargs)
        copy = Request(EnvironBuilder(path=path, method=method, headers=headers, **kwargs).get_environ())
        request = WerkzeugOpenAPIRequest(copy)
        op = operation_for(method, copy.path)
        self.test.assertIsNotNone(op, "%s %s is not in openapi.yaml" % (method, path))
        EXERCISED.add(op)
        if valid_request:
            SPEC.validate_request(request)
        SPEC.validate_response(request, WerkzeugOpenAPIResponse(response))
        return response

    def get(self, path, **kw):
        return self.call("GET", path, **kw)

    def post(self, path, **kw):
        return self.call("POST", path, **kw)


def sign(raw, secret=WEBHOOK_SECRET):
    return "sha256=" + hmac.new(secret, raw, hashlib.sha256).hexdigest()


def status_path(project=PROJECT):
    return "/projects/%s/status" % project


def concern(doc, ref):
    loop_id, concern_id = ref.split("/")
    loop = next(loop for loop in doc["loops"] if loop["id"] == loop_id)
    return next(c for c in loop["concerns"] if c["id"] == concern_id)


def environment(doc, name):
    return next(e for e in doc["environments"] if e["name"] == name)


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


class ServiceTestCase(unittest.TestCase):
    """A project with a real origin, a fake GitHub that knows alice (a collaborator) and carol (not one), each
    environment's /version, and the service wired to them, with a clock the test moves."""

    max_age_seconds = 20.0
    cache_seconds = 0.0

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="status-test-")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.version = VersionServer()
        self.addCleanup(self.version.close)
        self.marker = os.path.join(self.tmp, "a-command-from-the-repository-ran")
        self.world = World(self.tmp, PROJECT, initial_files(self.version.url, self.marker))
        self.version.serve("/staging/version", self.world.main())
        self.github = FakeGitHubServer(APP_KEY.public_key(), [PROJECT])
        self.addCleanup(self.github.close)
        self.github.users.update({"alice-token": "alice", "carol-token": "carol"})
        self.github.collaborators[PROJECT] = {"alice"}
        self.github.runs[PROJECT] = {}
        self.expo = FakeExpoServer()
        self.addCleanup(self.expo.close)
        self.clock = FakeClock()
        self.settings = self.make_settings()
        self.app = self.make_app()
        self.api = ContractClient(self.app, self)

    def make_settings(self, **changes):
        values = dict(
            projects=frozenset({PROJECT}),
            commit=COMMIT,
            github_app_id=APP_ID,
            github_private_key=APP_PEM,
            webhook_secret=WEBHOOK_SECRET,
            github_api_url=self.github.url,
            github_git_url=self.world.git_root,
            cache_dir=os.path.join(self.tmp, "cache"),
            max_age_seconds=self.max_age_seconds,
            cache_seconds=self.cache_seconds,
            served_timeout_seconds=2.0,
            expo_token=EXPO_TOKEN,
            eas_project_id=EAS_PROJECT_ID,
            expo_api_url=self.expo.url,
        )
        values.update(changes)
        return Settings(**values)

    def make_app(self, settings=None):
        return create_app(settings or self.settings, clock=self.clock, now=lambda: NOW)

    def restart(self, settings=None):
        """A new instance of the service: nothing carried over in memory."""
        self.app = self.make_app(settings)
        self.api = ContractClient(self.app, self)

    def status(self, token="alice-token", expect=200, project=PROJECT):
        response = self.api.get(status_path(project), token=token)
        self.assertEqual(response.status_code, expect, response.get_json())
        return response.get_json()

    def deliver(self, event, payload, secret=WEBHOOK_SECRET, signature=None, valid_request=True):
        raw = json.dumps(payload).encode()
        headers = {"X-GitHub-Event": event, "X-GitHub-Delivery": "d-%d" % len(self.github.requests),
                   "X-Hub-Signature-256": signature or sign(raw, secret)}
        return self.api.post("/webhooks/github", data=raw, content_type="application/json", headers=headers,
                             valid_request=valid_request)

    def push_event(self, project=PROJECT, ref="refs/heads/main"):
        return {"ref": ref, "after": self.world.main(), "repository": {"full_name": project}}

    def pr_event(self, number, action, project=PROJECT):
        return {"action": action, "number": number, "pull_request": {"number": number},
                "repository": {"full_name": project}}

    def open_pr(self, number, branch, files):
        """A branch with one commit, pushed, and its pull request open on GitHub."""
        sha = self.world.commit(files, "Work on %s\n\nConcern: %s" % (branch, branch), branch=branch)
        self.github.pr(number, branch, files=tuple(files))
        self.deliver("pull_request", self.pr_event(number, "opened"))
        return sha

    def merge_pr(self, number, branch, files):
        merge = self.world.merge(branch, number)
        self.github.pr(number, branch, state="MERGED", merge=merge, files=tuple(files))
        self.deliver("pull_request", self.pr_event(number, "closed"))
        return merge
