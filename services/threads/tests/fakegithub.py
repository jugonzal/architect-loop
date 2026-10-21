"""A fake GitHub REST API over real HTTP, for testing the real GitHub client: GET /user, the app's JWT and its
installation token, and the collaborator endpoints. It records every request it receives.
"""

import json
import re
import threading
import time
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

APP_ID = "123456"
INSTALLATION_ID = 42


def new_key():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                            serialization.NoEncryption()).decode()
    return key, pem


class FakeGitHubServer:
    def __init__(self, app_public_key, repo="jugonzal/architect-loop"):
        self.public_key = app_public_key
        self.repo = repo
        self.users = {}
        self.collaborators = []
        self.requests = []
        self.installation_tokens = []
        self.fail_with = None
        server = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                server.handle(self, "GET")

            def do_POST(self):
                server.handle(self, "POST")

            def do_PUT(self):
                server.handle(self, "PUT")

            def do_PATCH(self):
                server.handle(self, "PATCH")

            def do_DELETE(self):
                server.handle(self, "DELETE")

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.httpd.server_address[1]}"
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()

    def handle(self, h, method):
        length = int(h.headers.get("Content-Length") or 0)
        body = h.rfile.read(length) if length else b""
        auth = h.headers.get("Authorization", "")
        path, _, query = h.path.partition("?")
        self.requests.append((method, path))
        if self.fail_with:
            return self.send(h, self.fail_with, {"message": "fake outage"})
        if h.headers.get("Accept") != "application/vnd.github+json":
            return self.send(h, 415, {"message": "wrong Accept"})
        token = auth[len("Bearer "):] if auth.startswith("Bearer ") else None

        if method == "GET" and path == "/user":
            if token in self.users:
                return self.send(h, 200, {"login": self.users[token], "id": 1})
            return self.send(h, 401, {"message": "Bad credentials"})

        if path == f"/repos/{self.repo}/installation" and method == "GET":
            if not self.app_jwt_ok(token):
                return self.send(h, 401, {"message": "A JSON web token could not be decoded"})
            return self.send(h, 200, {"id": INSTALLATION_ID})

        if path == f"/app/installations/{INSTALLATION_ID}/access_tokens" and method == "POST":
            if not self.app_jwt_ok(token):
                return self.send(h, 401, {"message": "A JSON web token could not be decoded"})
            issued = f"ghs_fake{len(self.installation_tokens)}"
            self.installation_tokens.append(issued)
            expires = (datetime.now(timezone.utc) + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
            return self.send(h, 201, {"token": issued, "expires_at": expires})

        if token not in self.installation_tokens:
            return self.send(h, 401, {"message": "Bad credentials"})

        match = re.fullmatch(rf"/repos/{re.escape(self.repo)}/collaborators/([^/]+)", path)
        if match and method == "GET":
            return self.send(h, 204 if match.group(1) in self.collaborators else 404, None)

        if path == f"/repos/{self.repo}/collaborators" and method == "GET":
            params = dict(p.split("=", 1) for p in query.split("&") if "=" in p)
            page, per_page = int(params.get("page", 1)), int(params.get("per_page", 30))
            chunk = self.collaborators[(page - 1) * per_page:page * per_page]
            headers = {}
            if page * per_page < len(self.collaborators):
                headers["Link"] = (f'<{self.url}{path}?per_page={per_page}&page={page + 1}>; rel="next", '
                                   f'<{self.url}{path}?per_page={per_page}&page=99>; rel="last"')
            return self.send(h, 200, [{"login": login, "id": i} for i, login in enumerate(chunk)], headers)

        return self.send(h, 404, {"message": "Not Found"})

    def app_jwt_ok(self, token):
        try:
            claims = jwt.decode(token, self.public_key, algorithms=["RS256"])
        except jwt.PyJWTError:
            return False
        now = time.time()
        return str(claims.get("iss")) == APP_ID and claims["iat"] <= now and claims["exp"] - claims["iat"] <= 600

    def send(self, h, status, payload, headers=None):
        data = b"" if payload is None else json.dumps(payload).encode()
        h.send_response(status)
        for name, value in (headers or {}).items():
            h.send_header(name, value)
        if payload is not None:
            h.send_header("Content-Type", "application/json")
        h.send_header("Content-Length", str(len(data)))
        h.end_headers()
        h.wfile.write(data)
