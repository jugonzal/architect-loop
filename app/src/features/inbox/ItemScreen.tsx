// One item of Needs you on its own screen, after the Question and Review artboards (command-center/D4): back to
// the list, the item's loop and kind, who can finish it when that is not the person, and its body by kind
// (cards.tsx). An item the status no longer queues for the person says so instead of showing an old copy.

import { useRouter } from 'expo-router';
import { Text, View } from 'react-native';

import { ItemBody, WhoNotice } from './cards';
import { useInbox } from './InboxStatus';
import { entryFor, KIND_LABELS } from './queue';
import { BackButton, InboxPage, Notice, styles } from './ui';

export function ItemScreen({ itemId }: { itemId: string }) {
  const router = useRouter();
  const { login } = useInbox();
  return (
    <InboxPage testID="inbox-item">
      {(doc) => {
        const entry = entryFor(doc, login, itemId);
        return (
          <>
            <View style={styles.topBar}>
              <BackButton label="Needs you" onPress={() => router.dismissTo('/inbox')} />
              {entry && (
                <Text style={styles.topRef} numberOfLines={1}>
                  {`${entry.item.loop ?? 'across loops'} · ${KIND_LABELS[entry.item.kind]}`}
                </Text>
              )}
            </View>
            {entry ? (
              <>
                <WhoNotice entry={entry} />
                <ItemBody entry={entry} doc={doc} />
              </>
            ) : (
              <Notice text={`${itemId} is not in Needs you any more: the status no longer queues it for you.`} />
            )}
          </>
        );
      }}
    </InboxPage>
  );
}
