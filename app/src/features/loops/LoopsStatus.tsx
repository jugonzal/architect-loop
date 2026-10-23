// The Loops tab's copy of the project's status document. The tab's layout reads it once from the status client
// that app-shell provides, and its screens (the board, a loop, a concern) share that copy, so opening a concern
// never reads the status again. Pulling a screen down reads it afresh. A read that fails keeps the copy it had and
// says so, and every screen shows when its facts were gathered, so an old copy is never passed off as current.

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';

import type { StatusDocument } from '../../api/status';
import { useStatusClient } from '../../shell/session';

export type LoopsStatus =
  | { kind: 'no-service' }
  | { kind: 'loading' }
  | { kind: 'failed'; message: string }
  | { kind: 'ready'; doc: StatusDocument; refreshing: boolean; failure: string | null };

type Value = { status: LoopsStatus; refresh: () => void };

const LoopsStatusContext = createContext<Value | null>(null);

function messageOf(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

export function LoopsStatusProvider({ children }: { children: ReactNode }) {
  const client = useStatusClient();
  const [status, setStatus] = useState<LoopsStatus>(client ? { kind: 'loading' } : { kind: 'no-service' });
  const reads = useRef(0);

  const read = useCallback(async () => {
    if (!client) {
      setStatus({ kind: 'no-service' });
      return;
    }
    const n = ++reads.current;
    setStatus((now) => (now.kind === 'ready' ? { ...now, refreshing: true } : { kind: 'loading' }));
    try {
      const doc = await client.getStatus();
      if (n === reads.current) setStatus({ kind: 'ready', doc, refreshing: false, failure: null });
    } catch (error) {
      if (n !== reads.current) return;
      setStatus((now) =>
        now.kind === 'ready'
          ? { ...now, refreshing: false, failure: messageOf(error) }
          : { kind: 'failed', message: messageOf(error) },
      );
    }
  }, [client]);

  useEffect(() => {
    void read();
    return () => {
      // A read that answers after the tab is gone changes nothing.
      reads.current++;
    };
  }, [read]);

  const value = useMemo(() => ({ status, refresh: () => void read() }), [status, read]);
  return <LoopsStatusContext.Provider value={value}>{children}</LoopsStatusContext.Provider>;
}

export function useLoopsStatus(): Value {
  const value = useContext(LoopsStatusContext);
  if (!value) throw new Error("useLoopsStatus needs a LoopsStatusProvider: the Loops tab's layout renders one");
  return value;
}
