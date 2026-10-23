// A concern's page (C2), after the Concern artboard (command-center/D4): its state, with the reason and the facts
// the derivation took it from; its contract (needs, touches, effects, ships-to); and each claim with its latest
// verdict and the commit that verdict cites. The artboard's state strip is redrawn with the derivation's states, and
// what it drew as "review" or "proving" is the reason line under the strip (command-center/D5). Its batons and
// sessions belong to later work and are left out. The concern thread at the foot opens
// /threads/loops/[loop]/concerns/[concern], which app-threads serves (command-center/D52).

import { useRouter } from 'expo-router';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import type { Claim, Concern, ConcernState, StatusDocument } from '../../api/status';
import { colors, radius, space, touchTarget, type, verdict } from '../../theme';
import {
  asOf,
  CONCERN_STATES,
  citation,
  concernFacts,
  concernThreadHref,
  currentHolds,
  findConcern,
  latestEvidence,
  loopHref,
} from './board';
import { BackButton, Card, Heading, Notice, SectionLabel, StatusPage, styles as ui, VerdictPill } from './ui';

export function ConcernScreen({ loopId, concernId }: { loopId: string; concernId: string }) {
  const router = useRouter();
  return (
    <StatusPage
      footer={(doc) =>
        findConcern(doc, loopId, concernId) ? (
          <ThreadLink onPress={() => router.push(concernThreadHref(loopId, concernId))} />
        ) : null
      }
    >
      {(doc) => (
        <>
          <BackButton label={loopId} onPress={() => router.dismissTo(loopHref(loopId))} />
          <ConcernBody doc={doc} loopId={loopId} concernId={concernId} />
        </>
      )}
    </StatusPage>
  );
}

function ConcernBody({ doc, loopId, concernId }: { doc: StatusDocument; loopId: string; concernId: string }) {
  const found = findConcern(doc, loopId, concernId);
  if (!found) {
    return <Notice text={`The status gathered ${asOf(doc)} has no concern named ${loopId}/${concernId}.`} />;
  }
  const { loop, concern } = found;
  return (
    <>
      <Heading overline={`${loop.id}/${concern.id}${loop.owner ? ` · owner ${loop.owner}` : ''}`} title={concern.title} />
      <StateCard doc={doc} concern={concern} />
      <ContractCard concern={concern} />
      <ClaimsCard concern={concern} />
    </>
  );
}

function StateCard({ doc, concern }: { doc: StatusDocument; concern: Concern }) {
  return (
    <Card testID="state-card">
      <StateStrip state={concern.state} />
      <View style={ui.reason}>
        <Text style={ui.strong} testID="state-reason">
          {concern.reason}
        </Text>
        {concern.next && <Text style={ui.mono}>next: {concern.next}</Text>}
      </View>
      <View style={ui.tight}>
        {concernFacts(doc, concern).map((fact, i) => (
          <View key={i} style={styles.factRow} testID="fact">
            <Text style={[ui.mono, styles.factLabel]}>{fact.label}</Text>
            <Text style={[ui.mono, ui.grow, fact.missing && { color: verdict.CONTRADICTS.fg }]}>{fact.value}</Text>
          </View>
        ))}
      </View>
    </Card>
  );
}

/**
 * Every state the derivation can give, in the table's order, with the concern's own marked. The table's order is
 * the order its rows are checked, not a timeline, so no state is drawn as already passed.
 */
function StateStrip({ state }: { state: ConcernState }) {
  return (
    <View accessible accessibilityLabel={`State: ${state}`} testID="state-strip" style={ui.tight}>
      <View style={styles.bars}>
        {CONCERN_STATES.map((s) => (
          <View key={s} style={[styles.bar, s === state && styles.barNow]} />
        ))}
      </View>
      <View style={styles.labels}>
        {CONCERN_STATES.map((s) => (
          <Text
            key={s}
            testID={`strip-${s}`}
            accessibilityState={{ selected: s === state }}
            style={s === state ? styles.labelNow : styles.label}
          >
            {s}
          </Text>
        ))}
      </View>
    </View>
  );
}

function ContractCard({ concern }: { concern: Concern }) {
  const { contract } = concern;
  return (
    <Card testID="contract">
      <SectionLabel text="Contract" />
      <ContractRow label="needs" items={contract.needs} />
      <ContractRow label="touches" items={contract.touches} />
      <ContractRow label="effects" items={contract.effects} />
      <ContractRow label="ships-to" items={contract.ships_to ? [contract.ships_to] : []} />
    </Card>
  );
}

function ContractRow({ label, items }: { label: string; items: readonly string[] }) {
  return (
    <View style={styles.contractRow} testID={`contract-${label}`}>
      <Text style={[ui.mono, styles.contractLabel]}>{label}</Text>
      <View style={[ui.chips, ui.grow]}>
        {items.length === 0 ? (
          <Text style={[styles.item, styles.none]}>none</Text>
        ) : (
          items.map((item) => (
            <Text key={item} style={styles.item}>
              {item}
            </Text>
          ))
        )}
      </View>
    </View>
  );
}

function ClaimsCard({ concern }: { concern: Concern }) {
  return (
    <Card testID="claims">
      <SectionLabel text="Done when" />
      {concern.claims.length === 0 && <Text style={ui.bodyMuted}>It has no claims yet.</Text>}
      {concern.claims.map((claim) => (
        <ClaimRow key={claim.id} claim={claim} shipsTo={concern.contract.ships_to} />
      ))}
    </Card>
  );
}

function ClaimRow({ claim, shipsTo }: { claim: Claim; shipsTo: string | null }) {
  const latest = latestEvidence(claim);
  return (
    <View style={ui.tight} testID={`claim-${claim.id}`}>
      <View style={ui.between}>
        <Text style={[ui.strong, claim.struck && styles.struck]}>{claim.id}</Text>
        <VerdictPill verdict={latest?.verdict ?? null} testID={`verdict-${claim.id}`} />
      </View>
      <Text style={[ui.bodyMuted, claim.struck && styles.struck]}>{claim.text}</Text>
      {latest ? (
        <>
          <Text style={ui.mono} testID={`citation-${claim.id}`}>
            {citation(latest)}
          </Text>
          <Text style={ui.bodyMuted}>{latest.text}</Text>
        </>
      ) : null}
      <Text style={ui.mono}>{currentHolds(claim, shipsTo)}</Text>
    </View>
  );
}

function ThreadLink({ onPress }: { onPress: () => void }) {
  return (
    <View style={styles.footer}>
      <Pressable
        accessibilityRole="link"
        accessibilityLabel="Concern thread"
        accessibilityHint="Opens the concern's thread"
        onPress={onPress}
        style={({ pressed }) => [styles.thread, pressed && { borderColor: colors.accent }]}
      >
        <Text style={ui.strong}>Concern thread</Text>
        <Text style={[ui.strong, { color: colors.accent }]}>›</Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  bars: { flexDirection: 'row', gap: 3 },
  bar: { flex: 1, height: 6, borderRadius: 3, backgroundColor: colors.border },
  barNow: { backgroundColor: colors.accent },
  labels: { flexDirection: 'row', flexWrap: 'wrap', columnGap: space.m, rowGap: space.xs },
  label: { ...type.mono, color: colors.inkSubtle },
  labelNow: { ...type.mono, ...ui.monoStrong, color: colors.accent },
  factRow: { flexDirection: 'row', gap: space.s },
  factLabel: { width: 56, color: colors.inkSubtle },
  contractRow: { flexDirection: 'row', gap: space.m, alignItems: 'flex-start' },
  contractLabel: { width: 72, lineHeight: 24 },
  item: {
    ...type.mono,
    color: colors.ink,
    backgroundColor: colors.inset,
    borderColor: colors.border,
    borderWidth: 1,
    borderRadius: radius.chip,
    paddingHorizontal: space.s,
    paddingVertical: 3,
    overflow: 'hidden',
  },
  none: { backgroundColor: colors.surface, borderStyle: 'dashed', borderColor: colors.borderStrong, color: colors.inkMuted },
  struck: { textDecorationLine: 'line-through' },
  footer: {
    backgroundColor: colors.surface,
    borderTopWidth: 1,
    borderTopColor: colors.divider,
    paddingHorizontal: space.l,
    paddingTop: space.m,
    paddingBottom: space.m,
  },
  thread: {
    minHeight: touchTarget,
    borderRadius: radius.button,
    borderWidth: 1,
    borderColor: colors.borderStrong,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: space.l,
  },
});
