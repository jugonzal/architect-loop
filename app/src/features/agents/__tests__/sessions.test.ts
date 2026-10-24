// command-center/app-agents C1, the sessions: every active session with its skill, what it runs on, its sponsor, how
// long it has run and its spend against its budget, labelled as an estimate (command-center/D23); the sponsor's
// session slots against the runner's cap (D22); and only a sponsor may stop their own session.

import type { SessionList } from '../../../api/runner.gen';
import {
  canStop,
  duration,
  elapsed,
  REFRESH_MS,
  runningLine,
  runningSessions,
  skillBadge,
  slotsLine,
  slotsOf,
  spendView,
  stateLabel,
  targetOf,
} from '../sessions';
import { session } from './fakeRunner';

const NOW = Date.parse('2026-10-24T12:00:00Z');

describe('a running session', () => {
  it('names what it runs on: its concern, its loop or its environment', () => {
    expect(targetOf(session({ concern: 'report-pipeline/retries' }))).toBe('report-pipeline/retries');
    expect(targetOf(session({ skill: 'loop-status', concern: null, loop: 'report-pipeline' }))).toBe('report-pipeline');
    expect(targetOf(session({ skill: 'loop-ship', concern: null, environment: 'staging/app' }))).toBe('staging/app');
  });

  it("wears its skill's two letters, as the artboard's tiles do", () => {
    expect(['loop-build', 'loop-prove', 'loop-design', 'loop-status', 'loop-ship'].map((s) => skillBadge(s as never))).toEqual([
      'LB',
      'LP',
      'LD',
      'ST',
      'SH',
    ]);
  });

  it('has run since its job started, or since it was dispatched while it is starting', () => {
    expect(elapsed(session({ started_at: '2026-10-24T11:42:00Z' }), NOW)).toBe('18 min');
    expect(elapsed(session({ state: 'starting', created_at: '2026-10-24T11:59:20Z', started_at: null }), NOW)).toBe('40 s');
    expect(elapsed(session({ started_at: '2026-10-24T10:55:00Z' }), NOW)).toBe('1 h 05 min');
    // One that has ended stops counting.
    expect(elapsed(session({ started_at: '2026-10-24T11:00:00Z', ended_at: '2026-10-24T11:30:00Z' }), NOW)).toBe('30 min');
  });

  it("reads 0 s when it started ahead of the phone's clock, and says so when its times cannot be read", () => {
    expect(elapsed(session({ started_at: '2026-10-24T12:01:00Z' }), NOW)).toBe('0 s');
    expect(elapsed(session({ started_at: 'soon' }), NOW)).toBe('time unknown');
  });

  it('writes durations as the artboard does', () => {
    expect([0, 59, 60, 18 * 60 + 59, 3600, 3600 + 5 * 60, 26 * 3600].map(duration)).toEqual([
      '0 s',
      '59 s',
      '1 min',
      '18 min',
      '1 h 00 min',
      '1 h 05 min',
      '26 h 00 min',
    ]);
  });

  it('shows its spend against its budget, labelled as an estimate (D23)', () => {
    const view = spendView(session({ budget_usd: 2.5 }));
    expect(view.text).toBe('est. $1.10 / $2.50');
    expect(view.label).toBe('estimated spend $1.10 of a $2.50 budget');
    expect(view.fraction).toBeCloseTo(0.44);
    expect(view.over).toBe(false);
  });

  it('shows a spend past its budget as over, with a full bar, since a session may pass it by one response (D21)', () => {
    const base = session();
    const view = spendView({ ...base, budget_usd: 1, spend: { ...base.spend!, usd: 1.23 } });
    expect(view.text).toBe('est. $1.23 / $1.00');
    expect(view.fraction).toBe(1);
    expect(view.over).toBe(true);
  });

  it('says it has no spend yet until the runner publishes its first', () => {
    const view = spendView(session({ spend: null, budget_usd: 3 }));
    expect(view.text).toBe('no spend yet / $3.00');
    expect(view.fraction).toBe(0);
  });

  it('labels a starting or stopping session, and leaves a running one plain', () => {
    expect(stateLabel(session({ state: 'starting' }))).toBe('STARTING');
    expect(stateLabel(session({ state: 'stopping' }))).toBe('STOPPING');
    expect(stateLabel(session({ state: 'running' }))).toBeNull();
  });
});

describe('stopping a session', () => {
  it('is offered only to its sponsor, and only while it is starting or running', () => {
    expect(canStop(session({ sponsor: 'octocat', state: 'running' }), 'octocat')).toBe(true);
    expect(canStop(session({ sponsor: 'octocat', state: 'starting' }), 'octocat')).toBe(true);
    expect(canStop(session({ sponsor: 'hubot', state: 'running' }), 'octocat')).toBe(false);
    expect(canStop(session({ sponsor: 'octocat', state: 'stopping' }), 'octocat')).toBe(false);
    expect(canStop(session({ sponsor: 'octocat', state: 'ended', outcome: 'completed' }), 'octocat')).toBe(false);
  });
});

describe('the list', () => {
  const list: SessionList = {
    cap_per_sponsor: 3,
    sessions: [
      session({ sponsor: 'octocat', state: 'starting' }),
      session({ sponsor: 'hubot', state: 'running' }),
      session({ sponsor: 'octocat', state: 'stopping' }),
      session({ sponsor: 'octocat', state: 'running', project: 'example/other' }),
      session({ sponsor: 'octocat', state: 'ended', outcome: 'completed' }),
    ],
  };

  it("shows every sponsor's active sessions of this project, in the runner's order", () => {
    const shown = runningSessions(list, 'example/reports');
    expect(shown.map((s) => [s.sponsor, s.state])).toEqual([
      ['octocat', 'starting'],
      ['hubot', 'running'],
      ['octocat', 'stopping'],
    ]);
  });

  it("counts the person's active sessions on every project against the runner's cap, as the runner does (D22)", () => {
    expect(slotsOf(list, 'octocat')).toEqual({ used: 3, cap: 3 });
    expect(slotsOf(list, 'hubot')).toEqual({ used: 1, cap: 3 });
    expect(slotsLine({ used: 2, cap: 3 })).toBe('You sponsor 2 of your 3 session slots.');
    expect(slotsLine({ used: 3, cap: 3 })).toBe('You sponsor all 3 of your session slots, so a start waits until one ends.');
  });

  it('says how many run and what they have spent so far, as an estimate', () => {
    const shown = runningSessions(list, 'example/reports');
    expect(runningLine(shown)).toBe('3 running · est. $3.30 so far');
    expect(runningLine([])).toBe('0 running · est. $0.00 so far');
  });

  it('is read again well within 10 seconds (C1)', () => {
    expect(REFRESH_MS).toBeLessThanOrEqual(10_000 / 2);
  });
});
