// The design's tokens, read from the screen design canvas (command-center/D4) on 2026-10-21: 390×844 phone
// artboards in IBM Plex Sans and Mono on a pale green-grey ground. Screens take every colour, face and size from
// here, so the look changes in one place.

export const colors = {
  /** The page behind everything. */
  ground: '#EEF0EC',
  /** Cards, the tab bar and sheets. */
  surface: '#FFFFFF',
  /** A quieter surface inside a card, such as a chip or an inset. */
  inset: '#F2F4F0',
  ink: '#15181C',
  /** Body text that is not the headline. */
  inkMuted: '#4A5058',
  /** Labels, inactive tabs, metadata. */
  inkSubtle: '#5A616B',
  /** Text on a secondary button. */
  inkSecondary: '#2E333A',
  onInk: '#FFFFFF',
  accent: '#2443B8',
  accentPressed: '#1A3290',
  /** A tint of the accent, behind a state's reason line. */
  accentSoft: '#EEF1FC',
  onAccent: '#FFFFFF',
  /** A card's border. */
  border: '#DDE1DA',
  /** A secondary button's or a filter chip's border. */
  borderStrong: '#C9CEC6',
  /** The line above the tab bar. */
  divider: '#D9DDD6',
} as const;

/** Verdict colours: HOLDS green, UNPROVEN amber, CONTRADICTS (and objections) rust. */
export const verdict = {
  HOLDS: { fg: '#135C3B', bg: '#E3F1EA', dot: '#1F7A52' },
  UNPROVEN: { fg: '#6E4A00', bg: '#FFF1CF' },
  // The canvas draws rust only as text (#A1361A). The tint is not on the canvas: it is the same hue at the
  // lightness of the other two tints, so a CONTRADICTS chip reads like its neighbours.
  CONTRADICTS: { fg: '#A1361A', bg: '#F8E6E0' },
} as const;

/** Font family names, as loaded by fonts.ts. */
export const fonts = {
  sans: 'IBMPlexSans_400Regular',
  sansMedium: 'IBMPlexSans_500Medium',
  sansSemiBold: 'IBMPlexSans_600SemiBold',
  sansBold: 'IBMPlexSans_700Bold',
  mono: 'IBMPlexMono_400Regular',
  monoMedium: 'IBMPlexMono_500Medium',
  monoSemiBold: 'IBMPlexMono_600SemiBold',
} as const;

/** The type scale the artboards use, as React Native text styles. */
export const type = {
  title: { fontFamily: fonts.sansBold, fontSize: 30, lineHeight: 36, letterSpacing: -0.3 },
  heading: { fontFamily: fonts.sansSemiBold, fontSize: 16, lineHeight: 22 },
  body: { fontFamily: fonts.sans, fontSize: 14, lineHeight: 20 },
  bodySmall: { fontFamily: fonts.sans, fontSize: 13, lineHeight: 18 },
  caption: { fontFamily: fonts.sans, fontSize: 12, lineHeight: 16 },
  button: { fontFamily: fonts.sansSemiBold, fontSize: 14, lineHeight: 18 },
  tab: { fontFamily: fonts.sansMedium, fontSize: 11, lineHeight: 14 },
  tabActive: { fontFamily: fonts.sansSemiBold, fontSize: 11, lineHeight: 14 },
  /** The uppercase mono line above a screen's title. */
  overline: { fontFamily: fonts.monoMedium, fontSize: 12, lineHeight: 16, letterSpacing: 0.72 },
  /** A card's uppercase kind label. */
  label: { fontFamily: fonts.monoSemiBold, fontSize: 11, lineHeight: 16, letterSpacing: 0.88 },
  mono: { fontFamily: fonts.mono, fontSize: 12, lineHeight: 16 },
  /** A device code, large enough to read and type from another screen. */
  code: { fontFamily: fonts.monoSemiBold, fontSize: 32, lineHeight: 40, letterSpacing: 4 },
} as const;

export const radius = { chip: 6, button: 10, card: 14, pill: 999 } as const;

export const space = { xs: 4, s: 8, m: 12, l: 16, xl: 20, xxl: 24 } as const;

/** The smallest touch target the artboards use for a primary action. */
export const touchTarget = 44;

/** The tab bar's height, above the home indicator. */
export const tabBarHeight = 62;
