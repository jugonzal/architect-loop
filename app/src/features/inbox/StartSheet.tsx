// What a card shows before it starts a session, which costs money (the concern's effects; gates: spending): the
// command it would run, that the person sponsors it, the budget, the runner's estimate and the release of the
// skills. Nothing starts until the person presses Start, and every press starts exactly one session.
//
// The release is the one the runner's estimate names, the newest release tag (latest-release C2,
// command-center/D68), and the start sends exactly that tag, so what the sheet shows is what runs. Until the runner
// names one, nothing starts.
//
// The sponsor is whoever is signed in: the dispatch goes through the signed-in fetch, and the runner names its
// caller as the sponsor and takes no sponsor from the request (command-center/D28). A budget is a target the
// session may pass by one model response (command-center/D21), and every figure is an estimate
// (command-center/D23), so the sheet says both.

import { useState } from 'react';
import { ActivityIndicator, Text, TextInput, View } from 'react-native';

import type { Refusal, Session } from '../../api/runner.gen';
import { ServiceError, serviceNotConfiguredMessage } from '../../api/service';
import { colors } from '../../theme';
import { DEFAULT_BUDGET_USD, dispatchRequest, formatUsd, parseBudget, type SessionPlan } from './dispatch';
import { useInbox } from './InboxStatus';
import { serviceMessage, useEstimate, type EstimateRead } from './sessions';
import { Button, Card, Notice, SectionLabel, styles } from './ui';

export const NO_RUNNER_MESSAGE = serviceNotConfiguredMessage('runner');

type Failure = { message: string; running: Session | null };

function failureOf(error: unknown): Failure {
  const refusal =
    error instanceof ServiceError && error.status === 409 ? (error.body as Partial<Refusal> | null) : null;
  const running = refusal?.refused === 'running-session' ? (refusal.sessions?.[0] ?? null) : null;
  return { message: serviceMessage(error), running };
}

function estimateLine(read: EstimateRead, skill: string): string {
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
        : `No estimate yet: no ${skill} session on ${read.model} has been measured.`;
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

export function StartSheet({
  plan,
  intro,
  onStarted,
  onCancel,
}: {
  plan: SessionPlan;
  /** What starting it does, in a sentence. */
  intro: string;
  /** Called with the session the runner started, or with the one a refusal named as already doing the work. */
  onStarted: (session: Session) => void;
  onCancel: () => void;
}) {
  const { runner, project, login } = useInbox();
  const [budgetText, setBudgetText] = useState(DEFAULT_BUDGET_USD.toFixed(2));
  const [starting, setStarting] = useState(false);
  const [failure, setFailure] = useState<Failure | null>(null);
  const estimate = useEstimate(runner, plan.target.skill);
  const budget = parseBudget(budgetText);
  const release = estimate.kind === 'read' ? estimate.release : null;

  const start = async () => {
    if (!runner || budget === null || release === null || starting) return;
    setStarting(true);
    setFailure(null);
    try {
      const session = await runner.dispatch({ body: dispatchRequest(plan, { project, budgetUsd: budget, release }) });
      onStarted(session);
    } catch (error) {
      setFailure(failureOf(error));
      setStarting(false);
    }
  };

  return (
    <Card testID="start-sheet">
      <SectionLabel text="Start a session" />
      <Text style={styles.body}>{intro}</Text>
      <Text style={styles.command} selectable testID="start-command">
        {plan.command}
      </Text>
      <Text style={styles.bodyMuted} testID="start-sponsor">
        {`Sponsored by @${login}: the runner names whoever starts a session as its sponsor, and counts it against their cap.`}
      </Text>
      <View style={styles.tight}>
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
        <Text style={styles.bodyMuted}>
          {budget === null
            ? 'A budget is a number of dollars above 0, such as 2.50.'
            : 'A target: the session stops at the first model response that crosses it, so it can pass it by one.'}
        </Text>
      </View>
      <Text style={styles.bodyMuted} testID="start-estimate">
        {estimateLine(estimate, plan.target.skill)}
      </Text>
      <Text style={styles.bodyMuted} testID="start-release">
        {releaseLine(estimate)}
      </Text>
      {!runner && <Notice text={NO_RUNNER_MESSAGE} alert />}
      {failure && (
        <View style={styles.tight}>
          <Notice text={`The runner did not start it. ${failure.message}`} alert />
          {failure.running && (
            <Button
              label="Follow the session already doing it"
              kind="secondary"
              onPress={() => failure.running && onStarted(failure.running)}
            />
          )}
        </View>
      )}
      <View style={styles.buttons}>
        <Button label="Cancel" kind="secondary" onPress={onCancel} disabled={starting} />
        <Button
          label={budget === null ? 'Start' : `Start · budget ${formatUsd(budget)}`}
          hint={`Starts ${plan.command}, sponsored by you`}
          onPress={() => void start()}
          disabled={!runner || budget === null || release === null || starting}
        />
      </View>
      {starting && <ActivityIndicator color={colors.accent} accessibilityLabel="Starting" />}
    </Card>
  );
}
