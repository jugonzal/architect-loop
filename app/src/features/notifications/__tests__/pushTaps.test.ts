// command-center/notifications D1, the rule on its own: the route a tapped push opens, and the expo-notifications
// sources the app uses for taps and tokens.

jest.mock('expo-notifications', () => {
  const listeners: ((response: unknown) => void)[] = [];
  return {
    AndroidImportance: { HIGH: 4 },
    addNotificationResponseReceivedListener: jest.fn((listener) => {
      listeners.push(listener);
      return { remove: jest.fn(() => listeners.splice(listeners.indexOf(listener), 1)) };
    }),
    getLastNotificationResponseAsync: jest.fn(async () => null),
    getPermissionsAsync: jest.fn(async () => ({ granted: false, canAskAgain: true })),
    requestPermissionsAsync: jest.fn(async () => ({ granted: true, canAskAgain: true })),
    getExpoPushTokenAsync: jest.fn(async () => ({ type: 'expo', data: 'ExponentPushToken[from-expo]' })),
    setNotificationChannelAsync: jest.fn(async () => null),
    __listeners: listeners,
  };
});

// The token's EAS project comes from app.json's extra.eas.projectId, as a build's config has it.
jest.mock('expo-constants', () => ({
  __esModule: true,
  default: { expoConfig: require('../../../../app.json').expo },
}));

import * as Notifications from 'expo-notifications';

import { expoPushTaps, routeOfPush } from '../pushTaps';
import { easProjectId, expoPushTokens } from '../pushTokens';

const mocked = Notifications as unknown as typeof Notifications & { __listeners: ((r: unknown) => void)[] };
const response = (data: unknown) => ({ notification: { request: { content: { data } } } });

describe('routeOfPush', () => {
  it('follows only the two routes the notifier names, and opens the inbox otherwise', () => {
    expect(routeOfPush({ url: '/inbox', item: 'x' })).toBe('/inbox');
    expect(routeOfPush({ url: '/notifications', test: true })).toBe('/notifications');
    expect(routeOfPush({ url: '/threads/sessions/1' })).toBe('/inbox');
    expect(routeOfPush({ url: 'architectloop://anything' })).toBe('/inbox');
    expect(routeOfPush(null)).toBe('/inbox');
  });
});

describe("expo-notifications' taps", () => {
  it("hands each tapped push's data on, until it is stopped", () => {
    const onTap = jest.fn();
    const stop = expoPushTaps.subscribe(onTap);
    mocked.__listeners.forEach((l) => l(response({ url: '/inbox' })));
    expect(onTap).toHaveBeenCalledWith({ url: '/inbox' });
    stop();
    expect(mocked.__listeners).toHaveLength(0);
  });

  it('answers the data of the push that launched the app, or null', async () => {
    await expect(expoPushTaps.launchedBy()).resolves.toBeNull();
    jest.mocked(Notifications.getLastNotificationResponseAsync).mockResolvedValueOnce(
      response({ url: '/notifications' }) as never,
    );
    await expect(expoPushTaps.launchedBy()).resolves.toEqual({ url: '/notifications' });
  });
});

describe("expo-notifications' push tokens", () => {
  it("asks for permission, then answers this device's Expo push token for the app's EAS project", async () => {
    expect(easProjectId()).toMatch(/^[0-9a-f-]{36}$/);
    const tokens = expoPushTokens();
    expect(tokens?.platform).toBe('ios');
    await expect(tokens!.requestPermission()).resolves.toBe('granted');
    expect(Notifications.requestPermissionsAsync).toHaveBeenCalled();
    await expect(tokens!.getExpoPushToken()).resolves.toBe('ExponentPushToken[from-expo]');
    expect(Notifications.getExpoPushTokenAsync).toHaveBeenCalledWith({ projectId: easProjectId() });
  });

  it('says denied once the person refused and the system will not ask again', async () => {
    jest.mocked(Notifications.requestPermissionsAsync).mockResolvedValueOnce({ granted: false, canAskAgain: false } as never);
    await expect(expoPushTokens()!.requestPermission()).resolves.toBe('denied');
  });
});
