"""The local harness's fakes (scripts/local/fakes/server.py), run in this process on free ports against a scratch
repository: the GitHub calls the services make, git over smart HTTP, webhooks, the metadata server's tokens, and
Cloud Run's job launch against a fake Docker Engine. Standard library only, with git and openssl; no network.

Run from the repository root: python3 -m unittest discover -s scripts/local/tests -v
"""

import base64
import hashlib
import hmac
import importlib.util
import io
import json
import os
import shutil
import socketserver
import subprocess
import tarfile
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
spec = importlib.util.spec_from_file_location("fakes_server", os.path.join(ROOT, "scripts", "local", "fakes",
                                                                           "server.py"))
server = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server)

PROJECT = "example/project"
USERS = {"tok-sponsor": "sponsor", "tok-member": "member", "tok-outsider": "outsider"}
JWT = "e30.e30.c2ln"  # shaped like the app's signed JWT, which the fake does not check
GIT = ["-c", "user.name=t", "-c", "user.email=t@example.com"]


def call(method, url, token=None, body=None, headers=None):
    data = None if body is None else json.dumps(body).encode()
    request = urllib.request.Request(url, data=data, method=method, headers={
        **({"Authorization": f"Bearer {token}"} if token else {}), **(headers or {})})
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            raw = response.read()
            status = response.status
    except urllib.error.HTTPError as error:
        status, raw = error.code, error.read()
    try:
        return status, json.loads(raw) if raw else None
    except ValueError:
        return status, raw.decode()


class FakesTest(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.scratch, True)
        work = os.path.join(self.scratch, "work")
        subprocess.run(["git", "init", "--quiet", "-b", "main", work], check=True)
        os.makedirs(os.path.join(work, "docs", "loops", "demo"))
        with open(os.path.join(work, "docs", "loops", "demo", "one.md"), "w") as f:
            f.write("# One\n")
        subprocess.run(["git", "-C", work, *GIT, "add", "."], check=True)
        subprocess.run(["git", "-C", work, *GIT, "commit", "--quiet", "-m", "one"], check=True)
        subprocess.run(["git", "-C", work, *GIT, "tag", "v0.1.0"], check=True)
        root = os.path.join(self.scratch, "git")
        bare = os.path.join(root, "example", "project.git")
        subprocess.run(["git", "init", "--quiet", "--bare", "--initial-branch=main", bare], check=True)
        subprocess.run(["git", "-C", work, "push", "--quiet", bare, "main", "refs/tags/*:refs/tags/*"], check=True)

        self.deliveries = []
        outer = self

        class Receiver(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                body = self.rfile.read(int(self.headers["Content-Length"]))
                outer.deliveries.append(({k.lower(): v for k, v in self.headers.items()}, body))
                self.send_response(200)
                self.send_header("Content-Length", "0")
                self.end_headers()

        receiver = ThreadingHTTPServer(("127.0.0.1", 0), Receiver)
        threading.Thread(target=receiver.serve_forever, daemon=True).start()
        self.addCleanup(receiver.server_close)
        self.addCleanup(receiver.shutdown)

        self.docker = FakeDocker(os.path.join(self.scratch, "docker.sock"))
        self.addCleanup(self.docker.close)
        sdk = os.path.join(self.scratch, "fakesdk.py")
        with open(sdk, "w") as f:
            f.write("def client(options): ...\n")
        self.fakes = server.Fakes({
            "project": PROJECT, "users": USERS, "collaborators": ["sponsor", "member"], "git_root": root,
            "public_url": "http://localhost:8711", "identity": "runner@demo-local.iam.gserviceaccount.com",
            "webhooks": [{"url": f"http://127.0.0.1:{receiver.server_address[1]}/webhooks/github", "secret": "s3"}],
            "jobs": {"runner-session": {"image": "runner:abc", "command": ["python", "-m", "runner", "job"],
                                        "network": "internal", "env": {"A": "1"},
                                        "files": {"/opt/local/fakesdk.py": sdk}}},
            "docker": self.docker.path})
        self.bare, self.work = bare, work
        self.urls = {}
        for name, handler in (("github", server.GitHub), ("run", server.CloudRun), ("metadata", server.Metadata)):
            httpd = server.serve(handler, self.fakes, 0)
            self.addCleanup(httpd.server_close)
            self.addCleanup(httpd.shutdown)
            self.urls[name] = f"http://127.0.0.1:{httpd.server_address[1]}"

    def github(self, method, path, token=None, body=None):
        return call(method, self.urls["github"] + path, token, body)

    def mint(self, permissions=None):
        status, answer = self.github("POST", "/app/installations/42/access_tokens", JWT,
                                     {"permissions": permissions} if permissions else None)
        self.assertEqual(status, 201)
        return answer["token"]

    # GitHub.

    def test_get_user_names_the_tokens_owner(self):
        self.assertEqual(self.github("GET", "/user", "tok-member")[1]["login"], "member")
        self.assertEqual(self.github("GET", "/user", "tok-unknown")[0], 401)

    def test_installation_tokens_take_the_apps_jwt(self):
        self.assertEqual(self.github("POST", "/app/installations/42/access_tokens", "tok-member")[0], 401)
        token = self.mint()
        self.assertTrue(token.startswith("ghs_local_"))
        self.assertEqual(self.github("GET", f"/repos/{PROJECT}/installation", JWT)[1], {"id": 1})

    def test_collaborators(self):
        token = self.mint()
        self.assertEqual(self.github("GET", f"/repos/{PROJECT}/collaborators/member", token)[0], 204)
        self.assertEqual(self.github("GET", f"/repos/{PROJECT}/collaborators/outsider", token)[0], 404)
        self.assertEqual(self.github("GET", f"/repos/{PROJECT}/collaborators/member")[0], 401)
        logins = [u["login"] for u in self.github("GET", f"/repos/{PROJECT}/collaborators?per_page=100", token)[1]]
        self.assertEqual(logins, ["sponsor", "member"])

    def test_contents_and_tags_come_from_the_repository(self):
        token = self.mint()
        status, answer = self.github("GET", f"/repos/{PROJECT}/contents/docs/loops/demo/one.md?ref=main", token)
        self.assertEqual((status, base64.b64decode(answer["content"])), (200, b"# One\n"))
        self.assertEqual(self.github("GET", f"/repos/{PROJECT}/contents/docs/loops/demo/two.md?ref=main", token)[0],
                         404)
        self.assertEqual(self.github("GET", f"/repos/{PROJECT}/git/ref/tags/v0.1.0", token)[0], 200)
        self.assertEqual(self.github("GET", f"/repos/{PROJECT}/git/ref/tags/v9.9.9", token)[0], 404)
        self.assertEqual(self.github("GET", "/repos/other/project/contents/x", token)[0], 404)

    def test_git_clones_and_pushes_over_smart_http(self):
        clone = os.path.join(self.scratch, "clone")
        subprocess.run(["git", "clone", "--quiet", f"{self.urls['github']}/{PROJECT}.git", clone], check=True)
        self.assertTrue(os.path.exists(os.path.join(clone, "docs", "loops", "demo", "one.md")))
        subprocess.run(["git", "-C", clone, "switch", "--quiet", "-c", "demo/one"], check=True)
        with open(os.path.join(clone, "two.md"), "w") as f:
            f.write("two\n")
        subprocess.run(["git", "-C", clone, *GIT, "add", "two.md"], check=True)
        subprocess.run(["git", "-C", clone, *GIT, "commit", "--quiet", "-m", "two"], check=True)
        subprocess.run(["git", "-C", clone, "push", "--quiet", "origin", "demo/one"], check=True)
        pushed = subprocess.run(["git", "--git-dir", self.bare, "rev-parse", "demo/one"], capture_output=True)
        self.assertEqual(pushed.returncode, 0)
        self.assertIn(("github", "PUSH"), [(c["fake"], c["method"]) for c in self.fakes.calls])

    def push_branch(self, branch):
        subprocess.run(["git", "--git-dir", self.bare, "branch", branch, "main"], check=True)

    def test_a_pull_request_needs_a_pushed_branch_and_a_token_that_writes(self):
        self.push_branch("demo/one")
        reader = self.mint()
        writer = self.mint({"metadata": "read", "contents": "write", "pull_requests": "write"})
        request = {"title": "t", "head": "demo/one", "base": "main", "body": "b"}
        self.assertEqual(self.github("POST", f"/repos/{PROJECT}/pulls", reader, request)[0], 403)
        self.assertEqual(self.github("POST", f"/repos/{PROJECT}/pulls", writer, dict(request, head="nope"))[0], 422)
        status, pull = self.github("POST", f"/repos/{PROJECT}/pulls", writer, request)
        self.assertEqual((status, pull["number"], pull["html_url"]),
                         (201, 1, f"http://localhost:8711/{PROJECT}/pull/1"))
        self.assertEqual(self.github("POST", f"/repos/{PROJECT}/pulls", writer, request)[0], 422)
        found = self.github("GET", f"/repos/{PROJECT}/pulls?state=open&head=example:demo/one&per_page=100&page=1",
                            reader)[1]
        self.assertEqual([p["number"] for p in found], [1])
        self.assertEqual(self.github("GET", f"/repos/{PROJECT}/pulls?state=open&head=example:other", reader)[1], [])
        self.assertEqual(self.github("PATCH", f"/repos/{PROJECT}/pulls/1", writer, {"body": "b2"})[1]["body"], "b2")

    def test_a_review_is_delivered_as_a_signed_webhook(self):
        self.push_branch("demo/one")
        writer = self.mint({"metadata": "read", "pull_requests": "write"})
        self.github("POST", f"/repos/{PROJECT}/pulls", writer, {"head": "demo/one", "body": "Concern: demo/one"})
        self.assertEqual(self.github("POST", f"/repos/{PROJECT}/pulls/1/reviews", "tok-outsider",
                                     {"body": "no"})[0], 403)
        status, review = self.github("POST", f"/repos/{PROJECT}/pulls/1/reviews", "tok-member",
                                     {"body": "Looks right", "event": "COMMENT"})
        self.assertEqual((status, review["state"]), (200, "commented"))
        for _ in range(100):
            if len(self.deliveries) >= 2:
                break
            threading.Event().wait(0.05)
        events = {headers["x-github-event"]: (headers, body) for headers, body in self.deliveries}
        headers, body = events["pull_request_review"]
        expected = "sha256=" + hmac.new(b"s3", body, hashlib.sha256).hexdigest()
        self.assertEqual(headers["x-hub-signature-256"], expected)
        payload = json.loads(body)
        self.assertEqual((payload["action"], payload["review"]["body"], payload["pull_request"]["body"]),
                         ("submitted", "Looks right", "Concern: demo/one"))
        self.assertIn("pull_request", events)

    # The metadata server.

    def metadata(self, path, flavor=True):
        return call("GET", self.urls["metadata"] + path, headers={"Metadata-Flavor": "Google"} if flavor else {})

    def test_tokens_need_the_metadata_flavor_header(self):
        account = "/computeMetadata/v1/instance/service-accounts/default"
        self.assertEqual(self.metadata(f"{account}/token", flavor=False)[0], 403)
        status, answer = self.metadata(f"{account}/token")
        self.assertEqual(status, 200)
        self.assertIn(answer["access_token"], self.fakes.access_tokens)
        self.assertEqual(self.metadata(f"{account}/email")[1], "runner@demo-local.iam.gserviceaccount.com")

    def test_an_id_token_verifies_against_the_key_set(self):
        status, token = self.metadata("/computeMetadata/v1/instance/service-accounts/default/identity"
                                      "?audience=http://threads:8080&format=full")
        self.assertEqual(status, 200)
        header, claims, signature = token.split(".")
        [key] = self.metadata("/oauth2/v3/certs", flavor=False)[1]["keys"]
        self.assertEqual(json.loads(unpad(header))["kid"], key["kid"])

        def number(text):
            return int.from_bytes(unpad(text), "big")

        n, e = number(key["n"]), number(key["e"])
        decoded = pow(number(signature), e, n).to_bytes((n.bit_length() + 7) // 8, "big")
        digest = hashlib.sha256(f"{header}.{claims}".encode()).digest()
        # PKCS#1 v1.5: 0x00 0x01 0xff... 0x00, then SHA-256's DigestInfo and the digest.
        self.assertTrue(decoded.startswith(b"\x00\x01\xff"))
        self.assertTrue(decoded.endswith(bytes.fromhex("3031300d060960864801650304020105000420") + digest))
        body = json.loads(unpad(claims))
        self.assertEqual((body["aud"], body["email"], body["email_verified"], body["iss"]),
                         ("http://threads:8080", "runner@demo-local.iam.gserviceaccount.com", True,
                          "https://accounts.google.com"))

    # Cloud Run.

    def test_a_job_runs_in_a_container_of_its_own_with_the_sessions_id(self):
        run = f"{self.urls['run']}/v2/projects/demo-local/locations/us-east1/jobs/runner-session:run"
        body = {"overrides": {"containerOverrides": [{"env": [{"name": "RUNNER_SESSION_ID", "value": "s1"}]}],
                              "taskCount": 1}}
        self.assertEqual(call("POST", run, "ya29.unknown", body)[0], 401)
        token = self.metadata("/computeMetadata/v1/instance/service-accounts/default/token")[1]["access_token"]
        missing = run.replace("runner-session", "other")
        self.assertEqual(call("POST", missing, token, body)[0], 404)
        status, operation = call("POST", run, token, body)
        self.assertEqual(status, 200)
        self.assertIn("/jobs/runner-session/executions/runner-session-", operation["metadata"]["name"])
        [create, archive, start] = self.docker.requests
        self.assertTrue(create["path"].startswith("/containers/create?name=architect-loop-local-runner-session-"))
        self.assertEqual(create["body"]["Env"], ["A=1", "RUNNER_SESSION_ID=s1"])
        self.assertEqual(create["body"]["HostConfig"], {"NetworkMode": "internal"})
        self.assertEqual(create["body"]["Labels"]["architect-loop-local.session"], "s1")
        self.assertEqual(archive["path"], "/containers/c1/archive?path=/")
        with tarfile.open(fileobj=io.BytesIO(archive["raw"])) as tar:
            self.assertEqual(tar.extractfile("opt/local/fakesdk.py").read(), b"def client(options): ...\n")
        self.assertEqual(start["path"], "/containers/c1/start")


def unpad(text):
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


class FakeDocker:
    """The Docker Engine API on a unix socket, answering create, archive and start."""

    def __init__(self, path):
        self.path, self.requests = path, []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def address_string(self):
                return "docker"

            def handle_one(self):
                raw = self.rfile.read(int(self.headers.get("Content-Length") or 0))
                is_json = self.headers.get("Content-Type") == "application/json"
                outer.requests.append({"method": self.command, "path": self.path, "raw": raw,
                                       "body": json.loads(raw) if is_json and raw else None})
                answer = json.dumps({"Id": "c1"}).encode() if "/create" in self.path else b""
                self.send_response(201 if "/create" in self.path else 200 if self.command == "PUT" else 204)
                self.send_header("Content-Length", str(len(answer)))
                self.end_headers()
                self.wfile.write(answer)

            do_POST = do_PUT = handle_one

        class Server(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
            daemon_threads = True

        self.server = Server(path, Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()


if __name__ == "__main__":
    unittest.main()
