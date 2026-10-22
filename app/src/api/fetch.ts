// The signed-in fetch: every call the app makes to a command center service carries the person's GitHub token,
// and the service identifies them with GET /user on it (command-center/D28). The token proves who the person is
// and grants no repository access, so a service is never handed more than an identity.
//
// The screens build their own service clients on this (command-center/D29); app-shell provides only it and the
// status client.

export type Fetch = (input: string, init?: RequestInit) => Promise<Response>;

/** Thrown when a call needs a signed-in person and nobody is signed in. */
export class NotSignedInError extends Error {
  constructor() {
    super('Not signed in');
    this.name = 'NotSignedInError';
  }
}

export type SignedInFetchOptions = {
  /** The current token, or null when nobody is signed in. */
  getToken: () => string | null;
  /** Called when a service answers 401: the token is no longer good, so the person must sign in again. */
  onUnauthorized: () => void;
  fetch?: Fetch;
};

export function createSignedInFetch({ getToken, onUnauthorized, fetch = globalThis.fetch }: SignedInFetchOptions): Fetch {
  return async (input, init = {}) => {
    const token = getToken();
    if (!token) throw new NotSignedInError();
    const headers = new Headers(init.headers);
    headers.set('Authorization', `Bearer ${token}`);
    const response = await fetch(input, { ...init, headers });
    if (response.status === 401) onUnauthorized();
    return response;
  };
}
