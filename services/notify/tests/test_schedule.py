"""C3's rules on their own: what a person may save, when their quiet hours are, and when their digest is due, in their
own time zone."""

import unittest
from datetime import date, datetime, timezone

from notify.schedule import Invalid, PersonSettings, digest_due, in_quiet_hours


def utc(*parts):
    return datetime(*parts, tzinfo=timezone.utc)


def saved(**body):
    return PersonSettings.from_json({"timezone": "UTC", "digest_time": "09:00", "quiet_hours": None, **body})


class SettingsTest(unittest.TestCase):
    def test_what_a_person_saves_reads_back_the_same(self):
        body = {"timezone": "America/New_York", "digest_time": "08:30",
                "quiet_hours": {"start": "22:00", "end": "07:00"}}
        self.assertEqual(PersonSettings.from_json(body).to_json(), body)
        self.assertEqual(saved(digest_time=None).to_json()["digest_time"], None)

    def test_the_defaults_are_a_digest_at_nine_utc_and_no_quiet_hours(self):
        self.assertEqual(PersonSettings().to_json(), {"timezone": "UTC", "digest_time": "09:00", "quiet_hours": None})

    def test_what_cannot_be_saved_says_why(self):
        cases = [
            ([], "a JSON object"),
            ({"timezone": "UTC", "digest_time": "09:00"}, "missing fields: quiet_hours"),
            ({"timezone": "UTC", "digest_time": "09:00", "quiet_hours": None, "email": "x"}, "unknown fields: email"),
            ({"timezone": "Mars/Olympus", "digest_time": "09:00", "quiet_hours": None}, "IANA time zone"),
            ({"timezone": "../../etc/passwd", "digest_time": "09:00", "quiet_hours": None}, "IANA time zone"),
            ({"timezone": "UTC", "digest_time": "9:00", "quiet_hours": None}, "digest_time must be HH:MM"),
            ({"timezone": "UTC", "digest_time": "24:00", "quiet_hours": None}, "digest_time must be HH:MM"),
            ({"timezone": "UTC", "digest_time": None, "quiet_hours": {"start": "22:00"}}, "quiet_hours must be"),
            ({"timezone": "UTC", "digest_time": None, "quiet_hours": {"start": "22:00", "end": "7"}}, "HH:MM"),
            ({"timezone": "UTC", "digest_time": None, "quiet_hours": {"start": "22:00", "end": "22:00"}},
             "must differ"),
            ({"timezone": "UTC", "digest_time": "23:30", "quiet_hours": {"start": "22:00", "end": "07:00"}},
             "falls in the quiet hours"),
            ({"timezone": "UTC", "digest_time": "06:59", "quiet_hours": {"start": "22:00", "end": "07:00"}},
             "falls in the quiet hours"),
        ]
        for body, reason in cases:
            with self.subTest(reason=reason):
                with self.assertRaises(Invalid) as raised:
                    PersonSettings.from_json(body)
                self.assertIn(reason, str(raised.exception))

    def test_a_digest_at_the_end_of_the_quiet_hours_is_outside_them(self):
        self.assertEqual(saved(digest_time="07:00", quiet_hours={"start": "22:00", "end": "07:00"}).digest_time,
                         "07:00")


class QuietHoursTest(unittest.TestCase):
    def test_quiet_hours_run_past_midnight_in_the_persons_time_zone(self):
        night = saved(timezone="America/New_York", digest_time=None, quiet_hours={"start": "22:00", "end": "07:00"})
        # 2026-10-26 is EDT, UTC-4.
        self.assertFalse(in_quiet_hours(night, utc(2026, 10, 27, 1, 59)))   # 21:59 local
        self.assertTrue(in_quiet_hours(night, utc(2026, 10, 27, 2, 0)))     # 22:00
        self.assertTrue(in_quiet_hours(night, utc(2026, 10, 27, 6, 0)))     # 02:00
        self.assertTrue(in_quiet_hours(night, utc(2026, 10, 27, 10, 59)))   # 06:59
        self.assertFalse(in_quiet_hours(night, utc(2026, 10, 27, 11, 0)))   # 07:00

    def test_quiet_hours_within_a_day(self):
        lunch = saved(digest_time=None, quiet_hours={"start": "12:00", "end": "13:00"})
        self.assertFalse(in_quiet_hours(lunch, utc(2026, 10, 26, 11, 59)))
        self.assertTrue(in_quiet_hours(lunch, utc(2026, 10, 26, 12, 30)))
        self.assertFalse(in_quiet_hours(lunch, utc(2026, 10, 26, 13, 0)))

    def test_no_quiet_hours_is_never_quiet(self):
        self.assertFalse(in_quiet_hours(PersonSettings(), utc(2026, 10, 26, 3, 0)))

    def test_they_follow_the_clocks_when_they_change(self):
        # New York leaves summer time on 2026-11-01: 22:00 local is 02:00 UTC before it and 03:00 UTC after.
        night = saved(timezone="America/New_York", digest_time=None, quiet_hours={"start": "22:00", "end": "07:00"})
        self.assertTrue(in_quiet_hours(night, utc(2026, 10, 31, 2, 0)))
        self.assertFalse(in_quiet_hours(night, utc(2026, 11, 3, 2, 30)))
        self.assertTrue(in_quiet_hours(night, utc(2026, 11, 3, 3, 0)))


class DigestDueTest(unittest.TestCase):
    def test_it_is_due_from_the_time_set_for_fifteen_minutes(self):
        lisbon = saved(timezone="Europe/Lisbon", digest_time="08:00")  # UTC+0 in winter, from 2026-10-25
        self.assertIsNone(digest_due(lisbon, utc(2026, 10, 26, 7, 59)))
        self.assertEqual(digest_due(lisbon, utc(2026, 10, 26, 8, 0)), date(2026, 10, 26))
        self.assertEqual(digest_due(lisbon, utc(2026, 10, 26, 8, 14, 59)), date(2026, 10, 26))
        self.assertIsNone(digest_due(lisbon, utc(2026, 10, 26, 8, 15)))

    def test_it_is_due_at_the_local_time_not_utc(self):
        tokyo = saved(timezone="Asia/Tokyo", digest_time="08:00")  # UTC+9
        self.assertEqual(digest_due(tokyo, utc(2026, 10, 25, 23, 5)), date(2026, 10, 26))
        self.assertIsNone(digest_due(tokyo, utc(2026, 10, 26, 8, 5)))

    def test_a_digest_just_before_midnight_is_named_by_its_own_date(self):
        late = saved(digest_time="23:55")
        self.assertEqual(digest_due(late, utc(2026, 10, 27, 0, 5)), date(2026, 10, 26))

    def test_no_digest_is_never_due(self):
        self.assertIsNone(digest_due(saved(digest_time=None), utc(2026, 10, 26, 9, 0)))

    def test_a_time_the_clocks_skip_is_read_before_the_change(self):
        # New York's clocks skip 02:00 to 03:00 on 2027-03-14; a 02:30 digest comes at 03:30 local, 07:30 UTC.
        early = saved(timezone="America/New_York", digest_time="02:30")
        self.assertIsNone(digest_due(early, utc(2027, 3, 14, 7, 0)))
        self.assertEqual(digest_due(early, utc(2027, 3, 14, 7, 30)), date(2027, 3, 14))


if __name__ == "__main__":
    unittest.main()
