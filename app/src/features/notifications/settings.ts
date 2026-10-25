// What a person may save as their digest time, time zone and quiet hours (command-center/notifications C3), checked
// in the app with the notifier's own rules (services/notify/notify/schedule.py), so a form never sends what the
// service would refuse. The service checks again: this only says why earlier.

import type { Settings, SettingsInput } from '../../api/notify.gen';

const HHMM = /^([01][0-9]|2[0-3]):([0-5][0-9])$/;

/** The form as the person edits it: every field a string, and a switch for the digest and the quiet hours. */
export type SettingsDraft = {
  timezone: string;
  digestOn: boolean;
  digestTime: string;
  quietOn: boolean;
  quietStart: string;
  quietEnd: string;
};

/** The form's starting values for a person's settings, with sensible times behind a switch that is off. */
export function draftOf(settings: Settings): SettingsDraft {
  return {
    timezone: settings.timezone,
    digestOn: settings.digest_time !== null,
    digestTime: settings.digest_time ?? '09:00',
    quietOn: settings.quiet_hours !== null,
    quietStart: settings.quiet_hours?.start ?? '22:00',
    quietEnd: settings.quiet_hours?.end ?? '07:00',
  };
}

function minutes(hhmm: string): number {
  const [hours, mins] = hhmm.split(':').map(Number);
  return hours! * 60 + mins!;
}

/** Whether a time falls in [start, end), a span that may run past midnight. */
export function within(start: string, end: string, time: string): boolean {
  const [s, e, t] = [minutes(start), minutes(end), minutes(time)];
  return s < e ? s <= t && t < e : t >= s || t < e;
}

/** What the draft would save, or why it cannot be saved. */
export function inputOf(draft: SettingsDraft): { input: SettingsInput } | { problem: string } {
  const timezone = draft.timezone.trim();
  if (!timezone) return { problem: 'Name a time zone, such as America/New_York or UTC.' };
  const digest = draft.digestTime.trim();
  if (draft.digestOn && !HHMM.test(digest)) return { problem: 'The digest time is HH:MM, from 00:00 to 23:59.' };
  const [start, end] = [draft.quietStart.trim(), draft.quietEnd.trim()];
  if (draft.quietOn) {
    if (!HHMM.test(start) || !HHMM.test(end)) {
      return { problem: 'Quiet hours start and end at HH:MM, from 00:00 to 23:59.' };
    }
    if (start === end) return { problem: 'Quiet hours start and end at different times.' };
    if (draft.digestOn && within(start, end, digest)) {
      return { problem: `The digest at ${digest} falls in your quiet hours, when nothing is pushed.` };
    }
  }
  return {
    input: {
      timezone,
      digest_time: draft.digestOn ? digest : null,
      quiet_hours: draft.quietOn ? { start, end } : null,
    },
  };
}

/** This device's IANA time zone, or UTC when the device does not say. */
export function deviceTimeZone(): string {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';
  } catch {
    return 'UTC';
  }
}
