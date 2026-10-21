// What the root layout renders: the fonts, the session, and either the sign-in screen or the app's routes. No
// route is reachable until someone is signed in, so every screen can assume a person (useSignedInUser).

import { useFonts } from 'expo-font';
import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import type { ReactNode } from 'react';
import { View } from 'react-native';
import { SafeAreaProvider } from 'react-native-safe-area-context';

import type { Fetch } from '../api/fetch';
import { colors, fontAssets } from '../theme';
import type { SignIn } from './auth/signIn';
import type { AppConfig } from './config';
import { appSignIn, SessionProvider, useSession } from './session';
import { SignInScreen } from './SignInScreen';

export function AppRoot({ signIn, config, fetch }: { signIn?: SignIn; config?: AppConfig; fetch?: Fetch }) {
  const [fontsLoaded, fontError] = useFonts(fontAssets);
  // A font that fails to load falls back to the system face rather than keep the app blank.
  const ready = fontsLoaded || fontError !== null;
  return (
    <SafeAreaProvider>
      <StatusBar style="dark" />
      <SessionProvider signIn={signIn ?? appSignIn(config)} config={config} fetch={fetch}>
        {ready ? <Gate /> : <Ground />}
      </SessionProvider>
    </SafeAreaProvider>
  );
}

function Gate(): ReactNode {
  const { state } = useSession();
  if (state.kind === 'signed-in') {
    return <Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: colors.ground } }} />;
  }
  return <SignInScreen />;
}

function Ground() {
  return <View style={{ flex: 1, backgroundColor: colors.ground }} />;
}
