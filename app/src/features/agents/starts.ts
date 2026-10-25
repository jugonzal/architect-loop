// "Can start now" on the Agents tab (command-center/app-agents C2): the work the status service says an agent can
// start without a person (the document's agents_can_start), each with the dispatch that starts it, the runner's
// estimate of what it costs, and a budget the person confirms.
//
// The rows are the builds and the proofs: concerns the derivation marks ready (build), shipped or stale (prove),
// and the proofs that would meet a blocked concern's needs (command-center/D50). The document also lists designs of
// incomplete contracts, which the tab leaves out: a /loop-design session asks the owner its questions one at a time
// and records only the answers given in its conversation, which a session started from here has no way to reach
// (app-inbox D3 starts one from the question card, which opens its thread).
//
// Each start is a runner dispatch on the concern, sponsored by the signed-in person: the runner takes the sponsor
// from the caller's token, never from the request (command-center/D28), and refuses a budget above its ceiling, a
// start past the sponsor's cap, and a build on a concern that is already held (runner-dispatch C2).
//
// The release of the skills a start runs, never a clone's own plugin/ (command-center/D17), is the one the runner's
// estimate names: the newest release tag of the project (latest-release C2, command-center/D68). The tab holds no
// release of its own, so a tag the owner cuts reaches the next start with no new build, and the confirmation shows
// the tag it sends.

import type { DispatchRequest, Estimate, EstimateAnswer, Refusal } from '../../api/runner.gen';
import { ServiceError } from '../../api/service';
import type { Concern, ConcernState, StatusDocument } from '../../api/status';
import { duration, money } from './sessions';

const SKILL_OF = { build: 'loop-build', prove: 'loop-prove' } as const;

export type StartAction = keyof typeof SKILL_OF;
export type StartSkill = (typeof SKILL_OF)[StartAction];

export type StartRow = {
  /** The status document's command for it, such as /loop-prove report-pipeline/queue staging: unique per row. */
  readonly command: string;
  /** <loop>/<concern>. */
  readonly concern: string;
  /** The concern's title and state, or null when the document does not list the concern itself. */
  readonly title: string | null;
  readonly state: ConcernState | null;
  readonly action: StartAction;
  readonly skill: StartSkill;
  /** What the command passes after the concern, such as the environment to prove on; empty when nothing. */
  readonly arguments: string;
};

/** What a command passes to its skill after the concern: the rest of `/<skill> <concern> <arguments>`. */
export function argumentsOf(command: string, skill: string, concern: string): string {
  const head = `/${skill} ${concern}`;
  if (command.trim() === head) return '';
  return command.startsWith(`${head} `) ? command.slice(head.length).trim() : '';
}

export function startRows(doc: StatusDocument): StartRow[] {
  const concerns = new Map<string, Concern>(
    doc.loops.flatMap((loop) => loop.concerns.map((concern) => [`${loop.id}/${concern.id}`, concern] as const)),
  );
  const rows: StartRow[] = [];
  for (const start of doc.agents_can_start) {
    if (start.action !== 'build' && start.action !== 'prove') continue;
    const skill = SKILL_OF[start.action];
    const concern = concerns.get(start.concern);
    rows.push({
      command: start.command,
      concern: start.concern,
      title: concern?.title ?? null,
      state: concern?.state ?? null,
      action: start.action,
      skill,
      arguments: argumentsOf(start.command, skill, start.concern),
    });
  }
  return rows;
}

/** The row's first line, as the artboard writes it: "onboarding/welcome is ready". */
export function rowHeadline(row: StartRow): string {
  return row.state ? `${row.concern} is ${row.state}` : row.concern;
}

/** What the start does: "build", "prove on staging", or "re-prove on staging" for a stale concern. */
export function rowAction(row: StartRow): string {
  if (row.action === 'build') return 'build';
  const verb = row.state === 'stale' ? 're-prove' : 'prove';
  return row.arguments ? `${verb} on ${row.arguments}` : verb;
}

/** The row's button: Start for a build, Prove or Re-prove for a proof, as the artboard labels them. */
export function rowButton(row: StartRow): string {
  if (row.action === 'build') return 'Start';
  return row.state === 'stale' ? 'Re-prove' : 'Prove';
}

/** The estimate beside a row: "est. $2.00", or that there is none yet for the skill on its model. */
export function estimateShort(answer: EstimateAnswer): string {
  return answer.estimate ? `est. ${money(answer.estimate.usd)}` : 'no estimate yet';
}

/** Where the estimate comes from, in a sentence, for the start's confirmation (command-center/D23). */
export function estimateLong(answer: EstimateAnswer): string {
  const { estimate } = answer;
  if (!estimate) {
    return `No estimate yet: no ${answer.skill} session on ${answer.model} has been measured. Set the budget yourself.`;
  }
  const sessions = estimate.sessions === 1 ? 'the last session' : `the last ${estimate.sessions} sessions`;
  return (
    `Estimated ${money(estimate.usd)} and ${duration(estimate.wall_clock_s)}: the median of ${sessions} of ` +
    `${answer.skill} on ${answer.model}.`
  );
}

/** The release a start would run, in a sentence for its confirmation, or why there is none to run. */
export function releaseLine(answer: EstimateAnswer): string {
  return answer.plugin_release
    ? `It runs the skills of release ${answer.plugin_release}.`
    : 'The runner names no release of the skills, so it cannot start yet.';
}

/**
 * The budget the confirmation starts from: the estimate rounded up to a whole dollar, at least $1, or nothing when
 * there is no estimate, so the person types one. The person sees it and confirms it, or changes it, every time.
 */
export function suggestedBudget(estimate: Estimate | null | undefined): string {
  return estimate ? String(Math.max(1, Math.ceil(estimate.usd))) : '';
}

export type Budget = { ok: true; usd: number } | { ok: false; reason: string };

/** A budget as the person types it: dollars, with at most two decimals, and more than nothing. */
export function parseBudget(text: string): Budget {
  const value = text.trim().replace(/^\$\s*/, '');
  if (value === '') return { ok: false, reason: 'Set a budget for the session.' };
  if (!/^(\d+(\.\d{0,2})?|\.\d{1,2})$/.test(value)) {
    return { ok: false, reason: 'A budget is an amount in dollars, such as 2 or 2.50.' };
  }
  const usd = Number(value);
  if (!(usd > 0)) return { ok: false, reason: 'A budget must be more than $0.' };
  return { ok: true, usd };
}

/**
 * The dispatch that starts a row's work with a confirmed budget, on the release its estimate named. The runner names
 * the sponsor from the token.
 */
export function dispatchFor(row: StartRow, project: string, budgetUsd: number, release: string): DispatchRequest {
  return {
    project,
    skill: row.skill,
    concern: row.concern,
    ...(row.arguments ? { arguments: row.arguments } : {}),
    budget_usd: budgetUsd,
    plugin_release: release,
  };
}

function isRefusal(body: unknown): body is Refusal {
  return typeof body === 'object' && body !== null && typeof (body as Refusal).refused === 'string';
}

function problemOf(body: unknown): string | null {
  const message = (body as { message?: unknown } | null)?.message;
  return typeof message === 'string' && message ? message : null;
}

/** Why a start did not start, in the runner's words where it gave any. */
export function startFailure(error: unknown): string {
  if (error instanceof ServiceError) {
    if (error.kind === 'http' && error.status === 409 && isRefusal(error.body)) {
      return `The runner refused it: ${error.body.message}`;
    }
    if (error.kind === 'http') {
      const problem = problemOf(error.body);
      return problem ? `The runner did not start it (${error.status}): ${problem}` : error.message;
    }
  }
  return error instanceof Error ? error.message : String(error);
}
