import { createSignedInFetch, NotSignedInError, type Fetch } from '../fetch';

function recordingFetch(status = 200) {
  const calls: { url: string; init: RequestInit }[] = [];
  const fetch: Fetch = async (url, init = {}) => {
    calls.push({ url, init });
    return new Response('{}', { status });
  };
  return { fetch, calls };
}

describe('the signed-in fetch (command-center/D28, D29)', () => {
  it("adds the person's token and keeps the caller's headers", async () => {
    const { fetch, calls } = recordingFetch();
    const signedIn = createSignedInFetch({ getToken: () => 'gho_abc', onUnauthorized: jest.fn(), fetch });
    await signedIn('https://threads.example/x', { method: 'POST', headers: { 'Content-Type': 'application/json' } });
    const headers = new Headers(calls[0]?.init.headers);
    expect(headers.get('Authorization')).toBe('Bearer gho_abc');
    expect(headers.get('Content-Type')).toBe('application/json');
    expect(calls[0]?.init.method).toBe('POST');
  });

  it('reads the token at each call, so a sign-in or sign-out takes effect at once', async () => {
    const { fetch, calls } = recordingFetch();
    let token: string | null = 'gho_first';
    const signedIn = createSignedInFetch({ getToken: () => token, onUnauthorized: jest.fn(), fetch });
    await signedIn('https://a.example');
    token = 'gho_second';
    await signedIn('https://a.example');
    expect(calls.map((c) => new Headers(c.init.headers).get('Authorization'))).toEqual([
      'Bearer gho_first',
      'Bearer gho_second',
    ]);
  });

  it('refuses to call a service when nobody is signed in', async () => {
    const { fetch, calls } = recordingFetch();
    const signedIn = createSignedInFetch({ getToken: () => null, onUnauthorized: jest.fn(), fetch });
    await expect(signedIn('https://a.example')).rejects.toBeInstanceOf(NotSignedInError);
    expect(calls).toHaveLength(0);
  });

  it('signs the person out when a service says the token is no longer good', async () => {
    const onUnauthorized = jest.fn();
    const signedIn = createSignedInFetch({ getToken: () => 'gho_old', onUnauthorized, fetch: recordingFetch(401).fetch });
    const response = await signedIn('https://a.example');
    expect(response.status).toBe(401);
    expect(onUnauthorized).toHaveBeenCalledTimes(1);
  });

  it('leaves the person signed in on other failures', async () => {
    const onUnauthorized = jest.fn();
    const signedIn = createSignedInFetch({ getToken: () => 'gho_ok', onUnauthorized, fetch: recordingFetch(403).fetch });
    await signedIn('https://a.example');
    expect(onUnauthorized).not.toHaveBeenCalled();
  });
});
