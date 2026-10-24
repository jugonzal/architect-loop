"""C1: a device registers for push from the app, and a test notification sent to that person arrives on their devices
and no one else's.

Here with two accounts and three devices, against a fake Expo that records what it was given for each push token.
The staging proof, on two real devices with two real accounts, waits for a build that has the app's screen.
"""

import unittest

from support import OTHER_PROJECT, PROJECT, Harness, base, push_token


class RegistrationTest(Harness, unittest.TestCase):
    def setUp(self):
        self.make()

    def devices(self, login, project=PROJECT):
        response = self.api.get(f"{base(project)}/devices", token=f"{login}-token")
        self.assertEqual(response.status_code, 200, response.get_json())
        return response.get_json()["devices"]

    def test_a_registered_device_is_listed_for_its_person_only(self):
        phone = self.register("alice", "phone")
        self.assertEqual(phone["platform"], "ios")
        self.assertEqual(phone["name"], "alice's phone")
        self.assertRegex(phone["id"], r"^[0-9a-f]{32}$")
        self.assertEqual([d["id"] for d in self.devices("alice")], [phone["id"]])
        self.assertEqual(self.devices("bob"), [])
        self.assertEqual(self.devices("alice", OTHER_PROJECT), [], "each project keeps its own devices (D18)")

    def test_registering_a_token_again_is_the_same_device(self):
        first = self.register("alice", "phone")
        self.clock.advance(hours=1)
        again = self.register("alice", "phone", name="renamed")
        self.assertEqual(again["id"], first["id"])
        self.assertEqual(again["registered_at"], first["registered_at"])
        self.assertEqual([d["name"] for d in self.devices("alice")], ["renamed"])

    def test_a_token_registered_by_another_person_moves_to_them(self):
        # A phone that changes hands, or an account switch on one phone: it is only ever one person's device.
        self.register("alice", "shared")
        self.register("bob", "shared")
        self.assertEqual(self.devices("alice"), [])
        self.assertEqual(len(self.devices("bob")), 1)
        self.notifier.test(PROJECT, "alice")
        self.assertEqual(self.expo.sent, [])

    def test_a_person_unregisters_their_own_device_and_no_one_elses(self):
        alices = self.register("alice", "phone")
        response = self.api.delete(f"{base()}/devices/{alices['id']}", token="bob-token")
        self.assertEqual(response.status_code, 404, "another person's device answers as missing")
        self.assertEqual(len(self.devices("alice")), 1)
        response = self.api.delete(f"{base()}/devices/{alices['id']}", token="alice-token")
        self.assertEqual(response.status_code, 204)
        self.assertEqual(self.devices("alice"), [])

    def test_a_device_needs_an_expo_push_token_and_a_platform(self):
        cases = [
            ({"token": "not-a-token", "platform": "ios"}, "Expo push token"),
            ({"token": push_token("x"), "platform": "windows"}, "platform"),
            ({"token": push_token("x"), "platform": "ios", "name": ""}, "name"),
            ({"token": push_token("x"), "platform": "ios", "colour": "red"}, "unknown fields"),
            ({"token": push_token("x"), "platform": "ios", "timezone": "Nowhere/Else"}, "IANA time zone"),
        ]
        for body, reason in cases:
            with self.subTest(reason=reason):
                response = self.api.post(f"{base()}/devices", token="alice-token", json_body=body,
                                         valid_request=False)
                self.assertEqual(response.status_code, 400)
                self.assertIn(reason, response.get_json()["message"])
        self.assertEqual(self.devices("alice"), [])

    def test_a_caller_is_who_github_says_their_token_is(self):
        response = self.api.get(f"{base()}/devices", valid_request=False)
        self.assertEqual(response.status_code, 401)
        response = self.api.get(f"{base()}/devices", token="forged-token")
        self.assertEqual(response.status_code, 401)
        self.github.down = True
        response = self.api.get(f"{base()}/devices", token="alice-token")
        self.assertEqual(response.status_code, 503)

    def test_a_project_not_served_here_is_not_found(self):
        response = self.api.get(f"{base('example/unknown')}/devices", token="alice-token")
        self.assertEqual(response.status_code, 404)

    def test_the_first_registration_starts_the_settings_in_the_devices_time_zone(self):
        self.register("alice", "phone", timezone="America/New_York")
        settings = self.api.get(f"{base()}/settings/me", token="alice-token").get_json()
        self.assertEqual(settings, {"timezone": "America/New_York", "digest_time": "09:00", "quiet_hours": None,
                                    "saved": True})
        # Once saved, a later registration elsewhere never changes them.
        self.register("alice", "tablet", timezone="Asia/Tokyo")
        settings = self.api.get(f"{base()}/settings/me", token="alice-token").get_json()
        self.assertEqual(settings["timezone"], "America/New_York")


class TestNotificationTest(Harness, unittest.TestCase):
    """The test notification C1 proves with: it reaches every device of the person who sends it, and no other."""

    def setUp(self):
        self.make()
        self.register("alice", "phone")
        self.register("alice", "tablet", platform="android")
        self.register("bob", "phone-b")

    def send(self, login):
        return self.api.post(f"{base()}/test-notification", token=f"{login}-token")

    def test_it_arrives_on_the_persons_devices_and_no_one_elses(self):
        response = self.send("alice")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"devices": 2, "accepted": 2, "gone": 0})
        self.assertEqual(sorted(m["to"] for m in self.expo.sent), [push_token("phone"), push_token("tablet")])
        self.assertEqual(self.expo.to(push_token("phone-b")), [])
        message = self.expo.sent[0]
        self.assertEqual(message["title"], "Test notification")
        self.assertEqual(message["data"], {"url": "/notifications", "project": PROJECT, "test": True})

        self.expo.sent.clear()
        self.assertEqual(self.send("bob").get_json(), {"devices": 1, "accepted": 1, "gone": 0})
        self.assertEqual([m["to"] for m in self.expo.sent], [push_token("phone-b")])

    def test_a_person_without_a_device_is_sent_nothing(self):
        self.assertEqual(self.send("carol").get_json(), {"devices": 0, "accepted": 0, "gone": 0})
        self.assertEqual(self.expo.sent, [])

    def test_one_a_minute(self):
        self.assertEqual(self.send("alice").status_code, 200)
        response = self.send("alice")
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.get_json()["error"], "too_many_requests")
        self.assertEqual(self.send("bob").status_code, 200, "each person has their own minute")
        self.clock.advance(minutes=1)
        self.assertEqual(self.send("alice").status_code, 200)

    def test_a_device_expo_says_is_gone_is_forgotten(self):
        self.expo.gone.add(push_token("tablet"))
        self.assertEqual(self.send("alice").get_json(), {"devices": 2, "accepted": 1, "gone": 1})
        devices = self.api.get(f"{base()}/devices", token="alice-token").get_json()["devices"]
        self.assertEqual([d["name"] for d in devices], ["alice's phone"])

    def test_expo_down_answers_unavailable(self):
        self.expo.down = True
        response = self.send("alice")
        self.assertEqual(response.status_code, 503)
        self.assertIn("Expo", response.get_json()["message"])


if __name__ == "__main__":
    unittest.main()
