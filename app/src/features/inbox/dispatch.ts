// What finishing a card starts (command-center/app-inbox C2): the matching skill, through the runner, as a session
// the person sponsors. The runner takes the sponsor from the token that calls it, never from the request
// (command-center/D28), so the dispatch below has no sponsor field: whoever is signed in sponsors what they start.
// Every start costs money (gates: spending), so a card shows the budget first, and nothing here sends anything:
// it only says what would be sent.
//
// - A question starts /loop-design on its concern or loop, naming the question. The skill asks it in the session's
//   thread and the person answers there, so the answer never travels in the dispatch (D3). A gated question also
//   carries the person's typed reason, for the decision's notes (D4, command-center/D60).
// - A ship card starts /loop-ship on its environment, whose final report is the brief (D1). Once the person has
//   deployed, "Deployed" starts it again with `deployed`, for its verification.
// - A record card starts /loop-status's record step on the record's loop, saying what the person said yes to. The
//   step writes its own loop-document PR and merges it under LOOP.md §2.1, as from a terminal (D2).

import type { DispatchRequest, Session } from '../../api/runner.gen';
import type { ProjectKey, QueueItem } from '../../api/status';

/**
 * The release of the skills every dispatch runs (command-center/D17): a tag, never the clone's own plugin/. The
 * app has no way to read which release is current, so it is named here, and the start sheet shows it.
 */
export const PLUGIN_RELEASE = 'v0.4.0';

/** The budget a start sheet offers first, in dollars. The person can change it before anything starts. */
export const DEFAULT_BUDGET_USD = 2;

/** The longest reason a gated question carries, so its dispatch stays inside the runner's 2000 characters. */
export const REASON_MAX = 1500;

/** The skill and the one thing it runs on, as the runner's dispatch names them (runner-dispatch C3). */
export type PlanTarget =
  | { readonly skill: 'loop-design' | 'loop-status'; readonly concern: string }
  | { readonly skill: 'loop-design' | 'loop-status'; readonly loop: string }
  | { readonly skill: 'loop-ship'; readonly environment: string };

export type PlanPurpose = 'answer' | 'brief' | 'verify' | 'record';

/** One start a card can make: what it runs, on what, with which arguments, before the person sets a budget. */
export type SessionPlan = {
  readonly purpose: PlanPurpose;
  readonly target: PlanTarget;
  readonly arguments: string;
  /** The same start as a person would type it in a terminal, which the start sheet shows. */
  readonly command: string;
  /** How a session doing the same work is told by its arguments: exactly these, or the same first word. */
  readonly match: { readonly exact: string } | { readonly first: string };
};

export function targetName(target: PlanTarget): string {
  if ('concern' in target) return target.concern;
  if ('loop' in target) return target.loop;
  return target.environment;
}

function plan(purpose: PlanPurpose, target: PlanTarget, args: string, match: SessionPlan['match']): SessionPlan {
  const command = [`/${target.skill}`, targetName(target), args].filter(Boolean).join(' ');
  return { purpose, target, arguments: args, command, match };
}

function wrongKind(item: QueueItem, expected: string): Error {
  return new Error(`${item.id} is a ${item.kind} item, not a ${expected}`);
}

/**
 * A question card's start: /loop-design on the question's concern (<loop>/<concern>/Q<n>) or on its loop
 * (<loop>/Q<n>). A gated question needs the person's reason, which goes in the decision's notes (D4).
 */
export function answerPlan(item: QueueItem, reason?: string): SessionPlan {
  if (item.kind !== 'question') throw wrongKind(item, 'question');
  const parts = item.detail.ref.split('/');
  const question = parts[parts.length - 1] ?? '';
  let target: PlanTarget;
  if (parts.length === 3 && parts[0] && parts[1]) target = { skill: 'loop-design', concern: `${parts[0]}/${parts[1]}` };
  else if (parts.length === 2 && parts[0]) target = { skill: 'loop-design', loop: parts[0] };
  else throw new Error(`A question is <loop>/Q<n> or <loop>/<concern>/Q<n>, not ${item.detail.ref}`);
  let args = question;
  if (item.gate) {
    const why = reason?.trim().slice(0, REASON_MAX);
    if (!why) throw new Error(`${item.detail.ref} crosses the ${item.gate} gate, so it needs a reason first (D4)`);
    args = `${question} — its answer crosses the ${item.gate} gate. My reason, for the decision's notes: ${why}`;
  }
  return plan('answer', target, args, { first: question });
}

/** Whether a ship card is the one for the deploy itself, which "Deployed" belongs to (command-center/D59). */
export function isDeployItem(item: QueueItem): boolean {
  // A ship item written before addressing crosses no gate yet, and is the only one for its environment.
  return item.kind === 'ship' && (item.gate === null || item.gate === 'deploy');
}

/** A ship card's first start: /loop-ship on its environment, whose final report is the brief (D1). */
export function briefPlan(item: QueueItem): SessionPlan {
  if (item.kind !== 'ship') throw wrongKind(item, 'ship');
  return plan('brief', { skill: 'loop-ship', environment: item.detail.environment }, '', { exact: '' });
}

/** "Deployed": /loop-ship on the environment again, told it is deployed, so it verifies what the environment serves. */
export function deployedPlan(item: QueueItem): SessionPlan {
  if (item.kind !== 'ship') throw wrongKind(item, 'ship');
  return plan('verify', { skill: 'loop-ship', environment: item.detail.environment }, 'deployed', { exact: 'deployed' });
}

/** The loop a loop document belongs to: docs/loops/<loop>/... */
export function loopOfPath(path: string): string | null {
  return /^docs\/loops\/([^/]+)\//.exec(path)?.[1] ?? null;
}

/** A record card's start: /loop-status's record step on the record's loop, with what the person said yes to (D2). */
export function recordPlan(item: QueueItem): SessionPlan {
  if (item.kind !== 'record') throw wrongKind(item, 'record');
  const loop = item.loop ?? loopOfPath(item.detail.path);
  if (!loop) throw new Error(`${item.detail.path} is not a loop document, so no loop can record it`);
  const args = `record: yes to "${item.title.slice(0, 300)}" in ${item.detail.path}`;
  return plan('record', { skill: 'loop-status', loop }, args, { first: 'record:' });
}

/** The runner's dispatch for a plan. It names no sponsor: the runner's is always the caller (command-center/D28). */
export function dispatchRequest(
  sessionPlan: SessionPlan,
  { project, budgetUsd }: { project: ProjectKey; budgetUsd: number },
): DispatchRequest {
  return {
    project,
    ...sessionPlan.target,
    arguments: sessionPlan.arguments,
    budget_usd: budgetUsd,
    plugin_release: PLUGIN_RELEASE,
  };
}

/** Whether a session the runner lists does the work a plan would start, whoever sponsored it. */
export function sameWork(sessionPlan: SessionPlan, session: Session): boolean {
  const { target, match } = sessionPlan;
  if (session.skill !== target.skill) return false;
  const on =
    'concern' in target
      ? session.concern === target.concern
      : 'loop' in target
        ? session.loop === target.loop
        : session.environment === target.environment;
  if (!on) return false;
  const args = session.arguments.trim();
  return 'exact' in match ? args === match.exact : args.split(/\s+/)[0] === match.first;
}

/** A budget as the person types it: a positive number of dollars, with at most two decimals; null otherwise. */
export function parseBudget(text: string): number | null {
  const value = text.trim().replace(/^\$\s*/, '');
  if (!/^\d+(\.\d{1,2})?$/.test(value)) return null;
  const amount = Number(value);
  return amount > 0 ? amount : null;
}

export function formatUsd(amount: number): string {
  return `$${amount.toFixed(2)}`;
}
