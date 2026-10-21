"""The runner's own store of sessions and their spend (command-center/D26).

Nothing else keeps these, and nothing about any loop lives here: wiping it loses the estimates' history and the
record of past sessions, never a loop's state (G4). A dispatch claims its concern here in one transaction, so of
two dispatches at once at most one starts (session-runner Approach, C3).

`Store` is the interface the dispatcher and the session job use. `SqliteStore` implements it on one SQLite file,
which is what the tests exercise and what a single machine can run. Which database backs the store in staging
and production is not recorded in the loop's decisions yet; any backend must give `claim` the same guarantee.
"""

import contextlib
import datetime
import json
import os
import sqlite3
from typing import Protocol

from .models import ACTIVE, Refusal, Session, parse_iso


class Store(Protocol):
    def claim(self, session: Session, cap: int, now: str, lost_after_s: float) -> Refusal | None: ...
    def get(self, session_id: str) -> Session | None: ...
    def list(self, state: str = "active", sponsor: str | None = None, project: str | None = None) -> list: ...
    def set_execution(self, session_id: str, execution: str) -> None: ...
    def mark_running(self, session_id: str, now: str) -> Session | None: ...
    def publish(self, session_id: str, spend: dict | None, now: str) -> bool: ...
    def request_stop(self, session_id: str) -> Session | None: ...
    def finish(self, session_id: str, outcome: str, spend: dict | None, pull_requests: list, now: str) -> Session: ...
    def measurements(self, skill: str, model: str, limit: int = 10) -> list: ...
    def expire_lost(self, now: str, lost_after_s: float) -> list: ...


SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    project TEXT NOT NULL,
    skill TEXT NOT NULL,
    concern TEXT NOT NULL,
    arguments TEXT NOT NULL,
    model TEXT NOT NULL,
    sponsor TEXT NOT NULL,
    budget_usd REAL NOT NULL,
    plugin_release TEXT NOT NULL,
    branch TEXT NOT NULL,
    created_at TEXT NOT NULL,
    state TEXT NOT NULL,
    outcome TEXT,
    started_at TEXT,
    ended_at TEXT,
    heartbeat_at TEXT,
    spend TEXT,
    pull_requests TEXT NOT NULL DEFAULT '[]',
    stop_requested INTEGER NOT NULL DEFAULT 0,
    execution TEXT
);
-- A second guarantee under the claim's transaction: one active session per concern.
CREATE UNIQUE INDEX IF NOT EXISTS one_active_session_per_concern
    ON sessions (project, concern) WHERE state IN ('starting', 'running', 'stopping');
CREATE INDEX IF NOT EXISTS sessions_by_sponsor ON sessions (sponsor, state);
CREATE TABLE IF NOT EXISTS measurements (
    source TEXT PRIMARY KEY,
    skill TEXT NOT NULL,
    model TEXT NOT NULL,
    usd REAL NOT NULL,
    wall_clock_s REAL NOT NULL,
    at TEXT NOT NULL
);
"""

COLUMNS = ("id", "project", "skill", "concern", "arguments", "model", "sponsor", "budget_usd", "plugin_release",
           "branch", "created_at", "state", "outcome", "started_at", "ended_at", "heartbeat_at", "spend",
           "pull_requests", "stop_requested", "execution")
ACTIVE_SQL = "('starting', 'running', 'stopping')"


def _row_to_session(row):
    data = dict(zip(COLUMNS, row))
    data["spend"] = json.loads(data["spend"]) if data["spend"] else None
    data["pull_requests"] = json.loads(data["pull_requests"] or "[]")
    data["stop_requested"] = bool(data["stop_requested"])
    return Session(**data)


class SqliteStore:
    def __init__(self, path, seeds=()):
        self.path = path
        if os.path.dirname(path):
            os.makedirs(os.path.dirname(path), exist_ok=True)
        with self._connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript(SCHEMA)
            for seed in seeds:
                db.execute("INSERT OR IGNORE INTO measurements VALUES (?, ?, ?, ?, ?, ?)",
                           (f"seed:{seed['skill']}:{seed['model']}", seed["skill"], seed["model"], seed["usd"],
                            seed["wall_clock_s"], ""))

    @contextlib.contextmanager
    def _connect(self):
        db = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        try:
            yield db
        finally:
            db.close()

    @contextlib.contextmanager
    def _transaction(self):
        """A write transaction that takes the lock up front, so a check and the write after it cannot interleave."""
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                yield db
            except BaseException:
                db.execute("ROLLBACK")
                raise
            db.execute("COMMIT")

    def _select(self, db, where="1", params=()):
        rows = db.execute(f"SELECT {', '.join(COLUMNS)} FROM sessions WHERE {where} ORDER BY created_at DESC, id DESC",
                          params).fetchall()
        return [_row_to_session(r) for r in rows]

    def _expire_lost(self, db, now, lost_after_s):
        moment = parse_iso(now)
        lost = []
        for session in self._select(db, f"state IN {ACTIVE_SQL}"):
            last = parse_iso(session.heartbeat_at or session.created_at)
            if moment - last > datetime.timedelta(seconds=lost_after_s):
                db.execute("UPDATE sessions SET state = 'ended', outcome = 'lost', ended_at = ? WHERE id = ?",
                           (now, session.id))
                lost.append(session.id)
        return lost

    def claim(self, session, cap, now, lost_after_s):
        with self._transaction() as db:
            self._expire_lost(db, now, lost_after_s)
            on_concern = self._select(db, f"project = ? AND concern = ? AND state IN {ACTIVE_SQL}",
                                      (session.project, session.concern))
            if on_concern:
                return Refusal("running-session",
                               f"{session.concern} already has a running session: "
                               + "; ".join(s.describe() for s in on_concern),
                               sessions=on_concern)
            mine = self._select(db, f"sponsor = ? AND state IN {ACTIVE_SQL}", (session.sponsor,))
            if len(mine) >= cap:
                return Refusal("sponsor-cap",
                               f"{session.sponsor} already runs {len(mine)} sessions, the cap of {cap}: "
                               + "; ".join(s.describe() for s in mine),
                               sessions=mine, cap=cap)
            values = {**session.__dict__, "spend": json.dumps(session.spend) if session.spend else None,
                      "pull_requests": json.dumps(session.pull_requests),
                      "stop_requested": int(session.stop_requested)}
            db.execute(f"INSERT INTO sessions ({', '.join(COLUMNS)}) VALUES ({', '.join('?' for _ in COLUMNS)})",
                       [values[c] for c in COLUMNS])
            return None

    def get(self, session_id):
        with self._connect() as db:
            found = self._select(db, "id = ?", (session_id,))
        return found[0] if found else None

    def list(self, state="active", sponsor=None, project=None):
        where, params = ["1"], []
        if state == "active":
            where.append(f"state IN {ACTIVE_SQL}")
        if sponsor:
            where.append("sponsor = ?")
            params.append(sponsor)
        if project:
            where.append("project = ?")
            params.append(project)
        with self._connect() as db:
            return self._select(db, " AND ".join(where), params)

    def set_execution(self, session_id, execution):
        with self._transaction() as db:
            db.execute("UPDATE sessions SET execution = ? WHERE id = ?", (execution, session_id))

    def mark_running(self, session_id, now):
        with self._transaction() as db:
            db.execute("UPDATE sessions SET state = 'running', started_at = ?, heartbeat_at = ? "
                       "WHERE id = ? AND state = 'starting'", (now, now, session_id))
            db.execute("UPDATE sessions SET started_at = COALESCE(started_at, ?), heartbeat_at = ? "
                       "WHERE id = ? AND state = 'stopping'", (now, now, session_id))
            found = self._select(db, "id = ?", (session_id,))
        return found[0] if found else None

    def publish(self, session_id, spend, now):
        """Record the latest spend (None keeps the last one) and that the job is alive; answer whether to stop."""
        with self._transaction() as db:
            if spend is not None:
                db.execute(f"UPDATE sessions SET spend = ?, heartbeat_at = ? WHERE id = ? AND state IN {ACTIVE_SQL}",
                           (json.dumps(spend), now, session_id))
            else:
                db.execute(f"UPDATE sessions SET heartbeat_at = ? WHERE id = ? AND state IN {ACTIVE_SQL}",
                           (now, session_id))
            row = db.execute("SELECT stop_requested, state FROM sessions WHERE id = ?", (session_id,)).fetchone()
        return bool(row and (row[0] or row[1] not in ACTIVE))

    def request_stop(self, session_id):
        with self._transaction() as db:
            found = self._select(db, f"id = ? AND state IN {ACTIVE_SQL}", (session_id,))
            if not found:
                return None
            db.execute("UPDATE sessions SET stop_requested = 1, state = 'stopping' WHERE id = ?", (session_id,))
            return self._select(db, "id = ?", (session_id,))[0]

    def finish(self, session_id, outcome, spend, pull_requests, now):
        with self._transaction() as db:
            db.execute("UPDATE sessions SET state = 'ended', outcome = ?, ended_at = ?, "
                       "spend = COALESCE(?, spend), pull_requests = ? WHERE id = ?",
                       (outcome, now, json.dumps(spend) if spend else None, json.dumps(pull_requests), session_id))
            session = self._select(db, "id = ?", (session_id,))[0]
            if spend and spend.get("basis") == "sdk result":
                db.execute("INSERT OR REPLACE INTO measurements VALUES (?, ?, ?, ?, ?, ?)",
                           (session_id, session.skill, session.model, spend["usd"], spend["wall_clock_s"], now))
        return session

    def measurements(self, skill, model, limit=10):
        with self._connect() as db:
            rows = db.execute("SELECT usd, wall_clock_s, source FROM measurements WHERE skill = ? AND model = ? "
                              "ORDER BY at DESC, source DESC LIMIT ?", (skill, model, limit)).fetchall()
        return [{"usd": usd, "wall_clock_s": wall, "source": source} for usd, wall, source in rows]

    def expire_lost(self, now, lost_after_s):
        with self._transaction() as db:
            return self._expire_lost(db, now, lost_after_s)
