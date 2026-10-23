// The Loops tab (C1), after the Loops artboard (command-center/D4): active loops first, each a card with every
// concern and its state, then the backlog one line each, then parked loops. A loop whose state is unknown, or that
// is open with no concerns yet, gets a card under its own heading, with the reason that names what is missing; done
// loops come last, one line each (board.ts). A concern's chip opens its page, and a loop's name opens the loop.
// The artboard's "Plan a loop" button dispatches a skill, which is not this screen's, so it is left out.

import { useRouter } from 'expo-router';
import { Pressable, Text, View } from 'react-native';

import type { Claim, Loop, StatusDocument } from '../../api/status';
import { boardSections, boardSummary, concernHref, latestVerdict, loopHref, plural, type BoardSection } from './board';
import { verdictLook } from './look';
import { Card, ConcernChip, Heading, LoopChip, Notice, Row, SectionLabel, StatusPage, styles } from './ui';

export function LoopsBoard() {
  return <StatusPage>{(doc) => <Board doc={doc} />}</StatusPage>;
}

function Board({ doc }: { doc: StatusDocument }) {
  const sections = boardSections(doc);
  return (
    <>
      <Heading overline={sections.length ? boardSummary(sections) : doc.project} title="Loops" />
      {sections.length === 0 && <Notice text="This project has no loops yet. /loop-plan adds one to the backlog." />}
      {sections.map((section) => (
        <Section key={section.state} section={section} />
      ))}
    </>
  );
}

function Section({ section }: { section: BoardSection }) {
  const router = useRouter();
  if (section.full) {
    return (
      <View style={styles.group} testID={`section-${section.state}`}>
        <SectionLabel text={section.title} quiet />
        {section.loops.map((loop) => (
          <LoopCard key={loop.id} loop={loop} />
        ))}
      </View>
    );
  }
  return (
    <View testID={`section-${section.state}`}>
      <SectionLabel text={section.title} quiet />
      <View style={styles.rows}>
        {section.loops.map((loop) => (
          <Row
            key={loop.id}
            title={loop.id}
            detail={plural(loop.concerns.length, 'concern')}
            label={`${loop.id}, ${loop.state}, ${plural(loop.concerns.length, 'concern')}`}
            onPress={() => router.push(loopHref(loop.id))}
          />
        ))}
      </View>
    </View>
  );
}

function LoopCard({ loop }: { loop: Loop }) {
  const router = useRouter();
  const people = [loop.owner ? `owner ${loop.owner}` : null, loop.members?.length ? plural(loop.members.length, 'member') : null]
    .filter(Boolean)
    .join(' · ');
  const goals = loop.goals.filter((g) => !g.struck);
  return (
    <Card testID={`loop-${loop.id}`}>
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={`${loop.id}, ${loop.state}`}
        accessibilityHint="Opens the loop"
        onPress={() => router.push(loopHref(loop.id))}
      >
        <View style={styles.between}>
          <Text style={styles.name}>{loop.id}</Text>
          {people ? <Text style={styles.bodyMuted}>{people}</Text> : null}
        </View>
        <Text style={styles.bodyMuted}>{loop.title}</Text>
      </Pressable>
      {loop.state !== 'active' && (
        <View style={styles.stateLine}>
          <LoopChip state={loop.state} />
          <Text style={[styles.bodyMuted, styles.grow]}>{loop.reason}</Text>
        </View>
      )}
      {loop.concerns.length > 0 && (
        <View style={styles.chips}>
          {loop.concerns.map((c) => (
            <ConcernChip key={c.id} name={c.id} state={c.state} onPress={() => router.push(concernHref(loop.id, c.id))} />
          ))}
        </View>
      )}
      {goals.length > 0 && <Goals goals={goals} />}
      {loop.next && <Text style={styles.mono}>next: {loop.next}</Text>}
    </Card>
  );
}

/** Each goal with its latest verdict, as the artboard's "G1 HOLDS" line. */
export function Goals({ goals }: { goals: Claim[] }) {
  return (
    <View style={styles.inline}>
      {goals.map((goal) => {
        const v = latestVerdict(goal);
        return (
          <Text key={goal.id} style={styles.mono} testID={`goal-${goal.id}`}>
            {goal.id} <Text style={[styles.monoStrong, { color: verdictLook(v).color }]}>{v ?? 'no evidence'}</Text>
          </Text>
        );
      })}
    </View>
  );
}
