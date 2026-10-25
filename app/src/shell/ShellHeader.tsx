// The strip above every tab: the project, the environment when it is not production, and who is signed in. Each
// screen draws its own title below it, as the design's artboards do.

import { useRouter } from 'expo-router';
import { Alert, Pressable, StyleSheet, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { colors, space, type } from '../theme';
import { displayName } from './auth/github';
import { useSession, useSignedInUser } from './session';

export function ShellHeader() {
  const insets = useSafeAreaInsets();
  const { config, signIn } = useSession();
  const user = useSignedInUser();
  const router = useRouter();
  const name = displayName(user);
  const environment = config.environment === 'production/app' ? null : config.environment.replace(/\/app$/, '');

  // The account sheet: notifications (command-center/notifications D4) and signing out.
  const confirmSignOut = () =>
    Alert.alert(`Signed in as ${name}`, `GitHub account ${user.login}`, [
      { text: 'Notifications', onPress: () => router.navigate('/notifications') },
      { text: 'Cancel', style: 'cancel' },
      { text: 'Sign out', style: 'destructive', onPress: () => void signIn.signOut() },
    ]);

  return (
    <View style={[styles.header, { paddingTop: insets.top + space.s }]}>
      <Text style={styles.overline} numberOfLines={1}>
        {config.project}
        {environment ? ` · ${environment}` : ''}
      </Text>
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={`Signed in as ${name}`}
        accessibilityHint="Shows your account, your notifications, and signing out"
        onPress={confirmSignOut}
        hitSlop={6}
        style={styles.person}
      >
        <Text style={styles.name} numberOfLines={1} testID="signed-in-name">
          {name}
        </Text>
        <View style={styles.avatar}>
          <Text style={styles.initial}>{name.slice(0, 1).toUpperCase()}</Text>
        </View>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  header: {
    backgroundColor: colors.ground,
    paddingHorizontal: space.xl,
    paddingBottom: space.s,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: space.m,
  },
  overline: { ...type.overline, color: colors.inkSubtle, textTransform: 'uppercase', flexShrink: 1 },
  person: { flexDirection: 'row', alignItems: 'center', gap: space.s, minHeight: 44, flexShrink: 0, maxWidth: '55%' },
  name: { ...type.bodySmall, color: colors.inkSecondary, flexShrink: 1 },
  avatar: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: colors.ink,
    alignItems: 'center',
    justifyContent: 'center',
  },
  initial: { ...type.button, color: colors.onInk },
});
