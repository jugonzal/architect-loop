"""Expo's push service, which delivers to each device through APNs or FCM with the credentials the Expo project
holds (command-center/D7). The notifier sends it messages addressed to Expo push tokens, at most 100 in one request,
and reads one ticket per message back, in the same order.

A ticket that says DeviceNotRegistered means the app was uninstalled or the token is stale: the notifier forgets
that device. Receipts, which say whether APNs or FCM finally delivered a message, are not read: a ticket says only
that Expo accepted it.
"""

import json
import urllib.error
import urllib.request
from dataclasses import dataclass

from .errors import Unavailable

USER_AGENT = "architect-loop-notify"
MAX_MESSAGES = 100


@dataclass(frozen=True)
class Ticket:
    ok: bool
    error: str | None = None
    message: str | None = None

    @property
    def device_gone(self):
        return self.error == "DeviceNotRegistered"


class Expo:
    def __init__(self, push_url="https://exp.host/--/api/v2/push/send", access_token=None, timeout=15):
        self.push_url = push_url
        self.access_token = access_token
        self.timeout = timeout

    def send(self, messages):
        """One Ticket per message, in order; Unavailable when Expo took none of them."""
        tickets = []
        for start in range(0, len(messages), MAX_MESSAGES):
            tickets += self._send(messages[start:start + MAX_MESSAGES])
        return tickets

    def _send(self, messages):
        headers = {"Accept": "application/json", "Content-Type": "application/json", "User-Agent": USER_AGENT}
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        request = urllib.request.Request(self.push_url, data=json.dumps(messages).encode(), method="POST",
                                         headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                body = json.loads(response.read())
        except urllib.error.HTTPError as error:
            raise Unavailable(f"Expo answered {error.code}: {_errors(error)}") from error
        except (urllib.error.URLError, OSError, TimeoutError, ValueError) as error:
            raise Unavailable(f"Expo cannot be reached: {error}") from error
        data = body.get("data") if isinstance(body, dict) else None
        if not isinstance(data, list) or len(data) != len(messages):
            raise Unavailable("Expo did not answer one ticket for each message")
        tickets = []
        for ticket in data:
            ticket = ticket if isinstance(ticket, dict) else {}
            if ticket.get("status") == "ok":
                tickets.append(Ticket(ok=True))
            else:
                details = ticket.get("details") if isinstance(ticket.get("details"), dict) else {}
                tickets.append(Ticket(ok=False, error=details.get("error"), message=ticket.get("message")))
        return tickets


def _errors(error):
    try:
        body = json.loads(error.read())
        return "; ".join(e.get("message", "") for e in body.get("errors", [])) or "no message"
    except (ValueError, AttributeError, TypeError):
        return "no message"
