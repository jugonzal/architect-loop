"""The runner's store on Firestore (runner-store C1, per command-center/D44 and D26), against the Firestore emulator.

`FirestoreStoreTest` runs every test of `test_store.StoreTest` on a FirestoreStore, so the two stores keep one
contract and a test added there runs here too; the three that open the SQLite file itself are skipped, and the two
that reopen it reopen the Firestore database instead. Each racing claim and each job has a client of its own, as
separate service instances and session containers would. The other classes test what only this store has: the
documents a claim reads, the service and the job opening the database the manifest declares, and dispatches at once
through separate service instances.

runner.yml starts the emulator and sets RUNNER_FIRESTORE_TESTS=required, so CI fails, rather than skips, when the
emulator is missing. Elsewhere these are skipped without FIRESTORE_EMULATOR_HOST, except the manifest's, which need
no emulator. Each test has a project of its own in the emulator, wiped when it ends.
"""

import importlib.util
import json
import os
import threading
import unittest
import urllib.request
import uuid
from unittest import mock

from runner import main
from runner.api import Api
from runner.config import DEFAULT_SEEDS, Config
from runner.dispatch import Dispatcher
from runner.firestore_store import CLAIMS, SPONSORS, FirestoreStore, claim_id, sponsor_id
from runner.store import SqliteStore
from tests import test_store
from tests.contract import ContractClient
from tests.fakes import CONCERN, OTHER, PROJECT, FakeGitHub, FakeLauncher, dispatch_body, scratch
from tests.test_github import PEM
from tests.test_store import NOW, final, session

EMULATOR = os.environ.get("FIRESTORE_EMULATOR_HOST", "")
REQUIRED = os.environ.get("RUNNER_FIRESTORE_TESTS") == "required"
DATABASE = "runner"
SERVICE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(os.path.dirname(SERVICE))
THIRD = "command-center/app-agents"
FOURTH = "command-center/notifications"
FIFTH = "command-center/environments"


def wipe(project, database=DATABASE):
    """Delete every document of one database in the emulator (G4's wipe, as the emulator offers it)."""
    url = f"http://{EMULATOR}/emulator/v1/projects/{project}/databases/{database}/documents"
    with urllib.request.urlopen(urllib.request.Request(url, method="DELETE"), timeout=10) as response:
        response.read()


class Emulated:
    """Needs the Firestore emulator: skipped without one, unless runner.yml says it is required."""

    @classmethod
    def setUpClass(cls):
        if not EMULATOR:
            if REQUIRED:
                raise AssertionError("RUNNER_FIRESTORE_TESTS=required, but FIRESTORE_EMULATOR_HOST names no emulator")
            raise unittest.SkipTest("no Firestore emulator: set FIRESTORE_EMULATOR_HOST (runner.yml starts one)")
        super().setUpClass()

    def fresh_project(self):
        project = f"demo-runner-{uuid.uuid4().hex[:12]}"
        self.addCleanup(wipe, project)
        return project

    def open(self, seeds=()):
        """A client of its own on the test's database, as another service instance or a session's job holds one."""
        return FirestoreStore(DATABASE, project=self.project, seeds=seeds)


class FirestoreStoreTest(Emulated, test_store.StoreTest):
    """Every test of the SQLite store's contract, on Firestore."""

    def setUp(self):
        self.project = self.fresh_project()
        self.store = self.open(seeds=DEFAULT_SEEDS)

    def race(self, sessions):
        barrier = threading.Barrier(len(sessions))
        results = [None] * len(sessions)
        stores = [self.open() for _ in sessions]  # each dispatch on its own client, as separate instances would be

        def go(i):
            barrier.wait(timeout=10)
            try:
                results[i] = stores[i].claim(sessions[i], 3, NOW, 300)
            except Exception as error:  # a claim must refuse, never fail
                results[i] = error

        threads = [threading.Thread(target=go, args=(i,)) for i in range(len(sessions))]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=60)
        self.assertEqual([r for r in results if isinstance(r, Exception)], [])
        return results

    @unittest.skip("SQLite only: it opens the SQLite file and writes past the store; Firestore has no unique index")
    def test_the_database_itself_refuses_two_active_sessions_on_one_concern(self):
        pass

    @unittest.skip("SQLite only: it opens the SQLite file and writes past the store; Firestore has no unique index")
    def test_the_database_itself_refuses_two_holding_sessions_but_not_a_prove_beside_one(self):
        pass

    @unittest.skip("SQLite only: no runner wrote a Firestore store before this one, so there is nothing to migrate")
    def test_a_store_made_by_the_previous_runner_lets_a_prove_beside_a_build(self):
        pass

    def test_the_service_and_the_job_see_the_same_store(self):
        self.claim(session(1))
        job = self.open()
        job.mark_running(session(1).id, NOW)
        self.assertFalse(job.publish(session(1).id, final(0.1, basis="per-step usage"), NOW))
        self.assertEqual(self.store.get(session(1).id).state, "running")
        self.assertEqual(self.store.get(session(1).id).spend["usd"], 0.1)

    def test_the_seed_is_a_measurement_and_is_not_duplicated_or_lost_by_a_wipe(self):
        self.assertEqual(self.store.measurements("loop-status", "claude-opus-5-5"),
                         [{"usd": 0.44, "wall_clock_s": 75.0, "source": "seed:loop-status:claude-opus-5-5"}])
        self.open(seeds=DEFAULT_SEEDS)
        self.assertEqual(len(self.store.measurements("loop-status", "claude-opus-5-5")), 1)
        self.claim(session(1))
        wipe(self.project)  # G4: wiping the store loses history, and the seeds come back
        self.assertEqual(self.store.list(state="all"), [])
        fresh = self.open(seeds=DEFAULT_SEEDS)
        self.assertEqual(len(fresh.measurements("loop-status", "claude-opus-5-5")), 1)


def documents(store, collection):
    return {doc.id: doc.to_dict() for doc in store.client.collection(collection).stream()}


class ClaimDocumentsTest(Emulated, unittest.TestCase):
    """A claim reads two documents, the concern's claim and the sponsor's, and the sessions they name; it counts only
    the sessions still active, so a document that names an ended or missing one cannot refuse a dispatch."""

    def setUp(self):
        self.project = self.fresh_project()
        self.store = self.open()

    def claim(self, s, cap=3, now=NOW):
        return self.store.claim(s, cap, now, 300)

    def named(self):
        claims = {k: sorted(v["holders"]) for k, v in documents(self.store, CLAIMS).items()}
        sponsors = {k: sorted(v["active"]) for k, v in documents(self.store, SPONSORS).items()}
        return claims, sponsors

    def test_the_claim_names_its_holding_session_and_the_sponsor_every_active_one(self):
        build, prove = session(1, skill="loop-build"), session(2, skill="loop-prove")
        self.assertIsNone(self.claim(build))
        self.assertIsNone(self.claim(prove))
        self.assertEqual(self.named(), ({claim_id(PROJECT, CONCERN): [build.id]},
                                        {sponsor_id("juan"): sorted([build.id, prove.id])}))
        self.store.finish(build.id, "completed", None, [], NOW)
        self.assertEqual(self.named(), ({claim_id(PROJECT, CONCERN): []}, {sponsor_id("juan"): [prove.id]}))
        self.store.expire_lost("2026-10-20T12:05:01Z", 300)
        self.assertEqual(self.named(), ({claim_id(PROJECT, CONCERN): []}, {sponsor_id("juan"): []}))

    def test_a_claim_counts_only_the_sessions_still_active_whatever_the_documents_name(self):
        ended, running = session(1, skill="loop-build"), session(2, concern=OTHER)
        self.claim(ended)
        self.store.finish(ended.id, "completed", None, [], NOW)
        self.claim(running)
        # As if a cleanup had been lost: both documents still name the ended session, and one names no session at all.
        missing = "f" * 32
        self.store.client.collection(SPONSORS).document(sponsor_id("juan")).set(
            {"sponsor": "juan", "active": [ended.id, running.id, missing]})
        self.store.client.collection(CLAIMS).document(claim_id(PROJECT, CONCERN)).set(
            {"project": PROJECT, "concern": CONCERN, "holders": [ended.id, missing]})
        self.assertIsNone(self.claim(session(3, skill="loop-design")))
        self.assertIsNone(self.claim(session(4, concern=THIRD)))
        refusal = self.claim(session(5, concern=FOURTH))
        self.assertEqual((refusal.refused, sorted(s.id for s in refusal.sessions)),
                         ("sponsor-cap", sorted([running.id, session(3).id, session(4).id])))
        self.assertEqual(self.named(), ({claim_id(PROJECT, CONCERN): [session(3).id],
                                         claim_id(PROJECT, OTHER): [running.id],
                                         claim_id(PROJECT, THIRD): [session(4).id]},
                                        {sponsor_id("juan"): sorted([running.id, session(3).id, session(4).id])}))

    def test_a_silent_holder_sponsored_by_someone_else_is_lost_and_frees_its_sponsor(self):
        theirs = session(1, sponsor="ana")
        self.assertIsNone(self.claim(theirs))
        later = "2026-10-20T12:05:01Z"
        self.assertIsNone(self.claim(session(2), now=later))
        lost = self.store.get(theirs.id)
        self.assertEqual((lost.state, lost.outcome, lost.ended_at), ("ended", "lost", later))
        self.assertEqual(self.named(), ({claim_id(PROJECT, CONCERN): [session(2).id]},
                                        {sponsor_id("ana"): [], sponsor_id("juan"): [session(2).id]}))

    def test_a_holding_claim_on_a_concern_held_by_a_silent_session_ends_it_in_the_same_write(self):
        """Even when nothing ended the silent session first, the claim's own write does."""
        held = session(1, sponsor="ana")
        self.claim(held)
        later = "2026-10-20T12:05:01Z"
        with mock.patch.object(FirestoreStore, "expire_lost", return_value=[]):
            self.assertIsNone(self.claim(session(2), now=later))
        self.assertEqual(self.store.get(held.id).outcome, "lost")
        self.assertEqual(self.named()[1][sponsor_id("ana")], [])

    def test_a_refused_claim_stores_nothing(self):
        self.claim(session(1, sponsor="ana"))
        before = self.named()
        self.assertEqual(self.claim(session(2)).refused, "running-session")
        self.assertIsNone(self.store.get(session(2).id))
        self.assertEqual(self.named(), before)


class WiringTest(Emulated, unittest.TestCase):
    """The service and a session's job open the Firestore database RUNNER_STORE names, in RUNNER_GCP_PROJECT."""

    def setUp(self):
        self.project = self.fresh_project()

    def env(self, **extra):
        return {"RUNNER_STORE": f"firestore:{DATABASE}", "RUNNER_GCP_PROJECT": self.project, "COMMIT_SHA": "eee8119",
                **extra}

    def test_the_service_opens_the_database_its_store_setting_names(self):
        api = main.service_from_env(self.env())
        store = api.dispatcher.store
        self.assertIsInstance(store, FirestoreStore)
        self.assertEqual((store.database, store.project), (DATABASE, self.project))
        self.assertEqual([m["source"] for m in store.measurements("loop-status", "claude-opus-5-5")],
                         ["seed:loop-status:claude-opus-5-5"])

    def test_the_job_opens_the_same_database_and_sees_what_the_service_claimed(self):
        service = main.service_from_env(self.env()).dispatcher.store
        service.claim(session(1), 3, NOW, 300)
        env = self.env(RUNNER_SESSION_ID=session(1).id, RUNNER_APP_ID="12345", RUNNER_APP_INSTALLATION_ID="678",
                       RUNNER_APP_SLUG="architect-loop-runner", RUNNER_APP_PRIVATE_KEY=PEM)
        with mock.patch.object(main.RestGitHub, "bot_user_id", return_value=4321):
            job, session_id = main.job_from_env(env)
        self.assertIsInstance(job.store, FirestoreStore)
        self.assertIsNot(job.store.client, service.client)
        self.assertEqual(job.store.get(session_id), session(1))


class StoreSettingTest(unittest.TestCase):
    """What RUNNER_STORE names, and that the manifest names the database it declares (command-center/D46). These
    need no emulator."""

    def manifest(self):
        with open(os.path.join(SERVICE, "service.json"), encoding="utf-8") as f:
            return json.load(f)

    def test_a_path_is_still_a_sqlite_file(self):
        store = main.store_from(Config(store_path=os.path.join(scratch(self), "runner.sqlite3")))
        self.assertIsInstance(store, SqliteStore)

    def test_a_firestore_setting_without_a_database_is_refused(self):
        with self.assertRaises(ValueError):
            main.store_from(Config(store_path="firestore:"))

    def test_the_manifest_points_the_service_and_its_jobs_at_the_database_it_declares(self):
        manifest = self.manifest()
        setting = manifest["settings"]["RUNNER_STORE"]
        self.assertTrue(setting.startswith("firestore:"), setting)
        self.assertEqual(manifest["firestore"], [setting[len("firestore:"):]])
        self.assertEqual(manifest["firestore"], [DATABASE])  # a database named after the service (D44)
        for name, job in manifest["jobs"].items():
            with self.subTest(job=name):  # a job runs with the service's settings, so it shares the store
                self.assertNotIn("RUNNER_STORE", job.get("settings", {}))

    def test_the_manifest_lets_the_runner_use_firestore(self):
        manifest = self.manifest()
        self.assertIn("firestore.googleapis.com", manifest["apis"])
        self.assertIn("roles/datastore.user", manifest["identity"]["roles"])
        self.assertIn("roles/run.jobsExecutorWithOverrides", manifest["identity"]["roles"])

    def test_the_manifest_fits_the_format_the_bootstrap_and_deploy_read(self):
        path = os.path.join(ROOT, "scripts", "gcp", "manifest.py")
        spec = importlib.util.spec_from_file_location("gcp_manifest", path)
        checker = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(checker)
        self.assertEqual(checker.problems(checker.load(os.path.join(SERVICE, "service.json"))), [])
        self.assertIn(f"{DATABASE} runner", checker.listing(ROOT, "firestore"))  # what the bootstrap creates


class DispatchAcrossInstancesTest(Emulated, unittest.TestCase):
    """C1's proof on staging/runner, rehearsed on the emulator: dispatches at once, each through a service instance of
    its own on the one database, start at most one holding session per concern and at most the cap per sponsor."""

    def setUp(self):
        self.project = self.fresh_project()

    def instance(self, barrier):
        github, launcher = FakeGitHub(), FakeLauncher()
        for n in range(1, 11):
            github.tokens[f"tok-p{n}"] = f"p{n}"
            github.collaborators.add(f"p{n}")
        original = github.release_exists

        def all_pass_the_checks_before_the_claim(tag):
            result = original(tag)
            barrier.wait(timeout=10)
            return result

        github.release_exists = all_pass_the_checks_before_the_claim
        dispatcher = Dispatcher(Config(commit="eee8119"), self.open(seeds=DEFAULT_SEEDS), github, launcher)
        return ContractClient(self, Api(dispatcher)), launcher

    def race(self, bodies, tokens):
        barrier = threading.Barrier(len(bodies))
        instances = [self.instance(barrier) for _ in bodies]
        results = [None] * len(bodies)

        def go(i):
            results[i] = instances[i][0].call("POST", "/sessions", bodies[i], token=tokens[i])

        threads = [threading.Thread(target=go, args=(i,)) for i in range(len(bodies))]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=60)
        launched = sum(len(launcher.launched) for _, launcher in instances)
        return results, launched

    def test_ten_dispatches_at_once_on_one_concern_start_one_session(self):
        results, launched = self.race([dispatch_body()] * 10, [f"tok-p{n}" for n in range(1, 11)])
        self.assertEqual(sorted(r.status for r in results), [201] + [409] * 9)
        self.assertEqual({r.json["refused"] for r in results if r.status == 409}, {"running-session"})
        self.assertEqual(launched, 1)
        self.assertEqual(len(self.open().list()), 1)

    def test_four_dispatches_at_once_by_one_sponsor_start_the_cap(self):
        bodies = [dispatch_body(concern=c) for c in (CONCERN, OTHER, THIRD, FOURTH)]
        results, launched = self.race(bodies, ["tok-juan"] * 4)
        self.assertEqual(sorted(r.status for r in results), [201, 201, 201, 409])
        [refused] = [r.json for r in results if r.status == 409]
        self.assertEqual((refused["refused"], refused["cap"], len(refused["sessions"])), ("sponsor-cap", 3, 3))
        self.assertEqual(launched, 3)
        self.assertEqual(len(self.open().list(sponsor="juan")), 3)

    def test_after_the_race_the_sponsor_is_still_at_the_cap(self):
        self.race([dispatch_body(concern=c) for c in (CONCERN, OTHER, THIRD, FOURTH)], ["tok-juan"] * 4)
        client, _ = self.instance(threading.Barrier(1))
        response = client.call("POST", "/sessions", dispatch_body(concern=FIFTH), token="tok-juan")
        self.assertEqual((response.status, response.json["refused"]), (409, "sponsor-cap"))


if __name__ == "__main__":
    unittest.main()
