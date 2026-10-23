// The Loops tab (app-loops-board): a stack of the board, a loop and a concern, under the shell's tab bar and
// header. The tab reads the project's status once, here, and its screens share it (features/loops/LoopsStatus.tsx).

import { Stack } from 'expo-router';

import { LoopsStatusProvider } from '../../../features/loops/LoopsStatus';
import { colors } from '../../../theme';

export default function LoopsLayout() {
  return (
    <LoopsStatusProvider>
      <Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: colors.ground } }} />
    </LoopsStatusProvider>
  );
}
