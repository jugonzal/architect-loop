"""The thread store's schema ships as SQL files that the owner applies with `python -m threads.migrate`, because a
migration of the shared store is a migration of shared data (LOOP.md §2). The service never migrates on start.
"""

import os
import subprocess
import sys
import unittest

from support import SERVICE, Database
from threads import migrate


class MigrationTest(unittest.TestCase):
    def setUp(self):
        self.db = Database()
        self.addCleanup(self.db.drop)

    def tables(self):
        return {row[0] for row in self.db.rows(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = %s", self.db.schema)}

    def test_an_empty_database_is_migrated_once(self):
        self.assertEqual(migrate.pending(self.db.conninfo), ["0001_threads.sql"])
        self.assertEqual(migrate.apply(self.db.conninfo), ["0001_threads.sql"])
        self.assertEqual(self.tables(), {"schema_migrations", "threads", "messages", "watchers", "record_marks"})
        self.assertEqual(migrate.pending(self.db.conninfo), [])
        self.assertEqual(migrate.apply(self.db.conninfo), [], "a second run changes nothing")

    def test_the_command_lists_then_applies_what_is_pending(self):
        env = dict(os.environ, DATABASE_URL=self.db.conninfo)
        dry = subprocess.run([sys.executable, "-m", "threads.migrate", "--dry-run"], cwd=SERVICE, env=env,
                             capture_output=True, text=True)
        self.assertEqual(dry.returncode, 0, dry.stderr)
        self.assertIn("pending 0001_threads.sql", dry.stdout)
        self.assertEqual(self.tables(), set(), "a dry run writes nothing")
        real = subprocess.run([sys.executable, "-m", "threads.migrate"], cwd=SERVICE, env=env,
                              capture_output=True, text=True)
        self.assertEqual(real.returncode, 0, real.stderr)
        self.assertIn("applied 0001_threads.sql", real.stdout)
        again = subprocess.run([sys.executable, "-m", "threads.migrate"], cwd=SERVICE, env=env,
                               capture_output=True, text=True)
        self.assertIn("nothing to apply", again.stdout)

    def test_the_command_needs_a_database_url(self):
        env = {k: v for k, v in os.environ.items() if k != "DATABASE_URL"}
        result = subprocess.run([sys.executable, "-m", "threads.migrate"], cwd=SERVICE, env=env,
                                capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("DATABASE_URL", result.stderr)

    def test_migrations_are_numbered_sql_files(self):
        names = sorted(os.listdir(os.path.join(SERVICE, "migrations")))
        self.assertTrue(names)
        for i, name in enumerate(names, start=1):
            self.assertRegex(name, rf"^{i:04d}_[a-z0-9_]+\.sql$")


if __name__ == "__main__":
    unittest.main()
