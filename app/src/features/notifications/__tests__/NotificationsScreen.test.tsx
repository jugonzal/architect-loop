// command-center/notifications C1 and C3, the screen: a device registers its Expo push token for the signed-in person
// and sends itself a test notification, and the person saves a digest time, time zone and quiet hours. Against a
// fake notifier behind the generated client and the signed-in fetch, with a fake device for the push token.

import { act, fireEvent, render as renderBare, screen } from '@testing-library/react-native';
import type { ReactElement } from 'react';
import { SafeAreaProvider } from 'react-native-safe-area-context';

import { createSignedInFetch } from '../../../api/fetch';
import { createNotifyClient } from '../../../api/notify.gen';
import { NotificationsScreen, NO_NOTIFY_SERVICE_MESSAGE } from '../NotificationsScreen';
import { NO_PUSH_MODULE_MESSAGE, type PushTokenSource } from '../pushTokens';
import { fakeDevice, fakeNotify, NOTIFY_URL } from './fakeNotify';

const PROJECT = 'jugonzal/architect-loop';
const DEVICES = '/projects/jugonzal/architect-loop/devices';
const METRICS = { frame: { x: 0, y: 0, width: 390, height: 844 }, insets: { top: 47, left: 0, right: 0, bottom: 34 } };

/** The screen lives outside the tabs, so it reads the safe area itself, as the root layout provides it. */
function render(element: ReactElement) {
  return renderBare(<SafeAreaProvider initialMetrics={METRICS}>{element}</SafeAreaProvider>);
}

function clientFor(service: ReturnType<typeof fakeNotify>, token: string) {
  const fetch = createSignedInFetch({ getToken: () => token, onUnauthorized: jest.fn(), fetch: service.fetch });
  return createNotifyClient({ baseUrl: NOTIFY_URL, fetch });
}

async function settle() {
  for (let i = 0; i < 5; i++) await act(async () => {});
}

async function shown(
  service: ReturnType<typeof fakeNotify>,
  {
    token = 'gho_alice',
    pushTokens = null as PushTokenSource | null,
    timeZone = (): string => 'America/New_York',
  } = {},
) {
  const view = render(
    <NotificationsScreen
      notify={clientFor(service, token)}
      project={PROJECT}
      pushTokens={pushTokens}
      deviceName="Test phone"
      timeZone={timeZone}
    />,
  );
  await settle();
  return view;
}

async function press(name: string) {
  fireEvent.press(screen.getByRole('button', { name }));
  await settle();
}

describe('registering this device (C1)', () => {
  it("registers the device's Expo push token for the signed-in person, and lists it", async () => {
    const service = fakeNotify();
    const device = fakeDevice('ExponentPushToken[alice-phone]');
    await shown(service, { pushTokens: device.source });
    expect(screen.getByText('No device gets your notifications yet.')).toBeTruthy();

    await press('Turn on notifications on this device');
    expect(device.asked).toEqual(['permission', 'token']);
    const post = service.calls.find((c) => c.method === 'POST' && c.path === DEVICES);
    expect(post).toEqual({
      method: 'POST',
      path: DEVICES,
      token: 'gho_alice',
      body: { token: 'ExponentPushToken[alice-phone]', platform: 'ios', name: 'Test phone', timezone: 'America/New_York' },
    });
    expect(screen.getByText('This device gets your notifications.')).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Turn on notifications on this device' })).toBeNull();
    expect(screen.getByText('Test phone')).toBeTruthy();
    // The first registration started the person's settings in the device's time zone.
    expect(screen.getByDisplayValue('America/New_York')).toBeTruthy();
  });

  it('registers nothing when the person does not allow notifications', async () => {
    const service = fakeNotify();
    const device = fakeDevice('ExponentPushToken[x]', { permission: 'denied' });
    await shown(service, { pushTokens: device.source });
    await press('Turn on notifications on this device');
    expect(device.asked).toEqual(['permission']);
    expect(service.calls.filter((c) => c.method === 'POST')).toEqual([]);
    expect(screen.getByText(/Notifications are off for this app/)).toBeTruthy();
  });

  it('shows what the notifier said when it refuses the token', async () => {
    const service = fakeNotify();
    await shown(service, { pushTokens: fakeDevice('not-a-token').source });
    await press('Turn on notifications on this device');
    expect(screen.getByText('token must be an Expo push token, ExponentPushToken[...]')).toBeTruthy();
  });

  it('says why a build without a notification module cannot register this device', async () => {
    await shown(fakeNotify(), { pushTokens: null });
    expect(screen.getByText(NO_PUSH_MODULE_MESSAGE)).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Turn on notifications on this device' })).toBeNull();
  });

  it("removes one of the person's devices", async () => {
    const service = fakeNotify();
    await shown(service, { pushTokens: fakeDevice('ExponentPushToken[alice-phone]').source });
    await press('Turn on notifications on this device');
    await press('Stop notifications on Test phone');
    expect(service.calls.some((c) => c.method === 'DELETE' && c.path.startsWith(`${DEVICES}/`))).toBe(true);
    expect(screen.getByText('No device gets your notifications yet.')).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Turn on notifications on this device' })).toBeTruthy();
  });
});

describe('the test notification (C1)', () => {
  it("reaches the person's devices and no one else's", async () => {
    const service = fakeNotify();
    const alice = await shown(service, { pushTokens: fakeDevice('ExponentPushToken[alice-phone]').source });
    await press('Turn on notifications on this device');
    alice.unmount();
    const bob = await shown(service, { token: 'gho_bob', pushTokens: fakeDevice('ExponentPushToken[bob-phone]').source });
    await press('Turn on notifications on this device');
    bob.unmount();

    await shown(service, { token: 'gho_alice' });
    await press('Send a test notification');
    expect(service.tests).toEqual([['ExponentPushToken[alice-phone]']]);
    expect(screen.getByText('Sent to your device.')).toBeTruthy();
    // Each list shows only its person's device.
    expect(screen.getAllByText('Test phone')).toHaveLength(1);
  });

  it('says so when a test went out less than a minute ago', async () => {
    const service = fakeNotify();
    await shown(service);
    service.answerNext(429, { error: 'too_many_requests', message: 'one test notification a minute' });
    await press('Send a test notification');
    expect(screen.getByText('A test notification went out less than a minute ago. Try again shortly.')).toBeTruthy();
  });

  it('says nothing was sent to a person with no device', async () => {
    await shown(fakeNotify());
    await press('Send a test notification');
    expect(screen.getByText('You have no device registered, so nothing was sent.')).toBeTruthy();
  });
});

describe('the digest and quiet hours (C3)', () => {
  it("starts from the defaults in the device's time zone until the person saves", async () => {
    await shown(fakeNotify(), { timeZone: () => 'Europe/Lisbon' });
    expect(screen.getByDisplayValue('Europe/Lisbon')).toBeTruthy();
    expect(screen.getByDisplayValue('09:00')).toBeTruthy();
    expect(screen.getByText('These are the defaults until you save.')).toBeTruthy();
  });

  it('saves the digest time, time zone and quiet hours, all at once', async () => {
    const service = fakeNotify();
    await shown(service);
    fireEvent.changeText(screen.getByLabelText('Digest at'), '08:30');
    fireEvent(screen.getByLabelText('Quiet hours'), 'valueChange', true);
    await settle();
    await press('Save');
    const put = service.calls.find((c) => c.method === 'PUT');
    expect(put?.body).toEqual({
      timezone: 'America/New_York',
      digest_time: '08:30',
      quiet_hours: { start: '22:00', end: '07:00' },
    });
    expect(screen.getByText('Saved.')).toBeTruthy();
    expect(service.settings.get('alice')).toEqual(put?.body);
  });

  it('turns the digest off', async () => {
    const service = fakeNotify();
    await shown(service);
    fireEvent(screen.getByLabelText('A daily digest'), 'valueChange', false);
    await settle();
    expect(screen.queryByLabelText('Digest at')).toBeNull();
    await press('Save');
    expect(service.calls.find((c) => c.method === 'PUT')?.body).toMatchObject({ digest_time: null });
  });

  it('refuses a digest in the quiet hours before calling the notifier', async () => {
    const service = fakeNotify();
    await shown(service);
    fireEvent(screen.getByLabelText('Quiet hours'), 'valueChange', true);
    fireEvent.changeText(screen.getByLabelText('Digest at'), '23:00');
    await settle();
    await press('Save');
    expect(screen.getByText('The digest at 23:00 falls in your quiet hours, when nothing is pushed.')).toBeTruthy();
    expect(service.calls.filter((c) => c.method === 'PUT')).toEqual([]);
  });

  it("shows the notifier's reason when it refuses what was sent", async () => {
    const service = fakeNotify();
    await shown(service);
    fireEvent.changeText(screen.getByLabelText('Time zone'), 'Mars/Olympus');
    service.answerNext(400, { error: 'bad_request', message: 'timezone must be an IANA time zone' });
    await press('Save');
    expect(screen.getByText('timezone must be an IANA time zone')).toBeTruthy();
  });
});

describe('a build without a notify URL', () => {
  it('says so, and calls nothing', async () => {
    render(<NotificationsScreen notify={null} project={PROJECT} pushTokens={null} />);
    await settle();
    expect(screen.getByText(NO_NOTIFY_SERVICE_MESSAGE)).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Send a test notification' })).toBeNull();
  });
});
