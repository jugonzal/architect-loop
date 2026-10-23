// command-center/app-environments C1, in the app: the Environments tab is the real route file in its folder,
// (tabs)/environments/index.tsx, under the real root and tabs layouts. It reads the status document through the
// session's status client (the signed-in fetch, at the build's status URL), and its ship-brief link opens the
// Needs you tab, where the inbox shows the ship card (the concern's Approach: link to it, never duplicate it).

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

import TabsLayout from '../../../app/(tabs)/_layout';
import EnvironmentsTab from '../../../app/(tabs)/environments/index';
import type { Fetch } from '../../../api/fetch';
import { statusUrl } from '../../../api/status';
import { loadStatusFixture } from '../../../api/statusFixtures';
import { fakeClock, fakeGitHub } from '../../../shell/auth/__tests__/fakeGitHub';
import { memorySessionStore } from '../../../shell/auth/sessionStore';
import { SignIn } from '../../../shell/auth/signIn';
import { AppRoot } from '../../../shell/AppRoot';
import type { AppConfig } from '../../../shell/config';
import { SHELL_TABS } from '../../../shell/tabs';

const CONFIG: AppConfig = {
  githubClientId: 'Iv1.test-client',
  statusUrl: 'https://status-123456789012.us-east1.run.app',
  runnerUrl: null,
  threadsUrl: null,
  notifyUrl: null,
  // The fixtures describe example/reports, and the client refuses a document for another project.
  project: 'example/reports',
  environment: 'staging/app',
};

const SIGNED_IN = { token: 'gho_stored', user: { login: 'octocat', name: 'Mona Lisa Octocat' } };

/** A fake status service that answers the build's status URL with a fixture, and records who asked. */
function fakeStatusService(fixture: string) {
  const calls: { url: string; authorization: string | null }[] = [];
  const fetch: Fetch = async (url, init = {}) => {
    calls.push({ url, authorization: new Headers(init.headers).get('Authorization') });
    if (url !== statusUrl(CONFIG.statusUrl!, CONFIG.project)) return new Response('not found', { status: 404 });
    return new Response(JSON.stringify(loadStatusFixture(fixture)), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    });
  };
  return { fetch, calls };
}

function signedIn() {
  const github = fakeGitHub({ clock: fakeClock(), clientId: CONFIG.githubClientId! });
  return new SignIn({
    clientId: CONFIG.githubClientId,
    store: memorySessionStore(SIGNED_IN),
    fetch: github.fetch,
    clock: fakeClock(),
  });
}

async function flush() {
  for (let i = 0; i < 5; i++) {
    await act(async () => {
      await jest.advanceTimersByTimeAsync(0);
    });
  }
}

async function openEnvironments(fixture: string) {
  const service = fakeStatusService(fixture);
  const result = renderRouter(
    {
      _layout: () => <AppRoot signIn={signedIn()} config={CONFIG} fetch={service.fetch} />,
      '(tabs)/_layout': TabsLayout,
      // The other tabs' screens are stand-ins, as their concerns add them.
      ...Object.fromEntries(
        SHELL_TABS.filter((tab) => tab.name !== 'environments').map((tab) => [
          `(tabs)/${tab.name}/index`,
          () => <Text>{tab.title} screen</Text>,
        ]),
      ),
      '(tabs)/environments/index': EnvironmentsTab,
    },
    { initialUrl: '/environments' },
  );
  await flush();
  return { result, service };
}

describe('the Environments tab', () => {
  it("is the shell's Environments tab, and reads the status service as the signed-in person", async () => {
    const { result, service } = await openEnvironments('board');
    expect(result.getPathname()).toBe('/environments');
    expect(screen.getByTestId('tab-environments').props.accessibilityState).toMatchObject({ selected: true });
    expect(service.calls).toEqual([
      { url: 'https://status-123456789012.us-east1.run.app/projects/example/reports/status', authorization: 'Bearer gho_stored' },
    ]);
    expect(screen.getAllByTestId(/^environment-/).map((n) => n.props.testID)).toEqual([
      'environment-main',
      'environment-staging',
      'environment-production',
    ]);
    expect(screen.getByText('serves @d1b62ed')).toBeTruthy();
  });

  it('shows an environment it cannot read as unknown, with the failure', async () => {
    await openEnvironments('unknown');
    expect(screen.getAllByText('UNKNOWN')).toHaveLength(2);
    expect(screen.getByText('GET https://staging.example.com/version timed out after 10 s')).toBeTruthy();
  });

  it('opens Needs you, where the ship card is, from the ship-brief link', async () => {
    const { result } = await openEnvironments('board');
    fireEvent.press(screen.getByRole('button', { name: 'Read the ship brief' }));
    await flush();
    expect(result.getPathname()).toBe('/inbox');
    expect(screen.getByText('Needs you screen')).toBeTruthy();
  });
});
