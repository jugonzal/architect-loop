// app-threads, the rules under the screens: the routes command-center/D52 fixes, reading a thread whole, collapsing
// narration, who wrote what, and the /loop-design dispatch that accepting a "record this?" mark sends (C2).

import * as fs from 'fs';
import * as path from 'path';

import type { Session } from '../../../api/runner.gen';
import { ServiceError } from '../../../api/service';
import type { Message } from '../../../api/threads.gen';
import { concernThreadHref as boardConcernThreadHref } from '../../loops/board';
import {
  authorDetail,
  backTarget,
  concernThreadHref,
  dispatchErrorText,
  loopThreadHref,
  MAX_ARGUMENTS,
  parseBudget,
  readAllMessages,
  recordArguments,
  recordDispatch,
  recordTarget,
  sessionThreadHref,
  sessionTitle,
  threadErrorText,
  timeline,
  validRelease,
  withMessage,
  type ThreadCalls,
} from '../thread';
import { at, fakeSession } from './fakeServices';

function message(id: number, overrides: Partial<Message> = {}): Message {
  return {
    id,
    seq: id,
    thread: '/projects/example/reports/loops/report-pipeline/concerns/queue/thread',
    kind: 'message',
    author: { type: 'person', login: 'ben' },
    body: `Message ${id}`,
    created_at: at(id),
    record_marks: [],
    source: null,
    ...overrides,
  };
}

describe('the thread routes (command-center/D52)', () => {
  it('are the threads API paths without the project', () => {
    expect(loopThreadHref('report-pipeline')).toBe('/threads/loops/report-pipeline');
    expect(concernThreadHref('report-pipeline', 'queue')).toBe('/threads/loops/report-pipeline/concerns/queue');
    expect(sessionThreadHref('a1b2')).toBe('/threads/sessions/a1b2');
  });

  it("match the link app-loops-board's Concern page opens", () => {
    expect(concernThreadHref('report-pipeline', 'queue')).toBe(boardConcernThreadHref('report-pipeline', 'queue'));
  });

  it('go back to the loop, the concern, or Agents when nothing is behind them', () => {
    expect(backTarget({ scope: 'loop', loop: 'l' })).toEqual({ href: '/loops/l', label: 'l' });
    expect(backTarget({ scope: 'concern', loop: 'l', concern: 'c' })).toEqual({ href: '/loops/l/concerns/c', label: 'c' });
    expect(backTarget({ scope: 'session', session: 's' })).toEqual({ href: '/agents', label: 'Agents' });
  });
});

describe('reading a thread', () => {
  function pages(...answers: { messages: Message[]; next_after: number | null }[]) {
    const asked: { after?: number; limit?: number }[] = [];
    const calls = {
      page: async (query: { after?: number; limit?: number }) => {
        asked.push(query);
        return answers[asked.length - 1]!;
      },
    } as unknown as ThreadCalls;
    return { calls, asked };
  }

  it('reads every page, passing next_after along, until it is null', async () => {
    const { calls, asked } = pages(
      { messages: [message(1), message(2)], next_after: 2 },
      { messages: [message(3)], next_after: null },
    );
    expect((await readAllMessages(calls)).map((m) => m.id)).toEqual([1, 2, 3]);
    expect(asked).toEqual([
      { after: 0, limit: 500 },
      { after: 2, limit: 500 },
    ]);
  });

  it('stops, rather than loop forever, when a page does not move past the last', async () => {
    const { calls } = pages({ messages: [], next_after: 0 });
    await expect(readAllMessages(calls)).rejects.toThrow('did not move past seq 0');
  });

  it('puts a posted or marked message in its place by seq', () => {
    const history = [message(1), message(3)];
    expect(withMessage(history, message(2)).map((m) => m.id)).toEqual([1, 2, 3]);
    expect(withMessage(history, message(4)).map((m) => m.id)).toEqual([1, 3, 4]);
    const marked = message(3, { record_marks: [{ login: 'ana', marked_at: at(9) }] });
    expect(withMessage(history, marked)).toEqual([message(1), marked]);
  });
});

describe('the timeline', () => {
  it('collapses each run of narration into one item, keeps messages and milestones, and marks each new UTC day', () => {
    const items = timeline([
      message(1, { kind: 'milestone', created_at: '2026-10-23T23:59:00Z' }),
      message(2, { kind: 'narration' }),
      message(3, { kind: 'narration' }),
      message(4, { kind: 'milestone' }),
      message(5, { kind: 'narration' }),
      message(6),
    ]);
    expect(items.map((i) => (i.type === 'narration' ? `narration ${i.messages.map((m) => m.id)}` : i.type === 'day' ? i.day : i.message.id))).toEqual([
      '2026-10-23',
      1,
      '2026-10-24',
      'narration 2,3',
      4,
      'narration 5',
      6,
    ]);
  });
});

describe('who wrote a message', () => {
  it("names a person's part in the loop", () => {
    expect(authorDetail(message(1, { author: { type: 'person', login: 'Ana' } }), { owner: 'ana', sponsor: 'ana' })).toEqual([
      'loop owner',
      'sponsor',
    ]);
    expect(authorDetail(message(1), { owner: 'ana', sponsor: null })).toEqual([]);
  });

  it('says where a mirrored review came from, and its verdict (command-center/D6)', () => {
    const review = message(1, {
      author: { type: 'github', login: 'dana', association: 'NONE' },
      source: { type: 'github_review', url: 'u', pull_request: 12, path: null, review_state: 'changes_requested' },
    });
    expect(authorDetail(review, { owner: null, sponsor: null })).toEqual(['review on PR #12, changes requested']);
  });

  it("names a session by the runner's account of it, or by its id", () => {
    expect(sessionTitle('a1b2c3d4e5f6', fakeSession({ id: 'a1b2c3d4e5f6' }))).toBe('loop-build on report-pipeline/queue');
    expect(sessionTitle('a1b2c3d4e5f6', null)).toBe('Session a1b2c3d4');
  });
});

describe('no release of its own (latest-release C2)', () => {
  it('names no release tag anywhere in the threads’ code: the runner’s estimate names it', () => {
    const dir = path.join(__dirname, '..');
    const sources = fs.readdirSync(dir).filter((name) => /\.tsx?$/.test(name));
    expect(sources.length).toBeGreaterThan(0);
    for (const name of sources) {
      const text = fs.readFileSync(path.join(dir, name), 'utf8');
      expect([name, text.match(/v[0-9]+\.[0-9]+\.[0-9]+/g)]).toEqual([name, null]);
    }
  });
});

describe('accepting a "record this?" mark (C2)', () => {
  const marked = message(42, {
    author: { type: 'person', login: 'ana' },
    body: 'Five tries, then the dead-letter queue.',
    created_at: '2026-10-24T16:14:05.123456Z',
    record_marks: [{ login: 'ben', marked_at: at(20) }],
  });

  it("records into the thread's concern or loop, or a session's, and nowhere for an environment's session", () => {
    expect(recordTarget({ scope: 'concern', loop: 'rp', concern: 'queue' }, null)).toEqual({ kind: 'concern', loop: 'rp', concern: 'rp/queue' });
    expect(recordTarget({ scope: 'loop', loop: 'rp' }, null)).toEqual({ kind: 'loop', loop: 'rp' });
    const ref = { scope: 'session' as const, session: 's' };
    expect(recordTarget(ref, fakeSession({ id: 's' }))).toEqual({ kind: 'concern', loop: 'report-pipeline', concern: 'report-pipeline/queue' });
    expect(recordTarget(ref, fakeSession({ id: 's', concern: null, loop: 'report-pipeline' }))).toEqual({ kind: 'loop', loop: 'report-pipeline' });
    const ship: Session = fakeSession({ id: 's', skill: 'loop-ship', concern: null, environment: 'staging/runner' });
    expect(recordTarget(ref, ship)).toBeNull();
    expect(recordTarget(ref, null)).toBeNull();
  });

  it('dispatches /loop-design with the message in its arguments, and nothing the runner would refuse', () => {
    const body = recordDispatch({
      project: 'example/reports',
      target: { kind: 'concern', loop: 'report-pipeline', concern: 'report-pipeline/queue' },
      ref: { scope: 'concern', loop: 'report-pipeline', concern: 'queue' },
      message: marked,
      budgetUsd: 2,
      release: ' v0.4.0 ',
    });
    expect(body).toEqual({
      project: 'example/reports',
      skill: 'loop-design',
      concern: 'report-pipeline/queue',
      arguments:
        'Record the decision made in passing in the concern thread: message 42, written by ana at 2026-10-24 16:14 UTC, ' +
        'marked "record this?" by ben. It says: Five tries, then the dead-letter queue.',
      budget_usd: 2,
      plugin_release: 'v0.4.0',
    });
    const onLoop = recordDispatch({
      project: 'example/reports',
      target: { kind: 'loop', loop: 'report-pipeline' },
      ref: { scope: 'loop', loop: 'report-pipeline' },
      message: marked,
      budgetUsd: 1,
      release: 'v0.4.0',
    });
    expect(onLoop).toMatchObject({ loop: 'report-pipeline' });
    expect(onLoop).not.toHaveProperty('concern');
  });

  it("cuts a long message to fit the runner's 2000 characters, and says where the rest is", () => {
    const long = recordArguments({ scope: 'loop', loop: 'rp' }, { ...marked, body: 'y'.repeat(3000) });
    expect(long.length).toBeLessThanOrEqual(MAX_ARGUMENTS);
    expect(long.endsWith(' [cut to fit; the whole text is message 42]')).toBe(true);
  });

  it('takes a budget in dollars above 0, and a release tag', () => {
    expect(parseBudget('2')).toBe(2);
    expect(parseBudget(' $3.50 ')).toBe(3.5);
    expect(parseBudget('.5')).toBe(0.5);
    for (const bad of ['', '0', '-1', 'two', '1e3', '2.', 'Infinity']) expect(parseBudget(bad)).toBeNull();
    expect(validRelease('v0.4.0')).toBe(true);
    for (const bad of ['0.4.0', 'v0.4', 'latest', 'v0.4.0-rc1']) expect(validRelease(bad)).toBe(false);
  });

  it("says what holds the concern when the runner refuses (409), and the runner's reason otherwise", () => {
    const refused = new ServiceError('runner', 'dispatch', 'http', 'POST /sessions answered 409', {
      status: 409,
      body: {
        refused: 'running-session',
        message: 'report-pipeline/queue is held by a running session.',
        pull_requests: [],
        sessions: [fakeSession({ id: 'x', skill: 'loop-build', sponsor: 'ben' })],
      },
    });
    expect(dispatchErrorText(refused)).toBe(
      'report-pipeline/queue is held by a running session. Running: loop-build on report-pipeline/queue by ben.',
    );
    const unknown = new ServiceError('runner', 'dispatch', 'http', 'POST /sessions answered 422', {
      status: 422,
      body: { error: 'unknown-release', message: 'v9.9.9 is not a release tag' },
    });
    expect(dispatchErrorText(unknown)).toBe('The runner did not start it: v9.9.9 is not a release tag');
  });
});

describe('what a failed read says', () => {
  it('names membership for a 403, the project for a 404, and the missing URL when there is none', () => {
    const http = (status: number) =>
      new ServiceError('threads', 'getLoopThread', 'http', `answered ${status}`, { status, body: { error: 'x', message: 'why' } });
    expect(threadErrorText(http(403), 'example/reports')).toMatch(/^You are not a member of example\/reports.* It said: why$/);
    expect(threadErrorText(http(404), 'example/reports')).toBe("This build's threads service does not serve example/reports. It said: why");
    expect(threadErrorText(http(503), 'example/reports')).toBe('The threads service could not answer. It said: why');
    const none = new ServiceError('threads', 'getLoopThread', 'not-configured', 'This build has no URL for the threads service yet');
    expect(threadErrorText(none, 'example/reports')).toBe('This build has no URL for the threads service yet');
  });
});
