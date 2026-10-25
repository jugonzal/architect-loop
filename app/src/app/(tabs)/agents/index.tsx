// The Agents tab (command-center/app-agents), in the folder the shell names after it (src/shell/tabs.ts). It makes
// the runner's client from the build's runner URL and the signed-in fetch, so every call carries the person's token
// and the runner names them as the sponsor of what they start (command-center/D28). It takes the session's status
// client, and draws src/features/agents/, which reads the runner again only while this tab is in front.

import { useIsFocused } from 'expo-router';
import { useMemo } from 'react';

import { createRunnerClient } from '../../../api/runner.gen';
import { AgentsScreen } from '../../../features/agents/AgentsScreen';
import { useSession, useSignedInUser } from '../../../shell/session';

export default function AgentsTab() {
  const { config, fetch, status } = useSession();
  const user = useSignedInUser();
  const focused = useIsFocused();
  const runner = useMemo(
    () => (config.runnerUrl ? createRunnerClient({ baseUrl: config.runnerUrl, fetch }) : null),
    [config.runnerUrl, fetch],
  );
  return <AgentsScreen runner={runner} status={status} login={user.login} project={config.project} active={focused} />;
}
