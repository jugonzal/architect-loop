"""A person's settings, and what they mean at a moment: whether it is their quiet hours, and whether their digest is
due (C3). Everything here is a pure function of the settings and the time, in the person's own time zone.

A person who has saved nothing has the defaults: a digest at 09:00 UTC and no quiet hours. The app saves the
device's time zone when it registers one, so the default is only ever what a person sees before that.
"""

import functools
import re
from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo, available_timezones

HHMM = re.compile(r"^([01][0-9]|2[0-3]):([0-5][0-9])$")
DEFAULT_TIMEZONE = "UTC"
DEFAULT_DIGEST_TIME = "09:00"
# A digest is sent once the time the person set has come, and only within this long after it: a notifier that was
# down at that time sends nothing late rather than a digest at a time nobody chose.
DIGEST_GRACE = timedelta(minutes=15)


class Invalid(ValueError):
    """Settings a person cannot save, with what is wrong, for people."""


@functools.lru_cache(maxsize=1)
def _zones():
    return frozenset(available_timezones())


def _minutes(hhmm):
    hours, minutes = hhmm.split(":")
    return int(hours) * 60 + int(minutes)


def _within(start, end, minute):
    """Whether a minute of the day falls in [start, end), a span that may run past midnight."""
    if start < end:
        return start <= minute < end
    return minute >= start or minute < end


@dataclass(frozen=True)
class PersonSettings:
    timezone: str = DEFAULT_TIMEZONE
    # "HH:MM" in the person's time zone, or None for no digest.
    digest_time: str | None = DEFAULT_DIGEST_TIME
    # ("HH:MM", "HH:MM"): from the first, up to but not including the second; it may run past midnight. None for none.
    quiet_hours: tuple | None = None

    def zone(self):
        return ZoneInfo(self.timezone)

    def local(self, now):
        return now.astimezone(self.zone())

    def to_json(self):
        quiet = {"start": self.quiet_hours[0], "end": self.quiet_hours[1]} if self.quiet_hours else None
        return {"timezone": self.timezone, "digest_time": self.digest_time, "quiet_hours": quiet}

    @classmethod
    def from_json(cls, body):
        """The settings a request body describes, or Invalid saying what is wrong. Every field is required, so a save
        always says exactly what the person chose."""
        if not isinstance(body, dict):
            raise Invalid("the settings are a JSON object")
        unknown = sorted(set(body) - {"timezone", "digest_time", "quiet_hours"})
        if unknown:
            raise Invalid(f"unknown fields: {', '.join(unknown)}")
        missing = [name for name in ("timezone", "digest_time", "quiet_hours") if name not in body]
        if missing:
            raise Invalid(f"missing fields: {', '.join(missing)} (send null for no digest or no quiet hours)")
        zone = body["timezone"]
        if not isinstance(zone, str) or zone not in _zones():
            raise Invalid("timezone must be an IANA time zone, such as America/New_York or UTC")
        digest = body["digest_time"]
        if digest is not None and not (isinstance(digest, str) and HHMM.match(digest)):
            raise Invalid("digest_time must be HH:MM, 00:00 to 23:59, or null for no digest")
        quiet = body["quiet_hours"]
        hours = None
        if quiet is not None:
            if not isinstance(quiet, dict) or set(quiet) != {"start", "end"}:
                raise Invalid("quiet_hours must be {\"start\": \"HH:MM\", \"end\": \"HH:MM\"}, or null for none")
            start, end = quiet["start"], quiet["end"]
            if not all(isinstance(t, str) and HHMM.match(t) for t in (start, end)):
                raise Invalid("quiet_hours' start and end must each be HH:MM, 00:00 to 23:59")
            if start == end:
                raise Invalid("quiet_hours' start and end must differ; send null for no quiet hours")
            hours = (start, end)
            if digest is not None and _within(_minutes(start), _minutes(end), _minutes(digest)):
                raise Invalid(f"the digest at {digest} falls in the quiet hours from {start} to {end}, when nothing "
                              "is pushed; choose a digest time outside them")
        return cls(timezone=zone, digest_time=digest, quiet_hours=hours)


def in_quiet_hours(settings, now):
    """Whether `now` (an aware datetime) falls in the person's quiet hours, in their time zone."""
    if not settings.quiet_hours:
        return False
    local = settings.local(now)
    start, end = (_minutes(t) for t in settings.quiet_hours)
    return _within(start, end, local.hour * 60 + local.minute)


def digest_due(settings, now):
    """The local date whose digest is due at `now`, or None: the digest's time on that date has come, less than
    DIGEST_GRACE ago. The date names the digest, so each one is sent at most once."""
    if not settings.digest_time:
        return None
    zone = settings.zone()
    hours, minutes = (int(part) for part in settings.digest_time.split(":"))
    today = now.astimezone(zone).date()
    for day in (today, today - timedelta(days=1)):
        # A time that a change of clocks skips on that date is read with the offset before the change.
        at = datetime.combine(day, time(hours, minutes), tzinfo=zone).astimezone(timezone.utc)
        if at <= now < at + DIGEST_GRACE:
            return day
    return None
