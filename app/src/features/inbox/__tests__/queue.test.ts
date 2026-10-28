// command-center/app-inbox C1, worked out from the status document alone: "Needs you" lists every item waiting on
// the signed-in person, most unblocking first. The question, review, ship and record items are cards the person can
// finish; proofs, contradictions and refused loop-document PRs show read-only, with the command to run
// (command-center/D34, D40). Items that wait on someone else show read-only to the loop's members (command-center/D10).

import type { QueueItem, StatusDocument } from '../../../api/status';
import { loadStatusFixture, statusFixtureNames } from '../../../api/statusFixtures';
import {
  ACTIONABLE_KINDS,
  byUnblocks,
  findItem,
  inboxFor,
  itemHref,
  KIND_LABELS,
  READ_ONLY_KINDS,
  sameLogin,
  sessionThreadHref,
} from '../queue';

const ids = (entries: readonly { item: QueueItem }[]) => entries.map((e) => e.item.id);

function withQueue(doc: StatusDocument, queue: QueueItem[]): StatusDocument {
  return { ...doc, queue };
}

describe('the kinds (command-center/D34, D76, D77)', () => {
  it("has a card for exactly the schema's first four kinds and shows the other five read-only", () => {
    const doc = loadStatusFixture('board');
    expect([...ACTIONABLE_KINDS]).toEqual(['question', 'review', 'ship', 'record']);
    expect([...READ_ONLY_KINDS]).toEqual(['proof', 'fact', 'stuck', 'contradiction', 'refused_pr']);
    // Every kind the fixtures hold has a label, and the two lists cover every one of them.
    const kinds = new Set(doc.queue.map((item) => item.kind));
    for (const kind of kinds) {
      expect(KIND_LABELS[kind]).toBeTruthy();
      expect([...ACTIONABLE_KINDS, ...READ_ONLY_KINDS]).toContain(kind);
    }
  });
});

describe('Needs you (C1)', () => {
  it('lists every item waiting on the signed-in person, most unblocking first', () => {
    const doc = loadStatusFixture('board');
    const inbox = inboxFor(doc, 'ana');
    expect(ids(inbox.mine)).toEqual([
      'report-pipeline/worker/C2',
      'report-pipeline/dashboard/Q1',
      'example/reports#14',
      'report-pipeline/queue/C2',
      'example/reports#16',
      'record/report-pipeline/job-contract',
      'report-pipeline/Q2',
    ]);
    const counts = inbox.mine.map((e) => e.item.unblocks.length);
    expect(counts).toEqual([...counts].sort((a, b) => b - a));
    // ana is a member too, so she sees carla's ship item, read-only.
    expect(ids(inbox.others)).toEqual(['ship/production']);
    expect(inbox.unaddressed).toEqual([]);
  });

  it('sorts by how many concerns an item unblocks even when the document does not, keeping its order for ties', () => {
    const doc = loadStatusFixture('board');
    const shuffled = withQueue(doc, [...doc.queue].reverse());
    const order = ids(inboxFor(shuffled, 'ana').mine);
    expect(order[0]).toBe('report-pipeline/worker/C2');
    const counts = inboxFor(shuffled, 'ana').mine.map((e) => e.item.unblocks.length);
    expect(counts).toEqual([2, 1, 1, 1, 0, 0, 0]);
    // Ties keep the order they had in the document (here, reversed).
    expect(order.slice(1, 4)).toEqual(['report-pipeline/queue/C2', 'example/reports#14', 'report-pipeline/dashboard/Q1']);
    expect(byUnblocks(doc.queue).map((item) => item.id)).toEqual(doc.queue.map((item) => item.id));
  });

  it('lets the person act on the four kinds with cards, and shows the other three read-only', () => {
    const inbox = inboxFor(loadStatusFixture('board'), 'ana');
    expect(inbox.mine.map((e) => [e.item.kind, e.actionable])).toEqual([
      ['contradiction', false],
      ['question', true],
      ['review', true],
      ['proof', false],
      ['refused_pr', false],
      ['record', true],
      ['question', true],
    ]);
  });

  it("gives a gate's holder the item waiting on them, and nothing of a loop they are not a member of", () => {
    const inbox = inboxFor(loadStatusFixture('board'), 'carla');
    expect(ids(inbox.mine)).toEqual(['ship/production']);
    expect(inbox.mine[0]?.actionable).toBe(true);
    // carla holds the secrets gate but is not one of report-pipeline's members, so she sees nothing else.
    expect(inbox.others).toEqual([]);
  });

  it("shows a member every item of the loop, read-only, with whom it waits on (command-center/D10)", () => {
    const doc = loadStatusFixture('board');
    const inbox = inboxFor(doc, 'ben');
    expect(inbox.mine).toEqual([]);
    // Every item of report-pipeline, ben's loop, in the same order as for the people it waits on.
    expect(ids(inbox.others)).toEqual(byUnblocks(doc.queue).map((item) => item.id));
    expect(inbox.others.every((e) => !e.actionable)).toBe(true);
    expect(inbox.others.find((e) => e.item.id === 'ship/production')?.waitsOn).toBe('carla');
  });

  it('shows someone who is neither waited on nor a member nothing', () => {
    const inbox = inboxFor(loadStatusFixture('board'), 'dora');
    expect([...inbox.mine, ...inbox.others, ...inbox.unaddressed]).toEqual([]);
  });

  it('matches the signed-in login without regard to case, as GitHub does (command-center/D62)', () => {
    expect(sameLogin('Ana', 'ana')).toBe(true);
    expect(sameLogin('ana', 'anab')).toBe(false);
    expect(sameLogin(null, 'ana')).toBe(false);
    expect(ids(inboxFor(loadStatusFixture('board'), 'ANA').mine)).toHaveLength(7);
    expect(ids(inboxFor(loadStatusFixture('board'), 'Ben').others)).toHaveLength(8);
  });

  it('shows an item that waits on no one named read-only to everyone, so it is not hidden', () => {
    const inbox = inboxFor(loadStatusFixture('unknown'), 'ana');
    expect(inbox.mine).toEqual([]);
    expect(inbox.others).toEqual([]);
    expect(ids(inbox.unaddressed)).toEqual(['report-pipeline/dashboard/Q1']);
    expect(inbox.unaddressed[0]).toMatchObject({ actionable: false, waitsOn: null });
  });

  it('places every item of every fixture in at most one list, for the person it waits on in exactly one', () => {
    for (const name of statusFixtureNames()) {
      const doc = loadStatusFixture(name);
      for (const item of doc.queue) {
        const person = item.waits_on ?? 'someone';
        const inbox = inboxFor(doc, person);
        const lists = [inbox.mine, inbox.others, inbox.unaddressed].filter((list) => ids(list).includes(item.id));
        expect(lists).toHaveLength(1);
        if (item.waits_on) expect(ids(inbox.mine)).toContain(item.id);
      }
    }
  });

  it('is empty for a project with nothing queued', () => {
    const inbox = inboxFor(loadStatusFixture('empty'), 'ana');
    expect([...inbox.mine, ...inbox.others, ...inbox.unaddressed]).toEqual([]);
  });
});

describe('the routes', () => {
  it('opens one card under the Needs you tab by its id, and the session thread where app-threads serves it (command-center/D52)', () => {
    expect(itemHref('example/reports#14')).toBe('/inbox/example%2Freports%2314');
    expect(itemHref('report-pipeline/dashboard/Q1')).toBe('/inbox/report-pipeline%2Fdashboard%2FQ1');
    expect(sessionThreadHref('s_123')).toBe('/threads/sessions/s_123');
  });

  it('finds an item by its id, and nothing once it has left the queue', () => {
    const doc = loadStatusFixture('board');
    expect(findItem(doc, 'ship/production')?.kind).toBe('ship');
    expect(findItem(doc, 'ship/staging')).toBeUndefined();
  });
});
