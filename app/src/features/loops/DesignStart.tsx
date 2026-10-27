// A design session from a concern's or a loop's page (app-documents C2, command-center/D72). The card shows a design
// session already running on it, whoever sponsors it, and offers to start one. Starting costs money (the concern's
// effects; gates: spending), so the sheet shows first what the inbox's start sheet shows: the command, that the person
// sponsors it, the budget, the runner's estimate and the release of the skills. Nothing starts until the person
// presses Start, and every press starts exactly one session. Once it starts, its thread opens, where the person
// answers what /loop-design asks.

import { useRouter } from 'expo-router';
import { useEffect, useMemo, useState } from 'react';
import { ActivityIndicator, StyleSheet, Text, TextInput, View } from 'react-native';

import { createRunnerClient, type Refusal, type RunnerClient, type Session } from '../../api/runner.gen';
import { ServiceError, serviceNotConfiguredMessage } from '../../api/service';
import { useSession, useSignedInUser } from '../../shell/session';
import { colors, radius, space, type } from '../../theme';
import { DEFAULT_BUDGET_USD, formatUsd, parseBudget } from '../inbox/dispatch';
import { serviceMessage, sessionSummary, useEstimate, type EstimateRead } from '../inbox/sessions';
import { sessionThreadHref } from './board';
import { designCommand, designRequest, designsTarget, designTargetName, type DesignTarget } from './design';
import { Button, Card, Notice, SectionLabel, styles as ui } from './ui';

function useRunner(): RunnerClient | null {
  const { config, fetch } = useSession();
  return useMemo(
    () => (config.runnerUrl ? createRunnerClient({ baseUrl: config.runnerUrl, fetch }) : null),
    [config.runnerUrl, fetch],
  );
}

/** The design session already running on the target, if the runner lists one. */
function useRunningDesign(runner: RunnerClient | null, target: DesignTarget): Session | null {
  const { config } = useSession();
  const [running, setRunning] = useState<Session | null>(null);
  const key = designTargetName(target);
  useEffect(() => {
    if (!runner) return;
    let live = true;
    runner
      .listSessions({ query: { state: 'active', project: config.project } })
      .then(({ sessions }) => live && setRunning(sessions.find((s) => designsTarget(target, s)) ?? null))
      // Not knowing what runs only means none is shown; the runner still refuses a second one on a concern.
      .catch(() => live && setRunning(null));
    return () => {
      live = false;
    };
    // The target is read through its name, so a new object for the same target asks nothing again.
  }, [runner, config.project, key]); // eslint-disable-line react-hooks/exhaustive-deps
  return running;
}

export function DesignStart({ target, what }: { target: DesignTarget; what: string }) {
  const router = useRouter();
  const runner = useRunner();
  const running = useRunningDesign(runner, target);
  const [open, setOpen] = useState(false);
  const openThread = (session: Session) => router.push(sessionThreadHref(session.id));

  return (
    <Card testID="design">
      <SectionLabel text="Decide" />
      <Text style={ui.bodyMuted}>
        {`A design session works out the open decisions on ${what} with you: /loop-design asks in its thread, and you answer there.`}
      </Text>
      {!runner && <Notice text={serviceNotConfiguredMessage('runner')} alert />}
      {running && (
        <View style={ui.tight}>
          <Text style={ui.mono} testID="design-running">
            {sessionSummary(running)}
          </Text>
          <Button label="Open its thread" onPress={() => openThread(running)} />
        </View>
      )}
      {runner && !open && <Button label="Design it in a session" onPress={() => setOpen(true)} />}
      {runner && open && (
        <DesignSheet runner={runner} target={target} onStarted={openThread} onCancel={() => setOpen(false)} />
      )}
    </Card>
  );
}

type Failure = { message: string; running: Session | null };

function failureOf(error: unknown): Failure {
  const refusal =
    error instanceof ServiceError && error.status === 409 ? (error.body as Partial<Refusal> | null) : null;
  const running = refusal?.refused === 'running-session' ? (refusal.sessions?.[0] ?? null) : null;
  return { message: serviceMessage(error), running };
}

function estimateLine(read: EstimateRead): string {
  switch (read.kind) {
    case 'no-runner':
      return 'No estimate: this build cannot reach the runner.';
    case 'loading':
      return 'Asking the runner for an estimate…';
    case 'failed':
      return `No estimate: ${read.message}`;
    case 'read':
      return read.estimate
        ? `Estimated ${formatUsd(read.estimate.usd)} and ${Math.round(read.estimate.wall_clock_s / 60)} min, the ` +
            `median of its last ${read.estimate.sessions} on ${read.model}.`
        : `No estimate yet: no loop-design session on ${read.model} has been measured.`;
  }
}

function releaseLine(read: EstimateRead): string {
  switch (read.kind) {
    case 'no-runner':
      return 'No release: this build cannot reach the runner.';
    case 'loading':
      return 'Asking the runner for the newest release of the skills…';
    case 'failed':
      return 'The runner did not say which release of the skills to run, so nothing can start.';
    case 'read':
      return read.release
        ? `Runs the skills released as ${read.release}, the newest release.`
        : 'The project has no release of the skills yet, so nothing can start.';
  }
}

function DesignSheet({
  runner,
  target,
  onStarted,
  onCancel,
}: {
  runner: RunnerClient;
  target: DesignTarget;
  /** Called with the session the runner started, or with the one a refusal named as already doing the work. */
  onStarted: (session: Session) => void;
  onCancel: () => void;
}) {
  const { config } = useSession();
  const { login } = useSignedInUser();
  const [budgetText, setBudgetText] = useState(DEFAULT_BUDGET_USD.toFixed(2));
  const [starting, setStarting] = useState(false);
  const [failure, setFailure] = useState<Failure | null>(null);
  const estimate = useEstimate(runner, 'loop-design');
  const budget = parseBudget(budgetText);
  const release = estimate.kind === 'read' ? estimate.release : null;

  const start = async () => {
    if (budget === null || release === null || starting) return;
    setStarting(true);
    setFailure(null);
    try {
      const session = await runner.dispatch({
        body: designRequest(target, { project: config.project, budgetUsd: budget, release }),
      });
      onStarted(session);
    } catch (error) {
      setFailure(failureOf(error));
      setStarting(false);
    }
  };

  return (
    <View style={[ui.group, styles.sheet]} testID="design-sheet">
      <SectionLabel text="Start a session" />
      <Text style={styles.command} selectable testID="start-command">
        {designCommand(target)}
      </Text>
      <Text style={ui.bodyMuted} testID="start-sponsor">
        {`Sponsored by @${login}: the runner names whoever starts a session as its sponsor, and counts it against their cap.`}
      </Text>
      <View style={ui.tight}>
        <Text style={styles.label}>Budget, in dollars</Text>
        <TextInput
          accessibilityLabel="Budget, in dollars"
          value={budgetText}
          onChangeText={setBudgetText}
          keyboardType="decimal-pad"
          inputMode="decimal"
          editable={!starting}
          style={styles.input}
          placeholderTextColor={colors.inkSubtle}
        />
        <Text style={ui.bodyMuted}>
          {budget === null
            ? 'A budget is a number of dollars above 0, such as 2.50.'
            : 'A target: the session stops at the first model response that crosses it, so it can pass it by one.'}
        </Text>
      </View>
      <Text style={ui.bodyMuted} testID="start-estimate">
        {estimateLine(estimate)}
      </Text>
      <Text style={ui.bodyMuted} testID="start-release">
        {releaseLine(estimate)}
      </Text>
      {failure && (
        <View style={ui.tight}>
          <Notice text={`The runner did not start it. ${failure.message}`} alert />
          {failure.running && (
            <Button
              label="Follow the session already doing it"
              onPress={() => failure.running && onStarted(failure.running)}
            />
          )}
        </View>
      )}
      <View style={ui.inline}>
        <Button label="Cancel" onPress={onCancel} disabled={starting} />
        <Button
          label={budget === null ? 'Start' : `Start · budget ${formatUsd(budget)}`}
          hint={`Starts ${designCommand(target)}, sponsored by you`}
          onPress={() => void start()}
          disabled={budget === null || release === null || starting}
        />
      </View>
      {starting && <ActivityIndicator color={colors.accent} accessibilityLabel="Starting" />}
    </View>
  );
}

const styles = StyleSheet.create({
  sheet: { borderTopWidth: 1, borderTopColor: colors.divider, paddingTop: space.m },
  command: { ...type.mono, color: colors.ink, backgroundColor: colors.inset, borderRadius: radius.button, padding: space.s },
  label: { ...type.label, color: colors.inkMuted },
  input: {
    ...type.body,
    color: colors.ink,
    borderWidth: 1,
    borderColor: colors.borderStrong,
    borderRadius: radius.button,
    paddingHorizontal: space.m,
    paddingVertical: space.s,
  },
});
