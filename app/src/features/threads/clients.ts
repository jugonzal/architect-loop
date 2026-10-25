// The threads and runner clients the thread screens call, made from the clients app-clients generates into
// src/api/ (command-center/D55), this build's URLs for the two services and the signed-in fetch. A build without one
// of the URLs gets a client that says so instead of calling the service (src/api/service.ts).

import { useMemo } from 'react';

import { createRunnerClient, type RunnerClient } from '../../api/runner.gen';
import { createThreadsClient, type ThreadsClient } from '../../api/threads.gen';
import { useSession } from '../../shell/session';

export function useThreadsClient(): ThreadsClient {
  const { config, fetch } = useSession();
  return useMemo(() => createThreadsClient({ baseUrl: config.threadsUrl, fetch }), [config.threadsUrl, fetch]);
}

export function useRunnerClient(): RunnerClient {
  const { config, fetch } = useSession();
  return useMemo(() => createRunnerClient({ baseUrl: config.runnerUrl, fetch }), [config.runnerUrl, fetch]);
}
