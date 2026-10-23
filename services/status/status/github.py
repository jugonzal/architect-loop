"""GitHub, as the status service sees it (command-center/D27, D28).

Callers are identified with `GET /user` on their own token, which proves who they are and grants nothing else.
Everything else is read with the service's own GitHub App, which only reads: whether a caller collaborates on the
project, the project's pull requests, the workflow runs on main's head, and, for a repository other than the
project, its default branch and how two of its commits compare. The one request here that is not a GET or a
GraphQL query exchanges the app's signed JWT for an installation token.

Pull requests are read with GraphQL, the API `gh pr list` uses, and returned in the shape `gh pr list --json`
prints them, so the derivation's own normalize_pr reads the service's and the terminal's alike.
"""

import json
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime

import jwt

from .errors import InvalidCredentials, Unavailable

USER_AGENT = "architect-loop-status"
PR_LIMIT = 300  # as many as `gh pr list --limit 300` reads, which loop-status's gather runs

_PR_FIELDS = """
      number title url headRefName baseRefName state isDraft body
      mergeCommit { oid }
      files(first: 100) { nodes { path } }
      commits(last: 1) { nodes { commit { statusCheckRollup { contexts(first: 100) { nodes {
        __typename
        ... on CheckRun { name status conclusion }
        ... on StatusContext { context state }
      } } } } } }
"""
LIST_QUERY = """query($owner: String!, $name: String!, $first: Int!, $after: String) {
  repository(owner: $owner, name: $name) {
    pullRequests(first: $first, after: $after, orderBy: {field: CREATED_AT, direction: DESC}) {
      pageInfo { hasNextPage endCursor }
      nodes {%s}
    }
  }
}""" % _PR_FIELDS
ONE_QUERY = """query($owner: String!, $name: String!, $number: Int!) {
  repository(owner: $owner, name: $name) {
    pullRequest(number: $number) {%s}
  }
}""" % _PR_FIELDS


def gh_shape(node):
    """A pull request from the GraphQL API, in the shape `gh pr list --json <loop-status's fields>` prints it."""
    raw = {key: node.get(key) for key in ("number", "title", "url", "headRefName", "baseRefName", "state",
                                          "isDraft", "body", "mergeCommit")}
    raw["files"] = [{"path": f["path"]} for f in ((node.get("files") or {}).get("nodes") or []) if f]
    commits = (node.get("commits") or {}).get("nodes") or []
    rollup = (commits[-1].get("commit") or {}).get("statusCheckRollup") if commits else None
    raw["statusCheckRollup"] = [c for c in (((rollup or {}).get("contexts") or {}).get("nodes") or []) if c]
    return raw


class GitHubApp:
    def __init__(self, app_id, private_key, api_url="https://api.github.com", timeout=20, clock=time.time):
        self.app_id = str(app_id) if app_id is not None else None
        self.private_key = private_key
        self.api_url = api_url.rstrip("/")
        self.timeout = timeout
        self.clock = clock
        self._lock = threading.Lock()
        self._installations = {}
        self._tokens = {}

    # Who is calling.

    def user_login(self, token):
        status, body, _ = self._request("GET", "/user", token)
        if status == 401:
            raise InvalidCredentials("GitHub does not accept this token")
        self._expect(status, 200, "/user")
        return body["login"]

    def is_collaborator(self, project, login):
        path = "/repos/%s/collaborators/%s" % (project, urllib.parse.quote(login))
        status, _, _ = self._as_app("GET", path, project)
        if status == 404:
            return False
        self._expect(status, 204, path)
        return True

    # The facts GitHub's API holds.

    def pull_requests(self, project, limit=PR_LIMIT, page=100):
        """The newest `limit` pull requests, in every state, as gh prints them."""
        owner, name = project.split("/", 1)
        found, after = [], None
        while len(found) < limit:
            data = self._graphql(project, LIST_QUERY, {"owner": owner, "name": name,
                                                       "first": min(page, limit - len(found)), "after": after})
            connection = data["pullRequests"]
            found += [gh_shape(node) for node in connection.get("nodes") or [] if node]
            info = connection.get("pageInfo") or {}
            if not info.get("hasNextPage"):
                break
            after = info.get("endCursor")
        return found[:limit]

    def pull_request(self, project, number):
        """One pull request by its number, as gh prints it, or None if there is none."""
        owner, name = project.split("/", 1)
        data = self._graphql(project, ONE_QUERY, {"owner": owner, "name": name, "number": int(number)})
        node = data.get("pullRequest")
        return gh_shape(node) if node else None

    def workflow_runs(self, project, sha):
        """The workflow runs on a commit, as `gh run list --commit <sha> --json status,conclusion,workflowName`."""
        path = "/repos/%s/actions/runs?head_sha=%s&per_page=100" % (project, sha)
        status, body, _ = self._as_app("GET", path, project)
        self._expect(status, 200, "the workflow runs on %s" % sha[:12])
        return [{"status": run.get("status"), "conclusion": run.get("conclusion"), "workflowName": run.get("name")}
                for run in (body or {}).get("workflow_runs") or []]

    def default_branch(self, repository):
        status, body, _ = self._as_app("GET", "/repos/%s" % repository, repository)
        self._expect(status, 200, repository)
        return body["default_branch"]

    def compare_status(self, repository, base, head):
        """GitHub's word for how head compares with base: ahead, identical, behind or diverged."""
        path = "/repos/%s/compare/%s...%s" % (repository, base, head)
        status, body, _ = self._as_app("GET", path, repository)
        self._expect(status, 200, path)
        return body["status"]

    # The app's credentials.

    def installation_token(self, project):
        with self._lock:
            token, expires = self._tokens.get(project, (None, 0.0))
            if token and self.clock() < expires - 300:
                return token
            app_jwt = self._app_jwt()
            installation = self._installations.get(project)
            if installation is None:
                status, body, _ = self._request("GET", "/repos/%s/installation" % project, app_jwt)
                self._token_expect(status, 200, project)
                installation = self._installations[project] = body["id"]
            status, body, _ = self._request("POST", "/app/installations/%s/access_tokens" % installation, app_jwt)
            self._token_expect(status, 201, project)
            expires = datetime.strptime(body["expires_at"], "%Y-%m-%dT%H:%M:%S%z").timestamp()
            self._tokens[project] = (body["token"], min(expires, self.clock() + 3600))
            return body["token"]

    def forget_tokens(self):
        with self._lock:
            self._tokens.clear()

    def _as_app(self, method, path, project, body=None):
        status, answer, headers = self._request(method, path, self.installation_token(project), body)
        if status == 401:
            # GitHub no longer accepts the cached token; get a new one, once.
            self.forget_tokens()
            status, answer, headers = self._request(method, path, self.installation_token(project), body)
        return status, answer, headers

    def _graphql(self, project, query, variables):
        status, body, _ = self._as_app("POST", "/graphql", project, {"query": query, "variables": variables})
        self._expect(status, 200, "GraphQL")
        if not isinstance(body, dict) or body.get("errors") or not (body.get("data") or {}).get("repository"):
            errors = (body or {}).get("errors") if isinstance(body, dict) else None
            message = "; ".join(e.get("message", "?") for e in errors or []) or "no repository in the answer"
            raise Unavailable("GitHub's GraphQL API answered for %s: %s" % (project, message))
        return body["data"]["repository"]

    def _app_jwt(self):
        if not self.app_id or not self.private_key:
            raise Unavailable("the status service's GitHub App is not configured")
        now = int(self.clock())
        try:
            return jwt.encode({"iat": now - 60, "exp": now + 540, "iss": self.app_id}, self.private_key,
                              algorithm="RS256")
        except (ValueError, TypeError, jwt.PyJWTError) as error:
            raise Unavailable("the status service's GitHub App key cannot sign: %s" % error) from error

    @staticmethod
    def _token_expect(status, wanted, project):
        if status != wanted:
            raise Unavailable("the status service's GitHub App cannot get a token for %s: GitHub answered %s"
                              % (project, status))

    # HTTP.

    def _request(self, method, path, token, body=None):
        url = path if path.startswith("http") else self.api_url + path
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(url, data=data, method=method, headers={
            "Accept": "application/vnd.github+json",
            "Authorization": "Bearer %s" % token,
            "User-Agent": USER_AGENT,
            "X-GitHub-Api-Version": "2022-11-28",
            **({"Content-Type": "application/json"} if data is not None else {}),
        })
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return response.status, _json(response.read()), response.headers
        except urllib.error.HTTPError as error:
            if error.code >= 500 or error.code == 429:
                raise Unavailable("GitHub answered %d for %s" % (error.code, path.split("?")[0])) from error
            return error.code, _json(error.read()), error.headers
        except (urllib.error.URLError, OSError, TimeoutError) as error:
            raise Unavailable("GitHub cannot be reached: %s" % error) from error

    @staticmethod
    def _expect(status, wanted, what):
        if status != wanted:
            raise Unavailable("GitHub answered %s for %s" % (status, what.split("?")[0]))


def _json(data):
    if not data:
        return None
    try:
        return json.loads(data)
    except ValueError:
        return None
