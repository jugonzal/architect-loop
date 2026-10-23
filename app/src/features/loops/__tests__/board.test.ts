// app-loops-board C1 and C2, the part that is not drawing: what the Loops tab takes from a status document. It
// reads the schema and the schema's own fixtures (tests/fixtures/status/), so a change to either changes these
// tests with it (command-center/D15).

import * as fs from 'fs';
import * as path from 'path';

import type { ConcernState, StatusDocument } from '../../../api/status';
import { loadStatusFixture, statusFixtureNames } from '../../../api/statusFixtures';
import {
  asOf,
  boardSections,
  boardSummary,
  CONCERN_STATES,
  concernFacts,
  concernHref,
  concernThreadHref,
  findConcern,
  latestEvidence,
  loopHref,
} from '../board';

const SCHEMA = path.resolve(__dirname, '../../../../../plugin/skills/loop-status/scripts/status.schema.json');
const schema = JSON.parse(fs.readFileSync(SCHEMA, 'utf8'));
const defs = schema.$defs ?? schema.definitions;

const fixtures: Record<string, StatusDocument> = Object.fromEntries(
  statusFixtureNames().map((name) => [name, loadStatusFixture(name)]),
);

describe("the states are exactly the derivation's (command-center/D5)", () => {
  it("lists the schema's concern states, in the schema's order, and nothing else", () => {
    expect([...CONCERN_STATES]).toEqual(defs.concern_state.enum);
  });

  it('has fixtures that cover every one of them, so the screen tests below see each', () => {
    const seen = new Set<ConcernState>();
    for (const doc of Object.values(fixtures)) for (const loop of doc.loops) for (const c of loop.concerns) seen.add(c.state);
    expect([...seen].sort()).toEqual([...CONCERN_STATES].sort());
  });
});

describe('the board (C1)', () => {
  it('puts active loops first, then the backlog, then parked loops', () => {
    const sections = boardSections(fixtures.board!);
    expect(sections.map((s) => s.state)).toEqual(['active', 'open', 'backlog', 'parked', 'done']);
    expect(sections.map((s) => [s.state, s.full])).toEqual([
      ['active', true],
      ['open', true],
      ['backlog', false],
      ['parked', false],
      ['done', false],
    ]);
    expect(sections[0]!.loops.map((l) => l.id)).toEqual(['report-pipeline']);
  });

  it('shows a loop whose state is unknown under its own heading, never as active (command-center/D37)', () => {
    const sections = boardSections(fixtures.unknown!);
    expect(sections.map((s) => s.state)).toEqual(['active', 'unknown', 'parked']);
    const unknown = sections.find((s) => s.state === 'unknown')!;
    expect(unknown.full).toBe(true);
    expect(unknown.loops.map((l) => l.id)).toEqual(['search']);
    expect(sections.find((s) => s.state === 'active')!.loops.map((l) => l.id)).not.toContain('search');
  });

  it('places every loop of every fixture in exactly one section', () => {
    for (const doc of Object.values(fixtures)) {
      const placed = boardSections(doc).flatMap((s) => s.loops.map((l) => l.id));
      expect(placed.sort()).toEqual(doc.loops.map((l) => l.id).sort());
    }
  });

  it('has no section for a project with no loops', () => {
    expect(boardSections(fixtures.empty!)).toEqual([]);
  });

  it('counts each section above the title', () => {
    expect(boardSummary(boardSections(fixtures.board!))).toBe('1 active · 1 open · 1 backlog · 1 parked · 1 done');
  });

  it('writes when the facts were gathered as the terminal board does', () => {
    expect(asOf(fixtures.board!)).toBe('2026-10-20 15:00:00 UTC');
  });
});

describe('a concern (C2)', () => {
  it('finds a concern by its loop and id', () => {
    expect(findConcern(fixtures.board!, 'report-pipeline', 'worker')?.concern.state).toBe('contradicted');
    expect(findConcern(fixtures.board!, 'report-pipeline', 'nope')).toBeUndefined();
    expect(findConcern(fixtures.board!, 'nope', 'worker')).toBeUndefined();
  });

  it("takes a claim's latest verdict from its last evidence line", () => {
    const { concern } = findConcern(fixtures.board!, 'report-pipeline', 'worker')!;
    expect(latestEvidence(concern.claims[1]!)).toMatchObject({ verdict: 'CONTRADICTS', commit: '780d0c5' });
    expect(latestEvidence(findConcern(fixtures.board!, 'report-pipeline', 'retries')!.concern.claims[0]!)).toBeUndefined();
  });

  it('lists the facts its state came from, including every fact that could not be read', () => {
    const doc = fixtures.unknown!;
    for (const loop of doc.loops) {
      for (const concern of loop.concerns.filter((c) => c.state === 'unknown')) {
        const facts = concernFacts(doc, concern);
        expect(concern.inputs.missing?.length).toBeGreaterThan(0);
        for (const missing of concern.inputs.missing ?? []) {
          expect(facts).toContainEqual({ label: 'missing', value: missing, missing: true });
        }
      }
    }
    const queue = findConcern(doc, 'report-pipeline', 'queue')!.concern;
    expect(concernFacts(doc, queue)).toContainEqual({
      label: 'served',
      value: 'staging: GET https://staging.example.com/version timed out after 10 s',
      missing: true,
    });
  });

  it('says whether the ships-to environment serves its work', () => {
    const doc = fixtures.board!;
    const queue = findConcern(doc, 'report-pipeline', 'queue')!.concern;
    expect(concernFacts(doc, queue)).toContainEqual({ label: 'served', value: 'staging serves @780d0c5 · serves its work: yes' });
    const scheduler = findConcern(doc, 'report-pipeline', 'scheduler')!.concern;
    expect(concernFacts(doc, scheduler)).toContainEqual({ label: 'served', value: 'production serves @d1b62ed · serves its work: no' });
  });
});

describe('the routes', () => {
  it('open a loop and a concern under the Loops tab, and the concern thread where app-threads serves it (command-center/D52)', () => {
    expect(loopHref('report-pipeline')).toBe('/loops/report-pipeline');
    expect(concernHref('report-pipeline', 'worker')).toBe('/loops/report-pipeline/concerns/worker');
    expect(concernThreadHref('report-pipeline', 'worker')).toBe('/threads/loops/report-pipeline/concerns/worker');
  });
});
