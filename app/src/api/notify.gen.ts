/* eslint-disable */
// Generated from services/notify/openapi.yaml by src/api/generate-clients.js.
// Do not edit by hand: change the OpenAPI file, then run `npm run generate:clients` (command-center/D55).

import { operationCaller, type OperationSpec, type ServiceClientOptions } from './service';

/**
 * The device's operating system.
 */
export type Platform = 'ios' | 'android';
/**
 * A time of day, HH:MM, in the person's time zone.
 */
export type Clock = string;

/**
 * The notify service's operations, as services/notify/openapi.yaml (version 1.0.0) declares them: each one's request, and its responses' bodies by status.
 */
export interface NotifyOperations {
  /**
   * The commit this deployment was built from (command-center/D32).
   */
  getVersion: {
    responses: {
      /**
       * The commit.
       */
      '200': Version;
    };
  };
  /**
   * Read each project's queue once, and send what is due (C2, C3).
   */
  tick: {
    responses: {
      /**
       * What the tick read and sent, for each project.
       */
      '200': Tick;
      /**
       * No token, or a token GitHub does not accept.
       */
      '401': Error;
      /**
       * GitHub, the status service, Google's keys or Expo cannot be reached, or the service is not configured. Nothing is sent instead.
       */
      '503': Error;
    };
  };
  /**
   * The caller's devices registered for push in the project, oldest first.
   */
  listDevices: {
    request: {
      path: {
        /**
         * The project's owner on GitHub.
         */
        owner: string;
        /**
         * The project's repository name.
         */
        repo: string;
      };
    };
    responses: {
      /**
       * The caller's devices, and no one else's.
       */
      '200': DeviceList;
      /**
       * The request is malformed, or its settings cannot be saved.
       */
      '400': Error;
      /**
       * No token, or a token GitHub does not accept.
       */
      '401': Error;
      /**
       * The project is not served here, the caller has no such device, or there is no such path.
       */
      '404': Error;
      /**
       * GitHub, the status service, Google's keys or Expo cannot be reached, or the service is not configured. Nothing is sent instead.
       */
      '503': Error;
    };
  };
  /**
   * Register this device's Expo push token for the caller.
   */
  registerDevice: {
    request: {
      path: {
        /**
         * The project's owner on GitHub.
         */
        owner: string;
        /**
         * The project's repository name.
         */
        repo: string;
      };
      body: NewDevice;
    };
    responses: {
      /**
       * The device, registered to the caller.
       */
      '200': Device;
      /**
       * The request is malformed, or its settings cannot be saved.
       */
      '400': Error;
      /**
       * No token, or a token GitHub does not accept.
       */
      '401': Error;
      /**
       * The status document names the caller as no loop's owner or member, so no device is registered.
       */
      '403': Error;
      /**
       * The project is not served here, the caller has no such device, or there is no such path.
       */
      '404': Error;
      /**
       * GitHub, the status service, Google's keys or Expo cannot be reached, or the service is not configured. Nothing is sent instead.
       */
      '503': Error;
    };
  };
  /**
   * Stop pushing to one of the caller's devices.
   */
  unregisterDevice: {
    request: {
      path: {
        /**
         * The project's owner on GitHub.
         */
        owner: string;
        /**
         * The project's repository name.
         */
        repo: string;
        /**
         * The device's id, as registering it answered.
         */
        device: string;
      };
    };
    responses: {
      /**
       * The device is no longer registered.
       */
      '204': null;
      /**
       * The request is malformed, or its settings cannot be saved.
       */
      '400': Error;
      /**
       * No token, or a token GitHub does not accept.
       */
      '401': Error;
      /**
       * The project is not served here, the caller has no such device, or there is no such path.
       */
      '404': Error;
      /**
       * GitHub, the status service, Google's keys or Expo cannot be reached, or the service is not configured. Nothing is sent instead.
       */
      '503': Error;
    };
  };
  /**
   * Push a test notification to the caller's own devices, and no one else's (C1).
   */
  sendTestNotification: {
    request: {
      path: {
        /**
         * The project's owner on GitHub.
         */
        owner: string;
        /**
         * The project's repository name.
         */
        repo: string;
      };
    };
    responses: {
      /**
       * What Expo said of the push to each of the caller's devices.
       */
      '200': Delivery;
      /**
       * The request is malformed, or its settings cannot be saved.
       */
      '400': Error;
      /**
       * No token, or a token GitHub does not accept.
       */
      '401': Error;
      /**
       * The project is not served here, the caller has no such device, or there is no such path.
       */
      '404': Error;
      /**
       * A test notification was sent to the caller less than a minute ago.
       */
      '429': Error;
      /**
       * GitHub, the status service, Google's keys or Expo cannot be reached, or the service is not configured. Nothing is sent instead.
       */
      '503': Error;
    };
  };
  /**
   * The caller's digest time, time zone and quiet hours, or the defaults until they save some.
   */
  getSettings: {
    request: {
      path: {
        /**
         * The project's owner on GitHub.
         */
        owner: string;
        /**
         * The project's repository name.
         */
        repo: string;
      };
    };
    responses: {
      /**
       * The caller's settings.
       */
      '200': Settings;
      /**
       * The request is malformed, or its settings cannot be saved.
       */
      '400': Error;
      /**
       * No token, or a token GitHub does not accept.
       */
      '401': Error;
      /**
       * The project is not served here, the caller has no such device, or there is no such path.
       */
      '404': Error;
      /**
       * GitHub, the status service, Google's keys or Expo cannot be reached, or the service is not configured. Nothing is sent instead.
       */
      '503': Error;
    };
  };
  /**
   * Save the caller's digest time, time zone and quiet hours, all three at once (C3).
   */
  putSettings: {
    request: {
      path: {
        /**
         * The project's owner on GitHub.
         */
        owner: string;
        /**
         * The project's repository name.
         */
        repo: string;
      };
      body: SettingsInput;
    };
    responses: {
      /**
       * The caller's settings.
       */
      '200': Settings;
      /**
       * The request is malformed, or its settings cannot be saved.
       */
      '400': Error;
      /**
       * No token, or a token GitHub does not accept.
       */
      '401': Error;
      /**
       * The project is not served here, the caller has no such device, or there is no such path.
       */
      '404': Error;
      /**
       * GitHub, the status service, Google's keys or Expo cannot be reached, or the service is not configured. Nothing is sent instead.
       */
      '503': Error;
    };
  };
}
export interface Version {
  /**
   * The commit this deployment was built from, or `unknown` when the build did not say.
   */
  commit: string;
}
export interface Tick {
  reads: {
    project: string;
    /**
     * Whether the project's status document was read; nothing is sent from a failed read.
     */
    read: boolean;
    /**
     * Why it was not read, or null.
     */
    error: string | null;
    /**
     * Whether this was the project's first read, which marks what stands and sends none of it.
     */
    baseline: boolean;
    /**
     * How many blocking items were pushed, each to the person it waits on.
     */
    pushed: number;
    /**
     * How many blocking items wait for their person's quiet hours to end.
     */
    deferred: number;
    /**
     * How many people's digests came due on this tick.
     */
    digests: number;
  }[];
}
export interface Error {
  error: 'bad_request' | 'unauthorized' | 'forbidden' | 'not_found' | 'too_many_requests' | 'unavailable' | 'internal';
  /**
   * What went wrong, for people.
   */
  message: string;
}
export interface DeviceList {
  devices: Device[];
}
/**
 * A device registered for push. Its push token is never answered.
 */
export interface Device {
  /**
   * The device's id, the same whenever its push token is registered.
   */
  id: string;
  platform: Platform;
  /**
   * What the person calls the device, or null.
   */
  name: string | null;
  /**
   * When the caller first registered it.
   */
  registered_at: string;
}
export interface NewDevice {
  /**
   * The device's Expo push token.
   */
  token: string;
  platform: Platform;
  /**
   * What the person calls the device, or null.
   */
  name?: string | null;
  /**
   * The device's IANA time zone, which the caller's settings start in if they have saved none.
   */
  timezone?: string;
}
export interface Delivery {
  /**
   * How many devices the caller has registered; 0 means nothing was sent.
   */
  devices: number;
  /**
   * How many of them Expo accepted the push for.
   */
  accepted: number;
  /**
   * How many Expo said no longer exist; they are no longer registered.
   */
  gone: number;
}
export interface Settings {
  timezone: string;
  digest_time: Clock | null;
  quiet_hours: QuietHours | null;
  /**
   * Whether the person saved these; false while they are the defaults.
   */
  saved: boolean;
}
/**
 * From `start`, up to but not including `end`, every day; it may run past midnight. Nothing is pushed then.
 */
export interface QuietHours {
  start: Clock;
  end: Clock;
}
/**
 * All three, every time. The digest time may not fall in the quiet hours, and their start and end differ.
 */
export interface SettingsInput {
  /**
   * An IANA time zone, such as America/New_York or UTC, that the two times are in.
   */
  timezone: string;
  /**
   * When the digest arrives each day, or null for no digest.
   */
  digest_time: Clock | null;
  /**
   * When nothing is pushed, or null for no quiet hours.
   */
  quiet_hours: QuietHours | null;
}

/**
 * The method, path and success statuses of each of the notify service's operations, which the client calls.
 */
export const NOTIFY_OPERATIONS: { readonly [Operation in keyof NotifyOperations]: OperationSpec } = {
  getVersion: { method: 'GET', path: '/version', ok: { 200: 'json' } },
  tick: { method: 'POST', path: '/tick', ok: { 200: 'json' } },
  listDevices: { method: 'GET', path: '/projects/{owner}/{repo}/devices', ok: { 200: 'json' } },
  registerDevice: { method: 'POST', path: '/projects/{owner}/{repo}/devices', ok: { 200: 'json' } },
  unregisterDevice: { method: 'DELETE', path: '/projects/{owner}/{repo}/devices/{device}', ok: { 204: 'empty' } },
  sendTestNotification: { method: 'POST', path: '/projects/{owner}/{repo}/test-notification', ok: { 200: 'json' } },
  getSettings: { method: 'GET', path: '/projects/{owner}/{repo}/settings/me', ok: { 200: 'json' } },
  putSettings: { method: 'PUT', path: '/projects/{owner}/{repo}/settings/me', ok: { 200: 'json' } },
};

/**
 * The notify service's client, generated from services/notify/openapi.yaml: one method per operation
 * the app calls. Each call goes through the signed-in fetch the client was made with, to the base URL it was
 * made with, and resolves to the body of a success response. Any other answer rejects with a ServiceError
 * (service.ts) that carries the status and the body, typed for each status in NotifyOperations. A client made with
 * no base URL never calls the service: each method rejects with a 'not-configured' ServiceError that says
 * which URL the build is missing.
 */
export interface NotifyClient {
  /**
   * The commit this deployment was built from (command-center/D32).
   *
   * `GET /version`
   */
  getVersion(): Promise<NotifyOperations['getVersion']['responses']['200']>;
  /**
   * Read each project's queue once, and send what is due (C2, C3).
   *
   * The notifier's Cloud Scheduler job calls this every minute, with an OIDC token for the notifier's own
   * service identity whose audience is the notifier's URL (notifications D3, command-center/D67). Any other
   * token is refused. The app never calls it.
   *
   * `POST /tick`
   */
  tick(): Promise<NotifyOperations['tick']['responses']['200']>;
  /**
   * The caller's devices registered for push in the project, oldest first.
   *
   * `GET /projects/{owner}/{repo}/devices`
   */
  listDevices(
    request: NotifyOperations['listDevices']['request'],
  ): Promise<NotifyOperations['listDevices']['responses']['200']>;
  /**
   * Register this device's Expo push token for the caller.
   *
   * Registering a token that is already registered keeps one device: it stays the caller's, or moves to the
   * caller from whoever registered it before. When the caller has saved no settings yet and the request names
   * a time zone, their settings start as the defaults in that time zone.
   *
   * `POST /projects/{owner}/{repo}/devices`
   */
  registerDevice(
    request: NotifyOperations['registerDevice']['request'],
  ): Promise<NotifyOperations['registerDevice']['responses']['200']>;
  /**
   * Stop pushing to one of the caller's devices.
   *
   * `DELETE /projects/{owner}/{repo}/devices/{device}`
   */
  unregisterDevice(
    request: NotifyOperations['unregisterDevice']['request'],
  ): Promise<NotifyOperations['unregisterDevice']['responses']['204']>;
  /**
   * Push a test notification to the caller's own devices, and no one else's (C1).
   *
   * At most one a minute for each person.
   *
   * `POST /projects/{owner}/{repo}/test-notification`
   */
  sendTestNotification(
    request: NotifyOperations['sendTestNotification']['request'],
  ): Promise<NotifyOperations['sendTestNotification']['responses']['200']>;
  /**
   * The caller's digest time, time zone and quiet hours, or the defaults until they save some.
   *
   * `GET /projects/{owner}/{repo}/settings/me`
   */
  getSettings(
    request: NotifyOperations['getSettings']['request'],
  ): Promise<NotifyOperations['getSettings']['responses']['200']>;
  /**
   * Save the caller's digest time, time zone and quiet hours, all three at once (C3).
   *
   * `PUT /projects/{owner}/{repo}/settings/me`
   */
  putSettings(
    request: NotifyOperations['putSettings']['request'],
  ): Promise<NotifyOperations['putSettings']['responses']['200']>;
}

/**
 * Makes the notify service's client from this build's URL for it (AppConfig.notifyUrl, null while the
 * build has none) and the signed-in fetch (useSignedInFetch).
 */
export function createNotifyClient(options: ServiceClientOptions): NotifyClient {
  const call = operationCaller('notify', NOTIFY_OPERATIONS, options);
  return {
    getVersion: () => call<NotifyOperations['getVersion']['responses']['200']>('getVersion'),
    tick: () => call<NotifyOperations['tick']['responses']['200']>('tick'),
    listDevices: (request) => call<NotifyOperations['listDevices']['responses']['200']>('listDevices', request),
    registerDevice: (request) =>
      call<NotifyOperations['registerDevice']['responses']['200']>('registerDevice', request),
    unregisterDevice: (request) =>
      call<NotifyOperations['unregisterDevice']['responses']['204']>('unregisterDevice', request),
    sendTestNotification: (request) =>
      call<NotifyOperations['sendTestNotification']['responses']['200']>('sendTestNotification', request),
    getSettings: (request) => call<NotifyOperations['getSettings']['responses']['200']>('getSettings', request),
    putSettings: (request) => call<NotifyOperations['putSettings']['responses']['200']>('putSettings', request),
  };
}
