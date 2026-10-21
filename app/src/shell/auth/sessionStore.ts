// Where the person's sign-in is kept between launches: the token and who it belongs to, in the platform's secure
// storage (the iOS keychain, Android's keystore-backed storage), never in plain storage.

import * as SecureStore from 'expo-secure-store';

export type StoredSession = {
  token: string;
  user: { login: string; name: string | null };
};

export type SessionStore = {
  load(): Promise<StoredSession | null>;
  save(session: StoredSession): Promise<void>;
  clear(): Promise<void>;
};

const KEY = 'github-session';

function parse(raw: string | null): StoredSession | null {
  if (!raw) return null;
  try {
    const value = JSON.parse(raw) as Partial<StoredSession>;
    if (typeof value.token !== 'string' || !value.user || typeof value.user.login !== 'string') return null;
    return { token: value.token, user: { login: value.user.login, name: value.user.name ?? null } };
  } catch {
    return null;
  }
}

export const secureSessionStore: SessionStore = {
  async load() {
    return parse(await SecureStore.getItemAsync(KEY));
  },
  async save(session) {
    await SecureStore.setItemAsync(KEY, JSON.stringify(session));
  },
  async clear() {
    await SecureStore.deleteItemAsync(KEY);
  },
};

/** A store that forgets on restart, for tests. */
export function memorySessionStore(initial: StoredSession | null = null): SessionStore & { current: StoredSession | null } {
  const store = {
    current: initial,
    async load() {
      return store.current;
    },
    async save(session: StoredSession) {
      store.current = session;
    },
    async clear() {
      store.current = null;
    },
  };
  return store;
}
