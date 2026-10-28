// What Needs you shows (command-center/app-inbox C1), worked out from the status document and the signed-in
// person's GitHub login alone. Who an item waits on and who else sees it are the derivation's (waits_on and
// visible_to, which addressing fills, command-center/D58 to D63): the app only matches them to the person, and
// never works out an address of its own.
//
// - An item that waits on the person is theirs. Its card lets them finish it when its kind has one (question,
//   review, ship, record); a proof, a contradiction or a refused loop-document PR shows read-only, with the command
//   to run (command-center/D34, D40).
// - An item that waits on someone else shows read-only to the loop's members (command-center/D10), and to no one
//   else.
// - An item that waits on no one named shows read-only to everyone, so a gap in the addressing is never hidden; the
//   board's drift says why no one is named.
//
// Each list is sorted by how many concerns the item unblocks, longest first, as the document's queue is.

import type { QueueItem, QueueKind, StatusDocument } from '../../api/status';

/** The kinds a person finishes from a card (command-center/D34), in the schema's order. */
export const ACTIONABLE_KINDS = ['question', 'review', 'ship', 'record'] as const satisfies readonly QueueKind[];

/** The kinds shown read-only, with the command to run (command-center/D34, D40, D76, D77). */
export const READ_ONLY_KINDS = ['proof', 'fact', 'stuck', 'contradiction', 'refused_pr'] as const satisfies readonly QueueKind[];

/** A kind as a card's label names it. */
export const KIND_LABELS: Record<QueueKind, string> = {
  question: 'Question',
  review: 'Review',
  ship: 'Ship',
  record: 'Record',
  proof: 'Proof',
  fact: 'Fact',
  stuck: 'Stuck',
  contradiction: 'Contradiction',
  refused_pr: 'Refused PR',
};

export type InboxEntry = {
  readonly item: QueueItem;
  /** Whether the person can finish it here: it waits on them and its kind has a card. */
  readonly actionable: boolean;
  /** The one person it waits on, or null when no one is named. */
  readonly waitsOn: string | null;
};

export type Inbox = {
  /** What waits on the signed-in person: "Needs you". */
  readonly mine: readonly InboxEntry[];
  /** What waits on someone else in a loop the person is a member of, read-only. */
  readonly others: readonly InboxEntry[];
  /** What waits on no one named, read-only. */
  readonly unaddressed: readonly InboxEntry[];
};

/** Whether two GitHub logins are the same person. GitHub ignores case in logins, so this does too. */
export function sameLogin(a: string | null | undefined, b: string | null | undefined): boolean {
  return typeof a === 'string' && typeof b === 'string' && a.toLowerCase() === b.toLowerCase();
}

function hasCard(kind: QueueKind): boolean {
  return (ACTIONABLE_KINDS as readonly QueueKind[]).includes(kind);
}

/** The items, most unblocking first. The sort is stable, so ties keep the document's order. */
export function byUnblocks(items: readonly QueueItem[]): QueueItem[] {
  return items
    .map((item, index) => ({ item, index }))
    .sort((a, b) => b.item.unblocks.length - a.item.unblocks.length || a.index - b.index)
    .map(({ item }) => item);
}

export function inboxFor(doc: StatusDocument, login: string): Inbox {
  const mine: InboxEntry[] = [];
  const others: InboxEntry[] = [];
  const unaddressed: InboxEntry[] = [];
  for (const item of byUnblocks(doc.queue)) {
    const waitsOn = item.waits_on ?? null;
    if (waitsOn === null) {
      unaddressed.push({ item, actionable: false, waitsOn });
    } else if (sameLogin(waitsOn, login)) {
      mine.push({ item, actionable: hasCard(item.kind), waitsOn });
    } else if (item.visible_to.some((member) => sameLogin(member, login))) {
      others.push({ item, actionable: false, waitsOn });
    }
  }
  return { mine, others, unaddressed };
}

export function findItem(doc: StatusDocument, id: string): QueueItem | undefined {
  return doc.queue.find((item) => item.id === id);
}

/** One item as the person sees it, from the lists above; undefined when they do not see it. */
export function entryFor(doc: StatusDocument, login: string, id: string): InboxEntry | undefined {
  const inbox = inboxFor(doc, login);
  return [...inbox.mine, ...inbox.others, ...inbox.unaddressed].find((entry) => entry.item.id === id);
}

// The routes: one card, under the Needs you tab, and the session thread that app-threads serves
// (command-center/D52). An item's id can hold slashes and a #, so it is one encoded segment.

export function itemHref(id: string): string {
  return `/inbox/${encodeURIComponent(id)}`;
}

export function sessionThreadHref(sessionId: string): string {
  return `/threads/sessions/${encodeURIComponent(sessionId)}`;
}

/** A commit as the board writes it: its first 7 hex digits, or ? when there is none. */
export function shortSha(sha: string | null | undefined): string {
  return sha ? sha.slice(0, 7) : '?';
}

/** When the facts were gathered, as the terminal board writes it: 2026-10-20 15:00:00 UTC. */
export function asOf(doc: StatusDocument): string {
  return doc.as_of.replace('T', ' ').replace(/Z$/, ' UTC');
}
