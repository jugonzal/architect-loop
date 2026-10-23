"""C2: each environment's served commit is read only with an HTTP GET of the URL in LOOP.md §3, and nothing taken
from the repository is ever run (command-center/D9). The URL is the first http(s) URL in the row's served-commit
cell, and a row without one is unknown (command-center/D56). A read that fails is unknown, never an older value.
"""

import os
import re
import subprocess
import unittest
from unittest import mock

from status import derivation, served

from support import ROOT, ServiceTestCase, concern, environment, loop_md

LS = derivation.load()


def table(*rows):
    head = ("| Environment | Where | Agents may read | Agents may write | Deployed by | "
            "Served commit: a command that prints its SHA | Verify with |\n"
            "| --- | --- | --- | --- | --- | --- | --- |\n")
    return "# LOOP.md\n\n## 3. Environments\n\n" + head + "".join(rows) + "\n## 4. Commands\n"


def row(name, cell, readable="yes"):
    return "| %s | somewhere | %s | no | owner | %s | |\n" % (name, readable, cell)


class TheUrlInEachRowTest(unittest.TestCase):
    """Which URL the service reads for each row, from LOOP.md alone (command-center/D56)."""

    def rows(self, text):
        return {r["name"]: r for r in served.rows(LS, text)}

    def test_the_url_is_the_first_http_url_in_the_served_commit_cell(self):
        rows = self.rows(table(
            row("staging/status", "`sh scripts/gcp/served.sh https://status-665570365697.us-east1.run.app/version`"),
            row("two", "`sh served.sh http://a.example/version`, else https://b.example/version"),
            row("local/status", "`sh scripts/gcp/served.sh http://localhost:8080/version`"),
            row("plain", "https://plain.example/v1/version."),
        ))
        self.assertEqual(rows["staging/status"]["url"], "https://status-665570365697.us-east1.run.app/version")
        self.assertEqual(rows["two"]["url"], "http://a.example/version")
        self.assertEqual(rows["local/status"]["url"], "http://localhost:8080/version")
        self.assertEqual(rows["plain"]["url"], "https://plain.example/v1/version")
        self.assertTrue(all(r["error"] is None for r in rows.values()))

    def test_a_row_without_a_url_is_unknown_and_says_why(self):
        rows = self.rows(table(
            row("cmd", "`cat served.txt`"),
            row("todo", "TODO(owner): `sh scripts/gcp/served.sh <URL>`, with the URL `bootstrap.sh production` prints"),
            row("hidden", "`sh scripts/gcp/served.sh https://x.example/version`", readable="TODO(owner): no"),
            row("empty", ""),
        ))
        self.assertIsNone(rows["cmd"]["url"])
        self.assertIn("names no http(s) URL", rows["cmd"]["error"])
        self.assertIn("D56", rows["cmd"]["error"])
        self.assertIsNone(rows["todo"]["url"])
        self.assertIn("TODO(owner)", rows["todo"]["error"])
        # A row agents may not read stays unread, as the terminal leaves it, even when it names a URL.
        self.assertIsNone(rows["hidden"]["url"])
        self.assertIn("may not read", rows["hidden"]["error"])
        self.assertIsNone(rows["empty"]["url"])

    def test_the_rows_are_those_the_derivation_reads_in_its_order(self):
        text = loop_md("http://127.0.0.1:9", "/tmp/marker")
        self.assertEqual([r["name"] for r in served.rows(LS, text)],
                         [r["name"] for r in LS.environment_rows(text)])

    def test_this_repositorys_rows_read_the_url_their_served_sh_command_reads(self):
        with open(os.path.join(ROOT, "LOOP.md"), encoding="utf-8") as f:
            text = f.read()
        rows = self.rows(text)
        self.assertIn("staging/status", rows)
        for terminal in LS.environment_rows(text):
            with self.subTest(row=terminal["name"]):
                found = re.search(r"https?://\S+", terminal["command"] or "")
                if terminal["name"] == "main" or not found:
                    self.assertIsNone(rows[terminal["name"]]["url"])
                else:
                    self.assertEqual(rows[terminal["name"]]["url"], found.group(0))


class ReadingServedCommitsTest(ServiceTestCase):
    def test_a_served_commit_is_read_with_a_get_of_that_url(self):
        main = self.world.main()
        self.version.serve("/api/version", main[:12])
        doc = self.status()
        self.assertEqual(environment(doc, "staging/web"), {"name": "staging/web", "served": main, "error": None})
        # The first URL in the cell, not the second.
        self.assertEqual(environment(doc, "staging/api")["served"], main[:12])
        self.assertIn(("GET", "/staging/version"), self.version.requests)
        self.assertIn(("GET", "/api/version"), self.version.requests)
        self.assertNotIn(("GET", "/second/version"), self.version.requests)

    def test_the_main_row_is_mains_head_from_the_services_own_fetch(self):
        doc = self.status()
        self.assertEqual(environment(doc, "main"), {"name": "main", "served": self.world.main(), "error": None})

    def test_rows_without_a_url_are_unknown(self):
        doc = self.status()
        for name, words in (("staging/cmd", "names no http(s) URL"), ("staging/app", "may not read"),
                            ("production/web", "TODO(owner)")):
            with self.subTest(name=name):
                env = environment(doc, name)
                self.assertIsNone(env["served"])
                self.assertIn(words, env["error"])
                self.assertIn({"fact": "%s's served commit" % name, "error": env["error"]}, doc["missing"])

    def test_it_runs_no_command_taken_from_the_repository(self):
        ran = []
        real = subprocess.run

        def recording(argv, *args, **kwargs):
            ran.append((list(argv) if not isinstance(argv, str) else argv, kwargs.get("shell", False)))
            return real(argv, *args, **kwargs)

        with mock.patch("subprocess.run", recording):
            self.status()
        # The staging/cmd row's command would have created the marker.
        self.assertFalse(os.path.exists(self.marker))
        self.assertTrue(ran)
        for argv, shell in ran:
            with self.subTest(argv=argv):
                self.assertFalse(shell)
                self.assertEqual(argv[0], "git", argv)

    def test_a_failed_read_is_unknown_and_never_the_value_read_before(self):
        main = self.world.main()
        self.assertEqual(environment(self.status(), "staging/web")["served"], main)
        failures = {
            "answered 503": (503, '{"commit": "%s"}' % main, 0),
            "answered 404": (404, "", 0),
            "is not JSON": (200, "<html>deploying</html>", 0),
            "names no commit": (200, '{"commit": "latest"}', 0),
            "failed": (200, '{"commit": "%s"}' % main, 3),  # slower than STATUS_SERVED_TIMEOUT_SECONDS
        }
        for words, (status, raw, delay) in failures.items():
            with self.subTest(words=words):
                self.version.answer("/staging/version", status, raw, delay=delay)
                self.deliver("push", self.push_event())
                env = environment(self.status(), "staging/web")
                self.assertIsNone(env["served"])
                self.assertIn("GET %s/staging/version %s" % (self.version.url, words), env["error"])

    def test_a_concern_that_rests_on_an_unreadable_environment_is_unknown(self):
        files = {"src/alpha/a.py": "x = 1\n"}
        self.open_pr(1, "sandbox/alpha", files)
        merge = self.merge_pr(1, "sandbox/alpha", files)
        self.version.serve("/staging/version", merge)
        self.deliver("push", self.push_event())
        self.assertEqual(concern(self.status(), "sandbox/alpha")["state"], "shipped")
        self.version.answer("/staging/version", 500, "")
        self.deliver("push", self.push_event())
        alpha = concern(self.status(), "sandbox/alpha")
        self.assertEqual(alpha["state"], "unknown")
        self.assertIsNone(alpha["inputs"]["served"]["commit"])
        self.assertIn("answered 500", alpha["inputs"]["served"]["error"])


class ServedUnitTest(unittest.TestCase):
    def test_only_a_sha_is_a_served_commit(self):
        for body, ok in (('{"commit": "ABCDEF1"}', "abcdef1"), ('{"commit": "abc"}', None), ('{"commit": 7}', None),
                         ('["abcdef1"]', None), ('{"commit": "abcdef1 "}', None)):
            with self.subTest(body=body):
                self.assertEqual(served.commit_of(body.encode()), ok)


if __name__ == "__main__":
    unittest.main()
