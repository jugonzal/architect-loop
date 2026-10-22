// The root of the app's routes (Expo Router, command-center/D7). Everything it does lives in src/shell/, so the
// screen concerns, which add routes beside it, never need to edit it.

import { AppRoot } from '../shell/AppRoot';

export default function RootLayout() {
  return <AppRoot />;
}
