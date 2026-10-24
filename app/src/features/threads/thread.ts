// What a thread screen shows and sends, worked out from the threads service's answers (services/threads/openapi.yaml,
// through the client app-clients generates, command-center/D55) and nothing else. A thread holds messages, never
// facts: nothing here changes a loop's state, and a "record this?" mark is a note to people (command-center/D36).
// Only the /loop-design session that accepting a mark dispatches writes anything to the repository (C2).
//
// The screens in this folder only lay these out.

import type { DispatchRequest, Refusal, Session } from '../../api/runner.gen';
import { projectPath, ServiceError } from '../../api/service';
import type { ProjectKey } from '../../api/status';
import type { Message, MessagePage, NewMessage, Thread, ThreadsClient, ThreadsOperations } from '../../api/threads.gen';

/** One of the three threads a project has for each loop, concern and session. */
export type ThreadRef =
  | { scope: 'loop'; loop: string }
  | { scope: 'concern'; loop: string; concern: string }
  | { scope: 'session'; session: string };

// The routes app-threads serves, exactly as command-center/D52 names them: the threads API's paths without the
// project, since a build serves one project. app-inbox and app-loops-board link to these.

export function loopThreadHref(loop: string): string {
  return `/threads/loops/${encodeURIComponent(loop)}`;
}

export function concernThreadHref(loop: string, concern: string): string {
  return `${loopThreadHref(loop)}/concerns/${encodeURIComponent(concern)}`;
}

export function sessionThreadHref(session: string): string {
  return `/threads/sessions/${encodeURIComponent(session)}`;
}

export function threadHref(ref: ThreadRef): string {
  switch (ref.scope) {
    case 'loop':
      return loopThreadHref(ref.loop);
    case 'concern':
      return concernThreadHref(ref.loop, ref.concern);
    case 'session':
      return sessionThreadHref(ref.session);
  }
}

/**
 * Where Back goes when a thread was opened with nothing behind it, as from a link: a loop's or a concern's page on
 * the Loops tab, or the Agents tab for a session.
 */
export function backTarget(ref: ThreadRef): { href: string; label: string } {
  switch (ref.scope) {
    case 'loop':
      return { href: `/loops/${encodeURIComponent(ref.loop)}`, label: ref.loop };
    case 'concern':
      return {
        href: `/loops/${encodeURIComponent(ref.loop)}/concerns/${encodeURIComponent(ref.concern)}`,
        label: ref.concern,
      };
    case 'session':
      return { href: '/agents', label: 'Agents' };
  }
}

/** The loop a thread belongs to, when the thread itself says: a session's is its session's, from the runner. */
export function threadLoop(ref: ThreadRef, session: Session | null): string | null {
  if (ref.scope !== 'session') return ref.loop;
  return recordTarget(ref, session)?.loop ?? null;
}

/** One thread's calls, bound to its scope and the build's project. */
export type ThreadCalls = {
  get(): Promise<Thread>;
  page(query: { after?: number; limit?: number }): Promise<MessagePage>;
  post(message: NewMessage): Promise<Message>;
  watch(): Promise<Thread>;
  unwatch(): Promise<Thread>;
  mark(message: number): Promise<Message>;
  unmark(message: number): Promise<Message>;
};

export function threadCalls(client: ThreadsClient, project: ProjectKey, ref: ThreadRef): ThreadCalls {
  const base = projectPath(project);
  const marks = {
    mark: (message: number) => client.markMessageForRecord({ path: { ...base, message } }),
    unmark: (message: number) => client.unmarkMessageForRecord({ path: { ...base, message } }),
  };
  switch (ref.scope) {
    case 'loop': {
      const path: ThreadsOperations['getLoopThread']['request']['path'] = { ...base, loop: ref.loop };
      return {
        get: () => client.getLoopThread({ path }),
        page: (query) => client.listLoopMessages({ path, query }),
        post: (body) => client.postLoopMessage({ path, body }),
        watch: () => client.watchLoopThread({ path }),
        unwatch: () => client.unwatchLoopThread({ path }),
        ...marks,
      };
    }
    case 'concern': {
      const path: ThreadsOperations['getConcernThread']['request']['path'] = {
        ...base,
        loop: ref.loop,
        concern: ref.concern,
      };
      return {
        get: () => client.getConcernThread({ path }),
        page: (query) => client.listConcernMessages({ path, query }),
        post: (body) => client.postConcernMessage({ path, body }),
        watch: () => client.watchConcernThread({ path }),
        unwatch: () => client.unwatchConcernThread({ path }),
        ...marks,
      };
    }
    case 'session': {
      const path: ThreadsOperations['getSessionThread']['request']['path'] = { ...base, session: ref.session };
      return {
        get: () => client.getSessionThread({ path }),
        page: (query) => client.listSessionMessages({ path, query }),
        post: (body) => client.postSessionMessage({ path, body }),
        watch: () => client.watchSessionThread({ path }),
        unwatch: () => client.unwatchSessionThread({ path }),
        ...marks,
      };
    }
  }
}

/** The most messages the API serves in one page (openapi.yaml, `limit`). */
export const PAGE_LIMIT = 500;

/**
 * A thread's whole history, oldest first: every page, every kind. The session thread collapses narration on the
 * screen rather than leave it unread, so the person can open any run of it and see how many lines it holds.
 */
export async function readAllMessages(calls: ThreadCalls): Promise<Message[]> {
  const messages: Message[] = [];
  let after = 0;
  for (;;) {
    const page = await calls.page({ after, limit: PAGE_LIMIT });
    messages.push(...page.messages);
    if (page.next_after === null) return messages;
    if (page.next_after <= after) throw new Error(`The threads service's paging did not move past seq ${after}`);
    after = page.next_after;
  }
}

/** The history with one message added or replaced (a post, a mark), still in seq order. */
export function withMessage(messages: readonly Message[], message: Message): Message[] {
  const rest = messages.filter((m) => m.id !== message.id);
  const at = rest.findIndex((m) => m.seq > message.seq);
  return at === -1 ? [...rest, message] : [...rest.slice(0, at), message, ...rest.slice(at)];
}

/** What the screen draws, in order: a line for each new day, each message or milestone, and runs of narration. */
export type TimelineItem =
  | { type: 'day'; key: string; day: string }
  | { type: 'message'; key: string; message: Message }
  | { type: 'narration'; key: string; messages: Message[] };

/**
 * The session thread collapses narration to its milestones (C1): every run of consecutive narration lines becomes one
 * item the screen draws as "Show N narration lines". People's messages and milestones always show.
 */
export function timeline(messages: readonly Message[]): TimelineItem[] {
  const items: TimelineItem[] = [];
  let day: string | null = null;
  for (const message of messages) {
    const today = dayOf(message.created_at);
    const last = items[items.length - 1];
    if (message.kind === 'narration' && last?.type === 'narration') {
      last.messages.push(message);
      continue;
    }
    if (today !== day) {
      items.push({ type: 'day', key: `day-${today}`, day: today });
      day = today;
    }
    items.push(
      message.kind === 'narration'
        ? { type: 'narration', key: `narration-${message.seq}`, messages: [message] }
        : { type: 'message', key: `message-${message.id}`, message },
    );
  }
  return items;
}

// The service writes every time in UTC, as 2026-10-24T16:14:05.123456Z (threads/app.py). The screen shows them as
// the terminal board shows its times, in UTC, so a phone's time zone never changes what a thread says.
const UTC = /^(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2})/;

/** The UTC day of a service time: 2026-10-24. */
export function dayOf(at: string): string {
  return UTC.exec(at)?.[1] ?? at;
}

/** The UTC time of day of a service time: 16:14. */
export function timeOf(at: string): string {
  return UTC.exec(at)?.[2] ?? at;
}

export function sameLogin(a: string | null | undefined, b: string | null | undefined): boolean {
  return !!a && !!b && a.toLowerCase() === b.toLowerCase();
}

/** Who wrote a message, as its bubble names them. */
export function authorName(message: Message): string {
  const { author } = message;
  switch (author.type) {
    case 'person':
      return author.login;
    case 'session':
      return 'the session';
    case 'github':
      return author.login;
  }
}

/**
 * What the bubble says after the name: a person's part in the loop (the artboard's "· loop owner"), a session's
 * sponsor, or where a mirrored review comment came from (command-center/D6).
 */
export function authorDetail(message: Message, { owner, sponsor }: { owner: string | null; sponsor: string | null }): string[] {
  const { author, source } = message;
  if (author.type === 'session') return [`sponsored by ${author.sponsor}`];
  if (author.type === 'github') {
    const from = source
      ? `${source.type === 'github_review' ? 'review' : 'review comment'} on PR #${source.pull_request}`
      : 'on GitHub';
    return [
      source?.type === 'github_review' && source.review_state ? `${from}, ${source.review_state.replace(/_/g, ' ')}` : from,
      ...(source?.path ? [source.path] : []),
    ];
  }
  const parts: string[] = [];
  if (sameLogin(author.login, owner)) parts.push('loop owner');
  if (sameLogin(author.login, sponsor)) parts.push('sponsor');
  return parts;
}

/** A session thread's heading: "loop-build on report-pipeline/queue", or its id when the runner cannot say. */
export function sessionTitle(id: string, session: Session | null): string {
  if (!session) return `Session ${id.slice(0, 8)}`;
  return `${session.skill} on ${session.concern ?? session.loop ?? session.environment ?? 'nothing'}`;
}

/** The tile beside a session's heading, after the artboard's "LB": the skill's initials. */
export function sessionInitials(session: Session | null): string {
  if (!session) return 'S';
  return session.skill
    .split('-')
    .map((word) => word.slice(0, 1).toUpperCase())
    .join('');
}

export function dollars(usd: number): string {
  return `$${usd.toFixed(2)}`;
}

// "Record this?" (C2, command-center/D36). Any member marks a message; the loop's owner accepts a marked one, which
// dispatches /loop-design through the runner with the owner as its sponsor. Only the owner acts on a loop until they
// delegate, and everyone else sees the mark read-only (command-center/D10).

/** Whether a message can be marked: what people and sessions write to people, not a session's own steps. */
export function markable(message: Message): boolean {
  return message.kind === 'message';
}

/** What /loop-design runs on for a message in this thread: the thread's concern or loop, or a session's. */
export type RecordTarget = { kind: 'concern'; loop: string; concern: string } | { kind: 'loop'; loop: string };

export function recordTarget(ref: ThreadRef, session: Session | null): RecordTarget | null {
  switch (ref.scope) {
    case 'concern':
      return { kind: 'concern', loop: ref.loop, concern: `${ref.loop}/${ref.concern}` };
    case 'loop':
      return { kind: 'loop', loop: ref.loop };
    case 'session': {
      // A session runs on exactly one concern (loop/concern), loop or environment. /loop-design cannot run on an
      // environment, so a /loop-ship session's thread has nowhere to record into.
      if (session?.concern) return { kind: 'concern', loop: session.concern.split('/')[0]!, concern: session.concern };
      if (session?.loop) return { kind: 'loop', loop: session.loop };
      return null;
    }
  }
}

/** What /loop-design is run on, as a person would type it: report-pipeline/queue, or report-pipeline. */
export function targetName(target: RecordTarget): string {
  return target.kind === 'concern' ? target.concern : target.loop;
}

/** The runner refuses arguments longer than this (services/runner/runner/dispatch.py). */
export const MAX_ARGUMENTS = 2000;

/** The budget the sheet starts with; the person sees it, and can change it, before every dispatch. */
export const DEFAULT_BUDGET_USD = 2;

const RELEASE = /^v[0-9]+\.[0-9]+\.[0-9]+$/;

/**
 * Whether the record sheet's release field holds a tag of the skills, the only form the runner runs, never the
 * clone's own plugin/ (command-center/D17). The field starts from the release the runner's estimate names, the newest
 * release tag (latest-release C2, command-center/D68); the screen holds none of its own.
 */
export function validRelease(text: string): boolean {
  return RELEASE.test(text.trim());
}

/** A budget as typed, "2", "2.50" or "$2.50", in dollars, or null when it is not a number above 0. */
export function parseBudget(text: string): number | null {
  const cleaned = text.trim().replace(/^\$/, '');
  if (!/^\d+(\.\d+)?$|^\.\d+$/.test(cleaned)) return null;
  const usd = Number(cleaned);
  return Number.isFinite(usd) && usd > 0 ? usd : null;
}

const SCOPE_NAMES = { loop: 'loop thread', concern: 'concern thread', session: 'session thread' } as const;

/**
 * The arguments /loop-design gets: which message to record, who wrote and marked it, and its text, cut to fit the
 * runner's limit. The session cannot read the thread, so the message travels in the arguments. The skill records the
 * decision only once the person confirms it in the session's own thread, as from a terminal.
 */
export function recordArguments(ref: ThreadRef, message: Message): string {
  const where =
    ref.scope === 'session' ? `the session thread of session ${ref.session}` : `the ${SCOPE_NAMES[ref.scope]}`;
  const marked = message.record_marks.map((m) => m.login);
  const head =
    `Record the decision made in passing in ${where}: message ${message.id}, written by ${authorName(message)} at ` +
    `${dayOf(message.created_at)} ${timeOf(message.created_at)} UTC` +
    (marked.length ? `, marked "record this?" by ${marked.join(', ')}` : '') +
    '. It says: ';
  const cut = ` [cut to fit; the whole text is message ${message.id}]`;
  const room = MAX_ARGUMENTS - head.length;
  const body = message.body.length <= room ? message.body : message.body.slice(0, Math.max(0, room - cut.length)) + cut;
  return (head + body).slice(0, MAX_ARGUMENTS);
}

/** The runner dispatch that accepting a mark sends (C2): /loop-design on the target, sponsored by the caller. */
export function recordDispatch({
  project,
  target,
  ref,
  message,
  budgetUsd,
  release,
}: {
  project: ProjectKey;
  target: RecordTarget;
  ref: ThreadRef;
  message: Message;
  budgetUsd: number;
  release: string;
}): DispatchRequest {
  const common = {
    project,
    skill: 'loop-design' as const,
    arguments: recordArguments(ref, message),
    budget_usd: budgetUsd,
    plugin_release: release.trim(),
  };
  return target.kind === 'concern' ? { ...common, concern: target.concern } : { ...common, loop: target.loop };
}

/** What the screen says when a call to the threads service fails. */
export function threadErrorText(error: unknown, project: string): string {
  if (error instanceof ServiceError) {
    const detail = (error.body as { message?: unknown } | null)?.message;
    const said = typeof detail === 'string' && detail ? ` It said: ${detail}` : '';
    if (error.kind === 'not-configured') return error.message;
    if (error.status === 403) {
      return `You are not a member of ${project}, so its threads are closed to you. Its members are the repository's collaborators.${said}`;
    }
    if (error.status === 404) return `This build's threads service does not serve ${project}.${said}`;
    if (error.status === 503) return `The threads service could not answer.${said}`;
  }
  return error instanceof Error ? error.message : String(error);
}

/** What the record sheet says when the runner does not start the session: its refusal, naming what exists. */
export function dispatchErrorText(error: unknown): string {
  if (error instanceof ServiceError && error.kind === 'http' && error.status === 409) {
    const refusal = error.body as Refusal | null;
    if (refusal?.message) {
      const prs = (refusal.pull_requests ?? []).map((pr) => `#${pr.number}`);
      const sessions = (refusal.sessions ?? []).map((s) => `${s.skill} on ${s.concern ?? s.loop ?? s.environment} by ${s.sponsor}`);
      return [refusal.message, ...(prs.length ? [`Open: ${prs.join(', ')}.`] : []), ...(sessions.length ? [`Running: ${sessions.join('; ')}.`] : [])].join(' ');
    }
  }
  if (error instanceof ServiceError && error.kind === 'http') {
    const message = (error.body as { message?: unknown } | null)?.message;
    if (typeof message === 'string' && message) return `The runner did not start it: ${message}`;
  }
  return error instanceof Error ? error.message : String(error);
}
