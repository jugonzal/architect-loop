// command-center/app-agents C1 and C2, in the app: the Agents tab is the real route file in its folder,
// (tabs)/agents/index.tsx, under the real root and tabs layouts. It calls the runner at the build's runner URL and
// the status service at its status URL, both through the signed-in fetch, so every call carries the signed-in
// person's token and the runner makes them the sponsor of what they start (command-center/D28). It reads the
// runner again only while the tab is in front.

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
import AgentsTab from '../../../app/(tabs)/agents/index';
import type { Fetch } from '../../../api/fetch';
import { statusUrl } from '../../../api/status';
import { loadStatusFixture } from '../../../api/statusFixtures';
import { fakeClock, fakeGitHub } from '../../../shell/auth/__tests__/fakeGitHub';
import { memorySessionStore } from '../../../shell/auth/sessionStore';
import { SignIn } from '../../../shell/auth/signIn';
import { AppRoot } from '../../../shell/AppRoot';
import type { AppConfig } from '../../../shell/config';
import { SHELL_TABS } from '../../../shell/tabs';
import { REFRESH_MS } from '../sessions';
import { FAKE_RELEASE, fakeRunner, RUNNER_URL, session } from './fakeRunner';

const CONFIG: AppConfig = {
  githubClientId: 'Iv1.test-client',
  statusUrl: 'https://status-123456789012.us-east1.run.app',
  runnerUrl: RUNNER_URL,
  threadsUrl: null,
  notifyUrl: null,
  // The fixtures describe example/reports, and the status client refuses a document for another project.
  project: 'example/reports',
  environment: 'staging/app',
};

const SIGNED_IN = { token: 'gho_stored', user: { login: 'octocat', name: 'Mona Lisa Octocat' } };

function signedIn() {
  const clock = fakeClock();
  return new SignIn({
    clientId: CONFIG.githubClientId,
    store: memorySessionStore(SIGNED_IN),
    fetch: fakeGitHub({ clock, clientId: CONFIG.githubClientId! }).fetch,
    clock,
  });
}

/** One fetch for both services: the status service answers the board fixture, the fake runner the rest. */
function services(config: AppConfig) {
  const runner = fakeRunner({
    sessions: [
      session({ sponsor: 'octocat', concern: 'report-pipeline/retries' }),
      session({ sponsor: 'hubot', skill: 'loop-prove', concern: 'report-pipeline/queue', arguments: 'staging' }),
    ],
    estimates: { 'loop-build': { usd: 1.6, wall_clock_s: 840, sessions: 7 } },
  });
  const statusCalls: { url: string; auth: string | null }[] = [];
  const fetch: Fetch = async (url, init = {}) => {
    if (config.statusUrl && url.startsWith(config.statusUrl)) {
      statusCalls.push({ url, auth: new Headers(init.headers).get('Authorization') });
      if (url !== statusUrl(config.statusUrl, config.project)) return new Response('not found', { status: 404 });
      return new Response(JSON.stringify(loadStatusFixture('board')), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      });
    }
    return runner.fetch(url, init);
  };
  return { fetch, runner, statusCalls };
}

async function flush() {
  for (let i = 0; i < 6; i++) {
    await act(async () => {
      await jest.advanceTimersByTimeAsync(0);
    });
  }
}

async function openAgents(config: AppConfig = CONFIG) {
  const service = services(config);
  const result = renderRouter(
    {
      _layout: () => <AppRoot signIn={signedIn()} config={config} fetch={service.fetch} />,
      '(tabs)/_layout': TabsLayout,
      // The other tabs' screens are stand-ins, as their concerns add them.
      ...Object.fromEntries(
        SHELL_TABS.filter((tab) => tab.name !== 'agents').map((tab) => [
          `(tabs)/${tab.name}/index`,
          () => <Text>{tab.title} screen</Text>,
        ]),
      ),
      '(tabs)/agents/index': AgentsTab,
    },
    { initialUrl: '/agents' },
  );
  await flush();
  return { result, ...service };
}

describe('the Agents tab', () => {
  it("is the shell's Agents tab, and reads the runner and the status service as the signed-in person", async () => {
    const { result, runner, statusCalls } = await openAgents();
    expect(result.getPathname()).toBe('/agents');
    expect(screen.getByTestId('tab-agents').props.accessibilityState).toMatchObject({ selected: true });
    expect(statusCalls).toEqual([
      { url: 'https://status-123456789012.us-east1.run.app/projects/example/reports/status', auth: 'Bearer gho_stored' },
    ]);
    expect(runner.callsTo('GET', '/sessions')).toEqual([
      expect.objectContaining({ query: { state: 'active' }, auth: 'Bearer gho_stored' }),
    ]);
    expect(screen.getByText('loop-build · report-pipeline/retries')).toBeTruthy();
    expect(screen.getByText('loop-prove · report-pipeline/queue')).toBeTruthy();
    expect(screen.getByTestId('agents-slots')).toHaveTextContent('You sponsor 1 of your 3 session slots.');
    expect(screen.getByRole('button', { name: 'Start report-pipeline/exporter' })).toBeTruthy();
  });

  it('starts a ready concern only after the person confirms, with them as sponsor', async () => {
    const { runner } = await openAgents();
    fireEvent.press(screen.getByRole('button', { name: 'Start report-pipeline/exporter' }));
    await flush();
    expect(runner.callsTo('POST', '/sessions')).toHaveLength(0);
    await act(async () => {
      fireEvent.press(screen.getByRole('button', { name: 'Start with a $2.00 budget' }));
    });
    await flush();
    const dispatches = runner.callsTo('POST', '/sessions');
    expect(dispatches).toHaveLength(1);
    expect(dispatches[0]).toMatchObject({
      auth: 'Bearer gho_stored',
      body: {
        project: 'example/reports',
        skill: 'loop-build',
        concern: 'report-pipeline/exporter',
        budget_usd: 2,
        plugin_release: FAKE_RELEASE,
      },
    });
    expect(runner.state.sessions[0]).toMatchObject({ sponsor: 'octocat', concern: 'report-pipeline/exporter' });
    expect(screen.getByText(/^Started session [0-9a-f]{7}, sponsored by octocat, with a \$2\.00 budget\.$/)).toBeTruthy();
  });

  it('stops reading the runner while another tab is in front, and reads it at once on coming back', async () => {
    const { runner } = await openAgents();
    await act(async () => {
      await jest.advanceTimersByTimeAsync(REFRESH_MS);
    });
    await flush();
    const whileOpen = runner.callsTo('GET', '/sessions').length;
    expect(whileOpen).toBeGreaterThanOrEqual(2);

    fireEvent.press(screen.getByTestId('tab-loops'));
    await flush();
    expect(screen.getByText('Loops screen')).toBeTruthy();
    await act(async () => {
      await jest.advanceTimersByTimeAsync(6 * REFRESH_MS);
    });
    expect(runner.callsTo('GET', '/sessions')).toHaveLength(whileOpen);

    fireEvent.press(screen.getByTestId('tab-agents'));
    await flush();
    expect(runner.callsTo('GET', '/sessions')).toHaveLength(whileOpen + 1);
  });

  it('says the build has no runner URL instead of calling it', async () => {
    const { runner } = await openAgents({ ...CONFIG, runnerUrl: null });
    expect(runner.calls).toHaveLength(0);
    expect(screen.getAllByText(/This build has no URL for the runner service yet/).length).toBeGreaterThan(0);
  });
});
