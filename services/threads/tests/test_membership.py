"""C1: each loop, concern and session has one thread with a stable URL and a member list. A project member can read
its whole history, post and watch it, and anyone else cannot read it. The runner posts to a session's thread as that
session, labelled with its sponsor (command-center/D28).
"""

import unittest

from support import (
    OTHER_PROJECT, PROJECT, RUNNER_EMAIL, RUNNER_TOKEN, UNTRUSTED_JWT, ApiTestCase, base, concern_thread,
    loop_thread, session_thread,
)

THREADS = [loop_thread(), concern_thread(), session_thread()]


class MemberTest(ApiTestCase):
    def test_an_untouched_thread_reads_as_empty_with_its_members(self):
        for path in THREADS:
            with self.subTest(path=path):
                response = self.api.get(path, token="alice-token")
                self.assertEqual(response.status_code, 200)
                thread = response.get_json()
                self.assertEqual(thread["url"], path)
                self.assertEqual(thread["project"], PROJECT)
                self.assertEqual([m["login"] for m in thread["members"]], ["alice", "bob"])
                self.assertEqual(thread["watchers"], [])
                self.assertEqual(thread["last_seq"], 0)
                self.assertEqual(self.messages(path), {"messages": [], "next_after": None})
        self.assertEqual(self.db.rows("SELECT count(*) FROM threads"), [(0,)], "reading must not write")

    def test_each_scope_names_its_thread(self):
        loop = self.api.get(loop_thread(), token="alice-token").get_json()
        concern = self.api.get(concern_thread(), token="alice-token").get_json()
        session = self.api.get(session_thread("s-9"), token="alice-token").get_json()
        self.assertEqual((loop["scope"], loop["loop"], loop["concern"], loop["session"]),
                         ("loop", "command-center", None, None))
        self.assertEqual((concern["scope"], concern["loop"], concern["concern"], concern["session"]),
                         ("concern", "command-center", "threads", None))
        self.assertEqual((session["scope"], session["loop"], session["concern"], session["session"]),
                         ("session", None, None, "s-9"))

    def test_a_member_posts_as_themselves_and_every_member_reads_it(self):
        for path in THREADS:
            with self.subTest(path=path):
                posted = self.post_message(path, body="Why Postgres?", token="alice-token")
                self.assertEqual(posted["author"], {"type": "person", "login": "alice"})
                self.assertEqual(posted["kind"], "message")
                self.assertEqual(posted["thread"], path)
                self.assertEqual(posted["seq"], 1)
                self.assertEqual(posted["record_marks"], [])
                self.assertIsNone(posted["source"])
                page = self.messages(path, token="bob-token")
                self.assertEqual([m["id"] for m in page["messages"]], [posted["id"]])
                self.assertEqual(self.api.get(path, token="bob-token").get_json()["last_seq"], 1)

    def test_a_member_reads_the_whole_history_page_by_page(self):
        path = concern_thread()
        posted = [self.post_message(path, body=f"m{i}", token=("alice-token", "bob-token")[i % 2])["id"]
                  for i in range(7)]
        seen, after, pages = [], 0, 0
        while after is not None:
            page = self.messages(path, query=f"?after={after}&limit=3")
            seen += [m["id"] for m in page["messages"]]
            after = page["next_after"]
            pages += 1
        self.assertEqual(seen, posted)
        self.assertEqual(pages, 3)
        self.assertEqual([m["seq"] for m in self.messages(path)["messages"]], list(range(1, 8)))

    def test_one_thread_per_loop_concern_and_session(self):
        # The same name in different scopes, loops or projects is a different thread.
        paths = [
            loop_thread("threads"),
            concern_thread("command-center", "threads"),
            concern_thread("other-loop", "threads"),
            session_thread("threads"),
            concern_thread(project=OTHER_PROJECT),
        ]
        for i, path in enumerate(paths):
            self.post_message(path, body=f"in {i}")
        for i, path in enumerate(paths):
            self.assertEqual([m["body"] for m in self.messages(path)["messages"]], [f"in {i}"], path)
        self.post_message(paths[1], body="again")
        self.assertEqual(self.db.rows("SELECT count(*) FROM threads"), [(len(paths),)])

    def test_a_member_watches_and_unwatches(self):
        for path in THREADS:
            with self.subTest(path=path):
                watched = self.api.put(f"{path}/watchers/me", token="bob-token")
                self.assertEqual(watched.status_code, 200)
                again = self.api.put(f"{path}/watchers/me", token="bob-token").get_json()
                self.assertEqual([w["login"] for w in again["watchers"]], ["bob"])
                self.api.put(f"{path}/watchers/me", token="alice-token")
                thread = self.api.get(path, token="alice-token").get_json()
                self.assertEqual([w["login"] for w in thread["watchers"]], ["alice", "bob"])
                unwatched = self.api.delete(f"{path}/watchers/me", token="bob-token")
                self.assertEqual(unwatched.status_code, 200)
                self.assertEqual([w["login"] for w in unwatched.get_json()["watchers"]], ["alice"])

    def test_an_unknown_project_is_not_found(self):
        for path in (concern_thread(project="someone/else"), f"{base('someone/else')}/messages/1"):
            response = self.api.get(path, token="alice-token")
            self.assertEqual(response.status_code, 404)
            self.assertEqual(response.get_json()["error"], "not_found")

    def test_a_malformed_name_is_refused(self):
        response = self.api.get(f"{base()}/loops/-bad/thread", token="alice-token", valid_request=False)
        self.assertEqual(response.status_code, 400)


class NonMemberTest(ApiTestCase):
    def setUp(self):
        super().setUp()
        self.message = self.post_message(concern_thread(), body="members only")

    def every_person_operation(self):
        for path in THREADS:
            yield "GET", path, None
            yield "GET", f"{path}/messages", None
            yield "POST", f"{path}/messages", {"body": "let me in"}
            yield "PUT", f"{path}/watchers/me", None
            yield "DELETE", f"{path}/watchers/me", None
        yield "GET", f"{base()}/messages/{self.message['id']}", None
        yield "PUT", f"{base()}/messages/{self.message['id']}/record-marks/me", None
        yield "DELETE", f"{base()}/messages/{self.message['id']}/record-marks/me", None

    def test_a_signed_in_non_member_can_do_nothing(self):
        before = self.store_snapshot()
        for method, path, body in self.every_person_operation():
            with self.subTest(method=method, path=path):
                response = self.api.call(method, path, token="carol-token", json_body=body)
                self.assertEqual(response.status_code, 403)
                self.assertEqual(response.get_json()["error"], "forbidden")
                self.assertNotIn("members only", response.get_data(as_text=True))
        self.assertEqual(self.store_snapshot(), before)
        self.assertEqual(self.db.rows("SELECT count(*) FROM record_marks"), [(0,)])

    def test_a_member_of_another_project_is_not_a_member_here(self):
        response = self.api.get(concern_thread(project=OTHER_PROJECT), token="bob-token")
        self.assertEqual(response.status_code, 403)

    def test_no_token_or_a_bad_token_is_unauthorized(self):
        for method, path, body in self.every_person_operation():
            for headers in ({}, {"Authorization": "Bearer not-a-token"}, {"Authorization": "Basic YWxpY2U6eA=="},
                            {"Authorization": "Bearer "}):
                with self.subTest(method=method, path=path, headers=headers):
                    response = self.api.call(method, path, json_body=body, headers=headers, valid_request=False)
                    self.assertEqual(response.status_code, 401)
                    self.assertEqual(response.get_json()["error"], "unauthorized")
                    self.assertNotIn("members only", response.get_data(as_text=True))

    def test_when_github_cannot_be_reached_nothing_is_answered(self):
        self.github.down = True
        response = self.api.get(concern_thread(), token="alice-token")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.get_json()["error"], "unavailable")
        self.assertNotIn("members only", response.get_data(as_text=True))


class RevokedAccessTest(ApiTestCase):
    cache_seconds = 60

    def test_a_removed_collaborator_loses_access_once_the_cache_expires(self):
        self.assertEqual(self.api.get(concern_thread(), token="bob-token").status_code, 200)
        self.github.members[PROJECT].discard("bob")
        self.clock.now += 59
        self.assertEqual(self.api.get(concern_thread(), token="bob-token").status_code, 200)
        self.clock.now += 2
        self.assertEqual(self.api.get(concern_thread(), token="bob-token").status_code, 403)

    def test_github_is_asked_once_per_token_and_member_within_the_cache(self):
        for _ in range(5):
            self.api.get(concern_thread(), token="alice-token")
        self.assertEqual([c[0] for c in self.github.calls].count("user_login"), 1)
        self.assertEqual([c[0] for c in self.github.calls].count("is_collaborator"), 1)
        self.assertEqual([c[0] for c in self.github.calls].count("collaborators"), 1)


class RunnerTest(ApiTestCase):
    def test_the_runner_posts_as_the_session_labelled_with_its_sponsor(self):
        posted = self.runner_post("started", session="s-1", sponsor="alice")
        self.assertEqual(posted["author"], {"type": "session", "session": "s-1", "sponsor": "alice"})
        self.assertEqual(posted["kind"], "milestone")
        thread = self.api.get(session_thread("s-1"), token="bob-token").get_json()
        self.assertEqual(thread["sponsor"], "alice")
        self.assertEqual(self.messages(session_thread("s-1"), token="bob-token")["messages"][0]["author"],
                         posted["author"])
        self.assertEqual(self.identity.calls, [RUNNER_TOKEN])
        self.assertNotIn(("user_login", RUNNER_TOKEN), self.github.calls, "a service identity never goes to GitHub")

    def test_a_session_has_one_sponsor(self):
        self.runner_post("started", sponsor="alice")
        response = self.api.post(f"{session_thread()}/messages", token=RUNNER_TOKEN,
                                 json_body={"body": "hijack", "kind": "narration", "sponsor": "bob"})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.get_json()["error"], "conflict")
        self.assertEqual(len(self.messages(session_thread())["messages"]), 1)

    def test_the_runner_must_name_the_sponsor_and_a_person_must_not(self):
        response = self.api.post(f"{session_thread()}/messages", token=RUNNER_TOKEN, json_body={"body": "who?"})
        self.assertEqual(response.status_code, 400)
        response = self.api.post(f"{session_thread()}/messages", token="alice-token",
                                 json_body={"body": "as bob", "sponsor": "bob"})
        self.assertEqual(response.status_code, 400)

    def test_the_runner_reads_what_members_said_since_its_last_look(self):
        first = self.runner_post("tests run: 41 passed", kind="milestone")
        said = self.post_message(session_thread(), body="Stop after the tests, please", token="bob-token")
        thread = self.api.get(session_thread(), token=RUNNER_TOKEN)
        self.assertEqual(thread.status_code, 200)
        self.assertEqual(thread.get_json()["last_seq"], 2)
        page = self.messages(session_thread(), token=RUNNER_TOKEN, query=f"?after={first['seq']}")
        self.assertEqual([m["id"] for m in page["messages"]], [said["id"]])
        self.assertEqual(page["messages"][0]["author"], {"type": "person", "login": "bob"})
        reply = self.runner_post("Stopping after the tests.", kind="message")
        self.assertEqual(reply["seq"], 3)

    def test_the_runner_may_only_read_and_post_to_session_threads(self):
        message = self.post_message(concern_thread(), body="a person's message")
        denied = [
            ("GET", loop_thread(), None),
            ("GET", f"{loop_thread()}/messages", None),
            ("POST", f"{loop_thread()}/messages", {"body": "x", "sponsor": "alice"}),
            ("GET", concern_thread(), None),
            ("GET", f"{concern_thread()}/messages", None),
            ("POST", f"{concern_thread()}/messages", {"body": "x", "sponsor": "alice"}),
            ("PUT", f"{session_thread()}/watchers/me", None),
            ("DELETE", f"{session_thread()}/watchers/me", None),
            ("GET", f"{base()}/messages/{message['id']}", None),
            ("PUT", f"{base()}/messages/{message['id']}/record-marks/me", None),
        ]
        for method, path, body in denied:
            with self.subTest(method=method, path=path):
                # openapi.yaml does not offer the runner scheme on these, so the request itself is off-contract.
                response = self.api.call(method, path, token=RUNNER_TOKEN, json_body=body, valid_request=False)
                self.assertEqual(response.status_code, 403)
                self.assertNotIn("a person's message", response.get_data(as_text=True))

    def test_an_untrusted_service_identity_is_unauthorized_and_never_sent_to_github(self):
        response = self.api.post(f"{session_thread()}/messages", token=UNTRUSTED_JWT,
                                 json_body={"body": "x", "sponsor": "alice"})
        self.assertEqual(response.status_code, 401)
        self.assertNotIn(("user_login", UNTRUSTED_JWT), self.github.calls)
        self.assertEqual(self.db.rows("SELECT count(*) FROM messages"), [(0,)])

    def test_the_runner_service_account_is_what_the_identity_check_returns(self):
        self.identity.tokens = {RUNNER_TOKEN: RUNNER_EMAIL}
        self.assertEqual(self.api.get(session_thread(), token=RUNNER_TOKEN).status_code, 200)


if __name__ == "__main__":
    unittest.main()
