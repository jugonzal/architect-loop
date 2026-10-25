"""D3: a tick is accepted only with a Google-signed OIDC token whose audience is the notifier's URL and whose email is
a service account this deployment trusts to tick (its own). The keys and the key set here are made up and served
locally, in the shape of https://www.googleapis.com/oauth2/v3/certs, and the whole app is wired to the real check."""

import json
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.algorithms import RSAAlgorithm

from notify.app import create_app
from notify.errors import InvalidCredentials, Unavailable
from notify.identity import GoogleIdentity

from support import NOTIFY_IDENTITY, PROJECT, Harness

AUDIENCE = "https://notify-test.example.run.app"


def new_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


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


class TokenMaker:
    def setUp(self):
        self.key = new_key()
        self.keys = KeySet({"k1": self.key})
        self.addCleanup(self.keys.close)

    def token(self, key=None, kid="k1", **overrides):
        now = int(time.time())
        claims = {"iss": "https://accounts.google.com", "aud": AUDIENCE, "email": NOTIFY_IDENTITY,
                  "email_verified": True, "iat": now, "exp": now + 3600, **overrides}
        claims = {k: v for k, v in claims.items() if v is not None}
        return jwt.encode(claims, key or self.key, algorithm="RS256", headers={"kid": kid})


class GoogleIdentityTest(TokenMaker, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.identity = GoogleIdentity(AUDIENCE, [NOTIFY_IDENTITY], certs_url=self.keys.url)

    def test_the_notifiers_own_token_is_accepted(self):
        self.assertEqual(self.identity.verify(self.token()), NOTIFY_IDENTITY)
        self.assertEqual(self.identity.verify(self.token(email=NOTIFY_IDENTITY.upper())), NOTIFY_IDENTITY.upper())

    def test_any_other_token_is_refused(self):
        cases = {
            "another audience": self.token(aud="https://status-test.example.run.app"),
            "another identity": self.token(email="runner@notify-test.iam.gserviceaccount.com"),
            "an unverified email": self.token(email_verified=False),
            "no email": self.token(email=None),
            "expired": self.token(exp=int(time.time()) - 60),
            "another issuer": self.token(iss="https://example.com"),
            "signed by another key": self.token(key=new_key()),
            "an unknown key id": self.token(kid="k9"),
            "not a JWT": "a.b.c",
        }
        for case, token in cases.items():
            with self.subTest(case=case):
                with self.assertRaises(InvalidCredentials):
                    self.identity.verify(token)

    def test_a_deployment_that_trusts_no_one_refuses_everyone(self):
        for identity in (GoogleIdentity(None, [NOTIFY_IDENTITY], certs_url=self.keys.url),
                         GoogleIdentity(AUDIENCE, [], certs_url=self.keys.url)):
            with self.assertRaises(InvalidCredentials):
                identity.verify(self.token())

    def test_googles_keys_out_of_reach_is_unavailable(self):
        identity = GoogleIdentity(AUDIENCE, [NOTIFY_IDENTITY], certs_url="http://127.0.0.1:9/certs")
        with self.assertRaises(Unavailable):
            identity.verify(self.token())


class TickWithTheRealCheckTest(TokenMaker, Harness, unittest.TestCase):
    """POST /tick through the app with the real token check in place of the fake."""

    def setUp(self):
        TokenMaker.setUp(self)
        self.make()
        self.app = create_app(self.settings, store=self.store, github=self.github, notifier=self.notifier,
                              identity=GoogleIdentity(AUDIENCE, [NOTIFY_IDENTITY], certs_url=self.keys.url),
                              clock=lambda: 0.0, now=self.clock)
        self.client = self.app.test_client()

    def test_only_the_notifiers_own_token_reads_the_queue(self):
        refused = self.client.post("/tick", headers={"Authorization": f"Bearer {self.token(aud='https://x')}"})
        self.assertEqual(refused.status_code, 401)
        self.assertEqual(self.status.reads, [])
        accepted = self.client.post("/tick", headers={"Authorization": f"Bearer {self.token()}"})
        self.assertEqual(accepted.status_code, 200, accepted.get_json())
        self.assertIn(PROJECT, self.status.reads)
        self.assertEqual(self.github.calls, [])


if __name__ == "__main__":
    unittest.main()
