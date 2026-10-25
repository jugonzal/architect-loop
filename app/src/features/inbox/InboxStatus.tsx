// The Needs you tab's copy of the project's status document, and its runner client. The tab's layout reads the
// status once from the status client that app-shell provides, and the list and each card share that copy. Pulling
// a screen down reads it afresh. A read that fails keeps the copy it had and says so, and every screen shows when
// its facts were gathered, so an old copy is never passed off as current.
//
// The runner client is the one app-clients generates (command-center/D55), on the signed-in fetch, so every start
// carries the person's token and the runner names them as its sponsor (command-center/D28). A build with no runner
// URL has no client, and the cards say so instead of offering a start.

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';

import { createRunnerClient, type RunnerClient } from '../../api/runner.gen';
import type { ProjectKey, StatusDocument } from '../../api/status';
import { useSession, useSignedInUser, useStatusClient } from '../../shell/session';

export type InboxRead =
  | { kind: 'no-service' }
  | { kind: 'loading' }
  | { kind: 'failed'; message: string }
  | { kind: 'ready'; doc: StatusDocument; refreshing: boolean; failure: string | null };

export type InboxValue = {
  read: InboxRead;
  refresh: () => void;
  /** The signed-in person's GitHub login (command-center/D62). */
  login: string;
  project: ProjectKey;
  /** Null when the build has no runner URL yet. */
  runner: RunnerClient | null;
};

const InboxContext = createContext<InboxValue | null>(null);

function messageOf(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

export function InboxStatusProvider({ children }: { children: ReactNode }) {
  const client = useStatusClient();
  const { config, fetch } = useSession();
  const { login } = useSignedInUser();
  const [read, setRead] = useState<InboxRead>(client ? { kind: 'loading' } : { kind: 'no-service' });
  const reads = useRef(0);

  const load = useCallback(async () => {
    if (!client) {
      setRead({ kind: 'no-service' });
      return;
    }
    const n = ++reads.current;
    setRead((now) => (now.kind === 'ready' ? { ...now, refreshing: true } : { kind: 'loading' }));
    try {
      const doc = await client.getStatus();
      if (n === reads.current) setRead({ kind: 'ready', doc, refreshing: false, failure: null });
    } catch (error) {
      if (n !== reads.current) return;
      setRead((now) =>
        now.kind === 'ready'
          ? { ...now, refreshing: false, failure: messageOf(error) }
          : { kind: 'failed', message: messageOf(error) },
      );
    }
  }, [client]);

  useEffect(() => {
    void load();
    return () => {
      // A read that answers after the tab is gone changes nothing.
      reads.current++;
    };
  }, [load]);

  const runner = useMemo(
    () => (config.runnerUrl ? createRunnerClient({ baseUrl: config.runnerUrl, fetch }) : null),
    [config.runnerUrl, fetch],
  );

  const value = useMemo(
    () => ({ read, refresh: () => void load(), login, project: config.project, runner }),
    [read, load, login, config.project, runner],
  );
  return <InboxContext.Provider value={value}>{children}</InboxContext.Provider>;
}

export function useInbox(): InboxValue {
  const value = useContext(InboxContext);
  if (!value) throw new Error("useInbox needs an InboxStatusProvider: the Needs you tab's layout renders one");
  return value;
}
