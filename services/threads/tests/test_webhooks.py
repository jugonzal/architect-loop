"""C3: review comments on a concern's PR appear in that concern's thread within a minute (command-center/D6).

GitHub delivers them to threads' own app (command-center/D27), signed with its webhook secret. These tests sign with
a made-up secret. The mirror is written before the delivery is answered, so a comment is readable as soon as GitHub
has delivered it; how long GitHub takes to deliver is for staging to show.
"""

import time
import unittest

from support import (
    OTHER_PROJECT, PROJECT, ApiTestCase, concern_thread, pull_request, review_comment_event, review_event, sign,
)


class ReviewCommentMirrorTest(ApiTestCase):
    def test_a_signed_review_comment_is_in_the_concern_thread_when_the_delivery_is_answered(self):
        delivered = time.monotonic()
        response = self.deliver("pull_request_review_comment", review_comment_event(
            comment_id=101, body="Is this cached?", login="dave", association="NONE"))
        self.assertEqual(response.status_code, 200)
        mirrored = response.get_json()["mirrored"]
        self.assertEqual(len(mirrored), 1)

        page = self.messages(concern_thread("command-center", "threads"))
        readable = time.monotonic()
        self.assertLess(readable - delivered, 60)
        [message] = page["messages"]
        self.assertEqual(message["id"], mirrored[0])
        self.assertEqual(message["kind"], "message")
        self.assertEqual(message["body"], "Is this cached?")
        self.assertEqual(message["author"], {"type": "github", "login": "dave", "association": "NONE"})
        self.assertEqual(message["source"], {
            "type": "github_review_comment",
            "url": f"https://github.com/{PROJECT}/pull/17#discussion_r101",
            "pull_request": 17,
            "path": "services/threads/threads/app.py",
            "review_state": None,
        })

    def test_a_submitted_review_with_text_is_mirrored(self):
        response = self.deliver("pull_request_review", review_event(body="Looks right to me.", state="approved"))
        self.assertEqual(len(response.get_json()["mirrored"]), 1)
        [message] = self.messages(concern_thread())["messages"]
        self.assertEqual(message["body"], "Looks right to me.")
        self.assertEqual(message["author"], {"type": "github", "login": "erin", "association": "COLLABORATOR"})
        self.assertEqual(message["source"]["type"], "github_review")
        self.assertEqual(message["source"]["review_state"], "approved")
        self.assertIsNone(message["source"]["path"])

    def test_a_review_without_text_has_nothing_to_mirror(self):
        # A review that only holds inline comments arrives with an empty body; its comments arrive on their own.
        for body in ("", None):
            response = self.deliver("pull_request_review", review_event(review_id=300, body=body, state="commented"))
            self.assertEqual(response.get_json(), {"mirrored": []})
        self.assertEqual(self.messages(concern_thread())["messages"], [])

    def test_a_redelivery_mirrors_nothing_twice(self):
        event = review_comment_event(comment_id=555)
        first = self.deliver("pull_request_review_comment", event).get_json()["mirrored"]
        second = self.deliver("pull_request_review_comment", event)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.get_json(), {"mirrored": []})
        self.assertEqual([m["id"] for m in self.messages(concern_thread())["messages"]], first)
        review = review_event(review_id=555)
        self.assertEqual(len(self.deliver("pull_request_review", review).get_json()["mirrored"]), 1,
                         "a review and a comment with the same id are different things")

    def test_a_pull_request_naming_two_concerns_is_mirrored_into_both(self):
        pr = pull_request(body="Concern: command-center/threads\nConcern: command-center/session-narration\n")
        mirrored = self.deliver("pull_request_review_comment", review_comment_event(pr=pr)).get_json()["mirrored"]
        self.assertEqual(len(mirrored), 2)
        self.assertEqual(len(self.messages(concern_thread("command-center", "threads"))["messages"]), 1)
        self.assertEqual(len(self.messages(concern_thread("command-center", "session-narration"))["messages"]), 1)

    def test_only_a_pull_request_that_names_a_concern_is_mirrored(self):
        bodies = [
            "",
            None,
            "No trailer here",
            "Concern: <loop>/<concern>",  # the PR template's placeholder
            "Concern: command-center",  # no concern
            "  Concern: command-center/threads trailing words",
        ]
        for body in bodies:
            with self.subTest(body=body):
                pr = pull_request(body=body)
                response = self.deliver("pull_request_review_comment", review_comment_event(pr=pr))
                self.assertEqual(response.get_json(), {"mirrored": []})
        self.assertEqual(self.db.rows("SELECT count(*) FROM messages"), [(0,)])

    def test_the_trailer_is_read_from_anywhere_in_the_body(self):
        pr = pull_request(body="## What this changes\n\nStuff.\n\nConcern: command-center/threads\r\n\n🤖 Generated\n")
        self.assertEqual(len(self.deliver("pull_request_review_comment",
                                          review_comment_event(pr=pr)).get_json()["mirrored"]), 1)

    def test_a_comment_lands_in_the_project_it_was_made_in(self):
        self.deliver("pull_request_review_comment", review_comment_event(repo=OTHER_PROJECT, comment_id=7))
        self.assertEqual(len(self.messages(concern_thread(project=OTHER_PROJECT))["messages"]), 1)
        self.assertEqual(self.messages(concern_thread())["messages"], [])

    def test_a_repository_that_is_not_a_project_here_is_ignored(self):
        response = self.deliver("pull_request_review_comment", review_comment_event(repo="someone/else"))
        self.assertEqual(response.get_json(), {"mirrored": []})
        self.assertEqual(self.db.rows("SELECT count(*) FROM threads"), [(0,)])

    def test_other_events_and_actions_are_accepted_and_ignored(self):
        cases = [
            ("ping", {"zen": "Keep it logically awesome.", "hook_id": 1}),
            ("push", {"ref": "refs/heads/main", "repository": {"full_name": PROJECT}}),
            ("pull_request_review_comment", review_comment_event(action="edited")),
            ("pull_request_review_comment", review_comment_event(action="deleted")),
            ("pull_request_review", review_event(action="dismissed")),
            ("pull_request_review", review_event(action="edited")),
        ]
        for event, payload in cases:
            with self.subTest(event=event, action=payload.get("action")):
                response = self.deliver(event, payload)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.get_json(), {"mirrored": []})
        self.assertEqual(self.db.rows("SELECT count(*) FROM messages"), [(0,)])


class WebhookSignatureTest(ApiTestCase):
    def test_a_delivery_signed_with_another_secret_is_refused_and_stores_nothing(self):
        response = self.deliver("pull_request_review_comment", review_comment_event(), secret=b"not-the-secret")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.get_json()["error"], "unauthorized")
        self.assertEqual(self.db.rows("SELECT count(*) FROM threads"), [(0,)])

    def test_a_delivery_whose_body_was_changed_after_signing_is_refused(self):
        signature = sign(b'{"action": "created"}')
        response = self.deliver("pull_request_review_comment", review_comment_event(), signature=signature)
        self.assertEqual(response.status_code, 401)

    def test_an_unsigned_or_oddly_signed_delivery_is_refused(self):
        raw = b"{}"
        for headers in ({"X-GitHub-Event": "ping"},
                        {"X-GitHub-Event": "ping", "X-Hub-Signature-256": "sha1=abc"},
                        {"X-GitHub-Event": "ping", "X-Hub-Signature": "sha1=" + "0" * 40}):
            with self.subTest(headers=headers):
                response = self.api.post("/webhooks/github", data=raw, content_type="application/json",
                                         headers=headers, valid_request=False)
                self.assertEqual(response.status_code, 401)

    def test_without_a_configured_secret_every_delivery_is_refused(self):
        from threads.app import create_app
        from dataclasses import replace
        from support import ContractClient
        app = create_app(replace(self.settings, webhook_secret=None), store=self.store, github=self.github,
                         identity=self.identity, clock=self.clock)
        self.api = ContractClient(app, self)
        response = self.deliver("pull_request_review_comment", review_comment_event(), secret=b"")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(self.db.rows("SELECT count(*) FROM messages"), [(0,)])

    def test_a_signed_body_that_is_not_json_is_a_bad_request(self):
        raw = b"not json"
        response = self.api.post("/webhooks/github", data=raw, content_type="application/json",
                                 headers={"X-GitHub-Event": "ping", "X-Hub-Signature-256": sign(raw)},
                                 valid_request=False)
        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
