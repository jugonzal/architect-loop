// The notifications screen (command-center/notifications), at /notifications beside the tabs, so it edits no file of
// the shell's. It builds the notify client from the build's notify URL and the signed-in fetch (command-center/D55),
// and draws src/features/notifications/. A test notification's data opens this route.
//
// This build has no notification module, so it passes no push token source and the screen says why this device
// cannot register yet (src/features/notifications/pushTokens.ts).

import { useRouter } from 'expo-router';
import { useMemo } from 'react';

import { createNotifyClient } from '../../api/notify.gen';
import { NotificationsScreen } from '../../features/notifications/NotificationsScreen';
import { useSession } from '../../shell/session';

export default function NotificationsRoute() {
  const { config, fetch } = useSession();
  const router = useRouter();
  const notify = useMemo(
    () => (config.notifyUrl ? createNotifyClient({ baseUrl: config.notifyUrl, fetch }) : null),
    [config.notifyUrl, fetch],
  );
  return (
    <NotificationsScreen
      notify={notify}
      project={config.project}
      pushTokens={null}
      onBack={() => (router.canGoBack() ? router.back() : router.navigate('/inbox'))}
    />
  );
}
