"""The runner's Cloud Run service identity (command-center/D28): a Google-signed ID token whose audience is this
service and whose email is a service account this deployment trusts as the runner. The keys and the key set here are
made up and served locally, in the shape of https://www.googleapis.com/oauth2/v3/certs.
"""

import json
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import jwt
from jwt.algorithms import RSAAlgorithm

from fakegithub import new_key
from threads.errors import InvalidCredentials, Unavailable
from threads.identity import GoogleIdentity

AUDIENCE = "https://threads-test.example.run.app"
RUNNER = "runner@threads-test.iam.gserviceaccount.com"


class KeySet:
    def __init__(self, keys):
        body = json.dumps({"keys": [dict(json.loads(RSAAlgorithm.to_jwk(k.public_key())), kid=kid, alg="RS256",
                                         use="sig") for kid, k in keys.items()]}).encode()
        self.hits = 0
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                outer.hits += 1
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.httpd.server_address[1]}/oauth2/v3/certs"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()


class GoogleIdentityTest(unittest.TestCase):
    def setUp(self):
        self.key, _ = new_key()
        self.other, _ = new_key()
        self.keys = KeySet({"k1": self.key})
        self.addCleanup(self.keys.close)
        self.identity = GoogleIdentity(AUDIENCE, [RUNNER], certs_url=self.keys.url)

    def token(self, key=None, kid="k1", **overrides):
        now = int(time.time())
        claims = {"iss": "https://accounts.google.com", "aud": AUDIENCE, "email": RUNNER, "email_verified": True,
                  "sub": "1234567890", "iat": now, "exp": now + 3600}
        claims.update(overrides)
        claims = {k: v for k, v in claims.items() if v is not None}
        return jwt.encode(claims, key or self.key, algorithm="RS256", headers={"kid": kid})

    def test_the_runners_id_token_is_accepted(self):
        self.assertEqual(self.identity.verify(self.token()), RUNNER)
        self.assertEqual(self.identity.verify(self.token(iss="accounts.google.com")), RUNNER)

    def test_the_key_set_is_fetched_once_and_reused(self):
        for _ in range(3):
            self.identity.verify(self.token())
        self.assertEqual(self.keys.hits, 1)

    def test_tokens_that_are_not_the_runner_are_refused(self):
        refused = {
            "another audience": self.token(aud="https://status-test.example.run.app"),
            "another issuer": self.token(iss="https://evil.example"),
            "another service account": self.token(email="someone@else.iam.gserviceaccount.com"),
            "an unverified email": self.token(email_verified=False),
            "no email": self.token(email=None),
            "expired": self.token(iat=int(time.time()) - 7200, exp=int(time.time()) - 3600),
            "signed by another key": self.token(key=self.other),
            "an unknown key id": self.token(kid="k9"),
            "not a token": "eyJ.not.atoken",
            "unsigned": jwt.encode({"aud": AUDIENCE, "email": RUNNER}, None, algorithm="none"),
            "symmetric": jwt.encode({"iss": "https://accounts.google.com", "aud": AUDIENCE, "email": RUNNER,
                                     "email_verified": True, "exp": int(time.time()) + 60},
                                    "k" * 32, algorithm="HS256", headers={"kid": "k1"}),
        }
        for why, token in refused.items():
            with self.subTest(why):
                with self.assertRaises(InvalidCredentials):
                    self.identity.verify(token)

    def test_with_no_trusted_runner_nothing_is_accepted(self):
        identity = GoogleIdentity(AUDIENCE, [], certs_url=self.keys.url)
        with self.assertRaises(InvalidCredentials):
            identity.verify(self.token())
        unconfigured = GoogleIdentity(None, [RUNNER], certs_url=self.keys.url)
        with self.assertRaises(InvalidCredentials):
            unconfigured.verify(self.token())

    def test_an_unreachable_key_set_is_unavailable(self):
        identity = GoogleIdentity(AUDIENCE, [RUNNER], certs_url="http://127.0.0.1:9/certs")
        with self.assertRaises(Unavailable):
            identity.verify(self.token())


if __name__ == "__main__":
    unittest.main()
