"""C3: the service stores no state a person typed. Deleting its cache and restarting gives the same answer.

Its only store is its clone of the project's repository, under STATUS_CACHE_DIR, and the last document in memory.
No operation takes anything a person wrote, and a delivery from GitHub only marks a document stale: nothing in its
payload becomes a fact.
"""

import os
import shutil

from support import PROJECT, ServiceTestCase, concern, spec_operations


class WipeTest(ServiceTestCase):
    def setUp(self):
        super().setUp()
        files = {"src/alpha/a.py": "x = 1\n"}
        self.open_pr(1, "sandbox/alpha", files)
        self.merge_pr(1, "sandbox/alpha", files)
        self.open_pr(2, "sandbox/beta", {"src/beta/b.py": "y = 1\n"})

    def test_deleting_the_cache_and_restarting_gives_the_same_answer(self):
        before = self.status()
        self.assertEqual(concern(before, "sandbox/alpha")["state"], "merged")
        self.assertEqual(concern(before, "sandbox/beta")["state"], "building")
        shutil.rmtree(self.settings.cache_dir)
        self.restart()
        after = self.status()
        self.assertEqual(after, before)

    def test_restarting_on_the_cache_gives_the_same_answer_too(self):
        before = self.status()
        self.restart()
        self.assertEqual(self.status(), before)

    def test_the_cache_holds_only_the_clone_of_the_repository(self):
        self.status()
        top = os.listdir(self.settings.cache_dir)
        self.assertEqual(top, [PROJECT.split("/")[0]])
        self.assertEqual(os.listdir(os.path.join(self.settings.cache_dir, top[0])), [PROJECT.split("/")[1] + ".git"])
        clone = os.path.join(self.settings.cache_dir, PROJECT + ".git")
        self.assertTrue(os.path.exists(os.path.join(clone, "HEAD")))
        with open(os.path.join(clone, "config")) as f:
            config = f.read()
        self.assertNotIn("ghs_", config, "the clone keeps no token")

    def test_a_delivery_never_supplies_a_fact(self):
        before = self.status()
        forged = {
            "action": "closed",
            "number": 2,
            "pull_request": {"number": 2, "merged": True, "merge_commit_sha": "f" * 40, "head": {"ref": "sandbox/beta"},
                             "body": "Concern: sandbox/beta"},
            "repository": {"full_name": PROJECT},
            "commits": [{"id": "e" * 40, "message": "Concern: sandbox/beta"}],
        }
        self.assertEqual(self.deliver("pull_request", forged).get_json(), {"project": PROJECT, "stale": True})
        after = self.status()
        self.assertEqual(after, before)
        self.assertEqual(concern(after, "sandbox/beta")["state"], "building")

    def test_no_operation_takes_what_a_person_wrote(self):
        # People only read. The one write is GitHub's delivery, which is signed with the app's secret.
        writes = {(m, p) for m, p in spec_operations() if m != "GET"}
        self.assertEqual(writes, {("POST", "/webhooks/github")})
