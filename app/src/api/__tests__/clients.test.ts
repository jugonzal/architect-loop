// app-clients C1: the runner's and threads' clients are generated from their OpenAPI files, a check fails when
// either no longer matches its file, and every call goes through the signed-in fetch (command-center/D55).

import { execFileSync, spawnSync } from 'child_process';
import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';

import { createSignedInFetch, NotSignedInError, type Fetch } from '../fetch';
import {
  createRunnerClient,
  RUNNER_OPERATIONS,
  type DispatchRequest,
  type Refusal,
  type RunnerOperations,
  type Session,
} from '../runner.gen';
import { operationUrl, projectPath, ServiceError, serviceNotConfiguredMessage, serviceUrlVariable } from '../service';
import { createThreadsClient, THREADS_OPERATIONS, type Message, type ThreadsOperations } from '../threads.gen';

const APP = path.resolve(__dirname, '../../..');
const REPO = path.resolve(APP, '..');
const API_DIR = path.resolve(__dirname, '..');
const GENERATOR = path.join(API_DIR, 'generate-clients.js');

// The generator and the YAML parser are plain Node, so these run them as `npm run check:clients` does, in Node,
// outside jest's module system. A generator run compiles and formats both clients, so give it time.
const SLOW = 60_000;

function nodeJson<T>(script: string, ...args: string[]): T {
  return JSON.parse(execFileSync(process.execPath, ['-e', script, ...args], { cwd: APP, encoding: 'utf8' }));
}

const SERVICES = nodeJson<Record<string, { skip: Record<string, string> }>>(
  'process.stdout.write(JSON.stringify(require(process.argv[1]).SERVICES))',
  GENERATOR,
);

/** Every operation the OpenAPI file declares, in its order, as operationId, method and path. */
function declared(service: string): { id: string; method: string; path: string }[] {
  return nodeJson(
    `const spec = require('yaml').parse(require('fs').readFileSync(process.argv[1], 'utf8'));
     const ops = [];
     for (const [route, item] of Object.entries(spec.paths))
       for (const [method, op] of Object.entries(item))
         if (['get', 'put', 'post', 'delete', 'patch'].includes(method))
           ops.push({ id: op.operationId, method: method.toUpperCase(), path: route });
     process.stdout.write(JSON.stringify(ops));`,
    path.join(REPO, 'services', service, 'openapi.yaml'),
  );
}

const scratch: string[] = [];
afterAll(() => scratch.forEach((dir) => fs.rmSync(dir, { recursive: true, force: true })));

/** A scratch copy of the generator, the committed clients and the OpenAPI files, to change without harm. */
function scratchRepo(): string {
  const repo = fs.mkdtempSync(path.join(os.tmpdir(), 'app-clients-'));
  scratch.push(repo);
  const api = path.join(repo, 'app/src/api');
  fs.mkdirSync(api, { recursive: true });
  fs.symlinkSync(path.join(APP, 'node_modules'), path.join(repo, 'app/node_modules'), 'dir');
  for (const file of ['generate-clients.js', 'runner.gen.ts', 'threads.gen.ts']) {
    fs.copyFileSync(path.join(API_DIR, file), path.join(api, file));
  }
  for (const service of ['runner', 'threads']) {
    fs.mkdirSync(path.join(repo, 'services', service), { recursive: true });
    fs.copyFileSync(path.join(REPO, 'services', service, 'openapi.yaml'), path.join(repo, 'services', service, 'openapi.yaml'));
  }
  return repo;
}

function edit(file: string, from: string, to: string) {
  const text = fs.readFileSync(file, 'utf8');
  expect(text).toContain(from);
  fs.writeFileSync(file, text.replace(from, to));
}

function runCheck(repo: string, ...args: string[]) {
  return spawnSync(process.execPath, [path.join(repo, 'app/src/api/generate-clients.js'), '--check', ...args], {
    encoding: 'utf8',
  });
}

/** A fake service: answers every call with `answer`, and records each call as the network would see it. */
function fakeService(answer: { status?: number; body?: unknown } = {}) {
  const calls: { url: string; method: string; headers: Headers; body: unknown }[] = [];
  const fetch: Fetch = async (url, init = {}) => {
    calls.push({
      url,
      method: init.method ?? 'GET',
      headers: new Headers(init.headers),
      body: typeof init.body === 'string' ? JSON.parse(init.body) : init.body,
    });
    const body = answer.body === undefined ? {} : answer.body;
    return new Response(typeof body === 'string' ? body : JSON.stringify(body), {
      status: answer.status ?? 200,
      headers: { 'Content-Type': 'application/json' },
    });
  };
  return { fetch, calls };
}

function signedIn(service: ReturnType<typeof fakeService>, onUnauthorized = jest.fn()): Fetch {
  return createSignedInFetch({ getToken: () => 'gho_test', onUnauthorized, fetch: service.fetch });
}

const RUNNER = 'https://runner-123456789012.us-east1.run.app';
const THREADS = 'https://threads-123456789012.us-east1.run.app';
const PROJECT = projectPath('jugonzal/architect-loop');

describe('the clients are generated from the OpenAPI files (command-center/D55)', () => {
  it(
    'match the files they were generated from',
    () => {
      // Runs the check as `npm run check:clients` does, so CI's `npm test` runs it too.
      const out = execFileSync(process.execPath, [GENERATOR, '--check'], { encoding: 'utf8' });
      expect(out).toBe('src/api/runner.gen.ts, src/api/threads.gen.ts match their OpenAPI files\n');
    },
    SLOW,
  );

  it('say which OpenAPI file each was generated from', () => {
    for (const service of ['runner', 'threads']) {
      const source = fs.readFileSync(path.join(API_DIR, `${service}.gen.ts`), 'utf8');
      expect(source).toContain(`// Generated from services/${service}/openapi.yaml by src/api/generate-clients.js.`);
    }
  });

  it(
    'fail the check when an OpenAPI file changes without its client, or a client is edited by hand',
    () => {
      const repo = scratchRepo();
      expect(runCheck(repo).status).toBe(0);
      edit(path.join(repo, 'services/runner/openapi.yaml'), 'enum: [active, all]', 'enum: [active, all, ended]');
      edit(path.join(repo, 'app/src/api/threads.gen.ts'), "method: 'PUT'", "method: 'POST'");
      const result = runCheck(repo);
      expect(result.status).toBe(1);
      expect(result.stderr).toBe(
        'src/api/runner.gen.ts does not match services/runner/openapi.yaml: run `npm run generate:clients`\n' +
          'src/api/threads.gen.ts does not match services/threads/openapi.yaml: run `npm run generate:clients`\n',
      );
    },
    SLOW,
  );

  it(
    'fail the check when a client outlives its OpenAPI file, or a file has no client',
    () => {
      const repo = scratchRepo();
      fs.rmSync(path.join(repo, 'services/runner'), { recursive: true });
      fs.rmSync(path.join(repo, 'app/src/api/threads.gen.ts'));
      const result = runCheck(repo);
      expect(result.status).toBe(1);
      expect(result.stderr).toBe(
        'src/api/runner.gen.ts exists, but services/runner/openapi.yaml does not: delete the client or restore its file\n' +
          'src/api/threads.gen.ts is missing: run `npm run generate:clients`\n',
      );
    },
    SLOW,
  );

  it('generate notify with the same generator once its OpenAPI file exists, and never status', () => {
    expect(Object.keys(SERVICES)).toEqual(['runner', 'threads', 'notify']);
    const result = runCheck(REPO, 'notify');
    expect(result.status).toBe(1);
    expect(result.stderr).toBe('services/notify/openapi.yaml does not exist, so src/api/notify.gen.ts cannot be generated\n');
  });

  it.each([
    ['runner', RUNNER_OPERATIONS, () => createRunnerClient({ baseUrl: RUNNER, fetch: fakeService().fetch })],
    ['threads', THREADS_OPERATIONS, () => createThreadsClient({ baseUrl: THREADS, fetch: fakeService().fetch })],
  ] as const)('make every operation of services/%s/openapi.yaml a method, with its method and path', (service, table, make) => {
    const skip = SERVICES[service]?.skip ?? {};
    const expected = declared(service).filter((op) => !(op.id in skip));
    expect(expected.length).toBeGreaterThan(0);
    expect(Object.keys(table)).toEqual(expected.map((op) => op.id));
    expect(Object.keys(make())).toEqual(expected.map((op) => op.id));
    for (const op of expected) {
      expect(table[op.id as keyof typeof table]).toMatchObject({ method: op.method, path: op.path });
    }
  });

  it('leave out only the webhook GitHub calls, and say why', () => {
    expect(SERVICES.runner?.skip).toEqual({});
    expect(SERVICES.threads?.skip).toEqual({ receiveGitHubWebhook: expect.stringContaining('GitHub calls it') });
    expect(declared('threads').map((op) => op.id)).toContain('receiveGitHubWebhook');
    expect(fs.readFileSync(path.join(API_DIR, 'threads.gen.ts'), 'utf8')).toContain(
      '// Not a method here: receiveGitHubWebhook. GitHub calls it',
    );
  });
});

describe("the runner's client", () => {
  const dispatch: DispatchRequest = {
    project: 'jugonzal/architect-loop',
    skill: 'loop-build',
    concern: 'command-center/app-clients',
    budget_usd: 2,
    plugin_release: 'v0.4.0',
  };

  it('dispatches through the signed-in fetch, as JSON, and resolves to the session', async () => {
    const session = { id: 'a'.repeat(32), state: 'starting' };
    const service = fakeService({ status: 201, body: session });
    const runner = createRunnerClient({ baseUrl: `${RUNNER}/`, fetch: signedIn(service) });
    const started: Session = await runner.dispatch({ body: dispatch });
    expect(started).toEqual(session);
    expect(service.calls).toHaveLength(1);
    expect(service.calls[0]).toMatchObject({ url: `${RUNNER}/sessions`, method: 'POST', body: dispatch });
    expect(service.calls[0]?.headers.get('Authorization')).toBe('Bearer gho_test');
    expect(service.calls[0]?.headers.get('Content-Type')).toBe('application/json');
    expect(service.calls[0]?.headers.get('Accept')).toBe('application/json');
  });

  it("rejects a refusal with its status and the runner's body, typed by the operation's 409", async () => {
    const refusal: Refusal = {
      refused: 'budget-ceiling',
      message: 'The budget is above the ceiling of $10.',
      pull_requests: [],
      sessions: [],
      ceiling_usd: 10,
    };
    const runner = createRunnerClient({ baseUrl: RUNNER, fetch: signedIn(fakeService({ status: 409, body: refusal })) });
    const error: unknown = await runner.dispatch({ body: { ...dispatch, budget_usd: 50 } }).catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ServiceError);
    const failure = error as ServiceError;
    expect(failure).toMatchObject({ service: 'runner', operation: 'dispatch', kind: 'http', status: 409 });
    expect(failure.message).toBe(`POST ${RUNNER}/sessions answered 409: The budget is above the ceiling of $10.`);
    const body = failure.body as RunnerOperations['dispatch']['responses']['409'];
    expect(body.ceiling_usd).toBe(10);
  });

  it('fills path parameters and sends only the query parameters given', async () => {
    const service = fakeService();
    const runner = createRunnerClient({ baseUrl: RUNNER, fetch: signedIn(service) });
    await runner.listSessions();
    await runner.listSessions({ query: { state: 'all', sponsor: 'octocat', project: undefined } });
    await runner.getSession({ path: { id: 'b'.repeat(32) } });
    await runner.estimate({ query: { skill: 'loop-prove' } });
    expect(service.calls.map((c) => `${c.method} ${c.url}`)).toEqual([
      `GET ${RUNNER}/sessions`,
      `GET ${RUNNER}/sessions?state=all&sponsor=octocat`,
      `GET ${RUNNER}/sessions/${'b'.repeat(32)}`,
      `GET ${RUNNER}/estimates?skill=loop-prove`,
    ]);
    expect(service.calls.every((c) => c.body === undefined && !c.headers.has('Content-Type'))).toBe(true);
  });

  it('accepts only the success status the file declares for the operation', async () => {
    const service = fakeService({ status: 202, body: { id: 'c'.repeat(32), state: 'stopping' } });
    const runner = createRunnerClient({ baseUrl: RUNNER, fetch: signedIn(service) });
    await expect(runner.stopSession({ path: { id: 'c'.repeat(32) } })).resolves.toMatchObject({ state: 'stopping' });
    await expect(runner.getSession({ path: { id: 'c'.repeat(32) } })).rejects.toMatchObject({ kind: 'http', status: 202 });
  });

  it('types a dispatch so it names exactly one of a concern, a loop or an environment (runner-dispatch C3)', () => {
    const onLoop: DispatchRequest = { ...dispatch, skill: 'loop-status', concern: undefined, loop: 'command-center' };
    const { concern: _concern, ...withoutTarget } = dispatch;
    // @ts-expect-error A dispatch that names nothing to run on does not type-check.
    const nothing: DispatchRequest = withoutTarget;
    // @ts-expect-error Nor does one that names both a concern and a loop.
    const both: DispatchRequest = { ...dispatch, loop: 'command-center' };
    expect([onLoop.loop, nothing.project, both.project]).toEqual(['command-center', dispatch.project, dispatch.project]);
  });
});

describe("the threads' client", () => {
  const concern = { ...PROJECT, loop: 'command-center', concern: 'app-clients' };

  it('reads a page of a concern thread, with repeated kinds, and resolves to the typed page', async () => {
    const page = { messages: [{ id: 1, seq: 1, kind: 'milestone', body: 'PR opened' }], next_after: null };
    const service = fakeService({ body: page });
    const threads = createThreadsClient({ baseUrl: THREADS, fetch: signedIn(service) });
    const result = await threads.listConcernMessages({ path: concern, query: { after: 3, kind: ['milestone', 'message'] } });
    const first: Message | undefined = result.messages[0];
    expect(first?.body).toBe('PR opened');
    expect(service.calls[0]?.url).toBe(
      `${THREADS}/projects/jugonzal/architect-loop/loops/command-center/concerns/app-clients/thread/messages` +
        '?after=3&kind=milestone&kind=message',
    );
    expect(service.calls[0]?.headers.get('Authorization')).toBe('Bearer gho_test');
  });

  it('posts a message as JSON, and watches and unmarks with PUT and DELETE and no body', async () => {
    const service = fakeService({ status: 201, body: { id: 7 } });
    const threads = createThreadsClient({ baseUrl: THREADS, fetch: signedIn(service) });
    await threads.postConcernMessage({ path: concern, body: { body: 'Looks right.' } });
    expect(service.calls[0]).toMatchObject({ method: 'POST', body: { body: 'Looks right.' } });
    expect(service.calls[0]?.headers.get('Content-Type')).toBe('application/json');

    const watching = fakeService({ status: 200, body: { watchers: [] } });
    const watcher = createThreadsClient({ baseUrl: THREADS, fetch: signedIn(watching) });
    await watcher.watchLoopThread({ path: { ...PROJECT, loop: 'command-center' } });
    await watcher.unmarkMessageForRecord({ path: { ...PROJECT, message: 7 } });
    expect(watching.calls.map((c) => `${c.method} ${c.url}`)).toEqual([
      `PUT ${THREADS}/projects/jugonzal/architect-loop/loops/command-center/thread/watchers/me`,
      `DELETE ${THREADS}/projects/jugonzal/architect-loop/messages/7/record-marks/me`,
    ]);
    expect(watching.calls.every((c) => c.body === undefined && !c.headers.has('Content-Type'))).toBe(true);
  });

  it('encodes each path parameter, so a value cannot change the path, and refuses a missing one', () => {
    const url = operationUrl(THREADS, THREADS_OPERATIONS.getConcernThread, {
      path: { ...PROJECT, loop: 'a/b', concern: 'c d?e' },
    });
    expect(url).toBe(`${THREADS}/projects/jugonzal/architect-loop/loops/a%2Fb/concerns/c%20d%3Fe/thread`);
    expect(() => operationUrl(THREADS, THREADS_OPERATIONS.getConcernThread, { path: PROJECT })).toThrow(
      'needs its loop path parameter',
    );
  });

  it('signs the person out on a 401 and rejects with the status and a body typed by the operation', async () => {
    const onUnauthorized = jest.fn();
    const answer = { status: 401, body: { error: 'unauthorized', message: 'GitHub did not accept the token' } };
    const threads = createThreadsClient({ baseUrl: THREADS, fetch: signedIn(fakeService(answer), onUnauthorized) });
    const error = await threads.getLoopThread({ path: { ...PROJECT, loop: 'command-center' } }).catch((e: unknown) => e);
    expect(error).toMatchObject({ name: 'ServiceError', kind: 'http', status: 401, body: answer.body });
    expect(onUnauthorized).toHaveBeenCalledTimes(1);
    const body = (error as ServiceError).body as ThreadsOperations['getLoopThread']['responses']['401'];
    expect(body.error).toBe('unauthorized');
  });

  it('reports a success answer that is not JSON', async () => {
    const threads = createThreadsClient({ baseUrl: THREADS, fetch: signedIn(fakeService({ body: '<html>' })) });
    await expect(threads.getVersion()).rejects.toMatchObject({ kind: 'not-json', status: 200 });
  });

  it('calls nothing when nobody is signed in', async () => {
    const service = fakeService();
    const fetch = createSignedInFetch({ getToken: () => null, onUnauthorized: jest.fn(), fetch: service.fetch });
    await expect(createThreadsClient({ baseUrl: THREADS, fetch }).getVersion()).rejects.toBeInstanceOf(NotSignedInError);
    expect(service.calls).toHaveLength(0);
  });
});

describe('a build without a service URL (app-clients C2)', () => {
  const fetch = jest.fn<ReturnType<Fetch>, Parameters<Fetch>>();

  it.each([
    ['runner', () => createRunnerClient({ baseUrl: null, fetch }).getVersion()],
    ['threads', () => createThreadsClient({ baseUrl: undefined, fetch }).getVersion()],
  ])('says the %s URL is missing instead of calling it', async (service, call) => {
    const error = await call().catch((e: unknown) => e);
    expect(error).toMatchObject({ name: 'ServiceError', kind: 'not-configured', service });
    expect((error as Error).message).toBe(serviceNotConfiguredMessage(service));
    expect((error as Error).message).toContain(`${serviceUrlVariable(service)} in app/eas.json`);
    expect(fetch).not.toHaveBeenCalled();
  });
});

describe('projectPath', () => {
  it('splits a project key into the {owner}/{repo} every service keys by (command-center/D48)', () => {
    expect(projectPath('jugonzal/architect-loop')).toEqual({ owner: 'jugonzal', repo: 'architect-loop' });
    expect(() => projectPath('jugonzal/architect-loop/extra' as `${string}/${string}`)).toThrow('owner/repo');
  });
});
