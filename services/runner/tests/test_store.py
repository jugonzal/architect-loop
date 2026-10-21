"""The runner's store (command-center/D26): the atomic claim behind runner-dispatch C2 (only `/loop-build` and
`/loop-design` hold a concern, session-runner D6; every running session counts toward its sponsor's cap, D22),
spend publication, and measurements."""

import os
import sqlite3
import threading
import unittest

from runner.config import DEFAULT_SEEDS
from runner.models import Session
from runner.store import SqliteStore
from tests.fakes import CONCERN, ENVIRONMENT, LOOP, OTHER, PROJECT, SCOPED, scratch

NOW = "2026-10-20T12:00:00Z"

# The store's schema as session-runner first built it (main @a9fde89), to check that a file it made still opens.
V1_SCHEMA = """
CREATE TABLE sessions (
    id TEXT PRIMARY KEY, project TEXT NOT NULL, skill TEXT NOT NULL, concern TEXT NOT NULL, arguments TEXT NOT NULL,
    model TEXT NOT NULL, sponsor TEXT NOT NULL, budget_usd REAL NOT NULL, plugin_release TEXT NOT NULL,
    branch TEXT NOT NULL, created_at TEXT NOT NULL, state TEXT NOT NULL, outcome TEXT, started_at TEXT,
    ended_at TEXT, heartbeat_at TEXT, spend TEXT, pull_requests TEXT NOT NULL DEFAULT '[]',
    stop_requested INTEGER NOT NULL DEFAULT 0, execution TEXT
);
CREATE UNIQUE INDEX one_active_session_per_concern
    ON sessions (project, concern) WHERE state IN ('starting', 'running', 'stopping');
CREATE INDEX sessions_by_sponsor ON sessions (sponsor, state);
CREATE TABLE measurements (
    source TEXT PRIMARY KEY, skill TEXT NOT NULL, model TEXT NOT NULL, usd REAL NOT NULL, wall_clock_s REAL NOT NULL,
    at TEXT NOT NULL
);
"""


def session(n, concern=CONCERN, sponsor="juan", skill="loop-build", model="claude-opus-5-5", created_at=NOW):
    return Session(id=f"{n:032x}", project=PROJECT, skill=skill, concern=concern, arguments="", model=model,
                   sponsor=sponsor, budget_usd=1.0, plugin_release="v0.3.0", branch=concern, created_at=created_at)


def scoped(n, scope, skill, sponsor="juan"):
    """A session on the test concern, loop or environment (runner-dispatch C3)."""
    return Session(id=f"{n:032x}", project=PROJECT, skill=skill, arguments="", model="claude-opus-5-5",
                   sponsor=sponsor, budget_usd=1.0, plugin_release="v0.3.0", created_at=NOW, **SCOPED[scope])


def final(usd, wall=60.0, basis="sdk result"):
    return {"kind": "estimate", "basis": basis, "usd": usd, "overshoot_usd": 0.0,
            "tokens": {"input": 1, "output": 1, "cache_creation": 0, "cache_read": 0}, "wall_clock_s": wall,
            "as_of": NOW}


class StoreTest(unittest.TestCase):
    def setUp(self):
        self.path = os.path.join(scratch(self), "runner.sqlite3")
        self.store = SqliteStore(self.path, seeds=DEFAULT_SEEDS)

    def claim(self, s, cap=3):
        return self.store.claim(s, cap, NOW, 300)

    def test_a_claim_stores_the_session(self):
        self.assertIsNone(self.claim(session(1)))
        self.assertEqual(self.store.get(session(1).id), session(1))

    def test_a_second_claim_on_an_active_concern_is_refused_and_names_the_first(self):
        self.claim(session(1))
        refusal = self.claim(session(2, sponsor="ana"))
        self.assertEqual(refusal.refused, "running-session")
        self.assertEqual([s.id for s in refusal.sessions], [session(1).id])
        self.assertIsNone(self.store.get(session(2).id))

    def test_the_database_itself_refuses_two_active_sessions_on_one_concern(self):
        self.claim(session(1))
        db = sqlite3.connect(self.path)
        self.addCleanup(db.close)
        with self.assertRaises(sqlite3.IntegrityError):
            db.execute("INSERT INTO sessions (id, project, skill, concern, arguments, model, sponsor, budget_usd, "
                       "plugin_release, branch, created_at, state) VALUES ('x', ?, 'loop-build', ?, '', 'm', 'ana', "
                       "1, 'v0.3.0', ?, ?, 'running')", (PROJECT, CONCERN, CONCERN, NOW))

    def test_a_prove_or_a_status_claim_beside_a_holding_session_is_stored(self):
        self.claim(session(1, skill="loop-build"))
        self.assertIsNone(self.claim(session(2, sponsor="ana", skill="loop-prove")))
        self.assertIsNone(self.claim(session(3, sponsor="ana", skill="loop-status")))
        self.assertEqual(len(self.store.list()), 3)

    def test_a_holding_claim_beside_a_prove_is_stored_and_a_second_one_is_refused(self):
        self.claim(session(1, skill="loop-prove"))
        self.assertIsNone(self.claim(session(2, sponsor="ana", skill="loop-design")))
        refusal = self.claim(session(3, sponsor="bea", skill="loop-build"))
        self.assertEqual(refusal.refused, "running-session")
        self.assertEqual([s.id for s in refusal.sessions], [session(2).id])

    def test_the_database_itself_refuses_two_holding_sessions_but_not_a_prove_beside_one(self):
        self.claim(session(1, skill="loop-design"))
        db = sqlite3.connect(self.path)
        self.addCleanup(db.close)
        insert = ("INSERT INTO sessions (id, project, skill, concern, arguments, model, sponsor, budget_usd, "
                  "plugin_release, branch, created_at, state) VALUES (?, ?, ?, ?, '', 'm', 'ana', 1, 'v0.3.0', ?, ?, "
                  "'running')")
        db.execute(insert, ("p", PROJECT, "loop-prove", CONCERN, CONCERN, NOW))
        with self.assertRaises(sqlite3.IntegrityError):
            db.execute(insert, ("b", PROJECT, "loop-build", CONCERN, CONCERN, NOW))

    def test_every_active_session_counts_toward_the_cap_whatever_its_skill(self):
        for n, skill in enumerate(("loop-build", "loop-prove", "loop-status"), 1):
            self.assertIsNone(self.claim(session(n, skill=skill)))
        refusal = self.claim(session(4, concern=OTHER, skill="loop-prove"))
        self.assertEqual((refusal.refused, refusal.cap, len(refusal.sessions)), ("sponsor-cap", 3, 3))

    def test_a_loop_or_environment_session_holds_nothing_and_counts_toward_the_cap(self):
        self.assertIsNone(self.claim(scoped(1, "loop", "loop-design")))
        self.assertIsNone(self.claim(scoped(2, "loop", "loop-design", sponsor="ana")))
        self.assertIsNone(self.claim(scoped(3, "environment", "loop-ship")))
        self.assertIsNone(self.claim(scoped(4, "environment", "loop-ship", sponsor="ana")))
        self.assertIsNone(self.claim(session(5, skill="loop-build")))
        refusal = self.claim(session(6, concern=OTHER, skill="loop-prove"))
        self.assertEqual((refusal.refused, len(refusal.sessions)), ("sponsor-cap", 3))

    def test_a_session_reads_back_with_what_it_runs_on(self):
        for n, scope, skill in ((1, "loop", "loop-status"), (2, "environment", "loop-ship")):
            with self.subTest(scope=scope):
                self.claim(scoped(n, scope, skill))
                found = self.store.get(scoped(n, scope, skill).id)
                self.assertEqual(found, scoped(n, scope, skill))
                self.assertEqual((found.concern, found.loop, found.environment, found.branch),
                                 (None, LOOP if scope == "loop" else None,
                                  ENVIRONMENT if scope == "environment" else None, "main"))
                self.assertFalse(found.holds)

    def test_the_final_message_is_kept_with_how_it_ended(self):
        self.claim(scoped(1, "environment", "loop-ship"))
        ended = self.store.finish(scoped(1, "environment", "loop-ship").id, "completed", final(0.4), [], NOW,
                                  final_message="## Ship brief\n\nThree concerns go out.")
        self.assertEqual(ended.final_message, "## Ship brief\n\nThree concerns go out.")
        self.assertEqual(self.store.get(ended.id).public()["final_message"], "## Ship brief\n\nThree concerns go out.")

    def test_a_session_that_ends_without_one_has_no_final_message(self):
        self.claim(session(1))
        self.assertIsNone(self.store.finish(session(1).id, "error", None, [], NOW).final_message)

    def test_ten_proves_at_once_on_one_concern_are_all_stored(self):
        results = self.race([session(n, sponsor=f"p{n}", skill="loop-prove") for n in range(1, 11)])
        self.assertEqual(results, [None] * 10)

    def test_holding_and_non_holding_claims_at_once_store_one_holder_and_every_prove(self):
        claims = [session(n, sponsor=f"p{n}", skill="loop-build" if n % 2 else "loop-prove") for n in range(1, 11)]
        results = self.race(claims)
        stored = [c.skill for c, r in zip(claims, results) if r is None]
        self.assertEqual(sorted(stored), ["loop-build"] + ["loop-prove"] * 5)

    def test_ten_claims_at_once_on_one_concern_store_exactly_one(self):
        results = self.race([session(n, sponsor=f"p{n}") for n in range(1, 11)])
        self.assertEqual(sum(r is None for r in results), 1)
        self.assertEqual(len(self.store.list()), 1)

    def test_ten_claims_at_once_by_one_sponsor_store_exactly_the_cap(self):
        results = self.race([session(n, concern=f"loop/c{n}") for n in range(1, 11)])
        self.assertEqual(sum(r is None for r in results), 3)
        self.assertTrue(all(r.refused == "sponsor-cap" for r in results if r))
        self.assertEqual(len(self.store.list(sponsor="juan")), 3)

    def race(self, sessions):
        barrier = threading.Barrier(len(sessions))
        results = [None] * len(sessions)

        def go(i):
            other = SqliteStore(self.path)  # each dispatch on its own connection, as separate requests would be
            barrier.wait(timeout=5)
            try:
                results[i] = other.claim(sessions[i], 3, NOW, 300)
            except Exception as error:  # a claim must refuse, never fail
                results[i] = error

        threads = [threading.Thread(target=go, args=(i,)) for i in range(len(sessions))]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)
        self.assertEqual([r for r in results if isinstance(r, Exception)], [])
        return results

    def test_the_service_and_the_job_see_the_same_store(self):
        self.claim(session(1))
        job = SqliteStore(self.path)
        job.mark_running(session(1).id, NOW)
        self.assertFalse(job.publish(session(1).id, final(0.1, basis="per-step usage"), NOW))
        self.assertEqual(self.store.get(session(1).id).state, "running")
        self.assertEqual(self.store.get(session(1).id).spend["usd"], 0.1)

    def test_a_stop_request_reaches_the_job_through_publish(self):
        self.claim(session(1))
        self.store.mark_running(session(1).id, NOW)
        self.assertEqual(self.store.request_stop(session(1).id).state, "stopping")
        self.assertTrue(self.store.publish(session(1).id, None, NOW))

    def test_an_ended_session_cannot_be_stopped_and_tells_the_job_to_stop(self):
        self.claim(session(1))
        self.store.finish(session(1).id, "completed", None, [], NOW)
        self.assertIsNone(self.store.request_stop(session(1).id))
        self.assertTrue(self.store.publish(session(1).id, None, NOW))

    def test_a_silent_active_session_is_lost_after_the_limit(self):
        self.claim(session(1))
        self.assertEqual(self.store.expire_lost("2026-10-20T12:04:59Z", 300), [])
        self.assertEqual(self.store.expire_lost("2026-10-20T12:05:01Z", 300), [session(1).id])
        found = self.store.get(session(1).id)
        self.assertEqual((found.state, found.outcome), ("ended", "lost"))

    def test_publishing_keeps_a_session_alive(self):
        self.claim(session(1))
        self.store.publish(session(1).id, None, "2026-10-20T12:04:00Z")
        self.assertEqual(self.store.expire_lost("2026-10-20T12:08:59Z", 300), [])

    def test_a_finished_session_with_the_sdks_estimate_becomes_a_measurement(self):
        self.claim(session(1))
        self.store.finish(session(1).id, "completed", final(0.5, 90), [], NOW)
        self.assertEqual(self.store.measurements("loop-build", "claude-opus-5-5"),
                         [{"usd": 0.5, "wall_clock_s": 90, "source": session(1).id}])

    def test_a_session_without_the_sdks_estimate_is_not_a_measurement(self):
        self.claim(session(1))
        self.store.finish(session(1).id, "error", final(0.5, basis="per-step usage"), [], NOW)
        self.assertEqual(self.store.measurements("loop-build", "claude-opus-5-5"), [])

    def test_measurements_are_newest_first_and_limited(self):
        for n in range(1, 13):
            s = session(n, concern=f"loop/c{n}")
            self.store.claim(s, 99, NOW, 300)
            self.store.finish(s.id, "completed", final(n / 10), [], f"2026-10-20T12:{n:02d}:00Z")
        found = self.store.measurements("loop-build", "claude-opus-5-5", 10)
        self.assertEqual([m["usd"] for m in found], [1.2, 1.1, 1.0, 0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3])

    def test_the_seed_is_a_measurement_and_is_not_duplicated_or_lost_by_a_wipe(self):
        self.assertEqual(self.store.measurements("loop-status", "claude-opus-5-5"),
                         [{"usd": 0.44, "wall_clock_s": 75.0, "source": "seed:loop-status:claude-opus-5-5"}])
        SqliteStore(self.path, seeds=DEFAULT_SEEDS)
        self.assertEqual(len(self.store.measurements("loop-status", "claude-opus-5-5")), 1)
        os.remove(self.path)  # G4: wiping the store loses history, and the seeds come back
        fresh = SqliteStore(self.path, seeds=DEFAULT_SEEDS)
        self.assertEqual(len(fresh.measurements("loop-status", "claude-opus-5-5")), 1)

    def test_a_seed_falls_out_once_ten_sessions_are_measured(self):
        for n in range(1, 11):
            s = session(n, concern=f"loop/c{n}", skill="loop-status")
            self.store.claim(s, 99, NOW, 300)
            self.store.finish(s.id, "completed", final(0.3), [], NOW)
        sources = [m["source"] for m in self.store.measurements("loop-status", "claude-opus-5-5", 10)]
        self.assertNotIn("seed:loop-status:claude-opus-5-5", sources)

    def test_a_store_made_by_the_previous_runner_lets_a_prove_beside_a_build(self):
        """Its index refused any second active session on a concern; opening it replaces that index."""
        path = os.path.join(scratch(self), "old.sqlite3")
        db = sqlite3.connect(path)
        db.executescript(V1_SCHEMA)
        db.execute("INSERT INTO sessions (id, project, skill, concern, arguments, model, sponsor, budget_usd, "
                   "plugin_release, branch, created_at, state) VALUES (?, ?, 'loop-build', ?, '', 'm', 'juan', 1, "
                   "'v0.3.0', ?, ?, 'running')", ("b" * 32, PROJECT, CONCERN, CONCERN, NOW))
        db.commit()
        db.close()
        store = SqliteStore(path)
        self.assertIsNone(store.claim(session(2, sponsor="ana", skill="loop-prove"), 3, NOW, 3600))
        self.assertEqual(store.claim(session(3, sponsor="ana", skill="loop-design"), 3, NOW, 3600).refused,
                         "running-session")
        old = store.get("b" * 32)  # its row is kept, and now says it runs on no loop or environment
        self.assertEqual((old.concern, old.loop, old.environment, old.final_message), (CONCERN, None, None, None))
        self.assertIsNone(store.claim(scoped(4, "loop", "loop-status", sponsor="bea"), 3, NOW, 3600))
        SqliteStore(path)  # opening it again changes nothing
        self.assertEqual(len(store.list()), 3)

    def test_list_filters(self):
        self.claim(session(1))
        self.claim(session(2, concern=OTHER, sponsor="ana"))
        self.store.finish(session(1).id, "completed", None, [], NOW)
        self.assertEqual([s.id for s in self.store.list()], [session(2).id])
        self.assertEqual(len(self.store.list(state="all")), 2)
        self.assertEqual([s.id for s in self.store.list(state="all", sponsor="juan")], [session(1).id])


if __name__ == "__main__":
    unittest.main()
