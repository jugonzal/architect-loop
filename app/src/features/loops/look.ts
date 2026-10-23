// How each state and verdict is drawn, from the theme's tokens only. The Loops artboard (command-center/D4) draws
// done in ink, building with an accent outline, ready with a plain outline, shipped and merged in the HOLDS green,
// and a concern waiting on a question with a dashed rust outline. The states the artboard does not draw take the
// nearest token: contradicted in the CONTRADICTS rust, stale in the UNPROVEN amber (it needs proving again),
// unknown with a dotted ink outline. Every chip also writes its state's name, so no state is told by colour alone.

import { colors, verdict } from '../../theme';
import type { ConcernState, LoopState, Verdict } from '../../api/status';

export type Look = {
  backgroundColor: string;
  color: string;
  borderColor: string;
  borderStyle: 'solid' | 'dashed' | 'dotted';
};

const solid = (backgroundColor: string, color: string, borderColor = backgroundColor): Look => ({
  backgroundColor,
  color,
  borderColor,
  borderStyle: 'solid',
});

export const CONCERN_LOOK: Record<ConcernState, Look> = {
  parked: solid(colors.inset, colors.inkSubtle, colors.border),
  contradicted: solid(verdict.CONTRADICTS.bg, verdict.CONTRADICTS.fg),
  open: { ...solid(colors.surface, verdict.CONTRADICTS.fg, verdict.CONTRADICTS.fg), borderStyle: 'dashed' },
  blocked: { ...solid(colors.surface, colors.inkMuted, colors.borderStrong), borderStyle: 'dashed' },
  ready: solid(colors.surface, colors.inkSecondary, colors.borderStrong),
  building: solid(colors.surface, colors.accent, colors.accent),
  merged: solid(colors.surface, verdict.HOLDS.fg, verdict.HOLDS.dot),
  shipped: solid(verdict.HOLDS.bg, verdict.HOLDS.fg),
  stale: solid(verdict.UNPROVEN.bg, verdict.UNPROVEN.fg),
  done: solid(colors.ink, colors.onInk),
  unknown: { ...solid(colors.surface, colors.ink, colors.ink), borderStyle: 'dotted' },
};

export const LOOP_LOOK: Record<LoopState, Look> = {
  active: solid(colors.surface, colors.accent, colors.accent),
  unknown: CONCERN_LOOK.unknown,
  open: CONCERN_LOOK.open,
  backlog: solid(colors.surface, colors.inkSecondary, colors.borderStrong),
  parked: CONCERN_LOOK.parked,
  done: CONCERN_LOOK.done,
};

/** A claim's latest verdict, or none when it has no evidence line yet. */
export function verdictLook(v: Verdict | null): { backgroundColor: string; color: string } {
  if (v === null) return { backgroundColor: colors.inset, color: colors.inkSubtle };
  return { backgroundColor: verdict[v].bg, color: verdict[v].fg };
}
