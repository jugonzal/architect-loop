// Where the screen gets this device's Expo push token from (command-center/notifications C1). The screen only talks
// to this shape, so its tests give it a fake device and a build gives it expo-notifications (notifications D4).

import Constants from 'expo-constants';
import * as Notifications from 'expo-notifications';
import { Platform } from 'react-native';

export type PushPermission = 'granted' | 'denied' | 'undetermined';

export type PushTokenSource = {
  readonly platform: 'ios' | 'android';
  /** Asks to show notifications (the system asks the person the first time) and answers what they chose. */
  requestPermission(): Promise<PushPermission>;
  /** This device's Expo push token, ExponentPushToken[...]. Only called once permission is granted. */
  getExpoPushToken(): Promise<string>;
};

export const NO_PUSH_MODULE_MESSAGE =
  'This device cannot register for push: notifications reach only an iPhone or an Android phone, in a build with ' +
  "the app's EAS project id.";

/** The EAS project an Expo push token is issued for: app.json's extra.eas.projectId. */
export function easProjectId(): string | null {
  const extra = Constants.expoConfig?.extra as { eas?: { projectId?: unknown } } | undefined;
  const id = extra?.eas?.projectId;
  return typeof id === 'string' && id ? id : null;
}

/**
 * This device's push tokens through expo-notifications, or null where there are none to have: on the web, or in a
 * build without an EAS project id. Android also needs a notification channel before it asks, so one is made first.
 */
export function expoPushTokens(): PushTokenSource | null {
  const projectId = easProjectId();
  if ((Platform.OS !== 'ios' && Platform.OS !== 'android') || !projectId) return null;
  const platform = Platform.OS;
  return {
    platform,
    async requestPermission() {
      if (platform === 'android') {
        await Notifications.setNotificationChannelAsync('default', {
          name: 'Needs you',
          importance: Notifications.AndroidImportance.HIGH,
        });
      }
      const current = await Notifications.getPermissionsAsync();
      const answer = current.granted ? current : await Notifications.requestPermissionsAsync();
      return answer.granted ? 'granted' : answer.canAskAgain ? 'undetermined' : 'denied';
    },
    async getExpoPushToken() {
      return (await Notifications.getExpoPushTokenAsync({ projectId })).data;
    },
  };
}
