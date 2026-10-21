// The signed-in session, shared with every screen: who the person is, the signed-in fetch the screens build their
// service clients on (command-center/D29), and the status client. Screens use the hooks below and never touch the
// token.

import { createContext, useContext, useEffect, useMemo, useSyncExternalStore, type ReactNode } from 'react';

import { createSignedInFetch, type Fetch } from '../api/fetch';
import { createStatusClient, type StatusClient } from '../api/status';
import { secureSessionStore } from './auth/sessionStore';
import { SignIn, type SignedInUser, type SignInState } from './auth/signIn';
import { config as buildConfig, NOT_CONFIGURED_MESSAGE, type AppConfig } from './config';

export type Session = {
  state: SignInState;
  signIn: SignIn;
  config: AppConfig;
  /** Adds the person's token to every call; signs them out when a service answers 401. */
  fetch: Fetch;
  /** Null when the build has no status URL yet. */
  status: StatusClient | null;
};

const SessionContext = createContext<Session | null>(null);

let defaultSignIn: SignIn | null = null;

/** The app's one sign-in, kept in secure storage and configured from the build. */
export function appSignIn(config: AppConfig = buildConfig): SignIn {
  defaultSignIn ??= new SignIn({
    clientId: config.githubClientId,
    notConfiguredMessage: NOT_CONFIGURED_MESSAGE,
    store: secureSessionStore,
  });
  return defaultSignIn;
}

export function SessionProvider({
  signIn,
  config = buildConfig,
  fetch: baseFetch = globalThis.fetch,
  children,
}: {
  signIn: SignIn;
  config?: AppConfig;
  fetch?: Fetch;
  children: ReactNode;
}) {
  const state = useSyncExternalStore(
    (listener) => signIn.subscribe(listener),
    () => signIn.state,
  );

  useEffect(() => {
    void signIn.restore();
  }, [signIn]);

  const fetch = useMemo(
    () => createSignedInFetch({ getToken: signIn.getToken, onUnauthorized: signIn.onUnauthorized, fetch: baseFetch }),
    [signIn, baseFetch],
  );
  const status = useMemo(
    () => (config.statusUrl ? createStatusClient({ baseUrl: config.statusUrl, project: config.project, fetch }) : null),
    [config, fetch],
  );
  const session = useMemo(() => ({ state, signIn, config, fetch, status }), [state, signIn, config, fetch, status]);
  return <SessionContext.Provider value={session}>{children}</SessionContext.Provider>;
}

export function useSession(): Session {
  const session = useContext(SessionContext);
  if (!session) throw new Error('useSession needs a SessionProvider: the root layout renders one');
  return session;
}

/** The signed-in person. Screens under (tabs) only render while someone is signed in. */
export function useSignedInUser(): SignedInUser {
  const { state } = useSession();
  if (state.kind !== 'signed-in') throw new Error('Nobody is signed in');
  return state.user;
}

/** The fetch a screen's own service client is built on (command-center/D29). */
export function useSignedInFetch(): Fetch {
  return useSession().fetch;
}

/** The status client for this build's environment, or null when the build has no status URL yet. */
export function useStatusClient(): StatusClient | null {
  return useSession().status;
}
