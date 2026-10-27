// One loop: its state and the reason the derivation gave, its goals with their latest verdicts, and every concern
// with its state and reason. The board shows backlog, parked and done loops one line each, so this is where their
// concerns are reached. app-documents adds a design session on the loop and the loop's README at the status's main
// commit (command-center/D72).

import { useRouter } from 'expo-router';
import { Pressable, Text, View } from 'react-native';

import type { Loop, StatusDocument } from '../../api/status';
import { asOf, concernHref, findLoop } from './board';
import { DesignStart } from './DesignStart';
import { DocumentCard } from './DocumentCard';
import { Goals } from './LoopsBoard';
import { BackButton, Card, ConcernChip, Heading, LoopChip, Notice, SectionLabel, StatusPage, styles } from './ui';

export function LoopScreen({ loopId }: { loopId: string }) {
  const router = useRouter();
  return (
    <StatusPage>
      {(doc) => (
        <>
          <BackButton label="Loops" onPress={() => router.dismissTo('/loops')} />
          <LoopBody doc={doc} loopId={loopId} />
        </>
      )}
    </StatusPage>
  );
}

function LoopBody({ doc, loopId }: { doc: StatusDocument; loopId: string }) {
  const loop = findLoop(doc, loopId);
  if (!loop) return <Notice text={`The status gathered ${asOf(doc)} has no loop named ${loopId}.`} />;
  const people = [loop.owner ? `owner ${loop.owner}` : null, loop.members?.length ? loop.members.join(', ') : null]
    .filter(Boolean)
    .join(' · ');
  const goals = loop.goals.filter((g) => !g.struck);
  return (
    <>
      <Heading overline={loop.id} title={loop.title} />
      <Card>
        <View style={styles.stateLine}>
          <LoopChip state={loop.state} />
          {people ? <Text style={styles.bodyMuted}>{people}</Text> : null}
        </View>
        <View style={styles.reason}>
          <Text style={styles.strong} testID="loop-reason">
            {loop.reason}
          </Text>
          {loop.next && <Text style={styles.mono}>next: {loop.next}</Text>}
        </View>
        {goals.length > 0 && <Goals goals={goals} />}
      </Card>
      <DesignStart target={{ loop: loop.id }} what="this loop" />
      <Concerns loop={loop} />
      <DocumentCard doc={doc} path={loop.path} />
    </>
  );
}

function Concerns({ loop }: { loop: Loop }) {
  const router = useRouter();
  return (
    <Card>
      <SectionLabel text={`Concerns · ${loop.concerns.length}`} />
      {loop.concerns.length === 0 && <Text style={styles.bodyMuted}>It has no concerns yet.</Text>}
      {loop.concerns.map((c) => (
        <Pressable
          key={c.id}
          accessibilityRole="button"
          accessibilityLabel={`${c.id}, ${c.state}`}
          accessibilityHint="Opens the concern"
          onPress={() => router.push(concernHref(loop.id, c.id))}
          style={styles.tight}
          testID={`concern-${c.id}`}
        >
          <View style={styles.between}>
            <Text style={styles.name}>{c.id}</Text>
            <ConcernChip state={c.state} />
          </View>
          <Text style={styles.body}>{c.title}</Text>
          <Text style={styles.bodyMuted}>{c.reason}</Text>
        </Pressable>
      ))}
    </Card>
  );
}
