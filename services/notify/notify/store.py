"""The notifier's store: each person's devices and settings, and a mark for each push and digest already sent, so
that each goes out once (command-center/D26). It holds no loop's state: wiping it loses devices, settings and the
marks, and the first read of the queue after that marks what stands as already seen instead of pushing it again
(G4). That first read takes its marks before it records the baseline, so two instances reading at once can only
both mark, never push what stood before.

Two stores keep one contract, tested by tests/test_store.py on both: `MemoryStore`, for tests and local runs, and
`FirestoreStore` (firestore_store.py), the notifier's own Firestore database on Cloud Run (command-center/D44).
Every record is keyed by project (command-center/D18).

A mark is taken before its push is sent, by a write that succeeds only for the first to make it, so two instances
reading the same queue never both push one item. A push that Expo did not accept gives its mark back, so the next
read tries again.
"""

import hashlib
import threading
from dataclasses import dataclass, replace

from .schedule import PersonSettings

PLATFORMS = ("ios", "android")


def device_id(token):
    """A device's id: from its push token, so registering one token again is the same device, whoever registers
    it. The token itself is never in a URL or a response."""
    return hashlib.sha256(token.encode()).hexdigest()[:32]


@dataclass(frozen=True)
class Device:
    id: str
    login: str
    token: str
    platform: str
    name: str | None
    registered_at: str

    def to_json(self):
        return {"id": self.id, "platform": self.platform, "name": self.name, "registered_at": self.registered_at}


class MemoryStore:
    """Everything in this process's memory, gone on restart."""

    def __init__(self):
        self._lock = threading.Lock()
        self._devices = {}
        self._settings = {}
        self._marks = {}
        self._baselines = {}

    # Devices.

    def register(self, project, device):
        """Keep the device for its login. A token registered before, by anyone, moves to this login, so it is only
        ever one person's device. Its first registration time is kept when the same person registers it again."""
        with self._lock:
            earlier = self._devices.get((project, device.id))
            if earlier is not None and earlier.login == device.login:
                device = replace(device, registered_at=earlier.registered_at)
            self._devices[(project, device.id)] = device
            return device

    def device(self, project, ident):
        with self._lock:
            return self._devices.get((project, ident))

    def devices_of(self, project, login):
        with self._lock:
            found = [d for (p, _), d in self._devices.items() if p == project and d.login == login]
        return sorted(found, key=lambda d: (d.registered_at, d.id))

    def logins(self, project):
        """Every login with at least one device in the project."""
        with self._lock:
            return sorted({d.login for (p, _), d in self._devices.items() if p == project})

    def remove(self, project, ident):
        with self._lock:
            return self._devices.pop((project, ident), None) is not None

    # Settings.

    def settings_of(self, project, login):
        """What the person saved, or None."""
        with self._lock:
            return self._settings.get((project, login))

    def put_settings(self, project, login, settings):
        with self._lock:
            self._settings[(project, login)] = settings
            return settings

    # Marks: each push and digest sent once.

    def mark(self, project, key, at):
        """Take the mark `key`: True for the first to take it, False once anyone has."""
        with self._lock:
            if (project, key) in self._marks:
                return False
            self._marks[(project, key)] = at
            return True

    def unmark(self, project, key):
        with self._lock:
            self._marks.pop((project, key), None)

    def marked(self, project, key):
        with self._lock:
            return (project, key) in self._marks

    # The first read of a project's queue, after which what is new in it is pushed.

    def has_baseline(self, project):
        with self._lock:
            return project in self._baselines

    def set_baseline(self, project, at):
        with self._lock:
            self._baselines.setdefault(project, at)


def settings_or_default(store, project, login):
    return store.settings_of(project, login) or PersonSettings()
