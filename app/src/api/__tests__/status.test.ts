import { execFileSync } from 'child_process';
import * as fs from 'fs';
import * as path from 'path';

import { createSignedInFetch, type Fetch } from '../fetch';
import {
  createStatusClient,
  parseStatus,
  statusUrl,
  StatusError,
  SUPPORTED_SCHEMA_VERSION,
  type QueueItem,
  type StatusDocument,
} from '../status';
import {
  createFixtureStatusClient,
  loadStatusFixture,
  STATUS_FIXTURES_DIR,
  statusFixtureNames,
} from '../statusFixtures';

const GENERATOR = path.resolve(__dirname, '../generate-status-types.js');
const SCHEMA = path.resolve(__dirname, '../../../../plugin/skills/loop-status/scripts/status.schema.json');

const BASE = 'https://status-123456789012.us-east1.run.app';

/** A fake status service: answers GET /projects/{owner}/{repo}/status with a fixture, and records each call. */
function fakeStatusService(doc: unknown, status = 200) {
  const calls: { url: string; headers: Headers }[] = [];
  const fetch: Fetch = async (url, init = {}) => {
    calls.push({ url, headers: new Headers(init.headers) });
    return new Response(typeof doc === 'string' ? doc : JSON.stringify(doc), {
      status,
      headers: { 'Content-Type': 'application/json' },
    });
  };
  return { fetch, calls };
}

describe('the typed status client is generated from the schema (command-center/D15)', () => {
  it('matches the schema it was generated from', () => {
    // Runs the generator as `npm run check:status` does, in plain Node. Fails when the schema changes without
    // `npm run generate:status`, which would let the app read a shape the schema no longer promises.
    const out = execFileSync(process.execPath, [GENERATOR, '--check'], { encoding: 'utf8' });
    expect(out).toContain('matches the schema');
  });

  it('reads the schema the loop-status script writes against', () => {
    expect(fs.readFileSync(GENERATOR, 'utf8')).toContain("'../../../plugin/skills/loop-status/scripts/status.schema.json'");
    const schema = JSON.parse(fs.readFileSync(SCHEMA, 'utf8'));
    expect(schema.properties.schema_version.const).toBe(SUPPORTED_SCHEMA_VERSION);
  });
});

describe('the fixture stubs', () => {
  it('load every fixture in tests/fixtures/status', () => {
    const files = fs.readdirSync(STATUS_FIXTURES_DIR).filter((f) => f.endsWith('.json'));
    expect(statusFixtureNames()).toEqual(files.map((f) => f.replace(/\.json$/, '')).sort());
    expect(statusFixtureNames()).toEqual(expect.arrayContaining(['board', 'empty', 'unknown']));
    for (const name of statusFixtureNames()) {
      const doc = loadStatusFixture(name);
      expect(doc.schema_version).toBe(SUPPORTED_SCHEMA_VERSION);
    }
  });

  it('serve a fixture through the same interface as the real client', async () => {
    const client = createFixtureStatusClient('board');
    const doc = await client.getStatus();
    expect(client.project).toBe(doc.project);
    expect(doc.loops.length).toBeGreaterThan(0);
  });

  it('hand each call its own copy', async () => {
    const client = createFixtureStatusClient('board');
    const first = await client.getStatus();
    first.loops.length = 0;
    expect((await client.getStatus()).loops.length).toBeGreaterThan(0);
  });

  it('type the queue so a screen can narrow an item by its kind', () => {
    const doc: StatusDocument = loadStatusFixture('board');
    const kinds = doc.queue.map((item: QueueItem) => item.kind);
    expect(new Set(kinds)).toEqual(
      new Set(['question', 'review', 'ship', 'record', 'proof', 'contradiction', 'refused_pr']),
    );
    const question = doc.queue.find((item) => item.kind === 'question');
    if (!question || question.kind !== 'question') throw new Error('the board fixture has a question');
    // Compiles only because the generated union ties detail's shape to kind.
    expect(typeof question.detail.question).toBe('string');
  });
});

describe('the status client', () => {
  it('builds the service URL from the project key (command-center/D48)', () => {
    expect(statusUrl(BASE, 'jugonzal/architect-loop')).toBe(`${BASE}/projects/jugonzal/architect-loop/status`);
    expect(statusUrl(`${BASE}/`, 'jugonzal/architect-loop')).toBe(`${BASE}/projects/jugonzal/architect-loop/status`);
  });

  it('reads each fixture from a fake service, through the signed-in fetch', async () => {
    for (const name of statusFixtureNames()) {
      const doc = loadStatusFixture(name);
      const service = fakeStatusService(doc);
      const fetch = createSignedInFetch({ getToken: () => 'gho_test', onUnauthorized: jest.fn(), fetch: service.fetch });
      const client = createStatusClient({ baseUrl: BASE, project: doc.project as `${string}/${string}`, fetch });
      await expect(client.getStatus()).resolves.toEqual(doc);
      expect(service.calls).toHaveLength(1);
      expect(service.calls[0]?.url).toBe(statusUrl(BASE, doc.project as `${string}/${string}`));
      expect(service.calls[0]?.headers.get('Authorization')).toBe('Bearer gho_test');
    }
  });

  it('refuses a schema version this build does not read, instead of guessing', async () => {
    const doc = { ...loadStatusFixture('empty'), schema_version: 2 };
    const client = createStatusClient({ baseUrl: BASE, project: 'example/new-project', fetch: fakeStatusService(doc).fetch });
    await expect(client.getStatus()).rejects.toMatchObject({ name: 'StatusError', kind: 'schema-version' });
  });

  it('refuses a document for another project', () => {
    expect(() => parseStatus(loadStatusFixture('board'), 'jugonzal/architect-loop')).toThrow(StatusError);
  });

  it('reports an HTTP failure with its status', async () => {
    const client = createStatusClient({ baseUrl: BASE, project: 'example/reports', fetch: fakeStatusService('{}', 503).fetch });
    await expect(client.getStatus()).rejects.toMatchObject({ kind: 'http', status: 503 });
  });

  it('reports an answer that is not JSON', async () => {
    const client = createStatusClient({ baseUrl: BASE, project: 'example/reports', fetch: fakeStatusService('<html>', 200).fetch });
    await expect(client.getStatus()).rejects.toMatchObject({ kind: 'not-json' });
  });
});
