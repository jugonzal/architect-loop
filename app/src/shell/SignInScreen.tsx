// What the person sees until they are signed in: one button, then the code to type on github.com (app-shell D1).

import * as Clipboard from 'expo-clipboard';
import { useState } from 'react';
import { ActivityIndicator, Linking, Pressable, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { colors, radius, space, touchTarget, type, verdict } from '../theme';
import type { SignInState } from './auth/signIn';
import { useSession } from './session';

export function SignInScreen() {
  const { state, signIn } = useSession();
  return (
    <SafeAreaView style={styles.page}>
      <View style={styles.body}>
        <Text style={styles.overline}>Architect Loop</Text>
        <Text style={styles.title} accessibilityRole="header">
          Sign in with GitHub
        </Text>
        <Body state={state} onStart={() => void signIn.start()} onCancel={() => signIn.cancel()} />
      </View>
    </SafeAreaView>
  );
}

function Body({ state, onStart, onCancel }: { state: SignInState; onStart: () => void; onCancel: () => void }) {
  switch (state.kind) {
    case 'not-configured':
      return <Text style={styles.text}>{state.message}</Text>;
    case 'restoring':
      return <Waiting text="Checking your sign-in…" />;
    case 'signed-out':
      return (
        <>
          <Text style={styles.text}>
            The app asks GitHub only who you are. It gets no access to your repositories.
          </Text>
          {state.failure && (
            <Text style={styles.failure} accessibilityRole="alert">
              {state.failure.message}
            </Text>
          )}
          <Button label="Sign in with GitHub" onPress={onStart} />
        </>
      );
    case 'requesting-code':
      return <Waiting text="Asking GitHub for a code…" />;
    case 'awaiting-person':
      return <EnterCode state={state} onCancel={onCancel} />;
    case 'signed-in':
      return <Waiting text="Signed in." />;
  }
}

function EnterCode({ state, onCancel }: { state: Extract<SignInState, { kind: 'awaiting-person' }>; onCancel: () => void }) {
  const [copied, setCopied] = useState(false);
  const expires = new Date(state.expiresAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  return (
    <>
      <Text style={styles.text}>Enter this code at {state.verificationUri.replace(/^https:\/\//, '')}:</Text>
      <View style={styles.codeBox}>
        <Text style={styles.code} selectable accessibilityLabel={`Code ${state.userCode.split('').join(' ')}`}>
          {state.userCode}
        </Text>
      </View>
      <Button
        label={copied ? 'Copied' : 'Copy code'}
        secondary
        onPress={() => {
          void Clipboard.setStringAsync(state.userCode).then(() => setCopied(true));
        }}
      />
      <Button label="Open GitHub" onPress={() => void Linking.openURL(state.verificationUri)} />
      <Waiting
        text={
          state.unreachable
            ? 'GitHub cannot be reached. Still trying until the code expires.'
            : `Waiting for you to confirm on GitHub. The code works until ${expires}.`
        }
      />
      <Button label="Cancel" secondary onPress={onCancel} />
    </>
  );
}

function Waiting({ text }: { text: string }) {
  return (
    <View style={styles.waiting} accessibilityLiveRegion="polite">
      <ActivityIndicator color={colors.accent} />
      <Text style={styles.caption}>{text}</Text>
    </View>
  );
}

function Button({ label, onPress, secondary = false }: { label: string; onPress: () => void; secondary?: boolean }) {
  return (
    <Pressable
      accessibilityRole="button"
      onPress={onPress}
      style={({ pressed }) => [
        styles.button,
        secondary ? styles.buttonSecondary : { backgroundColor: pressed ? colors.accentPressed : colors.accent },
      ]}
    >
      <Text style={[styles.buttonLabel, secondary && { color: colors.inkSecondary }]}>{label}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  page: { flex: 1, backgroundColor: colors.ground },
  body: { flex: 1, justifyContent: 'center', paddingHorizontal: space.xl, gap: space.m },
  overline: { ...type.overline, color: colors.inkSubtle, textTransform: 'uppercase' },
  title: { ...type.title, color: colors.ink },
  text: { ...type.body, color: colors.inkMuted },
  caption: { ...type.caption, color: colors.inkMuted, flex: 1 },
  failure: { ...type.bodySmall, color: verdict.CONTRADICTS.fg },
  codeBox: {
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderWidth: 1,
    borderRadius: radius.card,
    paddingVertical: space.l,
    alignItems: 'center',
  },
  code: { ...type.code, color: colors.ink },
  waiting: { flexDirection: 'row', alignItems: 'center', gap: space.s, paddingVertical: space.s },
  button: { minHeight: touchTarget, borderRadius: radius.button, alignItems: 'center', justifyContent: 'center', paddingHorizontal: 18 },
  buttonSecondary: { backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.borderStrong },
  buttonLabel: { ...type.button, color: colors.onAccent },
});
