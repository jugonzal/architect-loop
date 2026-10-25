// command-center/app-agents C2, the rows and the dispatch: "Can start now" lists the builds and proofs the status
// document says an agent can start (ready, shipped and stale concerns, and the proofs a blocked concern's needs
// wait on), each with the dispatch that starts it on the concern, the runner's estimate (command-center/D23) and a
// budget the person confirms.

import * as fs from 'fs';
import * as path from 'path';

import type { EstimateAnswer } from '../../../api/runner.gen';
import { ServiceError } from '../../../api/service';
import { loadStatusFixture, statusFixtureNames } from '../../../api/statusFixtures';
import {
  argumentsOf,
  dispatchFor,
  estimateLong,
  estimateShort,
  parseBudget,
  releaseLine,
  rowAction,
  rowButton,
  rowHeadline,
  startFailure,
  startRows,
  suggestedBudget,
} from '../starts';

const answer = (estimate: EstimateAnswer['estimate'], skill: EstimateAnswer['skill'] = 'loop-build'): EstimateAnswer => ({
  skill,
  model: 'claude-opus-5-5',
  estimate,
  plugin_release: 'v0.7.0',
});

describe('the rows', () => {
  it('are the builds and proofs the status document lists, in its order, with each concern and its state', () => {
    const rows = startRows(loadStatusFixture('board'));
    expect(rows.map((r) => [r.concern, r.state, r.action, r.skill, r.arguments])).toEqual([
      ['report-pipeline/exporter', 'ready', 'build', 'loop-build', ''],
      ['search/indexer', 'ready', 'build', 'loop-build', ''],
      ['report-pipeline/queue', 'shipped', 'prove', 'loop-prove', 'staging'],
      ['report-pipeline/metrics', 'stale', 'prove', 'loop-prove', 'staging'],
    ]);
    expect(rows[0]?.title).toBe('Reports can be exported as CSV');
  });

  it('leave out designs, whose questions a session started here could not ask the owner', () => {
    const doc = loadStatusFixture('board');
    expect(doc.agents_can_start.some((s) => s.action === 'design')).toBe(true);
    expect(startRows(doc).some((r) => r.concern === 'search/ranking')).toBe(false);
  });

  it('are empty when the document lists nothing to start, in every fixture that lists none', () => {
    for (const name of statusFixtureNames()) {
      const doc = loadStatusFixture(name);
      if (doc.agents_can_start.length === 0) expect(startRows(doc)).toEqual([]);
    }
  });

  it('keep a proof the document lists for a concern it does not describe, without a state', () => {
    const doc = loadStatusFixture('board');
    doc.agents_can_start = [{ concern: 'other/need', action: 'prove', command: '/loop-prove other/need staging/runner' }];
    const [row] = startRows(doc);
    expect(row).toMatchObject({ concern: 'other/need', state: null, title: null, arguments: 'staging/runner' });
    expect(rowHeadline(row!)).toBe('other/need');
  });

  it("read as the artboard writes them: what is ready or stale, what the start does, and the button's label", () => {
    const [exporter, , queue, metrics] = startRows(loadStatusFixture('board'));
    expect([exporter, queue, metrics].map((r) => [rowHeadline(r!), rowAction(r!), rowButton(r!)])).toEqual([
      ['report-pipeline/exporter is ready', 'build', 'Start'],
      ['report-pipeline/queue is shipped', 'prove on staging', 'Prove'],
      ['report-pipeline/metrics is stale', 're-prove on staging', 'Re-prove'],
    ]);
  });
});

describe("a command's arguments", () => {
  it('are what it passes after the concern', () => {
    expect(argumentsOf('/loop-prove a/b staging/app', 'loop-prove', 'a/b')).toBe('staging/app');
    expect(argumentsOf('/loop-build a/b', 'loop-build', 'a/b')).toBe('');
  });

  it('are nothing when the command is not the skill on the concern', () => {
    expect(argumentsOf('/loop-prove a/bc staging', 'loop-prove', 'a/b')).toBe('');
    expect(argumentsOf('/loop-build a/b staging', 'loop-prove', 'a/b')).toBe('');
  });
});

describe('the dispatch', () => {
  it("starts the row's skill on its concern, with its arguments, the confirmed budget and the estimate's release", () => {
    const [exporter, , queue] = startRows(loadStatusFixture('board'));
    expect(dispatchFor(exporter!, 'example/reports', 3, 'v0.7.0')).toEqual({
      project: 'example/reports',
      skill: 'loop-build',
      concern: 'report-pipeline/exporter',
      budget_usd: 3,
      plugin_release: 'v0.7.0',
    });
    expect(dispatchFor(queue!, 'example/reports', 0.5, 'v0.12.3')).toEqual({
      project: 'example/reports',
      skill: 'loop-prove',
      concern: 'report-pipeline/queue',
      arguments: 'staging',
      budget_usd: 0.5,
      plugin_release: 'v0.12.3',
    });
  });

  it('names no sponsor: the runner takes it from the caller’s token (command-center/D28)', () => {
    const [exporter] = startRows(loadStatusFixture('board'));
    expect(Object.keys(dispatchFor(exporter!, 'example/reports', 1, 'v0.7.0'))).not.toContain('sponsor');
  });

  it("says the release the runner's estimate named, or that there is none to start (latest-release C2)", () => {
    expect(releaseLine(answer(null))).toBe('It runs the skills of release v0.7.0.');
    expect(releaseLine({ ...answer(null), plugin_release: null })).toBe(
      'The runner names no release of the skills, so it cannot start yet.',
    );
  });
});

describe('the estimate', () => {
  it("is the runner's, labelled as an estimate, with where it comes from (D23)", () => {
    const found = answer({ kind: 'estimate', usd: 1.6, wall_clock_s: 14 * 60, sessions: 7 });
    expect(estimateShort(found)).toBe('est. $1.60');
    expect(estimateLong(found)).toBe(
      'Estimated $1.60 and 14 min: the median of the last 7 sessions of loop-build on claude-opus-5-5.',
    );
    expect(estimateLong(answer({ kind: 'estimate', usd: 0.4, wall_clock_s: 90, sessions: 1 }))).toContain(
      'the median of the last session of',
    );
  });

  it('says there is none yet for a pairing the runner has not measured, and asks for a budget', () => {
    expect(estimateShort(answer(null, 'loop-prove'))).toBe('no estimate yet');
    expect(estimateLong(answer(null, 'loop-prove'))).toBe(
      'No estimate yet: no loop-prove session on claude-opus-5-5 has been measured. Set the budget yourself.',
    );
  });
});

describe('the budget', () => {
  it('starts from the estimate rounded up to a whole dollar, at least $1, and from nothing without one', () => {
    expect(suggestedBudget({ kind: 'estimate', usd: 1.6, wall_clock_s: 1, sessions: 3 })).toBe('2');
    expect(suggestedBudget({ kind: 'estimate', usd: 0.4, wall_clock_s: 1, sessions: 3 })).toBe('1');
    expect(suggestedBudget({ kind: 'estimate', usd: 3, wall_clock_s: 1, sessions: 3 })).toBe('3');
    expect(suggestedBudget(null)).toBe('');
  });

  it('is dollars as the person types them, with at most two decimals', () => {
    expect(parseBudget('2')).toEqual({ ok: true, usd: 2 });
    expect(parseBudget(' $2.50 ')).toEqual({ ok: true, usd: 2.5 });
    expect(parseBudget('.75')).toEqual({ ok: true, usd: 0.75 });
    expect(parseBudget('3.')).toEqual({ ok: true, usd: 3 });
  });

  it('is refused when it is empty, not an amount, or nothing', () => {
    expect(parseBudget('')).toEqual({ ok: false, reason: 'Set a budget for the session.' });
    for (const text of ['two', '2.505', '-1', '1e3', '2,50']) {
      expect(parseBudget(text)).toEqual({ ok: false, reason: 'A budget is an amount in dollars, such as 2 or 2.50.' });
    }
    expect(parseBudget('0')).toEqual({ ok: false, reason: 'A budget must be more than $0.' });
    expect(parseBudget('0.00')).toEqual({ ok: false, reason: 'A budget must be more than $0.' });
  });
});

describe('a start that did not start', () => {
  it("gives the runner's refusal, which names the cap, the ceiling, the pull request or the session", () => {
    const refusal = new ServiceError('runner', 'dispatch', 'http', 'POST … answered 409', {
      status: 409,
      body: {
        refused: 'budget-ceiling',
        message: "a budget of $50.00 is above the runner's ceiling of $10.00 (session-runner D8)",
        pull_requests: [],
        sessions: [],
        ceiling_usd: 10,
      },
    });
    expect(startFailure(refusal)).toBe(
      "The runner refused it: a budget of $50.00 is above the runner's ceiling of $10.00 (session-runner D8)",
    );
  });

  it("gives the runner's problem for any other answer, and the error itself otherwise", () => {
    const unknown = new ServiceError('runner', 'dispatch', 'http', 'POST … answered 422', {
      status: 422,
      body: { error: 'unknown-release', message: 'v0.4.0 is not a release tag of example/reports' },
    });
    expect(startFailure(unknown)).toBe(
      'The runner did not start it (422): v0.4.0 is not a release tag of example/reports',
    );
    expect(startFailure(new ServiceError('runner', 'dispatch', 'http', 'POST … answered 502', { status: 502 }))).toBe(
      'POST … answered 502',
    );
    expect(startFailure(new Error('network down'))).toBe('network down');
  });
});

describe('no release of its own (latest-release C2)', () => {
  it('names no release tag anywhere in the tab’s code: the runner’s estimate names it', () => {
    const sources = featureSources(path.join(__dirname, '..'));
    expect(sources.length).toBeGreaterThan(0);
    for (const [name, text] of sources) expect([name, text.match(/v[0-9]+\.[0-9]+\.[0-9]+/g)]).toEqual([name, null]);
  });
});

/** Each source file of a feature, by name, beside its text; its tests are left out. */
function featureSources(dir: string): [string, string][] {
  return fs
    .readdirSync(dir)
    .filter((name) => /\.tsx?$/.test(name))
    .map((name) => [name, fs.readFileSync(path.join(dir, name), 'utf8')]);
}
