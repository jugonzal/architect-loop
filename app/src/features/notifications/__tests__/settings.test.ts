// command-center/notifications C3, the form's rules: the app refuses what the notifier would refuse
// (services/notify/notify/schedule.py), and sends exactly what the person chose.

import { draftOf, inputOf, within, type SettingsDraft } from '../settings';

const DRAFT: SettingsDraft = {
  timezone: 'America/New_York',
  digestOn: true,
  digestTime: '08:30',
  quietOn: true,
  quietStart: '22:00',
  quietEnd: '07:00',
};

describe('the settings form', () => {
  it('sends the three settings as the notifier reads them', () => {
    expect(inputOf(DRAFT)).toEqual({
      input: { timezone: 'America/New_York', digest_time: '08:30', quiet_hours: { start: '22:00', end: '07:00' } },
    });
    expect(inputOf({ ...DRAFT, digestOn: false, quietOn: false })).toEqual({
      input: { timezone: 'America/New_York', digest_time: null, quiet_hours: null },
    });
  });

  it('starts from saved settings, with times behind a switch that is off', () => {
    expect(draftOf({ timezone: 'UTC', digest_time: null, quiet_hours: null, saved: true })).toEqual({
      timezone: 'UTC',
      digestOn: false,
      digestTime: '09:00',
      quietOn: false,
      quietStart: '22:00',
      quietEnd: '07:00',
    });
  });

  it.each([
    [{ timezone: ' ' }, 'Name a time zone'],
    [{ digestTime: '9:00' }, 'The digest time is HH:MM'],
    [{ digestTime: '24:00' }, 'The digest time is HH:MM'],
    [{ quietEnd: '7' }, 'Quiet hours start and end at HH:MM'],
    [{ quietEnd: '22:00' }, 'different times'],
    [{ digestTime: '23:30' }, 'falls in your quiet hours'],
    [{ digestTime: '06:59' }, 'falls in your quiet hours'],
  ] as const)('refuses %j: %s', (change, reason) => {
    const result = inputOf({ ...DRAFT, ...change });
    expect('problem' in result && result.problem).toContain(reason);
  });

  it('ignores a time behind a switch that is off', () => {
    expect(inputOf({ ...DRAFT, digestOn: false, digestTime: 'nonsense' })).toHaveProperty('input');
    expect(inputOf({ ...DRAFT, quietOn: false, quietEnd: '' })).toHaveProperty('input');
  });

  it('reads quiet hours that run past midnight as the notifier does', () => {
    expect(within('22:00', '07:00', '21:59')).toBe(false);
    expect(within('22:00', '07:00', '22:00')).toBe(true);
    expect(within('22:00', '07:00', '06:59')).toBe(true);
    expect(within('22:00', '07:00', '07:00')).toBe(false);
    expect(within('12:00', '13:00', '12:30')).toBe(true);
    expect(within('12:00', '13:00', '13:00')).toBe(false);
  });
});
