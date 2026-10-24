// The Agents tab's running sessions (command-center/app-agents C1), read from the runner alone: every session that is
// starting, running or stopping, with its skill, what it runs on, its sponsor, how long it has run, and its spend
// against its budget. The runner publishes a session's spend at least every 10 seconds while it runs
// (command-center/D23), and the tab reads the list again every REFRESH_MS, so what it shows is never more than one
// read behind. Every spend figure is the runner's estimate and is labelled as one (D23). A budget is a target a
// session may pass by one model response (D21), so a spend above it is shown as over, not as an error.
//
// The session slots come from the runner too: its config sets how many sessions one sponsor may run at once, 3 by
// default (D22), and the runner counts every active session of the sponsor's against it, whatever its project.

import type { Session, SessionList, Skill } from '../../api/runner.gen';

/** How often the tab reads the sessions again while it is open: well within C1's 10 seconds. */
export const REFRESH_MS = 5_000;

/** The states the runner lists as active: they hold a slot until they end. */
const ACTIVE: readonly Session['state'][] = ['starting', 'running', 'stopping'];

export function isActive(session: Session): boolean {
  return ACTIVE.includes(session.state);
}

/** What a session runs on: its concern, its loop or its environment, exactly one of which the runner sets. */
export function targetOf(session: Session): string {
  return session.concern ?? session.loop ?? session.environment ?? '';
}

/** The two letters on a session's tile, after the artboard's LB, LP and LD. */
const BADGES: Record<Skill, string> = {
  'loop-build': 'LB',
  'loop-prove': 'LP',
  'loop-design': 'LD',
  'loop-status': 'ST',
  'loop-ship': 'SH',
};

export function skillBadge(skill: Skill): string {
  return BADGES[skill] ?? skill.replace(/^loop-/, '').slice(0, 2).toUpperCase();
}

/** A length of time as the artboard writes it: "40 s", "18 min", "1 h 05 min". */
export function duration(seconds: number): string {
  const s = Math.max(0, Math.floor(seconds));
  if (s < 60) return `${s} s`;
  const minutes = Math.floor(s / 60);
  if (minutes < 60) return `${minutes} min`;
  const hours = Math.floor(minutes / 60);
  return `${hours} h ${String(minutes % 60).padStart(2, '0')} min`;
}

/**
 * How long a session has run: from when its job started (or, before that, when it was dispatched) until it ended,
 * or until now. A start ahead of the phone's clock reads as 0, and a time that cannot be parsed as null.
 */
export function elapsedSeconds(session: Session, now: number): number | null {
  const from = Date.parse(session.started_at ?? session.created_at);
  const to = session.ended_at ? Date.parse(session.ended_at) : now;
  if (Number.isNaN(from) || Number.isNaN(to)) return null;
  return Math.max(0, (to - from) / 1000);
}

export function elapsed(session: Session, now: number): string {
  const seconds = elapsedSeconds(session, now);
  return seconds === null ? 'time unknown' : duration(seconds);
}

/** When the list was read, by the phone's clock: "read just now", "read 12 s ago". */
export function readAgo(at: number, now: number): string {
  const seconds = (now - at) / 1000;
  return seconds < 5 ? 'read just now' : `read ${duration(seconds)} ago`;
}

/** Dollars as the artboard writes them: $1.10. */
export function money(usd: number): string {
  return `$${usd.toFixed(2)}`;
}

export type SpendView = {
  /** The line beside the bar, such as "est. $1.10 / $2.50". */
  readonly text: string;
  /** The same, in words, for a screen reader. */
  readonly label: string;
  /** How much of the budget the bar fills, from 0 to 1. */
  readonly fraction: number;
  /** Whether the estimate has passed the budget, as a session may by one response (D21). */
  readonly over: boolean;
};

export function spendView(session: Session): SpendView {
  const budget = money(session.budget_usd);
  if (session.spend === null) {
    return {
      text: `no spend yet / ${budget}`,
      label: `no spend published yet, of a ${budget} budget`,
      fraction: 0,
      over: false,
    };
  }
  const usd = session.spend.usd;
  const fraction = session.budget_usd > 0 ? Math.min(1, Math.max(0, usd / session.budget_usd)) : 1;
  return {
    text: `est. ${money(usd)} / ${budget}`,
    label: `estimated spend ${money(usd)} of a ${budget} budget`,
    fraction,
    over: usd > session.budget_usd,
  };
}

/** Only a session's sponsor may stop it, and only before it is already stopping (the runner checks both). */
export function canStop(session: Session, login: string): boolean {
  return session.sponsor === login && (session.state === 'starting' || session.state === 'running');
}

/** The sessions this project's tab shows: the active ones, newest first, as the runner orders them. */
export function runningSessions(list: SessionList, project: string): Session[] {
  return list.sessions.filter((session) => isActive(session) && session.project === project);
}

export type Slots = { readonly used: number; readonly cap: number };

/** The person's session slots: their active sessions on any project, against the runner's cap (D22). */
export function slotsOf(list: SessionList, login: string): Slots {
  return {
    used: list.sessions.filter((session) => session.sponsor === login && isActive(session)).length,
    cap: list.cap_per_sponsor,
  };
}

export function slotsLine({ used, cap }: Slots): string {
  if (used >= cap) return `You sponsor all ${cap} of your session slots, so a start waits until one ends.`;
  return `You sponsor ${used} of your ${cap} session slots.`;
}

/** The line above the title: how many run, and what they have spent so far, as an estimate. */
export function runningLine(sessions: readonly Session[]): string {
  const spent = sessions.reduce((sum, session) => sum + (session.spend?.usd ?? 0), 0);
  return `${sessions.length} running · est. ${money(spent)} so far`;
}

/** What the runner says of a session that is not simply running. */
export function stateLabel(session: Session): string | null {
  if (session.state === 'starting') return 'STARTING';
  if (session.state === 'stopping') return 'STOPPING';
  return null;
}
