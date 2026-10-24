// A fake notifier behind a fetch: the operations of services/notify/openapi.yaml, kept in memory per person, as
// the service keeps them (each person sees only their own devices and settings, and a test reaches only the
// caller's devices). It records every call, with the token it carried, so a test can see who asked for what.

import type { Fetch } from '../../../api/fetch';
import type { Delivery, Device, Settings } from '../../../api/notify.gen';
import type { PushPermission, PushTokenSource } from '../pushTokens';

export const NOTIFY_URL = 'https://notify-123456789012.us-east1.run.app';

type Call = { method: string; path: string; token: string | null; body: unknown };

export function fakeNotify({ logins = { gho_alice: 'alice', gho_bob: 'bob' } as Record<string, string> } = {}) {
  const devices = new Map<string, Device & { login: string; token: string }>();
  const settings = new Map<string, Omit<Settings, 'saved'>>();
  const calls: Call[] = [];
  /** Each test notification, as the device tokens it reached. */
  const tests: string[][] = [];
  const answers: { next?: { status: number; body: unknown } } = {};
  let seq = 0;

  const json = (status: number, body: unknown) =>
    new Response(body === null ? null : JSON.stringify(body), {
      status,
      headers: { 'Content-Type': 'application/json' },
    });
  const error = (status: number, kind: string, message: string) => json(status, { error: kind, message });
  const view = ({ login: _login, token: _token, ...device }: Device & { login: string; token: string }) => device;

  const fetch: Fetch = async (url, init = {}) => {
    const headers = new Headers(init.headers);
    const token = headers.get('Authorization')?.replace(/^Bearer /, '') ?? null;
    const method = init.method ?? 'GET';
    const path = url.startsWith(NOTIFY_URL) ? url.slice(NOTIFY_URL.length) : url;
    const body = typeof init.body === 'string' ? JSON.parse(init.body) : undefined;
    calls.push({ method, path, token, body });
    if (answers.next) {
      const { status, body: answer } = answers.next;
      answers.next = undefined;
      return json(status, answer);
    }
    const login = token ? logins[token] : undefined;
    if (!login) return error(401, 'unauthorized', 'GitHub does not accept this token');
    const match = /^\/projects\/([^/]+)\/([^/]+)\/(devices(?:\/([0-9a-f]+))?|test-notification|settings\/me)$/.exec(path);
    if (!match) return error(404, 'not_found', 'no such path');
    const [, , , what = '', id] = match;
    const mine = () => [...devices.values()].filter((d) => d.login === login);

    if (what === 'devices' && method === 'GET') return json(200, { devices: mine().map(view) });
    if (what === 'devices' && method === 'POST') {
      const { token: pushToken, platform, name = null, timezone } = body as Record<string, string>;
      if (!/^ExponentPushToken\[.+\]$/.test(pushToken ?? '')) {
        return error(400, 'bad_request', 'token must be an Expo push token, ExponentPushToken[...]');
      }
      const existing = [...devices.values()].find((d) => d.token === pushToken);
      const deviceId = existing?.id ?? (++seq).toString(16).padStart(32, '0');
      const device = {
        id: deviceId,
        platform: platform as Device['platform'],
        name,
        registered_at: existing?.login === login ? existing.registered_at : '2026-10-26T14:00:00Z',
        login,
        token: pushToken!,
      };
      devices.set(deviceId, device);
      if (timezone && !settings.has(login)) {
        settings.set(login, { timezone, digest_time: '09:00', quiet_hours: null });
      }
      return json(200, view(device));
    }
    if (what.startsWith('devices/') && method === 'DELETE') {
      const device = devices.get(id!);
      if (!device || device.login !== login) return error(404, 'not_found', `you have no device ${id}`);
      devices.delete(id!);
      return new Response(null, { status: 204 });
    }
    if (what === 'test-notification' && method === 'POST') {
      const reached = mine().map((d) => d.token);
      tests.push(reached);
      const delivery: Delivery = { devices: reached.length, accepted: reached.length, gone: 0 };
      return json(200, delivery);
    }
    if (what === 'settings/me' && method === 'GET') {
      const saved = settings.get(login);
      return json(200, { ...(saved ?? { timezone: 'UTC', digest_time: '09:00', quiet_hours: null }), saved: !!saved });
    }
    if (what === 'settings/me' && method === 'PUT') {
      settings.set(login, body as Omit<Settings, 'saved'>);
      return json(200, { ...(body as object), saved: true });
    }
    return error(405, 'bad_request', 'method not allowed here');
  };

  return {
    fetch,
    calls,
    tests,
    devices,
    settings,
    /** The next call answers this, whatever it is. */
    answerNext(status: number, body: unknown) {
      answers.next = { status, body };
    },
  };
}

/** A fake device: grants or denies permission, and answers its push token. */
export function fakeDevice(
  token: string,
  { permission = 'granted' as PushPermission, platform = 'ios' as 'ios' | 'android' } = {},
) {
  const asked: string[] = [];
  const source: PushTokenSource = {
    platform,
    async requestPermission() {
      asked.push('permission');
      return permission;
    },
    async getExpoPushToken() {
      asked.push('token');
      return token;
    },
  };
  return { source, asked };
}
