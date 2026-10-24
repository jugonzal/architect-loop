// The Needs you tab (app-inbox): a stack of the list and one item, under the shell's tab bar and header. The tab
// reads the project's status once, here, and its screens share it (features/inbox/InboxStatus.tsx).

import { Stack } from 'expo-router';

import { InboxStatusProvider } from '../../../features/inbox/InboxStatus';
import { colors } from '../../../theme';

export default function InboxLayout() {
  return (
    <InboxStatusProvider>
      <Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: colors.ground } }} />
    </InboxStatusProvider>
  );
}
