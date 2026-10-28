// app-inbox C1 and C2, drawn: the Needs you tab's real routes under the real shell and router, signed in, reading
// the schema's fixtures (tests/fixtures/status/) through the real status client from a fake status service, and
// starting sessions through the real runner client against a fake runner. Nothing here reaches a real service, and
// the fake runner starts nothing: it only records what the app sent. The other tabs, and app-threads' session
// thread (command-center/D52), are stand-ins.

import { act, fireEvent, render, renderRouter, screen, within } from 'expo-router/testing-library';
import { useLocalSearchParams } from 'expo-router';
import { Linking, Text } from 'react-native';

import type { Fetch } from '../../../api/fetch';
import type { DispatchRequest, Session } from '../../../api/runner.gen';
import { statusUrl, type QueueItem, type QueueKind, type StatusDocument } from '../../../api/status';
import { loadStatusFixture } from '../../../api/statusFixtures';
import TabsLayout from '../../../app/(tabs)/_layout';
import InboxLayout from '../../../app/(tabs)/inbox/_layout';
import InboxRoute from '../../../app/(tabs)/inbox/index';
import InboxItemRoute from '../../../app/(tabs)/inbox/[item]';
import { memorySessionStore } from '../../../shell/auth/sessionStore';
import { SignIn } from '../../../shell/auth/signIn';
import { fakeClock, fakeGitHub } from '../../../shell/auth/__tests__/fakeGitHub';
import { AppRoot } from '../../../shell/AppRoot';
import type { AppConfig } from '../../../shell/config';
import { ItemBody } from '../cards';
import { KIND_LABELS } from '../queue';
import { POLL_MS } from '../sessions';
import { NO_RUNNER_MESSAGE } from '../StartSheet';

const STATUS_URL = 'https://status-123456789012.us-east1.run.app';
const RUNNER_URL = 'https://runner-123456789012.us-east1.run.app';
const TOKEN = 'gho_stored';

function configFor(runnerUrl: string | null = RUNNER_URL): AppConfig {
  return {
    githubClientId: 'Iv1.test-client',
    statusUrl: STATUS_URL,
    runnerUrl,
    threadsUrl: null,
    notifyUrl: null,
    // The fixtures describe example/reports, and the client refuses a document for another project.
    project: 'example/reports',
    environment: 'staging/app',
  };
}

type Call = { method: string; url: string; auth: string | null; body: unknown };

/** The newest release the fake runner names, and the only one it accepts: not one any card was written with. */
const RELEASE = 'v0.7.0';

const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });

/**
 * A fake status service and a fake runner behind one fetch. The runner names the caller as each session's sponsor,
 * as the real one does from GET /user (command-center/D28), and keeps what it was asked to start so a test can end
 * it. It never runs anything.
 */
function services(
  doc: StatusDocument,
  login: string,
  options: { refuse?: Session; earlier?: Session[]; release?: string | null; oldRunner?: boolean } = {},
) {
  const release = options.release === undefined ? RELEASE : options.release;
  const calls: Call[] = [];
  const sessions: Session[] = [...(options.earlier ?? [])];
  let next = 1;
  const fetch: Fetch = async (url, init = {}) => {
    const method = init.method ?? 'GET';
    const body = typeof init.body === 'string' ? JSON.parse(init.body) : undefined;
    calls.push({ method, url, auth: new Headers(init.headers).get('Authorization'), body });
    if (url === statusUrl(STATUS_URL, 'example/reports')) return json(200, doc);
    if (!url.startsWith(RUNNER_URL)) return json(404, { error: 'not-found', message: url });
    const { pathname, searchParams } = new URL(url);
    if (method === 'GET' && pathname === '/sessions') return json(200, { sessions: [...sessions].reverse(), cap_per_sponsor: 3 });
    if (method === 'GET' && pathname === '/estimates') {
      const skill = searchParams.get('skill');
      const estimate = skill === 'loop-design' ? { kind: 'estimate', usd: 0.84, wall_clock_s: 540, sessions: 7 } : null;
      // A runner deployed before latest-release answers no plugin_release at all.
      return json(200, { skill, model: 'claude-test', estimate, ...(options.oldRunner ? {} : { plugin_release: release }) });
    }
    if (method === 'POST' && pathname === '/sessions') {
      if (options.refuse) {
        return json(409, {
          refused: 'running-session',
          message: `${options.refuse.concern} already has a running loop-design session`,
          pull_requests: [],
          sessions: [options.refuse],
        });
      }
      const request = body as DispatchRequest;
      if (request.plugin_release !== release) {
        return json(422, { error: 'unknown-release', message: `${request.plugin_release} is not a release tag` });
      }
      const session: Session = {
        id: `s_${next++}`,
        project: request.project,
        skill: request.skill,
        concern: request.concern ?? null,
        loop: request.loop ?? null,
        environment: request.environment ?? null,
        arguments: request.arguments ?? '',
        model: 'claude-test',
        sponsor: login,
        budget_usd: request.budget_usd,
        plugin_release: request.plugin_release,
        branch: 'main',
        state: 'starting',
        outcome: null,
        created_at: '2026-10-24T10:00:00Z',
        started_at: null,
        ended_at: null,
        spend: null,
        pull_requests: [],
        final_message: null,
      };
      sessions.push(session);
      return json(201, session);
    }
    const one = /^\/sessions\/([^/]+)$/.exec(pathname);
    if (method === 'GET' && one) {
      const found = sessions.find((s) => s.id === decodeURIComponent(one[1]!));
      return found ? json(200, found) : json(404, { error: 'no-such-session', message: 'no such session' });
    }
    return json(404, { error: 'not-found', message: url });
  };
  return {
    fetch,
    calls,
    runnerCalls: () => calls.filter((c) => c.url.startsWith(RUNNER_URL)),
    starts: () => calls.filter((c) => c.method === 'POST'),
    /** Ends a session as the runner would once its job finishes. */
    end(id: string, finalMessage: string) {
      const i = sessions.findIndex((s) => s.id === id);
      sessions[i] = {
        ...sessions[i]!,
        state: 'ended',
        outcome: 'completed',
        ended_at: '2026-10-24T10:20:00Z',
        final_message: finalMessage,
        spend: {
          kind: 'estimate',
          basis: 'sdk result',
          usd: 1.12,
          overshoot_usd: 0,
          tokens: { input: 1, output: 1, cache_creation: 0, cache_read: 0 },
          wall_clock_s: 600,
          as_of: '2026-10-24T10:20:00Z',
        },
      };
    },
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

function signedIn(login: string) {
  const clock = fakeClock();
  return new SignIn({
    clientId: 'Iv1.test-client',
    store: memorySessionStore({ token: TOKEN, user: { login, name: login } }),
    // GitHub's GET /user says who the token is, which is who the inbox matches items to (command-center/D62).
    fetch: fakeGitHub({ clock, clientId: 'Iv1.test-client', user: { login, name: login } }).fetch,
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
  {
    login = 'ana',
    doc = loadStatusFixture('board'),
    runnerUrl = RUNNER_URL as string | null,
    refuse,
    earlier,
    release,
    oldRunner,
  }: {
    login?: string;
    doc?: StatusDocument;
    runnerUrl?: string | null;
    refuse?: Session;
    earlier?: Session[];
    release?: string | null;
    oldRunner?: boolean;
  } = {},
) {
  const fake = services(doc, login, { refuse, earlier, release, oldRunner });
  const result = renderRouter(
    {
      _layout: () => <AppRoot signIn={signedIn(login)} config={configFor(runnerUrl)} fetch={fake.fetch} />,
      '(tabs)/_layout': TabsLayout,
      '(tabs)/inbox/_layout': InboxLayout,
      '(tabs)/inbox/index': InboxRoute,
      '(tabs)/inbox/[item]': InboxItemRoute,
      '(tabs)/loops/index': stand('Loops'),
      '(tabs)/agents/index': stand('Agents'),
      '(tabs)/environments/index': stand('Environments'),
      // app-threads serves this route (command-center/D52); a stand-in shows where the link lands.
      'threads/sessions/[session]': ThreadStand,
    },
    { initialUrl },
  );
  await flush();
  return { result, fake, doc };
}

const itemUrl = (id: string) => `/inbox/${encodeURIComponent(id)}`;

function cardOrder(section: string) {
  return within(screen.getByTestId(section))
    .getAllByTestId(/^item-/)
    .map((el) => String(el.props.testID).replace(/^item-/, ''));
}

function withItem(doc: StatusDocument, id: string, change: Partial<QueueItem>): StatusDocument {
  return { ...doc, queue: doc.queue.map((item) => (item.id === id ? ({ ...item, ...change } as QueueItem) : item)) };
}

async function press(name: string | RegExp) {
  fireEvent.press(screen.getByRole('button', { name }));
  await flush();
}

describe('Needs you (C1)', () => {
  it('lists every item waiting on the signed-in person, most unblocking first, under the Needs you tab', async () => {
    const { fake } = await open('/inbox');
    expect(screen.getByTestId('tab-inbox').props.accessibilityState).toMatchObject({ selected: true });
    expect(screen.getByTestId('inbox-count')).toHaveTextContent('7 items wait on you, sorted by how much each one unblocks.');
    expect(cardOrder('section-mine')).toEqual([
      'report-pipeline/worker/C2',
      'report-pipeline/dashboard/Q1',
      'example/reports#14',
      'report-pipeline/queue/C2',
      'example/reports#16',
      'record/report-pipeline/job-contract',
      'report-pipeline/Q2',
    ]);
    const question = within(screen.getByTestId('item-report-pipeline/dashboard/Q1'));
    expect(question.getByText('Question · report-pipeline')).toBeTruthy();
    expect(question.getByText('unblocks 1')).toBeTruthy();
    expect(question.getByText('Q1 blocks C1 · default if unanswered: The reports database, until the page needs more than one sample a minute')).toBeTruthy();
    expect(question.getByRole('button', { name: 'Answer' })).toBeTruthy();
    expect(within(screen.getByTestId('item-example/reports#14')).getByRole('button', { name: 'Read evidence' })).toBeTruthy();
    expect(within(screen.getByTestId('item-record/report-pipeline/job-contract')).getByRole('button', { name: 'Read the text' })).toBeTruthy();
    // The three read-only kinds open their details, with no card to finish (command-center/D34).
    expect(within(screen.getByTestId('item-report-pipeline/worker/C2')).getByRole('button', { name: 'Details' })).toBeTruthy();

    // ana is a member of report-pipeline, so she sees carla's ship item, read-only (command-center/D10).
    expect(cardOrder('section-others')).toEqual(['ship/production']);
    const ship = within(screen.getByTestId('item-ship/production'));
    expect(ship.getByTestId('card-footer')).toHaveTextContent('Waits on @carla');
    expect(ship.getByRole('button', { name: 'View' })).toBeTruthy();

    // The list reads the status as the signed-in person, and asks the runner nothing.
    expect(fake.calls).toEqual([
      { method: 'GET', url: `${STATUS_URL}/projects/example/reports/status`, auth: `Bearer ${TOKEN}`, body: undefined },
    ]);
  });

  it("gives a gate's holder the item waiting on them, and nothing from a loop they are not a member of", async () => {
    await open('/inbox', { login: 'carla' });
    expect(screen.getByTestId('inbox-count')).toHaveTextContent(/^1 item waits on you,/);
    expect(cardOrder('section-mine')).toEqual(['ship/production']);
    expect(screen.queryByTestId('section-others')).toBeNull();
  });

  it('shows a member what waits on someone else, read-only, and offers no start on it (command-center/D10)', async () => {
    const { fake } = await open('/inbox', { login: 'ben' });
    expect(screen.getByTestId('inbox-count')).toHaveTextContent('Nothing waits on you.');
    expect(cardOrder('section-others')).toHaveLength(8);
    expect(screen.getAllByRole('button', { name: 'View' })).toHaveLength(8);
    fireEvent.press(within(screen.getByTestId('item-report-pipeline/dashboard/Q1')).getByRole('button', { name: 'View' }));
    await flush();
    expect(screen.getByText(/^Waits on @ana\. You see it as a member of report-pipeline; only @ana can finish it\.$/)).toBeTruthy();
    expect(screen.getByText("Which store holds the dashboard's metrics?", { exact: false })).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Answer in a session' })).toBeNull();
    // Someone who cannot act asks the runner nothing, and starts nothing.
    expect(fake.runnerCalls()).toEqual([]);
  });

  it('shows an item that waits on no one named read-only, rather than hiding it', async () => {
    await open('/inbox', { doc: loadStatusFixture('unknown') });
    expect(screen.getByTestId('inbox-count')).toHaveTextContent('Nothing waits on you.');
    expect(cardOrder('section-unaddressed')).toEqual(['report-pipeline/dashboard/Q1']);
    await press('View');
    expect(screen.getByText(/It waits on no one named/)).toBeTruthy();
    expect(screen.getByText('It was written before options were recorded, so it shows only what it blocks and its default.')).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Answer in a session' })).toBeNull();
  });

  it('shows a proof, a contradiction and a refused PR read-only, with the command to run (command-center/D40)', async () => {
    const { fake } = await open(itemUrl('report-pipeline/worker/C2'));
    expect(screen.getByText('It is yours, and read-only here: run its command from a terminal.')).toBeTruthy();
    expect(screen.getByText('2026-10-18 · CONTRADICTS · rung 1 · staging @780d0c5 · p95 41 s over 200 jobs, needs at most 30 s')).toBeTruthy();
    expect(screen.getByTestId('command')).toHaveTextContent('/loop-design report-pipeline/worker');

    fireEvent.press(screen.getByRole('button', { name: 'Back to Needs you' }));
    await flush();
    fireEvent.press(within(screen.getByTestId('item-report-pipeline/queue/C2')).getByRole('button', { name: 'Details' }));
    await flush();
    expect(screen.getByText('a 10,000-job load on staging')).toBeTruthy();
    expect(screen.getByTestId('command')).toHaveTextContent('/loop-prove report-pipeline/queue staging');

    fireEvent.press(screen.getByRole('button', { name: 'Back to Needs you' }));
    await flush();
    fireEvent.press(within(screen.getByTestId('item-example/reports#16')).getByRole('button', { name: 'Details' }));
    await flush();
    expect(screen.getByText('FAIL: changes a file outside docs/loops/: docs/runbooks/worker.md')).toBeTruthy();
    expect(screen.getByTestId('command')).toHaveTextContent('scripts/check_loop_pr.sh --pr 16');
    expect(screen.queryByRole('button', { name: /^Start/ })).toBeNull();
    expect(fake.starts()).toEqual([]);
  });

  it('says so when an item is no longer queued for the person', async () => {
    await open(itemUrl('report-pipeline/dashboard/Q9'));
    expect(screen.getByText('report-pipeline/dashboard/Q9 is not in Needs you any more: the status no longer queues it for you.')).toBeTruthy();
  });
});

describe('the fact and stuck cards (app-owner-cards C1, C2; command-center/D76, D77)', () => {
  it('shows a fact only a person can read, who can supply it, the concerns waiting on it and the command (C1)', async () => {
    const { fake } = await open(itemUrl('fact/app'), { doc: loadStatusFixture('owner-queue') });
    expect(screen.getByText('loop · Fact')).toBeTruthy();
    expect(screen.getByRole('header', { name: 'Read what app serves' })).toBeTruthy();
    expect(screen.getByText('It is yours, and read-only here: run its command from a terminal.')).toBeTruthy();
    const fact = within(screen.getByTestId('fact'));
    expect(fact.getByText("app's served commit")).toBeTruthy();
    expect(fact.getByText('LOOP.md §3 says agents may not read app')).toBeTruthy();
    expect(fact.getByText('owner')).toBeTruthy();
    expect(fact.getByText('Read what app serves with the owner, then /loop-status again')).toBeTruthy();
    expect(within(screen.getByTestId('waiting')).getByText('loop/screen')).toBeTruthy();
    expect(screen.getByTestId('command')).toHaveTextContent('/loop-status loop');
    expect(screen.queryByRole('button', { name: /^Start/ })).toBeNull();
    expect(fake.starts()).toEqual([]);
  });

  it('shows a concern that leads to no one, its state, why, and its next step (C2)', async () => {
    const { fake } = await open(itemUrl('stuck/loop/lost'), { doc: loadStatusFixture('owner-queue') });
    expect(screen.getByText('loop · Stuck')).toBeTruthy();
    expect(screen.getByRole('header', { name: 'lost leads to no one' })).toBeTruthy();
    const stuck = within(screen.getByTestId('stuck'));
    expect(stuck.getByText('loop/lost')).toBeTruthy();
    expect(stuck.getByText('blocked')).toBeTruthy();
    expect(stuck.getByText('Nothing is built yet, and loop/gone, which it needs, does not exist')).toBeTruthy();
    expect(stuck.getByText('/loop-design loop/lost')).toBeTruthy();
    expect(screen.getByTestId('command')).toHaveTextContent('/loop-status loop/lost');
    expect(fake.starts()).toEqual([]);
  });

  it('gives every kind in the schema a card with a title, so none is blank (C2)', async () => {
    // One item of each kind from the fixtures, opened as the person it waits on.
    const docs = [loadStatusFixture('board'), loadStatusFixture('owner-queue')];
    const kinds = Object.keys(KIND_LABELS) as QueueKind[];
    for (const kind of kinds) {
      const doc = docs.find((d) => d.queue.some((item) => item.kind === kind));
      const item = doc?.queue.find((candidate) => candidate.kind === kind);
      if (!doc || !item) throw new Error(`no fixture has a ${kind} item`);
      const { result } = await open(itemUrl(item.id), { doc, login: item.waits_on ?? 'ana' });
      expect(screen.getByText(`${item.loop ?? 'across loops'} · ${KIND_LABELS[kind]}`)).toBeTruthy();
      // A question is titled by its question and a review by its pull request; every other kind by its title.
      const title =
        item.kind === 'question' ? item.detail.question : item.kind === 'review' ? item.detail.pr.title : item.title;
      expect(screen.getByRole('header', { name: title })).toBeTruthy();
      result.unmount();
    }
  });

  it('shows a kind this build has no card for by its title and why, not blank', () => {
    const doc = loadStatusFixture('owner-queue');
    const base = doc.queue.find((item) => item.kind === 'stuck')!;
    const item = { ...base, id: 'later/1', kind: 'later', title: 'A kind from a newer schema', why: 'Because it is new' } as unknown as QueueItem;
    render(<ItemBody entry={{ item, actionable: false, waitsOn: 'ana' }} doc={doc} />);
    expect(screen.getByRole('header', { name: 'A kind from a newer schema' })).toBeTruthy();
    expect(screen.getByTestId('fallback-why')).toHaveTextContent('Because it is new');
  });
});

describe('the question card (C1, C2; D3, D4)', () => {
  it('shows the options with their consequences and the recommendation, none pre-selected, and the default', async () => {
    const { result } = await open('/inbox');
    fireEvent.press(within(screen.getByTestId('item-report-pipeline/dashboard/Q1')).getByRole('button', { name: 'Answer' }));
    await flush();
    expect(result.getPathname()).toBe('/inbox/report-pipeline/dashboard/Q1');
    expect(screen.getByTestId('tab-inbox').props.accessibilityState).toMatchObject({ selected: true });
    const options = [screen.getByTestId('option-0'), screen.getByTestId('option-1')];
    expect(options.map((o) => o.props.accessibilityLabel)).toEqual([
      'The reports database, recommended. Nothing new to run or back up, but queries slow the reports above one sample a minute',
      'A separate time-series store. A sample every second, but one more service to deploy, monitor and back up',
    ]);
    for (const option of options) expect(option.props.accessibilityState).toEqual({ selected: false });
    expect(within(options[0]!).getByText('RECOMMENDED')).toBeTruthy();
    expect(within(options[1]!).queryByText('RECOMMENDED')).toBeNull();
    expect(screen.getByTestId('default')).toHaveTextContent(
      'Default if unanswered: The reports database, until the page needs more than one sample a minute',
    );
  });

  it("starts /loop-design on the question, sponsored by the person, after showing the budget, and opens the session's thread", async () => {
    const { fake, result } = await open(itemUrl('report-pipeline/dashboard/Q1'));
    expect(screen.getByTestId('answer-session-none')).toHaveTextContent('No session has been asked this question yet.');
    await press('Answer in a session');

    // The sheet shows what would start, who sponsors it, the budget and the estimate, and starts nothing yet.
    expect(screen.getByTestId('start-command')).toHaveTextContent('/loop-design report-pipeline/dashboard Q1');
    expect(screen.getByTestId('start-sponsor')).toHaveTextContent(/^Sponsored by @ana:/);
    expect(screen.getByLabelText('Budget, in dollars').props.value).toBe('2.00');
    expect(screen.getByTestId('start-estimate')).toHaveTextContent('Estimated $0.84 and 9 min, the median of its last 7 on claude-test.');
    expect(screen.getByTestId('start-release')).toHaveTextContent(`Runs the skills released as ${RELEASE}, the newest release.`);
    expect(fake.starts()).toEqual([]);

    await press('Start · budget $2.00');
    expect(fake.starts()).toEqual([
      {
        method: 'POST',
        url: `${RUNNER_URL}/sessions`,
        auth: `Bearer ${TOKEN}`,
        body: {
          project: 'example/reports',
          skill: 'loop-design',
          concern: 'report-pipeline/dashboard',
          arguments: 'Q1',
          budget_usd: 2,
          plugin_release: RELEASE,
        },
      },
    ]);
    // The person answers in the session's thread, which app-threads serves.
    expect(result.getPathname()).toBe('/threads/sessions/s_1');
    expect(screen.getByText('Thread for session s_1')).toBeTruthy();
  });

  it("starts a loop's own question on the loop, with the budget the person typed", async () => {
    const { fake } = await open(itemUrl('report-pipeline/Q2'));
    await press('Answer in a session');
    fireEvent.changeText(screen.getByLabelText('Budget, in dollars'), 'abc');
    expect(screen.getByRole('button', { name: 'Start' })).toBeDisabled();
    fireEvent.changeText(screen.getByLabelText('Budget, in dollars'), '3.5');
    await press('Start · budget $3.50');
    expect(fake.starts().map((c) => c.body)).toEqual([
      {
        project: 'example/reports',
        skill: 'loop-design',
        loop: 'report-pipeline',
        arguments: 'Q2',
        budget_usd: 3.5,
        plugin_release: RELEASE,
      },
    ]);
  });

  it("asks for a typed reason before a gated question's session starts, and carries it for the decision's notes", async () => {
    const doc = withItem(loadStatusFixture('board'), 'report-pipeline/dashboard/Q1', { gate: 'spending' });
    const { fake } = await open(itemUrl('report-pipeline/dashboard/Q1'), { doc });
    expect(screen.getByRole('button', { name: 'Answer in a session' })).toBeDisabled();
    fireEvent.changeText(screen.getByLabelText('Reason'), '   ');
    expect(screen.getByRole('button', { name: 'Answer in a session' })).toBeDisabled();
    fireEvent.changeText(screen.getByLabelText('Reason'), 'One sample a minute is enough for a year');
    await press('Answer in a session');
    await press('Start · budget $2.00');
    expect((fake.starts()[0]?.body as DispatchRequest).arguments).toBe(
      "Q1 — its answer crosses the spending gate. My reason, for the decision's notes: One sample a minute is enough for a year",
    );
  });

  it('follows the session a refusal names as already working on the question', async () => {
    const running: Session = {
      ...(sessionLike({ id: 's_0', concern: 'report-pipeline/dashboard', arguments: 'Q1', sponsor: 'ben' })),
      state: 'running',
    };
    const { result } = await open(itemUrl('report-pipeline/dashboard/Q1'), { refuse: running });
    await press('Answer in a session');
    await press('Start · budget $2.00');
    expect(screen.getByText(/The runner did not start it\. report-pipeline\/dashboard already has a running loop-design session/)).toBeTruthy();
    await press('Follow the session already doing it');
    expect(result.getPathname()).toBe('/threads/sessions/s_0');
  });

  it('shows a session already asked the question, whoever sponsored it, and opens its thread', async () => {
    const earlier = [sessionLike({ id: 's_9', concern: 'report-pipeline/dashboard', arguments: 'Q1', sponsor: 'ben' })];
    const { result } = await open(itemUrl('report-pipeline/dashboard/Q1'), { earlier });
    expect(screen.getByTestId('answer-session-summary')).toHaveTextContent('running · sponsored by @ben · budget $2.00');
    await press('Open its thread');
    expect(result.getPathname()).toBe('/threads/sessions/s_9');
  });

  it('says the build has no runner, instead of offering a start', async () => {
    const { fake } = await open(itemUrl('report-pipeline/dashboard/Q1'), { runnerUrl: null });
    expect(screen.getByText(NO_RUNNER_MESSAGE)).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Answer in a session' })).toBeNull();
    expect(fake.runnerCalls()).toEqual([]);
  });
});

describe('the review card (C1)', () => {
  it('shows the evidence before the diff, and leaves the diff and the merge to GitHub', async () => {
    const openURL = jest.spyOn(Linking, 'openURL').mockResolvedValue(true);
    const { fake } = await open(itemUrl('example/reports#14'));
    const sections = screen.getAllByTestId(/^(evidence|diff)$/).map((el) => el.props.testID);
    expect(sections).toEqual(['evidence', 'diff']);
    expect(screen.getByTestId('evidence-text')).toHaveTextContent(
      /C1: HOLDS \(rung 5, local, @bd994e4\): a job that fails 4 times is attempted 3 times and marked failed/,
    );
    await press('Open PR #14 on GitHub');
    expect(openURL).toHaveBeenCalledWith('https://github.com/example/reports/pull/14');
    // Reviewing starts no session, and the app never merges (LOOP.md §2).
    expect(screen.queryByRole('button', { name: /merge/i })).toBeNull();
    expect(fake.runnerCalls()).toEqual([]);
    openURL.mockRestore();
  });
});

describe('the ship card (C1, C2; D1)', () => {
  const deployDoc = () => withItem(loadStatusFixture('board'), 'ship/production', { gate: 'deploy' });

  it('shows the manual steps, prepares the brief with /loop-ship, and shows the brief once the session ends', async () => {
    const { fake } = await open(itemUrl('ship/production'), { login: 'carla', doc: deployDoc() });
    expect(within(screen.getByTestId('manual-steps')).getByText("1. Set the SMTP password in production's secret store (secrets)")).toBeTruthy();
    expect(screen.getByTestId('brief-session-none')).toHaveTextContent(/^No brief yet\. Preparing one starts \/loop-ship production,/);
    expect(screen.getByRole('button', { name: 'Deployed' })).toBeDisabled();

    await press('Prepare the brief');
    expect(screen.getByTestId('start-command')).toHaveTextContent('/loop-ship production');
    expect(screen.getByTestId('start-sponsor')).toHaveTextContent(/^Sponsored by @carla:/);
    expect(screen.getByTestId('start-estimate')).toHaveTextContent('No estimate yet: no loop-ship session on claude-test has been measured.');
    await press('Start · budget $2.00');
    expect(fake.starts().map((c) => c.body)).toEqual([
      { project: 'example/reports', skill: 'loop-ship', environment: 'production', arguments: '', budget_usd: 2, plugin_release: RELEASE },
    ]);
    expect(screen.getByTestId('brief-session-summary')).toHaveTextContent('starting · sponsored by @carla · budget $2.00');

    // The runner ends the session; the card asks again within a poll, and shows its final report as the brief.
    fake.end('s_1', 'Ship: production ← dca84f4 (1 concern)');
    await act(async () => {
      await jest.advanceTimersByTimeAsync(POLL_MS);
    });
    await flush();
    expect(screen.getByTestId('brief-session-message')).toHaveTextContent('Ship: production ← dca84f4 (1 concern)');
    expect(screen.getByTestId('brief-session-summary')).toHaveTextContent(
      'ended: completed · sponsored by @carla · budget $2.00 · spent about $1.12 (estimate)',
    );

    // "Deployed" starts /loop-ship again, told it is deployed, for the verification.
    await press('Deployed');
    expect(screen.getByTestId('start-command')).toHaveTextContent('/loop-ship production deployed');
    await press('Start · budget $2.00');
    expect(fake.starts().map((c) => (c.body as DispatchRequest).arguments)).toEqual(['', 'deployed']);
    expect(screen.getByTestId('verify-session-summary')).toHaveTextContent(/^starting · sponsored by @carla/);
  });

  it('shows a brief an earlier session wrote, so reopening the card needs no new session', async () => {
    const earlier = [
      {
        ...(sessionLike({ id: 's_7', skill: 'loop-ship', environment: 'production', sponsor: 'ana' })),
        state: 'ended' as const,
        outcome: 'completed' as const,
        final_message: 'Ship: production ← dca84f4',
      },
    ];
    const { fake } = await open(itemUrl('ship/production'), { login: 'carla', doc: deployDoc(), earlier });
    expect(screen.getByTestId('brief-session-message')).toHaveTextContent('Ship: production ← dca84f4');
    expect(screen.getByRole('button', { name: 'Prepare a new brief' })).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Deployed' })).not.toBeDisabled();
    expect(fake.starts()).toEqual([]);
  });

  it('keeps "Deployed" to the item that crosses deploy, and points a gate\'s own item at it (command-center/D59)', async () => {
    const board = loadStatusFixture('board');
    const secrets = { ...board.queue.find((i) => i.id === 'ship/production')!, id: 'ship/production/secrets', gate: 'secrets' };
    const deploy = { ...board.queue.find((i) => i.id === 'ship/production')!, gate: 'deploy', waits_on: 'ana' };
    const doc = { ...board, queue: [...board.queue.filter((i) => i.id !== 'ship/production'), deploy, secrets] as QueueItem[] };
    await open(itemUrl('ship/production/secrets'), { login: 'carla', doc });
    expect(screen.getByTestId('deploy-elsewhere')).toHaveTextContent('The deploy itself is its own card, waiting on @ana.');
    expect(screen.queryByRole('button', { name: 'Deployed' })).toBeNull();
    expect(screen.getByRole('button', { name: 'Prepare the brief' })).toBeTruthy();
  });
});

describe('the record card (C1, C2; D2)', () => {
  it("shows the proposed text and where it goes, and approving starts the record step on the record's loop", async () => {
    const { fake } = await open(itemUrl('record/report-pipeline/job-contract'));
    expect(within(screen.getByTestId('proposed-text')).getByText(/Shipped to main in #3 \(7c02eb4\), as designed\./)).toBeTruthy();
    expect(screen.getByText('docs/loops/report-pipeline/job-contract.md')).toBeTruthy();
    await press('Approve and record');
    expect(screen.getByTestId('start-command')).toHaveTextContent(
      '/loop-status report-pipeline record: yes to "Add a Shipped note to job-contract" in docs/loops/report-pipeline/job-contract.md',
    );
    expect(fake.starts()).toEqual([]);
    await press('Start · budget $2.00');
    expect(fake.starts().map((c) => c.body)).toEqual([
      {
        project: 'example/reports',
        skill: 'loop-status',
        loop: 'report-pipeline',
        arguments: 'record: yes to "Add a Shipped note to job-contract" in docs/loops/report-pipeline/job-contract.md',
        budget_usd: 2,
        plugin_release: RELEASE,
      },
    ]);
    expect(screen.getByTestId('record-session-summary')).toHaveTextContent('starting · sponsored by @ana · budget $2.00');
  });
});

/** A session as the runner lists it, for the sessions a test starts with. */
function sessionLike(over: Partial<Session>): Session {
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
    state: 'running',
    outcome: null,
    created_at: '2026-10-24T09:00:00Z',
    started_at: '2026-10-24T09:00:05Z',
    ended_at: null,
    spend: null,
    pull_requests: [],
    final_message: null,
    ...over,
  };
}

describe('the release a card starts (latest-release C2)', () => {
  it('shows and dispatches the tag the estimate named, so a tag cut later reaches the card with no new build', async () => {
    const { fake } = await open(itemUrl('report-pipeline/dashboard/Q1'), { release: 'v0.9.0' });
    await press('Answer in a session');
    expect(screen.getByTestId('start-release')).toHaveTextContent('Runs the skills released as v0.9.0, the newest release.');
    await press('Start · budget $2.00');
    expect(fake.starts().map((c) => (c.body as DispatchRequest).plugin_release)).toEqual(['v0.9.0']);
  });

  it('starts nothing on a runner that names no release, as one deployed before this concern', async () => {
    const { fake } = await open(itemUrl('report-pipeline/dashboard/Q1'), { oldRunner: true });
    await press('Answer in a session');
    expect(screen.getByTestId('start-release')).toHaveTextContent(
      'The project has no release of the skills yet, so nothing can start.',
    );
    expect(screen.getByRole('button', { name: 'Start · budget $2.00' })).toBeDisabled();
    expect(fake.starts()).toEqual([]);
  });

  it('starts nothing while the project has no release', async () => {
    const { fake } = await open(itemUrl('ship/production'), { login: 'carla', release: null });
    await press('Prepare the brief');
    expect(screen.getByTestId('start-release')).toHaveTextContent(
      'The project has no release of the skills yet, so nothing can start.',
    );
    expect(screen.getByRole('button', { name: 'Start · budget $2.00' })).toBeDisabled();
    expect(fake.starts()).toEqual([]);
  });
});
