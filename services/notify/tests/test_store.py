"""The store's contract, on MemoryStore and on FirestoreStore against the Firestore emulator (command-center/D44).

`StoreContract` runs on both, so the two stores keep one contract and a test added there runs on both. notify.yml
starts the emulator and sets NOTIFY_FIRESTORE_TESTS=required, so CI fails, rather than skips, when the emulator is
missing. Elsewhere the Firestore tests are skipped without FIRESTORE_EMULATOR_HOST. Each test has a project of its
own in the emulator, wiped when it ends.
"""

import os
import threading
import unittest
import urllib.request
import uuid

from notify.schedule import PersonSettings
from notify.store import Device, MemoryStore, device_id

from support import OTHER_PROJECT, PROJECT, FakeClock, FakeExpo, FakeStatus, document, item, push_token

EMULATOR = os.environ.get("FIRESTORE_EMULATOR_HOST", "")
REQUIRED = os.environ.get("NOTIFY_FIRESTORE_TESTS") == "required"
DATABASE = "notify"


def device(login, name, at="2026-10-26T14:00:00Z", platform="ios"):
    token = push_token(name)
    return Device(id=device_id(token), login=login, token=token, platform=platform, name=name, registered_at=at)


class StoreContract:
    def open(self):
        raise NotImplementedError

    def setUp(self):
        self.store = self.open()

    def test_a_device_is_kept_for_its_login_and_project(self):
        phone = self.store.register(PROJECT, device("alice", "phone"))
        self.store.register(PROJECT, device("alice", "tablet", at="2026-10-26T15:00:00Z", platform="android"))
        self.store.register(PROJECT, device("bob", "other"))
        self.assertEqual(self.store.device(PROJECT, phone.id), phone)
        self.assertEqual([d.name for d in self.store.devices_of(PROJECT, "alice")], ["phone", "tablet"])
        self.assertEqual(self.store.devices_of(OTHER_PROJECT, "alice"), [])
        self.assertEqual(self.store.logins(PROJECT), ["alice", "bob"])
        self.assertIsNone(self.store.device(OTHER_PROJECT, phone.id))

    def test_registering_again_keeps_the_first_time_and_another_login_takes_it_over(self):
        first = self.store.register(PROJECT, device("alice", "phone"))
        again = self.store.register(PROJECT, device("alice", "phone", at="2026-10-27T00:00:00Z"))
        self.assertEqual(again.registered_at, first.registered_at)
        moved = self.store.register(PROJECT, device("bob", "phone", at="2026-10-28T00:00:00Z"))
        self.assertEqual(moved.registered_at, "2026-10-28T00:00:00Z")
        self.assertEqual(self.store.devices_of(PROJECT, "alice"), [])
        self.assertEqual(self.store.devices_of(PROJECT, "bob"), [moved])

    def test_a_removed_device_is_gone(self):
        phone = self.store.register(PROJECT, device("alice", "phone"))
        self.assertTrue(self.store.remove(PROJECT, phone.id))
        self.assertFalse(self.store.remove(PROJECT, phone.id))
        self.assertEqual(self.store.devices_of(PROJECT, "alice"), [])
        self.assertEqual(self.store.logins(PROJECT), [])

    def test_settings_read_back_as_saved(self):
        self.assertIsNone(self.store.settings_of(PROJECT, "alice"))
        chosen = PersonSettings(timezone="America/New_York", digest_time=None, quiet_hours=("22:00", "07:00"))
        self.store.put_settings(PROJECT, "alice", chosen)
        self.assertEqual(self.store.settings_of(PROJECT, "alice"), chosen)
        self.assertIsNone(self.store.settings_of(OTHER_PROJECT, "alice"))
        self.store.put_settings(PROJECT, "alice", PersonSettings())
        self.assertEqual(self.store.settings_of(PROJECT, "alice"), PersonSettings())

    def test_a_mark_is_taken_once_and_can_be_given_back(self):
        key = "push|command-center/notifications/Q1|alice"
        self.assertFalse(self.store.marked(PROJECT, key))
        self.assertTrue(self.store.mark(PROJECT, key, "2026-10-26T14:00:00Z"))
        self.assertFalse(self.store.mark(PROJECT, key, "2026-10-26T14:00:20Z"))
        self.assertTrue(self.store.marked(PROJECT, key))
        self.assertTrue(self.store.mark(OTHER_PROJECT, key, "2026-10-26T14:00:20Z"), "marks are per project")
        self.store.unmark(PROJECT, key)
        self.assertTrue(self.store.mark(PROJECT, key, "2026-10-26T14:00:40Z"))

    def test_of_many_taking_one_mark_at_once_one_gets_it(self):
        stores = [self.open() for _ in range(8)]  # each on its own client, as separate instances would be
        barrier = threading.Barrier(len(stores))
        results = [None] * len(stores)

        def take(i):
            barrier.wait(timeout=10)
            try:
                results[i] = stores[i].mark(PROJECT, "digest|alice|2026-10-26", "2026-10-26T13:30:00Z")
            except Exception as error:  # a mark must be taken or refused, never fail
                results[i] = error

        threads = [threading.Thread(target=take, args=(i,)) for i in range(len(stores))]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=60)
        self.assertEqual(sorted(results, key=str), [False] * (len(stores) - 1) + [True], results)

    def test_the_baseline_is_recorded_once_per_project(self):
        self.assertFalse(self.store.has_baseline(PROJECT))
        self.store.set_baseline(PROJECT, "2026-10-26T14:00:00Z")
        self.store.set_baseline(PROJECT, "2026-10-26T14:00:20Z")
        self.assertTrue(self.store.has_baseline(PROJECT))
        self.assertFalse(self.store.has_baseline(OTHER_PROJECT))

    def test_ids_with_slashes_and_bars_stay_apart(self):
        self.assertTrue(self.store.mark(PROJECT, "push|a/b|c", "t"))
        self.assertTrue(self.store.mark(PROJECT, "push|a|b/c", "t"))
        self.store.put_settings("a/b", "c", PersonSettings(timezone="Asia/Tokyo"))
        self.assertIsNone(self.store.settings_of("a", "b/c"))


class MemoryStoreTest(StoreContract, unittest.TestCase):
    def setUp(self):
        self.shared = MemoryStore()
        super().setUp()

    def open(self):
        return self.shared


def wipe(project, database=DATABASE):
    """Delete every document of one database in the emulator (G4's wipe, as the emulator offers it)."""
    url = f"http://{EMULATOR}/emulator/v1/projects/{project}/databases/{database}/documents"
    with urllib.request.urlopen(urllib.request.Request(url, method="DELETE"), timeout=10) as response:
        response.read()


class FirestoreStoreTest(StoreContract, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not EMULATOR:
            if REQUIRED:
                raise AssertionError("NOTIFY_FIRESTORE_TESTS=required, but FIRESTORE_EMULATOR_HOST names no emulator")
            raise unittest.SkipTest("no Firestore emulator: set FIRESTORE_EMULATOR_HOST (notify.yml starts one)")

    def setUp(self):
        self.project = f"demo-notify-{uuid.uuid4().hex[:12]}"
        self.addCleanup(wipe, self.project)
        super().setUp()

    def open(self):
        from notify.firestore_store import FirestoreStore

        return FirestoreStore(DATABASE, project=self.project)

    def test_two_instances_reading_one_queue_push_each_item_once(self):
        # C2 on the store Cloud Run's instances share: each instance has its own client and its own poller.
        from notify.notifier import Notifier

        status, expo = FakeStatus(), FakeExpo()
        status.documents[PROJECT] = document()
        self.store.register(PROJECT, device("alice", "phone"))
        instances = [Notifier([PROJECT], self.open(), status, expo, clock=FakeClock()) for _ in range(3)]
        instances[0].tick()  # the baseline
        status.documents[PROJECT] = document(*(item(f"q{i}", unblocks=["x/y"]) for i in range(5)))
        barrier = threading.Barrier(len(instances))
        failures = []

        def read(notifier):
            barrier.wait(timeout=10)
            try:
                notifier.tick()
            except Exception as error:
                failures.append(error)

        threads = [threading.Thread(target=read, args=(n,)) for n in instances]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=60)
        self.assertEqual(failures, [])
        self.assertEqual(sorted(m["data"]["item"] for m in expo.sent), [f"q{i}" for i in range(5)])

    def test_a_wipe_loses_devices_settings_and_marks_and_nothing_else_is_kept(self):
        self.store.register(PROJECT, device("alice", "phone"))
        self.store.put_settings(PROJECT, "alice", PersonSettings(timezone="Asia/Tokyo"))
        self.store.mark(PROJECT, "push|x|alice", "t")
        self.store.set_baseline(PROJECT, "t")
        wipe(self.project)
        fresh = self.open()
        self.assertEqual(fresh.logins(PROJECT), [])
        self.assertIsNone(fresh.settings_of(PROJECT, "alice"))
        self.assertFalse(fresh.marked(PROJECT, "push|x|alice"))
        self.assertFalse(fresh.has_baseline(PROJECT))


if __name__ == "__main__":
    unittest.main()
