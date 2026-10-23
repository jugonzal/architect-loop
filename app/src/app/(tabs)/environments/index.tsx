// The Environments tab (command-center/app-environments), in the folder the shell names after it
// (src/shell/tabs.ts). It reads the session's status client and draws src/features/environments/. A card's
// ship-brief link opens Needs you, where the inbox shows the ship card, so the brief is never drawn twice. Needs
// you has no route for one card yet, so the link opens the tab and the item's id goes unused.

import { useRouter } from 'expo-router';

import { EnvironmentsScreen } from '../../../features/environments/EnvironmentsScreen';
import { useStatusClient } from '../../../shell/session';

export default function EnvironmentsTab() {
  const status = useStatusClient();
  const router = useRouter();
  return <EnvironmentsScreen status={status} onOpenShipCard={() => router.navigate('/inbox')} />;
}
