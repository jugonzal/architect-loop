"""Apply the thread store's migrations: `python -m threads.migrate [--dry-run]`, from services/threads/.

It applies every file in ../migrations/ that the database has not recorded in `schema_migrations`, in order, each
in its own transaction, and prints what it did. A second run applies nothing. Against staging or production this
is a migration of shared data, which only the owner runs (LOOP.md §2); the service itself never migrates on start.
The database is the one in DATABASE_URL (a libpq URL or conninfo; PGOPTIONS and the other libpq variables apply).
"""

import argparse
import os
import sys

import psycopg

MIGRATIONS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "migrations")


def available():
    return sorted(name for name in os.listdir(MIGRATIONS) if name.endswith(".sql"))


def _applied(conn):
    exists = conn.execute("SELECT to_regclass('schema_migrations')").fetchone()[0]
    if exists is None:
        return set()
    return {row[0] for row in conn.execute("SELECT version FROM schema_migrations")}


def pending(conninfo):
    with psycopg.connect(conninfo) as conn:
        done = _applied(conn)
    return [name for name in available() if name not in done]


def apply(conninfo, log=lambda line: None):
    """Apply what is pending and return the names applied."""
    applied = []
    with psycopg.connect(conninfo) as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS schema_migrations (
                            version    text        PRIMARY KEY,
                            applied_at timestamptz NOT NULL DEFAULT now())""")
        conn.commit()
        for name in available():
            with conn.transaction():
                # Serialise concurrent runs: the second waits, then sees the first's work and skips it.
                conn.execute("LOCK TABLE schema_migrations IN EXCLUSIVE MODE")
                if name in _applied(conn):
                    continue
                with open(os.path.join(MIGRATIONS, name)) as f:
                    conn.execute(f.read())
                conn.execute("INSERT INTO schema_migrations (version) VALUES (%s)", (name,))
            applied.append(name)
            log(f"applied {name}")
    return applied


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m threads.migrate", description=__doc__.split("\n\n")[0])
    parser.add_argument("--dry-run", action="store_true", help="list the pending migrations and change nothing")
    args = parser.parse_args(argv)
    conninfo = os.environ.get("DATABASE_URL")
    if not conninfo:
        print("DATABASE_URL is not set: it names the database to migrate", file=sys.stderr)
        return 2
    if args.dry_run:
        names = pending(conninfo)
        for name in names:
            print(f"pending {name}")
        if not names:
            print("nothing to apply")
        return 0
    if not apply(conninfo, log=print):
        print("nothing to apply")
    return 0


if __name__ == "__main__":
    sys.exit(main())
