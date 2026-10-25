"""GitHub, as the notifier sees it: who a caller is (command-center/D28).

A caller is identified with `GET /user` on their own token, which proves who they are and grants nothing else. The
notifier has no GitHub App of its own: it reads nothing from a repository, and it only ever sends a person what
already waits on their own login (README, "Who may register").
"""

import json
import urllib.error
import urllib.request

from .errors import InvalidCredentials, Unavailable

USER_AGENT = "architect-loop-notify"


class GitHub:
    def __init__(self, api_url="https://api.github.com", timeout=10):
        self.api_url = api_url.rstrip("/")
        self.timeout = timeout

    def user_login(self, token):
        request = urllib.request.Request(self.api_url + "/user", headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "User-Agent": USER_AGENT,
            "X-GitHub-Api-Version": "2022-11-28",
        })
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                body = json.loads(response.read() or b"null")
        except urllib.error.HTTPError as error:
            if error.code == 401:
                raise InvalidCredentials("GitHub does not accept this token") from error
            raise Unavailable(f"GitHub answered {error.code} for /user") from error
        except (urllib.error.URLError, OSError, TimeoutError, ValueError) as error:
            raise Unavailable(f"GitHub cannot be reached: {error}") from error
        login = body.get("login") if isinstance(body, dict) else None
        if not isinstance(login, str) or not login:
            raise Unavailable("GitHub's /user named no login")
        return login
