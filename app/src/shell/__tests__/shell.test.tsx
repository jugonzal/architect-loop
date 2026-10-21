// app-shell C1, the shell half: with the real root and tabs layouts and the real router, a signed-out person sees
// the sign-in, and a signed-in one sees their name and the four tabs of the screen design, in order, with no More
// tab. Screens are stand-ins here, added the way each screen concern adds its own: as files in its tab's folder.

// The router reads its redirects from the app config (extra.router), which the expo-router plugin fills from
// app.json; jest's expo-constants has a stand-in config, so give it app.json's.
jest.mock('expo-constants', () => {
  const actual = jest.requireActual('expo-constants');
  const plugins: unknown[] = require('../../../app.json').expo.plugins;
  const router = plugins.find((p): p is [string, object] => Array.isArray(p) && p[0] === 'expo-router');
  const constants = actual.default;
  const expoConfig = { ...constants.expoConfig, extra: { ...constants.expoConfig?.extra, router: router?.[1] } };
  const withConfig = Object.create(constants, { expoConfig: { value: expoConfig, enumerable: true } });
  return { __esModule: true, ...actual, default: withConfig };
});

import { act, fireEvent, renderRouter, screen } from 'expo-router/testing-library';
import { Text } from 'react-native';

import RootLayout from '../../app/_layout';
import TabsLayout from '../../app/(tabs)/_layout';
import { memorySessionStore } from '../auth/sessionStore';
import { SignIn } from '../auth/signIn';
import { fakeClock, fakeGitHub } from '../auth/__tests__/fakeGitHub';
import { AppRoot } from '../AppRoot';
import type { AppConfig } from '../config';
import { SHELL_TABS } from '../tabs';

const CONFIG: AppConfig = {
  githubClientId: 'Iv1.test-client',
  statusUrl: 'https://status-123456789012.us-east1.run.app',
  project: 'jugonzal/architect-loop',
  environment: 'staging/app',
};

const SIGNED_IN = { token: 'gho_stored', user: { login: 'octocat', name: 'Mona Lisa Octocat' } };

function stand(label: string) {
  return function Stand() {
    return <Text>{label} screen</Text>;
  };
}

/** Every screen concern's tab, as the four of them add it: (tabs)/<tab>/index.tsx. */
const ALL_SCREENS = Object.fromEntries(SHELL_TABS.map((tab) => [`(tabs)/${tab.name}/index`, stand(tab.title)]));

function app(signIn: SignIn, screens: Record<string, () => React.JSX.Element> = ALL_SCREENS) {
  return {
    _layout: () => <AppRoot signIn={signIn} config={CONFIG} />,
    '(tabs)/_layout': TabsLayout,
    ...screens,
  };
}

function signInWith(stored: typeof SIGNED_IN | null, github = fakeGitHub({ clock: fakeClock(), clientId: CONFIG.githubClientId! })) {
  return new SignIn({ clientId: CONFIG.githubClientId, store: memorySessionStore(stored), fetch: github.fetch, clock: fakeClock() });
}

/** renderRouter runs on fake timers, so pending work (fonts, the session's restore, navigation) runs by advancing them. */
async function flush() {
  for (let i = 0; i < 5; i++) {
    await act(async () => {
      await jest.advanceTimersByTimeAsync(0);
    });
  }
}

async function rendered(signIn: SignIn, screens?: Record<string, () => React.JSX.Element>, initialUrl = '/') {
  const result = renderRouter(app(signIn, screens), { initialUrl });
  await flush();
  return result;
}

describe('the app shell', () => {
  it('shows the sign-in, and no tab, until someone is signed in', async () => {
    await rendered(signInWith(null));
    expect(screen.getByRole('button', { name: 'Sign in with GitHub' })).toBeTruthy();
    expect(screen.queryByRole('tab')).toBeNull();
  });

  it("shows the signed-in person's name and the four tabs, in the design's order, with no More tab", async () => {
    await rendered(signInWith(SIGNED_IN));
    expect(screen.getByTestId('signed-in-name').props.children).toBe('Mona Lisa Octocat');
    expect(screen.getByLabelText('Signed in as Mona Lisa Octocat')).toBeTruthy();
    const tabs = screen.getAllByRole('tab').map((tab) => tab.props.accessibilityLabel);
    expect(tabs).toEqual(['Needs you', 'Loops', 'Agents', 'Environments']);
    expect(screen.queryByText(/More/)).toBeNull();
  });

  it('opens on Needs you, and each tab opens its own screen', async () => {
    const result = await rendered(signInWith(SIGNED_IN));
    expect(screen.getByText('Needs you screen')).toBeTruthy();
    expect(result.getPathname()).toBe('/inbox');
    for (const tab of SHELL_TABS) {
      fireEvent.press(screen.getByTestId(`tab-${tab.name}`));
      await flush();
      expect(screen.getByText(`${tab.title} screen`)).toBeTruthy();
      expect(result.getPathname()).toBe(`/${tab.name}`);
      expect(screen.getByTestId(`tab-${tab.name}`).props.accessibilityState).toMatchObject({ selected: true });
    }
  });

  it('lets a screen concern add a tab with a folder of its own and a nested stack, without editing the shell', async () => {
    const screens = {
      ...ALL_SCREENS,
      // app-loops-board, say, with its own stack: (tabs)/loops/_layout.tsx, index.tsx and [concern].tsx.
      '(tabs)/loops/_layout': () => {
        const { Stack } = require('expo-router');
        return <Stack screenOptions={{ headerShown: false }} />;
      },
      '(tabs)/loops/[concern]': stand('A concern'),
    };
    const result = await rendered(signInWith(SIGNED_IN), screens, '/loops/app-shell');
    expect(screen.getByText('A concern screen')).toBeTruthy();
    // The concern's screen is under the Loops tab, not a tab of its own.
    expect(screen.getAllByRole('tab')).toHaveLength(4);
    expect(screen.getByTestId('tab-loops').props.accessibilityState).toMatchObject({ selected: true });
    expect(result.getPathname()).toBe('/loops/app-shell');
  });

  it('shows a tab whose screen is not built yet, disabled', async () => {
    const { ['(tabs)/agents/index']: _agents, ...screens } = ALL_SCREENS;
    await rendered(signInWith(SIGNED_IN), screens);
    expect(screen.getAllByRole('tab')).toHaveLength(4);
    expect(screen.getByTestId('tab-agents').props.accessibilityState).toMatchObject({ disabled: true });
    expect(screen.getByLabelText('Agents, not built yet')).toBeTruthy();
  });

  it('goes back to the sign-in when the person signs out', async () => {
    const signIn = signInWith(SIGNED_IN);
    await rendered(signIn);
    expect(screen.getAllByRole('tab')).toHaveLength(4);
    await act(() => signIn.signOut());
    expect(screen.getByRole('button', { name: 'Sign in with GitHub' })).toBeTruthy();
    expect(screen.queryByRole('tab')).toBeNull();
  });

  it('is what the root layout file renders', () => {
    expect(RootLayout().type).toBe(AppRoot);
  });
});
