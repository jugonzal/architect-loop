// Needs you (command-center/app-inbox C1), after the Inbox artboard (command-center/D4): every item waiting on the
// signed-in person, most unblocking first, each a card that opens its own screen. Below them, read-only, what waits
// on someone else in the person's loops (command-center/D10), and what waits on no one named. The artboard's
// supply-reality and objection cards and its digest filter belong to later loops and are left out.

import { useRouter } from 'expo-router';
import { Text, View } from 'react-native';

import type { QueueItem, StatusDocument } from '../../api/status';
import { useInbox } from './InboxStatus';
import { inboxFor, itemHref, KIND_LABELS, type InboxEntry } from './queue';
import { Button, Card, Chip, InboxPage, SectionLabel, styles } from './ui';

const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`;

/** The line under a card's title, from the item's own facts. */
export function itemSummary(item: QueueItem): string {
  switch (item.kind) {
    case 'question': {
      const { ref, blocks } = item.detail;
      const q = ref.split('/').pop();
      const fallback = item.detail.default ? `default if unanswered: ${item.detail.default}` : 'no default';
      return `${q} blocks ${blocks.length ? blocks.join(', ') : 'nothing yet'} · ${fallback}`;
    }
    case 'review': {
      const { pr } = item.detail;
      return `PR #${pr.number} · checks ${pr.checks}${pr.draft ? ' · draft' : ''}`;
    }
    case 'ship':
      return `${item.detail.environment} · ${plural(item.detail.manual_steps.length, 'manual step', 'manual steps')}`;
    case 'record':
      return item.detail.path;
    case 'proof':
      return `${item.detail.claim} on ${item.detail.environment} needs ${item.detail.missing}`;
    case 'fact':
      return `${item.detail.fact} · ${plural(item.concerns.length, 'concern waits', 'concerns wait')}`;
    case 'stuck':
      return `${item.detail.concern} is ${item.detail.state}`;
    case 'contradiction':
      return `${item.detail.claim}: ${item.detail.evidence.verdict} on ${item.detail.evidence.environment}`;
    case 'refused_pr':
      return `PR #${item.detail.pr.number} · ${plural(item.detail.failures.length, 'failure', 'failures')}`;
  }
}

/** What a card's button says: the person's next step on an item that is theirs, or only a look. */
export function actionLabel(entry: InboxEntry, yours: boolean): string {
  if (!yours) return 'View';
  switch (entry.actionable ? entry.item.kind : null) {
    case 'question':
      return 'Answer';
    case 'review':
      return 'Read evidence';
    case 'ship':
      return 'Read the brief';
    case 'record':
      return 'Read the text';
    default:
      return 'Details';
  }
}

export function InboxScreen() {
  return <InboxPage testID="inbox-list">{(doc) => <InboxBody doc={doc} />}</InboxPage>;
}

function InboxBody({ doc }: { doc: StatusDocument }) {
  const router = useRouter();
  const { login } = useInbox();
  const inbox = inboxFor(doc, login);
  const n = inbox.mine.length;
  const open = (entry: InboxEntry) => router.push(itemHref(entry.item.id));
  return (
    <>
      <View style={styles.heading}>
        <Text style={styles.overline}>Most unblocking first</Text>
        <Text style={styles.title} accessibilityRole="header">
          Needs you
        </Text>
        <Text style={styles.subtitle} testID="inbox-count">
          {n === 0
            ? 'Nothing waits on you.'
            : `${plural(n, 'item waits', 'items wait')} on you, sorted by how much each one unblocks.`}
        </Text>
      </View>
      <View style={styles.group} testID="section-mine">
        {inbox.mine.map((entry) => (
          <ItemCard key={entry.item.id} entry={entry} yours onOpen={() => open(entry)} />
        ))}
      </View>
      {inbox.others.length > 0 && (
        <View style={styles.group} testID="section-others">
          <SectionLabel text="Waiting on others · read-only" quiet />
          {inbox.others.map((entry) => (
            <ItemCard key={entry.item.id} entry={entry} onOpen={() => open(entry)} />
          ))}
        </View>
      )}
      {inbox.unaddressed.length > 0 && (
        <View style={styles.group} testID="section-unaddressed">
          <SectionLabel text="Waiting on no one named · read-only" quiet />
          {inbox.unaddressed.map((entry) => (
            <ItemCard key={entry.item.id} entry={entry} onOpen={() => open(entry)} />
          ))}
        </View>
      )}
    </>
  );
}

function ItemCard({ entry, yours = false, onOpen }: { entry: InboxEntry; yours?: boolean; onOpen: () => void }) {
  const { item, actionable, waitsOn } = entry;
  const footer = yours ? item.why : waitsOn === null ? 'Waits on no one named' : `Waits on @${waitsOn}`;
  return (
    <Card testID={`item-${item.id}`}>
      <View style={styles.between}>
        <Text style={[styles.kindLine, !actionable && styles.quietKind]} numberOfLines={1}>
          {`${KIND_LABELS[item.kind]} · ${item.loop ?? 'across loops'}`}
        </Text>
        <Text style={styles.unblocks}>{`unblocks ${item.unblocks.length}`}</Text>
      </View>
      <Text style={styles.cardTitle}>{item.title}</Text>
      <Text style={styles.bodyMuted}>{itemSummary(item)}</Text>
      {item.gate && (
        <View style={styles.chips}>
          <Chip text={`gate: ${item.gate}`} tone="accent" />
        </View>
      )}
      <View style={styles.between}>
        <Text style={styles.footerLine} testID="card-footer">
          {footer}
        </Text>
        <Button
          label={actionLabel(entry, yours)}
          kind={actionable ? 'primary' : 'secondary'}
          hint={`Opens ${item.title}`}
          onPress={onOpen}
        />
      </View>
    </Card>
  );
}
