// The Environments tab's rows (command-center/app-environments C1), read from the status document alone: one for
// each environment LOOP.md §3 lists, in the document's order (lowest first), with the commit it serves, when that
// was read, and the concerns merged but not yet served. Nothing here keeps or remembers an earlier document, so an
// environment whose read failed is unknown, with the failure, and nothing is filled in for it.
//
// "Merged but not served" is the derivation's own state, never the app's guess (command-center/D5): a concern is
// merged when its work is on main and its ships-to environment does not serve it yet (the loop-status table), so
// it waits on exactly that environment. The derivation queues those concerns as one ship item per environment,
// which the inbox shows as the ship card; a row names that item so the tab can link to the card rather than
// duplicate it.

import type { Concern, Loop, StatusDocument } from '../../api/status';

/** A concern, as a row names it. */
export type ConcernLine = {
  /** <loop>/<concern>. */
  readonly ref: string;
  readonly title: string;
};

export type EnvironmentRow = {
  /** The LOOP.md §3 row's name, such as staging/app. */
  readonly name: string;
  /** The commit it serves, or null when the read failed. */
  readonly served: string | null;
  /** Why the read failed, or null when it did not. */
  readonly error: string | null;
  /** When the status document's facts were gathered, which is when this environment was read (UTC). */
  readonly readAt: string;
  /**
   * The concerns merged that ship to this environment and that it does not serve yet. Null when the environment
   * could not be read: then nobody can say, and the row must not say "none".
   */
  readonly waiting: readonly ConcernLine[] | null;
  /** The concerns whose work is on main and that ship here, where whether it serves them could not be read. */
  readonly unread: readonly ConcernLine[];
  /** The ids of the ship items waiting on this environment: the inbox's ship cards for it. */
  readonly shipItems: readonly string[];
};

function line(loop: Loop, concern: Concern): ConcernLine {
  return { ref: `${loop.id}/${concern.id}`, title: concern.title };
}

/** Whether any of the concern's work is on main: a commit with its trailer, or a pull request merged into main. */
function workOnMain(concern: Concern): boolean {
  return (
    concern.inputs.commits.length > 0 ||
    concern.inputs.prs.some((pr) => pr.state === 'merged' && pr.on_main === true)
  );
}

export function environmentRows(doc: StatusDocument): EnvironmentRow[] {
  const concerns = doc.loops.flatMap((loop) => loop.concerns.map((concern) => ({ loop, concern })));
  return doc.environments.map((env) => {
    const known = env.error === null && typeof env.served === 'string';
    const shipsHere = concerns.filter(({ concern }) => concern.contract.ships_to === env.name);
    return {
      name: env.name,
      served: known ? env.served : null,
      error: known ? null : (env.error ?? 'the served commit is missing from the status document'),
      readAt: doc.as_of,
      waiting: known
        ? shipsHere.filter(({ concern }) => concern.state === 'merged').map(({ loop, concern }) => line(loop, concern))
        : null,
      unread: shipsHere
        .filter(
          ({ concern }) =>
            concern.state === 'unknown' && concern.inputs.served.serves === null && workOnMain(concern),
        )
        .map(({ loop, concern }) => line(loop, concern)),
      shipItems: doc.queue
        .filter((item) => item.kind === 'ship' && item.detail.environment === env.name)
        .map((item) => item.id),
    };
  });
}

/** A commit as the board writes it: its first seven hex digits. */
export function shortSha(sha: string): string {
  return sha.slice(0, 7);
}

/**
 * How long ago a time was, relative to now: "40 s ago", "1 min ago". A time ahead of the phone's clock reads as
 * just now, and a time that cannot be parsed is given as written.
 */
export function ago(asOf: string, now: number): string {
  const at = Date.parse(asOf);
  if (Number.isNaN(at)) return asOf;
  const seconds = Math.floor((now - at) / 1000);
  if (seconds < 5) return 'just now';
  if (seconds < 60) return `${seconds} s ago`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} h ago`;
  const days = Math.floor(hours / 24);
  return `${days} ${days === 1 ? 'day' : 'days'} ago`;
}

/** When a row was read, as the artboard writes it: "read 40 s ago". */
export function readAgo(asOf: string, now: number): string {
  return `read ${ago(asOf, now)}`;
}
