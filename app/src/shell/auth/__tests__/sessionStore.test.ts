const mockItems = new Map<string, string>();

jest.mock('expo-secure-store', () => ({
  getItemAsync: jest.fn(async (key: string) => mockItems.get(key) ?? null),
  setItemAsync: jest.fn(async (key: string, value: string) => void mockItems.set(key, value)),
  deleteItemAsync: jest.fn(async (key: string) => void mockItems.delete(key)),
}));

import { secureSessionStore } from '../sessionStore';

describe('the session store', () => {
  beforeEach(() => mockItems.clear());

  it('keeps the token and who it belongs to in secure storage, and forgets them on clear', async () => {
    const session = { token: 'gho_x', user: { login: 'octocat', name: 'Mona Lisa Octocat' } };
    await secureSessionStore.save(session);
    expect(await secureSessionStore.load()).toEqual(session);
    await secureSessionStore.clear();
    expect(await secureSessionStore.load()).toBeNull();
  });

  it('reads anything it cannot use as no session, rather than fail the launch', async () => {
    mockItems.set('github-session', 'not json');
    expect(await secureSessionStore.load()).toBeNull();
    mockItems.set('github-session', JSON.stringify({ token: 1 }));
    expect(await secureSessionStore.load()).toBeNull();
  });
});
