// The tab bar: always the four tabs of SHELL_TABS, in their order, and nothing else. A screen concern's routes
// appear under its tab by being in its folder; a route that is no tab's never becomes a tab of its own, and a tab
// whose screen is not built yet shows, disabled, so the bar is the same from the first build on.

import type { BottomTabBarProps } from 'expo-router/js-tabs';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { colors, space, tabBarHeight, type } from '../theme';
import { TabIconView } from './icons';
import { routeOfTab, SHELL_TABS, tabOfRoute } from './tabs';

export function ShellTabBar({ state, descriptors, navigation }: BottomTabBarProps) {
  const insets = useSafeAreaInsets();
  const focused = state.routes[state.index];
  const focusedTab = focused ? tabOfRoute(focused.name) : undefined;

  return (
    <View
      accessibilityRole="tablist"
      style={[styles.bar, { height: tabBarHeight + insets.bottom, paddingBottom: insets.bottom }]}
    >
      {SHELL_TABS.map((tab) => {
        const route = routeOfTab(tab, state.routes);
        const isFocused = focusedTab?.name === tab.name;
        const color = isFocused ? colors.accent : colors.inkSubtle;
        const badge = route ? descriptors[route.key]?.options.tabBarBadge : undefined;
        const label = badge === undefined || badge === null || badge === '' ? tab.title : `${tab.title} · ${badge}`;

        const onPress = () => {
          if (!route) return;
          const event = navigation.emit({ type: 'tabPress', target: route.key, canPreventDefault: true });
          if (!isFocused && !event.defaultPrevented) navigation.navigate(route.name, route.params);
        };

        return (
          <Pressable
            key={tab.name}
            testID={`tab-${tab.name}`}
            accessibilityRole="tab"
            accessibilityLabel={route ? label : `${tab.title}, not built yet`}
            accessibilityState={{ selected: isFocused, disabled: !route }}
            disabled={!route}
            onPress={onPress}
            style={[styles.tab, !route && styles.unbuilt]}
          >
            <TabIconView icon={tab.icon} color={color} />
            <Text style={[isFocused ? type.tabActive : type.tab, { color }]} numberOfLines={1}>
              {label}
            </Text>
          </Pressable>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  bar: {
    flexDirection: 'row',
    backgroundColor: colors.surface,
    borderTopWidth: 1,
    borderTopColor: colors.divider,
    paddingHorizontal: space.s,
  },
  tab: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: space.xs, minHeight: 44 },
  unbuilt: { opacity: 0.4 },
});
