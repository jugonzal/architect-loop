// app-shell C1, the sign-in half: the app signs in with GitHub's device flow (D1), sends only its client ID,
// asks for no scope (command-center/D28), and ends knowing the person's name. These run the state machine against
// a fake GitHub; the same flow against the real one is proven on devices after the merge.

import { ACCESS_TOKEN_URL, DEVICE_CODE_URL, DEVICE_GRANT, displayName, USER_URL } from '../github';
import { memorySessionStore, type StoredSession } from '../sessionStore';
import { SignIn, type SignInState } from '../signIn';
import { fakeClock, fakeGitHub, manualClock, settle, type TokenAnswer } from './fakeGitHub';

const CLIENT_ID = 'Iv1.test-client';

type GitHubOptions = Omit<Parameters<typeof fakeGitHub>[0], 'clock'>;

function setup(options: GitHubOptions = {}, stored: StoredSession | null = null) {
  const clock = fakeClock();
  const github = fakeGitHub({ clock, clientId: CLIENT_ID, ...options });
  const store = memorySessionStore(stored);
  const signIn = new SignIn({ clientId: CLIENT_ID, store, fetch: github.fetch, clock });
  const states: SignInState['kind'][] = [];
  signIn.subscribe((s) => states.push(s.kind));
  return { clock, github, store, signIn, states };
}

async function signedOut(t: ReturnType<typeof setup>) {
  await t.signIn.restore();
  expect(t.signIn.state.kind).toBe('signed-out');
}

describe('signing in with the device flow', () => {
  it('shows the code, polls until it is entered, and ends signed in with the name', async () => {
    const t = setup({
      tokens: [
        { error: 'authorization_pending' },
        { error: 'authorization_pending' },
        { access_token: 'gho_16C7e42F292c6912E7710c838347Ae178B4a', scope: '', token_type: 'bearer' },
      ],
    });
    await signedOut(t);
    const seen: SignInState[] = [];
    t.signIn.subscribe((s) => seen.push(s));

    await t.signIn.start();

    const awaiting = seen.find((s) => s.kind === 'awaiting-person');
    expect(awaiting).toMatchObject({ userCode: 'WDJB-MJHT', verificationUri: 'https://github.com/login/device' });
    expect(t.signIn.state).toEqual({ kind: 'signed-in', user: { login: 'octocat', name: 'Mona Lisa Octocat' } });
    expect(displayName((t.signIn.state as Extract<SignInState, { kind: 'signed-in' }>).user)).toBe('Mona Lisa Octocat');
    expect(t.signIn.getToken()).toBe('gho_16C7e42F292c6912E7710c838347Ae178B4a');
    expect(t.store.current?.token).toBe('gho_16C7e42F292c6912E7710c838347Ae178B4a');
    expect(t.states).toEqual(['signed-out', 'requesting-code', 'awaiting-person', 'signed-in']);
  });

  it('sends only the client ID, asks for no scope, and never sends a secret', async () => {
    const t = setup({ tokens: [{ access_token: 'gho_x', scope: '' }] });
    await signedOut(t);
    await t.signIn.start();

    const [codeCall, ...rest] = t.github.calls;
    expect(codeCall?.url).toBe(DEVICE_CODE_URL);
    expect(codeCall?.method).toBe('POST');
    expect(codeCall?.fields).toEqual({ client_id: CLIENT_ID });
    expect(codeCall?.headers.get('Accept')).toBe('application/json');

    const poll = rest.find((c) => c.url === ACCESS_TOKEN_URL);
    expect(poll?.fields).toEqual({
      client_id: CLIENT_ID,
      device_code: '3584d83530557fdd1f46af8289938c8ef79f9dc5',
      grant_type: DEVICE_GRANT,
    });
    for (const call of t.github.calls) {
      expect(Object.keys(call.fields)).not.toContain('client_secret');
      expect(Object.keys(call.fields)).not.toContain('scope');
    }
    const userCall = t.github.calls.find((c) => c.url === USER_URL);
    expect(userCall?.headers.get('Authorization')).toBe('Bearer gho_x');
  });

  it("shows the login when the person has no profile name", async () => {
    const t = setup({ tokens: [{ access_token: 'gho_x' }], user: { login: 'jugonzal', name: null } });
    await signedOut(t);
    await t.signIn.start();
    const state = t.signIn.state as Extract<SignInState, { kind: 'signed-in' }>;
    expect(displayName(state.user)).toBe('jugonzal');
  });

  it('waits the interval before every poll, and five seconds more after each slow_down', async () => {
    const t = setup({
      tokens: [
        { error: 'authorization_pending' },
        { error: 'slow_down' },
        { error: 'authorization_pending' },
        { error: 'slow_down', interval: 20 },
        { access_token: 'gho_x' },
      ],
    });
    await signedOut(t);
    const started = t.clock.now();
    await t.signIn.start();
    const times = t.github.polls().map((c) => (c.at - started) / 1000);
    // interval 5: poll at 5, 10 (slow_down, no interval sent: 5 + 5 = 10), 20, 30 (slow_down to 20), 50.
    expect(times).toEqual([5, 10, 20, 30, 50]);
    expect(t.signIn.state.kind).toBe('signed-in');
  });

  it('gives up when the code expires, without asking GitHub again', async () => {
    const t = setup({
      deviceCode: { device_code: 'dc', user_code: 'ABCD-EFGH', verification_uri: 'https://github.com/login/device', expires_in: 12, interval: 5 },
      tokens: [{ error: 'authorization_pending' }],
    });
    await signedOut(t);
    await t.signIn.start();
    expect(t.github.polls()).toHaveLength(2); // at 5 and 10; at 15 the code is gone
    expect(t.signIn.state).toMatchObject({ kind: 'signed-out', failure: { code: 'expired_token' } });
  });

  it.each([
    [{ error: 'expired_token' }, 'expired_token'],
    [{ error: 'token_expired' }, 'expired_token'],
    [{ error: 'access_denied' }, 'access_denied'],
    [{ error: 'device_flow_disabled' }, 'device_flow_disabled'],
    [{ error: 'incorrect_device_code' }, 'incorrect_device_code'],
    [{ error: 'unsupported_grant_type' }, 'unsupported_grant_type'],
    [{ error: 'something_new' }, 'unexpected_response'],
  ] as [TokenAnswer, string][])('stops on %j and says why (%s)', async (answer, code) => {
    const t = setup({ tokens: [answer] });
    await signedOut(t);
    await t.signIn.start();
    expect(t.signIn.state).toMatchObject({ kind: 'signed-out', failure: { code } });
    expect(t.store.current).toBeNull();
  });

  it('says when GitHub does not know the client ID', async () => {
    const clock = fakeClock();
    const github = fakeGitHub({ clock, clientId: 'Iv1.the-real-one' });
    const signIn = new SignIn({ clientId: CLIENT_ID, store: memorySessionStore(), fetch: github.fetch, clock });
    await signIn.restore();
    await signIn.start();
    expect(signIn.state).toMatchObject({ kind: 'signed-out', failure: { code: 'incorrect_client_credentials' } });
  });

  it('keeps polling through a dropped connection while the code is still good', async () => {
    const t = setup({ tokens: ['network-down', 'network-down', { error: 'authorization_pending' }, { access_token: 'gho_x' }] });
    await signedOut(t);
    const seen: SignInState[] = [];
    t.signIn.subscribe((s) => seen.push(s));
    await t.signIn.start();
    expect(seen.some((s) => s.kind === 'awaiting-person' && s.unreachable)).toBe(true);
    expect(t.signIn.state.kind).toBe('signed-in');
  });

  it('refuses a token that carries repository access (command-center/D28)', async () => {
    const t = setup({ tokens: [{ access_token: 'gho_x', scope: 'repo' }] });
    await signedOut(t);
    await t.signIn.start();
    expect(t.signIn.state).toMatchObject({ kind: 'signed-out', failure: { code: 'has-scopes' } });
    expect(t.store.current).toBeNull();

    const u = setup({ tokens: [{ access_token: 'gho_y', scope: '' }], user: { scopes: 'repo, read:org' } });
    await signedOut(u);
    await u.signIn.start();
    expect(u.signIn.state).toMatchObject({ kind: 'signed-out', failure: { code: 'has-scopes' } });
  });

  it('stops polling when the person cancels', async () => {
    const clock = manualClock();
    const github = fakeGitHub({ clock, clientId: CLIENT_ID, tokens: [{ error: 'authorization_pending' }] });
    const signIn = new SignIn({ clientId: CLIENT_ID, store: memorySessionStore(), fetch: github.fetch, clock });
    await signIn.restore();
    const flow = signIn.start();
    await settle();
    expect(signIn.state.kind).toBe('awaiting-person');
    await clock.tick(); // the first poll: still pending
    expect(github.polls()).toHaveLength(1);
    expect(clock.sleeping()).toBe(1);

    signIn.cancel();
    await flow;
    expect(signIn.state).toEqual({ kind: 'signed-out', failure: null });
    await clock.tick();
    await settle();
    expect(github.polls()).toHaveLength(1);
  });

  it('does not start twice', async () => {
    const t = setup({ tokens: [{ access_token: 'gho_x' }] });
    await signedOut(t);
    await Promise.all([t.signIn.start(), t.signIn.start()]);
    expect(t.github.calls.filter((c) => c.url === DEVICE_CODE_URL)).toHaveLength(1);
  });
});

describe('the session after sign-in', () => {
  const stored = { token: 'gho_stored', user: { login: 'octocat', name: 'Old Name' } };

  it('signs back in at launch with a stored token GitHub still accepts, with the current name', async () => {
    const t = setup({ user: { name: 'Mona Lisa Octocat' } }, stored);
    await t.signIn.restore();
    expect(t.signIn.state).toEqual({ kind: 'signed-in', user: { login: 'octocat', name: 'Mona Lisa Octocat' } });
    expect(t.store.current?.user.name).toBe('Mona Lisa Octocat');
    expect(t.github.calls.map((c) => c.url)).toEqual([USER_URL]);
  });

  it('forgets a stored token GitHub no longer accepts', async () => {
    const t = setup({ user: { status: 401 } }, stored);
    await t.signIn.restore();
    expect(t.signIn.state).toEqual({ kind: 'signed-out', failure: null });
    expect(t.store.current).toBeNull();
  });

  it('keeps a stored sign-in when GitHub cannot be reached, rather than lock the person out offline', async () => {
    const clock = fakeClock();
    const signIn = new SignIn({
      clientId: CLIENT_ID,
      store: memorySessionStore(stored),
      fetch: async () => {
        throw new TypeError('Network request failed');
      },
      clock,
    });
    await signIn.restore();
    expect(signIn.state).toEqual({ kind: 'signed-in', user: stored.user });
  });

  it('signs out on request and forgets the token', async () => {
    const t = setup({}, stored);
    await t.signIn.restore();
    await t.signIn.signOut();
    expect(t.signIn.state).toEqual({ kind: 'signed-out', failure: null });
    expect(t.signIn.getToken()).toBeNull();
    expect(t.store.current).toBeNull();
  });

  it('signs out, saying why, when a service answers 401', async () => {
    const t = setup({}, stored);
    await t.signIn.restore();
    t.signIn.onUnauthorized();
    await Promise.resolve();
    expect(t.signIn.state).toMatchObject({ kind: 'signed-out', failure: { code: 'signed-out-by-service' } });
  });
});

describe('a build without a client ID', () => {
  it('says sign-in is not configured and never calls GitHub', async () => {
    const calls: string[] = [];
    const signIn = new SignIn({
      clientId: null,
      notConfiguredMessage: 'Set EXPO_PUBLIC_GITHUB_CLIENT_ID',
      store: memorySessionStore(),
      fetch: async (url) => {
        calls.push(url);
        return new Response('{}');
      },
    });
    await signIn.restore();
    await signIn.start();
    expect(signIn.state).toEqual({ kind: 'not-configured', message: 'Set EXPO_PUBLIC_GITHUB_CLIENT_ID' });
    expect(calls).toEqual([]);
  });
});
