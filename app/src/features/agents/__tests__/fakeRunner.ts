// A fake runner for the Agents tab's tests: it answers the operations the tab calls, at the paths and with the
// statuses services/runner/openapi.yaml gives them, from an in-memory list of sessions. It names the caller from
// the bearer token, as the runner names a sponsor from GET /user (command-center/D28), and refuses what the runner
// refuses: a stop by anyone but the sponsor, a start past the sponsor's cap or above the budget ceiling. It never
// starts anything.

import type { Fetch } from '../../../api/fetch';
import type {
  DispatchRequest,
  EstimateAnswer,
  Problem,
  Refusal,
  Session,
  SessionList,
  Skill,
} from '../../../api/runner.gen';

export const RUNNER_URL = 'https://runner-123456789012.us-east1.run.app';

let ids = 0;

/** A session as the runner serves it, running since 18 minutes before 2026-10-24T12:00:00Z. */
export function session(overrides: Partial<Session> = {}): Session {
  ids += 1;
  return {
    id: ids.toString(16).padStart(32, '0'),
    project: 'example/reports',
    skill: 'loop-build',
    concern: 'report-pipeline/retries',
    loop: null,
    environment: null,
    arguments: '',
    model: 'claude-opus-5-5',
    sponsor: 'octocat',
    budget_usd: 2.5,
    plugin_release: 'v0.4.0',
    branch: 'report-pipeline/retries',
    state: 'running',
    outcome: null,
    created_at: '2026-10-24T11:41:30Z',
    started_at: '2026-10-24T11:42:00Z',
    ended_at: null,
    spend: {
      kind: 'estimate',
      basis: 'per-step usage',
      usd: 1.1,
      overshoot_usd: null,
      tokens: { input: 120_000, output: 4_000, cache_creation: 0, cache_read: 80_000 },
      wall_clock_s: 1080,
      as_of: '2026-10-24T11:59:55Z',
    },
    pull_requests: [],
    final_message: null,
    ...overrides,
  };
}

export type RunnerCall = { method: string; path: string; query: Record<string, string>; auth: string | null; body: unknown };

export type FakeRunnerOptions = {
  sessions?: Session[];
  cap?: number;
  ceiling?: number;
  /** The estimate for each skill, or null for a skill with none; a skill not named has none. */
  estimates?: Partial<Record<Skill, { usd: number; wall_clock_s: number; sessions: number } | null>>;
  /** Who each token belongs to. */
  tokens?: Record<string, string>;
  /** An answer to give instead, for a call, before the fake's own. */
  answer?: (call: RunnerCall) => { status: number; body: unknown } | undefined;
};

function json(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
}

function problem(status: number, error: Problem['error'], message: string): Response {
  return json(status, { error, message } satisfies Problem);
}

export function fakeRunner({
  sessions = [],
  cap = 3,
  ceiling = 10,
  estimates = {},
  tokens = { gho_stored: 'octocat', gho_octocat: 'octocat' },
  answer,
}: FakeRunnerOptions = {}) {
  const state = { sessions: [...sessions] };
  const calls: RunnerCall[] = [];

  const fetch: Fetch = async (input, init = {}) => {
    // Parsed by hand: React Native's URL, which the tests run under, does not implement pathname or searchParams.
    const [base = '', search = ''] = input.split('?');
    const method = (init.method ?? 'GET').toUpperCase();
    const auth = new Headers(init.headers).get('Authorization');
    const body = typeof init.body === 'string' ? JSON.parse(init.body) : null;
    const call: RunnerCall = {
      method,
      path: base.startsWith(RUNNER_URL) ? base.slice(RUNNER_URL.length) || '/' : base,
      query: Object.fromEntries(
        search
          .split('&')
          .filter(Boolean)
          .map((part) => part.split('=').map(decodeURIComponent) as [string, string]),
      ),
      auth,
      body,
    };
    calls.push(call);
    if (!base.startsWith(`${RUNNER_URL}/`)) return new Response('not found', { status: 404 });

    const caller = auth?.startsWith('Bearer ') ? tokens[auth.slice('Bearer '.length)] : undefined;
    if (!caller) return problem(401, 'unauthenticated', 'GitHub did not accept the token');

    const scripted = answer?.(call);
    if (scripted) return json(scripted.status, scripted.body);

    if (method === 'GET' && call.path === '/sessions') {
      const which = call.query.state ?? 'active';
      const listed = state.sessions.filter(
        (s) =>
          (which === 'all' || s.state !== 'ended') &&
          (!call.query.sponsor || s.sponsor === call.query.sponsor) &&
          (!call.query.project || s.project === call.query.project),
      );
      return json(200, { sessions: listed, cap_per_sponsor: cap } satisfies SessionList);
    }

    if (method === 'GET' && call.path === '/estimates') {
      const skill = call.query.skill as Skill;
      const found = estimates[skill];
      const estimate = found ? { kind: 'estimate' as const, ...found } : null;
      return json(200, { skill, model: call.query.model ?? 'claude-opus-5-5', estimate } satisfies EstimateAnswer);
    }

    if (method === 'POST' && call.path === '/sessions') {
      const request = body as DispatchRequest;
      if (request.budget_usd > ceiling) {
        return json(409, {
          refused: 'budget-ceiling',
          message: `a budget of $${request.budget_usd.toFixed(2)} is above the runner's ceiling of $${ceiling.toFixed(2)} (session-runner D8)`,
          pull_requests: [],
          sessions: [],
          ceiling_usd: ceiling,
        } satisfies Refusal);
      }
      const mine = state.sessions.filter((s) => s.sponsor === caller && s.state !== 'ended');
      if (mine.length >= cap) {
        return json(409, {
          refused: 'sponsor-cap',
          message: `${caller} already runs ${mine.length} sessions, the cap of ${cap}`,
          pull_requests: [],
          sessions: mine,
          cap,
        } satisfies Refusal);
      }
      const started = session({
        project: request.project,
        skill: request.skill,
        concern: request.concern ?? null,
        arguments: request.arguments ?? '',
        sponsor: caller,
        budget_usd: request.budget_usd,
        plugin_release: request.plugin_release,
        branch: request.concern ?? 'main',
        state: 'starting',
        created_at: '2026-10-24T12:00:00Z',
        started_at: null,
        spend: null,
      });
      state.sessions.unshift(started);
      return json(201, started);
    }

    const stop = /^\/sessions\/([0-9a-f]{32})\/stop$/.exec(call.path);
    if (method === 'POST' && stop) {
      const index = state.sessions.findIndex((s) => s.id === stop[1]);
      const found = state.sessions[index];
      if (!found) return problem(404, 'no-such-session', `no session is ${stop[1]}`);
      if (found.sponsor !== caller) {
        return problem(403, 'not-the-sponsor', `only ${found.sponsor}, its sponsor, may stop ${found.id}`);
      }
      if (found.state === 'ended') return problem(409, 'already-ended', `${found.id} has already ended`);
      const stopping = { ...found, state: 'stopping' as const };
      state.sessions[index] = stopping;
      return json(202, stopping);
    }

    return problem(404, 'not-found', `nothing is at ${call.path}`);
  };

  return {
    fetch,
    calls,
    state,
    /** The calls made to one operation, by method and path. */
    callsTo: (method: string, path: string | RegExp) =>
      calls.filter((c) => c.method === method && (typeof path === 'string' ? c.path === path : path.test(c.path))),
  };
}
