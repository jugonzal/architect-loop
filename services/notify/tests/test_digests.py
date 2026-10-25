"""C3: the digest arrives at the time the person set, and nothing is pushed during their quiet hours.

Here with one account on a test schedule, ticks played by tick() every 20 s across a day (finer than the scheduler's
minute, so a time is pinned to the read it went out on), and each message's time compared with the settings, as the
staging proof will compare delivery times.
"""

import unittest
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from support import PROJECT, Harness, base, item, push_token

NEW_YORK = ZoneInfo("America/New_York")
QUIET = {"start": "22:00", "end": "07:00"}


class SettingsApiTest(Harness, unittest.TestCase):
    def setUp(self):
        self.make()

    def test_a_person_sees_the_defaults_until_they_save_their_own(self):
        response = self.api.get(f"{base()}/settings/me", token="alice-token")
        self.assertEqual(response.get_json(), {"timezone": "UTC", "digest_time": "09:00", "quiet_hours": None,
                                               "saved": False})
        saved = self.save_settings("alice", timezone="America/New_York", digest_time="08:30", quiet_hours=QUIET)
        self.assertEqual(saved, {"timezone": "America/New_York", "digest_time": "08:30", "quiet_hours": QUIET,
                                 "saved": True})
        self.assertEqual(self.api.get(f"{base()}/settings/me", token="alice-token").get_json(), saved)
        self.assertEqual(self.api.get(f"{base()}/settings/me", token="bob-token").get_json()["saved"], False)

    def test_settings_that_cannot_work_are_refused_with_the_reason(self):
        response = self.api.put(f"{base()}/settings/me", token="alice-token", valid_request=False,
                                json_body={"timezone": "UTC", "digest_time": "23:00", "quiet_hours": QUIET})
        self.assertEqual(response.status_code, 400)
        self.assertIn("falls in the quiet hours", response.get_json()["message"])
        self.assertFalse(self.api.get(f"{base()}/settings/me", token="alice-token").get_json()["saved"])


class ScheduleTest(Harness, unittest.TestCase):
    """alice in New York: digest at 08:30, quiet from 22:00 to 07:00. bob keeps the defaults."""

    def setUp(self):
        self.make()
        self.register("alice", "alice-phone")
        self.register("bob", "bob-phone")
        self.save_settings("alice", timezone="America/New_York", digest_time="08:30", quiet_hours=QUIET)
        # Start at 20:00 in New York on Monday 2026-10-26, with the baseline read already done.
        self.clock.now = datetime(2026, 10, 26, 20, 0, tzinfo=NEW_YORK).astimezone(timezone.utc)
        self.first_read()

    def run_until(self, local, every=timedelta(seconds=20)):
        """Read every 20 s until `local` (a New York time), and give each message with the time it went out."""
        sent = []
        until = local.astimezone(timezone.utc)
        while self.clock.now < until:
            self.clock.advance(seconds=every.total_seconds())
            before = len(self.expo.sent)
            self.tick()
            sent += [(self.clock.now.astimezone(NEW_YORK), m) for m in self.expo.sent[before:]]
        return sent

    def to(self, sent, token):
        return [(at, m) for at, m in sent if m["to"] == token]

    def test_the_digest_arrives_at_the_time_set_once_a_day_and_counts_what_waits(self):
        self.queue(item("a", waits_on="alice"), item("b", waits_on="alice"), item("c", waits_on="bob"))
        sent = self.run_until(datetime(2026, 10, 28, 12, 0, tzinfo=NEW_YORK))
        digests = self.to(sent, push_token("alice-phone"))
        self.assertEqual([at.strftime("%Y-%m-%d %H:%M") for at, _ in digests],
                         ["2026-10-27 08:30", "2026-10-28 08:30"])
        for at, message in digests:
            self.assertLess(at.second, 21, "within one read of the time set")
            self.assertEqual(message["title"], "Needs you")
            self.assertEqual(message["body"], "2 items wait on you.")
            self.assertEqual(message["data"]["url"], "/inbox")
        # bob's default, 09:00 UTC, is 05:00 in New York while summer time lasts.
        bobs = self.to(sent, push_token("bob-phone"))
        self.assertEqual([at.astimezone(timezone.utc).strftime("%H:%M") for at, _ in bobs], ["09:00", "09:00"])
        self.assertEqual(bobs[0][1]["body"], "1 item waits on you.")

    def test_no_digest_on_a_day_nothing_waits(self):
        sent = self.run_until(datetime(2026, 10, 27, 12, 0, tzinfo=NEW_YORK))
        self.assertEqual(sent, [])

    def test_a_blocking_item_in_the_quiet_hours_waits_for_them_to_end(self):
        self.clock.now = datetime(2026, 10, 26, 23, 0, tzinfo=NEW_YORK).astimezone(timezone.utc)
        self.queue(item("urgent", waits_on="alice", unblocks=["command-center/app-inbox"]))
        sent = self.run_until(datetime(2026, 10, 27, 9, 0, tzinfo=NEW_YORK))
        pushes = [(at, m) for at, m in self.to(sent, push_token("alice-phone")) if m["data"].get("item")]
        self.assertEqual([at.strftime("%H:%M") for at, _ in pushes], ["07:00"])
        for at, _ in self.to(sent, push_token("alice-phone")):
            self.assertFalse(at.hour >= 22 or at.hour < 7, f"pushed at {at:%H:%M}, in the quiet hours")

    def test_a_blocking_item_gone_before_the_quiet_hours_end_is_never_pushed(self):
        self.clock.now = datetime(2026, 10, 26, 23, 0, tzinfo=NEW_YORK).astimezone(timezone.utc)
        self.queue(item("urgent", waits_on="alice", unblocks=["command-center/app-inbox"]))
        self.run_until(datetime(2026, 10, 27, 3, 0, tzinfo=NEW_YORK))
        self.queue()
        sent = self.run_until(datetime(2026, 10, 27, 8, 0, tzinfo=NEW_YORK))
        self.assertEqual(self.to(sent, push_token("alice-phone")), [])

    def test_no_digest_means_none(self):
        self.save_settings("alice", timezone="America/New_York", digest_time=None, quiet_hours=QUIET)
        self.queue(item("a", waits_on="alice"))
        sent = self.run_until(datetime(2026, 10, 27, 12, 0, tzinfo=NEW_YORK))
        self.assertEqual(self.to(sent, push_token("alice-phone")), [])

    def test_a_digest_expo_did_not_take_is_sent_on_the_next_read(self):
        self.queue(item("a", waits_on="alice"))
        self.run_until(datetime(2026, 10, 27, 8, 29, 30, tzinfo=NEW_YORK))  # the last read is at 08:29:40
        self.expo.down = True
        self.run_until(datetime(2026, 10, 27, 8, 31, tzinfo=NEW_YORK))
        self.expo.down = False
        sent = self.run_until(datetime(2026, 10, 27, 9, 0, tzinfo=NEW_YORK))
        self.assertEqual([at.strftime("%H:%M") for at, _ in self.to(sent, push_token("alice-phone"))], ["08:31"])

    def test_a_digest_is_never_sent_late(self):
        self.queue(item("a", waits_on="alice"))
        self.run_until(datetime(2026, 10, 27, 8, 0, tzinfo=NEW_YORK))
        # The notifier is down from 08:00 to 09:00, past the time and its fifteen minutes.
        self.clock.now = datetime(2026, 10, 27, 9, 0, tzinfo=NEW_YORK).astimezone(timezone.utc)
        sent = self.run_until(datetime(2026, 10, 27, 12, 0, tzinfo=NEW_YORK))
        self.assertEqual(self.to(sent, push_token("alice-phone")), [])
        self.assertTrue(self.store.has_baseline(PROJECT))


if __name__ == "__main__":
    unittest.main()
