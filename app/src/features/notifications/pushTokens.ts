// Where the screen gets this device's Expo push token from (command-center/notifications C1). The screen only talks
// to this shape, so its tests give it a fake device and a build gives it the real one.
//
// The real one is expo-notifications' requestPermissionsAsync and getExpoPushTokenAsync, with the EAS project id
// from app.json. The app does not have that package yet: adding it changes app/package.json and app.json's plugins,
// which this concern does not touch, so until then the route passes null and the screen says why it cannot
// register this device.

export type PushPermission = 'granted' | 'denied' | 'undetermined';

export type PushTokenSource = {
  readonly platform: 'ios' | 'android';
  /** Asks to show notifications (the system asks the person the first time) and answers what they chose. */
  requestPermission(): Promise<PushPermission>;
  /** This device's Expo push token, ExponentPushToken[...]. Only called once permission is granted. */
  getExpoPushToken(): Promise<string>;
};

export const NO_PUSH_MODULE_MESSAGE =
  'This build cannot register a device for push yet: it has no notification module. A build that adds ' +
  'expo-notifications to app/package.json and app.json can.';
