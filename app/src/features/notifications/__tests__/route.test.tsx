// command-center/notifications, in the app: /notifications is the real route file, src/app/notifications/index.tsx,
// under the real root layout and its sign-in. It calls the build's notify URL through the signed-in fetch, and a
// build without one says so and calls nothing.

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
import { Text } from 'react-native';

import NotificationsRoute from '../../../app/notifications/index';
import { fakeClock, fakeGitHub } from '../../../shell/auth/__tests__/fakeGitHub';
import { memorySessionStore } from '../../../shell/auth/sessionStore';
import { SignIn } from '../../../shell/auth/signIn';
import { AppRoot } from '../../../shell/AppRoot';
import type { AppConfig } from '../../../shell/config';
import { NO_NOTIFY_SERVICE_MESSAGE } from '../NotificationsScreen';
import { NO_PUSH_MODULE_MESSAGE } from '../pushTokens';
import { fakeNotify, NOTIFY_URL } from './fakeNotify';

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

async function flush() {
  for (let i = 0; i < 5; i++) await act(async () => {});
}

async function open(config: AppConfig) {
  const service = fakeNotify();
  const result = renderRouter(
    {
      _layout: () => <AppRoot signIn={signedIn()} config={config} fetch={service.fetch} />,
      'inbox/index': () => <Text>Needs you screen</Text>,
      'notifications/index': NotificationsRoute,
    },
    { initialUrl: '/notifications' },
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
    // This build has no notification module, so it says why it cannot register the device.
    expect(screen.getByText(NO_PUSH_MODULE_MESSAGE)).toBeTruthy();
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
});
