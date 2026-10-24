"""The real clients for GitHub, the metadata server, the status service and Expo, each against a fake server over HTTP
on 127.0.0.1 that records what it was sent. Nothing here reaches a real service or a real device."""

import base64
import json
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from notify.errors import InvalidCredentials, Unavailable
from notify.expo import Expo
from notify.github import GitHub
from notify.status import MetadataIdentity, StatusService

from support import PROJECT, document, item, push_token


def jwt_with_exp(exp):
    def part(obj):
        return base64.urlsafe_b64encode(json.dumps(obj).encode()).decode().rstrip("=")

    return f"{part({'alg': 'RS256'})}.{part({'exp': exp, 'aud': 'x'})}.c2lnbmF0dXJl"


class FakeServer:
    """Answers each request with `answer(method, path, query, headers, body)` -> (status, body), and records it."""

    def __init__(self, answer):
        self.answer = answer
        self.requests = []
        server = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def handle_any(self):
                length = int(self.headers.get("Content-Length") or 0)
                raw = self.rfile.read(length) if length else b""
                url = urlparse(self.path)
                record = {"method": self.command, "path": url.path, "query": parse_qs(url.query),
                          "headers": dict(self.headers), "body": json.loads(raw) if raw else None}
                server.requests.append(record)
                status, body = server.answer(record)
                data = body if isinstance(body, bytes) else json.dumps(body).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            do_GET = do_POST = handle_any

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.httpd.server_address[1]}"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()


class ServerTest(unittest.TestCase):
    def serve(self, answer):
        server = FakeServer(answer)
        self.addCleanup(server.close)
        return server


class GitHubTest(ServerTest):
    def test_a_caller_is_the_login_get_user_answers_for_their_token(self):
        server = self.serve(lambda r: (200, {"login": "alice", "id": 1})
                            if r["headers"].get("Authorization") == "Bearer gho_alice" else (401, {}))
        github = GitHub(server.url)
        self.assertEqual(github.user_login("gho_alice"), "alice")
        self.assertEqual(server.requests[0]["path"], "/user")
        self.assertEqual(server.requests[0]["headers"]["Accept"], "application/vnd.github+json")
        with self.assertRaises(InvalidCredentials):
            github.user_login("gho_forged")

    def test_github_failing_is_unavailable_not_unauthorized(self):
        server = self.serve(lambda r: (502, {"message": "bad gateway"}))
        with self.assertRaises(Unavailable):
            GitHub(server.url).user_login("gho_alice")
        with self.assertRaises(Unavailable):
            GitHub("http://127.0.0.1:9", timeout=1).user_login("gho_alice")


class StatusServiceTest(ServerTest):
    def setUp(self):
        self.token = jwt_with_exp(time.time() + 3600)
        self.metadata = self.serve(lambda r: (200, self.token.encode())
                                   if r["headers"].get("Metadata-Flavor") == "Google" else (403, {}))
        self.doc = document(item("command-center/notifications/Q1", unblocks=["x/y"]))
        self.answer = (200, self.doc)
        self.status = self.serve(lambda r: self.answer if r["headers"].get("Authorization") == f"Bearer {self.token}"
                                 else (401, {"error": "unauthorized", "message": "no"}))
        self.client = StatusService(self.status.url, MetadataIdentity(self.metadata.url))

    def test_it_reads_the_projects_document_with_an_id_token_for_the_status_service(self):
        self.assertEqual(self.client.document(PROJECT), self.doc)
        [mint] = self.metadata.requests
        self.assertEqual(mint["path"], "/computeMetadata/v1/instance/service-accounts/default/identity")
        self.assertEqual(mint["query"], {"audience": [self.status.url], "format": ["full"]})
        [read] = self.status.requests
        self.assertEqual(read["path"], "/projects/jugonzal/architect-loop/status")

    def test_an_id_token_is_reused_until_shortly_before_it_expires(self):
        self.client.document(PROJECT)
        self.client.document(PROJECT)
        self.assertEqual(len(self.metadata.requests), 1)
        self.token = jwt_with_exp(time.time() + 60)
        identity = MetadataIdentity(self.metadata.url)
        identity.id_token("aud")
        identity.id_token("aud")
        self.assertEqual(len(self.metadata.requests), 3, "a token within five minutes of expiring is not reused")

    def test_a_status_service_that_refuses_or_fails_is_unavailable(self):
        for answer in ((503, {"error": "unavailable", "message": "main cannot be read"}),
                       (403, {"error": "forbidden", "message": "no"}),
                       (200, b"<html>"),
                       (200, document(project="example/other")),
                       (200, {"project": PROJECT})):
            with self.subTest(answer=answer):
                self.answer = answer
                with self.assertRaises(Unavailable):
                    self.client.document(PROJECT)

    def test_no_metadata_server_is_unavailable(self):
        client = StatusService(self.status.url, MetadataIdentity("http://127.0.0.1:9", timeout=1))
        with self.assertRaises(Unavailable):
            client.document(PROJECT)
        self.assertEqual(self.status.requests, [], "nothing is read without the service's identity")


class ExpoTest(ServerTest):
    def tickets(self, request):
        out = []
        for message in request["body"]:
            if message["to"].endswith("[gone]"):
                out.append({"status": "error", "message": "not registered",
                            "details": {"error": "DeviceNotRegistered"}})
            else:
                out.append({"status": "ok", "id": "ticket"})
        return 200, {"data": out}

    def test_it_posts_the_messages_and_reads_a_ticket_for_each(self):
        server = self.serve(self.tickets)
        expo = Expo(server.url + "/--/api/v2/push/send")
        messages = [{"to": push_token("a"), "title": "t", "body": "b"}, {"to": push_token("gone"), "title": "t"}]
        tickets = expo.send(messages)
        self.assertEqual([t.ok for t in tickets], [True, False])
        self.assertTrue(tickets[1].device_gone)
        [request] = server.requests
        self.assertEqual((request["method"], request["path"]), ("POST", "/--/api/v2/push/send"))
        self.assertEqual(request["body"], messages)
        self.assertNotIn("Authorization", request["headers"])

    def test_more_than_a_hundred_go_in_requests_of_a_hundred(self):
        server = self.serve(self.tickets)
        tickets = Expo(server.url).send([{"to": push_token(str(i))} for i in range(250)])
        self.assertEqual(len(tickets), 250)
        self.assertEqual([len(r["body"]) for r in server.requests], [100, 100, 50])

    def test_an_access_token_is_sent_when_there_is_one(self):
        server = self.serve(self.tickets)
        Expo(server.url, access_token="expo-test-token").send([{"to": push_token("a")}])
        self.assertEqual(server.requests[0]["headers"]["Authorization"], "Bearer expo-test-token")

    def test_expo_failing_is_unavailable(self):
        for answer in ((503, {"errors": [{"code": "INTERNAL", "message": "down"}]}),
                       (200, {"data": []}),
                       (200, b"not json")):
            with self.subTest(answer=answer):
                server = self.serve(lambda r, a=answer: a)
                with self.assertRaises(Unavailable):
                    Expo(server.url).send([{"to": push_token("a")}])


if __name__ == "__main__":
    unittest.main()
