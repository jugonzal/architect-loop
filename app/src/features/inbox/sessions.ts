// The runner's side of a card: the latest session doing the card's work, followed until it ends, and the runner's
// estimate before a start. A card finds an earlier session through the runner's own list, newest first and whoever
// sponsored it, so a brief written an hour ago, or a question already being answered, shows again when the card is
// reopened. Nothing is kept on the phone: the runner is the record of its sessions (command-center/D26).
//
// Nothing here starts a session. Starting is the start sheet's, on the person's press (StartSheet.tsx).

import { useCallback, useEffect, useRef, useState } from 'react';

import type { Estimate, RunnerClient, Session, Skill } from '../../api/runner.gen';
import { ServiceError } from '../../api/service';
import type { ProjectKey } from '../../api/status';
import { formatUsd, sameWork, targetName, type SessionPlan } from './dispatch';

/** How often a card asks the runner about a session that has not ended. */
export const POLL_MS = 5_000;

export type Watch =
  | { kind: 'no-runner' }
  | { kind: 'looking' }
  | { kind: 'none' }
  | { kind: 'session'; session: Session; failure: string | null }
  | { kind: 'failed'; message: string };

/** What a service said, in its own words when it gave some (Problem and Refusal both carry a message). */
export function serviceMessage(error: unknown): string {
  if (error instanceof ServiceError) {
    const said = (error.body as { message?: unknown } | null)?.message;
    if (typeof said === 'string' && said) return said;
  }
  return error instanceof Error ? error.message : String(error);
}

/**
 * A session in one line: its state (or how it ended), its sponsor, its budget, and what it has spent, which is
 * always an estimate (command-center/D23).
 */
export function sessionSummary(session: Session): string {
  const state = session.state === 'ended' ? `ended: ${session.outcome ?? 'outcome unknown'}` : session.state;
  const spend = session.spend
    ? ` · ${session.state === 'ended' ? 'spent' : 'spent so far'} about ${formatUsd(session.spend.usd)} (estimate)`
    : '';
  return `${state} · sponsored by @${session.sponsor} · budget ${formatUsd(session.budget_usd)}${spend}`;
}

function planKey(plan: SessionPlan | null): string {
  return plan ? `${plan.purpose}|${plan.target.skill}|${targetName(plan.target)}|${JSON.stringify(plan.match)}` : '';
}

/**
 * The newest session that does a plan's work, followed until it ends. `adopt` takes a session the card has just
 * started (or one a refusal named) and follows it instead.
 */
export function useLatestSession(
  runner: RunnerClient | null,
  project: ProjectKey,
  plan: SessionPlan | null,
): { watch: Watch; adopt: (session: Session) => void } {
  const [watch, setWatch] = useState<Watch>(runner ? { kind: 'looking' } : { kind: 'no-runner' });
  // Only the latest lookup or poll may change the card, and none after it unmounts.
  const turn = useRef(0);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const key = planKey(plan);
  const planRef = useRef(plan);
  planRef.current = plan;

  const stop = useCallback(() => {
    if (timer.current) clearTimeout(timer.current);
    timer.current = null;
  }, []);

  const follow = useCallback(
    (first: Session, n: number) => {
      stop();
      const show = (session: Session, failure: string | null) => {
        setWatch({ kind: 'session', session, failure });
        if (!runner || session.state === 'ended') return;
        timer.current = setTimeout(async () => {
          try {
            const next = await runner.getSession({ path: { id: session.id } });
            if (n === turn.current) show(next, null);
          } catch (error) {
            // Keep asking: a session that could not be read once has not ended because of it.
            if (n === turn.current) show(session, serviceMessage(error));
          }
        }, POLL_MS);
      };
      show(first, null);
    },
    [runner, stop],
  );

  useEffect(() => {
    const n = ++turn.current;
    const current = planRef.current;
    if (!runner || !current) {
      setWatch(runner ? { kind: 'none' } : { kind: 'no-runner' });
      return;
    }
    setWatch({ kind: 'looking' });
    void (async () => {
      try {
        const { sessions } = await runner.listSessions({ query: { state: 'all', project } });
        if (n !== turn.current) return;
        const found = sessions.find((s) => sameWork(current, s));
        if (found) follow(found, n);
        else setWatch({ kind: 'none' });
      } catch (error) {
        if (n === turn.current) setWatch({ kind: 'failed', message: serviceMessage(error) });
      }
    })();
    return () => {
      turn.current++;
      stop();
    };
  }, [runner, project, key, follow, stop]);

  // A lookup still on its way answers too late to replace the session the card now follows.
  const adopt = useCallback((session: Session) => follow(session, ++turn.current), [follow]);
  return { watch, adopt };
}

export type EstimateRead =
  | { kind: 'no-runner' }
  | { kind: 'loading' }
  | { kind: 'read'; model: string; estimate: Estimate | null; release: string | null }
  | { kind: 'failed'; message: string };

/**
 * The runner's estimate for a skill on its model, before a start (command-center/D23), and the newest release of the
 * skills, which the start runs (command-center/D68).
 */
export function useEstimate(runner: RunnerClient | null, skill: Skill): EstimateRead {
  const [read, setRead] = useState<EstimateRead>(runner ? { kind: 'loading' } : { kind: 'no-runner' });
  useEffect(() => {
    if (!runner) {
      setRead({ kind: 'no-runner' });
      return;
    }
    let live = true;
    setRead({ kind: 'loading' });
    runner
      .estimate({ query: { skill } })
      .then(
        (answer) =>
          // A runner deployed before latest-release names no release at all, which is none: nothing starts on it.
          live && setRead({ kind: 'read', model: answer.model, estimate: answer.estimate, release: answer.plugin_release ?? null }),
      )
      .catch((error: unknown) => live && setRead({ kind: 'failed', message: serviceMessage(error) }));
    return () => {
      live = false;
    };
  }, [runner, skill]);
  return read;
}
