// /loops/[loop]: one loop and every one of its concerns.

import { useLocalSearchParams } from 'expo-router';

import { LoopScreen } from '../../../../features/loops/LoopScreen';

export default function LoopRoute() {
  const { loop } = useLocalSearchParams<{ loop: string }>();
  return <LoopScreen loopId={String(loop)} />;
}
