"""The runner's store on Firestore: a database of its own, `runner`, in its environment's project, which the service
and every session's job share across containers (runner-store C1, per command-center/D44 and D26).

It implements `store.Store` with SqliteStore's guarantees, and runs the same tests (tests/test_firestore_store.py).
Wiping it loses session history and the estimates' medians, never a loop's state (G4).

One database, four collections:

  sessions/<id>               a session's fields, plus `active` (its state is starting, running or stopping)
  claims/<project>|<concern>  `holders`: the active /loop-build or /loop-design sessions on that concern
  sponsors/<sponsor>          `active`: the sponsor's active sessions, whatever their skill or what they run on
  measurements/<source>       a measured session's spend (its id is the session's), and the seeds

A claim reads the concern's claim document (when the session holds its concern, per session-runner D6), the
sponsor's document and every session the two name. It then commits the new session and both documents in one
atomic write that Firestore applies only if every document it rewrites is still as the claim read it (its update
time, or still missing). Two claims that could not both start each rewrite the same claim or sponsor document, so
one commits and the other reads again and decides on what the first wrote: of ten at once on one concern one
starts, and a sponsor never passes the cap. Every change to a session that a claim counts, its end included, also
rewrites one of those documents or the session itself, so it too makes a claim that read before it read again.
The documents only say where to look: a claim counts a session only if its own document says it is active, so a
name left behind cannot refuse a dispatch.

Why a conditional write and not a Firestore transaction: a transaction locks what it reads, and the emulator the
tests run on breaks two transactions' deadlock over one document only by timing out every lock in it after 2 s.
Ten claims at once by one sponsor were measured aborting all together round after round, and in one run of six,
seven of them gave up after 25 attempts. A conditional write holds no lock, so a conflict costs one more read.

Every query has one equality filter and is sorted here, so the database needs no index beyond the single-field
ones Firestore keeps by itself.
"""

import datetime
import random
import time
import urllib.parse
from dataclasses import fields

from google.api_core import exceptions
from google.cloud import firestore

from .models import ACTIVE, Refusal, Session, parse_iso

SESSIONS = "sessions"
CLAIMS = "claims"
SPONSORS = "sponsors"
MEASUREMENTS = "measurements"

# A change whose reads went stale is decided again. Each round of conflict commits at least one of the changes in it,
# so ten claims at once on one document need at most ten rounds. Each retry first waits a random moment, up to twice
# as long each time, so changes that conflicted together do not meet again.
ATTEMPTS = 25
BACKOFF_S = 0.01
BACKOFF_CAP_S = 0.5
# What Firestore answers when a write's precondition no longer holds: the document changed (or vanished) since it was
# read, or it was created since it was read as missing. Production may also abort a write that contends with others.
CONFLICTS = (exceptions.FailedPrecondition, exceptions.AlreadyExists, exceptions.NotFound, exceptions.Aborted)

SESSION_FIELDS = tuple(f.name for f in fields(Session))


def _key(*parts):
    return "|".join(urllib.parse.quote(part, safe="") for part in parts)


def claim_id(project, concern):
    """The id of a concern's claim document. A document id cannot hold `/`, and both a project and a concern do."""
    return _key(project, concern)


def sponsor_id(sponsor):
    return _key(sponsor)


def _document(session):
    return {**session.__dict__, "pull_requests": list(session.pull_requests), "active": session.active}


def _from(data):
    return Session(**{name: data[name] for name in SESSION_FIELDS if name in data})


def _newest_first(sessions):
    return sorted(sessions, key=lambda s: (s.created_at, s.id), reverse=True)


def _silent(session, now, lost_after_s):
    last = parse_iso(session.heartbeat_at or session.created_at)
    return parse_iso(now) - last > datetime.timedelta(seconds=lost_after_s)


class _Attempt:
    """One try at a change: the documents it read, and its writes, committed together or not at all."""

    def __init__(self, client):
        self.client, self.batch, self.writes, self.seen = client, client.batch(), 0, {}

    def read(self, refs):
        """The documents at `refs`, by path, as dicts (None for a missing one), all as they were at one moment."""
        found = {ref.path: None for ref in refs}
        if refs:
            for snapshot in self.client.get_all(refs):
                self.seen[snapshot.reference.path] = snapshot
                found[snapshot.reference.path] = snapshot.to_dict() if snapshot.exists else None
        return found

    def write(self, ref, data):
        """Set these fields of a document this attempt read, only if it is as read: unchanged, or still missing."""
        snapshot = self.seen[ref.path]
        if snapshot.exists:
            self.batch.update(ref, data, option=self.client.write_option(last_update_time=snapshot.update_time))
        else:
            self.batch.create(ref, data)
        self.writes += 1

    def create(self, ref, data):
        self.batch.create(ref, data)
        self.writes += 1

    def put(self, ref, data):
        """Replace a document, whatever it holds now."""
        self.batch.set(ref, data)
        self.writes += 1

    def remove(self, ref, field, ids):
        """Take `ids` out of an array field, whatever else the document holds now."""
        self.batch.set(ref, {field: firestore.ArrayRemove(ids)}, merge=True)
        self.writes += 1

    def commit(self):
        if self.writes:
            self.batch.commit()


class FirestoreStore:
    def __init__(self, database, project=None, seeds=(), client=None):
        """`database` in `project` (by default the client's own, from the environment it runs in). With
        FIRESTORE_EMULATOR_HOST set, the client talks to that emulator instead, as the tests do."""
        self.client = client or firestore.Client(project=project, database=database)
        self.database, self.project = database, self.client.project
        for seed in seeds:
            source = f"seed:{seed['skill']}:{seed['model']}"
            try:
                self._measurement(source).create({"source": source, "skill": seed["skill"], "model": seed["model"],
                                                  "usd": seed["usd"], "wall_clock_s": seed["wall_clock_s"], "at": ""})
            except exceptions.AlreadyExists:
                pass

    def _ref(self, session_id):
        return self.client.collection(SESSIONS).document(session_id)

    def _claim(self, project, concern):
        return self.client.collection(CLAIMS).document(claim_id(project, concern))

    def _sponsor(self, sponsor):
        return self.client.collection(SPONSORS).document(sponsor_id(sponsor))

    def _measurement(self, source):
        return self.client.collection(MEASUREMENTS).document(source)

    def _change(self, decide):
        """Answer decide(attempt) once the attempt's writes commit, deciding again on fresh reads while a conflict
        refuses them (see CONFLICTS). A decision that writes nothing answers at once."""
        for n in range(1, ATTEMPTS + 1):
            attempt = _Attempt(self.client)
            result = decide(attempt)
            try:
                attempt.commit()
                return result
            except CONFLICTS:
                if n == ATTEMPTS:
                    raise
                time.sleep(random.uniform(0, min(BACKOFF_CAP_S, BACKOFF_S * 2 ** n)))

    def _one(self, attempt, session_id):
        """The session as this attempt read it, or None."""
        ref = self._ref(session_id)
        data = attempt.read([ref])[ref.path]
        return _from(data) if data is not None else None

    def _release(self, attempt, ended, rewritten=()):
        """Take sessions that ended out of the documents that name them, except those this attempt rewrites."""
        removals = {}
        for s in ended:
            named = [(self._sponsor(s.sponsor), "active")]
            if s.holds:
                named.append((self._claim(s.project, s.concern), "holders"))
            for ref, field in named:
                if ref.path not in rewritten:
                    removals.setdefault(ref.path, (ref, field, []))[2].append(s.id)
        for ref, field, ids in removals.values():
            attempt.remove(ref, field, ids)

    def _end_lost(self, attempt, s, now):
        s.state, s.outcome, s.ended_at = "ended", "lost", now
        attempt.write(self._ref(s.id), {"state": "ended", "outcome": "lost", "ended_at": now, "active": False})

    def claim(self, session, cap, now, lost_after_s):
        self.expire_lost(now, lost_after_s)
        return self._change(lambda attempt: self._decide_claim(attempt, session, cap, now, lost_after_s))

    def _decide_claim(self, attempt, session, cap, now, lost_after_s):
        sponsor_ref = self._sponsor(session.sponsor)
        claim_ref = self._claim(session.project, session.concern) if session.holds else None
        docs = attempt.read([r for r in (sponsor_ref, claim_ref) if r is not None])
        listed = list((docs[sponsor_ref.path] or {}).get("active", []))
        holding = list((docs[claim_ref.path] or {}).get("holders", [])) if claim_ref else []
        named = list(dict.fromkeys(listed + holding))
        sessions = [_from(data) for data in attempt.read([self._ref(i) for i in named]).values() if data is not None]

        # What a claim does first (store.Store.claim): a counted session that has been silent too long ends as lost.
        lost = [s for s in sessions if s.active and _silent(s, now, lost_after_s)]
        for s in lost:
            self._end_lost(attempt, s, now)

        mine = _newest_first(s for s in sessions if s.active and s.sponsor == session.sponsor)
        holders = _newest_first(s for s in sessions if s.active and s.holds and s.project == session.project
                                and s.concern == session.concern) if claim_ref else []
        refusal = None
        if holders:
            refusal = Refusal("running-session",
                              f"{session.concern} is held by a running /loop-build or /loop-design session: "
                              + "; ".join(s.describe() for s in holders),
                              sessions=holders)
        elif len(mine) >= cap:
            refusal = Refusal("sponsor-cap",
                              f"{session.sponsor} already runs {len(mine)} sessions, the cap of {cap}: "
                              + "; ".join(s.describe() for s in mine),
                              sessions=mine, cap=cap)

        # A claim that starts its session always rewrites the sponsor's document, and the concern's claim when it
        # holds it, so it commits only if neither changed since it read them.
        started = [session.id] if refusal is None else []
        active = [s.id for s in mine] + started
        if sorted(active) != sorted(listed):
            attempt.write(sponsor_ref, {"sponsor": session.sponsor, "active": active})
        if claim_ref is not None:
            held = [s.id for s in holders] + started
            if sorted(held) != sorted(holding):
                attempt.write(claim_ref, {"project": session.project, "concern": session.concern, "holders": held})
        self._release(attempt, lost, rewritten={ref.path for ref in (sponsor_ref, claim_ref) if ref is not None})
        if refusal is None:
            attempt.create(self._ref(session.id), _document(session))
        return refusal

    def get(self, session_id):
        snapshot = self._ref(session_id).get()
        return _from(snapshot.to_dict()) if snapshot.exists else None

    def _where(self, field, value):
        query = self.client.collection(SESSIONS).where(filter=firestore.FieldFilter(field, "==", value))
        return [_from(snapshot.to_dict()) for snapshot in query.stream()]

    def list(self, state="active", sponsor=None, project=None):
        if state == "active":
            found = self._where("active", True)
        elif sponsor:
            found = self._where("sponsor", sponsor)
        elif project:
            found = self._where("project", project)
        else:
            found = [_from(snapshot.to_dict()) for snapshot in self.client.collection(SESSIONS).stream()]
        return _newest_first(s for s in found if (not sponsor or s.sponsor == sponsor)
                             and (not project or s.project == project))

    def set_execution(self, session_id, execution):
        try:
            self._ref(session_id).update({"execution": execution})
        except exceptions.NotFound:
            pass

    def mark_running(self, session_id, now):
        def decide(attempt):
            s = self._one(attempt, session_id)
            if s is None:
                return None
            if s.state == "starting":
                s.state, s.started_at, s.heartbeat_at = "running", now, now
            elif s.state == "stopping":
                s.started_at, s.heartbeat_at = s.started_at or now, now
            else:
                return s
            attempt.write(self._ref(session_id), {"state": s.state, "started_at": s.started_at,
                                                  "heartbeat_at": s.heartbeat_at})
            return s

        return self._change(decide)

    def publish(self, session_id, spend, now):
        """Record the latest spend (None keeps the last one) and that the job is alive; answer whether to stop."""
        def decide(attempt):
            s = self._one(attempt, session_id)
            if s is None:
                return False
            if s.active:
                changes = {"heartbeat_at": now}
                if spend is not None:
                    changes["spend"] = spend
                attempt.write(self._ref(session_id), changes)
            return bool(s.stop_requested or not s.active)

        return self._change(decide)

    def request_stop(self, session_id):
        def decide(attempt):
            s = self._one(attempt, session_id)
            if s is None or not s.active:
                return None
            s.stop_requested, s.state = True, "stopping"
            attempt.write(self._ref(session_id), {"stop_requested": True, "state": "stopping"})
            return s

        return self._change(decide)

    def finish(self, session_id, outcome, spend, pull_requests, now, final_message=None):
        def decide(attempt):
            s = self._one(attempt, session_id)
            if s is None:
                raise LookupError(f"no session has the id {session_id}")
            s.state, s.outcome, s.ended_at = "ended", outcome, now
            s.spend = spend or s.spend
            s.pull_requests, s.final_message = list(pull_requests), final_message
            attempt.write(self._ref(session_id), _document(s))
            if spend and spend.get("basis") == "sdk result":
                attempt.put(self._measurement(session_id), {
                    "source": session_id, "skill": s.skill, "model": s.model, "usd": spend["usd"],
                    "wall_clock_s": spend["wall_clock_s"], "at": now})
            self._release(attempt, [s])
            return s

        return self._change(decide)

    def measurements(self, skill, model, limit=10):
        query = self.client.collection(MEASUREMENTS).where(filter=firestore.FieldFilter("skill", "==", skill))
        found = [m for m in (snapshot.to_dict() for snapshot in query.stream()) if m["model"] == model]
        found.sort(key=lambda m: (m["at"], m["source"]), reverse=True)
        return [{"usd": m["usd"], "wall_clock_s": m["wall_clock_s"], "source": m["source"]} for m in found[:limit]]

    def expire_lost(self, now, lost_after_s):
        def decide(attempt, session_id):
            s = self._one(attempt, session_id)
            if s is None or not (s.active and _silent(s, now, lost_after_s)):
                return False  # it published, or ended, since the query
            self._end_lost(attempt, s, now)
            self._release(attempt, [s])
            return True

        silent = [s for s in self._where("active", True) if _silent(s, now, lost_after_s)]
        return [s.id for s in _newest_first(silent) if self._change(lambda attempt, i=s.id: decide(attempt, i))]
