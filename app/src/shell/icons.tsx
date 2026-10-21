// The tab icons, drawn as on the screen design: 24-unit stroke icons at 1.8 width, in the label's colour.

import Svg, { Path, Rect } from 'react-native-svg';

import type { TabIcon } from './tabs';

export function TabIconView({ icon, color, size = 22 }: { icon: TabIcon; color: string; size?: number }) {
  const stroke = { stroke: color, strokeWidth: 1.8, strokeLinecap: 'round', strokeLinejoin: 'round', fill: 'none' } as const;
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" accessibilityElementsHidden importantForAccessibility="no">
      {icon === 'inbox' && (
        <>
          <Path d="M3 13h5l2 3h4l2-3h5" {...stroke} />
          <Path d="M5 4h14l2 9v7H3v-7z" {...stroke} />
        </>
      )}
      {icon === 'loops' && (
        <>
          <Path d="M17 2l3 3-3 3" {...stroke} />
          <Path d="M4 11V9a4 4 0 0 1 4-4h12" {...stroke} />
          <Path d="M7 22l-3-3 3-3" {...stroke} />
          <Path d="M20 13v2a4 4 0 0 1-4 4H4" {...stroke} />
        </>
      )}
      {icon === 'agents' && (
        <>
          <Rect x={4} y={6} width={16} height={13} rx={3} {...stroke} />
          <Path d="M12 2v4" {...stroke} />
          <Path d="M9 12h.01" {...stroke} />
          <Path d="M15 12h.01" {...stroke} />
          <Path d="M9.5 16h5" {...stroke} />
        </>
      )}
      {icon === 'environments' && (
        <>
          <Rect x={3} y={4} width={18} height={7} rx={2} {...stroke} />
          <Rect x={3} y={13} width={18} height={7} rx={2} {...stroke} />
          <Path d="M7 7.5h.01" {...stroke} />
          <Path d="M7 16.5h.01" {...stroke} />
        </>
      )}
    </Svg>
  );
}
