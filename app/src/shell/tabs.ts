// The tabs from the screen design (command-center/D4), in its order. The design's fifth tab, More (Charter,
// Commons, Retro), belongs to later loops and is not here.
//
// Each tab is the folder of the same name under app/src/app/(tabs)/, which its screen concern owns:
// app-inbox adds (tabs)/inbox/, app-loops-board (tabs)/loops/, app-agents (tabs)/agents/ and app-environments
// (tabs)/environments/. A screen's folder holds an index.tsx, and a _layout.tsx if it pushes screens of its own.
// Adding those files is all a screen does to appear in its tab: nothing here, and nothing in
// (tabs)/_layout.tsx, changes.

export type TabIcon = 'inbox' | 'loops' | 'agents' | 'environments';

export type ShellTab = {
  /** The folder under app/src/app/(tabs)/ that holds the tab's screen. */
  readonly name: string;
  readonly title: string;
  readonly icon: TabIcon;
  /** The screen concern that builds the tab's screen. */
  readonly concern: string;
};

export const SHELL_TABS: readonly ShellTab[] = [
  { name: 'inbox', title: 'Needs you', icon: 'inbox', concern: 'command-center/app-inbox' },
  { name: 'loops', title: 'Loops', icon: 'loops', concern: 'command-center/app-loops-board' },
  { name: 'agents', title: 'Agents', icon: 'agents', concern: 'command-center/app-agents' },
  { name: 'environments', title: 'Environments', icon: 'environments', concern: 'command-center/app-environments' },
];

/**
 * The tab a route of the tab navigator belongs to. A folder with its own _layout.tsx is one route named after
 * the folder; without one, each of its files is a route named <folder>/<file>, such as inbox/index. Both belong
 * to the folder's tab.
 */
export function tabOfRoute(routeName: string): ShellTab | undefined {
  return SHELL_TABS.find((tab) => routeName === tab.name || routeName.startsWith(`${tab.name}/`));
}

/** The route a tab opens: its folder's own route, else the folder's index, else nothing yet. */
export function routeOfTab<R extends { name: string }>(tab: ShellTab, routes: readonly R[]): R | undefined {
  return (
    routes.find((r) => r.name === tab.name) ??
    routes.find((r) => r.name === `${tab.name}/index`) ??
    routes.find((r) => r.name.startsWith(`${tab.name}/`))
  );
}
