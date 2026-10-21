"""The thread store, in Postgres (command-center/D8): threads, their messages, watchers and "record this?" marks.

It holds only what people and sessions write (command-center/D26). The schema is in ../migrations/, applied by the
owner with `python -m threads.migrate`; this module never changes it.
"""

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

MESSAGE_COLUMNS = """
    m.id, m.seq, m.kind, m.author_type, m.author, m.author_label, m.body, m.created_at,
    m.source_type, m.source_url, m.source_pr, m.source_path, m.source_state,
    t.scope AS thread_scope, t.name AS thread_name
"""


class SponsorConflict(Exception):
    """The runner named a sponsor other than the one the session thread already has."""

    def __init__(self, sponsor):
        super().__init__(f"this session's sponsor is {sponsor}")
        self.sponsor = sponsor


class Store:
    def __init__(self, conninfo, max_size=8):
        self.pool = ConnectionPool(conninfo, min_size=1, max_size=max_size, open=True,
                                   kwargs={"row_factory": dict_row})

    def close(self):
        self.pool.close()

    # Threads.

    def thread(self, project, scope, name):
        """The thread's sponsor, last seq and watchers. A thread nobody has written to or watched has no row and
        reads as empty; reading never creates one."""
        with self.pool.connection() as conn:
            row = conn.execute("SELECT id, sponsor, last_seq FROM threads WHERE project = %s AND scope = %s AND name = %s",
                               (project, scope, name)).fetchone()
            if row is None:
                return {"sponsor": None, "last_seq": 0, "watchers": []}
            watchers = conn.execute("SELECT login, since FROM watchers WHERE thread_id = %s ORDER BY login",
                                    (row["id"],)).fetchall()
            return {"sponsor": row["sponsor"], "last_seq": row["last_seq"], "watchers": watchers}

    def watch(self, project, scope, name, login):
        with self.pool.connection() as conn, conn.transaction():
            thread_id = self._ensure_thread(conn, project, scope, name)
            conn.execute("INSERT INTO watchers (thread_id, login) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                         (thread_id, login))

    def unwatch(self, project, scope, name, login):
        with self.pool.connection() as conn:
            conn.execute("""DELETE FROM watchers w USING threads t
                            WHERE w.thread_id = t.id AND t.project = %s AND t.scope = %s AND t.name = %s
                              AND w.login = %s""", (project, scope, name, login))

    # Messages.

    def post(self, project, scope, name, *, kind, author_type, author, body, author_label=None, source=None):
        """Append a message and return it, or None when `source` was already mirrored into this thread.

        The thread's row is locked for the insert, so seq order is commit order within a thread: a reader paging
        with `after` never skips a message that committed after one with a greater seq. For a session author,
        `author_label` is the sponsor; the first one sets the thread's sponsor, and a different one later raises
        SponsorConflict.
        """
        source = source or {}
        with self.pool.connection() as conn, conn.transaction():
            thread_id = self._ensure_thread(conn, project, scope, name)
            thread = conn.execute("SELECT sponsor, last_seq FROM threads WHERE id = %s FOR UPDATE",
                                  (thread_id,)).fetchone()
            if author_type == "session":
                if thread["sponsor"] is None:
                    conn.execute("UPDATE threads SET sponsor = %s WHERE id = %s", (author_label, thread_id))
                elif thread["sponsor"] != author_label:
                    raise SponsorConflict(thread["sponsor"])
            if source:
                seen = conn.execute("SELECT 1 FROM messages WHERE thread_id = %s AND source_type = %s AND source_id = %s",
                                    (thread_id, source["type"], source["id"])).fetchone()
                if seen:
                    return None
            seq = thread["last_seq"] + 1
            conn.execute("UPDATE threads SET last_seq = %s WHERE id = %s", (seq, thread_id))
            message_id = conn.execute(
                """INSERT INTO messages (thread_id, seq, kind, author_type, author, author_label, body,
                                         source_type, source_id, source_url, source_pr, source_path, source_state)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id""",
                (thread_id, seq, kind, author_type, author, author_label, body, source.get("type"), source.get("id"),
                 source.get("url"), source.get("pull_request"), source.get("path"), source.get("review_state")),
            ).fetchone()["id"]
            return self._messages(conn, "m.id = %s", (message_id,))[0]

    def messages(self, project, scope, name, after=0, limit=100, kinds=None):
        """Up to `limit` messages with seq greater than `after`, oldest first, and whether more follow."""
        where = "t.project = %s AND t.scope = %s AND t.name = %s AND m.seq > %s"
        params = [project, scope, name, after]
        if kinds:
            where += " AND m.kind = ANY(%s)"
            params.append(list(kinds))
        with self.pool.connection() as conn:
            rows = self._messages(conn, where, params, limit + 1)
        return rows[:limit], len(rows) > limit

    def message(self, project, message_id):
        with self.pool.connection() as conn:
            rows = self._messages(conn, "t.project = %s AND m.id = %s", (project, message_id))
        return rows[0] if rows else None

    # "Record this?" marks.

    def mark(self, project, message_id, login):
        """Mark a message "record this?" for `login`. False when the project has no such message."""
        with self.pool.connection() as conn:
            row = conn.execute("""INSERT INTO record_marks (message_id, login)
                                  SELECT m.id, %s FROM messages m JOIN threads t ON t.id = m.thread_id
                                  WHERE m.id = %s AND t.project = %s
                                  ON CONFLICT DO NOTHING RETURNING message_id""",
                               (login, message_id, project)).fetchone()
            return row is not None or self._exists(conn, project, message_id)

    def unmark(self, project, message_id, login):
        with self.pool.connection() as conn:
            if not self._exists(conn, project, message_id):
                return False
            conn.execute("DELETE FROM record_marks WHERE message_id = %s AND login = %s", (message_id, login))
            return True

    # Helpers.

    @staticmethod
    def _ensure_thread(conn, project, scope, name):
        conn.execute("""INSERT INTO threads (project, scope, name) VALUES (%s, %s, %s)
                        ON CONFLICT (project, scope, name) DO NOTHING""", (project, scope, name))
        return conn.execute("SELECT id FROM threads WHERE project = %s AND scope = %s AND name = %s",
                            (project, scope, name)).fetchone()["id"]

    @staticmethod
    def _exists(conn, project, message_id):
        return conn.execute("SELECT 1 FROM messages m JOIN threads t ON t.id = m.thread_id WHERE m.id = %s AND t.project = %s",
                            (message_id, project)).fetchone() is not None

    @staticmethod
    def _messages(conn, where, params, limit=None):
        sql = f"SELECT {MESSAGE_COLUMNS} FROM messages m JOIN threads t ON t.id = m.thread_id WHERE {where} ORDER BY m.seq"
        if limit is not None:
            sql += f" LIMIT {int(limit)}"
        rows = conn.execute(sql, params).fetchall()
        if rows:
            marks = conn.execute("""SELECT message_id, login, marked_at FROM record_marks
                                    WHERE message_id = ANY(%s) ORDER BY marked_at, login""",
                                 ([r["id"] for r in rows],)).fetchall()
            by_message = {}
            for mark in marks:
                by_message.setdefault(mark["message_id"], []).append(mark)
            for row in rows:
                row["record_marks"] = by_message.get(row["id"], [])
        return rows
