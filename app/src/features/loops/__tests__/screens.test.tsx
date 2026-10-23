// app-loops-board C1 and C2, drawn: the Loops tab's real routes under the real shell and router, signed in, reading
// the schema's fixtures (tests/fixtures/status/) through the real status client from a fake status service. The
// other tabs, and app-threads' concern thread (command-center/D52), are stand-ins.

import * as fs from 'fs';
import * as path from 'path';

import { act, fireEvent, renderRouter, screen, within } from 'expo-router/testing-library';
import { useLocalSearchParams } from 'expo-router';
import { RefreshControl, Text } from 'react-native';

import type { Fetch } from '../../../api/fetch';
import type { StatusDocument } from '../../../api/status';
import { loadStatusFixture, statusFixtureNames } from '../../../api/statusFixtures';
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
import { NO_SERVICE_MESSAGE } from '../ui';

const SCHEMA = path.resolve(__dirname, '../../../../../plugin/skills/loop-status/scripts/status.schema.json');
const schema = JSON.parse(fs.readFileSync(SCHEMA, 'utf8'));
const DERIVATION_STATES: string[] = (schema.$defs ?? schema.definitions).concern_state.enum;

const STATUS_URL = 'https://status-123456789012.us-east1.run.app';
const SIGNED_IN = { token: 'gho_stored', user: { login: 'octocat', name: 'Mona Lisa Octocat' } };

function configFor(project: string, statusUrl: string | null = STATUS_URL): AppConfig {
  return {
    githubClientId: 'Iv1.test-client',
    statusUrl,
    runnerUrl: null,
    threadsUrl: null,
    notifyUrl: null,
    project: project as AppConfig['project'],
    environment: 'staging/app',
  };
}

/** A fake status service that answers each GET with the next of its answers (the last one repeats). */
function statusService(...answers: (StatusDocument | number)[]) {
  const calls: { url: string; auth: string | null }[] = [];
  const fetch: Fetch = async (url, init = {}) => {
    calls.push({ url, auth: new Headers(init.headers).get('Authorization') });
    const answer = answers[Math.min(calls.length, answers.length) - 1]!;
    return typeof answer === 'number'
      ? new Response('{"error":"unavailable"}', { status: answer, headers: { 'Content-Type': 'application/json' } })
      : new Response(JSON.stringify(answer), { status: 200, headers: { 'Content-Type': 'application/json' } });
  };
  return { fetch, calls };
}

function stand(label: string) {
  return function Stand() {
    return <Text>{label} screen</Text>;
  };
}

function ThreadStand() {
  const { loop, concern } = useLocalSearchParams<{ loop: string; concern: string }>();
  return (
    <Text>
      Thread for {loop}/{concern}
    </Text>
  );
}

function signedIn() {
  const clock = fakeClock();
  return new SignIn({
    clientId: 'Iv1.test-client',
    store: memorySessionStore(SIGNED_IN),
    fetch: fakeGitHub({ clock, clientId: 'Iv1.test-client' }).fetch,
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

async function open(initialUrl: string, config: AppConfig, fetch: Fetch) {
  const signIn = signedIn();
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
      // app-threads serves this route (command-center/D52); a stand-in shows where the link lands.
      'threads/loops/[loop]/concerns/[concern]': ThreadStand,
    },
    { initialUrl },
  );
  await flush();
  return result;
}

async function openWith(initialUrl: string, fixture: string) {
  const doc = loadStatusFixture(fixture);
  const service = statusService(doc);
  const result = await open(initialUrl, configFor(doc.project), service.fetch);
  return { ...result, doc, service };
}

function sectionOrder() {
  return screen.getAllByTestId(/^section-/).map((el) => String(el.props.testID).replace(/^section-/, ''));
}

describe('the Loops tab (C1)', () => {
  it('shows active loops first with their concerns’ states, then the backlog one line each, then parked loops', async () => {
    const { doc } = await openWith('/loops', 'board');
    expect(screen.getByTestId('tab-loops').props.accessibilityState).toMatchObject({ selected: true });
    expect(sectionOrder()).toEqual(['active', 'open', 'backlog', 'parked', 'done']);
    expect(screen.getByText('1 active · 1 open · 1 backlog · 1 parked · 1 done')).toBeTruthy();

    // Every concern of the active loop, with the state the derivation gave it.
    const active = doc.loops.find((l) => l.state === 'active')!;
    const card = within(screen.getByTestId(`loop-${active.id}`));
    expect(active.concerns.length).toBe(9);
    for (const c of active.concerns) expect(card.getByRole('button', { name: `${c.id}, ${c.state}` })).toBeTruthy();
    expect(card.getByTestId('goal-G1')).toHaveTextContent('G1 no evidence');

    // The backlog and parked loops, one line each, and none of their concerns on the board.
    const backlog = within(screen.getByTestId('section-backlog'));
    expect(backlog.getAllByRole('button').map((b) => b.props.accessibilityLabel)).toEqual(['search, backlog, 2 concerns']);
    expect(within(screen.getByTestId('section-parked')).getAllByRole('button').map((b) => b.props.accessibilityLabel)).toEqual([
      'billing, parked, 1 concern',
    ]);
    expect(screen.queryByRole('button', { name: 'indexer, ready' })).toBeNull();
    expect(screen.queryByRole('button', { name: 'invoices, parked' })).toBeNull();

    // An open loop has no concerns yet: its card is its reason and its next step.
    const openLoop = within(screen.getByTestId('loop-audit-log'));
    expect(openLoop.getByText('It has no concerns yet')).toBeTruthy();
    expect(openLoop.getByText('next: /loop-design audit-log')).toBeTruthy();

    expect(screen.getByTestId('as-of')).toHaveTextContent('main @dca84f4 · CI success · facts gathered 2026-10-20 15:00:00 UTC');
  });

  it('shows unknown wherever the derivation does, and never shows an unknown loop as active (command-center/D5, D37)', async () => {
    await openWith('/loops', 'unknown');
    expect(sectionOrder()).toEqual(['active', 'unknown', 'parked']);
    const pipeline = within(screen.getByTestId('loop-report-pipeline'));
    expect(pipeline.getByRole('button', { name: 'job-contract, unknown' })).toBeTruthy();
    expect(pipeline.getByRole('button', { name: 'queue, unknown' })).toBeTruthy();
    expect(pipeline.getByRole('button', { name: 'dashboard, open' })).toBeTruthy();

    const unknown = within(screen.getByTestId('section-unknown'));
    const search = within(unknown.getByTestId('loop-search'));
    expect(search.getByTestId('loop-state')).toHaveTextContent('unknown');
    expect(search.getByText(/whether one has an open pull request cannot be read/)).toBeTruthy();
    expect(search.getByRole('button', { name: 'indexer, unknown' })).toBeTruthy();
    expect(within(screen.getByTestId('section-active')).queryByTestId('loop-search')).toBeNull();
    expect(screen.getByTestId('as-of')).toHaveTextContent('main @db5da19 · CI unknown · facts gathered 2026-10-20 15:05:00 UTC');
  });

  it('says so when the project has no loops', async () => {
    await openWith('/loops', 'empty');
    expect(screen.getByText('This project has no loops yet. /loop-plan adds one to the backlog.')).toBeTruthy();
    expect(screen.queryAllByTestId(/^section-/)).toHaveLength(0);
  });

  it('reads the status through the signed-in client, once for the whole tab', async () => {
    const { service } = await openWith('/loops', 'board');
    expect(service.calls).toEqual([{ url: `${STATUS_URL}/projects/example/reports/status`, auth: 'Bearer gho_stored' }]);
    fireEvent.press(screen.getByRole('button', { name: 'retries, building' }));
    await flush();
    fireEvent.press(screen.getByRole('button', { name: 'Back to report-pipeline' }));
    await flush();
    expect(screen.getByTestId('loop-reason')).toBeTruthy();
    expect(service.calls).toHaveLength(1);
  });

  it('opens a concern from its chip, under the Loops tab', async () => {
    const result = await openWith('/loops', 'board');
    fireEvent.press(screen.getByRole('button', { name: 'worker, contradicted' }));
    await flush();
    expect(result.getPathname()).toBe('/loops/report-pipeline/concerns/worker');
    expect(screen.getByTestId('state-strip').props.accessibilityLabel).toBe('State: contradicted');
    expect(screen.getAllByRole('tab')).toHaveLength(4);
    expect(screen.getByTestId('tab-loops').props.accessibilityState).toMatchObject({ selected: true });
  });

  it('opens a backlog loop from its line, and its concerns from there', async () => {
    const result = await openWith('/loops', 'board');
    fireEvent.press(screen.getByRole('button', { name: 'search, backlog, 2 concerns' }));
    await flush();
    expect(result.getPathname()).toBe('/loops/search');
    expect(screen.getByTestId('loop-reason')).toHaveTextContent('None of its concerns has a decision, linked work or evidence');
    expect(screen.getByTestId('loop-state')).toHaveTextContent('backlog');
    fireEvent.press(screen.getByRole('button', { name: 'ranking, open' }));
    await flush();
    expect(result.getPathname()).toBe('/loops/search/concerns/ranking');
  });

  it('shows every loop on its own page, with each concern’s state and reason', async () => {
    for (const name of statusFixtureNames()) {
      const doc = loadStatusFixture(name);
      for (const loop of doc.loops) {
        await open(`/loops/${loop.id}`, configFor(doc.project), statusService(doc).fetch);
        expect(screen.getByTestId('loop-state')).toHaveTextContent(loop.state);
        expect(screen.getByTestId('loop-reason')).toHaveTextContent(loop.reason);
        for (const c of loop.concerns) {
          const row = within(screen.getByTestId(`concern-${c.id}`));
          expect(row.getByText(c.state)).toBeTruthy();
          expect(row.getByText(c.reason)).toBeTruthy();
        }
        screen.unmount();
      }
    }
  });

  it('says why it cannot show the loops when the build has no status service URL', async () => {
    const service = statusService(loadStatusFixture('board'));
    await open('/loops', configFor('example/reports', null), service.fetch);
    expect(screen.getByText(NO_SERVICE_MESSAGE)).toBeTruthy();
    expect(service.calls).toHaveLength(0);
  });

  it('says when the status cannot be read, and reads it again on request', async () => {
    const doc = loadStatusFixture('board');
    const service = statusService(503, doc);
    await open('/loops', configFor(doc.project), service.fetch);
    expect(screen.getByRole('alert')).toHaveTextContent(
      `The status could not be read. GET ${STATUS_URL}/projects/example/reports/status answered 503`,
    );
    fireEvent.press(screen.getByRole('button', { name: 'Try again' }));
    await flush();
    expect(sectionOrder()[0]).toBe('active');
    expect(service.calls).toHaveLength(2);
  });

  it('refuses a document for another project rather than show it', async () => {
    const service = statusService(loadStatusFixture('board'));
    await open('/loops', configFor('jugonzal/architect-loop'), service.fetch);
    expect(screen.getByRole('alert')).toHaveTextContent(
      'The status could not be read. Asked for jugonzal/architect-loop, got a status document for example/reports',
    );
    expect(screen.queryAllByTestId(/^section-/)).toHaveLength(0);
  });

  it('reads again when pulled down, and keeps the earlier copy, saying so, if that read fails', async () => {
    const doc = loadStatusFixture('board');
    const service = statusService(doc, 503);
    await open('/loops', configFor(doc.project), service.fetch);
    const scroll = screen.UNSAFE_getByType(RefreshControl);
    await act(async () => scroll.props.onRefresh());
    await flush();
    expect(service.calls).toHaveLength(2);
    expect(screen.getByRole('alert')).toHaveTextContent(
      `The status could not be read again, so this is the earlier copy. GET ${STATUS_URL}/projects/example/reports/status answered 503`,
    );
    expect(sectionOrder()[0]).toBe('active');
    expect(screen.getByTestId('as-of')).toHaveTextContent('main @dca84f4 · CI success · facts gathered 2026-10-20 15:00:00 UTC');
  });
});

describe('a concern page (C2)', () => {
  const cases = statusFixtureNames().flatMap((name) =>
    loadStatusFixture(name).loops.flatMap((loop) => loop.concerns.map((c) => [name, loop.id, c.id, c.state] as const)),
  );

  it('is tested for every state the derivation gives, unknown included', () => {
    expect([...new Set(cases.map((c) => c[3]))].sort()).toEqual([...DERIVATION_STATES].sort());
  });

  it.each(cases)('%s: %s/%s (%s) shows its state and the facts behind it, its contract and its claims', async (fixture, loopId, concernId) => {
    const { doc } = await openWith(`/loops/${loopId}/concerns/${concernId}`, fixture);
    const loop = doc.loops.find((l) => l.id === loopId)!;
    const concern = loop.concerns.find((c) => c.id === concernId)!;
    expect(screen.getByRole('header', { name: concern.title })).toBeTruthy();

    // The state strip draws exactly the derivation's states, and marks this one (command-center/D5).
    const strip = screen.getByTestId('state-strip');
    expect(strip.props.accessibilityLabel).toBe(`State: ${concern.state}`);
    const labels = within(strip).getAllByTestId(/^strip-/);
    expect(labels.map((l) => l.props.children)).toEqual(DERIVATION_STATES);
    expect(labels.filter((l) => l.props.accessibilityState?.selected).map((l) => l.props.children)).toEqual([concern.state]);
    for (const old of ['provisional', 'designing', 'review', 'in review', 'proving']) {
      expect(within(strip).queryByText(old)).toBeNull();
    }

    // The reason, and the facts it came from, every fact that could not be read included.
    expect(screen.getByTestId('state-reason')).toHaveTextContent(concern.reason);
    const facts = within(screen.getByTestId('state-card'));
    expect(facts.getByText(`@${concern.inputs.main.slice(0, 7)}`)).toBeTruthy();
    for (const missing of concern.inputs.missing ?? []) expect(facts.getByText(missing)).toBeTruthy();
    for (const pr of concern.inputs.prs) expect(facts.getByText(new RegExp(`^#${pr.number} ${pr.state}`))).toBeTruthy();
    if (concern.next) expect(facts.getByText(`next: ${concern.next}`)).toBeTruthy();

    // The contract: needs, touches, effects and ships-to, each item, or none.
    const { contract } = concern;
    const rows: [string, string[]][] = [
      ['needs', contract.needs],
      ['touches', contract.touches],
      ['effects', contract.effects],
      ['ships-to', contract.ships_to ? [contract.ships_to] : []],
    ];
    for (const [label, items] of rows) {
      const row = within(screen.getByTestId(`contract-${label}`));
      if (items.length === 0) expect(row.getByText('none')).toBeTruthy();
      for (const item of items) expect(row.getByText(item)).toBeTruthy();
    }

    // Each claim, with its latest verdict and the commit that verdict cites.
    for (const claim of concern.claims) {
      const row = within(screen.getByTestId(`claim-${claim.id}`));
      const latest = claim.evidence[claim.evidence.length - 1];
      expect(row.getByTestId(`verdict-${claim.id}`)).toHaveTextContent(latest ? latest.verdict : 'no evidence');
      if (latest) {
        expect(row.getByTestId(`citation-${claim.id}`)).toHaveTextContent(
          `rung ${latest.rung} · ${latest.environment} @${latest.commit ? latest.commit.slice(0, 7) : '?'} · ${latest.date}`,
        );
      } else {
        expect(row.queryByTestId(`citation-${claim.id}`)).toBeNull();
      }
    }
  });

  it('shows a claim’s latest verdict and its commit, not an earlier line’s', async () => {
    // No fixture claim has two lines, so give worker's C2 an earlier HOLDS before its CONTRADICTS.
    const doc = loadStatusFixture('board');
    const worker = doc.loops[0]!.concerns.find((c) => c.id === 'worker')!;
    worker.claims[1]!.evidence.unshift({
      date: '2026-10-16',
      verdict: 'HOLDS',
      rung: 1,
      environment: 'staging',
      commit: '1a2b3c4d5e6f',
      text: 'p95 22 s over 200 jobs',
    });
    await open('/loops/report-pipeline/concerns/worker', configFor(doc.project), statusService(doc).fetch);
    expect(screen.getByTestId('verdict-C2')).toHaveTextContent('CONTRADICTS');
    expect(screen.getByTestId('citation-C2')).toHaveTextContent('rung 1 · staging @780d0c5 · 2026-10-18');
    expect(screen.queryByText(/1a2b3c4/)).toBeNull();
    expect(within(screen.getByTestId('claim-C2')).getByText('current HOLDS on staging: no')).toBeTruthy();
  });

  it('shows a struck claim as counting for nothing, and a line migrated without a commit as @?', async () => {
    await openWith('/loops/onboarding/concerns/welcome-email', 'board');
    expect(screen.getByTestId('verdict-C2')).toHaveTextContent('CONTRADICTS');
    expect(screen.getByTestId('citation-C2')).toHaveTextContent('rung 6 · main @? · 2026-10-07');
    expect(within(screen.getByTestId('claim-C2')).getByText('struck: counts for nothing')).toBeTruthy();
    expect(within(screen.getByTestId('claim-C1')).getByText('current HOLDS on main: yes')).toBeTruthy();
  });

  it('opens the concern thread that app-threads serves (command-center/D52)', async () => {
    const result = await openWith('/loops/report-pipeline/concerns/retries', 'board');
    fireEvent.press(screen.getByRole('link', { name: 'Concern thread' }));
    await flush();
    expect(result.getPathname()).toBe('/threads/loops/report-pipeline/concerns/retries');
    expect(screen.getByText('Thread for report-pipeline/retries')).toBeTruthy();
  });

  it('says so when the status has no such concern', async () => {
    await openWith('/loops/report-pipeline/concerns/nope', 'board');
    expect(screen.getByText('The status gathered 2026-10-20 15:00:00 UTC has no concern named report-pipeline/nope.')).toBeTruthy();
    expect(screen.queryByRole('link', { name: 'Concern thread' })).toBeNull();
  });
});
