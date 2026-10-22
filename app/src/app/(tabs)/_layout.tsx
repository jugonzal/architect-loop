// The tabs: Needs you, Loops, Agents and Environments, from src/shell/tabs.ts. Each screen concern adds its own
// folder beside this file, (tabs)/<tab>/ with an index.tsx (and a _layout.tsx if it pushes screens of its own),
// and its tab opens it. Nothing here names a screen's file, so adding one never edits this file or the shell.
// Until a tab's folder exists, the router warns in development that no route is named after it, and the tab
// shows disabled.

import { Tabs } from 'expo-router/js-tabs';

import { colors } from '../../theme';
import { ShellHeader } from '../../shell/ShellHeader';
import { ShellTabBar } from '../../shell/TabBar';
import { SHELL_TABS } from '../../shell/tabs';

export default function TabsLayout() {
  return (
    <Tabs
      tabBar={(props) => <ShellTabBar {...props} />}
      screenOptions={{ header: () => <ShellHeader />, sceneStyle: { backgroundColor: colors.ground } }}
    >
      {/* Declared in the design's order, so the first tab that exists opens first. A name matches the folder's
          own route (with a _layout.tsx) or its index (without one). */}
      {SHELL_TABS.map((tab) => (
        <Tabs.Screen key={tab.name} name={tab.name} />
      ))}
    </Tabs>
  );
}
