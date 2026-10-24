// command-center/app-agents C1 and C2, the screen: against a fake runner, through the real generated client and the
// signed-in fetch, and the status fixtures. C1: every running session with its skill, concern, sponsor, elapsed time
// and spend against budget, read again within 10 seconds, and a sponsor stops their own session and nobody else's.
// C2: "Can start now" lists the ready, shipped and stale concerns, each with Start, the runner's estimate and a
// budget, and nothing is dispatched until the person confirms; the dispatch is sent as them, so the runner makes
// them the sponsor.

import { act, fireEvent, render, screen, within } from '@testing-library/react-native';

import { createSignedInFetch } from '../../../api/fetch';
import { createRunnerClient, type RunnerClient, type Session } from '../../../api/runner.gen';
import { StatusError, type StatusClient } from '../../../api/status';
import { createFixtureStatusClient } from '../../../api/statusFixtures';
import { AgentsScreen, BUDGET_NOTE, NO_STATUS_SERVICE_MESSAGE } from '../AgentsScreen';
import { REFRESH_MS } from '../sessions';
import { FAKE_RELEASE, fakeRunner, RUNNER_URL, session, type FakeRunnerOptions } from './fakeRunner';

const NOW = Date.parse('2026-10-24T12:00:00Z');

/** octocat's build, 18 minutes in, and hubot's proof, 6 minutes in. */
function twoSessions(): Session[] {
  return [
    session({ sponsor: 'octocat', skill: 'loop-build', concern: 'report-pipeline/retries', budget_usd: 2.5 }),
    session({
      sponsor: 'hubot',
      skill: 'loop-prove',
      concern: 'report-pipeline/queue',
      arguments: 'staging',
      budget_usd: 1,
      started_at: '2026-10-24T11:54:00Z',
      spend: { ...session().spend!, usd: 0.3 },
    }),
  ];
}

function runnerFor(fake: ReturnType<typeof fakeRunner>, token = 'gho_octocat'): RunnerClient {
  const fetch = createSignedInFetch({ getToken: () => token, onUnauthorized: () => {}, fetch: fake.fetch });
  return createRunnerClient({ baseUrl: RUNNER_URL, fetch });
}

let clock = NOW;

async function flush() {
  for (let i = 0; i < 4; i++) {
    await act(async () => {
      await jest.advanceTimersByTimeAsync(0);
    });
  }
}

async function shown(
  options: FakeRunnerOptions = {},
  {
    status = createFixtureStatusClient('board'),
    runner,
  }: { status?: StatusClient | null; runner?: RunnerClient | null } = {},
) {
  const fake = fakeRunner(options);
  const client = runner === undefined ? runnerFor(fake) : runner;
  const view = render(
    <AgentsScreen runner={client} status={status} login="octocat" project="example/reports" now={() => clock} />,
  );
  await flush();
  return { fake, client, view };
}

/** Every string a part of the screen draws, joined, so a test can read a card as a person does. */
function textIn(testID: string): string {
  return screen
    .getByTestId(testID)
    // Host nodes only: each Text is also a composite node with the same children.
    .findAll((node) => typeof node.type === 'string' && typeof node.props.children === 'string')
    .map((node) => String(node.props.children))
    .join(' | ');
}

const sessionCards = () => screen.queryAllByTestId(/^session-/);

beforeEach(() => {
  jest.useFakeTimers();
  clock = NOW;
});

afterEach(() => {
  jest.useRealTimers();
});

describe('the running sessions (C1)', () => {
  it('lists every running session with its skill, concern, sponsor, elapsed time and spend against budget', async () => {
    const sessions = twoSessions();
    await shown({ sessions });
    expect(sessionCards()).toHaveLength(2);

    const build = textIn(`session-${sessions[0]!.id}`);
    expect(build).toContain('loop-build · report-pipeline/retries');
    expect(build).toContain('sponsor octocat (you) · 18 min');
    expect(build).toContain('est. $1.10 / $2.50');

    const proof = textIn(`session-${sessions[1]!.id}`);
    expect(proof).toContain('loop-prove · report-pipeline/queue');
    expect(proof).toContain('sponsor hubot · 6 min');
    expect(proof).toContain('est. $0.30 / $1.00');

    expect(screen.getByLabelText('estimated spend $1.10 of a $2.50 budget')).toBeTruthy();
    expect(screen.getByTestId('agents-overline')).toHaveTextContent('2 running · est. $1.40 so far');
    expect(screen.getByTestId('agents-slots')).toHaveTextContent('You sponsor 1 of your 3 session slots.');
    expect(screen.getByTestId('sessions-read')).toHaveTextContent('read just now');
  });

  it('asks the runner for the active sessions as the signed-in person', async () => {
    const { fake } = await shown({ sessions: twoSessions() });
    const [first] = fake.callsTo('GET', '/sessions');
    expect(first).toMatchObject({ query: { state: 'active' }, auth: 'Bearer gho_octocat' });
  });

  it('reads the sessions again within 10 seconds, so a new spend and a new session show without a pull', async () => {
    const sessions = twoSessions();
    const { fake } = await shown({ sessions });
    expect(fake.callsTo('GET', '/sessions')).toHaveLength(1);

    // The runner publishes a new spend and a new session, as its jobs do at least every 10 seconds (D23).
    fake.state.sessions[0] = { ...fake.state.sessions[0]!, spend: { ...fake.state.sessions[0]!.spend!, usd: 1.6 } };
    fake.state.sessions.push(session({ sponsor: 'hubot', skill: 'loop-status', concern: null, loop: 'search' }));
    clock += REFRESH_MS;
    await act(async () => {
      await jest.advanceTimersByTimeAsync(REFRESH_MS);
    });
    await flush();

    expect(REFRESH_MS).toBeLessThan(10_000);
    expect(fake.callsTo('GET', '/sessions')).toHaveLength(2);
    expect(textIn(`session-${sessions[0]!.id}`)).toContain('est. $1.60 / $2.50');
    expect(sessionCards()).toHaveLength(3);
    expect(screen.getByText('loop-status · search')).toBeTruthy();
  });

  it('drops a session once the runner says it has ended', async () => {
    const sessions = twoSessions();
    const { fake } = await shown({ sessions });
    fake.state.sessions[1] = { ...fake.state.sessions[1]!, state: 'ended', outcome: 'completed', ended_at: '2026-10-24T12:00:03Z' };
    await act(async () => {
      await jest.advanceTimersByTimeAsync(REFRESH_MS);
    });
    await flush();
    expect(sessionCards()).toHaveLength(1);
    expect(screen.queryByText('loop-prove · report-pipeline/queue')).toBeNull();
  });

  it('reads the runner only while the tab is in front, and at once when it comes back', async () => {
    const fake = fakeRunner({ sessions: twoSessions() });
    const runner = runnerFor(fake);
    const status = createFixtureStatusClient('board');
    const view = render(<AgentsScreen runner={runner} status={status} login="octocat" project="example/reports" now={() => clock} />);
    await flush();
    expect(fake.callsTo('GET', '/sessions')).toHaveLength(1);

    view.rerender(<AgentsScreen runner={runner} status={status} login="octocat" project="example/reports" now={() => clock} active={false} />);
    await act(async () => {
      await jest.advanceTimersByTimeAsync(6 * REFRESH_MS);
    });
    expect(fake.callsTo('GET', '/sessions')).toHaveLength(1);

    view.rerender(<AgentsScreen runner={runner} status={status} login="octocat" project="example/reports" now={() => clock} active />);
    await flush();
    expect(fake.callsTo('GET', '/sessions')).toHaveLength(2);
  });

  it('says no session is running when none is', async () => {
    await shown();
    expect(screen.getByText('No session is running.')).toBeTruthy();
    expect(screen.getByTestId('agents-overline')).toHaveTextContent('0 running · est. $0.00 so far');
  });

  it('shows the failure, and no session, when the runner cannot be read; Try again reads it again', async () => {
    let fail = true;
    const { fake } = await shown({
      sessions: twoSessions(),
      answer: (call) => (fail && call.path === '/sessions' ? { status: 502, body: { error: 'upstream-failed', message: 'GitHub is down' } } : undefined),
    });
    expect(screen.getByText('The runner could not be read, so no session is shown.')).toBeTruthy();
    expect(screen.getByText(/answered 502: GitHub is down/)).toBeTruthy();
    expect(sessionCards()).toHaveLength(0);

    fail = false;
    await act(async () => {
      fireEvent.press(screen.getByRole('button', { name: 'Try again' }));
    });
    await flush();
    expect(fake.callsTo('GET', '/sessions').length).toBeGreaterThanOrEqual(2);
    expect(sessionCards()).toHaveLength(2);
  });

  it('keeps the last list when a later read fails, and says how old it is', async () => {
    let fail = false;
    await shown({
      sessions: twoSessions(),
      answer: (call) => (fail && call.path === '/sessions' ? { status: 502, body: { error: 'upstream-failed', message: 'GitHub is down' } } : undefined),
    });
    fail = true;
    clock += 12_000;
    await act(async () => {
      await jest.advanceTimersByTimeAsync(REFRESH_MS);
    });
    await flush();
    expect(sessionCards()).toHaveLength(2);
    expect(screen.getByRole('alert')).toHaveTextContent(
      /^The runner could not be read again, so this is the list as it was read 12 s ago: .*GitHub is down$/,
    );
  });

  it('says so, and shows no session, when the build has no runner URL', async () => {
    await shown({}, { runner: null });
    expect(screen.getAllByText(/This build has no URL for the runner service yet/).length).toBeGreaterThan(0);
    expect(sessionCards()).toHaveLength(0);
  });
});

describe('stopping a session (C1)', () => {
  it("offers Stop on the person's own sessions only", async () => {
    const sessions = twoSessions();
    await shown({ sessions });
    expect(within(screen.getByTestId(`session-${sessions[0]!.id}`)).getByRole('button', { name: 'Stop' })).toBeTruthy();
    expect(within(screen.getByTestId(`session-${sessions[1]!.id}`)).queryByRole('button', { name: 'Stop' })).toBeNull();
  });

  it('stops the sponsor’s session after they confirm, as them, and shows it stopping', async () => {
    const sessions = twoSessions();
    const { fake } = await shown({ sessions });
    const card = () => within(screen.getByTestId(`session-${sessions[0]!.id}`));
    fireEvent.press(card().getByRole('button', { name: 'Stop' }));
    expect(card().getByText(/Stop this session\?/)).toBeTruthy();
    expect(fake.callsTo('POST', /\/stop$/)).toHaveLength(0);

    await act(async () => {
      fireEvent.press(card().getByRole('button', { name: 'Stop it' }));
    });
    await flush();
    const stops = fake.callsTo('POST', /\/stop$/);
    expect(stops).toEqual([expect.objectContaining({ path: `/sessions/${sessions[0]!.id}/stop`, auth: 'Bearer gho_octocat' })]);
    expect(card().getByText('STOPPING')).toBeTruthy();
    expect(card().queryByRole('button', { name: 'Stop' })).toBeNull();
  });

  it('keeps the session running when the sponsor thinks better of it', async () => {
    const sessions = twoSessions();
    const { fake } = await shown({ sessions });
    const card = () => within(screen.getByTestId(`session-${sessions[0]!.id}`));
    fireEvent.press(card().getByRole('button', { name: 'Stop' }));
    fireEvent.press(card().getByRole('button', { name: 'Keep running' }));
    expect(card().getByRole('button', { name: 'Stop' })).toBeTruthy();
    expect(fake.callsTo('POST', /\/stop$/)).toHaveLength(0);
  });

  it('says why when the runner does not stop it', async () => {
    const sessions = twoSessions();
    await shown({
      sessions,
      answer: (call) =>
        call.path.endsWith('/stop') ? { status: 409, body: { error: 'already-ended', message: 'it has already ended (completed)' } } : undefined,
    });
    const card = () => within(screen.getByTestId(`session-${sessions[0]!.id}`));
    fireEvent.press(card().getByRole('button', { name: 'Stop' }));
    await act(async () => {
      fireEvent.press(card().getByRole('button', { name: 'Stop it' }));
    });
    await flush();
    expect(card().getByRole('alert')).toHaveTextContent(/It was not stopped: .*answered 409: it has already ended \(completed\)/);
    expect(card().getByRole('button', { name: 'Stop' })).toBeTruthy();
  });
});

describe('can start now (C2)', () => {
  const ESTIMATES: FakeRunnerOptions['estimates'] = {
    'loop-build': { usd: 1.6, wall_clock_s: 14 * 60, sessions: 7 },
    'loop-prove': null,
  };

  it('lists the ready, shipped and stale concerns, each with its button and the runner’s estimate', async () => {
    const { fake } = await shown({ estimates: ESTIMATES });
    expect(textIn('start-report-pipeline/exporter-build')).toBe('report-pipeline/exporter is ready | build · est. $1.60 | Start');
    expect(textIn('start-search/indexer-build')).toContain('search/indexer is ready');
    expect(textIn('start-report-pipeline/queue-prove')).toBe(
      'report-pipeline/queue is shipped | prove on staging · no estimate yet | Prove',
    );
    expect(textIn('start-report-pipeline/metrics-prove')).toBe(
      'report-pipeline/metrics is stale | re-prove on staging · no estimate yet | Re-prove',
    );
    // A design is left out: its session would ask the owner questions it cannot reach.
    expect(screen.queryByTestId(/^start-search\/ranking/)).toBeNull();
    // One estimate per skill, asked as the person.
    expect(fake.callsTo('GET', '/estimates').map((c) => [c.query.skill, c.auth])).toEqual([
      ['loop-build', 'Bearer gho_octocat'],
      ['loop-prove', 'Bearer gho_octocat'],
    ]);
  });

  it('shows the estimate and a budget, and dispatches nothing until the person confirms', async () => {
    const { fake } = await shown({ estimates: ESTIMATES });
    fireEvent.press(screen.getByRole('button', { name: 'Start report-pipeline/exporter' }));
    const confirmation = within(screen.getByTestId('start-confirmation'));
    expect(confirmation.getByText('/loop-build report-pipeline/exporter')).toBeTruthy();
    expect(confirmation.getByTestId('start-estimate')).toHaveTextContent(
      'Estimated $1.60 and 14 min: the median of the last 7 sessions of loop-build on claude-opus-5-5.',
    );
    expect(confirmation.getByLabelText('Budget in dollars').props.value).toBe('2');
    expect(confirmation.getByText(BUDGET_NOTE)).toBeTruthy();
    expect(confirmation.getByText(`Sponsored by you, octocat. It runs the skills of release ${FAKE_RELEASE}.`)).toBeTruthy();
    expect(fake.callsTo('POST', '/sessions')).toHaveLength(0);

    fireEvent.press(confirmation.getByRole('button', { name: 'Cancel' }));
    expect(screen.queryByTestId('start-confirmation')).toBeNull();
    expect(fake.callsTo('POST', '/sessions')).toHaveLength(0);
  });

  it('starts the concern with the confirmed budget, as the person, who the runner makes its sponsor', async () => {
    const { fake } = await shown({ estimates: ESTIMATES });
    fireEvent.press(screen.getByRole('button', { name: 'Start report-pipeline/exporter' }));
    fireEvent.changeText(screen.getByLabelText('Budget in dollars'), '3.50');
    await act(async () => {
      fireEvent.press(screen.getByRole('button', { name: 'Start with a $3.50 budget' }));
    });
    await flush();

    const [dispatch] = fake.callsTo('POST', '/sessions');
    expect(dispatch?.auth).toBe('Bearer gho_octocat');
    expect(dispatch?.body).toEqual({
      project: 'example/reports',
      skill: 'loop-build',
      concern: 'report-pipeline/exporter',
      budget_usd: 3.5,
      plugin_release: FAKE_RELEASE,
    });
    expect(fake.callsTo('POST', '/sessions')).toHaveLength(1);

    const started = fake.state.sessions[0]!;
    expect(started.sponsor).toBe('octocat');
    expect(screen.queryByTestId('start-confirmation')).toBeNull();
    expect(screen.getByText(`Started session ${started.id.slice(0, 7)}, sponsored by octocat, with a $3.50 budget.`)).toBeTruthy();
    // The list is read again at once, and shows the new session starting, sponsored by the person.
    const card = textIn(`session-${started.id}`);
    expect(card).toContain('loop-build · report-pipeline/exporter');
    expect(card).toContain('STARTING');
    expect(card).toContain('sponsor octocat (you)');
    expect(card).toContain('no spend yet / $3.50');
    // And its row now says it is running, so it is not started twice.
    expect(textIn('start-report-pipeline/exporter-build')).toContain('running · octocat');
    expect(screen.queryByRole('button', { name: 'Start report-pipeline/exporter' })).toBeNull();
  });

  it('passes a proof its environment, as the status document’s command does', async () => {
    const { fake } = await shown({ estimates: ESTIMATES });
    fireEvent.press(screen.getByRole('button', { name: 'Re-prove report-pipeline/metrics' }));
    fireEvent.changeText(screen.getByLabelText('Budget in dollars'), '1');
    await act(async () => {
      fireEvent.press(screen.getByRole('button', { name: 'Start with a $1.00 budget' }));
    });
    await flush();
    expect(fake.callsTo('POST', '/sessions')[0]?.body).toMatchObject({
      skill: 'loop-prove',
      concern: 'report-pipeline/metrics',
      arguments: 'staging',
      budget_usd: 1,
    });
  });

  it('asks for a budget where there is no estimate, and will not start without a valid one', async () => {
    const { fake } = await shown({ estimates: ESTIMATES });
    fireEvent.press(screen.getByRole('button', { name: 'Prove report-pipeline/queue' }));
    const confirmation = () => within(screen.getByTestId('start-confirmation'));
    expect(confirmation().getByTestId('start-estimate')).toHaveTextContent(
      'No estimate yet: no loop-prove session on claude-opus-5-5 has been measured. Set the budget yourself.',
    );
    expect(confirmation().getByLabelText('Budget in dollars').props.value).toBe('');
    expect(confirmation().getByText('Set a budget for the session.')).toBeTruthy();

    const start = () => confirmation().getByRole('button', { name: 'Start' });
    expect(start().props.accessibilityState).toMatchObject({ disabled: true });
    fireEvent.press(start());
    fireEvent.changeText(confirmation().getByLabelText('Budget in dollars'), 'lots');
    expect(confirmation().getByText('A budget is an amount in dollars, such as 2 or 2.50.')).toBeTruthy();
    fireEvent.press(start());
    fireEvent.changeText(confirmation().getByLabelText('Budget in dollars'), '0');
    fireEvent.press(start());
    await flush();
    expect(fake.callsTo('POST', '/sessions')).toHaveLength(0);
  });

  it("shows the runner's refusal, starts nothing, and keeps the confirmation open", async () => {
    const { fake } = await shown({ estimates: ESTIMATES, ceiling: 10 });
    fireEvent.press(screen.getByRole('button', { name: 'Start report-pipeline/exporter' }));
    fireEvent.changeText(screen.getByLabelText('Budget in dollars'), '50');
    await act(async () => {
      fireEvent.press(screen.getByRole('button', { name: 'Start with a $50.00 budget' }));
    });
    await flush();
    expect(fake.callsTo('POST', '/sessions')).toHaveLength(1);
    expect(fake.state.sessions).toHaveLength(0);
    expect(within(screen.getByTestId('start-confirmation')).getByRole('alert')).toHaveTextContent(
      "The runner refused it: a budget of $50.00 is above the runner's ceiling of $10.00 (session-runner D8)",
    );
  });

  it('takes the suggested budget when the estimate arrives after the confirmation opened', async () => {
    let release: () => void = () => {};
    const gate = new Promise<void>((resolve) => (release = resolve));
    const fake = fakeRunner({ estimates: ESTIMATES });
    const slow: typeof fake.fetch = async (input, init) => {
      if (input.includes('/estimates')) await gate;
      return fake.fetch(input, init);
    };
    const runner = createRunnerClient({
      baseUrl: RUNNER_URL,
      fetch: createSignedInFetch({ getToken: () => 'gho_octocat', onUnauthorized: () => {}, fetch: slow }),
    });
    render(<AgentsScreen runner={runner} status={createFixtureStatusClient('board')} login="octocat" project="example/reports" now={() => clock} />);
    await flush();
    expect(textIn('start-report-pipeline/exporter-build')).toContain('estimating…');
    fireEvent.press(screen.getByRole('button', { name: 'Start report-pipeline/exporter' }));
    expect(screen.getByTestId('start-estimate')).toHaveTextContent('Reading the estimate…');
    expect(screen.getByLabelText('Budget in dollars').props.value).toBe('');
    await act(async () => release());
    await flush();
    expect(screen.getByLabelText('Budget in dollars').props.value).toBe('2');
  });

  it("offers no start while the person's session slots are all in use", async () => {
    const mine = [1, 2, 3].map((n) => session({ sponsor: 'octocat', concern: `report-pipeline/c${n}` }));
    await shown({ sessions: mine, estimates: ESTIMATES, cap: 3 });
    expect(screen.getByTestId('agents-slots')).toHaveTextContent(
      'You sponsor all 3 of your session slots, so a start waits until one ends.',
    );
    const start = screen.getByRole('button', { name: 'Start report-pipeline/exporter' });
    expect(start.props.accessibilityState).toMatchObject({ disabled: true });
    fireEvent.press(start);
    expect(screen.queryByTestId('start-confirmation')).toBeNull();
  });

  it('shows a concern whose same skill is already running as running, with its sponsor, instead of a button', async () => {
    await shown({ sessions: twoSessions(), estimates: ESTIMATES });
    // hubot runs loop-prove on report-pipeline/queue.
    expect(textIn('start-report-pipeline/queue-prove')).toContain('running · hubot');
    expect(screen.queryByRole('button', { name: 'Prove report-pipeline/queue' })).toBeNull();
  });

  it('says there is nothing to start when the document lists nothing', async () => {
    await shown({}, { status: createFixtureStatusClient('empty') });
    expect(screen.getByText('Nothing is ready, shipped or stale.')).toBeTruthy();
  });

  it('says so when the build has no status service, or the status service cannot be read', async () => {
    await shown({}, { status: null });
    expect(screen.getByText(NO_STATUS_SERVICE_MESSAGE)).toBeTruthy();
    screen.unmount();

    const failing: StatusClient = {
      project: 'example/reports',
      getStatus: async () => {
        throw new StatusError('http', 'GET https://status.example/x answered 503', 503);
      },
    };
    await shown({}, { status: failing });
    expect(screen.getByText('The status service could not be read, so nothing is offered to start.')).toBeTruthy();
    expect(screen.getByText('GET https://status.example/x answered 503')).toBeTruthy();
  });

  it('lists what can start but offers no start when the build has no runner URL', async () => {
    await shown({}, { runner: null });
    const start = screen.getByRole('button', { name: 'Start report-pipeline/exporter' });
    expect(start.props.accessibilityState).toMatchObject({ disabled: true });
    expect(textIn('start-report-pipeline/exporter-build')).toContain('no estimate');
  });
});

describe('the release a start runs (latest-release C2)', () => {
  const ESTIMATES: FakeRunnerOptions['estimates'] = { 'loop-build': { usd: 1.6, wall_clock_s: 14 * 60, sessions: 7 } };

  it('shows and dispatches the tag the estimate named, so a tag cut later reaches the tab with no new build', async () => {
    const { fake } = await shown({ estimates: ESTIMATES, release: 'v0.9.0' });
    fireEvent.press(screen.getByRole('button', { name: 'Start report-pipeline/exporter' }));
    expect(screen.getByTestId('start-release')).toHaveTextContent(
      'Sponsored by you, octocat. It runs the skills of release v0.9.0.',
    );
    await act(async () => {
      fireEvent.press(screen.getByRole('button', { name: 'Start with a $2.00 budget' }));
    });
    await flush();
    expect(fake.callsTo('POST', '/sessions').map((c) => (c.body as { plugin_release: string }).plugin_release)).toEqual([
      'v0.9.0',
    ]);
    expect(fake.state.sessions[0]?.plugin_release).toBe('v0.9.0');
  });

  it('starts nothing when the runner names no release', async () => {
    const { fake } = await shown({ estimates: ESTIMATES, release: null });
    fireEvent.press(screen.getByRole('button', { name: 'Start report-pipeline/exporter' }));
    expect(screen.getByTestId('start-release')).toHaveTextContent(
      'Sponsored by you, octocat. The runner names no release of the skills, so it cannot start yet.',
    );
    const start = screen.getByRole('button', { name: 'Start with a $2.00 budget' });
    expect(start.props.accessibilityState).toMatchObject({ disabled: true });
    fireEvent.press(start);
    await flush();
    expect(fake.callsTo('POST', '/sessions')).toHaveLength(0);
  });

  it('starts nothing when the estimate, and so the release, cannot be read', async () => {
    const { fake } = await shown({
      answer: (call) =>
        call.path === '/estimates' ? { status: 502, body: { error: 'upstream-failed', message: 'GitHub is down' } } : undefined,
    });
    fireEvent.press(screen.getByRole('button', { name: 'Start report-pipeline/exporter' }));
    expect(screen.getByTestId('start-release')).toHaveTextContent(
      'Sponsored by you, octocat. The release of the skills could not be read, so it cannot start.',
    );
    fireEvent.changeText(screen.getByLabelText('Budget in dollars'), '2');
    const start = screen.getByRole('button', { name: 'Start with a $2.00 budget' });
    expect(start.props.accessibilityState).toMatchObject({ disabled: true });
    fireEvent.press(start);
    await flush();
    expect(fake.callsTo('POST', '/sessions')).toHaveLength(0);
  });
});
