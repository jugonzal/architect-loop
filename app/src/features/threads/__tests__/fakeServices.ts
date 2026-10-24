// Test-only fakes of the services a thread screen calls, at the fetch level, so the screens are tested through the
// real generated clients (src/api/threads.gen.ts, runner.gen.ts) and the real signed-in fetch. The threads fake keeps
// the rules services/threads/openapi.yaml states: members only (403 otherwise), people post only messages and name no
// sponsor, pages are oldest first with next_after, watching and marking twice is the same as once. The runner fake
// keeps runner/openapi.yaml's dispatch: the sponsor is the caller, and a scripted refusal answers 409 as it would.

import type { Fetch } from '../../../api/fetch';
import type { DispatchRequest, Refusal, Session } from '../../../api/runner.gen';
import type { StatusDocument } from '../../../api/status';
import type { Kind, Message, Thread, Watcher } from '../../../api/threads.gen';

export const THREADS_URL = 'https://threads-123456789012.us-east1.run.app';
export const RUNNER_URL = 'https://runner-123456789012.us-east1.run.app';
export const STATUS_URL = 'https://status-123456789012.us-east1.run.app';

export type Call = { service: string; method: string; path: string; query: URLSearchParams; body: unknown; auth: string | null };

type Stored = Omit<Thread, 'members' | 'last_seq'> & { messages: Message[] };

const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });

const problem = (status: number, error: string, message: string) => json(status, { error, message });

/** A service time as threads writes it, a fixed number of minutes after 16:00 UTC on 2026-10-24. */
export function at(minutes: number, day = '2026-10-24'): string {
  const h = 16 + Math.floor(minutes / 60);
  const m = minutes % 60;
  return `${day}T${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:05.123456Z`;
}

export type Seed = {
  kind?: Kind;
  body: string;
  author: Message['author'];
  created_at?: string;
  source?: Message['source'];
  record_marks?: Message['record_marks'];
};

export function person(login: string): Message['author'] {
  return { type: 'person', login };
}

export function fakeThreads({
  project,
  members,
  tokens,
  pageSize = Infinity,
}: {
  project: string;
  members: string[];
  /** Each token the fake GitHub accepts, and whose it is. */
  tokens: Record<string, string>;
  /** The most messages the fake serves in a page, below the limit asked for, to test paging. */
  pageSize?: number;
}) {
  const threads = new Map<string, Stored>();
  let nextId = 100;
  let clock = 30;
  /** Answers the next calls with this status instead, as a service that is down would. */
  let failWith: number | null = null;

  function threadAt(path: string, scope: Thread['scope'], names: { loop?: string; concern?: string; session?: string }) {
    let thread = threads.get(path);
    if (!thread) {
      thread = {
        project,
        scope,
        url: path,
        loop: names.loop ?? null,
        concern: names.concern ?? null,
        session: names.session ?? null,
        sponsor: null,
        watchers: [],
        messages: [],
      };
      threads.set(path, thread);
    }
    return thread;
  }

  function view(thread: Stored): Thread {
    const { messages, ...rest } = thread;
    return {
      ...rest,
      members: members.map((login) => ({ login })),
      watchers: [...thread.watchers],
      last_seq: messages.length ? messages[messages.length - 1]!.seq : 0,
    };
  }

  function add(thread: Stored, seed: Seed): Message {
    const message: Message = {
      id: nextId++,
      seq: (thread.messages.length ? thread.messages[thread.messages.length - 1]!.seq : 0) + 1,
      thread: thread.url,
      kind: seed.kind ?? 'message',
      author: seed.author,
      body: seed.body,
      created_at: seed.created_at ?? at(clock++),
      record_marks: seed.record_marks ?? [],
      source: seed.source ?? null,
    };
    if (seed.author.type === 'session' && !thread.sponsor) thread.sponsor = seed.author.sponsor;
    thread.messages.push(message);
    return message;
  }

  const base = `/projects/${project}`;
  const paths = {
    loop: (loop: string) => `${base}/loops/${loop}/thread`,
    concern: (loop: string, concern: string) => `${base}/loops/${loop}/concerns/${concern}/thread`,
    session: (session: string) => `${base}/sessions/${session}/thread`,
  };

  function parse(path: string) {
    let m = /^\/projects\/([^/]+)\/([^/]+)\/loops\/([^/]+)(?:\/concerns\/([^/]+))?\/thread(\/messages|\/watchers\/me)?$/.exec(path);
    if (m) {
      const [, owner, repo, loop, concern, rest] = m;
      const scope = concern ? 'concern' : 'loop';
      const url = concern ? paths.concern(loop!, concern) : paths.loop(loop!);
      return { kind: 'thread' as const, project: `${owner}/${repo}`, url, scope, names: { loop, concern }, rest: rest ?? '' } as const;
    }
    m = /^\/projects\/([^/]+)\/([^/]+)\/sessions\/([^/]+)\/thread(\/messages|\/watchers\/me)?$/.exec(path);
    if (m) {
      const [, owner, repo, session, rest] = m;
      return { kind: 'thread' as const, project: `${owner}/${repo}`, url: paths.session(session!), scope: 'session', names: { session }, rest: rest ?? '' } as const;
    }
    m = /^\/projects\/([^/]+)\/([^/]+)\/messages\/(\d+)(\/record-marks\/me)?$/.exec(path);
    if (m) return { kind: 'message' as const, project: `${m[1]}/${m[2]}`, id: Number(m[3]), rest: m[4] ?? '' } as const;
    return null;
  }

  function handle(method: string, path: string, query: URLSearchParams, body: unknown, auth: string | null): Response {
    if (failWith !== null) return problem(failWith, 'unavailable', 'GitHub could not be reached to check your access');
    const token = auth?.replace(/^Bearer /, '') ?? '';
    const login = tokens[token];
    if (!login) return problem(401, 'unauthorized', 'GitHub does not accept this token');
    if (!members.some((m) => m.toLowerCase() === login.toLowerCase())) {
      return problem(403, 'forbidden', `${login} is not a collaborator on ${project}`);
    }
    const route = parse(path);
    if (!route) return problem(404, 'not_found', `no route ${path}`);
    if (route.project !== project) return problem(404, 'not_found', `${route.project} is not served here`);

    if (route.kind === 'message') {
      const message = [...threads.values()].flatMap((t) => t.messages).find((msg) => msg.id === route.id);
      if (!message) return problem(404, 'not_found', `no message ${route.id}`);
      if (route.rest && method === 'PUT' && !message.record_marks.some((mark) => mark.login === login)) {
        message.record_marks.push({ login, marked_at: at(clock++) });
      }
      if (route.rest && method === 'DELETE') message.record_marks = message.record_marks.filter((mark) => mark.login !== login);
      return json(200, structuredClone(message));
    }

    const thread = threadAt(route.url, route.scope, route.names);
    if (route.rest === '') return json(200, view(thread));
    if (route.rest === '/watchers/me') {
      if (method === 'PUT' && !thread.watchers.some((w) => w.login === login)) {
        thread.watchers.push({ login, since: at(clock++) } satisfies Watcher);
      }
      if (method === 'DELETE') thread.watchers = thread.watchers.filter((w) => w.login !== login);
      return json(200, view(thread));
    }
    if (method === 'GET') {
      const after = Number(query.get('after') ?? 0);
      const limit = Math.min(Number(query.get('limit') ?? 100), pageSize);
      const kinds = query.getAll('kind');
      const matching = thread.messages.filter((msg) => msg.seq > after && (!kinds.length || kinds.includes(msg.kind)));
      const page = matching.slice(0, limit);
      const more = matching.length > page.length;
      return json(200, { messages: structuredClone(page), next_after: more ? page[page.length - 1]!.seq : null });
    }
    const fields = body as { body?: unknown; kind?: unknown; sponsor?: unknown };
    if (typeof fields.body !== 'string' || fields.body.length < 1 || fields.body.length > 65536) {
      return problem(400, 'bad_request', 'body must be a string of 1 to 65536 characters');
    }
    if ((fields.kind ?? 'message') !== 'message') return problem(403, 'forbidden', 'people post only messages');
    if (fields.sponsor !== undefined) return problem(400, 'bad_request', 'sponsor is refused from a person');
    return json(201, structuredClone(add(thread, { body: fields.body, author: { type: 'person', login } })));
  }

  return {
    paths,
    /** Adds messages to a thread, as people, sessions and GitHub's mirror would have posted them. */
    seed(url: string, seeds: Seed[], options: { watchers?: string[]; sponsor?: string } = {}): Message[] {
      const route = parse(url)!;
      if (route.kind !== 'thread') throw new Error(`not a thread: ${url}`);
      const thread = threadAt(route.url, route.scope, route.names);
      if (options.sponsor) thread.sponsor = options.sponsor;
      for (const login of options.watchers ?? []) thread.watchers.push({ login, since: at(0) });
      return seeds.map((seed) => add(thread, seed));
    },
    fail(status: number | null) {
      failWith = status;
    },
    handle,
  };
}

export function fakeSession(overrides: Partial<Session> & Pick<Session, 'id'>): Session {
  return {
    project: 'example/reports',
    skill: 'loop-build',
    concern: 'report-pipeline/queue',
    loop: null,
    environment: null,
    arguments: '',
    model: 'claude-test',
    sponsor: 'ana',
    budget_usd: 2.5,
    plugin_release: 'v0.4.0',
    branch: 'report-pipeline/queue',
    state: 'running',
    outcome: null,
    created_at: at(0),
    started_at: at(1),
    ended_at: null,
    spend: null,
    pull_requests: [],
    final_message: null,
    ...overrides,
  };
}

/**
 * The newest release the fake runner's estimate names. Not the release any screen was written with, so a test that
 * passes with it shows the screen took the runner's (latest-release C2).
 */
export const FAKE_RELEASE = 'v0.7.0';

export function fakeRunner({ tokens }: { tokens: Record<string, string> }) {
  const sessions = new Map<string, Session>();
  let release: string | null = FAKE_RELEASE;
  let estimateFails = false;
  const dispatched: DispatchRequest[] = [];
  let refusal: Refusal | null = null;
  let nextId = 1;

  function handle(method: string, path: string, query: URLSearchParams, body: unknown, auth: string | null): Response {
    const login = tokens[auth?.replace(/^Bearer /, '') ?? ''];
    if (!login) return problem(401, 'unauthenticated', 'GitHub did not accept the token');
    if (method === 'GET' && path === '/estimates') {
      if (estimateFails) return problem(502, 'upstream-failed', 'GitHub did not answer as expected');
      return json(200, {
        skill: query.get('skill'),
        model: 'claude-test',
        estimate: { kind: 'estimate', usd: 0.84, wall_clock_s: 300, sessions: 7 },
        plugin_release: release,
      });
    }
    const one = /^\/sessions\/([0-9a-f]+)$/.exec(path);
    if (method === 'GET' && one) {
      const session = sessions.get(one[1]!);
      return session ? json(200, session) : problem(404, 'no-such-session', `no session ${one[1]}`);
    }
    if (method === 'POST' && path === '/sessions') {
      const request = body as DispatchRequest;
      dispatched.push(request);
      if (refusal) return json(409, refusal);
      const id = String(nextId++).padStart(32, '0');
      const session = fakeSession({
        id,
        project: request.project,
        skill: request.skill,
        concern: request.concern ?? null,
        loop: request.loop ?? null,
        environment: request.environment ?? null,
        arguments: request.arguments ?? '',
        sponsor: login,
        budget_usd: request.budget_usd,
        plugin_release: request.plugin_release,
        branch: request.concern ?? 'main',
        state: 'starting',
        started_at: null,
      });
      sessions.set(id, session);
      return json(201, session);
    }
    return problem(404, 'not-found', `no route ${method} ${path}`);
  }

  return {
    sessions,
    dispatched,
    add(session: Session) {
      sessions.set(session.id, session);
    },
    refuse(next: Refusal | null) {
      refusal = next;
    },
    /** The newest release the estimate names from now on, or null for a project with none. */
    release(next: string | null) {
      release = next;
    },
    /** Whether the estimate, and so the release, fails to be read from now on. */
    failEstimates(fails: boolean) {
      estimateFails = fails;
    },
    handle,
  };
}

/** One fetch for every service a thread screen calls, recording each call with the token it carried. */
export function services({
  threads,
  runner,
  status,
}: {
  threads: ReturnType<typeof fakeThreads>;
  runner: ReturnType<typeof fakeRunner>;
  status: StatusDocument;
}) {
  const calls: Call[] = [];
  const fetch: Fetch = async (input, init = {}) => {
    const url = new URL(input);
    const method = init.method ?? 'GET';
    const auth = new Headers(init.headers).get('Authorization');
    const body = typeof init.body === 'string' ? JSON.parse(init.body) : undefined;
    const origin = url.origin;
    const service = origin === THREADS_URL ? 'threads' : origin === RUNNER_URL ? 'runner' : origin === STATUS_URL ? 'status' : origin;
    calls.push({ service, method, path: url.pathname, query: url.searchParams, body, auth });
    if (service === 'threads') return threads.handle(method, url.pathname, url.searchParams, body, auth);
    if (service === 'runner') return runner.handle(method, url.pathname, url.searchParams, body, auth);
    if (service === 'status') {
      return url.pathname === `/projects/${status.project}/status` ? json(200, status) : problem(404, 'not_found', 'no such project');
    }
    return new Response('not found', { status: 404 });
  };
  return { fetch, calls };
}
