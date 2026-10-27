// The pieces the Loops tab's screens share: the scrolling page with its pull-to-refresh, what a screen shows before
// it has a status document, cards, section labels and the state and verdict chips. Every colour, face and size
// comes from src/theme/.

import type { ReactNode } from 'react';
import { ActivityIndicator, Pressable, RefreshControl, ScrollView, StyleSheet, Text, View } from 'react-native';

import type { ConcernState, LoopState, StatusDocument, Verdict } from '../../api/status';
import { colors, fonts, radius, space, touchTarget, type } from '../../theme';
import { asOf, shortSha } from './board';
import { CONCERN_LOOK, LOOP_LOOK, verdictLook, type Look } from './look';
import { useLoopsStatus } from './LoopsStatus';

export const NO_SERVICE_MESSAGE =
  'This build has no status service URL yet, so it cannot show the loops. The owner sets EXPO_PUBLIC_STATUS_URL ' +
  "for the build's profile in app/eas.json.";

/**
 * A screen of the Loops tab: a scrolling page that pulls down to read the status again, and that shows its body only
 * once there is a status document to show.
 */
export function StatusPage({
  children,
  footer,
}: {
  children: (doc: StatusDocument) => ReactNode;
  /** Drawn below the page, outside the scroll, once there is a document. */
  footer?: (doc: StatusDocument) => ReactNode;
}) {
  const { status, refresh } = useLoopsStatus();
  const refreshing = status.kind === 'ready' && status.refreshing;
  return (
    <View style={styles.page}>
      <ScrollView
        style={styles.page}
        contentContainerStyle={styles.content}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={refresh} tintColor={colors.accent} />}
      >
        {status.kind === 'no-service' && <Notice text={NO_SERVICE_MESSAGE} />}
        {status.kind === 'loading' && (
          <View style={styles.waiting} accessibilityLiveRegion="polite">
            <ActivityIndicator color={colors.accent} />
            <Text style={styles.muted}>Reading the status…</Text>
          </View>
        )}
        {status.kind === 'failed' && (
          <>
            <Notice text={`The status could not be read. ${status.message}`} alert />
            <Button label="Try again" onPress={refresh} />
          </>
        )}
        {status.kind === 'ready' && (
          <>
            {status.failure && (
              <Notice text={`The status could not be read again, so this is the earlier copy. ${status.failure}`} alert />
            )}
            {children(status.doc)}
            <Text style={styles.asOf} testID="as-of">
              main @{shortSha(status.doc.main.sha)} · CI {status.doc.main.ci} · facts gathered {asOf(status.doc)}
            </Text>
          </>
        )}
      </ScrollView>
      {status.kind === 'ready' && footer?.(status.doc)}
    </View>
  );
}

export function Notice({ text, alert = false }: { text: string; alert?: boolean }) {
  return (
    <Text style={[styles.notice, alert && styles.alert]} accessibilityRole={alert ? 'alert' : 'text'}>
      {text}
    </Text>
  );
}

export function Button({
  label,
  onPress,
  disabled = false,
  hint,
}: {
  label: string;
  onPress: () => void;
  disabled?: boolean;
  hint?: string;
}) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityHint={hint}
      accessibilityState={{ disabled }}
      disabled={disabled}
      onPress={onPress}
      style={({ pressed }) => [
        styles.button,
        pressed && { borderColor: colors.accentPressed },
        disabled && { borderColor: colors.border },
      ]}
    >
      <Text style={[styles.buttonLabel, disabled && { color: colors.inkSubtle }]}>{label}</Text>
    </Pressable>
  );
}

/** A screen's heading: the uppercase mono line, then the title. */
export function Heading({ overline, title }: { overline: ReactNode; title: string }) {
  return (
    <View style={styles.heading}>
      <Text style={styles.overline}>{overline}</Text>
      <Text style={styles.title} accessibilityRole="header">
        {title}
      </Text>
    </View>
  );
}

export function Card({ children, testID }: { children: ReactNode; testID?: string }) {
  return (
    <View style={styles.card} testID={testID}>
      {children}
    </View>
  );
}

/** A card's or a section's uppercase label. */
export function SectionLabel({ text, quiet = false }: { text: string; quiet?: boolean }) {
  return (
    <Text style={[styles.sectionLabel, quiet && { color: colors.inkMuted }]} accessibilityRole="header">
      {text}
    </Text>
  );
}

function chipStyle(look: Look) {
  return [styles.chip, { backgroundColor: look.backgroundColor, borderColor: look.borderColor, borderStyle: look.borderStyle }];
}

/** A concern's state, written out, optionally after the concern's name. */
export function ConcernChip({ state, name, onPress }: { state: ConcernState; name?: string; onPress?: () => void }) {
  const look = CONCERN_LOOK[state];
  const text = name ? `${name} ${state}` : state;
  const chip = (
    <View style={chipStyle(look)}>
      <Text style={[styles.chipText, { color: look.color }]}>{text}</Text>
    </View>
  );
  if (!onPress) return chip;
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={`${name ?? 'Concern'}, ${state}`}
      accessibilityHint="Opens the concern"
      onPress={onPress}
      hitSlop={4}
    >
      {chip}
    </Pressable>
  );
}

export function LoopChip({ state }: { state: LoopState }) {
  const look = LOOP_LOOK[state];
  return (
    <View style={chipStyle(look)} testID="loop-state">
      <Text style={[styles.chipText, { color: look.color }]}>{state}</Text>
    </View>
  );
}

/** A claim's or a goal's latest verdict, or "no evidence" when it has none yet. */
export function VerdictPill({ verdict, testID }: { verdict: Verdict | null; testID?: string }) {
  const look = verdictLook(verdict);
  return (
    <View style={[styles.pill, { backgroundColor: look.backgroundColor }]} testID={testID}>
      <Text style={[styles.pillText, { color: look.color }]}>{verdict ?? 'no evidence'}</Text>
    </View>
  );
}

/** A row that opens another screen: what it is on the left, a short fact on the right. */
export function Row({ title, detail, onPress, label }: { title: string; detail: string; onPress: () => void; label: string }) {
  return (
    <Pressable accessibilityRole="button" accessibilityLabel={label} onPress={onPress} style={styles.row}>
      <Text style={styles.rowTitle} numberOfLines={1}>
        {title}
      </Text>
      <Text style={styles.rowDetail} numberOfLines={1}>
        {detail}
      </Text>
    </Pressable>
  );
}

export function BackButton({ label, onPress }: { label: string; onPress: () => void }) {
  return (
    <Pressable accessibilityRole="button" accessibilityLabel={`Back to ${label}`} onPress={onPress} hitSlop={6} style={styles.back}>
      <Text style={styles.backText}>‹ {label}</Text>
    </Pressable>
  );
}

export const styles = StyleSheet.create({
  page: { flex: 1, backgroundColor: colors.ground },
  content: { paddingHorizontal: space.l, paddingTop: space.xs, paddingBottom: space.xxl, gap: space.m },
  waiting: { flexDirection: 'row', alignItems: 'center', gap: space.s, paddingVertical: space.l },
  muted: { ...type.bodySmall, color: colors.inkMuted },
  notice: { ...type.body, color: colors.inkMuted, paddingVertical: space.s },
  alert: { color: colors.ink },
  asOf: { ...type.mono, color: colors.inkSubtle, paddingTop: space.s },
  button: {
    minHeight: touchTarget,
    borderRadius: radius.button,
    borderWidth: 1,
    borderColor: colors.accent,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: space.l,
    alignSelf: 'flex-start',
  },
  buttonLabel: { ...type.button, color: colors.accent },
  heading: { gap: space.xs, paddingHorizontal: space.xs, paddingBottom: space.xs },
  overline: { ...type.overline, color: colors.inkSubtle, textTransform: 'uppercase' },
  title: { ...type.title, color: colors.ink },
  card: {
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderWidth: 1,
    borderRadius: radius.card,
    paddingVertical: space.m,
    paddingHorizontal: space.l,
    gap: space.m,
  },
  sectionLabel: { ...type.label, color: colors.accent, textTransform: 'uppercase' },
  chip: { borderWidth: 1, borderRadius: radius.chip, paddingHorizontal: space.s, paddingVertical: 2, alignSelf: 'flex-start' },
  chipText: { ...type.mono },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: space.s },
  pill: { borderRadius: radius.pill, paddingHorizontal: space.s, paddingVertical: 2, alignSelf: 'flex-start', flexShrink: 0 },
  pillText: { ...type.label },
  row: {
    minHeight: touchTarget,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: space.m,
    borderTopWidth: 1,
    borderTopColor: colors.divider,
  },
  rowTitle: { ...type.body, color: colors.ink, flexShrink: 1 },
  rowDetail: { ...type.mono, color: colors.inkMuted, flexShrink: 0 },
  back: { minHeight: touchTarget, justifyContent: 'center', alignSelf: 'flex-start', paddingRight: space.m },
  backText: { ...type.body, color: colors.accent },
  body: { ...type.body, color: colors.ink },
  bodyMuted: { ...type.bodySmall, color: colors.inkMuted },
  mono: { ...type.mono, color: colors.inkMuted },
  strong: { ...type.body, fontFamily: fonts.sansSemiBold, color: colors.ink },
  monoStrong: { ...type.mono, fontFamily: fonts.monoSemiBold },
  name: { ...type.heading, color: colors.ink, flexShrink: 1 },
  group: { gap: space.m },
  tight: { gap: space.xs },
  rows: { paddingTop: space.xs },
  between: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'baseline', gap: space.s },
  inline: { flexDirection: 'row', flexWrap: 'wrap', gap: space.m },
  stateLine: { flexDirection: 'row', gap: space.s, alignItems: 'flex-start' },
  grow: { flex: 1 },
  reason: { backgroundColor: colors.accentSoft, borderRadius: radius.button, padding: space.m, gap: space.xs },
});
