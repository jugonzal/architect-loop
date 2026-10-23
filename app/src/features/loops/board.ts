// What the Loops tab shows, worked out from a status document and nothing else (command-center/D15). Every state,
// reason and fact here is the derivation's, as the loop-status script wrote it with --json: the app never derives a
// state of its own, never renames one, and shows unknown wherever the document does (command-center/D5, D37).
// The screens in this folder only lay these out.

import type {
  Claim,
  Concern,
  ConcernState,
  Evidence,
  Loop,
  LoopState,
  StatusDocument,
  Verdict,
} from '../../api/status';

/**
 * Every state a concern can have, exactly as the schema's concern_state lists them: the rows of the derivation table
 * in loop-status SKILL.md, in its order, plus unknown. The concern page's state strip draws exactly these, and
 * finer detail ("in review", "proving") is the reason line under it, never a state of its own (command-center/D5).
 */
export const CONCERN_STATES = [
  'parked',
  'contradicted',
  'open',
  'blocked',
  'ready',
  'building',
  'merged',
  'shipped',
  'stale',
  'done',
  'unknown',
] as const satisfies readonly ConcernState[];

// Fails to compile if the schema gains a concern state this list does not have.
const everyConcernState: Record<Exclude<ConcernState, (typeof CONCERN_STATES)[number]>, never> = {};
void everyConcernState;

export type BoardSection = {
  state: LoopState;
  title: string;
  /** In full, as a card with each concern and its state; otherwise one line for each loop. */
  full: boolean;
  loops: Loop[];
};

/**
 * The board's sections, in the order the Loops tab shows them (C1): active loops first, in full; then the backlog,
 * one line each; then parked loops. A loop whose state is unknown is shown in full under its own heading, as the
 * terminal board shows it, so the missing fact is in view and the loop is never shown as active (command-center/D37).
 * A loop that is open has no concerns yet, so its card is only its reason and its next step. Done loops come last,
 * one line each. Every loop state is in exactly one section.
 */
const SECTIONS = [
  { state: 'active', title: 'Active', full: true },
  { state: 'unknown', title: 'Unknown', full: true },
  { state: 'open', title: 'Open', full: true },
  { state: 'backlog', title: 'Backlog', full: false },
  { state: 'parked', title: 'Parked', full: false },
  { state: 'done', title: 'Done', full: false },
] as const satisfies readonly Omit<BoardSection, 'loops'>[];

// Fails to compile if the schema gains a loop state with no section.
const everyLoopState: Record<Exclude<LoopState, (typeof SECTIONS)[number]['state']>, never> = {};
void everyLoopState;

/** The board's non-empty sections, in order, each with its loops in the document's order. */
export function boardSections(doc: StatusDocument): BoardSection[] {
  return SECTIONS.map((section) => ({ ...section, loops: doc.loops.filter((loop) => loop.state === section.state) })).filter(
    (section) => section.loops.length > 0,
  );
}

/** The line above the title: how many loops are in each section, such as "1 active · 1 backlog · 1 parked". */
export function boardSummary(sections: readonly BoardSection[]): string {
  return sections.map((section) => `${section.loops.length} ${section.state}`).join(' · ');
}

export function plural(n: number, one: string, many = `${one}s`): string {
  return `${n} ${n === 1 ? one : many}`;
}

export function findLoop(doc: StatusDocument, loopId: string): Loop | undefined {
  return doc.loops.find((loop) => loop.id === loopId);
}

export function findConcern(doc: StatusDocument, loopId: string, concernId: string): { loop: Loop; concern: Concern } | undefined {
  const loop = findLoop(doc, loopId);
  const concern = loop?.concerns.find((c) => c.id === concernId);
  return loop && concern ? { loop, concern } : undefined;
}

// The routes of the Loops tab, and the concern thread that app-threads serves (command-center/D52).

export function loopHref(loopId: string): string {
  return `/loops/${encodeURIComponent(loopId)}`;
}

export function concernHref(loopId: string, concernId: string): string {
  return `${loopHref(loopId)}/concerns/${encodeURIComponent(concernId)}`;
}

export function concernThreadHref(loopId: string, concernId: string): string {
  return `/threads/loops/${encodeURIComponent(loopId)}/concerns/${encodeURIComponent(concernId)}`;
}

/** A commit as the board writes it: its first 7 hex digits, or ? for an evidence line migrated without one. */
export function shortSha(sha: string | null | undefined): string {
  return sha ? sha.slice(0, 7) : '?';
}

/** When the facts were gathered, as the terminal board writes it: 2026-10-20 15:00:00 UTC. */
export function asOf(doc: StatusDocument): string {
  return doc.as_of.replace('T', ' ').replace(/Z$/, ' UTC');
}

/** A claim's latest verdict: its last evidence line, in file order (the schema's rule), or none. */
export function latestEvidence(claim: Claim): Evidence | undefined {
  return claim.evidence[claim.evidence.length - 1];
}

export function latestVerdict(claim: Claim): Verdict | null {
  return latestEvidence(claim)?.verdict ?? null;
}

/** Where an evidence line was proven and the commit it cites: "rung 1 · staging @780d0c5 · 2026-10-18". */
export function citation(line: Evidence): string {
  return `rung ${line.rung} · ${line.environment} @${shortSha(line.commit)} · ${line.date}`;
}

function yesNo(value: boolean | null): string {
  return value === true ? 'yes' : value === false ? 'no' : 'unknown';
}

/** Whether a claim holds now on the concern's ships-to environment, as the document says, unknown included. */
export function currentHolds(claim: Claim, shipsTo: string | null): string {
  if (claim.struck) return 'struck: counts for nothing';
  return `current HOLDS on ${shipsTo ?? 'its ships-to'}: ${yesNo(claim.current_holds)}`;
}

export type Fact = {
  label: string;
  value: string;
  /** A fact that could not be read: whatever rests on it is unknown. */
  missing?: boolean;
};

/** The facts a concern's state came from, as the document's inputs record them, in the terminal's order. */
export function concernFacts(doc: StatusDocument, concern: Concern): Fact[] {
  const { inputs } = concern;
  const facts: Fact[] = [{ label: 'main', value: `@${shortSha(inputs.main)}` }];

  const served = inputs.served;
  if (!served.environment) {
    facts.push({ label: 'served', value: served.error ?? 'the contract has no ships-to' });
  } else if (served.commit) {
    facts.push({
      label: 'served',
      value: `${served.environment} serves @${shortSha(served.commit)} · serves its work: ${yesNo(served.serves)}`,
    });
  } else {
    facts.push({ label: 'served', value: `${served.environment}: ${served.error ?? 'cannot be read'}`, missing: true });
  }

  for (const pr of inputs.prs) {
    const name = pr.repository === doc.project ? `#${pr.number}` : `${pr.repository}#${pr.number}`;
    const merge = pr.merge_commit ? ` · merge @${shortSha(pr.merge_commit)}, on main: ${yesNo(pr.on_main)}` : '';
    facts.push({
      label: 'pr',
      value: `${name} ${pr.state}${pr.draft ? ' (draft)' : ''} · ${pr.head} → ${pr.base} · checks ${pr.checks}${merge}`,
    });
  }

  for (const sha of inputs.commits) facts.push({ label: 'commit', value: `@${shortSha(sha)} carries its trailer` });

  if (inputs.branch) {
    const exists = inputs.branch.exists === true ? 'exists' : inputs.branch.exists === false ? 'absent' : 'unknown';
    facts.push({ label: 'branch', value: `${inputs.branch.name}: ${exists}`, missing: inputs.branch.exists === null });
  }

  for (const fact of inputs.missing ?? []) facts.push({ label: 'missing', value: fact, missing: true });
  return facts;
}
