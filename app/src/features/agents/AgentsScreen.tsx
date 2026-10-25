// The Agents tab (command-center/app-agents), drawn after the screen design's Agents artboard (command-center/D4):
// every running session with its skill, what it runs on, its sponsor, how long it has run and its spend against its
// budget (C1), and what an agent can start now, each with Start, the runner's estimate and a budget the person
// confirms (C2). The artboard's paused state and objections belong to later loops and are not drawn.
//
// The sessions come from the runner, read again every REFRESH_MS while the tab is in front. What can start comes
// from the status document, read when the tab opens and when it is pulled down. Every figure is the runner's
// estimate, labelled as one (D23). Starting costs money (the concern's effects; gates: spending), so nothing starts
// without the person seeing the estimate and the budget and pressing the confirmation; the runner names them as
// the sponsor from their token. A sponsor can stop their own sessions, and nobody else's.

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  ActivityIndicator,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';

import type { EstimateAnswer, RunnerClient, Session, SessionList } from '../../api/runner.gen';
import { serviceNotConfiguredMessage } from '../../api/service';
import type { StatusClient, StatusDocument } from '../../api/status';
import { colors, fonts, radius, space, touchTarget, type, verdict } from '../../theme';
import {
  canStop,
  elapsed,
  isActive,
  money,
  readAgo,
  REFRESH_MS,
  runningLine,
  runningSessions,
  skillBadge,
  slotsLine,
  slotsOf,
  spendView,
  stateLabel,
  targetOf,
} from './sessions';
import {
  dispatchFor,
  estimateLong,
  estimateShort,
  parseBudget,
  releaseLine,
  rowAction,
  rowButton,
  rowHeadline,
  startFailure,
  startRows,
  suggestedBudget,
  type StartRow,
  type StartSkill,
} from './starts';

export const NO_STATUS_SERVICE_MESSAGE =
  'This build has no status service yet, so it cannot tell what an agent can start. The owner sets ' +
  'EXPO_PUBLIC_STATUS_URL in app/eas.json once the status service is deployed.';

export const BUDGET_NOTE =
  'A budget is a target: the session stops at the first model response that crosses it, so it can pass it by one ' +
  "response. Its spend is the runner's estimate.";

type SessionsRead =
  | { kind: 'no-runner' }
  | { kind: 'reading' }
  | { kind: 'read'; list: SessionList; at: number; failure: string | null }
  | { kind: 'failed'; message: string };

type StatusRead =
  | { kind: 'no-service' }
  | { kind: 'reading' }
  | { kind: 'read'; doc: StatusDocument }
  | { kind: 'failed'; message: string };

type EstimateRead = { kind: 'reading' } | { kind: 'read'; answer: EstimateAnswer } | { kind: 'failed'; message: string };

/**
 * The release a start runs: the one its skill's estimate named, or none until the estimate names one (D68). A runner
 * deployed before latest-release answers no plugin_release at all, which is none too, so nothing starts on it.
 */
function releaseOf(estimate: EstimateRead | undefined): string | null {
  return estimate?.kind === 'read' ? (estimate.answer.plugin_release ?? null) : null;
}

/** The confirmation open under one row: the budget as typed, and whether it is being sent. */
type Draft = { command: string; budget: string; touched: boolean; sending: boolean; failure: string | null };

type Stop = { kind: 'confirm' } | { kind: 'sending' } | { kind: 'failed'; message: string };

export type AgentsScreenProps = {
  /** The runner's client for this build's environment, or null when the build has no runner URL. */
  runner: RunnerClient | null;
  /** The status client for this build's environment, or null when the build has none. */
  status: StatusClient | null;
  /** The signed-in person's GitHub login: the sponsor of whatever they start. */
  login: string;
  /** The project the build serves (command-center/D18). */
  project: string;
  /** Whether the tab is in front: the sessions are read again only while it is. */
  active?: boolean;
  /** The current time in ms since the epoch; tests pass their own. */
  now?: () => number;
  refreshMs?: number;
};

function messageOf(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

export function AgentsScreen({
  runner,
  status,
  login,
  project,
  active = true,
  now = Date.now,
  refreshMs = REFRESH_MS,
}: AgentsScreenProps) {
  const [sessions, setSessions] = useState<SessionsRead>(runner ? { kind: 'reading' } : { kind: 'no-runner' });
  const [doc, setDoc] = useState<StatusRead>(status ? { kind: 'reading' } : { kind: 'no-service' });
  const [estimates, setEstimates] = useState<Partial<Record<StartSkill, EstimateRead>>>({});
  const [draft, setDraft] = useState<Draft | null>(null);
  const [started, setStarted] = useState<Record<string, Session>>({});
  const [stops, setStops] = useState<Record<string, Stop>>({});
  const [refreshing, setRefreshing] = useState(false);
  // Only the latest read of each may change the screen, and none after it unmounts.
  const sessionReads = useRef(0);
  const statusReads = useRef(0);
  const alive = useRef(true);
  // The clock is read through a ref, so a caller that passes a new function each render does not restart the reads.
  const clock = useRef(now);
  clock.current = now;
  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
    };
  }, []);

  const readSessions = useCallback(async () => {
    if (!runner) {
      setSessions({ kind: 'no-runner' });
      return;
    }
    const id = ++sessionReads.current;
    try {
      const list = await runner.listSessions({ query: { state: 'active' } });
      if (alive.current && id === sessionReads.current) {
        setSessions({ kind: 'read', list, at: clock.current(), failure: null });
      }
    } catch (error) {
      if (!alive.current || id !== sessionReads.current) return;
      // A list read before stays, said to be old and how old, so a spend is never passed off as current.
      setSessions((was) =>
        was.kind === 'read' ? { ...was, failure: messageOf(error) } : { kind: 'failed', message: messageOf(error) },
      );
    }
  }, [runner]);

  const readStatus = useCallback(async () => {
    if (!status) {
      setDoc({ kind: 'no-service' });
      return;
    }
    const id = ++statusReads.current;
    try {
      const read = await status.getStatus();
      if (alive.current && id === statusReads.current) setDoc({ kind: 'read', doc: read });
    } catch (error) {
      if (alive.current && id === statusReads.current) setDoc({ kind: 'failed', message: messageOf(error) });
    }
  }, [status]);

  const readEstimates = useCallback(
    async (skills: readonly StartSkill[]) => {
      if (!runner || skills.length === 0) return;
      setEstimates((was) => ({ ...was, ...Object.fromEntries(skills.map((skill) => [skill, { kind: 'reading' }])) }));
      await Promise.all(
        skills.map(async (skill) => {
          let read: EstimateRead;
          try {
            read = { kind: 'read', answer: await runner.estimate({ query: { skill } }) };
          } catch (error) {
            read = { kind: 'failed', message: messageOf(error) };
          }
          if (alive.current) setEstimates((was) => ({ ...was, [skill]: read }));
        }),
      );
    },
    [runner],
  );

  // The sessions, now and every refreshMs while the tab is in front.
  useEffect(() => {
    if (!runner || !active) return;
    void readSessions();
    const timer = setInterval(() => void readSessions(), refreshMs);
    return () => {
      clearInterval(timer);
      sessionReads.current += 1;
    };
  }, [runner, active, refreshMs, readSessions]);

  useEffect(() => {
    void readStatus();
  }, [readStatus]);

  const rows = useMemo(() => (doc.kind === 'read' ? startRows(doc.doc) : []), [doc]);
  // The skills the rows start, kept the same while the set is, so a new status document with the same skills does
  // not read their estimates again.
  const skillsKey = [...new Set(rows.map((row) => row.skill))].sort().join(' ');
  const skills = useMemo(() => (skillsKey ? (skillsKey.split(' ') as StartSkill[]) : []), [skillsKey]);

  // One estimate per skill the rows start, read once the rows are known.
  useEffect(() => {
    void readEstimates(skills);
  }, [skills, readEstimates]);

  const refresh = useCallback(async () => {
    setRefreshing(true);
    await Promise.all([readSessions(), readStatus(), readEstimates(skills)]);
    if (alive.current) setRefreshing(false);
  }, [readSessions, readStatus, readEstimates, skills]);

  const estimateOf = (skill: StartSkill): EstimateRead | undefined => estimates[skill];

  // A confirmation opened before its estimate arrived takes the suggested budget once it does, unless the person
  // has typed one.
  useEffect(() => {
    if (!draft || draft.touched || draft.budget !== '') return;
    const row = rows.find((r) => r.command === draft.command);
    const estimate = row ? estimates[row.skill] : undefined;
    if (estimate?.kind === 'read' && estimate.answer.estimate) {
      setDraft({ ...draft, budget: suggestedBudget(estimate.answer.estimate) });
    }
  }, [draft, estimates, rows]);

  const time = now();
  const list = sessions.kind === 'read' ? sessions.list : null;
  const running = list ? runningSessions(list, project) : [];
  const slots = list ? slotsOf(list, login) : null;
  const full = slots !== null && slots.used >= slots.cap;

  const openStart = (row: StartRow) => {
    const estimate = estimateOf(row.skill);
    setDraft({
      command: row.command,
      budget: estimate?.kind === 'read' ? suggestedBudget(estimate.answer.estimate) : '',
      touched: false,
      sending: false,
      failure: null,
    });
  };

  const confirmStart = async (row: StartRow) => {
    if (!runner || !draft || draft.command !== row.command || draft.sending) return;
    const budget = parseBudget(draft.budget);
    const release = releaseOf(estimateOf(row.skill));
    if (!budget.ok || !release) return;
    setDraft({ ...draft, sending: true, failure: null });
    try {
      const session = await runner.dispatch({ body: dispatchFor(row, project, budget.usd, release) });
      if (!alive.current) return;
      setStarted((was) => ({ ...was, [row.command]: session }));
      setDraft(null);
      void readSessions();
    } catch (error) {
      if (!alive.current) return;
      setDraft((was) => (was && was.command === row.command ? { ...was, sending: false, failure: startFailure(error) } : was));
    }
  };

  const confirmStop = async (session: Session) => {
    if (!runner) return;
    setStops((was) => ({ ...was, [session.id]: { kind: 'sending' } }));
    try {
      const stopping = await runner.stopSession({ path: { id: session.id } });
      if (!alive.current) return;
      // A read that left before the stop would show the session running again, so it changes nothing.
      sessionReads.current += 1;
      setSessions((was) =>
        was.kind === 'read'
          ? { ...was, list: { ...was.list, sessions: was.list.sessions.map((s) => (s.id === session.id ? stopping : s)) } }
          : was,
      );
      setStops(({ [session.id]: _done, ...rest }) => rest);
    } catch (error) {
      if (alive.current) setStops((was) => ({ ...was, [session.id]: { kind: 'failed', message: messageOf(error) } }));
    }
  };

  return (
    <ScrollView
      testID="agents-list"
      style={styles.page}
      contentContainerStyle={styles.content}
      keyboardShouldPersistTaps="handled"
      refreshControl={
        <RefreshControl
          refreshing={refreshing}
          onRefresh={() => void refresh()}
          tintColor={colors.inkSubtle}
          colors={[colors.accent]}
        />
      }
    >
      <View style={styles.header}>
        <Text style={styles.overline} testID="agents-overline">
          {list ? runningLine(running) : 'Read from the runner'}
        </Text>
        <Text style={styles.title} accessibilityRole="header">
          Agents
        </Text>
        <Text style={styles.subtitle} testID="agents-slots">
          {slots ? slotsLine(slots) : 'Who runs what, and what it costs.'}
        </Text>
      </View>

      <SectionLabel text="Running" />
      {sessions.kind === 'no-runner' && <Notice text={serviceNotConfiguredMessage('runner')} />}
      {sessions.kind === 'reading' && <Reading text="Reading the runner…" />}
      {sessions.kind === 'failed' && (
        <Notice
          text="The runner could not be read, so no session is shown."
          detail={sessions.message}
          onRetry={() => void readSessions()}
        />
      )}
      {sessions.kind === 'read' && (
        <>
          {sessions.failure !== null && (
            <Text style={styles.failure} accessibilityRole="alert">
              {`The runner could not be read again, so this is the list as it was ${readAgo(sessions.at, time)}: ${sessions.failure}`}
            </Text>
          )}
          {running.length === 0 && <Text style={styles.muted}>No session is running.</Text>}
          {running.map((session) => (
            <SessionCard
              key={session.id}
              session={session}
              login={login}
              now={time}
              stop={stops[session.id]}
              onStop={() => setStops((was) => ({ ...was, [session.id]: { kind: 'confirm' } }))}
              onKeep={() => setStops(({ [session.id]: _kept, ...rest }) => rest)}
              onConfirmStop={() => void confirmStop(session)}
            />
          ))}
          <Text style={styles.caption} testID="sessions-read">
            {readAgo(sessions.at, time)}
          </Text>
        </>
      )}

      <SectionLabel text="Can start now" />
      {doc.kind === 'no-service' && <Notice text={NO_STATUS_SERVICE_MESSAGE} />}
      {doc.kind === 'reading' && <Reading text="Reading the status service…" />}
      {doc.kind === 'failed' && (
        <Notice
          text="The status service could not be read, so nothing is offered to start."
          detail={doc.message}
          onRetry={() => void readStatus()}
        />
      )}
      {doc.kind === 'read' && rows.length === 0 && <Text style={styles.muted}>Nothing is ready, shipped or stale.</Text>}
      {doc.kind === 'read' && rows.length > 0 && (
        <View style={styles.list}>
          {!runner && <Text style={[styles.muted, styles.listNote]}>{serviceNotConfiguredMessage('runner')}</Text>}
          {rows.map((row, index) => {
            const holder = list?.sessions.find(
              (s) => isActive(s) && s.concern === row.concern && s.skill === row.skill,
            );
            return (
              <StartRowView
                key={row.command}
                row={row}
                divider={index > 0 || !runner}
                estimate={estimateOf(row.skill)}
                holder={holder ?? null}
                started={started[row.command] ?? null}
                draft={draft?.command === row.command ? draft : null}
                canOpen={!!runner && !full && draft?.command !== row.command}
                login={login}
                onOpen={() => openStart(row)}
                onBudget={(budget) => setDraft((was) => (was ? { ...was, budget, touched: true } : was))}
                onCancel={() => setDraft(null)}
                onConfirm={() => void confirmStart(row)}
              />
            );
          })}
        </View>
      )}
    </ScrollView>
  );
}

function SessionCard({
  session,
  login,
  now,
  stop,
  onStop,
  onKeep,
  onConfirmStop,
}: {
  session: Session;
  login: string;
  now: number;
  stop: Stop | undefined;
  onStop: () => void;
  onKeep: () => void;
  onConfirmStop: () => void;
}) {
  const spend = spendView(session);
  const label = stateLabel(session);
  const mine = session.sponsor === login;
  return (
    <View testID={`session-${session.id}`} style={styles.card}>
      <View style={styles.tile} accessibilityElementsHidden importantForAccessibility="no-hide-descendants">
        <Text style={styles.tileText}>{skillBadge(session.skill)}</Text>
      </View>
      <View style={styles.cardBody}>
        <View style={styles.between}>
          <Text style={styles.cardTitle}>{`${session.skill} · ${targetOf(session)}`}</Text>
          {label !== null && (
            <View style={styles.chip}>
              <Text style={styles.chipText}>{label}</Text>
            </View>
          )}
        </View>
        <Text style={styles.meta}>{`sponsor ${session.sponsor}${mine ? ' (you)' : ''} · ${elapsed(session, now)}`}</Text>
        <View style={styles.spend} accessible accessibilityLabel={spend.label}>
          <View style={styles.track}>
            <View
              style={[styles.bar, { width: `${Math.round(spend.fraction * 100)}%` }, spend.over && styles.barOver]}
            />
          </View>
          <Text style={[styles.spendText, spend.over && styles.overText]}>{spend.text}</Text>
        </View>
        {canStop(session, login) && <StopControl stop={stop} onStop={onStop} onKeep={onKeep} onConfirm={onConfirmStop} />}
      </View>
    </View>
  );
}

function StopControl({
  stop,
  onStop,
  onKeep,
  onConfirm,
}: {
  stop: Stop | undefined;
  onStop: () => void;
  onKeep: () => void;
  onConfirm: () => void;
}) {
  if (stop?.kind === 'sending') return <Reading text="Stopping…" />;
  if (stop?.kind === 'confirm') {
    return (
      <View style={styles.confirmStop}>
        <Text style={styles.meta}>
          Stop this session? It ends within about 10 seconds. Its branch and pull request stay for a person to close.
        </Text>
        <View style={styles.buttons}>
          <SmallButton label="Stop it" kind="danger" onPress={onConfirm} />
          <SmallButton label="Keep running" kind="secondary" onPress={onKeep} />
        </View>
      </View>
    );
  }
  return (
    <View style={styles.tight}>
      {stop?.kind === 'failed' && (
        <Text style={styles.failure} accessibilityRole="alert">
          {`It was not stopped: ${stop.message}`}
        </Text>
      )}
      <SmallButton label="Stop" kind="secondary" onPress={onStop} />
    </View>
  );
}

function StartRowView({
  row,
  divider,
  estimate,
  holder,
  started,
  draft,
  canOpen,
  login,
  onOpen,
  onBudget,
  onCancel,
  onConfirm,
}: {
  row: StartRow;
  divider: boolean;
  estimate: EstimateRead | undefined;
  holder: Session | null;
  started: Session | null;
  draft: Draft | null;
  canOpen: boolean;
  login: string;
  onOpen: () => void;
  onBudget: (budget: string) => void;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  const short =
    estimate === undefined
      ? 'no estimate'
      : estimate.kind === 'reading'
        ? 'estimating…'
        : estimate.kind === 'failed'
          ? 'estimate unavailable'
          : estimateShort(estimate.answer);
  const label = rowButton(row);
  return (
    <View testID={`start-${row.concern}-${row.action}`} style={[styles.startRow, divider && styles.rowDivider]}>
      <View style={styles.startLine}>
        <View style={styles.grow}>
          <Text style={styles.startTitle}>{rowHeadline(row)}</Text>
          <Text style={styles.meta}>{`${rowAction(row)} · ${short}`}</Text>
        </View>
        {holder ? (
          <Text style={styles.meta}>{`running · ${holder.sponsor}`}</Text>
        ) : (
          <Pressable
            accessibilityRole="button"
            accessibilityLabel={`${label} ${row.concern}`}
            accessibilityState={{ disabled: !canOpen }}
            disabled={!canOpen}
            onPress={onOpen}
            style={({ pressed }) => [
              styles.rowButton,
              row.action === 'build' ? styles.primary : styles.outline,
              pressed && (row.action === 'build' ? styles.primaryPressed : styles.outlinePressed),
              !canOpen && styles.disabled,
            ]}
          >
            <Text style={row.action === 'build' ? styles.primaryText : styles.outlineText}>{label}</Text>
          </Pressable>
        )}
      </View>
      {started !== null && (
        <Text style={styles.startedText} accessibilityLiveRegion="polite">
          {`Started session ${started.id.slice(0, 7)}, sponsored by ${started.sponsor}, with a ${money(started.budget_usd)} budget.`}
        </Text>
      )}
      {draft !== null && (
        <Confirmation row={row} draft={draft} estimate={estimate} login={login} onBudget={onBudget} onCancel={onCancel} onConfirm={onConfirm} />
      )}
    </View>
  );
}

function Confirmation({
  row,
  draft,
  estimate,
  login,
  onBudget,
  onCancel,
  onConfirm,
}: {
  row: StartRow;
  draft: Draft;
  estimate: EstimateRead | undefined;
  login: string;
  onBudget: (budget: string) => void;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  const budget = parseBudget(draft.budget);
  const estimateText =
    estimate === undefined || estimate.kind === 'reading'
      ? 'Reading the estimate…'
      : estimate.kind === 'failed'
        ? `The estimate could not be read: ${estimate.message}`
        : estimateLong(estimate.answer);
  const release =
    estimate === undefined || estimate.kind === 'reading'
      ? 'Reading the release of the skills…'
      : estimate.kind === 'failed'
        ? 'The release of the skills could not be read, so it cannot start.'
        : releaseLine(estimate.answer);
  const confirmLabel = budget.ok ? `Start with a ${money(budget.usd)} budget` : 'Start';
  const enabled = budget.ok && !draft.sending && releaseOf(estimate) !== null;
  return (
    <View style={styles.confirm} testID="start-confirmation">
      <Text style={styles.confirmTitle}>{`/${row.skill} ${row.concern}${row.arguments ? ` ${row.arguments}` : ''}`}</Text>
      <Text style={styles.body} testID="start-estimate">
        {estimateText}
      </Text>
      <View style={styles.tight}>
        <Text style={styles.inputLabel}>Budget in dollars</Text>
        <TextInput
          testID="start-budget"
          accessibilityLabel="Budget in dollars"
          value={draft.budget}
          onChangeText={onBudget}
          editable={!draft.sending}
          keyboardType="decimal-pad"
          inputMode="decimal"
          placeholder="2.50"
          placeholderTextColor={colors.inkSubtle}
          style={styles.input}
        />
        {!budget.ok && <Text style={styles.meta}>{budget.reason}</Text>}
      </View>
      <Text style={styles.meta}>{BUDGET_NOTE}</Text>
      <Text style={styles.meta} testID="start-release">{`Sponsored by you, ${login}. ${release}`}</Text>
      {draft.failure !== null && (
        <Text style={styles.failure} accessibilityRole="alert">
          {draft.failure}
        </Text>
      )}
      {draft.sending ? (
        <Reading text="Starting…" />
      ) : (
        <View style={styles.buttons}>
          <Pressable
            accessibilityRole="button"
            accessibilityState={{ disabled: !enabled }}
            disabled={!enabled}
            onPress={onConfirm}
            style={({ pressed }) => [styles.rowButton, styles.primary, pressed && styles.primaryPressed, !enabled && styles.disabled]}
          >
            <Text style={styles.primaryText}>{confirmLabel}</Text>
          </Pressable>
          <SmallButton label="Cancel" kind="secondary" onPress={onCancel} />
        </View>
      )}
    </View>
  );
}

function SmallButton({ label, kind, onPress }: { label: string; kind: 'secondary' | 'danger'; onPress: () => void }) {
  return (
    <Pressable
      accessibilityRole="button"
      onPress={onPress}
      style={({ pressed }) => [styles.rowButton, styles.secondary, kind === 'danger' && styles.danger, pressed && styles.secondaryPressed]}
    >
      <Text style={[styles.secondaryText, kind === 'danger' && styles.dangerText]}>{label}</Text>
    </Pressable>
  );
}

function SectionLabel({ text }: { text: string }) {
  return (
    <Text style={styles.section} accessibilityRole="header">
      {text}
    </Text>
  );
}

function Reading({ text }: { text: string }) {
  return (
    <View style={styles.reading}>
      <ActivityIndicator color={colors.inkSubtle} />
      <Text style={styles.muted}>{text}</Text>
    </View>
  );
}

function Notice({ text, detail, onRetry }: { text: string; detail?: string; onRetry?: () => void }) {
  return (
    <View style={[styles.card, styles.notice]}>
      <View style={styles.cardBody}>
        <Text style={styles.noticeText}>{text}</Text>
        {detail !== undefined && <Text style={styles.failure}>{detail}</Text>}
        {onRetry && <SmallButton label="Try again" kind="secondary" onPress={onRetry} />}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  page: { flex: 1, backgroundColor: colors.ground },
  content: { paddingHorizontal: space.l, paddingBottom: space.xxl, gap: space.m },
  header: { paddingHorizontal: space.xs, paddingTop: space.s, paddingBottom: space.xs, gap: space.xs },
  overline: { ...type.overline, color: colors.inkSubtle, textTransform: 'uppercase' },
  title: { ...type.title, color: colors.ink },
  subtitle: { ...type.bodySmall, color: colors.inkMuted },
  section: { ...type.label, color: colors.inkMuted, textTransform: 'uppercase', marginTop: space.xs, marginHorizontal: space.xs },
  reading: { flexDirection: 'row', alignItems: 'center', gap: space.s, paddingVertical: space.s },
  muted: { ...type.bodySmall, color: colors.inkMuted },
  caption: { ...type.caption, color: colors.inkSubtle, marginHorizontal: space.xs },
  failure: { ...type.mono, color: verdict.CONTRADICTS.fg },
  card: {
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.card,
    paddingVertical: space.m,
    paddingHorizontal: space.l,
    flexDirection: 'row',
    gap: space.m,
  },
  // A notice is drawn like the Environments tab's unknown card: a dashed outline on the ground.
  notice: { backgroundColor: 'transparent', borderStyle: 'dashed', borderColor: colors.inkSubtle },
  noticeText: { ...type.bodySmall, color: colors.inkSecondary },
  tile: {
    width: 36,
    height: 36,
    borderRadius: 8,
    backgroundColor: colors.ink,
    alignItems: 'center',
    justifyContent: 'center',
    flexShrink: 0,
  },
  tileText: { fontFamily: fonts.monoSemiBold, fontSize: 11, lineHeight: 14, color: colors.onInk },
  cardBody: { flex: 1, minWidth: 0, gap: space.xs },
  between: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start', gap: space.s },
  cardTitle: { ...type.body, fontFamily: fonts.sansSemiBold, color: colors.ink, flexShrink: 1 },
  chip: { borderRadius: radius.pill, backgroundColor: colors.inset, paddingHorizontal: 7, paddingVertical: 1, flexShrink: 0 },
  chipText: { fontFamily: fonts.monoSemiBold, fontSize: 10, lineHeight: 16, letterSpacing: 0.4, color: colors.inkSecondary },
  meta: { ...type.caption, color: colors.inkMuted },
  spend: { flexDirection: 'row', alignItems: 'center', gap: space.s },
  track: { flex: 1, height: 4, borderRadius: 2, backgroundColor: colors.border, overflow: 'hidden' },
  bar: { height: 4, backgroundColor: colors.accent },
  barOver: { backgroundColor: verdict.CONTRADICTS.fg },
  spendText: { ...type.mono, fontFamily: fonts.monoMedium, fontSize: 11, color: colors.inkSecondary },
  overText: { color: verdict.CONTRADICTS.fg },
  confirmStop: { gap: space.s, paddingTop: space.xs },
  tight: { gap: space.xs, alignItems: 'flex-start' },
  buttons: { flexDirection: 'row', flexWrap: 'wrap', gap: space.s },
  list: {
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.card,
  },
  listNote: { paddingHorizontal: space.l, paddingTop: space.m },
  startRow: { paddingVertical: space.m, paddingHorizontal: space.l, gap: space.s },
  rowDivider: { borderTopWidth: 1, borderTopColor: colors.divider },
  startLine: { flexDirection: 'row', alignItems: 'center', gap: space.m },
  grow: { flex: 1, minWidth: 0 },
  startTitle: { ...type.body, fontFamily: fonts.sansMedium, color: colors.ink },
  startedText: { ...type.caption, color: verdict.HOLDS.fg },
  rowButton: {
    minHeight: touchTarget,
    paddingHorizontal: space.l,
    borderRadius: radius.button,
    alignItems: 'center',
    justifyContent: 'center',
  },
  primary: { backgroundColor: colors.accent },
  primaryPressed: { backgroundColor: colors.accentPressed },
  primaryText: { ...type.button, color: colors.onAccent },
  outline: { borderWidth: 1, borderColor: colors.accent, backgroundColor: colors.surface },
  outlinePressed: { backgroundColor: colors.accentSoft },
  outlineText: { ...type.button, color: colors.accent },
  secondary: { borderWidth: 1, borderColor: colors.borderStrong, backgroundColor: colors.surface },
  secondaryPressed: { backgroundColor: colors.inset },
  secondaryText: { ...type.button, color: colors.inkSecondary },
  danger: { borderColor: verdict.CONTRADICTS.fg },
  dangerText: { color: verdict.CONTRADICTS.fg },
  disabled: { opacity: 0.45 },
  confirm: { backgroundColor: colors.inset, borderRadius: radius.button, padding: space.m, gap: space.s },
  confirmTitle: { ...type.mono, fontFamily: fonts.monoSemiBold, color: colors.ink },
  body: { ...type.bodySmall, color: colors.ink },
  inputLabel: { ...type.caption, fontFamily: fonts.sansSemiBold, color: colors.inkMuted },
  input: {
    ...type.body,
    minHeight: touchTarget,
    alignSelf: 'stretch',
    borderWidth: 1,
    borderColor: colors.borderStrong,
    borderRadius: radius.button,
    backgroundColor: colors.surface,
    paddingHorizontal: space.m,
    color: colors.ink,
  },
});
