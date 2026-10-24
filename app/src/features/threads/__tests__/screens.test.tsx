// app-threads C1 and C2, drawn: the three thread routes at the paths command-center/D52 fixes, under the real root
// layout, router and signed-in fetch, calling a fake threads service and a fake runner through the clients app-clients
// generated (command-center/D55), with the loop's owner read from the status schema's board fixture (ana owns
// report-pipeline; ben is a member). The Loops tab's real routes are here too, to follow the Concern page's link in.

import { act, fireEvent, renderRouter, screen, within } from 'expo-router/testing-library';
import { Text } from 'react-native';

import type { Fetch } from '../../../api/fetch';
import { loadStatusFixture } from '../../../api/statusFixtures';
import TabsLayout from '../../../app/(tabs)/_layout';
import LoopsLayout from '../../../app/(tabs)/loops/_layout';
import LoopsRoute from '../../../app/(tabs)/loops/index';
import LoopRoute from '../../../app/(tabs)/loops/[loop]/index';
import ConcernRoute from '../../../app/(tabs)/loops/[loop]/concerns/[concern]';
import LoopThreadRoute from '../../../app/threads/loops/[loop]/index';
import ConcernThreadRoute from '../../../app/threads/loops/[loop]/concerns/[concern]';
import SessionThreadRoute from '../../../app/threads/sessions/[session]';
import { fakeClock, fakeGitHub } from '../../../shell/auth/__tests__/fakeGitHub';
import { memorySessionStore } from '../../../shell/auth/sessionStore';
import { SignIn } from '../../../shell/auth/signIn';
import { AppRoot } from '../../../shell/AppRoot';
import type { AppConfig } from '../../../shell/config';
import { MAX_ARGUMENTS, SKILLS_RELEASE } from '../thread';
import { at, fakeRunner, fakeSession, fakeThreads, person, RUNNER_URL, services, STATUS_URL, THREADS_URL } from './fakeServices';

const PROJECT = 'example/reports';
const PEOPLE = {
  ana: { token: 'gho_ana', user: { login: 'ana', name: 'Ana' } },
  ben: { token: 'gho_ben', user: { login: 'ben', name: 'Ben' } },
  carol: { token: 'gho_carol', user: { login: 'carol', name: 'Carol' } },
};
const TOKENS = { gho_ana: 'ana', gho_ben: 'ben', gho_carol: 'carol' };
const SESSION_ID = 'a1b2c3d4e5f60718293a4b5c6d7e8f90';

const CONCERN_THREAD = '/threads/loops/report-pipeline/concerns/queue';
const LOOP_THREAD = '/threads/loops/report-pipeline';
const SESSION_THREAD = `/threads/sessions/${SESSION_ID}`;

function configWith(overrides: Partial<AppConfig> = {}): AppConfig {
  return {
    githubClientId: 'Iv1.test-client',
    statusUrl: STATUS_URL,
    runnerUrl: RUNNER_URL,
    threadsUrl: THREADS_URL,
    notifyUrl: null,
    project: PROJECT,
    environment: 'staging/app',
    ...overrides,
  };
}

/** Signed in with a stored token, which the fake GitHub confirms is that person's when the app restores it. */
function signedInAs(who: keyof typeof PEOPLE) {
  const clock = fakeClock();
  return new SignIn({
    clientId: 'Iv1.test-client',
    store: memorySessionStore(PEOPLE[who]),
    fetch: fakeGitHub({ clock, clientId: 'Iv1.test-client', user: PEOPLE[who].user }).fetch,
    clock,
  });
}

function stand(label: string) {
  return function Stand() {
    return <Text>{label} screen</Text>;
  };
}

async function flush() {
  for (let i = 0; i < 8; i++) {
    await act(async () => {
      await jest.advanceTimersByTimeAsync(0);
    });
  }
}

function world({ pageSize }: { pageSize?: number } = {}) {
  const threads = fakeThreads({ project: PROJECT, members: ['ana', 'ben'], tokens: TOKENS, pageSize });
  const runner = fakeRunner({ tokens: TOKENS });
  return { threads, runner };
}

async function open(
  initialUrl: string,
  { threads, runner }: ReturnType<typeof world>,
  { as = 'ana', config = configWith() }: { as?: keyof typeof PEOPLE; config?: AppConfig } = {},
) {
  const service = services({ threads, runner, status: loadStatusFixture('board') });
  const fetch: Fetch = service.fetch;
  const signIn = signedInAs(as);
  const result = renderRouter(
    {
      _layout: () => <AppRoot signIn={signIn} config={config} fetch={fetch} />,
      '(tabs)/_layout': TabsLayout,
      '(tabs)/inbox/index': stand('Needs you'),
      '(tabs)/agents/index': stand('Agents'),
      '(tabs)/environments/index': stand('Environments'),
      '(tabs)/loops/_layout': LoopsLayout,
      '(tabs)/loops/index': LoopsRoute,
      '(tabs)/loops/[loop]/index': LoopRoute,
      '(tabs)/loops/[loop]/concerns/[concern]': ConcernRoute,
      'threads/loops/[loop]/index': LoopThreadRoute,
      'threads/loops/[loop]/concerns/[concern]': ConcernThreadRoute,
      'threads/sessions/[session]': SessionThreadRoute,
    },
    { initialUrl },
  );
  await flush();
  return { ...result, calls: service.calls };
}

/** The message bubbles and lines on screen, by message id, in the order they are drawn. */
function drawnIds(): number[] {
  return screen.getAllByTestId(/^message-\d+$/).map((el) => Number(String(el.props.testID).replace('message-', '')));
}

function threadCalls(calls: { service: string; method: string; path: string; query: URLSearchParams }[]) {
  return calls
    .filter((c) => c.service === 'threads')
    .map((c) => `${c.method} ${c.path}${[...c.query].length ? `?${c.query}` : ''}`);
}

async function type(text: string) {
  fireEvent.changeText(screen.getByLabelText('Message the thread'), text);
  await flush();
}

async function press(name: string | RegExp, scope: Pick<typeof screen, 'getByRole'> = screen) {
  fireEvent.press(scope.getByRole('button', { name }));
  await flush();
}

function seedConcernThread(threads: ReturnType<typeof fakeThreads>) {
  return threads.seed(
    threads.paths.concern('report-pipeline', 'queue'),
    [
      { body: 'Should the queue retry forever?', author: person('ben'), created_at: at(0, '2026-10-23') },
      {
        body: 'Cap it at five tries.',
        author: { type: 'github', login: 'dana', association: 'NONE' },
        created_at: at(5, '2026-10-23'),
        source: {
          type: 'github_review_comment',
          url: 'https://github.com/example/reports/pull/61#discussion_r1',
          pull_request: 61,
          path: 'worker/retry.py',
          review_state: null,
        },
      },
      { body: 'Five tries, then the dead-letter queue.', author: person('ana'), created_at: at(14) },
    ],
    { watchers: ['ben'] },
  );
}

describe('a concern thread (C1)', () => {
  it('shows its whole history oldest first, its members and who is watching, read as the signed-in member', async () => {
    const w = world();
    const seeded = seedConcernThread(w.threads);
    const { calls } = await open(CONCERN_THREAD, w);

    expect(screen.getByText('Concern thread')).toBeTruthy();
    expect(screen.getByText('report-pipeline/queue · owner ana')).toBeTruthy();
    expect(drawnIds()).toEqual(seeded.map((m) => m.id));
    for (const m of seeded) expect(screen.getByText(m.body)).toBeTruthy();
    // A day line wherever the day changes, in UTC like the board.
    expect(screen.getByText('2026-10-23 · UTC')).toBeTruthy();
    expect(screen.getByText('2026-10-24 · UTC')).toBeTruthy();
    // A mirrored review comment says where it came from (command-center/D6); the owner is named as such.
    expect(within(screen.getByTestId(`message-${seeded[1]!.id}`)).getByText(/review comment on PR #61 · worker\/retry.py · 16:05/)).toBeTruthy();
    expect(within(screen.getByTestId(`message-${seeded[2]!.id}`)).getByText(/loop owner · 16:14/)).toBeTruthy();

    expect(screen.getByTestId('members')).toHaveTextContent('2 members: ana, ben');
    expect(screen.getByTestId('watchers')).toHaveTextContent('Watching: ben');

    expect(threadCalls(calls)).toEqual([
      'GET /projects/example/reports/loops/report-pipeline/concerns/queue/thread',
      'GET /projects/example/reports/loops/report-pipeline/concerns/queue/thread/messages?after=0&limit=500',
    ]);
    expect(new Set(calls.map((c) => c.auth))).toEqual(new Set(['Bearer gho_ana']));
  });

  it('reads a history longer than a page whole, a page at a time', async () => {
    const w = world({ pageSize: 2 });
    const seeded = w.threads.seed(
      w.threads.paths.concern('report-pipeline', 'queue'),
      [1, 2, 3, 4, 5].map((n) => ({ body: `Message ${n}`, author: person('ben') })),
    );
    const { calls } = await open(CONCERN_THREAD, w);
    expect(drawnIds()).toEqual(seeded.map((m) => m.id));
    expect(threadCalls(calls).filter((c) => c.includes('/messages'))).toEqual([
      'GET /projects/example/reports/loops/report-pipeline/concerns/queue/thread/messages?after=0&limit=500',
      'GET /projects/example/reports/loops/report-pipeline/concerns/queue/thread/messages?after=2&limit=500',
      'GET /projects/example/reports/loops/report-pipeline/concerns/queue/thread/messages?after=4&limit=500',
    ]);
  });

  it('posts as the signed-in person, a plain message naming no sponsor, and shows it as theirs', async () => {
    const w = world();
    seedConcernThread(w.threads);
    const { calls } = await open(CONCERN_THREAD, w, { as: 'ben' });

    await type('  Agreed: five tries.  ');
    await press('Send');

    const post = calls.find((c) => c.method === 'POST')!;
    expect(post.path).toBe('/projects/example/reports/loops/report-pipeline/concerns/queue/thread/messages');
    expect(post.body).toEqual({ body: 'Agreed: five tries.' });
    expect(post.auth).toBe('Bearer gho_ben');
    const posted = screen.getByText('Agreed: five tries.');
    expect(posted).toBeTruthy();
    const bubble = screen.getAllByTestId(/^message-\d+$/).pop()!;
    expect(within(bubble).getByText(/^ben/)).toBeTruthy();
    expect(screen.getByLabelText('Message the thread').props.value).toBe('');
  });

  it('does not send an empty message', async () => {
    const w = world();
    const { calls } = await open(CONCERN_THREAD, w);
    await type('   ');
    expect(screen.getByRole('button', { name: 'Send' }).props.accessibilityState).toMatchObject({ disabled: true });
    fireEvent.press(screen.getByRole('button', { name: 'Send' }));
    await flush();
    expect(calls.filter((c) => c.method === 'POST')).toEqual([]);
  });

  it('keeps the text and says why when a post fails', async () => {
    const w = world();
    await open(CONCERN_THREAD, w);
    await type('Lost?');
    w.threads.fail(503);
    await press('Send');
    expect(screen.getByText(/It was not posted. The threads service could not answer/)).toBeTruthy();
    expect(screen.getByLabelText('Message the thread').props.value).toBe('Lost?');
  });

  it('watches the thread, and stops watching it', async () => {
    const w = world();
    seedConcernThread(w.threads);
    const { calls } = await open(CONCERN_THREAD, w);
    await press('Watch');
    expect(screen.getByTestId('watchers')).toHaveTextContent('Watching: ben, ana');
    expect(screen.getByRole('button', { name: 'Watching' }).props.accessibilityState).toMatchObject({ selected: true });
    await press('Watching');
    expect(screen.getByTestId('watchers')).toHaveTextContent('Watching: ben');
    expect(threadCalls(calls).filter((c) => c.includes('watchers'))).toEqual([
      'PUT /projects/example/reports/loops/report-pipeline/concerns/queue/thread/watchers/me',
      'DELETE /projects/example/reports/loops/report-pipeline/concerns/queue/thread/watchers/me',
    ]);
  });

  it('says so when the person is not a member of the project, and shows nothing of the thread', async () => {
    const w = world();
    seedConcernThread(w.threads);
    await open(CONCERN_THREAD, w, { as: 'carol' });
    expect(screen.getByText(/You are not a member of example\/reports, so its threads are closed to you/)).toBeTruthy();
    expect(screen.queryAllByTestId(/^message-\d+$/)).toEqual([]);
    expect(screen.queryByTestId('members')).toBeNull();
  });

  it('says the build has no threads URL instead of calling the service', async () => {
    const w = world();
    const { calls } = await open(CONCERN_THREAD, w, { config: configWith({ threadsUrl: null }) });
    expect(screen.getByText(/This build has no URL for the threads service yet/)).toBeTruthy();
    expect(screen.getByText(/EXPO_PUBLIC_THREADS_URL/)).toBeTruthy();
    expect(calls.filter((c) => c.service === 'threads')).toEqual([]);
  });

  it('reads again when pulled down, and keeps the earlier copy, saying so, if that read fails', async () => {
    const w = world();
    const seeded = seedConcernThread(w.threads);
    await open(CONCERN_THREAD, w);
    w.threads.seed(w.threads.paths.concern('report-pipeline', 'queue'), [{ body: 'A new one', author: person('ben') }]);
    await act(async () => {
      screen.getByTestId('thread-history').props.refreshControl.props.onRefresh();
    });
    await flush();
    expect(screen.getByText('A new one')).toBeTruthy();

    w.threads.fail(503);
    await act(async () => {
      screen.getByTestId('thread-history').props.refreshControl.props.onRefresh();
    });
    await flush();
    expect(screen.getByText(/could not be read again, so this is the earlier copy/)).toBeTruthy();
    expect(screen.getByText(seeded[0]!.body)).toBeTruthy();
  });

  it("opens from the Concern page's thread link, at the path app-loops-board links to (command-center/D52)", async () => {
    const w = world();
    seedConcernThread(w.threads);
    const result = await open('/loops/report-pipeline/concerns/queue', w);
    fireEvent.press(screen.getByRole('link', { name: 'Concern thread' }));
    await flush();
    expect(result.getPathname()).toBe(CONCERN_THREAD);
    expect(screen.getByText('Five tries, then the dead-letter queue.')).toBeTruthy();
    await press('Back to queue');
    expect(result.getPathname()).toBe('/loops/report-pipeline/concerns/queue');
  });

  it('goes back to the concern page when it was opened with nothing behind it', async () => {
    const w = world();
    const result = await open(CONCERN_THREAD, w);
    await press('Back to queue');
    expect(result.getPathname()).toBe('/loops/report-pipeline/concerns/queue');
  });
});

describe('a loop thread (C1)', () => {
  it('reads and posts to the loop thread at /threads/loops/[loop]', async () => {
    const w = world();
    const [first] = w.threads.seed(w.threads.paths.loop('report-pipeline'), [{ body: 'Kick-off notes', author: person('ana') }]);
    const { calls } = await open(LOOP_THREAD, w, { as: 'ben' });
    expect(screen.getByText('Loop thread')).toBeTruthy();
    expect(drawnIds()).toEqual([first!.id]);
    await type('Thanks');
    await press('Send');
    expect(threadCalls(calls)).toEqual([
      'GET /projects/example/reports/loops/report-pipeline/thread',
      'GET /projects/example/reports/loops/report-pipeline/thread/messages?after=0&limit=500',
      'POST /projects/example/reports/loops/report-pipeline/thread/messages',
    ]);
    expect(screen.getByText('Thanks')).toBeTruthy();
  });
});

function seedSessionThread(threads: ReturnType<typeof fakeThreads>) {
  const session = { type: 'session' as const, session: SESSION_ID, sponsor: 'ana' };
  return threads.seed(threads.paths.session(SESSION_ID), [
    { kind: 'milestone', body: 'Started loop-build on report-pipeline/queue.', author: session },
    { kind: 'narration', body: 'Reading the concern file.', author: session },
    { kind: 'narration', body: 'Reading LOOP.md.', author: session },
    { kind: 'narration', body: 'Looking at worker/retry.py.', author: session },
    { kind: 'milestone', body: 'Opened branch report-pipeline/queue.', author: session },
    { kind: 'narration', body: 'Writing the retry test first.', author: session },
    { kind: 'milestone', body: 'Tests run: 42 of 42 pass.', author: session },
    { body: 'Keep the dead-letter queue out of this PR.', author: person('ben') },
    { body: 'Understood: the dead-letter queue stays out.', author: session },
  ]);
}

describe('a session thread (C1)', () => {
  it('collapses narration to its milestones, and opens a run of it on request', async () => {
    const w = world();
    w.runner.add(fakeSession({ id: SESSION_ID }));
    const seeded = seedSessionThread(w.threads);
    await open(SESSION_THREAD, w);

    const milestones = seeded.filter((m) => m.kind === 'milestone');
    for (const m of milestones) expect(screen.getByText(m.body)).toBeTruthy();
    expect(screen.getByText('Keep the dead-letter queue out of this PR.')).toBeTruthy();
    for (const m of seeded.filter((m) => m.kind === 'narration')) expect(screen.queryByText(m.body)).toBeNull();
    expect(screen.getByRole('button', { name: 'Show 3 narration lines' })).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Show 1 narration line' })).toBeTruthy();

    await press('Show 3 narration lines');
    expect(screen.getByText('Reading the concern file.')).toBeTruthy();
    expect(screen.getByText('Looking at worker/retry.py.')).toBeTruthy();
    expect(screen.queryByText('Writing the retry test first.')).toBeNull();
    await press('Hide narration');
    expect(screen.queryByText('Reading the concern file.')).toBeNull();

    // Everything else is drawn in seq order, milestones as lines and messages as bubbles.
    expect(drawnIds()).toEqual(seeded.filter((m) => m.kind !== 'narration').map((m) => m.id));
    // A session's own message names its sponsor.
    expect(within(screen.getByTestId(`message-${seeded[8]!.id}`)).getByText(/the session/)).toBeTruthy();
    expect(within(screen.getByTestId(`message-${seeded[8]!.id}`)).getByText(/sponsored by ana/)).toBeTruthy();
  });

  it('names the session from the runner: its skill, what it runs on, its sponsor, and its spend as an estimate', async () => {
    const w = world();
    w.runner.add(
      fakeSession({
        id: SESSION_ID,
        spend: {
          kind: 'estimate',
          basis: 'per-step usage',
          usd: 1.1,
          overshoot_usd: null,
          tokens: { input: 1, output: 1, cache_creation: 0, cache_read: 0 },
          wall_clock_s: 600,
          as_of: at(20),
        },
      }),
    );
    seedSessionThread(w.threads);
    const { calls } = await open(SESSION_THREAD, w);
    expect(screen.getByTestId('session-title')).toHaveTextContent('loop-build on report-pipeline/queue');
    expect(screen.getByText('sponsored by ana · running')).toBeTruthy();
    expect(screen.getByText('$1.10 spent, an estimate')).toBeTruthy();
    expect(screen.getByText('budget $2.50')).toBeTruthy();
    expect(calls.filter((c) => c.service === 'runner').map((c) => `${c.method} ${c.path}`)).toEqual([`GET /sessions/${SESSION_ID}`]);
    expect(screen.getByLabelText('Message the thread').props.placeholder).toBe('Redirect the agent');
  });

  it('still shows the thread when the build has no runner URL, naming the session by its id and the thread’s sponsor', async () => {
    const w = world();
    const seeded = seedSessionThread(w.threads);
    await open(SESSION_THREAD, w, { config: configWith({ runnerUrl: null }) });
    expect(screen.getByTestId('session-title')).toHaveTextContent('Session a1b2c3d4');
    expect(screen.getByText('sponsored by ana')).toBeTruthy();
    expect(screen.getByText(/This build has no URL for the runner service yet/)).toBeTruthy();
    expect(screen.getByText(seeded[0]!.body)).toBeTruthy();
  });

  it('posts a member’s redirect to the session thread, as the member', async () => {
    const w = world();
    w.runner.add(fakeSession({ id: SESSION_ID }));
    seedSessionThread(w.threads);
    const { calls } = await open(SESSION_THREAD, w, { as: 'ben' });
    await type('Stop after the tests pass.');
    await press('Send');
    const post = calls.find((c) => c.method === 'POST')!;
    expect(post.path).toBe(`/projects/example/reports/sessions/${SESSION_ID}/thread/messages`);
    expect(post.body).toEqual({ body: 'Stop after the tests pass.' });
    expect(post.auth).toBe('Bearer gho_ben');
  });

  it('goes back to the Agents tab when it was opened with nothing behind it', async () => {
    const w = world();
    const result = await open(SESSION_THREAD, w);
    await press('Back to Agents');
    expect(result.getPathname()).toBe('/agents');
  });
});

describe('"record this?" (C2)', () => {
  it('lets any member mark a message and take the mark back, and leaves accepting it to the loop’s owner', async () => {
    const w = world();
    const seeded = seedConcernThread(w.threads);
    const { calls } = await open(CONCERN_THREAD, w, { as: 'ben' });
    const bubble = () => within(screen.getByTestId(`message-${seeded[2]!.id}`));

    await press('Record this?', bubble());
    expect(bubble().getByText('Record this? · marked by ben')).toBeTruthy();
    expect(bubble().getByText("ana records it, as the loop's owner.")).toBeTruthy();
    expect(bubble().queryByRole('button', { name: 'Record it…' })).toBeNull();

    await press('Unmark', bubble());
    expect(bubble().queryByText(/marked by/)).toBeNull();
    expect(threadCalls(calls).filter((c) => c.includes('record-marks'))).toEqual([
      `PUT /projects/example/reports/messages/${seeded[2]!.id}/record-marks/me`,
      `DELETE /projects/example/reports/messages/${seeded[2]!.id}/record-marks/me`,
    ]);
    // A mark is a note to people: nothing was dispatched.
    expect(w.runner.dispatched).toEqual([]);
  });

  it('offers no mark on a session’s milestones or narration, only on what is written to people', async () => {
    const w = world();
    w.runner.add(fakeSession({ id: SESSION_ID }));
    const seeded = seedSessionThread(w.threads);
    await open(SESSION_THREAD, w);
    expect(within(screen.getByTestId(`message-${seeded[0]!.id}`)).queryByRole('button', { name: 'Record this?' })).toBeNull();
    expect(within(screen.getByTestId(`message-${seeded[7]!.id}`)).getByRole('button', { name: 'Record this?' })).toBeTruthy();
    expect(within(screen.getByTestId(`message-${seeded[8]!.id}`)).getByRole('button', { name: 'Record this?' })).toBeTruthy();
  });

  it('lets the owner accept a marked message: /loop-design on the concern, sponsored by them, then its thread opens', async () => {
    const w = world();
    const seeded = seedConcernThread(w.threads);
    const decision = seeded[2]!;
    const result = await open(CONCERN_THREAD, w, { as: 'ben' });
    await press('Record this?', within(screen.getByTestId(`message-${decision.id}`)));
    result.unmount();

    const { calls, getPathname } = await open(CONCERN_THREAD, w, { as: 'ana' });
    const bubble = within(screen.getByTestId(`message-${decision.id}`));
    expect(bubble.getByText('Record this? · marked by ben')).toBeTruthy();
    await press('Record it…', bubble);

    const sheet = within(screen.getByTestId('record-sheet'));
    expect(sheet.getByText(/\/loop-design report-pipeline\/queue/)).toBeTruthy();
    expect(sheet.getByText(/as a session you sponsor \(ana\)/)).toBeTruthy();
    expect(sheet.getByLabelText('Budget in dollars').props.value).toBe('2');
    expect(sheet.getByLabelText('Skills release').props.value).toBe(SKILLS_RELEASE);
    expect(sheet.getByTestId('estimate')).toHaveTextContent(
      "Estimate: about $0.84, the median of loop-design's last 7 sessions on claude-test.",
    );
    // Nothing starts until the owner says so.
    expect(w.runner.dispatched).toEqual([]);

    await press('Start /loop-design', sheet);
    const dispatch = calls.find((c) => c.service === 'runner' && c.method === 'POST')!;
    expect(dispatch.path).toBe('/sessions');
    expect(dispatch.auth).toBe('Bearer gho_ana');
    expect(dispatch.body).toEqual({
      project: 'example/reports',
      skill: 'loop-design',
      concern: 'report-pipeline/queue',
      arguments: expect.stringContaining(`message ${decision.id}, written by ana`),
      budget_usd: 2,
      plugin_release: SKILLS_RELEASE,
    });
    const args = (dispatch.body as { arguments: string }).arguments;
    expect(args).toContain('marked "record this?" by ben');
    expect(args).toContain('It says: Five tries, then the dead-letter queue.');
    expect(args).toContain('the concern thread');

    // The new session's thread opens, sponsored by the person who accepted.
    const started = [...w.runner.sessions.values()][0]!;
    expect(started.sponsor).toBe('ana');
    expect(getPathname()).toBe(`/threads/sessions/${started.id}`);
    expect(screen.getByTestId('session-title')).toHaveTextContent('loop-design on report-pipeline/queue');
  });

  it("shows the runner's refusal, naming what holds the concern, and opens nothing", async () => {
    const w = world();
    seedConcernThread(w.threads);
    w.runner.refuse({
      refused: 'open-pull-request',
      message: 'report-pipeline/queue has an open pull request, so loop-design cannot hold it.',
      pull_requests: [{ number: 61, url: 'https://github.com/example/reports/pull/61', head: 'report-pipeline/queue' }],
      sessions: [],
    });
    const markedOnServer = w.threads.seed(w.threads.paths.concern('report-pipeline', 'queue'), [
      { body: 'Dead letters after five.', author: person('ben'), record_marks: [{ login: 'ben', marked_at: at(16) }] },
    ])[0]!;
    const { getPathname } = await open(CONCERN_THREAD, w, { as: 'ana' });
    await press('Record it…', within(screen.getByTestId(`message-${markedOnServer.id}`)));
    await press('Start /loop-design', within(screen.getByTestId('record-sheet')));
    expect(screen.getByText(/has an open pull request, so loop-design cannot hold it. Open: #61./)).toBeTruthy();
    expect(getPathname()).toBe(CONCERN_THREAD);
    expect(w.runner.sessions.size).toBe(0);
  });

  it('starts with the budget and release the owner typed, and not with a budget that is not a number', async () => {
    const w = world();
    const [marked] = w.threads.seed(w.threads.paths.concern('report-pipeline', 'queue'), [
      { body: 'Retry five times.', author: person('ben'), record_marks: [{ login: 'ben', marked_at: at(1) }] },
    ]);
    await open(CONCERN_THREAD, w, { as: 'ana' });
    await press('Record it…', within(screen.getByTestId(`message-${marked!.id}`)));
    const sheet = () => within(screen.getByTestId('record-sheet'));

    fireEvent.changeText(sheet().getByLabelText('Budget in dollars'), 'lots');
    await flush();
    expect(sheet().getByText('The budget must be a number of dollars above 0.')).toBeTruthy();
    expect(sheet().getByRole('button', { name: 'Start /loop-design' }).props.accessibilityState).toMatchObject({ disabled: true });
    fireEvent.press(sheet().getByRole('button', { name: 'Start /loop-design' }));
    await flush();
    expect(w.runner.dispatched).toEqual([]);

    fireEvent.changeText(sheet().getByLabelText('Budget in dollars'), '$3.50');
    fireEvent.changeText(sheet().getByLabelText('Skills release'), 'v0.3.0');
    await flush();
    await press('Start /loop-design', sheet());
    expect(w.runner.dispatched).toEqual([expect.objectContaining({ budget_usd: 3.5, plugin_release: 'v0.3.0' })]);
  });

  it('closes the sheet on Cancel, and starts nothing', async () => {
    const w = world();
    const [marked] = w.threads.seed(w.threads.paths.concern('report-pipeline', 'queue'), [
      { body: 'Retry five times.', author: person('ben'), record_marks: [{ login: 'ben', marked_at: at(1) }] },
    ]);
    await open(CONCERN_THREAD, w, { as: 'ana' });
    await press('Record it…', within(screen.getByTestId(`message-${marked!.id}`)));
    await press('Cancel', within(screen.getByTestId('record-sheet')));
    expect(screen.queryByTestId('record-sheet')).toBeNull();
    expect(screen.getByLabelText('Message the thread')).toBeTruthy();
    expect(w.runner.dispatched).toEqual([]);
  });

  it('records into the loop from a loop thread', async () => {
    const w = world();
    const [marked] = w.threads.seed(w.threads.paths.loop('report-pipeline'), [
      { body: 'Every worker logs to one place.', author: person('ben'), record_marks: [{ login: 'ben', marked_at: at(1) }] },
    ]);
    await open(LOOP_THREAD, w, { as: 'ana' });
    await press('Record it…', within(screen.getByTestId(`message-${marked!.id}`)));
    expect(within(screen.getByTestId('record-sheet')).getByText(/\/loop-design report-pipeline\b/)).toBeTruthy();
    await press('Start /loop-design', within(screen.getByTestId('record-sheet')));
    expect(w.runner.dispatched).toEqual([expect.objectContaining({ skill: 'loop-design', loop: 'report-pipeline' })]);
    expect(w.runner.dispatched[0]).not.toHaveProperty('concern');
  });

  it("records into the session's concern from a session thread, with its owner read through the session's loop", async () => {
    const w = world();
    w.runner.add(fakeSession({ id: SESSION_ID }));
    const seeded = seedSessionThread(w.threads);
    const redirect = seeded[7]!;
    redirect.record_marks.push({ login: 'ben', marked_at: at(40) });
    await open(SESSION_THREAD, w, { as: 'ana' });
    await press('Record it…', within(screen.getByTestId(`message-${redirect.id}`)));
    await press('Start /loop-design', within(screen.getByTestId('record-sheet')));
    expect(w.runner.dispatched).toEqual([
      expect.objectContaining({ skill: 'loop-design', concern: 'report-pipeline/queue' }),
    ]);
    expect(w.runner.dispatched[0]!.arguments).toContain(`the session thread of session ${SESSION_ID}`);
  });

  it("says why it cannot be recorded when the loop's owner cannot be read", async () => {
    const w = world();
    const [marked] = w.threads.seed(w.threads.paths.concern('report-pipeline', 'queue'), [
      { body: 'Retry five times.', author: person('ben'), record_marks: [{ login: 'ben', marked_at: at(1) }] },
    ]);
    await open(CONCERN_THREAD, w, { as: 'ana', config: configWith({ statusUrl: null }) });
    const bubble = within(screen.getByTestId(`message-${marked!.id}`));
    expect(bubble.getByText(/Only the loop's owner can record it. This build has no status service URL/)).toBeTruthy();
    expect(bubble.queryByRole('button', { name: 'Record it…' })).toBeNull();
  });

  it('keeps a long message within the runner’s limit on arguments', async () => {
    const w = world();
    const [marked] = w.threads.seed(w.threads.paths.concern('report-pipeline', 'queue'), [
      { body: 'x'.repeat(5000), author: person('ben'), record_marks: [{ login: 'ben', marked_at: at(1) }] },
    ]);
    await open(CONCERN_THREAD, w, { as: 'ana' });
    await press('Record it…', within(screen.getByTestId(`message-${marked!.id}`)));
    await press('Start /loop-design', within(screen.getByTestId('record-sheet')));
    const args = w.runner.dispatched[0]!.arguments!;
    expect(args.length).toBeLessThanOrEqual(MAX_ARGUMENTS);
    expect(args).toContain(`[cut to fit; the whole text is message ${marked!.id}]`);
  });
});
