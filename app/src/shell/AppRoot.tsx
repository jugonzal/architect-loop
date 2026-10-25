// What the root layout renders: the fonts, the session, and either the sign-in screen or the app's routes. No
// route is reachable until someone is signed in, so every screen can assume a person (useSignedInUser).

import { useFonts } from 'expo-font';
import { Stack, useRouter } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { useCallback, type ReactNode } from 'react';
import { View } from 'react-native';
import { SafeAreaProvider } from 'react-native-safe-area-context';

import type { Fetch } from '../api/fetch';
import { expoPushTaps, useOpenFromPush, type PushRoute, type PushTaps } from '../features/notifications/pushTaps';
import { colors, fontAssets } from '../theme';
import type { SignIn } from './auth/signIn';
import type { AppConfig } from './config';
import { appSignIn, SessionProvider, useSession } from './session';
import { SignInScreen } from './SignInScreen';

export function AppRoot({
  signIn,
  config,
  fetch,
  pushTaps = expoPushTaps,
}: {
  signIn?: SignIn;
  config?: AppConfig;
  fetch?: Fetch;
  /** Where taps on pushes come from (command-center/notifications D1); tests pass a fake. */
  pushTaps?: PushTaps;
}) {
  const [fontsLoaded, fontError] = useFonts(fontAssets);
  // A font that fails to load falls back to the system face rather than keep the app blank.
  const ready = fontsLoaded || fontError !== null;
  return (
    <SafeAreaProvider>
      <StatusBar style="dark" />
      <SessionProvider signIn={signIn ?? appSignIn(config)} config={config} fetch={fetch}>
        {ready ? <Gate pushTaps={pushTaps} /> : <Ground />}
      </SessionProvider>
    </SafeAreaProvider>
  );
}

function Gate({ pushTaps }: { pushTaps: PushTaps }): ReactNode {
  const { state } = useSession();
  if (state.kind === 'signed-in') {
    return (
      <>
        <OpenFromPush taps={pushTaps} />
        <Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: colors.ground } }} />
      </>
    );
  }
  return <SignInScreen />;
}

/** A tap on a push opens the inbox, or the route it names (command-center/notifications D1). */
function OpenFromPush({ taps }: { taps: PushTaps }) {
  const router = useRouter();
  const open = useCallback((route: PushRoute) => router.navigate(route), [router]);
  useOpenFromPush(taps, open);
  return null;
}

function Ground() {
  return <View style={{ flex: 1, backgroundColor: colors.ground }} />;
}
