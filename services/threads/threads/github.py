"""GitHub, as threads sees it: who a caller is, and who the project's members are (command-center/D27, D28).

A caller is identified with `GET /user` on their own token, which proves who they are and grants nothing else.
Membership is the repository's collaborators, read with threads' own GitHub App. The app only reads: the one
request here that is not a GET exchanges the app's signed JWT for an installation token.
"""

import json
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime

import jwt

from .errors import InvalidCredentials, Unavailable

USER_AGENT = "architect-loop-threads"
_NEXT = re.compile(r'<([^>]+)>;\s*rel="next"')


class GitHubApp:
    def __init__(self, app_id, private_key, api_url="https://api.github.com", timeout=10, clock=time.time):
        self.app_id = str(app_id) if app_id is not None else None
        self.private_key = private_key
        self.api_url = api_url.rstrip("/")
        self.timeout = timeout
        self.clock = clock
        self._lock = threading.Lock()
        self._installations = {}
        self._tokens = {}

    # The three questions the service asks.

    def user_login(self, token):
        status, body, _ = self._request("GET", "/user", token)
        if status == 401:
            raise InvalidCredentials("GitHub does not accept this token")
        self._expect(status, 200, "/user")
        return body["login"]

    def is_collaborator(self, project, login):
        path = f"/repos/{project}/collaborators/{urllib.parse.quote(login)}"
        status, _, _ = self._as_app("GET", path, project)
        if status == 404:
            return False
        self._expect(status, 204, path)
        return True

    def collaborators(self, project):
        logins = []
        url = f"/repos/{project}/collaborators?per_page=100&affiliation=all"
        while url:
            status, body, headers = self._as_app("GET", url, project)
            self._expect(status, 200, url)
            logins += [user["login"] for user in body]
            match = _NEXT.search(headers.get("Link") or "")
            url = match.group(1) if match else None
        return logins

    # The app's credentials.

    def _as_app(self, method, path, project):
        status, body, headers = self._request(method, path, self._installation_token(project))
        if status == 401:
            # GitHub no longer accepts the cached token; get a new one, once.
            self.forget_tokens()
            status, body, headers = self._request(method, path, self._installation_token(project))
        return status, body, headers

    def forget_tokens(self):
        with self._lock:
            self._tokens.clear()

    def _installation_token(self, project):
        with self._lock:
            token, expires = self._tokens.get(project, (None, 0.0))
            if token and self.clock() < expires - 300:
                return token
            app_jwt = self._app_jwt()
            installation = self._installations.get(project)
            if installation is None:
                status, body, _ = self._request("GET", f"/repos/{project}/installation", app_jwt)
                self._expect(status, 200, "the app's installation")
                installation = self._installations[project] = body["id"]
            path = f"/app/installations/{installation}/access_tokens"
            status, body, _ = self._request("POST", path, app_jwt)
            self._expect(status, 201, "an installation token")
            expires = datetime.strptime(body["expires_at"], "%Y-%m-%dT%H:%M:%S%z").timestamp()
            self._tokens[project] = (body["token"], min(expires, self.clock() + 3600))
            return body["token"]

    def _app_jwt(self):
        if not self.app_id or not self.private_key:
            raise Unavailable("threads' GitHub App is not configured")
        now = int(self.clock())
        try:
            return jwt.encode({"iat": now - 60, "exp": now + 540, "iss": self.app_id}, self.private_key,
                              algorithm="RS256")
        except (ValueError, TypeError) as error:
            raise Unavailable(f"threads' GitHub App key cannot sign: {error}") from error

    # HTTP.

    def _request(self, method, path, token):
        url = path if path.startswith("http") else self.api_url + path
        request = urllib.request.Request(url, method=method, headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "User-Agent": USER_AGENT,
            "X-GitHub-Api-Version": "2022-11-28",
        })
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return response.status, _json(response.read()), response.headers
        except urllib.error.HTTPError as error:
            if error.code >= 500 or error.code == 429:
                raise Unavailable(f"GitHub answered {error.code} for {path}") from error
            return error.code, _json(error.read()), error.headers
        except (urllib.error.URLError, OSError, TimeoutError) as error:
            raise Unavailable(f"GitHub cannot be reached: {error}") from error

    @staticmethod
    def _expect(status, wanted, what):
        if status != wanted:
            raise Unavailable(f"GitHub answered {status} for {what}")


def _json(data):
    if not data:
        return None
    try:
        return json.loads(data)
    except ValueError:
        return None
