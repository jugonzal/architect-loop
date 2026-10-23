// /loops/[loop]/concerns/[concern]: one concern's state, contract and claims (app-loops-board C2).

import { useLocalSearchParams } from 'expo-router';

import { ConcernScreen } from '../../../../../features/loops/ConcernScreen';

export default function ConcernRoute() {
  const { loop, concern } = useLocalSearchParams<{ loop: string; concern: string }>();
  return <ConcernScreen loopId={String(loop)} concernId={String(concern)} />;
}
