"""Callers that are services (command-center/status-callers, D66): a Google-signed ID token whose audience is the
status service's own URL and whose email is a service account its manifest trusts gets the document a member gets.
Anything else that looks like an ID token is refused with 401, and a person's GitHub token works as before.

The keys and the key set here are made up and served on 127.0.0.1, in the shape of
https://www.googleapis.com/oauth2/v3/certs, as threads' tests do for the runner.
"""

import json
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import jwt
from jwt.algorithms import RSAAlgorithm

from status.config import GOOGLE_CERTS, Settings
from status.errors import InvalidCredentials, Unavailable
from status.identity import GoogleIdentity

from support import APP_KEY, ServiceTestCase, _new_key, status_path

AUDIENCE = "https://status-test.example.run.app"
NOTIFIER = "notify@status-test.iam.gserviceaccount.com"
# APP_KEY signs Google's ID tokens here; OTHER_KEY is one Google never published.
OTHER_KEY, _ = _new_key()


class KeySet:
    """Google's published keys, made up: a JWK set on 127.0.0.1 that counts how often it is fetched."""

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
        self.url = "http://127.0.0.1:%d/oauth2/v3/certs" % self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()


def id_token(key=APP_KEY, kid="k1", **overrides):
    """An ID token as Cloud Run's metadata server hands a service: Google-signed, for one audience."""
    now = int(time.time())
    claims = {"iss": "https://accounts.google.com", "aud": AUDIENCE, "email": NOTIFIER, "email_verified": True,
              "sub": "1234567890", "iat": now, "exp": now + 3600}
    claims.update(overrides)
    claims = {k: v for k, v in claims.items() if v is not None}
    return jwt.encode(claims, key, algorithm="RS256", headers={"kid": kid})


def refused_tokens():
    now = int(time.time())
    return {
        "another service account": id_token(email="runner@status-test.iam.gserviceaccount.com"),
        "another audience": id_token(aud="https://threads-test.example.run.app"),
        "expired": id_token(iat=now - 7200, exp=now - 3600),
        "signed by a key Google never published": id_token(key=OTHER_KEY),
        "an unknown key id": id_token(kid="k9"),
        "another issuer": id_token(iss="https://issuer.example"),
        "an unverified email": id_token(email_verified=False),
        "no email": id_token(email=None),
        "no expiry": id_token(exp=None),
        "unsigned": jwt.encode({"iss": "https://accounts.google.com", "aud": AUDIENCE, "email": NOTIFIER,
                                "email_verified": True, "exp": now + 60}, None, algorithm="none"),
        "symmetric": jwt.encode({"iss": "https://accounts.google.com", "aud": AUDIENCE, "email": NOTIFIER,
                                 "email_verified": True, "iat": now, "exp": now + 60},
                                "k" * 32, algorithm="HS256", headers={"kid": "k1"}),
        "not a token": "eyJ.not.atoken",
    }


class TrustedServiceTest(ServiceTestCase):
    """The status API, deployed with its manifest's trust: its own URL as the audience, the notifier trusted."""

    def setUp(self):
        self.keys = KeySet({"k1": APP_KEY})
        self.addCleanup(self.keys.close)
        super().setUp()
        self.restart(self.trusting())

    def trusting(self, **changes):
        values = dict(audience=AUDIENCE, caller_service_accounts=(NOTIFIER,), caller_keys_url=self.keys.url)
        values.update(changes)
        return self.make_settings(**values)

    def test_a_trusted_service_reads_the_document_a_member_gets(self):
        as_service = self.status(token=id_token())
        self.assertEqual(as_service, self.status(token="alice-token"))
        self.assertEqual(as_service["project"], "example/shop")

    def test_a_trusted_service_is_no_person_so_github_is_not_asked_who_it_is(self):
        self.github.requests.clear()
        self.status(token=id_token())
        self.assertNotIn(("GET", "/user"), self.github.requests)
        self.assertFalse(any("/collaborators/" in path for _, path in self.github.requests))

    def test_the_trusted_account_is_matched_without_case(self):
        self.restart(self.trusting(caller_service_accounts=(NOTIFIER.upper(),)))
        self.status(token=id_token())

    def test_any_other_id_token_is_refused_and_never_sent_to_github(self):
        for why, token in refused_tokens().items():
            with self.subTest(why):
                self.github.requests.clear()
                self.assertEqual(self.status(token=token, expect=401)["error"], "unauthorized")
                self.assertNotIn(("GET", "/user"), self.github.requests)

    def test_a_persons_github_token_works_as_before(self):
        self.assertEqual(self.status(token="alice-token")["project"], "example/shop")
        self.assertEqual(self.status(token="carol-token", expect=403)["error"], "forbidden")
        self.assertEqual(self.status(token="gho_forged", expect=401)["error"], "unauthorized")

    def test_googles_keys_are_fetched_once_and_reused(self):
        for _ in range(3):
            self.status(token=id_token())
        self.assertEqual(self.keys.hits, 1)

    def test_when_googles_keys_cannot_be_fetched_it_answers_503(self):
        self.restart(self.trusting(caller_keys_url="http://127.0.0.1:9/certs"))
        self.assertEqual(self.status(token=id_token(), expect=503)["error"], "unavailable")


class UntrustingServiceTest(ServiceTestCase):
    """A deployment that trusts no service, as every deployment did before this concern."""

    def test_an_id_token_is_treated_as_a_github_token_as_before(self):
        self.github.requests.clear()
        self.assertEqual(self.status(token=id_token(), expect=401)["error"], "unauthorized")
        self.assertIn(("GET", "/user"), self.github.requests)

    def test_without_an_audience_or_an_account_no_service_is_trusted(self):
        keys = KeySet({"k1": APP_KEY})
        self.addCleanup(keys.close)
        for changes in (dict(audience=AUDIENCE), dict(caller_service_accounts=(NOTIFIER,))):
            with self.subTest(changes):
                self.restart(self.make_settings(caller_keys_url=keys.url, **changes))
                self.assertEqual(self.status(token=id_token(), expect=401)["error"], "unauthorized")
        self.assertEqual(keys.hits, 0)


class GoogleIdentityTest(unittest.TestCase):
    def setUp(self):
        self.keys = KeySet({"k1": APP_KEY})
        self.addCleanup(self.keys.close)
        self.identity = GoogleIdentity(AUDIENCE, [NOTIFIER], certs_url=self.keys.url)

    def test_a_trusted_accounts_id_token_names_it(self):
        self.assertEqual(self.identity.verify(id_token()), NOTIFIER)
        self.assertEqual(self.identity.verify(id_token(iss="accounts.google.com")), NOTIFIER)

    def test_every_other_token_is_invalid(self):
        for why, token in refused_tokens().items():
            with self.subTest(why):
                with self.assertRaises(InvalidCredentials):
                    self.identity.verify(token)

    def test_with_nothing_trusted_nothing_is_accepted(self):
        for identity in (GoogleIdentity(AUDIENCE, [], certs_url=self.keys.url),
                         GoogleIdentity(None, [NOTIFIER], certs_url=self.keys.url)):
            with self.assertRaises(InvalidCredentials):
                identity.verify(id_token())
        self.assertEqual(self.keys.hits, 0)

    def test_an_unreachable_key_set_is_unavailable(self):
        identity = GoogleIdentity(AUDIENCE, [NOTIFIER], certs_url="http://127.0.0.1:9/certs")
        with self.assertRaises(Unavailable):
            identity.verify(id_token())


class CallerSettingsTest(unittest.TestCase):
    def test_the_trust_is_read_from_the_environment(self):
        settings = Settings.from_env({
            "STATUS_PROJECTS": "a/b",
            "STATUS_AUDIENCE": AUDIENCE,
            "STATUS_CALLER_SERVICE_ACCOUNTS": NOTIFIER + ", other@x.iam.gserviceaccount.com",
            "STATUS_CALLER_KEYS_URL": "http://127.0.0.1:9/certs",
        })
        self.assertEqual(settings.audience, AUDIENCE)
        self.assertEqual(settings.caller_service_accounts, (NOTIFIER, "other@x.iam.gserviceaccount.com"))
        self.assertEqual(settings.caller_keys_url, "http://127.0.0.1:9/certs")
        self.assertTrue(settings.trusts_services)

    def test_by_default_no_service_is_trusted_and_the_keys_are_googles(self):
        settings = Settings.from_env({"STATUS_PROJECTS": "a/b"})
        self.assertIsNone(settings.audience)
        self.assertEqual(settings.caller_service_accounts, ())
        self.assertEqual(settings.caller_keys_url, GOOGLE_CERTS)
        self.assertFalse(settings.trusts_services)


class ManifestTrustTest(unittest.TestCase):
    """services/status/service.json names whom each deployment trusts (D66, D46)."""

    def setUp(self):
        from test_config import MANIFEST_PATH, manifest
        self.manifest, self.path = manifest, MANIFEST_PATH
        self.settings = manifest.load(MANIFEST_PATH)["settings"]

    def test_the_audience_is_the_status_services_own_cloud_run_url(self):
        self.assertEqual(self.settings["STATUS_AUDIENCE"], "https://status-{number}.{region}.run.app")

    def test_the_notifier_is_the_one_service_trusted(self):
        self.assertEqual(self.settings["STATUS_CALLER_SERVICE_ACCOUNTS"], "notify@{project}.iam.gserviceaccount.com")

    def test_the_keys_are_googles_in_every_deployment(self):
        self.assertNotIn("STATUS_CALLER_KEYS_URL", self.settings)

    def test_deployed_it_trusts_the_notifier_of_its_own_project_for_its_own_url(self):
        checked = self.manifest.checked(self.path, env="staging")
        facts = {"project": "loops-test", "number": "123", "region": "us-east1"}
        env = self.manifest.render(checked, "staging", facts, "a" * 40)["service"]["env"]
        settings = Settings.from_env(env)
        self.assertEqual(settings.audience, "https://status-123.us-east1.run.app")
        self.assertEqual(settings.caller_service_accounts, ("notify@loops-test.iam.gserviceaccount.com",))
        self.assertTrue(settings.trusts_services)


if __name__ == "__main__":
    unittest.main()
