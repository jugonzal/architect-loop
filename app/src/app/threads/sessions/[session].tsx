// /threads/sessions/[session]: an agent session's thread (app-threads C1), at the path command-center/D52 fixes, by
// the runner's id for the session. A question card (app-inbox) and an accepted "record this?" open it.

import { useLocalSearchParams } from 'expo-router';

import { ThreadScreen } from '../../../features/threads/ThreadScreen';

export default function SessionThreadRoute() {
  const { session } = useLocalSearchParams<{ session: string }>();
  return <ThreadScreen thread={{ scope: 'session', session: String(session) }} />;
}
