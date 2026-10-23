// The Environments tab (command-center/app-environments C1), drawn after the screen design's Environments
// artboard (command-center/D4): a card for each environment LOOP.md §3 lists, with the commit it serves, when that
// was read, and what is merged but not served, and a dashed card that says UNKNOWN, with the failure, for one
// whose read failed. The ship brief is the inbox's ship card, so a card links to it and never repeats it.
//
// The screen shows only the latest read of the status document. A read that fails replaces what the screen
// showed with the failure, so nothing is ever filled in from memory.

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  ActivityIndicator,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  View,
  type StyleProp,
  type TextStyle,
} from 'react-native';

import type { StatusClient, StatusDocument } from '../../api/status';
import { colors, fonts, radius, space, touchTarget, type } from '../../theme';
import { ago, environmentRows, readAgo, shortSha, type ConcernLine, type EnvironmentRow } from './rows';

/** How often "read 40 s ago" is redrawn while the screen stays open. */
const TICK_MS = 15_000;

export const NO_STATUS_SERVICE_MESSAGE =
  'This build has no status service yet, so no environment can be read. The owner sets EXPO_PUBLIC_STATUS_URL ' +
  'in app/eas.json once the status service is deployed.';

type Read =
  | { kind: 'no-service' }
  | { kind: 'reading' }
  | { kind: 'read'; doc: StatusDocument }
  | { kind: 'failed'; message: string };

export type EnvironmentsScreenProps = {
  /** The status client for this build's environment, or null when the build has none. */
  status: StatusClient | null;
  /** Opens the inbox's ship card for a ship item, by its id. */
  onOpenShipCard: (itemId: string) => void;
  /** The current time in ms since the epoch; tests pass their own. */
  now?: () => number;
};

export function EnvironmentsScreen({ status, onOpenShipCard, now = Date.now }: EnvironmentsScreenProps) {
  const [read, setRead] = useState<Read>(status ? { kind: 'reading' } : { kind: 'no-service' });
  const [refreshing, setRefreshing] = useState(false);
  // Only the latest read may change the screen, and none after it unmounts.
  const latest = useRef(0);

  const load = useCallback(
    async (how: 'first' | 'refresh') => {
      const id = ++latest.current;
      if (!status) {
        setRead({ kind: 'no-service' });
        return;
      }
      if (how === 'refresh') setRefreshing(true);
      else setRead({ kind: 'reading' });
      try {
        const doc = await status.getStatus();
        if (id === latest.current) setRead({ kind: 'read', doc });
      } catch (error) {
        if (id === latest.current) {
          setRead({ kind: 'failed', message: error instanceof Error ? error.message : String(error) });
        }
      } finally {
        if (id === latest.current) setRefreshing(false);
      }
    },
    [status],
  );

  useEffect(() => {
    void load('first');
    return () => {
      latest.current += 1;
    };
  }, [load]);

  // Redraw on a timer, so "read 40 s ago" stays true while the screen is open.
  const [, setTick] = useState(0);
  useEffect(() => {
    const timer = setInterval(() => setTick((tick) => tick + 1), TICK_MS);
    return () => clearInterval(timer);
  }, []);
  const time = now();

  const rows = useMemo(() => (read.kind === 'read' ? environmentRows(read.doc) : []), [read]);

  return (
    <ScrollView
      testID="environments-list"
      style={styles.page}
      contentContainerStyle={styles.content}
      refreshControl={
        <RefreshControl
          refreshing={refreshing}
          onRefresh={() => void load('refresh')}
          enabled={status !== null}
          tintColor={colors.inkSubtle}
          colors={[colors.accent]}
        />
      }
    >
      <View style={styles.header}>
        <Text style={styles.overline}>Read from each environment</Text>
        <Text style={styles.title} accessibilityRole="header">
          Environments
        </Text>
        <Text style={styles.subtitle}>Merged is not shipped. This is where the difference lives.</Text>
      </View>

      {read.kind === 'no-service' && (
        <Notice heading="UNKNOWN" text={NO_STATUS_SERVICE_MESSAGE} />
      )}

      {read.kind === 'reading' && (
        <View style={styles.reading}>
          <ActivityIndicator color={colors.inkSubtle} />
          <Text style={styles.muted}>Reading the status service…</Text>
        </View>
      )}

      {read.kind === 'failed' && (
        <Notice
          heading="UNKNOWN"
          text="The status service could not be read, so nothing is filled in from memory."
          detail={read.message}
          onRetry={() => void load('first')}
        />
      )}

      {read.kind === 'read' && rows.length === 0 && (
        <Text style={styles.muted}>The status document lists no environment.</Text>
      )}

      {rows.map((row) =>
        row.served !== null ? (
          <KnownCard key={row.name} row={row} served={row.served} now={time} onOpenShipCard={onOpenShipCard} />
        ) : (
          <UnknownCard key={row.name} row={row} now={time} />
        ),
      )}
    </ScrollView>
  );
}

function KnownCard({
  row,
  served,
  now,
  onOpenShipCard,
}: {
  row: EnvironmentRow;
  served: string;
  now: number;
  onOpenShipCard: (itemId: string) => void;
}) {
  const shipItem = row.shipItems[0];
  return (
    <View testID={`environment-${row.name}`} style={styles.card}>
      <CardHeading name={row.name} trailing={readAgo(row.readAt, now)} />
      <Text style={styles.served} accessibilityLabel={`serves commit ${shortSha(served)}`}>
        {`serves @${shortSha(served)}`}
      </Text>
      {row.waiting && row.waiting.length > 0 ? (
        <ConcernList label="Merged, not served" concerns={row.waiting} />
      ) : (
        <Text style={styles.muted}>Nothing merged is waiting for it.</Text>
      )}
      {row.unread.length > 0 && <ConcernList label="Cannot tell whether it serves" concerns={row.unread} />}
      {shipItem !== undefined && (
        <Pressable
          accessibilityRole="button"
          accessibilityHint={`Opens Needs you, where the ship card for ${row.name} is`}
          onPress={() => onOpenShipCard(shipItem)}
          style={({ pressed }) => [styles.primary, pressed && styles.primaryPressed]}
        >
          <Text style={styles.primaryText}>Read the ship brief</Text>
        </Pressable>
      )}
    </View>
  );
}

function UnknownCard({ row, now }: { row: EnvironmentRow; now: number }) {
  return (
    <View testID={`environment-${row.name}`} style={[styles.card, styles.unknown]}>
      <CardHeading name={row.name} trailing="UNKNOWN" trailingStyle={styles.unknownLabel} />
      <Text style={styles.unknownText}>Its served commit could not be read, so nothing is filled in from memory.</Text>
      {row.error !== null && <Text style={styles.failure}>{row.error}</Text>}
      <Text style={styles.muted}>{`Tried ${ago(row.readAt, now)}.`}</Text>
      {row.unread.length > 0 && <ConcernList label="Cannot tell whether it serves" concerns={row.unread} />}
    </View>
  );
}

function CardHeading({
  name,
  trailing,
  trailingStyle,
}: {
  name: string;
  trailing: string;
  trailingStyle?: StyleProp<TextStyle>;
}) {
  return (
    <View style={styles.heading}>
      <Text style={styles.name} accessibilityRole="header">
        {name}
      </Text>
      <Text style={[styles.readAgo, trailingStyle]}>{trailing}</Text>
    </View>
  );
}

function ConcernList({ label, concerns }: { label: string; concerns: readonly ConcernLine[] }) {
  return (
    <View style={styles.inset}>
      <Text style={styles.insetLabel}>{label}</Text>
      {concerns.map((concern) => (
        <Text key={concern.ref} style={styles.concern}>
          <Text style={styles.ref}>{concern.ref}</Text>
          {` · ${concern.title}`}
        </Text>
      ))}
    </View>
  );
}

function Notice({
  heading,
  text,
  detail,
  onRetry,
}: {
  heading: string;
  text: string;
  detail?: string;
  onRetry?: () => void;
}) {
  return (
    <View style={[styles.card, styles.unknown]}>
      <Text style={styles.unknownLabel}>{heading}</Text>
      <Text style={styles.unknownText}>{text}</Text>
      {detail !== undefined && <Text style={styles.failure}>{detail}</Text>}
      {onRetry && (
        <Pressable
          accessibilityRole="button"
          onPress={onRetry}
          style={({ pressed }) => [styles.secondary, pressed && styles.secondaryPressed]}
        >
          <Text style={styles.secondaryText}>Try again</Text>
        </Pressable>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  page: { flex: 1, backgroundColor: colors.ground },
  content: { paddingHorizontal: space.l, paddingBottom: space.l, gap: space.m },
  header: { paddingHorizontal: space.xs, paddingTop: space.s, paddingBottom: space.xs, gap: space.xs },
  overline: { ...type.overline, color: colors.inkSubtle, textTransform: 'uppercase' },
  title: { ...type.title, color: colors.ink },
  subtitle: { ...type.bodySmall, color: colors.inkMuted },
  reading: { flexDirection: 'row', alignItems: 'center', gap: space.s, paddingVertical: space.m },
  muted: { ...type.bodySmall, color: colors.inkMuted },
  card: {
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.card,
    paddingVertical: space.m,
    paddingHorizontal: space.l,
    gap: space.s,
  },
  // The artboard draws an unknown environment as a dashed outline on the ground, not as a card.
  unknown: { backgroundColor: 'transparent', borderStyle: 'dashed', borderColor: colors.inkSubtle },
  heading: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'baseline', gap: space.m },
  name: { ...type.heading, color: colors.ink, flexShrink: 1 },
  readAgo: { ...type.caption, color: colors.inkMuted, flexShrink: 0 },
  unknownLabel: { ...type.label, color: colors.inkSecondary },
  unknownText: { ...type.bodySmall, color: colors.inkSecondary },
  failure: { ...type.mono, color: colors.inkMuted },
  served: { ...type.mono, fontFamily: fonts.monoMedium, color: colors.ink },
  inset: {
    backgroundColor: colors.inset,
    borderRadius: radius.button,
    paddingVertical: space.s,
    paddingHorizontal: space.m,
    gap: space.xs,
  },
  insetLabel: { ...type.caption, fontFamily: fonts.sansSemiBold, color: colors.inkMuted },
  concern: { ...type.bodySmall, color: colors.ink },
  ref: { fontFamily: fonts.mono },
  primary: {
    minHeight: touchTarget,
    borderRadius: radius.button,
    backgroundColor: colors.accent,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: space.l,
  },
  primaryPressed: { backgroundColor: colors.accentPressed },
  primaryText: { ...type.button, color: colors.onAccent },
  secondary: {
    minHeight: touchTarget,
    borderRadius: radius.button,
    borderWidth: 1,
    borderColor: colors.borderStrong,
    backgroundColor: colors.surface,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: space.l,
  },
  secondaryPressed: { backgroundColor: colors.inset },
  secondaryText: { ...type.button, color: colors.inkSecondary },
});
