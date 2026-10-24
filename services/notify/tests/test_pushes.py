"""C2: within a minute of the status changing, a push goes out for each blocking item that waits on the person, once,
and everything else waits for the digest.

Here against a fake status service and a fake Expo, with two accounts and one blocking and one non-blocking item, as
the staging proof will have. "Within a minute" is the poller's interval, at most 30 s (test_config.py), on top of
the status service's own freshness; the staging proof measures it end to end.
"""

import threading
import unittest

from notify.notifier import Notifier
from notify.poller import Poller
from notify.store import MemoryStore

from support import PROJECT, FakeExpo, FakeStatus, Harness, item, push_token

BLOCKING = item("command-center/notifications/Q3", waits_on="alice", unblocks=["command-center/app-inbox"])
QUIET = item("command-center/notifications/Q4", waits_on="bob", title="Answer Q4")


class PushTest(Harness, unittest.TestCase):
    def setUp(self):
        self.make()
        self.register("alice", "alice-phone")
        self.register("bob", "bob-phone")
        self.first_read()

    def test_a_blocking_item_is_pushed_to_its_person_and_the_rest_wait(self):
        self.queue(BLOCKING, QUIET)
        read = self.tick()
        self.assertEqual(read.pushed, [(BLOCKING["id"], "alice", 1)])
        [message] = self.expo.to(push_token("alice-phone"))
        self.assertEqual(message["title"], "Answer command-center/notifications/Q3")
        self.assertEqual(message["body"], "Waits on you, and unblocks command-center/app-inbox.")
        self.assertEqual(message["data"], {"url": "/inbox", "project": PROJECT, "item": BLOCKING["id"]})
        self.assertEqual(message["priority"], "high")
        self.assertEqual(self.expo.to(push_token("bob-phone")), [], "a non-blocking item waits for the digest")

    def test_each_blocking_item_is_pushed_once(self):
        self.queue(BLOCKING, QUIET)
        self.tick()
        for _ in range(3):
            self.clock.advance(seconds=20)
            self.assertEqual(self.tick().pushed, [])
        self.assertEqual(len(self.expo.to(push_token("alice-phone"))), 1)

    def test_two_instances_on_one_store_push_once(self):
        # Cloud Run may run two instances, each with its own poller, on the one Firestore database.
        other = Notifier([PROJECT], self.store, self.status, self.expo, clock=self.clock)
        self.queue(BLOCKING)
        barrier = threading.Barrier(2)

        def read(notifier):
            barrier.wait(timeout=5)
            notifier.tick()

        threads = [threading.Thread(target=read, args=(n,)) for n in (self.notifier, other)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)
        self.assertEqual(len(self.expo.to(push_token("alice-phone"))), 1)

    def test_an_item_counts_as_blocking_only_when_it_unblocks_a_concern(self):
        self.queue(item("a", waits_on="alice", unblocks=[]), item("b", waits_on="alice",
                                                                   unblocks=["x/one", "x/two", "x/three"]))
        self.assertEqual([p[0] for p in self.tick().pushed], ["b"])
        self.assertEqual(self.expo.sent[0]["body"], "Waits on you, and unblocks x/one and 2 more.")

    def test_an_item_that_waits_on_nobody_yet_is_pushed_to_nobody(self):
        self.queue(item("a", waits_on=None, unblocks=["x/one"]))
        self.assertEqual(self.tick().pushed, [])
        self.assertEqual(self.expo.sent, [])

    def test_a_backlog_loops_items_carry_no_notifications(self):
        loops = [{"id": "command-center", "state": "active"}, {"id": "someday", "state": "backlog"}]
        self.queue(item("later", loop="someday", unblocks=["someday/x"]), BLOCKING, loops=loops)
        self.assertEqual([p[0] for p in self.tick().pushed], [BLOCKING["id"]])

    def test_an_item_that_comes_to_wait_on_someone_else_is_pushed_to_them(self):
        self.queue(BLOCKING)
        self.tick()
        self.queue({**BLOCKING, "waits_on": "bob"})
        self.assertEqual(self.tick().pushed, [(BLOCKING["id"], "bob", 1)])
        self.assertEqual(len(self.expo.to(push_token("alice-phone"))), 1)

    def test_a_person_with_no_device_is_sent_nothing_and_not_later(self):
        self.queue(item("for-carol", waits_on="carol", unblocks=["x/y"]))
        self.assertEqual(self.tick().pushed, [("for-carol", "carol", 0)])
        self.register("carol", "carol-phone")
        self.assertEqual(self.tick().pushed, [], "once means once: registering later does not replay it")

    def test_a_read_that_fails_pushes_nothing(self):
        self.queue(BLOCKING)
        self.status.down = True
        read = self.tick()
        self.assertFalse(read.ok)
        self.assertEqual(self.expo.sent, [])
        self.status.down = False
        self.assertEqual([p[0] for p in self.tick().pushed], [BLOCKING["id"]])

    def test_a_push_expo_did_not_take_is_tried_again_on_the_next_read(self):
        self.queue(BLOCKING)
        self.expo.down = True
        self.assertEqual(self.tick().pushed, [])
        self.expo.down = False
        self.assertEqual([p[0] for p in self.tick().pushed], [BLOCKING["id"]])
        self.assertEqual(len(self.expo.sent), 1)

    def test_a_push_expo_refused_is_not_retried_every_read(self):
        self.expo.refused.add(push_token("alice-phone"))
        self.queue(BLOCKING)
        self.assertEqual(self.tick().pushed, [(BLOCKING["id"], "alice", 0)])
        self.expo.refused.clear()
        self.assertEqual(self.tick().pushed, [])


class FirstReadTest(Harness, unittest.TestCase):
    """The first read of a new or wiped store marks what already stands, so a wipe never pushes it all again (G4)."""

    def setUp(self):
        self.make()
        self.register("alice", "alice-phone")

    def test_what_stands_at_the_first_read_is_seen_not_pushed(self):
        read = self.first_read(BLOCKING)
        self.assertEqual(read.pushed, [])
        self.assertEqual(self.expo.sent, [])
        fresh = item("new", waits_on="alice", unblocks=["x/y"])
        self.queue(BLOCKING, fresh)
        self.assertEqual([p[0] for p in self.tick().pushed], ["new"])

    def test_after_a_wipe_the_first_read_is_a_baseline_again(self):
        self.first_read(BLOCKING)
        wiped = MemoryStore()
        self.notifier.store = wiped
        self.assertTrue(self.tick().baseline)
        self.assertEqual(self.expo.sent, [])

    def test_a_first_read_that_fails_records_no_baseline(self):
        self.status.down = True
        self.notifier.tick()
        self.assertFalse(self.store.has_baseline(PROJECT))


class PollerTest(unittest.TestCase):
    def test_it_reads_again_and_again_and_survives_a_failure(self):
        calls = []
        done = threading.Event()

        class Flaky:
            def tick(self):
                calls.append(1)
                if len(calls) == 1:
                    raise RuntimeError("one bad read (test)")
                if len(calls) >= 3:
                    done.set()

        with self.assertLogs("notify.poller", level="ERROR") as logged:
            poller = Poller(Flaky(), 0.01).start()
            self.assertTrue(done.wait(5))
            poller.stop(timeout=5)
        self.assertIn("one bad read (test)", "\n".join(logged.output))
        self.assertGreaterEqual(len(calls), 3)

    def test_it_reads_each_project_through_the_notifier(self):
        status, expo = FakeStatus(), FakeExpo()
        notifier = Notifier([PROJECT], MemoryStore(), status, expo)
        poller = Poller(notifier, 0.01).start()
        try:
            for _ in range(500):
                if len(status.reads) >= 2:
                    break
                threading.Event().wait(0.01)
        finally:
            poller.stop(timeout=5)
        self.assertGreaterEqual(status.reads.count(PROJECT), 2)


if __name__ == "__main__":
    unittest.main()
