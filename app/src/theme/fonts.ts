import {
  IBMPlexMono_400Regular,
  IBMPlexMono_500Medium,
  IBMPlexMono_600SemiBold,
} from '@expo-google-fonts/ibm-plex-mono';
import {
  IBMPlexSans_400Regular,
  IBMPlexSans_500Medium,
  IBMPlexSans_600SemiBold,
  IBMPlexSans_700Bold,
} from '@expo-google-fonts/ibm-plex-sans';

import { fonts } from './tokens';

/** The font files to load before the first screen draws, keyed by the family names in tokens.ts. */
export const fontAssets = {
  [fonts.sans]: IBMPlexSans_400Regular,
  [fonts.sansMedium]: IBMPlexSans_500Medium,
  [fonts.sansSemiBold]: IBMPlexSans_600SemiBold,
  [fonts.sansBold]: IBMPlexSans_700Bold,
  [fonts.mono]: IBMPlexMono_400Regular,
  [fonts.monoMedium]: IBMPlexMono_500Medium,
  [fonts.monoSemiBold]: IBMPlexMono_600SemiBold,
};
