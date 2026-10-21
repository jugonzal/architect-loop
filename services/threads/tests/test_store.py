"""The store under concurrent posts: the runner narrates while members write, so posts to one thread race.

Each post locks its thread's row, so seqs in a thread are distinct, gapless and in commit order. A reader that pages
with `after` (as the runner does, looking for what members said) therefore never skips a message.
"""

import threading
import unittest

from support import ApiTestCase


class ConcurrentPostTest(ApiTestCase):
    def test_concurrent_posts_to_one_thread_get_distinct_gapless_seqs(self):
        workers, each = 8, 15
        errors, barrier = [], threading.Barrier(workers)

        def post(worker):
            barrier.wait()
            for i in range(each):
                try:
                    self.store.post("jugonzal/architect-loop", "session", "s-race", kind="narration",
                                    author_type="session", author="s-race", author_label="alice",
                                    body=f"{worker}.{i}")
                except Exception as error:  # noqa: BLE001 - every failure is the finding
                    errors.append(repr(error))

        threads = [threading.Thread(target=post, args=(w,)) for w in range(workers)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(errors, [])
        rows, more = self.store.messages("jugonzal/architect-loop", "session", "s-race", limit=500)
        self.assertFalse(more)
        self.assertEqual([r["seq"] for r in rows], list(range(1, workers * each + 1)))
        self.assertEqual(sorted(r["id"] for r in rows), [r["id"] for r in rows], "seq order is insert order")
        self.assertEqual(self.store.thread("jugonzal/architect-loop", "session", "s-race")["last_seq"], workers * each)

    def test_concurrent_first_posts_create_one_thread(self):
        workers, barrier, errors = 8, threading.Barrier(8), []

        def post(worker):
            barrier.wait()
            try:
                self.store.post("jugonzal/architect-loop", "concern", "command-center/threads", kind="message",
                                author_type="person", author="alice", body=str(worker))
            except Exception as error:  # noqa: BLE001
                errors.append(repr(error))

        threads = [threading.Thread(target=post, args=(w,)) for w in range(workers)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors, [])
        self.assertEqual(self.db.rows("SELECT count(*) FROM threads"), [(1,)])
        self.assertEqual(self.db.rows("SELECT count(*) FROM messages"), [(workers,)])


if __name__ == "__main__":
    unittest.main()
