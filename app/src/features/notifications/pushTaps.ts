// Opening the app from a push (notifications D1): a tap on a blocking item or the digest opens the inbox, and a tap
// on a test notification opens the notifications screen. The notifier names the route in the push's data, as `url`
// (services/notify/notify/notifier.py); only these two are followed, so a push can never open anything else.
//
// The shell's root (src/shell/AppRoot.tsx) listens with expoPushTaps; tests give it a fake.

import * as Notifications from 'expo-notifications';
import { useEffect } from 'react';

export const PUSH_ROUTES = ['/inbox', '/notifications'] as const;
export type PushRoute = (typeof PUSH_ROUTES)[number];

export type PushTaps = {
  /** Calls `onTap` with each tapped push's data while the app runs; answers how to stop. */
  subscribe(onTap: (data: unknown) => void): () => void;
  /** The data of the push whose tap launched the app, or null. */
  launchedBy(): Promise<unknown>;
};

/** The route a push's data opens: its `url` when it is one the app follows, else the inbox (D1). */
export function routeOfPush(data: unknown): PushRoute {
  const url = (data as { url?: unknown } | null | undefined)?.url;
  return PUSH_ROUTES.find((route) => route === url) ?? '/inbox';
}

export const expoPushTaps: PushTaps = {
  subscribe(onTap) {
    const subscription = Notifications.addNotificationResponseReceivedListener((response) =>
      onTap(response.notification.request.content.data),
    );
    return () => subscription.remove();
  },
  async launchedBy() {
    const response = await Notifications.getLastNotificationResponseAsync();
    return response ? response.notification.request.content.data : null;
  },
};

/** Opens the route of each tapped push, and of the one that launched the app, while a person is signed in. */
export function useOpenFromPush(taps: PushTaps, open: (route: PushRoute) => void) {
  useEffect(() => {
    let live = true;
    const stop = taps.subscribe((data) => open(routeOfPush(data)));
    void taps.launchedBy().then(
      (data) => {
        if (live && data !== null && data !== undefined) open(routeOfPush(data));
      },
      () => undefined,
    );
    return () => {
      live = false;
      stop();
    };
  }, [taps, open]);
}
