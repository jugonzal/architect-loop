"""GitHub, as the runner uses it (command-center/D27, D28).

A caller's token is used for one call only, `GET /user`, to learn who is calling. Everything else goes through
the runner's own GitHub App, with an installation token scoped to the one project's repository and to the
permissions that call needs. The app does not exist yet; the owner creates it (see services/runner/README.md).
"""

import base64
import calendar
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Protocol

API = "https://api.github.com"
VERSION_HEADERS = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28",
                   "User-Agent": "architect-loop-runner"}

# What the dispatching service needs: read who collaborates, read pull requests and contents.
SERVICE_PERMISSIONS = {"metadata": "read", "contents": "read", "pull_requests": "read"}
# What a session's job needs: push its branches and open or edit its pull requests. Never `workflows`, so a
# session cannot change the workflow that checks its trailers.
JOB_PERMISSIONS = {"metadata": "read", "contents": "write", "pull_requests": "write"}


class GitHubError(Exception):
    """GitHub answered something the runner cannot act on."""


class GitHub(Protocol):
    def login(self, token: str) -> str | None: ...
    def is_collaborator(self, login: str) -> bool: ...
    def concern_exists(self, loop: str, concern: str) -> bool: ...
    def release_exists(self, tag: str) -> bool: ...
    def loop_exists(self, loop: str) -> bool: ...
    def environments(self) -> list: ...
    def open_pull_requests(self) -> list: ...
    def pull_requests_for_heads(self, heads) -> list: ...
    def set_pull_request_body(self, number: int, body: str) -> None: ...
    def installation_token(self, permissions: dict) -> str: ...
    def bot_user_id(self) -> int: ...


def concern_pull_requests(pulls, concern):
    """The open pull requests linked to a concern, as loop-status links them: its branch, or its trailer."""
    trailer = re.compile(rf"^Concern:\s*{re.escape(concern)}\s*$", re.MULTILINE | re.IGNORECASE)
    return [{"number": p["number"], "url": p["url"], "head": p["head"]} for p in pulls
            if p["head"] == concern or trailer.search(p.get("body") or "")]


ENVIRONMENTS_HEADING = re.compile(r"^#{1,6}\s+(?:\d+(?:\.\d+)*\.?\s+)?Environments\s*$", re.IGNORECASE)


def environments_in(loop_md):
    """The environments LOOP.md names: the first column of the table in its "Environments" section (§3), the names
    `/loop-ship` takes (command-center/D43)."""
    names, inside = [], False
    for line in loop_md.splitlines():
        if re.match(r"^#{1,6}\s", line):
            inside = bool(ENVIRONMENTS_HEADING.match(line.strip()))
            continue
        if not (inside and line.lstrip().startswith("|")):
            continue
        first = line.strip().strip("|").split("|")[0].strip().strip("`*").strip()
        if first and not set(first) <= set("-: ") and first.lower() != "environment":
            names.append(first)
    return names


def urllib_transport(method, url, headers, body=None, timeout=30):
    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, dict(response.headers), response.read()
    except urllib.error.HTTPError as error:
        return error.code, dict(error.headers or {}), error.read()


class AppAuth:
    """Installation tokens for the runner's GitHub App, minted from its private key and cached until near expiry."""

    def __init__(self, app_id, installation_id, private_key, repository, transport=urllib_transport, clock=time.time,
                 api=API):
        self.app_id, self.installation_id, self.private_key = str(app_id), str(installation_id), private_key
        self.repository, self.transport, self.clock, self.api = repository, transport, clock, api
        self._cache = {}

    def jwt(self):
        import jwt  # PyJWT, only where the app's key is used

        now = int(self.clock())
        return jwt.encode({"iat": now - 60, "exp": now + 540, "iss": self.app_id}, self.private_key, algorithm="RS256")

    def token(self, permissions):
        key = tuple(sorted(permissions.items()))
        cached = self._cache.get(key)
        if cached and cached[1] - self.clock() > 300:
            return cached[0]
        body = json.dumps({"repositories": [self.repository], "permissions": dict(permissions)}).encode()
        status, _, data = self.transport(
            "POST", f"{self.api}/app/installations/{self.installation_id}/access_tokens",
            {**VERSION_HEADERS, "Authorization": f"Bearer {self.jwt()}", "Content-Type": "application/json"}, body)
        if status != 201:
            raise GitHubError(f"minting an installation token answered {status}")
        answer = json.loads(data)
        expires = calendar.timegm(time.strptime(answer["expires_at"], "%Y-%m-%dT%H:%M:%SZ"))
        self._cache[key] = (answer["token"], expires)
        return answer["token"]


class RestGitHub:
    def __init__(self, project, app_auth, app_slug="", main_branch="main", transport=urllib_transport, api=API):
        self.owner, self.repo = project.split("/", 1)
        self.app_auth, self.app_slug, self.main_branch = app_auth, app_slug, main_branch
        self.transport, self.api = transport, api

    def _request(self, method, path, token, body=None, scheme="Bearer"):
        headers = {**VERSION_HEADERS, "Authorization": f"{scheme} {token}"}
        data = None
        if body is not None:
            data, headers["Content-Type"] = json.dumps(body).encode(), "application/json"
        status, _, raw = self.transport(method, f"{self.api}{path}", headers, data)
        return status, (json.loads(raw) if raw else None)

    def _as_app(self, method, path, body=None, permissions=SERVICE_PERMISSIONS):
        return self._request(method, path, self.app_auth.token(permissions), body)

    @property
    def _repo(self):
        return f"/repos/{self.owner}/{self.repo}"

    def login(self, token):
        status, answer = self._request("GET", "/user", token)
        if status in (401, 403):
            return None
        if status != 200:
            raise GitHubError(f"GET /user answered {status}")
        return answer["login"]

    def is_collaborator(self, login):
        status, _ = self._as_app("GET", f"{self._repo}/collaborators/{urllib.parse.quote(login)}")
        if status in (204, 404):
            return status == 204
        raise GitHubError(f"the collaborator check answered {status}")

    def _exists(self, path):
        status, _ = self._as_app("GET", path)
        if status in (200, 404):
            return status == 200
        raise GitHubError(f"GET {path} answered {status}")

    def concern_exists(self, loop, concern):
        return self._exists(f"{self._repo}/contents/docs/loops/{loop}/{concern}.md?ref={self.main_branch}")

    def release_exists(self, tag):
        return self._exists(f"{self._repo}/git/ref/tags/{urllib.parse.quote(tag)}")

    def loop_exists(self, loop):
        return self._exists(f"{self._repo}/contents/docs/loops/{loop}/README.md?ref={self.main_branch}")

    def environments(self):
        status, answer = self._as_app("GET", f"{self._repo}/contents/LOOP.md?ref={self.main_branch}")
        if status == 404:
            return []
        if status != 200 or not isinstance(answer, dict) or answer.get("encoding") != "base64":
            raise GitHubError(f"reading LOOP.md answered {status}")
        return environments_in(base64.b64decode(answer["content"]).decode())

    def _pulls(self, query, permissions=SERVICE_PERMISSIONS):
        found, page = [], 1
        while True:
            status, answer = self._as_app("GET", f"{self._repo}/pulls?{query}&per_page=100&page={page}",
                                          permissions=permissions)
            if status != 200:
                raise GitHubError(f"listing pull requests answered {status}")
            found += [{"number": p["number"], "url": p["html_url"], "head": p["head"]["ref"], "body": p.get("body") or ""}
                      for p in answer]
            if len(answer) < 100:
                return found
            page += 1

    def open_pull_requests(self):
        return self._pulls("state=open")

    def pull_requests_for_heads(self, heads):
        found = []
        for head in heads:
            found += self._pulls(f"state=open&head={self.owner}:{urllib.parse.quote(head)}",
                                 permissions=JOB_PERMISSIONS)
        return found

    def set_pull_request_body(self, number, body):
        status, _ = self._as_app("PATCH", f"{self._repo}/pulls/{number}", {"body": body}, JOB_PERMISSIONS)
        if status != 200:
            raise GitHubError(f"editing pull request #{number} answered {status}")

    def installation_token(self, permissions):
        return self.app_auth.token(permissions)

    def bot_user_id(self):
        status, answer = self._as_app("GET", f"/users/{urllib.parse.quote(self.app_slug + '[bot]')}")
        if status != 200:
            raise GitHubError(f"looking up {self.app_slug}[bot] answered {status}")
        return answer["id"]
