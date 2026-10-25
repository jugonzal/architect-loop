// /inbox/[item]: one item's card, by its id, which is one encoded segment (app-inbox C1, C2).

import { useLocalSearchParams } from 'expo-router';

import { ItemScreen } from '../../../features/inbox/ItemScreen';

export default function InboxItemRoute() {
  const { item } = useLocalSearchParams<{ item: string }>();
  return <ItemScreen itemId={String(item)} />;
}
