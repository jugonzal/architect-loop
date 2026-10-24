"""The local harness's fakes (command-center/local-harness, per command-center/D53), in one process:

- GitHub, on FAKE_GITHUB_PORT (8711): the REST calls the services make (`GET /user`, collaborator checks,
  installation tokens, contents, tags, pull requests and reviews), the project's repository over git's smart HTTP,
  and the webhooks GitHub delivers to each service's app.
- Cloud Run's job launch, on FAKE_RUN_PORT (8712): `POST /v2/projects/<p>/locations/<r>/jobs/<job>:run` starts one
  execution of the job in a container of its own, through the Docker Engine API on /var/run/docker.sock.
- The metadata server, on FAKE_METADATA_PORT (8713): the service identity's access tokens and ID tokens, signed
  with a key made when it starts, and that key set at `/oauth2/v3/certs`.
- Port forwards (FAKE_FORWARDS): the host reaches the services, which sit on a network with no route off the
  machine, only through these.

It stands in for what the services rely on, and proves their wiring, not GitHub, Cloud Run or Google. Every call it
answers is logged, and `GET /_local/calls` on the GitHub port lists them, so the smoke test can tell what the
services asked. Its config comes from the environment harness.py gives it. Standard library only, with git and
openssl.
"""

import asyncio
import base64
import datetime
import hashlib
import hmac
import http.client
import io
import json
import os
import re
import secrets
import socket
import subprocess
import sys
import tarfile
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ISSUER = "https://accounts.google.com"  # the ID tokens say Google issued them; only the local threads trusts the key
KID = "local-harness"


def utc(seconds_from_now=0):
    moment = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=seconds_from_now)
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def b64url(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


class Fakes:
    """What the fakes know and remember: users, tokens, pull requests, reviews and every call."""

    def __init__(self, config):
        self.project = config["project"]
        self.users = dict(config.get("users", {}))  # token -> login
        self.collaborators = list(config.get("collaborators", []))
        self.installation = str(config.get("installation", "1"))
        self.git_root = config["git_root"]
        self.public_url = config.get("public_url", "http://localhost:8711").rstrip("/")
        self.webhooks = list(config.get("webhooks", []))
        self.jobs = dict(config.get("jobs", {}))
        self.identity = config.get("identity", "")
        self.docker = config.get("docker", "/var/run/docker.sock")
        self.key = config.get("key")  # the metadata server's signing key, a PEM file
        self.lock = threading.Lock()
        self.installation_tokens = {}  # token -> permissions
        self.access_tokens = set()
        self.pulls, self.reviews, self.calls = [], [], []

    @property
    def repository(self):
        return os.path.join(self.git_root, *self.project.split("/")) + ".git"

    def log(self, fake, method, path, **details):
        with self.lock:
            self.calls.append({"fake": fake, "method": method, "path": path, "at": utc(), **details})

    def git(self, *args):
        result = subprocess.run(["git", "--git-dir", self.repository, *args], capture_output=True, text=True)
        return result.returncode, result.stdout.strip()

    # The metadata server's key.

    def signing_key(self):
        if self.key is None:
            handle, self.key = tempfile.mkstemp(prefix="identity-", suffix=".pem")
            os.close(handle)
            subprocess.run(["openssl", "genrsa", "-out", self.key, "2048"], check=True, capture_output=True)
        return self.key

    def key_set(self):
        out = subprocess.run(["openssl", "rsa", "-in", self.signing_key(), "-noout", "-modulus"], check=True,
                             capture_output=True, text=True).stdout
        modulus = bytes.fromhex(out.strip().split("=", 1)[1])
        return {"keys": [{"kty": "RSA", "alg": "RS256", "use": "sig", "kid": KID, "n": b64url(modulus),
                          "e": b64url((65537).to_bytes(3, "big"))}]}

    def id_token(self, audience):
        now = int(time.time())
        header = {"alg": "RS256", "kid": KID, "typ": "JWT"}
        claims = {"iss": ISSUER, "aud": audience, "azp": self.identity, "sub": "1" * 21, "email": self.identity,
                  "email_verified": True, "iat": now, "exp": now + 3600}
        signing_input = ".".join(b64url(json.dumps(part, separators=(",", ":")).encode()) for part in (header, claims))
        signature = subprocess.run(["openssl", "dgst", "-sha256", "-sign", self.signing_key()],
                                   input=signing_input.encode(), check=True, capture_output=True).stdout
        return f"{signing_input}.{b64url(signature)}"

    # Webhooks, delivered the way GitHub delivers them to an app: signed with each app's own secret.

    def deliver(self, event, payload):
        def send():
            data = json.dumps(payload).encode()
            for hook in self.webhooks:
                signature = "sha256=" + hmac.new(hook["secret"].encode(), data, hashlib.sha256).hexdigest()
                request = urllib.request.Request(hook["url"], data=data, method="POST", headers={
                    "Content-Type": "application/json", "X-GitHub-Event": event,
                    "X-GitHub-Delivery": secrets.token_hex(16), "X-Hub-Signature-256": signature})
                try:
                    with urllib.request.urlopen(request, timeout=10) as response:
                        status = response.status
                except urllib.error.HTTPError as error:
                    status = error.code
                except OSError as error:
                    status = str(error)
                self.log("github", "DELIVER", hook["url"], event=event, status=status)

        threading.Thread(target=send, daemon=True).start()


class Handler(BaseHTTPRequestHandler):
    fakes: Fakes
    fake = ""
    protocol_version = "HTTP/1.1"

    def log_message(self, format, *args):
        sys.stderr.write("%s %s\n" % (self.fake, format % args))

    def answer(self, status, document=None, headers=None, raw=None):
        body = raw if raw is not None else (b"" if document is None else json.dumps(document).encode())
        self.send_response(status)
        if raw is None and document is not None:
            self.send_header("Content-Type", "application/json")
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def body(self):
        if self.headers.get("Transfer-Encoding", "").lower() == "chunked":
            data = b""
            while True:
                size = int(self.rfile.readline().split(b";")[0].strip() or b"0", 16)
                if size == 0:
                    self.rfile.readline()
                    return data
                data += self.rfile.read(size)
                self.rfile.readline()
        return self.rfile.read(int(self.headers.get("Content-Length") or 0))

    def json_body(self):
        try:
            return json.loads(self.body() or b"null")
        except ValueError:
            return None

    def bearer(self):
        scheme, _, token = (self.headers.get("Authorization") or "").partition(" ")
        return token.strip() if scheme.lower() in ("bearer", "token") else ""

    def split(self):
        parts = urllib.parse.urlsplit(self.path)
        return parts.path, urllib.parse.parse_qs(parts.query)

    def do_GET(self):
        self.route("GET")

    def do_POST(self):
        self.route("POST")

    def do_PATCH(self):
        self.route("PATCH")


class GitHub(Handler):
    fake = "github"
    REPO = re.compile(r"^/repos/(?P<owner>[^/]+)/(?P<repo>[^/]+)(?P<rest>/.*)?$")

    def route(self, method):
        path, query = self.split()
        if path == "/_local/calls":
            with self.fakes.lock:
                return self.answer(200, {"calls": list(self.fakes.calls), "pulls": list(self.fakes.pulls)})
        if re.match(r"^/[^/]+/[^/]+\.git/", path):
            return self.git_http(method, path)
        self.fakes.log("github", method, path, caller=self.caller_kind())
        if method == "GET" and path == "/user":
            login = self.fakes.users.get(self.bearer())
            return self.answer(200, {"login": login, "id": self.user_id(login)}) if login else self.unauthorized()
        match = re.match(r"^/users/(?P<login>[^/]+)$", path)
        if method == "GET" and match:
            login = urllib.parse.unquote(match["login"])
            return self.answer(200, {"login": login, "id": self.user_id(login),
                                     "type": "Bot" if login.endswith("[bot]") else "User"})
        match = re.match(r"^/app/installations/(?P<id>[^/]+)/access_tokens$", path)
        if method == "POST" and match:
            return self.mint(match["id"])
        match = self.REPO.match(path)
        if not match or f"{match['owner']}/{match['repo']}" != self.fakes.project:
            return self.answer(404, {"message": "Not Found"})
        return self.repository(method, match["rest"] or "", query)

    def caller_kind(self):
        token = self.bearer()
        if token in self.fakes.users:
            return "user"
        if token in self.fakes.installation_tokens:
            return "installation"
        return "app" if token.count(".") == 2 else "anonymous"

    @staticmethod
    def user_id(login):
        return int(hashlib.sha256(login.encode()).hexdigest()[:8], 16)

    def unauthorized(self):
        return self.answer(401, {"message": "Bad credentials"})

    def mint(self, installation):
        """An installation token for whichever app asks: each service has its own app (command-center/D27), and here
        every app is installed, under whatever installation id its config names."""
        if self.caller_kind() != "app":
            return self.unauthorized()  # minting takes the app's signed JWT, never a token
        request = self.json_body() or {}
        permissions = request.get("permissions") or {"metadata": "read", "contents": "read", "pull_requests": "read"}
        token = "ghs_local_" + secrets.token_hex(16)
        with self.fakes.lock:
            self.fakes.installation_tokens[token] = dict(permissions)
        self.fakes.log("github", "MINT", f"/app/installations/{installation}/access_tokens", permissions=permissions)
        return self.answer(201, {"token": token, "expires_at": utc(3600), "permissions": permissions})

    def may(self, permission, level="read"):
        """Whether the caller may do this: a user token reads, an installation token does what it was minted for."""
        token = self.bearer()
        if token in self.fakes.users:
            return level == "read"
        granted = self.fakes.installation_tokens.get(token)
        return granted is not None and (granted.get(permission) == "write" or level == "read" and permission in granted)

    def repository(self, method, rest, query):
        if method == "GET" and rest == "/installation":
            return self.answer(200, {"id": int(self.fakes.installation)}) if self.caller_kind() == "app" \
                else self.unauthorized()
        if not self.may("metadata"):
            return self.unauthorized()
        match = re.match(r"^/collaborators(?:/(?P<login>[^/]+))?$", rest)
        if method == "GET" and match:
            if match["login"]:
                return self.answer(204 if urllib.parse.unquote(match["login"]) in self.fakes.collaborators else 404)
            return self.answer(200, [{"login": login, "id": self.user_id(login)} for login in self.fakes.collaborators])
        match = re.match(r"^/contents/(?P<path>.+)$", rest)
        if method == "GET" and match:
            return self.contents(urllib.parse.unquote(match["path"]), (query.get("ref") or ["main"])[0])
        match = re.match(r"^/git/ref/tags/(?P<tag>.+)$", rest)
        if method == "GET" and match:
            tag = urllib.parse.unquote(match["tag"])
            code, sha = self.fakes.git("rev-parse", "--verify", "--quiet", f"refs/tags/{tag}")
            if code:
                return self.answer(404, {"message": "Not Found"})
            return self.answer(200, {"ref": f"refs/tags/{tag}", "object": {"sha": sha}})
        if rest == "/pulls":
            return self.list_pulls(query) if method == "GET" else self.open_pull() if method == "POST" else \
                self.answer(405)
        match = re.match(r"^/pulls/(?P<number>\d+)(?P<reviews>/reviews)?$", rest)
        if match:
            pull = next((p for p in self.fakes.pulls if p["number"] == int(match["number"])), None)
            if pull is None:
                return self.answer(404, {"message": "Not Found"})
            if match["reviews"] and method == "POST":
                return self.review(pull)
            if method == "PATCH":
                return self.edit_pull(pull)
            if method == "GET":
                return self.answer(200, pull)
        return self.answer(404, {"message": "Not Found"})

    def contents(self, path, ref):
        code, sha = self.fakes.git("rev-parse", "--verify", "--quiet", f"{ref}:{path}")
        if code:
            return self.answer(404, {"message": "Not Found"})
        blob = subprocess.run(["git", "--git-dir", self.fakes.repository, "cat-file", "blob", sha],
                              capture_output=True)
        if blob.returncode:
            return self.answer(404, {"message": "Not Found"})
        return self.answer(200, {"type": "file", "encoding": "base64", "path": path, "name": os.path.basename(path),
                                 "sha": sha, "content": base64.b64encode(blob.stdout).decode()})

    def list_pulls(self, query):
        state = (query.get("state") or ["open"])[0]
        head = (query.get("head") or [""])[0]
        page, per_page = int((query.get("page") or ["1"])[0]), int((query.get("per_page") or ["30"])[0])
        with self.fakes.lock:
            found = [p for p in self.fakes.pulls if state == "all" or p["state"] == state]
        if head:
            found = [p for p in found if p["head"]["label"] == head or p["head"]["ref"] == head]
        return self.answer(200, found[(page - 1) * per_page:page * per_page])

    def open_pull(self):
        if not self.may("pull_requests", "write"):
            return self.answer(403, {"message": "Resource not accessible by integration"})
        request = self.json_body() or {}
        head = str(request.get("head") or "").split(":")[-1]
        code, sha = self.fakes.git("rev-parse", "--verify", "--quiet", f"refs/heads/{head}")
        if not head or code:
            return self.answer(422, {"message": "Validation Failed", "errors": [{"field": "head", "code": "invalid"}]})
        owner = self.fakes.project.split("/")[0]
        with self.fakes.lock:
            if any(p["head"]["ref"] == head and p["state"] == "open" for p in self.fakes.pulls):
                return self.answer(422, {"message": f"A pull request already exists for {owner}:{head}."})
            number = len(self.fakes.pulls) + 1
            pull = {"number": number, "state": "open", "title": request.get("title") or head,
                    "body": request.get("body") or "", "html_url": f"{self.fakes.public_url}/{self.fakes.project}"
                                                                   f"/pull/{number}",
                    "head": {"ref": head, "sha": sha, "label": f"{owner}:{head}"},
                    "base": {"ref": request.get("base") or "main"}, "user": {"login": "app"}}
            self.fakes.pulls.append(pull)
        self.fakes.deliver("pull_request", {"action": "opened", "number": number, "pull_request": pull,
                                            "repository": {"full_name": self.fakes.project}})
        return self.answer(201, pull)

    def edit_pull(self, pull):
        if not self.may("pull_requests", "write"):
            return self.answer(403, {"message": "Resource not accessible by integration"})
        request = self.json_body() or {}
        with self.fakes.lock:
            for key in ("body", "title"):
                if key in request:
                    pull[key] = request[key]
        return self.answer(200, pull)

    def review(self, pull):
        login = self.fakes.users.get(self.bearer())
        if login not in self.fakes.collaborators:
            return self.answer(403, {"message": "Must have push access to review"})
        request = self.json_body() or {}
        with self.fakes.lock:
            review = {"id": len(self.fakes.reviews) + 1, "body": request.get("body") or "",
                      "state": {"APPROVE": "approved", "REQUEST_CHANGES": "changes_requested"}.get(
                          request.get("event"), "commented"),
                      "user": {"login": login}, "author_association": "COLLABORATOR",
                      "html_url": f"{pull['html_url']}#pullrequestreview-{len(self.fakes.reviews) + 1}"}
            self.fakes.reviews.append(review)
        self.fakes.deliver("pull_request_review", {"action": "submitted", "review": review, "pull_request": pull,
                                                   "repository": {"full_name": self.fakes.project}})
        return self.answer(200, review)

    def git_http(self, method, path):
        """The repository over git's smart HTTP, through git http-backend. It asks for no credentials."""
        parts = urllib.parse.urlsplit(self.path)
        env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "GIT_PROJECT_ROOT": self.fakes.git_root,
               "GIT_HTTP_EXPORT_ALL": "1", "PATH_INFO": urllib.parse.unquote(parts.path), "QUERY_STRING": parts.query,
               "REQUEST_METHOD": method, "CONTENT_TYPE": self.headers.get("Content-Type", ""),
               "REMOTE_USER": "local", "REMOTE_ADDR": self.client_address[0]}
        for header, variable in (("Content-Encoding", "HTTP_CONTENT_ENCODING"), ("Git-Protocol", "GIT_PROTOCOL")):
            if self.headers.get(header):
                env[variable] = self.headers[header]
        data = self.body() if method == "POST" else b""
        env["CONTENT_LENGTH"] = str(len(data))
        out = subprocess.run(["git", "http-backend"], input=data, env=env, capture_output=True).stdout
        head, separator, payload = out.partition(b"\r\n\r\n")
        if not separator:
            head, _, payload = out.partition(b"\n\n")
        status, headers = 200, {}
        for line in head.decode(errors="replace").splitlines():
            key, _, value = line.partition(":")
            if key.lower() == "status":
                status = int(value.split()[0])
            elif key:
                headers[key.strip()] = value.strip()
        if path.endswith("/git-receive-pack"):
            self.fakes.log("github", "PUSH", path, status=status)
        return self.answer(status, headers=headers, raw=payload)


class CloudRun(Handler):
    fake = "run"
    RUN = re.compile(r"^/v2/projects/(?P<project>[^/]+)/locations/(?P<region>[^/]+)/jobs/(?P<job>[^/:]+):run$")

    def route(self, method):
        path, _ = self.split()
        self.fakes.log("run", method, path)
        match = self.RUN.match(path)
        if method != "POST" or not match:
            return self.answer(404, {"error": {"code": 404, "message": "not found"}})
        if self.bearer() not in self.fakes.access_tokens:
            return self.answer(401, {"error": {"code": 401, "message": "the service identity's token is missing"}})
        job = self.fakes.jobs.get(match["job"])
        if job is None:
            return self.answer(404, {"error": {"code": 404, "message": f"no job {match['job']}"}})
        overrides = (self.json_body() or {}).get("overrides") or {}
        env = dict(job.get("env", {}))
        for container in overrides.get("containerOverrides") or []:
            env.update({item["name"]: item.get("value", "") for item in container.get("env") or []})
        execution = f"{match['job']}-{secrets.token_hex(3)}"
        try:
            container = start_container(self.fakes, job, execution, env)
        except (OSError, RuntimeError) as error:
            return self.answer(500, {"error": {"code": 500, "message": f"the job's container did not start: {error}"}})
        name = f"projects/{match['project']}/locations/{match['region']}/jobs/{match['job']}/executions/{execution}"
        self.fakes.log("run", "EXECUTE", path, execution=execution, container=container,
                       session=env.get("RUNNER_SESSION_ID"))
        return self.answer(200, {"name": f"projects/{match['project']}/locations/{match['region']}/operations/"
                                         f"{secrets.token_hex(8)}", "metadata": {"name": name}})


class Metadata(Handler):
    fake = "metadata"
    ACCOUNT = "/computeMetadata/v1/instance/service-accounts/default"

    def route(self, method):
        path, query = self.split()
        self.fakes.log("metadata", method, path)
        if path == "/oauth2/v3/certs":
            return self.answer(200, self.fakes.key_set())
        if self.headers.get("Metadata-Flavor") != "Google":
            return self.answer(403, raw=b"Missing Metadata-Flavor:Google header.")
        if path == f"{self.ACCOUNT}/token":
            token = "ya29.local-" + secrets.token_hex(16)
            with self.fakes.lock:
                self.fakes.access_tokens.add(token)
            return self.answer(200, {"access_token": token, "expires_in": 3599, "token_type": "Bearer"})
        if path == f"{self.ACCOUNT}/identity":
            audience = (query.get("audience") or [""])[0]
            if not audience:
                return self.answer(400, raw=b"non-empty audience parameter required")
            return self.answer(200, raw=self.fakes.id_token(audience).encode())
        if path == f"{self.ACCOUNT}/email":
            return self.answer(200, raw=self.fakes.identity.encode())
        return self.answer(404, raw=b"not found")


# The Docker Engine API, over its unix socket.

class UnixConnection(http.client.HTTPConnection):
    def __init__(self, socket_path):
        super().__init__("localhost", timeout=60)
        self.socket_path = socket_path

    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.connect(self.socket_path)


def docker(fakes, method, path, body=None, content_type="application/json"):
    connection = UnixConnection(fakes.docker)
    data = json.dumps(body).encode() if content_type == "application/json" and body is not None else body
    connection.request(method, path, body=data, headers={"Content-Type": content_type} if data is not None else {})
    response = connection.getresponse()
    raw = response.read()
    connection.close()
    if response.status >= 300:
        raise RuntimeError(f"docker {method} {path} answered {response.status}: {raw[:300]!r}")
    return json.loads(raw) if raw else None


def start_container(fakes, job, execution, env):
    """One execution of a job: a container of its own, on the job's network only, with the job's files added."""
    name = f"architect-loop-local-{execution}"
    created = docker(fakes, "POST", f"/containers/create?name={name}", {
        "Image": job["image"], "Cmd": job["command"], "Env": [f"{k}={v}" for k, v in sorted(env.items())],
        "Labels": {"architect-loop-local": "1", "architect-loop-local.execution": execution,
                   "architect-loop-local.session": env.get("RUNNER_SESSION_ID", "")},
        "HostConfig": {"NetworkMode": job["network"]}})
    files = job.get("files") or {}
    if files:
        archive = io.BytesIO()
        with tarfile.open(fileobj=archive, mode="w") as tar:
            for target, source in sorted(files.items()):
                directory = ""
                for part in target.strip("/").split("/")[:-1]:
                    directory = f"{directory}/{part}" if directory else part
                    info = tarfile.TarInfo(directory)
                    info.type, info.mode = tarfile.DIRTYPE, 0o755
                    tar.addfile(info)
                tar.add(source, arcname=target.strip("/"), filter=_readable)
        docker(fakes, "PUT", f"/containers/{created['Id']}/archive?path=/", archive.getvalue(), "application/x-tar")
    docker(fakes, "POST", f"/containers/{created['Id']}/start")
    return name


def _readable(info):
    info.uid = info.gid = 0
    info.uname = info.gname = "root"
    info.mode = 0o644
    return info


# Forwards from the host's published ports to the services, which have no route off the machine.

async def forward(listen_port, target):
    host, _, port = target.rpartition(":")

    async def pipe(reader, writer):
        try:
            while data := await reader.read(65536):
                writer.write(data)
                await writer.drain()
        except (ConnectionError, OSError):
            pass
        finally:
            writer.close()

    async def handle(client_reader, client_writer):
        try:
            reader, writer = await asyncio.open_connection(host, int(port))
        except OSError:
            client_writer.close()
            return
        await asyncio.gather(pipe(client_reader, writer), pipe(reader, client_writer))

    server = await asyncio.start_server(handle, "0.0.0.0", listen_port)
    async with server:
        await server.serve_forever()


def serve(handler, fakes, port):
    server = ThreadingHTTPServer(("0.0.0.0", port), type(handler.__name__, (handler,), {"fakes": fakes}))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def main():
    config = json.loads(os.environ["FAKE_CONFIG"])
    fakes = Fakes(config)
    fakes.signing_key()
    servers = [serve(GitHub, fakes, config.get("github_port", 8711)),
               serve(CloudRun, fakes, config.get("run_port", 8712)),
               serve(Metadata, fakes, config.get("metadata_port", 8713))]
    print(f"fakes: GitHub, Cloud Run and the metadata server on {[s.server_address[1] for s in servers]}; "
          f"forwards {config.get('forwards', {})}", flush=True)

    async def forwards():
        await asyncio.gather(*(forward(int(port), target) for port, target in config.get("forwards", {}).items()))

    if config.get("forwards"):
        asyncio.run(forwards())
    else:
        threading.Event().wait()


if __name__ == "__main__":
    main()
