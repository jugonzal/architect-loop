// GitHub's OAuth device flow, as GitHub documents it at
// https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/authorizing-oauth-apps#device-flow (read
// 2026-10-21). The app sends only its client ID, so no secret is in the app or in any service (app-shell D1).
// It asks for no scope, so the token proves who the person is and grants no repository access
// (command-center/D28).

import type { Fetch } from '../../api/fetch';

export const DEVICE_CODE_URL = 'https://github.com/login/device/code';
export const ACCESS_TOKEN_URL = 'https://github.com/login/oauth/access_token';
export const USER_URL = 'https://api.github.com/user';
export const DEVICE_GRANT = 'urn:ietf:params:oauth:grant-type:device_code';
/** GitHub adds this many seconds to the interval each time it answers slow_down. */
export const SLOW_DOWN_SECONDS = 5;

export type DeviceCode = {
  deviceCode: string;
  /** The code the person types at verificationUri: eight characters with a hyphen in the middle. */
  userCode: string;
  verificationUri: string;
  expiresIn: number;
  interval: number;
};

/** What one poll of the token endpoint answered. */
export type PollResult =
  | { kind: 'token'; token: string; scope: string }
  | { kind: 'pending' }
  | { kind: 'slow-down'; interval: number }
  | { kind: 'error'; error: GitHubAuthErrorCode; description: string };

/** The device flow's error codes from GitHub's table, plus what the app adds when an answer makes no sense. */
export type GitHubAuthErrorCode =
  | 'expired_token'
  | 'access_denied'
  | 'device_flow_disabled'
  | 'incorrect_client_credentials'
  | 'incorrect_device_code'
  | 'unsupported_grant_type'
  | 'unexpected_response';

export class GitHubAuthError extends Error {
  readonly code: GitHubAuthErrorCode;

  constructor(code: GitHubAuthErrorCode, message: string) {
    super(message);
    this.name = 'GitHubAuthError';
    this.code = code;
  }
}

export type GitHubUser = {
  login: string;
  /** The profile's name; null when the person has not set one. */
  name: string | null;
  /** The scopes GitHub says the token carries (its X-OAuth-Scopes header), which must be none. */
  scopes: string[];
};

function form(fields: Record<string, string>): string {
  return Object.entries(fields)
    .map(([key, value]) => `${encodeURIComponent(key)}=${encodeURIComponent(value)}`)
    .join('&');
}

async function postForm(fetch: Fetch, url: string, fields: Record<string, string>): Promise<Record<string, unknown>> {
  const response = await fetch(url, {
    method: 'POST',
    // GitHub answers form-encoded unless asked for JSON.
    headers: { Accept: 'application/json', 'Content-Type': 'application/x-www-form-urlencoded' },
    body: form(fields),
  });
  let body: unknown;
  try {
    body = await response.json();
  } catch {
    throw new GitHubAuthError('unexpected_response', `${url} answered ${response.status} without JSON`);
  }
  if (typeof body !== 'object' || body === null) {
    throw new GitHubAuthError('unexpected_response', `${url} answered ${response.status} without a JSON object`);
  }
  return body as Record<string, unknown>;
}

function knownError(error: unknown): GitHubAuthErrorCode {
  switch (error) {
    // GitHub's table says expired_token; the same page's prose says token_expired. Both mean a new code is needed.
    case 'expired_token':
    case 'token_expired':
      return 'expired_token';
    case 'access_denied':
    case 'device_flow_disabled':
    case 'incorrect_client_credentials':
    case 'incorrect_device_code':
    case 'unsupported_grant_type':
      return error;
    default:
      return 'unexpected_response';
  }
}

/** Step 1: ask GitHub for a device code and a user code, with the client ID alone and no scope. */
export async function requestDeviceCode(fetch: Fetch, clientId: string): Promise<DeviceCode> {
  const body = await postForm(fetch, DEVICE_CODE_URL, { client_id: clientId });
  if (typeof body.error === 'string') {
    throw new GitHubAuthError(knownError(body.error), String(body.error_description ?? body.error));
  }
  const { device_code, user_code, verification_uri, expires_in, interval } = body;
  if (
    typeof device_code !== 'string' ||
    typeof user_code !== 'string' ||
    typeof verification_uri !== 'string' ||
    typeof expires_in !== 'number' ||
    typeof interval !== 'number'
  ) {
    throw new GitHubAuthError('unexpected_response', 'GitHub answered the device code request without a code');
  }
  return { deviceCode: device_code, userCode: user_code, verificationUri: verification_uri, expiresIn: expires_in, interval };
}

/** Step 3, once: ask whether the person has entered the code yet. */
export async function pollForToken(fetch: Fetch, clientId: string, deviceCode: string): Promise<PollResult> {
  const body = await postForm(fetch, ACCESS_TOKEN_URL, {
    client_id: clientId,
    device_code: deviceCode,
    grant_type: DEVICE_GRANT,
  });
  if (typeof body.access_token === 'string' && body.access_token) {
    return { kind: 'token', token: body.access_token, scope: typeof body.scope === 'string' ? body.scope : '' };
  }
  if (body.error === 'authorization_pending') return { kind: 'pending' };
  if (body.error === 'slow_down') {
    return { kind: 'slow-down', interval: typeof body.interval === 'number' ? body.interval : NaN };
  }
  const description = String(body.error_description ?? body.error ?? 'no token and no error');
  return { kind: 'error', error: knownError(body.error), description };
}

/** Who the token belongs to, from GET /user. Throws 'unauthorized' when GitHub no longer accepts the token. */
export async function fetchUser(fetch: Fetch, token: string): Promise<GitHubUser> {
  const response = await fetch(USER_URL, {
    headers: {
      Accept: 'application/vnd.github+json',
      Authorization: `Bearer ${token}`,
      'X-GitHub-Api-Version': '2022-11-28',
    },
  });
  if (response.status === 401) throw new UnauthorizedError();
  if (!response.ok) throw new GitHubAuthError('unexpected_response', `GET /user answered ${response.status}`);
  const body = (await response.json()) as { login?: unknown; name?: unknown };
  if (typeof body.login !== 'string') throw new GitHubAuthError('unexpected_response', 'GET /user answered no login');
  const scopes = (response.headers.get('X-OAuth-Scopes') ?? '')
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean);
  return { login: body.login, name: typeof body.name === 'string' && body.name ? body.name : null, scopes };
}

export class UnauthorizedError extends Error {
  constructor() {
    super('GitHub no longer accepts this token');
    this.name = 'UnauthorizedError';
  }
}

/** The name to show for a person: their profile name, else their login. */
export function displayName(user: Pick<GitHubUser, 'login' | 'name'>): string {
  return user.name ?? user.login;
}
