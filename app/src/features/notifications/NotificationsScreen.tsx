// The notifications screen (command-center/notifications): this device registers for push (C1), sends itself a
// test notification, and the person sets their digest time, time zone and quiet hours (C3). Pushes themselves come
// from the notifier, never from the app: a blocking item that waits on the person at once, the rest in the digest
// (notifications D1, D2).
//
// The screen shows only what the notifier last answered. A read that fails shows the failure, never an earlier
// answer.

import { useCallback, useEffect, useRef, useState } from 'react';
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Switch, Text, TextInput, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import type { Delivery, Device, NotifyClient, Settings } from '../../api/notify.gen';
import { projectPath, ServiceError } from '../../api/service';
import type { ProjectKey } from '../../api/status';
import { colors, fonts, radius, space, touchTarget, type } from '../../theme';
import { NO_PUSH_MODULE_MESSAGE, type PushTokenSource } from './pushTokens';
import { deviceTimeZone, draftOf, inputOf, type SettingsDraft } from './settings';

export const NO_NOTIFY_SERVICE_MESSAGE =
  'This build has no notify service yet, so nothing can be registered or set. The owner sets ' +
  'EXPO_PUBLIC_NOTIFY_URL in app/eas.json once the notifier is deployed.';

type Read<T> = { kind: 'reading' } | { kind: 'read'; value: T } | { kind: 'failed'; message: string };

type Registration =
  | { kind: 'idle' }
  | { kind: 'working' }
  | { kind: 'registered'; device: Device }
  | { kind: 'denied' }
  | { kind: 'failed'; message: string };

type Action<T> = { kind: 'idle' } | { kind: 'working' } | { kind: 'done'; value: T } | { kind: 'failed'; message: string };

export type NotificationsScreenProps = {
  /** The notify client for this build's environment, or null when the build has no notify URL. */
  notify: NotifyClient | null;
  project: ProjectKey;
  /** Where this device's push token comes from, or null when the build cannot register for push. */
  pushTokens: PushTokenSource | null;
  /** What the person's devices list calls this one, or null. */
  deviceName?: string | null;
  /** This device's time zone; tests pass their own. */
  timeZone?: () => string;
  onBack?: () => void;
};

/** What a failed call says to people: the service's own message when it gave one. */
export function failureText(error: unknown): string {
  if (error instanceof ServiceError) {
    if (error.status === 429) return 'A test notification went out less than a minute ago. Try again shortly.';
    const message = (error.body as { message?: unknown } | null)?.message;
    if (typeof message === 'string' && message) return message;
  }
  return error instanceof Error ? error.message : String(error);
}

export function deliveryText({ devices, accepted, gone }: Delivery): string {
  if (devices === 0) return 'You have no device registered, so nothing was sent.';
  const sent =
    devices === 1
      ? accepted === 1
        ? 'Sent to your device.'
        : 'Not sent to your device.'
      : `Sent to ${accepted} of your ${devices} devices.`;
  if (gone === 0) return sent;
  return `${sent} ${gone === 1 ? 'One no longer exists and was' : `${gone} no longer exist and were`} removed.`;
}

export function NotificationsScreen({
  notify,
  project,
  pushTokens,
  deviceName = null,
  timeZone = deviceTimeZone,
  onBack,
}: NotificationsScreenProps) {
  const insets = useSafeAreaInsets();
  const path = projectPath(project);
  const [devices, setDevices] = useState<Read<Device[]>>({ kind: 'reading' });
  const [settings, setSettings] = useState<Read<Settings>>({ kind: 'reading' });
  const [draft, setDraft] = useState<SettingsDraft | null>(null);
  const [registration, setRegistration] = useState<Registration>({ kind: 'idle' });
  const [test, setTest] = useState<Action<Delivery>>({ kind: 'idle' });
  const [save, setSave] = useState<Action<Settings>>({ kind: 'idle' });
  // No answer may change the screen after it unmounts.
  const mounted = useRef(true);
  useEffect(
    () => () => {
      mounted.current = false;
    },
    [],
  );

  const loadDevices = useCallback(async () => {
    if (!notify) return;
    try {
      const { devices: found } = await notify.listDevices({ path });
      if (mounted.current) setDevices({ kind: 'read', value: found });
    } catch (error) {
      if (mounted.current) setDevices({ kind: 'failed', message: failureText(error) });
    }
  }, [notify, path.owner, path.repo]); // eslint-disable-line react-hooks/exhaustive-deps

  const loadSettings = useCallback(async () => {
    if (!notify) return;
    try {
      const found = await notify.getSettings({ path });
      if (!mounted.current) return;
      setSettings({ kind: 'read', value: found });
      setDraft(draftOf(found.saved ? found : { ...found, timezone: timeZone() }));
    } catch (error) {
      if (mounted.current) setSettings({ kind: 'failed', message: failureText(error) });
    }
  }, [notify, path.owner, path.repo, timeZone]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    void loadDevices();
    void loadSettings();
  }, [loadDevices, loadSettings]);

  const register = async () => {
    if (!notify || !pushTokens) return;
    setRegistration({ kind: 'working' });
    try {
      if ((await pushTokens.requestPermission()) !== 'granted') {
        if (mounted.current) setRegistration({ kind: 'denied' });
        return;
      }
      const token = await pushTokens.getExpoPushToken();
      const device = await notify.registerDevice({
        path,
        body: { token, platform: pushTokens.platform, name: deviceName, timezone: timeZone() },
      });
      if (!mounted.current) return;
      setRegistration({ kind: 'registered', device });
      void loadDevices();
      void loadSettings();
    } catch (error) {
      if (mounted.current) setRegistration({ kind: 'failed', message: failureText(error) });
    }
  };

  const remove = async (device: Device) => {
    if (!notify) return;
    try {
      await notify.unregisterDevice({ path: { ...path, device: device.id } });
      if (registration.kind === 'registered' && registration.device.id === device.id) {
        setRegistration({ kind: 'idle' });
      }
    } catch (error) {
      if (mounted.current) setDevices({ kind: 'failed', message: failureText(error) });
      return;
    }
    void loadDevices();
  };

  const sendTest = async () => {
    if (!notify) return;
    setTest({ kind: 'working' });
    try {
      const delivery = await notify.sendTestNotification({ path });
      if (mounted.current) setTest({ kind: 'done', value: delivery });
      if (delivery.gone > 0) void loadDevices();
    } catch (error) {
      if (mounted.current) setTest({ kind: 'failed', message: failureText(error) });
    }
  };

  const saveSettings = async () => {
    if (!notify || !draft) return;
    const checked = inputOf(draft);
    if ('problem' in checked) {
      setSave({ kind: 'failed', message: checked.problem });
      return;
    }
    setSave({ kind: 'working' });
    try {
      const saved = await notify.putSettings({ path, body: checked.input });
      if (!mounted.current) return;
      setSettings({ kind: 'read', value: saved });
      setDraft(draftOf(saved));
      setSave({ kind: 'done', value: saved });
    } catch (error) {
      if (mounted.current) setSave({ kind: 'failed', message: failureText(error) });
    }
  };

  const edit = (change: Partial<SettingsDraft>) => {
    setDraft((current) => (current ? { ...current, ...change } : current));
    setSave({ kind: 'idle' });
  };

  return (
    <ScrollView
      testID="notifications-screen"
      style={styles.page}
      contentContainerStyle={[styles.content, { paddingTop: insets.top + space.s, paddingBottom: insets.bottom + space.l }]}
      keyboardShouldPersistTaps="handled"
    >
      {onBack && (
        <Pressable accessibilityRole="button" accessibilityLabel="Back" onPress={onBack} hitSlop={8} style={styles.back}>
          <Text style={styles.backText}>‹ Back</Text>
        </Pressable>
      )}
      <View style={styles.header}>
        <Text style={styles.overline}>{project}</Text>
        <Text style={styles.title} accessibilityRole="header">
          Notifications
        </Text>
        <Text style={styles.subtitle}>
          What blocks other work reaches you at once. Everything else waits for your digest.
        </Text>
      </View>

      {!notify ? (
        <Notice text={NO_NOTIFY_SERVICE_MESSAGE} />
      ) : (
        <>
          <View style={styles.card} testID="this-device">
            <Text style={styles.heading} accessibilityRole="header">
              This device
            </Text>
            {!pushTokens && <Text style={styles.muted}>{NO_PUSH_MODULE_MESSAGE}</Text>}
            {pushTokens && registration.kind === 'registered' && (
              <Text style={styles.body}>This device gets your notifications.</Text>
            )}
            {pushTokens && registration.kind === 'denied' && (
              <Text style={styles.body}>
                Notifications are off for this app. Turn them on in the system settings, then try again.
              </Text>
            )}
            {pushTokens && registration.kind === 'failed' && <Text style={styles.failure}>{registration.message}</Text>}
            {pushTokens && registration.kind !== 'registered' && (
              <Primary
                label="Turn on notifications on this device"
                busy={registration.kind === 'working'}
                onPress={() => void register()}
              />
            )}
            <Secondary label="Send a test notification" busy={test.kind === 'working'} onPress={() => void sendTest()} />
            {test.kind === 'done' && <Text style={styles.body}>{deliveryText(test.value)}</Text>}
            {test.kind === 'failed' && <Text style={styles.failure}>{test.message}</Text>}
          </View>

          <View style={styles.card} testID="devices">
            <Text style={styles.heading} accessibilityRole="header">
              Your devices
            </Text>
            {devices.kind === 'reading' && <Reading />}
            {devices.kind === 'failed' && <Text style={styles.failure}>{devices.message}</Text>}
            {devices.kind === 'read' && devices.value.length === 0 && (
              <Text style={styles.muted}>No device gets your notifications yet.</Text>
            )}
            {devices.kind === 'read' &&
              devices.value.map((device) => (
                <View key={device.id} style={styles.deviceRow} testID={`device-${device.id}`}>
                  <View style={styles.deviceText}>
                    <Text style={styles.body}>{device.name ?? (device.platform === 'ios' ? 'iPhone' : 'Android')}</Text>
                    <Text style={styles.caption}>{`${device.platform} · since ${device.registered_at.slice(0, 10)}`}</Text>
                  </View>
                  <Pressable
                    accessibilityRole="button"
                    accessibilityLabel={`Stop notifications on ${device.name ?? device.platform}`}
                    onPress={() => void remove(device)}
                    hitSlop={6}
                    style={styles.remove}
                  >
                    <Text style={styles.removeText}>Remove</Text>
                  </Pressable>
                </View>
              ))}
          </View>

          <View style={styles.card} testID="schedule">
            <Text style={styles.heading} accessibilityRole="header">
              Digest and quiet hours
            </Text>
            {settings.kind === 'reading' && <Reading />}
            {settings.kind === 'failed' && <Text style={styles.failure}>{settings.message}</Text>}
            {settings.kind === 'read' && draft && (
              <>
                <Field
                  label="Time zone"
                  value={draft.timezone}
                  onChange={(timezone) => edit({ timezone })}
                  placeholder="America/New_York"
                />
                <Toggle label="A daily digest" value={draft.digestOn} onChange={(digestOn) => edit({ digestOn })} />
                {draft.digestOn && (
                  <Field
                    label="Digest at"
                    value={draft.digestTime}
                    onChange={(digestTime) => edit({ digestTime })}
                    placeholder="09:00"
                  />
                )}
                <Toggle label="Quiet hours" value={draft.quietOn} onChange={(quietOn) => edit({ quietOn })} />
                {draft.quietOn && (
                  <View style={styles.pair}>
                    <Field label="From" value={draft.quietStart} onChange={(quietStart) => edit({ quietStart })} placeholder="22:00" />
                    <Field label="Until" value={draft.quietEnd} onChange={(quietEnd) => edit({ quietEnd })} placeholder="07:00" />
                  </View>
                )}
                <Text style={styles.caption}>
                  Nothing is pushed in your quiet hours. A blocking item that arrives then reaches you when they end.
                </Text>
                <Primary label="Save" busy={save.kind === 'working'} onPress={() => void saveSettings()} />
                {save.kind === 'done' && <Text style={styles.body}>Saved.</Text>}
                {save.kind === 'failed' && <Text style={styles.failure}>{save.message}</Text>}
                {!settings.value.saved && save.kind !== 'done' && (
                  <Text style={styles.caption}>These are the defaults until you save.</Text>
                )}
              </>
            )}
          </View>
        </>
      )}
    </ScrollView>
  );
}

function Notice({ text }: { text: string }) {
  return (
    <View style={[styles.card, styles.unknown]}>
      <Text style={styles.unknownLabel}>UNKNOWN</Text>
      <Text style={styles.body}>{text}</Text>
    </View>
  );
}

function Reading() {
  return (
    <View style={styles.reading}>
      <ActivityIndicator color={colors.inkSubtle} />
      <Text style={styles.muted}>Reading the notifier…</Text>
    </View>
  );
}

function Primary({ label, busy, onPress }: { label: string; busy: boolean; onPress: () => void }) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityState={{ busy, disabled: busy }}
      disabled={busy}
      onPress={onPress}
      style={({ pressed }) => [styles.primary, pressed && styles.primaryPressed]}
    >
      <Text style={styles.primaryText}>{label}</Text>
    </Pressable>
  );
}

function Secondary({ label, busy, onPress }: { label: string; busy: boolean; onPress: () => void }) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityState={{ busy, disabled: busy }}
      disabled={busy}
      onPress={onPress}
      style={({ pressed }) => [styles.secondary, pressed && styles.secondaryPressed]}
    >
      <Text style={styles.secondaryText}>{label}</Text>
    </Pressable>
  );
}

function Field({
  label,
  value,
  onChange,
  placeholder,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder: string;
}) {
  return (
    <View style={styles.field}>
      <Text style={styles.label}>{label}</Text>
      <TextInput
        accessibilityLabel={label}
        value={value}
        onChangeText={onChange}
        placeholder={placeholder}
        placeholderTextColor={colors.inkSubtle}
        autoCapitalize="none"
        autoCorrect={false}
        style={styles.input}
      />
    </View>
  );
}

function Toggle({ label, value, onChange }: { label: string; value: boolean; onChange: (value: boolean) => void }) {
  return (
    <View style={styles.toggle}>
      <Text style={styles.body}>{label}</Text>
      <Switch
        accessibilityLabel={label}
        value={value}
        onValueChange={onChange}
        trackColor={{ true: colors.accent, false: colors.borderStrong }}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  page: { flex: 1, backgroundColor: colors.ground },
  content: { paddingHorizontal: space.l, gap: space.m },
  back: { minHeight: touchTarget, justifyContent: 'center', alignSelf: 'flex-start' },
  backText: { ...type.button, color: colors.accent },
  header: { paddingHorizontal: space.xs, paddingBottom: space.xs, gap: space.xs },
  overline: { ...type.overline, color: colors.inkSubtle, textTransform: 'uppercase' },
  title: { ...type.title, color: colors.ink },
  subtitle: { ...type.bodySmall, color: colors.inkMuted },
  card: {
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.card,
    paddingVertical: space.m,
    paddingHorizontal: space.l,
    gap: space.s,
  },
  unknown: { backgroundColor: 'transparent', borderStyle: 'dashed', borderColor: colors.inkSubtle },
  unknownLabel: { ...type.label, color: colors.inkSecondary },
  heading: { ...type.heading, color: colors.ink },
  body: { ...type.bodySmall, color: colors.ink },
  muted: { ...type.bodySmall, color: colors.inkMuted },
  caption: { ...type.caption, color: colors.inkMuted },
  failure: { ...type.mono, color: colors.inkMuted },
  reading: { flexDirection: 'row', alignItems: 'center', gap: space.s, paddingVertical: space.s },
  deviceRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: space.m },
  deviceText: { flexShrink: 1, gap: 2 },
  remove: { minHeight: touchTarget, justifyContent: 'center' },
  removeText: { ...type.button, color: colors.inkSecondary },
  field: { gap: space.xs, flex: 1 },
  label: { ...type.caption, fontFamily: fonts.sansSemiBold, color: colors.inkMuted },
  input: {
    ...type.body,
    fontFamily: fonts.mono,
    color: colors.ink,
    minHeight: touchTarget,
    borderWidth: 1,
    borderColor: colors.borderStrong,
    borderRadius: radius.button,
    paddingHorizontal: space.m,
    backgroundColor: colors.surface,
  },
  pair: { flexDirection: 'row', gap: space.m },
  toggle: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', minHeight: touchTarget },
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
