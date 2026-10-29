"""app-served: anyone can read which commit each app platform's builds were made from, without an Expo login.

C1: `GET /apps/{channel}/{platform}/version` answers `{"commit": "<sha>"}` with the commit that the platform's latest
finished build of the channel's profile was made from (command-center/D79). It answers 404 when the platform has no
finished build, or its latest one records no commit, and 503 when EAS cannot be read, saying why each time, and never
an older commit. It reads EAS the way eas-cli 22.4.0 does (app-served D2), with the robot token in
STATUS_EXPO_TOKEN, and needs no credentials from the caller, like /version.
"""

import unittest

from support import EAS_PROJECT_ID, EXPO_TOKEN, ServiceTestCase, status_path

A = "a" * 40
B = "b" * 40
C = "c" * 40


class AppVersionTest(ServiceTestCase):
    def served(self, channel="staging", platform="android", expect=200):
        response = self.api.get("/apps/%s/%s/version" % (channel, platform))
        self.assertEqual(response.status_code, expect, response.get_json())
        return response.get_json()

    def test_a_platform_serves_its_latest_finished_builds_commit(self):
        self.expo.build("ANDROID", A, "2026-10-27T10:00:00.000Z")
        self.expo.build("ANDROID", B, "2026-10-28T10:00:00.000Z")
        self.expo.build("ANDROID", C, "2026-10-28T11:00:00.000Z", status="ERRORED")
        self.expo.build("ANDROID", C, "2026-10-28T12:00:00.000Z", profile="production")
        self.expo.build("IOS", C, "2026-10-28T13:00:00.000Z")
        self.assertEqual(self.served(), {"commit": B})
        self.assertEqual(self.served(platform="ios"), {"commit": C})

    def test_one_platform_reads_without_the_other(self):
        """D79: an Android build alone makes its row readable; iOS without a build answers 404 on its own."""
        self.expo.build("ANDROID", A, "2026-10-28T10:00:00.000Z")
        self.assertEqual(self.served(), {"commit": A})
        body = self.served(platform="ios", expect=404)
        self.assertEqual(body["error"], "not_found")
        self.assertIn("no finished ios build for profile staging", body["message"])

    def test_a_latest_build_without_a_commit_is_not_served_and_no_older_one_stands_in(self):
        self.expo.build("ANDROID", A, "2026-10-27T10:00:00.000Z")
        self.expo.build("ANDROID", None, "2026-10-28T10:00:00.000Z")
        body = self.served(expect=404)
        self.assertIn("records no commit", body["message"])

    def test_it_asks_eas_as_eas_cli_does_with_the_robot_token(self):
        self.expo.build("ANDROID", A, "2026-10-28T10:00:00.000Z")
        self.served()
        request = self.expo.requests[-1]
        self.assertEqual((request["method"], request["path"]), ("POST", "/graphql"))
        self.assertEqual(request["authorization"], "Bearer %s" % EXPO_TOKEN)
        variables = request["body"]["variables"]
        self.assertEqual(variables["appId"], EAS_PROJECT_ID)
        self.assertEqual(variables["filter"], {"platform": "ANDROID", "status": "FINISHED", "buildProfile": "staging"})
        self.assertIn("builds(offset: $offset, limit: $limit, filter: $filter)", request["body"]["query"])

    def test_it_needs_no_credentials(self):
        self.expo.build("ANDROID", A, "2026-10-28T10:00:00.000Z")
        response = self.app.test_client().get("/apps/staging/android/version")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"commit": A})

    def test_eas_unreadable_is_503_and_never_an_older_commit(self):
        self.expo.build("ANDROID", A, "2026-10-28T10:00:00.000Z")
        self.assertEqual(self.served(), {"commit": A})
        self.clock.now += 61
        for status, raw in ((500, b"{}"), (200, b'{"errors": [{"message": "boom"}]}'), (200, b"not json"),
                            (401, b'{"errors": [{"message": "unauthorized"}]}')):
            with self.subTest(status=status, raw=raw):
                self.expo.failure = (status, raw)
                self.clock.now += 61
                body = self.served(expect=503)
                self.assertEqual(body["error"], "unavailable")
                self.assertIn("EAS", body["message"])
        self.expo.failure = None
        self.expo.close()
        self.clock.now += 61
        self.assertIn("EAS", self.served(expect=503)["message"])

    def test_eas_answers_are_reused_for_at_most_a_minute(self):
        self.expo.build("ANDROID", A, "2026-10-28T10:00:00.000Z")
        self.assertEqual(self.served(), {"commit": A})
        self.expo.build("ANDROID", B, "2026-10-28T11:00:00.000Z")
        self.clock.now += 59
        self.assertEqual(self.served(), {"commit": A})
        self.assertEqual(len(self.expo.requests), 1)
        self.clock.now += 2
        self.assertEqual(self.served(), {"commit": B})
        self.assertEqual(len(self.expo.requests), 2)

    def test_an_unknown_platform_or_channel_is_not_found(self):
        self.assertEqual(self.served(platform="windows", expect=404)["error"], "not_found")
        self.assertEqual(self.served(channel="Bad.Channel", expect=404)["error"], "not_found")
        self.assertEqual(self.expo.requests, [])

    def test_without_the_robot_token_only_this_route_is_unavailable(self):
        self.restart(self.make_settings(expo_token=None))
        body = self.served(expect=503)
        self.assertIn("STATUS_EXPO_TOKEN", body["message"])
        self.assertEqual(self.expo.requests, [])
        self.assertEqual(self.api.get(status_path(), token="alice-token").status_code, 200)


if __name__ == "__main__":
    unittest.main()
