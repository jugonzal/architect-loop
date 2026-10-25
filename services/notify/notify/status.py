"""The status service, as the notifier reads it: each project's status document, whose queue says what waits on whom
(command-center/status-service, D48).

The notifier calls it with its own Cloud Run service identity (command-center/D28, D66): it asks the metadata
server for a Google-signed ID token whose audience is the status service's URL, and sends it as a bearer token. The
status service trusts that identity (its STATUS_AUDIENCE and STATUS_CALLER_SERVICE_ACCOUNTS). A document that cannot
be read, or that describes another project, is never replaced by an earlier one: the tick pushes nothing from that
read.
"""

import base64
import json
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

from .errors import Unavailable

USER_AGENT = "architect-loop-notify"
# An ID token is good for an hour; one is reused until this long before it expires.
REFRESH_BEFORE_S = 300


def _expiry(token):
    """The `exp` of a JWT, read without checking it: the status service checks it, this only decides when to ask
    for another one."""
    try:
        payload = token.split(".")[1]
        claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
        return float(claims["exp"])
    except (IndexError, KeyError, TypeError, ValueError):
        return 0.0


class MetadataIdentity:
    """ID tokens for this service's own identity, from Cloud Run's metadata server."""

    def __init__(self, metadata_url="http://metadata.google.internal", timeout=5, clock=time.time):
        self.metadata_url = metadata_url.rstrip("/")
        self.timeout = timeout
        self.clock = clock
        self._lock = threading.Lock()
        self._tokens = {}

    def id_token(self, audience):
        with self._lock:
            token, expires = self._tokens.get(audience, (None, 0.0))
            if token and self.clock() < expires - REFRESH_BEFORE_S:
                return token
        query = urllib.parse.urlencode({"audience": audience, "format": "full"})
        url = f"{self.metadata_url}/computeMetadata/v1/instance/service-accounts/default/identity?{query}"
        request = urllib.request.Request(url, headers={"Metadata-Flavor": "Google"})
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                token = response.read().decode().strip()
        except (urllib.error.URLError, OSError, TimeoutError) as error:
            raise Unavailable(f"the metadata server cannot mint an ID token: {error}") from error
        if token.count(".") != 2:
            raise Unavailable("the metadata server did not answer an ID token")
        with self._lock:
            self._tokens[audience] = (token, _expiry(token))
        return token


class StatusService:
    def __init__(self, base_url, identity, timeout=30):
        self.base_url = base_url.rstrip("/")
        self.identity = identity
        self.timeout = timeout

    def document(self, project):
        """The project's status document, or Unavailable."""
        owner, repo = project.split("/", 1)
        url = f"{self.base_url}/projects/{urllib.parse.quote(owner)}/{urllib.parse.quote(repo)}/status"
        request = urllib.request.Request(url, headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {self.identity.id_token(self.base_url)}",
            "User-Agent": USER_AGENT,
        })
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                doc = json.loads(response.read())
        except urllib.error.HTTPError as error:
            raise Unavailable(f"the status service answered {error.code} for {project}") from error
        except (urllib.error.URLError, OSError, TimeoutError, ValueError) as error:
            raise Unavailable(f"the status service cannot be read: {error}") from error
        if not isinstance(doc, dict) or doc.get("project") != project or not isinstance(doc.get("queue"), list):
            raise Unavailable(f"the status service did not answer a status document for {project}")
        return doc
