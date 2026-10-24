"""What goes out, and when (C2, C3).

Each read of a project's status document takes the queue items that wait on a person (`waits_on`), leaving out the
items of a loop in the backlog, which carry no notifications (proposal §5). Then:

- **A blocking item**, one whose `unblocks` names at least one concern (notifications D2), is pushed at once to the
  devices of the person it waits on, once: a mark keyed by the item's id and that person is taken first, so the next
  read, or another instance, never pushes it again. During the person's quiet hours it is not pushed and not
  marked, so the first read after they end pushes it if it still stands. An item that waits on someone else later
  is pushed to them too, since the mark names the person.
- **Everything else waits for the digest**: one push at the time the person chose, saying how many items wait on
  them, which opens the inbox (notifications D1). It is marked by the person and their local date, so it goes out
  once a day, and not at all on a day nothing waits.

The first read of a project with no baseline in the store (a new store, or one just wiped) marks every blocking
item already standing as seen without pushing it: those are not changes, and a wipe must not push them all again
(G4). A read that fails pushes nothing; a push that Expo did not take gives its mark back, so the next read tries
again. A ticket that Expo refused for any other reason keeps its mark: it is logged, never retried every read.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

from .errors import Unavailable
from .schedule import digest_due, in_quiet_hours
from .store import settings_or_default

log = logging.getLogger(__name__)

INBOX = "/inbox"
SETTINGS_SCREEN = "/notifications"


def timestamp(now):
    return now.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def is_blocking(item):
    """notifications D2: an item is blocking when its `unblocks` names at least one concern."""
    return bool(item.get("unblocks"))


def waiting(doc):
    """The queue items that wait on someone, without those of a loop in the backlog."""
    quiet = {loop.get("id") for loop in doc.get("loops") or [] if loop.get("state") == "backlog"}
    return [item for item in doc["queue"]
            if isinstance(item, dict) and isinstance(item.get("waits_on"), str) and item["waits_on"]
            and isinstance(item.get("id"), str) and item.get("loop") not in quiet]


def push_key(item):
    return f"push|{item['id']}|{item['waits_on']}"


def digest_key(login, day):
    return f"digest|{login}|{day.isoformat()}"


def _unblocks(concerns):
    first = concerns[0]
    return first if len(concerns) == 1 else f"{first} and {len(concerns) - 1} more"


def item_message(project, item):
    return {"title": item.get("title") or item["id"],
            "body": f"Waits on you, and unblocks {_unblocks(item['unblocks'])}.",
            "data": {"url": INBOX, "project": project, "item": item["id"]},
            "priority": "high"}


def digest_message(project, count, day):
    return {"title": "Needs you",
            "body": "1 item waits on you." if count == 1 else f"{count} items wait on you.",
            "data": {"url": INBOX, "project": project, "digest": day.isoformat()}}


def test_message(project):
    return {"title": "Test notification",
            "body": "Notifications from the command center reach this device.",
            "data": {"url": SETTINGS_SCREEN, "project": project, "test": True}}


@dataclass
class Read:
    """What one read of a project's queue did, for the log and the tests."""

    project: str
    ok: bool = True
    error: str | None = None
    baseline: bool = False
    pushed: list = field(default_factory=list)      # (item id, login, devices reached)
    deferred: list = field(default_factory=list)    # (item id, login): in their quiet hours
    digests: list = field(default_factory=list)     # (login, local date, items counted, devices reached)


@dataclass(frozen=True)
class Delivery:
    devices: int
    accepted: int
    gone: int


class Notifier:
    def __init__(self, projects, store, status, expo, clock=None):
        self.projects = sorted(projects)
        self.store = store
        self.status = status
        self.expo = expo
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def tick(self):
        """Read each project's queue once, and send what is due."""
        now = self.clock()
        reads = []
        for project in self.projects:
            try:
                doc = self.status.document(project)
            except Unavailable as error:
                log.warning("%s: not read, nothing pushed: %s", project, error)
                reads.append(Read(project, ok=False, error=str(error)))
                continue
            reads.append(self.read(project, doc, now))
        return reads

    def read(self, project, doc, now):
        at = timestamp(now)
        items = waiting(doc)
        result = Read(project)
        blocking = [item for item in items if is_blocking(item)]
        if not self.store.has_baseline(project):
            for item in blocking:
                self.store.mark(project, push_key(item), at)
            self.store.set_baseline(project, at)
            result.baseline = True
            log.info("%s: first read; %d blocking items already standing are marked as seen", project,
                     len(blocking))
        else:
            for item in blocking:
                self._push(project, item, now, at, result)
        self._digests(project, items, now, at, result)
        return result

    def _push(self, project, item, now, at, result):
        login = item["waits_on"]
        if in_quiet_hours(settings_or_default(self.store, project, login), now):
            result.deferred.append((item["id"], login))
            return
        key = push_key(item)
        if not self.store.mark(project, key, at):
            return
        try:
            delivery = self.deliver(project, login, item_message(project, item))
        except Unavailable as error:
            self.store.unmark(project, key)
            log.warning("%s: %s for %s not pushed, tried again next read: %s", project, item["id"], login, error)
            return
        result.pushed.append((item["id"], login, delivery.accepted))
        log.info("%s: pushed %s to %s on %d of %d devices", project, item["id"], login, delivery.accepted,
                 delivery.devices)

    def _digests(self, project, items, now, at, result):
        for login in self.store.logins(project):
            settings = settings_or_default(self.store, project, login)
            day = digest_due(settings, now)
            if day is None or in_quiet_hours(settings, now):
                continue
            key = digest_key(login, day)
            if not self.store.mark(project, key, at):
                continue
            count = sum(1 for item in items if item["waits_on"] == login)
            if count == 0:
                result.digests.append((login, day.isoformat(), 0, 0))
                continue
            try:
                delivery = self.deliver(project, login, digest_message(project, count, day))
            except Unavailable as error:
                self.store.unmark(project, key)
                log.warning("%s: %s's digest not sent, tried again next read: %s", project, login, error)
                continue
            result.digests.append((login, day.isoformat(), count, delivery.accepted))

    def deliver(self, project, login, message):
        """Send one message to every device of the person, and forget the devices Expo says are gone. Unavailable
        when Expo took none of it."""
        devices = self.store.devices_of(project, login)
        if not devices:
            return Delivery(0, 0, 0)
        tickets = self.expo.send([{"to": d.token, "sound": "default", **message} for d in devices])
        gone = 0
        for device, ticket in zip(devices, tickets):
            if ticket.device_gone:
                self.store.remove(project, device.id)
                gone += 1
            elif not ticket.ok:
                log.warning("%s: Expo refused a message to %s's %s device: %s %s", project, login, device.platform,
                            ticket.error, ticket.message)
        return Delivery(len(devices), sum(1 for t in tickets if t.ok), gone)

    def test(self, project, login):
        """A test notification to the person's own devices, and no one else's (C1)."""
        return self.deliver(project, login, test_message(project))
