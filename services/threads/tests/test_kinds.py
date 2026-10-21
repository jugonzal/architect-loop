"""C1: every message has a kind, message, milestone or narration, so a client can collapse a session thread to its
milestones. People write messages; a session writes any kind.
"""

import unittest

from support import RUNNER_TOKEN, ApiTestCase, concern_thread, session_thread


class KindTest(ApiTestCase):
    def test_a_person_writes_messages(self):
        self.assertEqual(self.post_message(concern_thread(), body="plain")["kind"], "message")
        self.assertEqual(self.post_message(concern_thread(), body="explicit", kind="message")["kind"], "message")

    def test_only_a_session_writes_milestones_and_narration(self):
        for kind in ("milestone", "narration"):
            with self.subTest(kind=kind):
                response = self.api.post(f"{session_thread()}/messages", token="alice-token",
                                         json_body={"body": "I am a session", "kind": kind})
                self.assertEqual(response.status_code, 403)
        self.assertEqual(self.db.rows("SELECT count(*) FROM messages"), [(0,)])

    def test_a_session_writes_every_kind(self):
        for kind in ("milestone", "narration", "message"):
            self.assertEqual(self.runner_post(f"a {kind}", kind=kind)["kind"], kind)
        self.assertEqual([m["kind"] for m in self.messages(session_thread())["messages"]],
                         ["milestone", "narration", "message"])

    def test_a_session_thread_collapses_to_its_milestones(self):
        self.runner_post("started", kind="milestone")
        self.runner_post("reading LOOP.md", kind="narration")
        self.runner_post("reading the concern", kind="narration")
        self.post_message(session_thread(), body="Go on", token="bob-token")
        self.runner_post("branch opened", kind="milestone")
        self.runner_post("running tests", kind="narration")
        self.runner_post("tests run: 12 passed", kind="milestone")

        milestones = self.messages(session_thread(), query="?kind=milestone")
        self.assertEqual([m["body"] for m in milestones["messages"]],
                         ["started", "branch opened", "tests run: 12 passed"])
        talk = self.messages(session_thread(), query="?kind=milestone&kind=message")
        self.assertEqual([m["body"] for m in talk["messages"]],
                         ["started", "Go on", "branch opened", "tests run: 12 passed"])

        first = self.messages(session_thread(), query="?kind=milestone&limit=2")
        self.assertEqual([m["body"] for m in first["messages"]], ["started", "branch opened"])
        rest = self.messages(session_thread(), query=f"?kind=milestone&limit=2&after={first['next_after']}")
        self.assertEqual([m["body"] for m in rest["messages"]], ["tests run: 12 passed"])
        self.assertIsNone(rest["next_after"])

    def test_an_unknown_kind_is_refused(self):
        response = self.api.post(f"{session_thread()}/messages", token=RUNNER_TOKEN, valid_request=False,
                                 json_body={"body": "x", "kind": "decision", "sponsor": "alice"})
        self.assertEqual(response.status_code, 400)
        response = self.api.post(f"{concern_thread()}/messages", token="alice-token", valid_request=False,
                                 json_body={"body": "x", "kind": "decision"})
        self.assertEqual(response.status_code, 400)
        response = self.api.get(f"{concern_thread()}/messages?kind=decision", token="alice-token",
                                valid_request=False)
        self.assertEqual(response.status_code, 400)


class NewMessageValidationTest(ApiTestCase):
    def refused(self, **kwargs):
        response = self.api.post(f"{concern_thread()}/messages", token="alice-token", valid_request=False, **kwargs)
        self.assertEqual(response.status_code, 400, response.get_json())
        self.assertEqual(response.get_json()["error"], "bad_request")

    def test_bodies_that_are_not_a_message_are_refused(self):
        self.refused(json_body={"body": ""})
        self.refused(json_body={"body": "x" * 65537})
        self.refused(json_body={"body": 12})
        self.refused(json_body={"text": "wrong field"})
        self.refused(json_body={"body": "x", "extra": True})
        self.refused(json_body=["body"])
        self.refused(data="not json", content_type="application/json")
        self.assertEqual(self.db.rows("SELECT count(*) FROM messages"), [(0,)])

    def test_the_longest_body_is_accepted(self):
        self.assertEqual(len(self.post_message(concern_thread(), body="x" * 65536)["body"]), 65536)

    def test_paging_parameters_are_checked(self):
        for query in ("?limit=0", "?limit=501", "?after=-1", "?after=x"):
            with self.subTest(query=query):
                response = self.api.get(f"{concern_thread()}/messages{query}", token="alice-token",
                                        valid_request=False)
                self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
