"""Which commit each app platform's builds were made from, for anyone to read (command-center/D57, D79).

`GET /apps/{channel}/{platform}/version` answers `{"commit": "<sha>"}`, the deploy convention (command-center/D32),
with the commit EAS recorded for the platform's latest finished build of the channel's build profile in
`app/eas.json`. So `sh scripts/gcp/served.sh` reads a platform's row like a service's, and `/loop-status` and the
status service read it without an Expo login.

EAS is asked the way eas-cli 22.4.0 asks for `eas build:list` (app-served D2): a GraphQL query of the app's builds,
filtered by platform, status and profile, with an Expo robot user's token. Each platform stands alone: one with no
finished build, or whose latest finished build records no commit, is not served (404), and an EAS that cannot be
read is unavailable (503). Neither ever answers an older commit. An answer from EAS is reused for a minute.
"""

import json
import re
import threading
import urllib.error
import urllib.request

from .errors import Unavailable

PLATFORMS = {"android": "ANDROID", "ios": "IOS"}
CHANNEL = re.compile(r"[a-z0-9][a-z0-9-]{0,62}")
COMMIT = re.compile(r"[0-9a-f]{7,40}")
REUSE_SECONDS = 60.0
PAGE = 50
USER_AGENT = "architect-loop-status"

# The query eas-cli 22.4.0 sends for `eas build:list` (build/graphql/queries/BuildQuery.js, ViewBuildsOnApp), with
# only the fields this route reads.
QUERY = """query ViewBuildsOnApp($appId: String!, $offset: Int!, $limit: Int!, $filter: BuildFilter) {
  app {
    byId(appId: $appId) {
      id
      builds(offset: $offset, limit: $limit, filter: $filter) {
        id
        platform
        status
        buildProfile
        gitCommitHash
        createdAt
      }
    }
  }
}"""


class NotServed(Exception):
    """The platform has no build whose commit can be answered (404)."""


class Apps:
    """The commit each (channel, platform) serves, with EAS's answer reused for REUSE_SECONDS on `clock`."""

    def __init__(self, settings, clock):
        self.settings, self.clock = settings, clock
        self._answers = {}
        self._lock = threading.Lock()

    @staticmethod
    def known(channel, platform):
        return bool(CHANNEL.fullmatch(channel)) and platform in PLATFORMS

    def commit(self, channel, platform):
        if not self.settings.expo_token or not self.settings.eas_project_id:
            missing = "STATUS_EXPO_TOKEN" if not self.settings.expo_token else "STATUS_EAS_PROJECT_ID"
            raise Unavailable("not configured: %s is not set, so EAS's builds cannot be read" % missing)
        key = (channel, platform)
        now = self.clock()
        with self._lock:
            hit = self._answers.get(key)
        if hit and now < hit[1]:
            builds = hit[0]
        else:
            builds = self._builds(channel, PLATFORMS[platform])
            with self._lock:
                self._answers[key] = (builds, now + REUSE_SECONDS)
        return latest_commit(builds, channel, platform)

    def _builds(self, profile, platform):
        body = json.dumps({"query": QUERY, "variables": {
            "appId": self.settings.eas_project_id, "offset": 0, "limit": PAGE,
            "filter": {"platform": platform, "status": "FINISHED", "buildProfile": profile}}}).encode()
        request = urllib.request.Request(self.settings.expo_api_url + "/graphql", data=body, method="POST", headers={
            "Authorization": "Bearer %s" % self.settings.expo_token, "Content-Type": "application/json",
            "Accept": "application/json", "User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(request, timeout=self.settings.served_timeout_seconds) as response:
                raw = response.read()
        except urllib.error.HTTPError as error:
            raise Unavailable("EAS answered %d for the %s builds of profile %s" % (
                error.code, platform.lower(), profile)) from None
        except (urllib.error.URLError, OSError) as error:
            raise Unavailable("EAS cannot be reached: %s" % getattr(error, "reason", error)) from None
        try:
            payload = json.loads(raw)
        except ValueError:
            raise Unavailable("EAS did not answer JSON for the builds of profile %s" % profile) from None
        errors = payload.get("errors") if isinstance(payload, dict) else None
        app = ((payload.get("data") or {}).get("app") or {}).get("byId") if isinstance(payload, dict) else None
        if errors or not isinstance(app, dict) or not isinstance(app.get("builds"), list):
            reason = "; ".join(str(e.get("message", e)) for e in errors if isinstance(e, dict)) if errors else \
                "no builds list in its answer"
            raise Unavailable("EAS did not list the builds of profile %s: %s" % (profile, reason))
        return app["builds"]


def latest_commit(builds, profile, platform):
    """The commit of the newest finished build of `profile` on `platform`, or NotServed saying why."""
    wanted = PLATFORMS[platform]
    finished = [b for b in builds if isinstance(b, dict) and b.get("platform") == wanted
                and b.get("status") == "FINISHED" and b.get("buildProfile") == profile]
    if not finished:
        raise NotServed("no finished %s build for profile %s" % (platform, profile))
    latest = max(finished, key=lambda b: str(b.get("createdAt") or ""))
    commit = latest.get("gitCommitHash")
    if not isinstance(commit, str) or not COMMIT.fullmatch(commit):
        raise NotServed("the latest finished %s build for profile %s records no commit" % (platform, profile))
    return commit
