// /threads/loops/[loop]: a loop's thread (app-threads C1), at the path command-center/D52 fixes, so app-inbox and
// app-loops-board link here without waiting for this concern. It opens over the tabs, from the root stack.

import { useLocalSearchParams } from 'expo-router';

import { ThreadScreen } from '../../../../features/threads/ThreadScreen';

export default function LoopThreadRoute() {
  const { loop } = useLocalSearchParams<{ loop: string }>();
  return <ThreadScreen thread={{ scope: 'loop', loop: String(loop) }} />;
}
