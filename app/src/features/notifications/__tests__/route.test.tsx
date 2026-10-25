// command-center/notifications, in the app: /notifications is the real route file, src/app/notifications/index.tsx,
// under the real root layout and its sign-in, reached from the account sheet in the shell's header (D4). It calls the
// build's notify URL through the signed-in fetch, registers this device with the token source it is given, and a
// tap on a push opens the inbox, or the route the push names (D1), through the real root.

// The router reads its redirects from the app config (extra.router), as in the shell's own test.
jest.mock('expo-constants', () => {
  const actual = jest.requireActual('expo-constants');
  const plugins: unknown[] = require('../../../../app.json').expo.plugins;
  const router = plugins.find((p): p is [string, object] => Array.isArray(p) && p[0] === 'expo-router');
  const constants = actual.default;
  const expoConfig = { ...constants.expoConfig, extra: { ...constants.expoConfig?.extra, router: router?.[1] } };
  const withConfig = Object.create(constants, { expoConfig: { value: expoConfig, enumerable: true } });
  return { __esModule: true, ...actual, default: withConfig };
});

import { act, fireEvent, renderRouter, screen } from 'expo-router/testing-library';
import { Alert, Text } from 'react-native';

import TabsLayout from '../../../app/(tabs)/_layout';
import NotificationsRoute from '../../../app/notifications/index';
import { fakeClock, fakeGitHub } from '../../../shell/auth/__tests__/fakeGitHub';
import { memorySessionStore } from '../../../shell/auth/sessionStore';
import { SignIn } from '../../../shell/auth/signIn';
import { AppRoot } from '../../../shell/AppRoot';
import type { AppConfig } from '../../../shell/config';
import { SHELL_TABS } from '../../../shell/tabs';
import { NO_NOTIFY_SERVICE_MESSAGE } from '../NotificationsScreen';
import type { PushTaps } from '../pushTaps';
import type { PushTokenSource } from '../pushTokens';
import { fakeDevice, fakeNotify, NOTIFY_URL } from './fakeNotify';

const CONFIG: AppConfig = {
  githubClientId: 'Iv1.test-client',
  statusUrl: null,
  runnerUrl: null,
  threadsUrl: null,
  notifyUrl: NOTIFY_URL,
  project: 'jugonzal/architect-loop',
  environment: 'staging/app',
};

function signedIn() {
  const github = fakeGitHub({ clock: fakeClock(), clientId: CONFIG.githubClientId! });
  return new SignIn({
    clientId: CONFIG.githubClientId,
    store: memorySessionStore({ token: 'gho_alice', user: { login: 'alice', name: 'Alice' } }),
    fetch: github.fetch,
    clock: fakeClock(),
  });
}

/** Pushes the test taps by hand: `tap` as a person would, and `launch` for the one that opened the app. */
function fakeTaps(launch: unknown = null) {
  const listeners = new Set<(data: unknown) => void>();
  const taps: PushTaps = {
    subscribe(onTap) {
      listeners.add(onTap);
      return () => listeners.delete(onTap);
    },
    launchedBy: async () => launch,
  };
  return { taps, tap: (data: unknown) => listeners.forEach((l) => l(data)), listening: () => listeners.size };
}

async function flush() {
  for (let i = 0; i < 5; i++) await act(async () => {});
}

async function open(
  config: AppConfig,
  { initialUrl = '/notifications', pushTokens = null as PushTokenSource | null, taps = fakeTaps().taps } = {},
) {
  const service = fakeNotify();
  const result = renderRouter(
    {
      _layout: () => <AppRoot signIn={signedIn()} config={config} fetch={service.fetch} pushTaps={taps} />,
      '(tabs)/_layout': TabsLayout,
      ...Object.fromEntries(
        SHELL_TABS.map((tab) => [`(tabs)/${tab.name}/index`, () => <Text>{tab.title} screen</Text>]),
      ),
      'notifications/index': () => <NotificationsRoute pushTokens={pushTokens} />,
    },
    { initialUrl },
  );
  await flush();
  return { result, service };
}

describe('the notifications route', () => {
  it("is /notifications, and reads the notifier as the signed-in person at the build's URL", async () => {
    const { result, service } = await open(CONFIG);
    expect(result.getPathname()).toBe('/notifications');
    expect(screen.getByText('Notifications')).toBeTruthy();
    expect(service.calls.map((c) => `${c.method} ${c.path} ${c.token}`).sort()).toEqual([
      'GET /projects/jugonzal/architect-loop/devices gho_alice',
      'GET /projects/jugonzal/architect-loop/settings/me gho_alice',
    ]);
  });

  it("registers this device with the build's push tokens", async () => {
    const { service } = await open(CONFIG, { pushTokens: fakeDevice('ExponentPushToken[route]').source });
    fireEvent.press(screen.getByRole('button', { name: 'Turn on notifications on this device' }));
    await flush();
    expect(service.devices.size).toBe(1);
    expect(screen.getByText('This device gets your notifications.')).toBeTruthy();
  });

  it('says a build without a notify URL has none, and calls nothing', async () => {
    const { service } = await open({ ...CONFIG, notifyUrl: null });
    expect(screen.getByText(NO_NOTIFY_SERVICE_MESSAGE)).toBeTruthy();
    expect(service.calls).toEqual([]);
  });

  it('goes back to Needs you when it was opened on its own, from a notification', async () => {
    const { result } = await open(CONFIG);
    fireEvent.press(screen.getByRole('button', { name: 'Back' }));
    await flush();
    expect(result.getPathname()).toBe('/inbox');
  });

  it("opens from the account sheet in the shell's header (D4)", async () => {
    const alert = jest.spyOn(Alert, 'alert').mockImplementation(() => undefined);
    try {
      const { result } = await open(CONFIG, { initialUrl: '/inbox' });
      fireEvent.press(screen.getByLabelText(/^Signed in as /));
      const buttons = alert.mock.calls[0]?.[2] ?? [];
      expect(buttons.map((b) => b.text)).toEqual(['Notifications', 'Cancel', 'Sign out']);
      act(() => buttons.find((b) => b.text === 'Notifications')?.onPress?.());
      await flush();
      expect(result.getPathname()).toBe('/notifications');
    } finally {
      alert.mockRestore();
    }
  });
});

describe('a tap on a push (D1)', () => {
  it('opens the inbox for a blocking item or the digest', async () => {
    const taps = fakeTaps();
    const { result } = await open(CONFIG, { initialUrl: '/loops', taps: taps.taps });
    expect(taps.listening()).toBe(1);
    act(() => taps.tap({ url: '/inbox', project: CONFIG.project, item: 'command-center/notifications/Q1' }));
    await flush();
    expect(result.getPathname()).toBe('/inbox');
  });

  it('opens the notifications screen for a test notification, and the inbox for anything else', async () => {
    const taps = fakeTaps();
    const { result } = await open(CONFIG, { initialUrl: '/loops', taps: taps.taps });
    act(() => taps.tap({ url: '/notifications', test: true }));
    await flush();
    expect(result.getPathname()).toBe('/notifications');
    act(() => taps.tap({ url: 'https://example.com/elsewhere' }));
    await flush();
    expect(result.getPathname()).toBe('/inbox');
  });

  it('opens what the push that launched the app names', async () => {
    const { result } = await open(CONFIG, { initialUrl: '/loops', taps: fakeTaps({ url: '/inbox' }).taps });
    expect(result.getPathname()).toBe('/inbox');
  });
});
