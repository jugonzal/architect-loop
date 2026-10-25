// /threads/loops/[loop]/concerns/[concern]: a concern's thread (app-threads C1), at the path command-center/D52
// fixes. The Concern page's thread link opens it (app-loops-board).

import { useLocalSearchParams } from 'expo-router';

import { ThreadScreen } from '../../../../../features/threads/ThreadScreen';

export default function ConcernThreadRoute() {
  const { loop, concern } = useLocalSearchParams<{ loop: string; concern: string }>();
  return <ThreadScreen thread={{ scope: 'concern', loop: String(loop), concern: String(concern) }} />;
}
