// command-center/app-environments C1, the rows: one for each environment the status document lists (LOOP.md §3,
// lowest first), with the commit it serves, when that was read, and the concerns merged but not yet served. An
// environment whose read failed is unknown, with the failure, and nothing is filled in for it.

import type { StatusDocument } from '../../../api/status';
import { loadStatusFixture, statusFixtureNames } from '../../../api/statusFixtures';
import { environmentRows, readAgo, shortSha } from '../rows';

const SECOND = 1000;
const MINUTE = 60 * SECOND;
const HOUR = 60 * MINUTE;
const DAY = 24 * HOUR;

function row(doc: StatusDocument, name: string) {
  const found = environmentRows(doc).find((r) => r.name === name);
  if (!found) throw new Error(`no row for ${name}`);
  return found;
}

const refs = (lines: readonly { ref: string }[] | null) => (lines === null ? null : lines.map((l) => l.ref));

describe('the Environments rows', () => {
  it('has one row for each environment in the document, in its order, for every fixture', () => {
    for (const name of statusFixtureNames()) {
      const doc = loadStatusFixture(name);
      expect(environmentRows(doc).map((r) => r.name)).toEqual(doc.environments.map((e) => e.name));
    }
  });

  it('gives a known environment the commit it serves and when the facts were read', () => {
    const doc = loadStatusFixture('board');
    const production = row(doc, 'production');
    expect(production.served).toBe('d1b62eda1e9ba70d07976e477aa8f0784d87df81');
    expect(production.error).toBeNull();
    expect(production.readAt).toBe(doc.as_of);
  });

  it("lists the concerns merged but not served: the derivation's merged state, for the environment they ship to", () => {
    const doc = loadStatusFixture('board');
    // scheduler is merged and ships to production, which serves d1b62ed, without it.
    expect(refs(row(doc, 'production').waiting)).toEqual(['report-pipeline/scheduler']);
    expect(row(doc, 'production').waiting?.[0]?.title).toBe(
      doc.loops[0]?.concerns.find((c) => c.id === 'scheduler')?.title,
    );
    // staging serves queue, worker and metrics, and retries is not merged, so nothing waits for it.
    expect(refs(row(doc, 'staging').waiting)).toEqual([]);
    // main serves whatever is on main.
    expect(refs(row(doc, 'main').waiting)).toEqual([]);
  });

  it("names the ship item for an environment, which the inbox shows as the ship card, and none for the others", () => {
    const doc = loadStatusFixture('board');
    expect(row(doc, 'production').shipItems).toEqual(['ship/production']);
    expect(row(doc, 'staging').shipItems).toEqual([]);
    expect(row(doc, 'main').shipItems).toEqual([]);
  });

  it('says unknown, with the failure, for an environment whose read failed, and fills nothing in', () => {
    const doc = loadStatusFixture('unknown');
    const staging = row(doc, 'staging');
    expect(staging.served).toBeNull();
    expect(staging.error).toBe('GET https://staging.example.com/version timed out after 10 s');
    // Nobody can say what is merged but not served there, so the row says nothing rather than "nothing waits".
    expect(staging.waiting).toBeNull();
    // queue's work is on main, and whether staging serves it cannot be read: the row names it.
    expect(refs(staging.unread)).toEqual(['report-pipeline/queue']);

    const production = row(doc, 'production');
    expect(production.served).toBeNull();
    expect(production.error).toBe('LOOP.md §3 has no served-commit command for production');
    expect(production.waiting).toBeNull();
    // dashboard, invoices and indexer ship to production, but none of them has work on main.
    expect(refs(production.unread)).toEqual([]);

    // main was read, and is known.
    expect(row(doc, 'main').served).toBe('db5da19ad45cbf9c3a78298855471e4cdc6dc291');
    expect(row(doc, 'main').waiting).toEqual([]);
  });

  it('never fills an unknown environment in from a merged concern, even if the document had one', () => {
    // The derivation cannot call a concern merged where the served commit is unknown; if a document ever did, the
    // row still says unknown rather than list what it cannot know.
    const doc = loadStatusFixture('board');
    const production = doc.environments.find((e) => e.name === 'production')!;
    production.served = null;
    production.error = 'GET https://production.example.com/version answered 503';
    const r = row(doc, 'production');
    expect(r.served).toBeNull();
    expect(r.error).toBe('GET https://production.example.com/version answered 503');
    expect(r.waiting).toBeNull();
  });

  it("shows a local row the status service cannot reach as unknown (command-center/D53, D56)", () => {
    const doc = loadStatusFixture('unknown');
    doc.environments.splice(1, 0, {
      name: 'local/status',
      served: null,
      error: 'the row names localhost, which the status service cannot read',
    });
    const names = environmentRows(doc).map((r) => r.name);
    expect(names.slice(0, 2)).toEqual(['main', 'local/status']);
    const local = row(doc, 'local/status');
    expect(local.served).toBeNull();
    expect(local.error).toBe('the row names localhost, which the status service cannot read');
    expect(local.waiting).toBeNull();
  });

  it('has no rows when the document lists no environments', () => {
    const doc = loadStatusFixture('empty');
    doc.environments = [];
    expect(environmentRows(doc)).toEqual([]);
  });
});

describe('when a row was read', () => {
  const asOf = '2026-10-20T15:00:00Z';
  const at = Date.parse(asOf);

  it.each([
    [0, 'read just now'],
    [4 * SECOND, 'read just now'],
    [40 * SECOND, 'read 40 s ago'],
    [59 * SECOND, 'read 59 s ago'],
    [60 * SECOND, 'read 1 min ago'],
    [59 * MINUTE + 59 * SECOND, 'read 59 min ago'],
    [HOUR, 'read 1 h ago'],
    [23 * HOUR, 'read 23 h ago'],
    [DAY, 'read 1 day ago'],
    [3 * DAY + 5 * HOUR, 'read 3 days ago'],
  ])('%d ms after the facts were gathered: %s', (elapsed, expected) => {
    expect(readAgo(asOf, at + elapsed)).toBe(expected);
  });

  it('says just now when the phone is behind the service, rather than a time in the future', () => {
    expect(readAgo(asOf, at - 5 * MINUTE)).toBe('read just now');
  });

  it('gives the time as written when it cannot be parsed', () => {
    expect(readAgo('yesterday-ish', at)).toBe('read yesterday-ish');
  });
});

describe('a short commit', () => {
  it('is its first seven hex digits, as the board writes it', () => {
    expect(shortSha('d1b62eda1e9ba70d07976e477aa8f0784d87df81')).toBe('d1b62ed');
    expect(shortSha('d1b62ed')).toBe('d1b62ed');
  });
});
