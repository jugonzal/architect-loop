// A design session started from a concern's or a loop's page (app-documents C2, command-center/D72): /loop-design on
// that concern or loop, naming no question, so the skill finds the open decisions itself and the person steers it in
// the session's thread. It runs the release the runner's estimate names (command-center/D68), and names no sponsor:
// the runner's is always its caller (command-center/D28).

import type { DispatchRequest, Session } from '../../api/runner.gen';
import type { ProjectKey } from '../../api/status';

export type DesignTarget = { readonly concern: string } | { readonly loop: string };

export function designTargetName(target: DesignTarget): string {
  return 'concern' in target ? target.concern : target.loop;
}

/** The same start as a person would type it in a terminal, which the sheet shows. */
export function designCommand(target: DesignTarget): string {
  return `/loop-design ${designTargetName(target)}`;
}

export function designRequest(
  target: DesignTarget,
  { project, budgetUsd, release }: { project: ProjectKey; budgetUsd: number; release: string },
): DispatchRequest {
  return { project, skill: 'loop-design', ...target, arguments: '', budget_usd: budgetUsd, plugin_release: release };
}

/**
 * Whether a session the runner lists is a design session on this concern or loop that has not ended, whatever it was
 * asked and whoever sponsored it: the runner refuses a second one on a concern (runner-dispatch C2).
 */
export function designsTarget(target: DesignTarget, session: Session): boolean {
  if (session.skill !== 'loop-design' || session.state === 'ended') return false;
  return 'concern' in target ? session.concern === target.concern : session.loop === target.loop && !session.concern;
}
