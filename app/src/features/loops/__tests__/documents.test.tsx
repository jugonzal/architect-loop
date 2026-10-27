// app-documents C1 and C2, drawn: the Loops tab's real routes under the real shell and router, signed in, reading
// the board fixture through the real status client, each document through a fake GitHub contents API, and starting
// sessions through the real runner client against a fake runner. Nothing here reaches a real service, and the fake
// runner starts nothing: it only records what the app sent. app-threads' session thread is a stand-in.

import { act, fireEvent, renderRouter, screen, within } from 'expo-router/testing-library';
import { useLocalSearchParams } from 'expo-router';
import { Text } from 'react-native';

import type { Fetch } from '../../../api/fetch';
import type { DispatchRequest, Session } from '../../../api/runner.gen';
import { statusUrl, type StatusDocument } from '../../../api/status';
import { loadStatusFixture } from '../../../api/statusFixtures';
import TabsLayout from '../../../app/(tabs)/_layout';
import LoopsLayout from '../../../app/(tabs)/loops/_layout';
import LoopsRoute from '../../../app/(tabs)/loops/index';
import LoopRoute from '../../../app/(tabs)/loops/[loop]/index';
import ConcernRoute from '../../../app/(tabs)/loops/[loop]/concerns/[concern]';
import { memorySessionStore } from '../../../shell/auth/sessionStore';
import { SignIn } from '../../../shell/auth/signIn';
import { fakeClock, fakeGitHub } from '../../../shell/auth/__tests__/fakeGitHub';
import { AppRoot } from '../../../shell/AppRoot';
import type { AppConfig } from '../../../shell/config';

const STATUS_URL = 'https://status-123456789012.us-east1.run.app';
const RUNNER_URL = 'https://runner-123456789012.us-east1.run.app';
const TOKEN = 'gho_stored';
const RELEASE = 'v0.7.0';

const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });

function configFor(runnerUrl: string | null = RUNNER_URL): AppConfig {
  return {
    githubClientId: 'Iv1.test-client',
    statusUrl: STATUS_URL,
    runnerUrl,
    threadsUrl: null,
    notifyUrl: null,
    project: 'example/reports',
    environment: 'staging/app',
  };
}

const DASHBOARD = [
  '---',
  'needs: [queue]',
  'touches: [web/dashboard/]',
  '---',
  '# The dashboard shows each report as it runs',
  '',
  '## Design',
  '',
  '### Where we are',
  '',
  '- Verified 2026-10-20: the queue publishes `job.started`.',
  '',
  '## Decisions',
  '',
  '| # | Decision | Decided by, date | Closes |',
  '| --- | --- | --- | --- |',
  '| D1 | Poll every **5 s** until push lands. | Ana, 2026-10-20 | Q1 |',
].join('\n');

const README = '# Reports run on a queue\n\n**Intent.** Reports stop timing out.\n';

type Call = { method: string; url: string; auth: string | null; accept: string | null; body: unknown };

/** The fake GitHub contents API, the fake status service and the fake runner behind one fetch. */
function services(
  doc: StatusDocument,
  { files = {}, refuse, earlier = [] }: { files?: Record<string, string>; refuse?: Session; earlier?: Session[] } = {},
) {
  const calls: Call[] = [];
  const sessions: Session[] = [...earlier];
  let next = 1;
  const fetch: Fetch = async (url, init = {}) => {
    const method = init.method ?? 'GET';
    const headers = new Headers(init.headers);
    const body = typeof init.body === 'string' ? JSON.parse(init.body) : undefined;
    calls.push({ method, url, auth: headers.get('Authorization'), accept: headers.get('Accept'), body });
    if (url === statusUrl(STATUS_URL, 'example/reports')) return json(200, doc);
    const contents = /^https:\/\/api\.github\.com\/repos\/example\/reports\/contents\/(.+)\?ref=([0-9a-f]+)$/.exec(url);
    if (contents) {
      const file = files[`${decodeURIComponent(contents[1]!)}@${contents[2]}`];
      return file === undefined ? json(404, { message: 'Not Found' }) : new Response(file, { status: 200 });
    }
    if (!url.startsWith(RUNNER_URL)) return json(404, { error: 'not-found', message: url });
    const { pathname, searchParams } = new URL(url);
    if (method === 'GET' && pathname === '/sessions') return json(200, { sessions: [...sessions].reverse(), cap_per_sponsor: 3 });
    if (method === 'GET' && pathname === '/estimates') {
      const estimate = { kind: 'estimate', usd: 0.84, wall_clock_s: 540, sessions: 7 };
      return json(200, { skill: searchParams.get('skill'), model: 'claude-test', estimate, plugin_release: RELEASE });
    }
    if (method === 'POST' && pathname === '/sessions') {
      if (refuse) {
        return json(409, {
          refused: 'running-session',
          message: `${refuse.concern} already has a running loop-design session`,
          pull_requests: [],
          sessions: [refuse],
        });
      }
      const request = body as DispatchRequest;
      const session = sessionFor({
        id: `s_${next++}`,
        concern: request.concern ?? null,
        loop: request.loop ?? null,
        arguments: request.arguments ?? '',
        budget_usd: request.budget_usd,
      });
      sessions.push(session);
      return json(201, session);
    }
    return json(404, { error: 'not-found', message: url });
  };
  return {
    fetch,
    calls,
    github: () => calls.filter((c) => c.url.startsWith('https://api.github.com/')),
    starts: () => calls.filter((c) => c.method === 'POST'),
  };
}

function sessionFor(change: Partial<Session>): Session {
  return {
    id: 's_0',
    project: 'example/reports',
    skill: 'loop-design',
    concern: null,
    loop: null,
    environment: null,
    arguments: '',
    model: 'claude-test',
    sponsor: 'ana',
    budget_usd: 2,
    plugin_release: RELEASE,
    branch: 'main',
    state: 'starting',
    outcome: null,
    created_at: '2026-10-24T10:00:00Z',
    started_at: null,
    ended_at: null,
    spend: null,
    pull_requests: [],
    final_message: null,
    ...change,
  };
}

function ThreadStand() {
  const { session } = useLocalSearchParams<{ session: string }>();
  return <Text>Thread for session {session}</Text>;
}

function stand(label: string) {
  return function Stand() {
    return <Text>{label} screen</Text>;
  };
}

function signedIn() {
  const clock = fakeClock();
  return new SignIn({
    clientId: 'Iv1.test-client',
    store: memorySessionStore({ token: TOKEN, user: { login: 'ana', name: 'Ana' } }),
    fetch: fakeGitHub({ clock, clientId: 'Iv1.test-client', user: { login: 'ana', name: 'Ana' } }).fetch,
    clock,
  });
}

async function flush() {
  for (let i = 0; i < 6; i++) {
    await act(async () => {
      await jest.advanceTimersByTimeAsync(0);
    });
  }
}

async function open(
  initialUrl: string,
  options: { files?: Record<string, string>; refuse?: Session; earlier?: Session[]; runnerUrl?: string | null } = {},
) {
  const doc = loadStatusFixture('board');
  const fake = services(doc, options);
  const result = renderRouter(
    {
      _layout: () => <AppRoot signIn={signedIn()} config={configFor(options.runnerUrl)} fetch={fake.fetch} />,
      '(tabs)/_layout': TabsLayout,
      '(tabs)/inbox/index': stand('Needs you'),
      '(tabs)/agents/index': stand('Agents'),
      '(tabs)/environments/index': stand('Environments'),
      '(tabs)/loops/_layout': LoopsLayout,
      '(tabs)/loops/index': LoopsRoute,
      '(tabs)/loops/[loop]/index': LoopRoute,
      '(tabs)/loops/[loop]/concerns/[concern]': ConcernRoute,
      'threads/sessions/[session]': ThreadStand,
    },
    { initialUrl },
  );
  await flush();
  return { result, fake, doc };
}

async function press(name: string | RegExp) {
  fireEvent.press(screen.getByRole('button', { name }));
  await flush();
}

const SHA = loadStatusFixture('board').main.sha;
const DASHBOARD_PATH = 'docs/loops/report-pipeline/dashboard.md';
const README_PATH = 'docs/loops/report-pipeline/README.md';

describe('a page’s document (C1)', () => {
  it('shows a concern’s file as it stands at the main commit of the status, and says which commit', async () => {
    const { fake } = await open('/loops/report-pipeline/concerns/dashboard', {
      files: { [`${DASHBOARD_PATH}@${SHA}`]: DASHBOARD },
    });
    expect(fake.github()).toEqual([
      {
        method: 'GET',
        url: `https://api.github.com/repos/example/reports/contents/docs/loops/report-pipeline/dashboard.md?ref=${SHA}`,
        auth: `Bearer ${TOKEN}`,
        accept: 'application/vnd.github.raw+json',
        body: undefined,
      },
    ]);
    const card = within(screen.getByTestId('document'));
    expect(card.getByTestId('document-source')).toHaveTextContent(`${DASHBOARD_PATH} @${SHA.slice(0, 7)}`);
    expect(card.getByText('The dashboard shows each report as it runs')).toBeTruthy();
    expect(card.getByText('Where we are')).toBeTruthy();
    expect(card.getByText('job.started')).toBeTruthy();
    // A decision's row, with its cells under their headers.
    const row = within(card.getByTestId('table-row-0'));
    expect(row.getByText('D1')).toBeTruthy();
    expect(row.getByText('5 s')).toBeTruthy();
    expect(row.getByText('Decided by, date')).toBeTruthy();
    // The front matter is the Contract card's, not drawn again.
    expect(card.queryByText(/touches:/)).toBeNull();
    // The derived state stays first.
    expect(screen.getByTestId('state-strip').props.accessibilityLabel).toBe('State: open');
  });

  it('shows a loop’s README on the loop page', async () => {
    await open('/loops/report-pipeline', { files: { [`${README_PATH}@${SHA}`]: README } });
    const card = within(screen.getByTestId('document'));
    expect(card.getByTestId('document-source')).toHaveTextContent(`${README_PATH} @${SHA.slice(0, 7)}`);
    expect(card.getByText('Reports run on a queue')).toBeTruthy();
    expect(card.getByText('Intent.')).toBeTruthy();
    expect(screen.getByTestId('loop-reason')).toBeTruthy();
  });

  it('says so when the file cannot be read, and still shows the derived state', async () => {
    await open('/loops/report-pipeline/concerns/dashboard');
    const card = within(screen.getByTestId('document'));
    expect(card.getByText(/could not be read at @[0-9a-f]{7}/)).toBeTruthy();
    expect(card.getByText(/answered 404/)).toBeTruthy();
    expect(screen.getByTestId('state-strip').props.accessibilityLabel).toBe('State: open');
    expect(screen.getByTestId('contract')).toBeTruthy();
  });

});

describe('a design session from a page (C2)', () => {
  it('starts /loop-design on the concern, naming no question, after showing the estimate, the budget and the release', async () => {
    const { fake, result } = await open('/loops/report-pipeline/concerns/dashboard');
    expect(fake.starts()).toEqual([]);
    await press('Design it in a session');
    const sheet = within(screen.getByTestId('design-sheet'));
    expect(sheet.getByTestId('start-command')).toHaveTextContent('/loop-design report-pipeline/dashboard');
    expect(sheet.getByTestId('start-sponsor')).toHaveTextContent(/^Sponsored by @ana:/);
    expect(sheet.getByTestId('start-estimate')).toHaveTextContent(/^Estimated \$0\.84 and 9 min/);
    expect(sheet.getByTestId('start-release')).toHaveTextContent(new RegExp(`^Runs the skills released as ${RELEASE}`));
    expect(fake.starts()).toEqual([]);

    fireEvent.changeText(sheet.getByLabelText('Budget, in dollars'), '3.50');
    await flush();
    await press('Start · budget $3.50');
    expect(fake.starts().map((c) => c.body)).toEqual([
      {
        project: 'example/reports',
        skill: 'loop-design',
        concern: 'report-pipeline/dashboard',
        arguments: '',
        budget_usd: 3.5,
        plugin_release: RELEASE,
      },
    ]);
    expect(fake.starts()[0]!.auth).toBe(`Bearer ${TOKEN}`);
    expect(result.getPathname()).toBe('/threads/sessions/s_1');
  });

  it('starts /loop-design on the loop from the loop page', async () => {
    const { fake, result } = await open('/loops/report-pipeline');
    await press('Design it in a session');
    expect(screen.getByTestId('start-command')).toHaveTextContent('/loop-design report-pipeline');
    await press('Start · budget $2.00');
    expect(fake.starts().map((c) => c.body)).toEqual([
      {
        project: 'example/reports',
        skill: 'loop-design',
        loop: 'report-pipeline',
        arguments: '',
        budget_usd: 2,
        plugin_release: RELEASE,
      },
    ]);
    expect(result.getPathname()).toBe('/threads/sessions/s_1');
  });

  it('shows the runner’s refusal and the session already running, and follows that one', async () => {
    const running = sessionFor({ id: 's_9', concern: 'report-pipeline/dashboard', arguments: 'Q1', state: 'running', sponsor: 'ben' });
    const { result } = await open('/loops/report-pipeline/concerns/dashboard', { refuse: running });
    await press('Design it in a session');
    await press('Start · budget $2.00');
    expect(screen.getByText(/The runner did not start it\. report-pipeline\/dashboard already has a running loop-design session/)).toBeTruthy();
    await press('Follow the session already doing it');
    expect(result.getPathname()).toBe('/threads/sessions/s_9');
  });

  it('shows a design session already running on the concern, whoever started it, before anything starts', async () => {
    const running = sessionFor({ id: 's_7', concern: 'report-pipeline/dashboard', state: 'running', sponsor: 'ben' });
    const other = sessionFor({ id: 's_8', concern: 'report-pipeline/worker', state: 'running' });
    const ended = sessionFor({ id: 's_6', concern: 'report-pipeline/dashboard', state: 'ended', outcome: 'completed' });
    const { fake, result } = await open('/loops/report-pipeline/concerns/dashboard', { earlier: [ended, running, other] });
    const card = within(screen.getByTestId('design'));
    expect(card.getByTestId('design-running')).toHaveTextContent(/^running · sponsored by @ben · /);
    expect(fake.starts()).toEqual([]);
    fireEvent.press(card.getByRole('button', { name: 'Open its thread' }));
    await flush();
    expect(result.getPathname()).toBe('/threads/sessions/s_7');
  });

  it('cancels without starting anything', async () => {
    const { fake } = await open('/loops/report-pipeline/concerns/dashboard');
    await press('Design it in a session');
    await press('Cancel');
    expect(screen.queryByTestId('design-sheet')).toBeNull();
    expect(fake.starts()).toEqual([]);
  });

  it('says the build has no runner, instead of offering a start', async () => {
    const { fake } = await open('/loops/report-pipeline/concerns/dashboard', { runnerUrl: null });
    expect(within(screen.getByTestId('design')).getByText(/no URL for the runner service/)).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Design it in a session' })).toBeNull();
    expect(fake.calls.filter((c) => c.url.startsWith(RUNNER_URL))).toEqual([]);
  });
});
