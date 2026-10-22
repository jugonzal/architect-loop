// A fake GitHub for the device flow: the three endpoints the app calls, answering from a script, and a clock
// that sleeps by moving time forward, so a test can see when each poll happened.

import type { Fetch } from '../../../api/fetch';
import { ACCESS_TOKEN_URL, DEVICE_CODE_URL, USER_URL } from '../github';
import type { Clock } from '../signIn';

export type TokenAnswer =
  | { error: 'authorization_pending' }
  | { error: 'slow_down'; interval?: number }
  | { error: string; error_description?: string }
  | { access_token: string; scope?: string; token_type?: string }
  | 'network-down';

export type Call = { url: string; method: string; at: number; fields: Record<string, string>; headers: Headers };

export function fakeClock(start = 1_000_000) {
  const clock: Clock & { time: number } = {
    time: start,
    now: () => clock.time,
    async sleep(ms, signal) {
      if (signal.aborted) return;
      clock.time += ms;
      // Let other work (a cancel, say) run between polls, as a real timer would.
      await Promise.resolve();
    },
  };
  return clock;
}

/** A clock whose sleeps wait until the test calls tick(), so a test can act between two polls. */
export function manualClock(start = 1_000_000) {
  const waiting: { until: number; resolve: () => void }[] = [];
  const clock: Clock & { time: number; sleeping(): number; tick(): Promise<void> } = {
    time: start,
    now: () => clock.time,
    sleep(ms, signal) {
      return new Promise<void>((resolve) => {
        if (signal.aborted) return resolve();
        waiting.push({ until: clock.time + ms, resolve });
        signal.addEventListener('abort', () => resolve());
      });
    },
    sleeping: () => waiting.length,
    /** Wakes the next sleeper, moving time to when it asked to wake, and lets the work after it run. */
    async tick() {
      const next = waiting.shift();
      if (!next) return;
      clock.time = next.until;
      next.resolve();
      await settle();
    },
  };
  return clock;
}

/** Lets pending work run: promise callbacks, and the timers a Response body uses. */
export async function settle() {
  for (let i = 0; i < 5; i++) await new Promise((resolve) => setTimeout(resolve, 0));
}

export function fakeGitHub(options: {
  clock: { now(): number };
  clientId?: string;
  deviceCode?: Record<string, unknown> | { error: string };
  tokens?: TokenAnswer[];
  user?: { status?: number; login?: string; name?: string | null; scopes?: string };
}) {
  const clientId = options.clientId ?? 'Iv1.test-client';
  const tokens = [...(options.tokens ?? [])];
  const calls: Call[] = [];
  const deviceCode = options.deviceCode ?? {
    device_code: '3584d83530557fdd1f46af8289938c8ef79f9dc5',
    user_code: 'WDJB-MJHT',
    verification_uri: 'https://github.com/login/device',
    expires_in: 900,
    interval: 5,
  };

  const json = (body: unknown, status = 200, headers: Record<string, string> = {}) =>
    new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json', ...headers } });

  const fetch: Fetch = async (url, init = {}) => {
    const headers = new Headers(init.headers);
    const fields = Object.fromEntries(new URLSearchParams(typeof init.body === 'string' ? init.body : ''));
    calls.push({ url, method: init.method ?? 'GET', at: options.clock.now(), fields, headers });

    if (url === DEVICE_CODE_URL) {
      if (fields.client_id !== clientId) return json({ error: 'incorrect_client_credentials' });
      return json(deviceCode);
    }
    if (url === ACCESS_TOKEN_URL) {
      const answer = tokens.length > 1 ? tokens.shift()! : (tokens[0] ?? { error: 'authorization_pending' });
      if (answer === 'network-down') throw new TypeError('Network request failed');
      return json(answer);
    }
    if (url === USER_URL) {
      const user = options.user ?? {};
      if ((user.status ?? 200) !== 200) return json({ message: 'Bad credentials' }, user.status);
      return json(
        { login: user.login ?? 'octocat', name: user.name === undefined ? 'Mona Lisa Octocat' : user.name },
        200,
        { 'X-OAuth-Scopes': user.scopes ?? '' },
      );
    }
    return json({ message: 'Not Found' }, 404);
  };

  return { fetch, calls, polls: () => calls.filter((c) => c.url === ACCESS_TOKEN_URL) };
}
