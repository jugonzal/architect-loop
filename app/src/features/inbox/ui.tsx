// The pieces the Needs you screens share, after the Inbox, Question and Review artboards (command-center/D4): the
// scrolling page with its pull-to-refresh and what it shows before there is a status document, cards with their
// uppercase kind line, section labels, chips, notices and buttons. Every colour, face and size comes from
// src/theme/.

import type { ReactNode } from 'react';
import { ActivityIndicator, Pressable, RefreshControl, ScrollView, StyleSheet, Text, View } from 'react-native';

import type { StatusDocument } from '../../api/status';
import { colors, fonts, radius, space, touchTarget, type, verdict } from '../../theme';
import { useInbox } from './InboxStatus';
import { asOf, shortSha } from './queue';

export const NO_STATUS_MESSAGE =
  'This build has no status service URL yet, so it cannot show what needs you. The owner sets ' +
  "EXPO_PUBLIC_STATUS_URL for the build's profile in app/eas.json.";

/**
 * A screen of the Needs you tab: a scrolling page that pulls down to read the status again, and that shows its body
 * only once there is a status document to show.
 */
export function InboxPage({
  children,
  footer,
  testID,
}: {
  children: (doc: StatusDocument) => ReactNode;
  /** Drawn below the page, outside the scroll, once there is a document. */
  footer?: (doc: StatusDocument) => ReactNode;
  testID?: string;
}) {
  const { read, refresh } = useInbox();
  const refreshing = read.kind === 'ready' && read.refreshing;
  return (
    <View style={styles.page}>
      <ScrollView
        testID={testID}
        style={styles.page}
        contentContainerStyle={styles.content}
        keyboardShouldPersistTaps="handled"
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={refresh}
            enabled={read.kind !== 'no-service'}
            tintColor={colors.accent}
          />
        }
      >
        {read.kind === 'no-service' && <Notice text={NO_STATUS_MESSAGE} />}
        {read.kind === 'loading' && (
          <View style={styles.waiting} accessibilityLiveRegion="polite">
            <ActivityIndicator color={colors.accent} />
            <Text style={styles.muted}>Reading the status…</Text>
          </View>
        )}
        {read.kind === 'failed' && (
          <>
            <Notice text={`The status could not be read, so nothing is shown from memory. ${read.message}`} alert />
            <Button label="Try again" kind="secondary" onPress={refresh} />
          </>
        )}
        {read.kind === 'ready' && (
          <>
            {read.failure && (
              <Notice text={`The status could not be read again, so this is the earlier copy. ${read.failure}`} alert />
            )}
            {children(read.doc)}
            <Text style={styles.asOf} testID="as-of">
              main @{shortSha(read.doc.main.sha)} · facts gathered {asOf(read.doc)}
            </Text>
          </>
        )}
      </ScrollView>
      {read.kind === 'ready' && footer?.(read.doc)}
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
  kind = 'primary',
  disabled = false,
  hint,
  grow = false,
}: {
  label: string;
  onPress: () => void;
  kind?: 'primary' | 'secondary';
  disabled?: boolean;
  hint?: string;
  grow?: boolean;
}) {
  const primary = kind === 'primary';
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityHint={hint}
      accessibilityState={{ disabled }}
      disabled={disabled}
      onPress={onPress}
      style={({ pressed }) => [
        styles.button,
        primary ? styles.primary : styles.secondary,
        pressed && (primary ? styles.primaryPressed : styles.secondaryPressed),
        disabled && styles.disabled,
        grow && styles.grow,
      ]}
    >
      <Text style={[styles.buttonText, primary ? styles.primaryText : styles.secondaryText, disabled && styles.disabledText]}>
        {label}
      </Text>
    </Pressable>
  );
}

export function Card({ children, testID }: { children: ReactNode; testID?: string }) {
  return (
    <View style={styles.card} testID={testID}>
      {children}
    </View>
  );
}

/** A card's or a section's uppercase label, in the accent, or quiet. */
export function SectionLabel({ text, quiet = false, testID }: { text: string; quiet?: boolean; testID?: string }) {
  return (
    <Text style={[styles.sectionLabel, quiet && styles.quietLabel]} accessibilityRole="header" testID={testID}>
      {text}
    </Text>
  );
}

const TONES = {
  plain: { borderColor: colors.border, color: colors.ink, backgroundColor: colors.surface },
  accent: { borderColor: colors.accent, color: colors.accent, backgroundColor: colors.surface },
  holds: { borderColor: verdict.HOLDS.bg, color: verdict.HOLDS.fg, backgroundColor: verdict.HOLDS.bg },
  unproven: { borderColor: verdict.UNPROVEN.bg, color: verdict.UNPROVEN.fg, backgroundColor: verdict.UNPROVEN.bg },
  contradicts: { borderColor: verdict.CONTRADICTS.bg, color: verdict.CONTRADICTS.fg, backgroundColor: verdict.CONTRADICTS.bg },
} as const;

/** A small chip, such as a claim a question blocks, the gate an item crosses, or a pull request's checks. */
export function Chip({ text, tone = 'plain' }: { text: string; tone?: keyof typeof TONES }) {
  const look = TONES[tone];
  return (
    <View style={[styles.chip, { borderColor: look.borderColor, backgroundColor: look.backgroundColor }]}>
      <Text style={[styles.chipText, { color: look.color }]}>{text}</Text>
    </View>
  );
}

/** A labelled fact: the label on the left, the value on the right, as the Review artboard's grid draws them. */
export function Fact({ label, children, mono = false }: { label: string; children: ReactNode; mono?: boolean }) {
  return (
    <View style={styles.fact}>
      <Text style={styles.factLabel}>{label}</Text>
      <Text style={[styles.factValue, mono && styles.mono]} selectable>
        {children}
      </Text>
    </View>
  );
}

/** A command to run from a terminal, in mono, that the person can select and copy. */
export function Command({ command }: { command: string }) {
  return (
    <View style={styles.inset}>
      <Text style={styles.insetLabel}>Run from a terminal</Text>
      <Text style={styles.command} selectable testID="command">
        {command}
      </Text>
    </View>
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
  heading: { gap: space.xs, paddingHorizontal: space.xs, paddingBottom: space.xs },
  overline: { ...type.overline, color: colors.inkSubtle, textTransform: 'uppercase' },
  title: { ...type.title, color: colors.ink },
  subtitle: { ...type.body, color: colors.inkMuted },
  card: {
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderWidth: 1,
    borderRadius: radius.card,
    paddingTop: space.m + 2,
    paddingBottom: space.l,
    paddingHorizontal: space.l,
    gap: space.s + 2,
  },
  between: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', gap: space.m },
  kindLine: { ...type.label, color: colors.accent, textTransform: 'uppercase', flexShrink: 1 },
  quietKind: { color: colors.inkSubtle },
  unblocks: { ...type.mono, fontFamily: fonts.monoMedium, color: colors.inkMuted, flexShrink: 0 },
  cardTitle: { ...type.heading, color: colors.ink },
  screenTitle: { fontFamily: fonts.sansBold, fontSize: 23, lineHeight: 30, letterSpacing: -0.2, color: colors.ink },
  body: { ...type.body, color: colors.ink },
  bodyMuted: { ...type.bodySmall, color: colors.inkMuted },
  mono: { fontFamily: fonts.mono },
  monoMuted: { ...type.mono, color: colors.inkMuted },
  footerLine: { ...type.caption, color: colors.inkMuted, flexShrink: 1 },
  sectionLabel: { ...type.label, color: colors.accent, textTransform: 'uppercase' },
  quietLabel: { color: colors.inkMuted },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: space.s - 2, alignItems: 'center' },
  chip: { borderWidth: 1, borderRadius: radius.chip, paddingHorizontal: space.s, paddingVertical: 2, alignSelf: 'flex-start' },
  chipText: { ...type.mono, fontFamily: fonts.monoMedium },
  button: {
    minHeight: touchTarget,
    borderRadius: radius.button,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: space.l + 2,
  },
  grow: { flex: 1 },
  primary: { backgroundColor: colors.accent },
  primaryPressed: { backgroundColor: colors.accentPressed },
  secondary: { backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.borderStrong },
  secondaryPressed: { backgroundColor: colors.inset },
  disabled: { backgroundColor: colors.divider, borderColor: colors.divider },
  buttonText: { ...type.button },
  primaryText: { color: colors.onAccent },
  secondaryText: { color: colors.inkSecondary },
  disabledText: { color: colors.inkMuted },
  buttons: { flexDirection: 'row', gap: space.s + 2, justifyContent: 'flex-end', flexWrap: 'wrap' },
  fact: { flexDirection: 'row', gap: space.s + 2, alignItems: 'flex-start' },
  factLabel: { ...type.bodySmall, color: colors.inkMuted, width: 84, flexShrink: 0 },
  factValue: { ...type.bodySmall, color: colors.ink, flex: 1 },
  inset: {
    backgroundColor: colors.inset,
    borderRadius: radius.button,
    paddingVertical: space.s + 2,
    paddingHorizontal: space.m,
    gap: space.xs,
  },
  insetLabel: { ...type.caption, fontFamily: fonts.sansSemiBold, color: colors.inkMuted },
  command: { ...type.mono, color: colors.ink },
  prose: { ...type.body, color: colors.ink },
  note: { ...type.bodySmall, color: colors.inkSecondary, backgroundColor: colors.inset, borderRadius: radius.button, padding: space.m },
  back: { minHeight: touchTarget, justifyContent: 'center', alignSelf: 'flex-start', paddingRight: space.m },
  backText: { ...type.body, color: colors.accent },
  topBar: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', gap: space.m },
  topRef: { ...type.mono, fontFamily: fonts.monoMedium, color: colors.inkMuted, flexShrink: 1, textAlign: 'right' },
  group: { gap: space.m },
  tight: { gap: space.xs },
  dashed: { borderStyle: 'dashed', borderColor: colors.inkSubtle, backgroundColor: 'transparent' },
  input: {
    ...type.body,
    color: colors.ink,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.borderStrong,
    borderRadius: radius.button,
    paddingHorizontal: space.m,
    paddingVertical: space.s + 2,
    minHeight: touchTarget,
  },
  label: { ...type.bodySmall, fontFamily: fonts.sansSemiBold, color: colors.ink },
});
