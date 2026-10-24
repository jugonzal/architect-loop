"""The notifier's store on Firestore: a database of its own, `notify`, in its environment's project, shared by every
instance of the service (command-center/D44 and D26).

It implements store.MemoryStore's contract, and runs the same tests (tests/test_store.py). Four collections, each
document id built from its project and key, since neither may hold `/` in an id:

  devices/<project>|<device id>    a device: its login, push token, platform and name, and `owner`, <project>|<login>
  settings/<project>|<login>       what the person saved
  marks/<project>|<key>            a push or digest already sent (or seen when the queue was first read)
  baselines/<project>              when the project's queue was first read

A mark is created, never written over: Firestore refuses to create a document that exists, so of two instances
taking one mark, one gets it. A create that Firestore aborts because others contend for the same document is
looked for and tried again. Every query has one equality filter, so the database needs no index beyond the
single-field ones Firestore keeps by itself.
"""

import random
import time
import urllib.parse
from dataclasses import replace

from google.api_core import exceptions
from google.cloud import firestore

from .errors import Unavailable
from .schedule import PersonSettings
from .store import Device

DEVICES = "devices"
SETTINGS = "settings"
MARKS = "marks"
BASELINES = "baselines"
# A mark whose create was aborted is looked for and tried again, after a random wait up to twice as long each time.
ATTEMPTS = 10
BACKOFF_S = 0.05
BACKOFF_CAP_S = 1.0


def _key(*parts):
    return "|".join(urllib.parse.quote(part, safe="") for part in parts)


def _device(data):
    return Device(id=data["id"], login=data["login"], token=data["token"], platform=data["platform"],
                  name=data.get("name"), registered_at=data["registered_at"])


class FirestoreStore:
    def __init__(self, database, project=None, client=None):
        self.database = database
        self.client = client or firestore.Client(project=project, database=database)

    def _doc(self, collection, *parts):
        return self.client.collection(collection).document(_key(*parts))

    # Devices.

    def register(self, project, device):
        ref = self._doc(DEVICES, project, device.id)

        @firestore.transactional
        def put(transaction):
            snapshot = ref.get(transaction=transaction)
            stored = device
            if snapshot.exists and snapshot.get("login") == device.login:
                stored = replace(device, registered_at=snapshot.get("registered_at"))
            transaction.set(ref, {**stored.__dict__, "project": project, "owner": _key(project, device.login)})
            return stored

        return put(self.client.transaction())

    def device(self, project, ident):
        snapshot = self._doc(DEVICES, project, ident).get()
        return _device(snapshot.to_dict()) if snapshot.exists else None

    def _where(self, collection, field, value):
        query = self.client.collection(collection).where(filter=firestore.FieldFilter(field, "==", value))
        return [snapshot.to_dict() for snapshot in query.stream()]

    def devices_of(self, project, login):
        found = [_device(data) for data in self._where(DEVICES, "owner", _key(project, login))]
        return sorted(found, key=lambda d: (d.registered_at, d.id))

    def logins(self, project):
        return sorted({data["login"] for data in self._where(DEVICES, "project", project)})

    def remove(self, project, ident):
        ref = self._doc(DEVICES, project, ident)
        if not ref.get().exists:
            return False
        ref.delete()
        return True

    # Settings.

    def settings_of(self, project, login):
        snapshot = self._doc(SETTINGS, project, login).get()
        if not snapshot.exists:
            return None
        data = snapshot.to_dict()
        quiet = data.get("quiet_hours")
        return PersonSettings(timezone=data["timezone"], digest_time=data.get("digest_time"),
                              quiet_hours=(quiet["start"], quiet["end"]) if quiet else None)

    def put_settings(self, project, login, settings):
        self._doc(SETTINGS, project, login).set({"project": project, "login": login, **settings.to_json()})
        return settings

    # Marks.

    def mark(self, project, key, at):
        ref = self._doc(MARKS, project, key)
        for attempt in range(ATTEMPTS):
            try:
                ref.create({"project": project, "key": key, "at": at})
                return True
            except exceptions.AlreadyExists:
                return False
            except exceptions.Aborted:
                # Creates of one document at once contend: the emulator, and Firestore under load, abort the losers
                # instead of answering AlreadyExists. An aborted create wrote nothing, so look, and try again.
                if ref.get().exists:
                    return False
                time.sleep(min(BACKOFF_CAP_S, BACKOFF_S * 2 ** attempt) * random.random())
        raise Unavailable(f"Firestore kept aborting the mark {key}")

    def unmark(self, project, key):
        self._doc(MARKS, project, key).delete()

    def marked(self, project, key):
        return self._doc(MARKS, project, key).get().exists

    # The first read of a project's queue.

    def has_baseline(self, project):
        return self._doc(BASELINES, project).get().exists

    def set_baseline(self, project, at):
        try:
            self._doc(BASELINES, project).create({"project": project, "at": at})
        except exceptions.AlreadyExists:
            pass
