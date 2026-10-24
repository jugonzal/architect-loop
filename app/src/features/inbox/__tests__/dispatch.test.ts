// command-center/app-inbox C2, the dispatches: finishing a card starts the matching skill through the runner. A
// question starts /loop-design on its concern or loop (D3), a ship card /loop-ship on its environment for the brief
// and again with "deployed" for the verification (D1), and a record card /loop-status's record step on its loop
// (D2). The sponsor is never a field of the request: the runner names whoever's token starts it
// (command-center/D28), and the person sees the budget before anything starts (the concern's effects).

import type { Session } from '../../../api/runner.gen';
import type { QueueItem } from '../../../api/status';
import { loadStatusFixture } from '../../../api/statusFixtures';
import {
  answerPlan,
  briefPlan,
  DEFAULT_BUDGET_USD,
  deployedPlan,
  dispatchRequest,
  formatUsd,
  isDeployItem,
  parseBudget,
  PLUGIN_RELEASE,
  REASON_MAX,
  recordPlan,
  sameWork,
} from '../dispatch';

const doc = loadStatusFixture('board');

function item(id: string): QueueItem {
  const found = doc.queue.find((i) => i.id === id);
  if (!found) throw new Error(`no item ${id}`);
  return found;
}

function gated(id: string, gate: string): QueueItem {
  return { ...item(id), gate };
}

function session(over: Partial<Session>): Session {
  return {
    id: 's_1',
    project: 'example/reports',
    skill: 'loop-design',
    concern: null,
    loop: null,
    environment: null,
    arguments: '',
    model: 'claude-test',
    sponsor: 'ana',
    budget_usd: 2,
    plugin_release: PLUGIN_RELEASE,
    branch: 'main',
    state: 'running',
    outcome: null,
    created_at: '2026-10-24T10:00:00Z',
    started_at: null,
    ended_at: null,
    spend: null,
    pull_requests: [],
    final_message: null,
    ...over,
  };
}

describe('a question card (D3, D4)', () => {
  it("starts /loop-design on the question's concern, naming the question, and carries no answer", () => {
    const plan = answerPlan(item('report-pipeline/dashboard/Q1'));
    expect(plan.target).toEqual({ skill: 'loop-design', concern: 'report-pipeline/dashboard' });
    expect(plan.arguments).toBe('Q1');
    expect(plan.command).toBe('/loop-design report-pipeline/dashboard Q1');
  });

  it("starts /loop-design on the loop for a loop's own question", () => {
    const plan = answerPlan(item('report-pipeline/Q2'));
    expect(plan.target).toEqual({ skill: 'loop-design', loop: 'report-pipeline' });
    expect(plan.command).toBe('/loop-design report-pipeline Q2');
  });

  it("carries a gated question's typed reason for the decision's notes, and needs one", () => {
    const question = gated('report-pipeline/dashboard/Q1', 'spending');
    expect(() => answerPlan(question)).toThrow(/needs a reason/);
    expect(() => answerPlan(question, '   ')).toThrow(/needs a reason/);
    const plan = answerPlan(question, '  Cheaper to run for a year  ');
    expect(plan.arguments).toBe(
      "Q1 — its answer crosses the spending gate. My reason, for the decision's notes: Cheaper to run for a year",
    );
    expect(plan.arguments.length).toBeLessThanOrEqual(2000);
    expect(answerPlan(question, 'x'.repeat(REASON_MAX + 50)).arguments.length).toBeLessThanOrEqual(2000);
  });

  it('ignores a reason for an ungated question', () => {
    expect(answerPlan(item('report-pipeline/dashboard/Q1'), 'because').arguments).toBe('Q1');
  });
});

describe('a ship card (D1, command-center/D59)', () => {
  it('starts /loop-ship on its environment for the brief, and again with "deployed" for the verification', () => {
    const ship = item('ship/production');
    expect(briefPlan(ship)).toMatchObject({
      target: { skill: 'loop-ship', environment: 'production' },
      arguments: '',
      command: '/loop-ship production',
    });
    expect(deployedPlan(ship)).toMatchObject({
      target: { skill: 'loop-ship', environment: 'production' },
      arguments: 'deployed',
      command: '/loop-ship production deployed',
    });
  });

  it('says "deployed" only on the item that crosses deploy, not on one split out for another gate', () => {
    expect(isDeployItem({ ...item('ship/production'), gate: 'deploy' })).toBe(true);
    // Written before addressing, a ship item crosses no gate yet, and is the only one for its environment.
    expect(isDeployItem({ ...item('ship/production'), gate: null })).toBe(true);
    expect(isDeployItem(item('ship/production'))).toBe(false); // the fixture's is split out for its secrets
  });
});

describe('a record card (D2)', () => {
  it("starts /loop-status's record step on the record's loop, saying what the person said yes to", () => {
    const plan = recordPlan(item('record/report-pipeline/job-contract'));
    expect(plan.target).toEqual({ skill: 'loop-status', loop: 'report-pipeline' });
    expect(plan.arguments).toBe(
      'record: yes to "Add a Shipped note to job-contract" in docs/loops/report-pipeline/job-contract.md',
    );
  });

  it("takes the loop from the record's path when the item spans loops", () => {
    const record = { ...item('record/report-pipeline/job-contract'), loop: null };
    expect(recordPlan(record).target).toEqual({ skill: 'loop-status', loop: 'report-pipeline' });
  });
});

describe('the dispatch', () => {
  it('names the project, the budget and the release, and never a sponsor (command-center/D28)', () => {
    const body = dispatchRequest(answerPlan(item('report-pipeline/dashboard/Q1')), {
      project: 'example/reports',
      budgetUsd: 2.5,
    });
    expect(body).toEqual({
      project: 'example/reports',
      skill: 'loop-design',
      concern: 'report-pipeline/dashboard',
      arguments: 'Q1',
      budget_usd: 2.5,
      plugin_release: PLUGIN_RELEASE,
    });
    expect(Object.keys(body)).not.toContain('sponsor');
  });

  it('runs a tagged release of the skills, never a branch (command-center/D17)', () => {
    expect(PLUGIN_RELEASE).toMatch(/^v[0-9]+\.[0-9]+\.[0-9]+$/);
  });

  it('starts from a budget the person can change, and refuses one that is not a positive amount', () => {
    expect(DEFAULT_BUDGET_USD).toBeGreaterThan(0);
    expect(parseBudget('2')).toBe(2);
    expect(parseBudget(' 1.50 ')).toBe(1.5);
    expect(parseBudget('$3')).toBe(3);
    for (const bad of ['', '0', '-1', 'abc', '1.234', 'Infinity', '1e3']) expect(parseBudget(bad)).toBeNull();
    expect(formatUsd(2)).toBe('$2.00');
    expect(formatUsd(0.846)).toBe('$0.85');
  });

  it('knows a session that already does the same work, newest first, whoever sponsored it', () => {
    const brief = briefPlan(item('ship/production'));
    const deployed = deployedPlan(item('ship/production'));
    const ship = session({ skill: 'loop-ship', environment: 'production' });
    expect(sameWork(brief, ship)).toBe(true);
    expect(sameWork(deployed, ship)).toBe(false);
    expect(sameWork(deployed, { ...ship, arguments: 'deployed' })).toBe(true);
    expect(sameWork(brief, { ...ship, environment: 'staging' })).toBe(false);

    const answer = answerPlan(item('report-pipeline/dashboard/Q1'));
    const design = session({ concern: 'report-pipeline/dashboard', arguments: 'Q1' });
    expect(sameWork(answer, design)).toBe(true);
    expect(sameWork(answer, { ...design, arguments: 'Q1 — its answer crosses the spending gate. My reason: x' })).toBe(true);
    expect(sameWork(answer, { ...design, arguments: 'Q10' })).toBe(false);
    expect(sameWork(answer, { ...design, skill: 'loop-build' })).toBe(false);

    const record = recordPlan(item('record/report-pipeline/job-contract'));
    expect(sameWork(record, session({ skill: 'loop-status', loop: 'report-pipeline', arguments: record.arguments }))).toBe(true);
    expect(sameWork(record, session({ skill: 'loop-status', loop: 'report-pipeline', arguments: '' }))).toBe(false);
  });
});
