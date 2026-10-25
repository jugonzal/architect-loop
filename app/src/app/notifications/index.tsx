// The notifications screen (command-center/notifications), at /notifications beside the tabs. The account sheet in
// the shell's header links here, and a tap on a test notification opens it. It builds the notify client from the
// build's notify URL and the signed-in fetch (command-center/D55), gets this device's push token through
// expo-notifications, and draws src/features/notifications/.

import { useRouter } from 'expo-router';
import { useMemo } from 'react';

import { createNotifyClient } from '../../api/notify.gen';
import { NotificationsScreen } from '../../features/notifications/NotificationsScreen';
import { expoPushTokens, type PushTokenSource } from '../../features/notifications/pushTokens';
import { useSession } from '../../shell/session';

export default function NotificationsRoute({ pushTokens }: { pushTokens?: PushTokenSource | null }) {
  const { config, fetch } = useSession();
  const router = useRouter();
  const notify = useMemo(
    () => (config.notifyUrl ? createNotifyClient({ baseUrl: config.notifyUrl, fetch }) : null),
    [config.notifyUrl, fetch],
  );
  const tokens = useMemo(() => (pushTokens === undefined ? expoPushTokens() : pushTokens), [pushTokens]);
  return (
    <NotificationsScreen
      notify={notify}
      project={config.project}
      pushTokens={tokens}
      onBack={() => (router.canGoBack() ? router.back() : router.navigate('/inbox'))}
    />
  );
}
