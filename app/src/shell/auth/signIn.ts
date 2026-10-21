// The sign-in state machine (app-shell D1). It owns every step of GitHub's device flow and the session that
// follows, so the screens only draw its state:
//
//   restoring ──► signed-in                    (a stored token GitHub still accepts)
//       │
//       └──────► signed-out ──start()──► requesting-code ──► awaiting-person ──► signed-in
//                    ▲  ▲                      │                    │   (poll every interval seconds, slower on
//                    │  └──────── failure ─────┴────────────────────┤    slow_down, until the code expires)
//                    │                                              │
//                    └──────────────────── cancel() ────────────────┘
//
//   signed-in ──signOut() or a 401 from a service──► signed-out
//
// With no client ID configured, every state is not-configured: the app says so instead of asking GitHub with a
// placeholder.

import type { Fetch } from '../../api/fetch';
import {
  fetchUser,
  GitHubAuthError,
  pollForToken,
  requestDeviceCode,
  SLOW_DOWN_SECONDS,
  UnauthorizedError,
  type GitHubAuthErrorCode,
} from './github';
import type { SessionStore, StoredSession } from './sessionStore';

export type SignedInUser = StoredSession['user'];

export type SignInFailure = {
  code: GitHubAuthErrorCode | 'has-scopes' | 'network' | 'signed-out-by-service';
  message: string;
};

export type SignInState =
  | { kind: 'not-configured'; message: string }
  | { kind: 'restoring' }
  | { kind: 'signed-out'; failure: SignInFailure | null }
  | { kind: 'requesting-code' }
  | {
      kind: 'awaiting-person';
      userCode: string;
      verificationUri: string;
      /** When the code stops working, in ms since the epoch. */
      expiresAt: number;
      /** Set while GitHub cannot be reached; polling goes on until the code expires. */
      unreachable: boolean;
    }
  | { kind: 'signed-in'; user: SignedInUser };

export type Clock = {
  now(): number;
  /** Resolves after ms, or at once when signal aborts. */
  sleep(ms: number, signal: AbortSignal): Promise<void>;
};

export const realClock: Clock = {
  now: () => Date.now(),
  sleep: (ms, signal) =>
    new Promise((resolve) => {
      if (signal.aborted) return resolve();
      const timer = setTimeout(done, ms);
      function done() {
        clearTimeout(timer);
        signal.removeEventListener('abort', done);
        resolve();
      }
      signal.addEventListener('abort', done);
    }),
};

export type SignInOptions = {
  /** The OAuth app's client ID, or null when the build has none (see config.ts). */
  clientId: string | null;
  notConfiguredMessage?: string;
  store: SessionStore;
  fetch?: Fetch;
  clock?: Clock;
};

const FAILURE_MESSAGES: Record<SignInFailure['code'], string> = {
  expired_token: 'The code expired before it was entered. Start again for a new one.',
  access_denied: 'Sign-in was cancelled on GitHub.',
  device_flow_disabled: "This app's GitHub sign-in is not switched on yet: the device flow is off in its OAuth app.",
  incorrect_client_credentials: "GitHub does not recognise this build's client ID.",
  incorrect_device_code: 'GitHub did not recognise the code. Start again for a new one.',
  unsupported_grant_type: 'GitHub refused the sign-in request.',
  unexpected_response: 'GitHub answered in a way this build does not understand.',
  'has-scopes': 'GitHub gave this sign-in repository access, which the app never asks for, so it was refused.',
  network: 'GitHub cannot be reached. Check the connection and start again.',
  'signed-out-by-service': 'Your sign-in is no longer accepted. Sign in again.',
};

function failure(code: SignInFailure['code']): SignInFailure {
  return { code, message: FAILURE_MESSAGES[code] };
}

export class SignIn {
  private _state: SignInState;
  private readonly listeners = new Set<(state: SignInState) => void>();
  private session: StoredSession | null = null;
  /** Aborts the flow in progress; replaced each time one starts. */
  private flow: AbortController | null = null;
  private readonly clientId: string | null;
  private readonly store: SessionStore;
  private readonly fetch: Fetch;
  private readonly clock: Clock;

  constructor({ clientId, notConfiguredMessage, store, fetch = globalThis.fetch, clock = realClock }: SignInOptions) {
    this.clientId = clientId;
    this.store = store;
    this.fetch = fetch;
    this.clock = clock;
    this._state = clientId
      ? { kind: 'restoring' }
      : { kind: 'not-configured', message: notConfiguredMessage ?? 'This build has no GitHub client ID.' };
  }

  get state(): SignInState {
    return this._state;
  }

  /** The signed-in person's token, or null. The signed-in fetch reads it at every call. */
  getToken = (): string | null => (this._state.kind === 'signed-in' ? (this.session?.token ?? null) : null);

  subscribe(listener: (state: SignInState) => void): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  private set(state: SignInState) {
    this._state = state;
    for (const listener of this.listeners) listener(state);
  }

  /** At launch: sign the person back in with the stored token if GitHub still accepts it. */
  async restore(): Promise<void> {
    if (this._state.kind !== 'restoring') return;
    const stored = await this.store.load();
    if (!stored) return this.set({ kind: 'signed-out', failure: null });
    try {
      const user = await fetchUser(this.fetch, stored.token);
      if (user.scopes.length > 0) {
        await this.store.clear();
        return this.set({ kind: 'signed-out', failure: failure('has-scopes') });
      }
      this.session = { token: stored.token, user: { login: user.login, name: user.name } };
      await this.store.save(this.session);
    } catch (error) {
      if (error instanceof UnauthorizedError) {
        await this.store.clear();
        return this.set({ kind: 'signed-out', failure: null });
      }
      // GitHub cannot be reached, or answered oddly: keep the stored sign-in rather than lock the person out
      // offline. A service that no longer accepts the token answers 401, which signs them out (onUnauthorized).
      this.session = stored;
    }
    this.set({ kind: 'signed-in', user: this.session.user });
  }

  /** Starts the device flow: get a code, show it, and poll until the person enters it on github.com. */
  async start(): Promise<void> {
    if (!this.clientId || this._state.kind !== 'signed-out') return;
    const clientId = this.clientId;
    this.flow?.abort();
    const flow = new AbortController();
    this.flow = flow;
    this.set({ kind: 'requesting-code' });

    let code;
    try {
      code = await requestDeviceCode(this.fetch, clientId);
    } catch (error) {
      if (!flow.signal.aborted) this.fail(error);
      return;
    }
    if (flow.signal.aborted) return;

    const expiresAt = this.clock.now() + code.expiresIn * 1000;
    let interval = code.interval;
    const awaiting = { kind: 'awaiting-person', userCode: code.userCode, verificationUri: code.verificationUri, expiresAt } as const;
    let unreachable = false;
    this.set({ ...awaiting, unreachable });

    for (;;) {
      await this.clock.sleep(interval * 1000, flow.signal);
      if (flow.signal.aborted) return;
      if (this.clock.now() >= expiresAt) return this.set({ kind: 'signed-out', failure: failure('expired_token') });

      let result;
      try {
        result = await pollForToken(this.fetch, clientId, code.deviceCode);
      } catch (error) {
        if (flow.signal.aborted) return;
        if (error instanceof GitHubAuthError) return this.fail(error);
        // The network dropped: the code is still good until it expires, so keep asking at the same pace.
        if (!unreachable) this.set({ ...awaiting, unreachable: (unreachable = true) });
        continue;
      }
      if (flow.signal.aborted) return;

      switch (result.kind) {
        case 'pending':
          if (unreachable) this.set({ ...awaiting, unreachable: (unreachable = false) });
          continue;
        case 'slow-down':
          // GitHub sends the new interval; it is the old one plus five seconds when it does not.
          interval = Number.isFinite(result.interval) ? result.interval : interval + SLOW_DOWN_SECONDS;
          continue;
        case 'error':
          return this.set({ kind: 'signed-out', failure: failure(result.error) });
        case 'token':
          return this.finish(result.token, result.scope, flow.signal);
      }
    }
  }

  private async finish(token: string, grantedScope: string, signal: AbortSignal) {
    if (grantedScope.trim()) return this.set({ kind: 'signed-out', failure: failure('has-scopes') });
    try {
      const user = await fetchUser(this.fetch, token);
      if (signal.aborted) return;
      if (user.scopes.length > 0) return this.set({ kind: 'signed-out', failure: failure('has-scopes') });
      this.session = { token, user: { login: user.login, name: user.name } };
      await this.store.save(this.session);
      this.set({ kind: 'signed-in', user: this.session.user });
    } catch (error) {
      if (!signal.aborted) this.fail(error);
    }
  }

  private fail(error: unknown) {
    if (error instanceof GitHubAuthError) return this.set({ kind: 'signed-out', failure: failure(error.code) });
    this.set({ kind: 'signed-out', failure: failure('network') });
  }

  /** Stops a flow in progress and goes back to signed out, with no failure to show. */
  cancel(): void {
    if (this._state.kind !== 'requesting-code' && this._state.kind !== 'awaiting-person') return;
    this.flow?.abort();
    this.flow = null;
    this.set({ kind: 'signed-out', failure: null });
  }

  /**
   * Forgets the token on this device. Revoking it on GitHub needs the OAuth app's client secret, which the app
   * does not have (D1), so the person revokes it from their GitHub settings if they want it gone there too.
   */
  async signOut(failureCode: 'signed-out-by-service' | null = null): Promise<void> {
    if (this._state.kind !== 'signed-in') return;
    this.session = null;
    this.set({ kind: 'signed-out', failure: failureCode ? failure(failureCode) : null });
    await this.store.clear();
  }

  /** For the signed-in fetch: a service answered 401, so the token is no longer good. */
  onUnauthorized = (): void => {
    void this.signOut('signed-out-by-service');
  };
}
