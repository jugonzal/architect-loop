"""C2: nothing in a thread changes a loop's derived state. Any member can mark a message "record this?", no model
classifies messages, and only the skill's write to the repository counts (command-center/D36).

What these tests can show before staging: a mark is stored as a mark and changes nothing else in the store, and the
service asks GitHub only who is calling and who the members are. test_github_client.py shows, over HTTP, that the
service never sends GitHub anything but reads. Whether the status service's answer stays the same needs the status
service, on staging.
"""

import os
import re
import unittest

from support import OTHER_PROJECT, SERVICE, ApiTestCase, base, concern_thread, review_comment_event, session_thread


class RecordMarkTest(ApiTestCase):
    def setUp(self):
        super().setUp()
        self.message = self.post_message(concern_thread(), body="Let's keep the store in Postgres", token="bob-token")
        self.mark_path = f"{base()}/messages/{self.message['id']}/record-marks/me"

    def test_any_member_marks_a_message_record_this(self):
        marked = self.api.put(self.mark_path, token="alice-token")
        self.assertEqual(marked.status_code, 200)
        self.assertEqual([m["login"] for m in marked.get_json()["record_marks"]], ["alice"])
        self.api.put(self.mark_path, token="alice-token")
        self.api.put(self.mark_path, token="bob-token")
        shown = self.api.get(f"{base()}/messages/{self.message['id']}", token="bob-token").get_json()
        self.assertEqual([m["login"] for m in shown["record_marks"]], ["alice", "bob"])
        listed = self.messages(concern_thread())["messages"][0]
        self.assertEqual(listed["record_marks"], shown["record_marks"])

    def test_a_member_removes_only_their_own_mark(self):
        self.api.put(self.mark_path, token="alice-token")
        self.api.put(self.mark_path, token="bob-token")
        after = self.api.delete(self.mark_path, token="bob-token").get_json()
        self.assertEqual([m["login"] for m in after["record_marks"]], ["alice"])
        again = self.api.delete(self.mark_path, token="bob-token")
        self.assertEqual(again.status_code, 200)
        self.assertEqual([m["login"] for m in again.get_json()["record_marks"]], ["alice"])

    def test_marking_changes_nothing_but_the_mark(self):
        self.runner_post("started")
        self.api.put(f"{concern_thread()}/watchers/me", token="alice-token")
        before = self.store_snapshot()
        calls_before = len(self.github.calls)

        self.api.put(self.mark_path, token="alice-token")
        self.api.put(self.mark_path, token="bob-token")
        self.api.delete(self.mark_path, token="bob-token")

        self.assertEqual(self.store_snapshot(), before, "a mark must not change a message, thread or watcher")
        self.assertEqual(self.db.rows("SELECT login FROM record_marks"), [("alice",)])
        reads = {"user_login", "is_collaborator", "collaborators"}
        self.assertTrue({c[0] for c in self.github.calls[calls_before:]} <= reads,
                        "marking may only ask GitHub who is calling and who the members are")

    def test_mirrored_and_session_messages_can_be_marked_too(self):
        mirrored = self.deliver("pull_request_review_comment", review_comment_event()).get_json()["mirrored"][0]
        said = self.runner_post("I think the cap should be 2", kind="message")
        for message_id in (mirrored, said["id"]):
            response = self.api.put(f"{base()}/messages/{message_id}/record-marks/me", token="alice-token")
            self.assertEqual(response.status_code, 200)
        self.assertEqual(self.messages(session_thread())["messages"][0]["record_marks"][0]["login"], "alice")

    def test_a_message_outside_the_project_is_not_found(self):
        missing = self.api.put(f"{base()}/messages/999999/record-marks/me", token="alice-token")
        self.assertEqual(missing.status_code, 404)
        elsewhere = self.api.put(f"{base(OTHER_PROJECT)}/messages/{self.message['id']}/record-marks/me",
                                 token="alice-token")
        self.assertEqual(elsewhere.status_code, 404)
        self.assertEqual(self.api.get(f"{base(OTHER_PROJECT)}/messages/{self.message['id']}",
                                      token="alice-token").status_code, 404)
        self.assertEqual(self.db.rows("SELECT count(*) FROM record_marks"), [(0,)])


class NoClassifierTest(unittest.TestCase):
    """No model reads messages (command-center/D36): the service has no dependency or call that could."""

    def test_no_model_client_is_a_dependency_or_imported(self):
        with open(os.path.join(SERVICE, "requirements.txt")) as f:
            requirements = f.read().lower()
        for name in ("anthropic", "openai", "claude", "vertexai", "google-cloud-aiplatform", "langchain"):
            self.assertNotIn(name, requirements)
        package = os.path.join(SERVICE, "threads")
        for filename in sorted(os.listdir(package)):
            if filename.endswith(".py"):
                with open(os.path.join(package, filename)) as f:
                    source = f.read()
                self.assertIsNone(re.search(r"^\s*(import|from)\s+(anthropic|openai|claude|vertexai)", source, re.M),
                                  filename)


if __name__ == "__main__":
    unittest.main()
