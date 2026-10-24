// A loop's, a concern's or a session's thread (C1), after the screen design's Session thread artboard
// (command-center/D4), without its objection block, which belongs to a later loop, and without its Stop button, which
// writes a baton, also a later loop's. The header names the thread and its members, and has Watch; the history reads
// oldest first, with each run of a session's narration collapsed to one line that opens it, so the milestones show;
// the footer says who is watching and lets the person post as themselves.
//
// Any member can mark a message "record this?" (command-center/D36). The loop's owner can accept a marked message,
// which opens a sheet that shows the /loop-design dispatch, its budget and the skills' release before it starts it
// through the runner, sponsored by them (C2). Everyone else sees the mark read-only (command-center/D10).
//
// The screen shows only what the threads service answered. A read that fails keeps what the screen had and says so.

import { useRouter } from 'expo-router';
import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import {
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import Svg, { Path } from 'react-native-svg';

import type { EstimateAnswer, RunnerClient, Session } from '../../api/runner.gen';
import type { ProjectKey } from '../../api/status';
import type { Message, Thread } from '../../api/threads.gen';
import { useSession, useSignedInUser, useStatusClient } from '../../shell/session';
import { colors, fonts, radius, space, touchTarget, type, verdict } from '../../theme';
import { useRunnerClient, useThreadsClient } from './clients';
import {
  authorDetail,
  authorName,
  backTarget,
  DEFAULT_BUDGET_USD,
  dispatchErrorText,
  dollars,
  markable,
  parseBudget,
  readAllMessages,
  recordDispatch,
  recordTarget,
  sameLogin,
  sessionInitials,
  sessionThreadHref,
  sessionTitle,
  SKILLS_RELEASE,
  targetName,
  threadCalls,
  threadErrorText,
  threadHref,
  threadLoop,
  timeline,
  timeOf,
  validRelease,
  withMessage,
  type RecordTarget,
  type ThreadCalls,
  type ThreadRef,
  type TimelineItem,
} from './thread';

/** The most a person can post at once (openapi.yaml, NewMessage.body). */
const MAX_BODY = 65536;

function messageOf(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

type History =
  | { kind: 'reading' }
  | { kind: 'failed'; message: string }
  | { kind: 'read'; thread: Thread; messages: Message[]; refreshing: boolean; failure: string | null };

/** The thread and its whole history, read when the screen opens and again when it is pulled down. */
function useHistory(calls: ThreadCalls, project: string) {
  const [history, setHistory] = useState<History>({ kind: 'reading' });
  // Only the latest read may change the screen, and none after it closes.
  const reads = useRef(0);

  const read = useCallback(async () => {
    const n = ++reads.current;
    setHistory((now) => (now.kind === 'read' ? { ...now, refreshing: true } : { kind: 'reading' }));
    try {
      const [thread, messages] = await Promise.all([calls.get(), readAllMessages(calls)]);
      if (n === reads.current) setHistory({ kind: 'read', thread, messages, refreshing: false, failure: null });
    } catch (error) {
      if (n !== reads.current) return;
      const message = threadErrorText(error, project);
      setHistory((now) =>
        now.kind === 'read' ? { ...now, refreshing: false, failure: message } : { kind: 'failed', message },
      );
    }
  }, [calls, project]);

  useEffect(() => {
    void read();
    return () => {
      reads.current++;
    };
  }, [read]);

  const put = useCallback(
    (message: Message) =>
      setHistory((now) => (now.kind === 'read' ? { ...now, messages: withMessage(now.messages, message) } : now)),
    [],
  );
  const setThread = useCallback(
    (thread: Thread) => setHistory((now) => (now.kind === 'read' ? { ...now, thread } : now)),
    [],
  );
  return { history, read, put, setThread };
}

type RunnerRead = { kind: 'none' } | { kind: 'reading' } | { kind: 'read'; session: Session } | { kind: 'failed'; message: string };

/** A session thread's session, from the runner: its skill, what it runs on, its sponsor and its spend. */
function useRunnerSession(runner: RunnerClient, ref: ThreadRef): RunnerRead {
  const id = ref.scope === 'session' ? ref.session : null;
  const [read, setRead] = useState<RunnerRead>(id ? { kind: 'reading' } : { kind: 'none' });
  useEffect(() => {
    if (!id) {
      setRead({ kind: 'none' });
      return;
    }
    let live = true;
    setRead({ kind: 'reading' });
    runner.getSession({ path: { id } }).then(
      (session) => live && setRead({ kind: 'read', session }),
      (error) => live && setRead({ kind: 'failed', message: messageOf(error) }),
    );
    return () => {
      live = false;
    };
  }, [runner, id]);
  return read;
}

type OwnerRead = { kind: 'reading' } | { kind: 'known'; login: string } | { kind: 'unknown'; why: string };

/** The loop's owner, from the status document: the one person who accepts a mark (command-center/D10). */
function useLoopOwner(loop: string | null, pending: boolean): OwnerRead {
  const status = useStatusClient();
  const [owner, setOwner] = useState<OwnerRead>({ kind: 'reading' });
  useEffect(() => {
    if (pending) {
      setOwner({ kind: 'reading' });
      return;
    }
    if (!loop) {
      setOwner({ kind: 'unknown', why: 'The runner could not say which loop this session belongs to.' });
      return;
    }
    if (!status) {
      setOwner({ kind: 'unknown', why: "This build has no status service URL, so the loop's owner cannot be read." });
      return;
    }
    let live = true;
    setOwner({ kind: 'reading' });
    status.getStatus().then(
      (doc) => {
        if (!live) return;
        const found = doc.loops.find((l) => l.id === loop);
        setOwner(
          found?.owner
            ? { kind: 'known', login: found.owner }
            : { kind: 'unknown', why: found ? `The status names no owner for ${loop}.` : `The status has no loop named ${loop}.` },
        );
      },
      (error) => live && setOwner({ kind: 'unknown', why: `The status could not be read, so the loop's owner is unknown. ${messageOf(error)}` }),
    );
    return () => {
      live = false;
    };
  }, [status, loop, pending]);
  return owner;
}

export function ThreadScreen({ thread }: { thread: ThreadRef }) {
  const key = threadHref(thread);
  // The route makes a new ref on every render; the screen keeps one per thread.
  const ref = useMemo(() => thread, [key]);
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const { config } = useSession();
  const user = useSignedInUser();
  const threads = useThreadsClient();
  const runner = useRunnerClient();
  const calls = useMemo(() => threadCalls(threads, config.project, ref), [threads, config.project, ref]);

  const { history, read, put, setThread } = useHistory(calls, config.project);
  const runnerRead = useRunnerSession(runner, ref);
  const session = runnerRead.kind === 'read' ? runnerRead.session : null;
  const owner = useLoopOwner(threadLoop(ref, session), runnerRead.kind === 'reading');
  const target = recordTarget(ref, session);

  const [failure, setFailure] = useState<string | null>(null);
  const [busy, setBusy] = useState<Set<string>>(new Set());
  const [recording, setRecording] = useState<Message | null>(null);
  const scroll = useRef<ScrollView>(null);

  /** Runs one action on the thread (a mark, a watch), at most once at a time, and says so if it fails. */
  const act = useCallback(
    async (what: string, action: () => Promise<void>) => {
      if (busy.has(what)) return;
      setBusy((now) => new Set(now).add(what));
      setFailure(null);
      try {
        await action();
      } catch (error) {
        setFailure(threadErrorText(error, config.project));
      } finally {
        setBusy((now) => {
          const next = new Set(now);
          next.delete(what);
          return next;
        });
      }
    },
    [busy, config.project],
  );

  const back = backTarget(ref);
  const goBack = () => (router.canGoBack() ? router.back() : router.replace(back.href));

  const shown = history.kind === 'read' ? history : null;
  const sponsor = shown?.thread.sponsor ?? session?.sponsor ?? null;
  const ownerLogin = owner.kind === 'known' ? owner.login : null;
  const watching = !!shown?.thread.watchers.some((w) => sameLogin(w.login, user.login));

  return (
    <KeyboardAvoidingView style={styles.page} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      <View style={[styles.header, { paddingTop: insets.top + space.s }]}>
        <View style={styles.headerRow}>
          <Pressable
            accessibilityRole="button"
            accessibilityLabel={`Back to ${back.label}`}
            onPress={goBack}
            hitSlop={6}
            style={styles.back}
          >
            <Text style={styles.backText}>‹ {back.label}</Text>
          </Pressable>
          {shown && (
            <SmallButton
              label={watching ? 'Watching' : 'Watch'}
              hint={watching ? 'Stops watching this thread' : 'Watches this thread'}
              selected={watching}
              disabled={busy.has('watch')}
              onPress={() =>
                void act('watch', async () => setThread(await (watching ? calls.unwatch() : calls.watch())))
              }
            />
          )}
        </View>
        <ThreadHeading thread={ref} runnerRead={runnerRead} sponsor={sponsor} owner={ownerLogin} />
        {shown && (
          <Text style={styles.members} numberOfLines={2} testID="members">
            {shown.thread.members.length === 1 ? '1 member' : `${shown.thread.members.length} members`}:{' '}
            {shown.thread.members.map((m) => m.login).join(', ')}
          </Text>
        )}
      </View>

      <ScrollView
        ref={scroll}
        testID="thread-history"
        style={styles.page}
        contentContainerStyle={styles.content}
        onContentSizeChange={() => scroll.current?.scrollToEnd?.({ animated: false })}
        refreshControl={
          <RefreshControl refreshing={!!shown?.refreshing} onRefresh={() => void read()} tintColor={colors.accent} />
        }
      >
        {history.kind === 'reading' && (
          <View style={styles.waiting} accessibilityLiveRegion="polite">
            <ActivityIndicator color={colors.accent} />
            <Text style={styles.muted}>Reading the thread…</Text>
          </View>
        )}
        {history.kind === 'failed' && (
          <>
            <Notice text={`The thread could not be read. ${history.message}`} alert />
            <SmallButton label="Try again" onPress={() => void read()} />
          </>
        )}
        {shown?.failure && <Notice text={`The thread could not be read again, so this is the earlier copy. ${shown.failure}`} alert />}
        {failure && <Notice text={failure} alert />}
        {shown && shown.messages.length === 0 && <Text style={styles.muted}>Nothing has been posted here yet.</Text>}
        {shown && (
          <Timeline
            items={timeline(shown.messages)}
            me={user.login}
            owner={owner}
            sponsor={sponsor}
            target={target}
            targetUnknown={ref.scope === 'session' ? sessionTargetWhy(runnerRead) : null}
            busy={busy}
            onMark={(message, marked) =>
              void act(`mark-${message.id}`, async () => put(await (marked ? calls.unmark(message.id) : calls.mark(message.id))))
            }
            onRecord={setRecording}
          />
        )}
      </ScrollView>

      <View style={[styles.footer, { paddingBottom: insets.bottom + space.m }]}>
        {shown && (
          <Text style={styles.watchers} testID="watchers">
            {shown.thread.watchers.length
              ? `Watching: ${shown.thread.watchers.map((w) => w.login).join(', ')}`
              : 'Nobody is watching this thread.'}
          </Text>
        )}
        {recording && target && ownerLogin ? (
          <RecordSheet
            message={recording}
            target={target}
            thread={ref}
            project={config.project}
            runner={runner}
            sponsor={user.login}
            onCancel={() => setRecording(null)}
            onStarted={(started) => {
              setRecording(null);
              router.push(sessionThreadHref(started.id));
            }}
          />
        ) : (
          <Composer
            calls={calls}
            project={config.project}
            disabled={!shown}
            placeholder={
              session && (session.state === 'running' || session.state === 'starting')
                ? 'Redirect the agent'
                : 'Write to the thread'
            }
            onPosted={put}
          />
        )}
      </View>
    </KeyboardAvoidingView>
  );
}

function sessionTargetWhy(read: RunnerRead): string | null {
  if (read.kind === 'failed') return `The runner could not say what this session runs on, so it cannot be recorded from here. ${read.message}`;
  if (read.kind === 'read' && !read.session.concern && !read.session.loop) {
    return 'This session runs on an environment, so it has no loop to record a decision into.';
  }
  return null;
}

function ThreadHeading({
  thread,
  runnerRead,
  sponsor,
  owner,
}: {
  thread: ThreadRef;
  runnerRead: RunnerRead;
  sponsor: string | null;
  owner: string | null;
}) {
  if (thread.scope !== 'session') {
    const name = thread.scope === 'concern' ? `${thread.loop}/${thread.concern}` : thread.loop;
    return (
      <View style={styles.heading}>
        <Text style={styles.overline}>
          {name}
          {owner ? ` · owner ${owner}` : ''}
        </Text>
        <Text style={styles.title} accessibilityRole="header">
          {thread.scope === 'concern' ? 'Concern thread' : 'Loop thread'}
        </Text>
      </View>
    );
  }
  const session = runnerRead.kind === 'read' ? runnerRead.session : null;
  const facts = [
    sponsor ? `sponsored by ${sponsor}` : null,
    session ? (session.state === 'ended' ? `ended${session.outcome ? `, ${session.outcome}` : ''}` : session.state) : null,
  ].filter(Boolean);
  return (
    <View style={styles.heading}>
      <View style={styles.sessionRow}>
        <View style={styles.tile} accessibilityElementsHidden importantForAccessibility="no">
          <Text style={styles.tileText}>{sessionInitials(session)}</Text>
        </View>
        <View style={styles.grow}>
          <Text style={styles.sessionTitle} accessibilityRole="header" testID="session-title">
            {sessionTitle(thread.session, session)}
          </Text>
          {facts.length > 0 && <Text style={styles.muted}>{facts.join(' · ')}</Text>}
        </View>
      </View>
      {runnerRead.kind === 'failed' && <Text style={styles.muted}>The runner could not say more about this session. {runnerRead.message}</Text>}
      {session?.spend && <Spend session={session} spent={session.spend.usd} />}
    </View>
  );
}

/** What the session has spent against its budget. Every figure is the runner's estimate (command-center/D23). */
function Spend({ session, spent }: { session: Session; spent: number }) {
  const share = session.budget_usd > 0 ? Math.min(1, spent / session.budget_usd) : 0;
  return (
    <View style={styles.spend} testID="spend">
      <View style={styles.between}>
        <Text style={styles.spendText}>{dollars(spent)} spent, an estimate</Text>
        <Text style={[styles.spendText, { color: colors.inkMuted }]}>budget {dollars(session.budget_usd)}</Text>
      </View>
      <View style={styles.bar} accessibilityElementsHidden importantForAccessibility="no">
        <View style={[styles.barFill, { width: `${Math.round(share * 100)}%` }]} />
      </View>
    </View>
  );
}

function Timeline({
  items,
  me,
  owner,
  sponsor,
  target,
  targetUnknown,
  busy,
  onMark,
  onRecord,
}: {
  items: TimelineItem[];
  me: string;
  owner: OwnerRead;
  sponsor: string | null;
  target: RecordTarget | null;
  targetUnknown: string | null;
  busy: Set<string>;
  onMark: (message: Message, marked: boolean) => void;
  onRecord: (message: Message) => void;
}) {
  const [open, setOpen] = useState<Set<string>>(new Set());
  const toggle = (key: string) =>
    setOpen((now) => {
      const next = new Set(now);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  const ownerLogin = owner.kind === 'known' ? owner.login : null;
  return (
    <>
      {items.map((item) => {
        if (item.type === 'day') {
          return (
            <Text key={item.key} style={styles.day}>
              {item.day} · UTC
            </Text>
          );
        }
        if (item.type === 'narration') {
          const n = item.messages.length;
          const shown = open.has(item.key);
          return (
            <View key={item.key} style={styles.narration} testID={item.key}>
              {shown &&
                item.messages.map((m) => (
                  <Line key={m.id} at={m.created_at} testID={`message-${m.id}`}>
                    <Text style={styles.narrationText}>{m.body}</Text>
                  </Line>
                ))}
              <Pressable
                accessibilityRole="button"
                accessibilityState={{ expanded: shown }}
                onPress={() => toggle(item.key)}
                style={styles.narrationButton}
              >
                <Text style={styles.narrationButtonText}>
                  {shown ? 'Hide narration' : `Show ${n} narration ${n === 1 ? 'line' : 'lines'}`}
                </Text>
              </Pressable>
            </View>
          );
        }
        const { message } = item;
        if (message.kind === 'milestone') {
          return (
            <Line key={item.key} at={message.created_at} testID={`message-${message.id}`}>
              <Text style={styles.milestone}>{message.body}</Text>
            </Line>
          );
        }
        return (
          <Bubble key={item.key} message={message} details={authorDetail(message, { owner: ownerLogin, sponsor })}>
            {markable(message) && (
              <Marks
                message={message}
                me={me}
                owner={owner}
                target={target}
                targetUnknown={targetUnknown}
                busy={busy.has(`mark-${message.id}`)}
                onMark={onMark}
                onRecord={onRecord}
              />
            )}
          </Bubble>
        );
      })}
    </>
  );
}

/** A milestone or a narration line, as the artboard draws them: its time, then what happened. */
function Line({ at, children, testID }: { at: string; children: ReactNode; testID?: string }) {
  return (
    <View style={styles.line} testID={testID}>
      <Text style={styles.time}>{timeOf(at)}</Text>
      <View style={styles.grow}>{children}</View>
    </View>
  );
}

function Bubble({ message, details, children }: { message: Message; details: string[]; children?: ReactNode }) {
  const name = authorName(message);
  const fromSession = message.author.type === 'session';
  return (
    <View style={styles.bubbleRow} testID={`message-${message.id}`}>
      <View
        style={[styles.avatar, fromSession && styles.avatarSession]}
        accessibilityElementsHidden
        importantForAccessibility="no"
      >
        <Text style={styles.avatarText}>{fromSession ? 'S' : name.slice(0, 1).toUpperCase()}</Text>
      </View>
      <View style={[styles.bubble, message.author.type === 'github' && styles.bubbleMirrored]}>
        <Text style={styles.author}>
          {name}
          <Text style={styles.authorDetail}> · {[...details, timeOf(message.created_at)].join(' · ')}</Text>
        </Text>
        <Text style={styles.body}>{message.body}</Text>
        {children}
      </View>
    </View>
  );
}

/**
 * A message's "record this?" marks, and what the signed-in person can do with them: mark it or take back their own
 * mark, and, for the loop's owner only, accept a marked message for the record (command-center/D10, D36).
 */
function Marks({
  message,
  me,
  owner,
  target,
  targetUnknown,
  busy,
  onMark,
  onRecord,
}: {
  message: Message;
  me: string;
  owner: OwnerRead;
  target: RecordTarget | null;
  targetUnknown: string | null;
  busy: boolean;
  onMark: (message: Message, marked: boolean) => void;
  onRecord: (message: Message) => void;
}) {
  const by = message.record_marks.map((m) => m.login);
  const mine = by.some((login) => sameLogin(login, me));
  const isOwner = owner.kind === 'known' && sameLogin(owner.login, me);
  let accept: ReactNode = null;
  if (by.length > 0) {
    if (!target) accept = targetUnknown ? <Text style={styles.markNote}>{targetUnknown}</Text> : null;
    else if (owner.kind === 'reading') accept = null;
    else if (owner.kind === 'unknown') accept = <Text style={styles.markNote}>Only the loop's owner can record it. {owner.why}</Text>;
    else if (isOwner) {
      accept = <SmallButton label="Record it…" hint={`Starts /loop-design on ${targetName(target)}, after you confirm`} onPress={() => onRecord(message)} primary />;
    } else accept = <Text style={styles.markNote}>{owner.login} records it, as the loop's owner.</Text>;
  }
  return (
    <View style={styles.marks}>
      {by.length > 0 && <Text style={styles.markedBy}>Record this? · marked by {by.join(', ')}</Text>}
      <View style={styles.markActions}>
        <SmallButton
          label={mine ? 'Unmark' : 'Record this?'}
          hint={mine ? 'Takes back your "record this?" mark' : 'Marks this message for the loop\'s owner to record'}
          disabled={busy}
          onPress={() => onMark(message, mine)}
        />
        {accept}
      </View>
    </View>
  );
}

function Composer({
  calls,
  project,
  disabled,
  placeholder,
  onPosted,
}: {
  calls: ThreadCalls;
  project: string;
  disabled: boolean;
  placeholder: string;
  onPosted: (message: Message) => void;
}) {
  const [draft, setDraft] = useState('');
  const [posting, setPosting] = useState(false);
  const [failure, setFailure] = useState<string | null>(null);
  const body = draft.trim();
  const canSend = !disabled && !posting && body.length > 0;

  const send = async () => {
    if (!canSend) return;
    setPosting(true);
    setFailure(null);
    try {
      // A person posts only messages, as themselves: no kind, no sponsor (threads D4).
      onPosted(await calls.post({ body }));
      setDraft('');
    } catch (error) {
      setFailure(`It was not posted. ${threadErrorText(error, project)}`);
    } finally {
      setPosting(false);
    }
  };

  return (
    <View style={styles.composerWrap}>
      {failure && <Notice text={failure} alert />}
      <View style={styles.composer}>
        <TextInput
          accessibilityLabel="Message the thread"
          placeholder={placeholder}
          placeholderTextColor={colors.inkSubtle}
          value={draft}
          onChangeText={setDraft}
          editable={!disabled && !posting}
          multiline
          maxLength={MAX_BODY}
          style={styles.input}
        />
        <Pressable
          accessibilityRole="button"
          accessibilityLabel="Send"
          accessibilityState={{ disabled: !canSend }}
          disabled={!canSend}
          onPress={() => void send()}
          style={[styles.send, !canSend && styles.sendDisabled]}
        >
          {posting ? (
            <ActivityIndicator color={colors.onAccent} />
          ) : (
            <Svg width={20} height={20} viewBox="0 0 24 24" accessibilityElementsHidden importantForAccessibility="no">
              <Path d="M5 12h14" stroke={colors.onAccent} strokeWidth={2} strokeLinecap="round" fill="none" />
              <Path d="M13 6l6 6-6 6" stroke={colors.onAccent} strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" fill="none" />
            </Svg>
          )}
        </Pressable>
      </View>
    </View>
  );
}

type EstimateRead = { kind: 'reading' } | { kind: 'read'; answer: EstimateAnswer } | { kind: 'failed'; message: string };

/**
 * Accepting a mark (C2): what will run, as whom, with what budget and which release of the skills, before anything
 * starts. Start dispatches /loop-design through the runner with the signed-in person as its sponsor, and opens the
 * new session's thread, where the skill asks them to confirm the decision before it writes the D#.
 */
function RecordSheet({
  message,
  target,
  thread,
  project,
  runner,
  sponsor,
  onCancel,
  onStarted,
}: {
  message: Message;
  target: RecordTarget;
  thread: ThreadRef;
  project: ProjectKey;
  runner: RunnerClient;
  sponsor: string;
  onCancel: () => void;
  onStarted: (session: Session) => void;
}) {
  const [budget, setBudget] = useState(String(DEFAULT_BUDGET_USD));
  const [release, setRelease] = useState(SKILLS_RELEASE);
  const [estimate, setEstimate] = useState<EstimateRead>({ kind: 'reading' });
  const [starting, setStarting] = useState(false);
  const [failure, setFailure] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    runner.estimate({ query: { skill: 'loop-design' } }).then(
      (answer) => live && setEstimate({ kind: 'read', answer }),
      (error) => live && setEstimate({ kind: 'failed', message: messageOf(error) }),
    );
    return () => {
      live = false;
    };
  }, [runner]);

  const usd = parseBudget(budget);
  const releaseOk = validRelease(release);
  const canStart = usd !== null && releaseOk && !starting;

  const start = async () => {
    if (!canStart) return;
    setStarting(true);
    setFailure(null);
    try {
      const session = await runner.dispatch({
        body: recordDispatch({ project, target, ref: thread, message, budgetUsd: usd, release }),
      });
      onStarted(session);
    } catch (error) {
      setFailure(dispatchErrorText(error));
      setStarting(false);
    }
  };

  return (
    <View style={styles.sheet} testID="record-sheet">
      <Text style={styles.sheetLabel} accessibilityRole="header">
        Record this decision
      </Text>
      <Text style={styles.quote} numberOfLines={3}>
        “{message.body}”
      </Text>
      <Text style={styles.body}>
        Starts <Text style={styles.code}>/loop-design {targetName(target)}</Text> as a session you sponsor ({sponsor}). It
        asks you to confirm the decision in its own thread before it writes the D#.
      </Text>
      <View style={styles.field}>
        <Text style={styles.fieldLabel}>Budget, $</Text>
        <TextInput
          accessibilityLabel="Budget in dollars"
          value={budget}
          onChangeText={setBudget}
          keyboardType="decimal-pad"
          editable={!starting}
          style={styles.fieldInput}
        />
      </View>
      <Text style={styles.muted} testID="estimate">
        {estimateText(estimate)}
      </Text>
      <View style={styles.field}>
        <Text style={styles.fieldLabel}>Skills release</Text>
        <TextInput
          accessibilityLabel="Skills release"
          value={release}
          onChangeText={setRelease}
          autoCapitalize="none"
          autoCorrect={false}
          editable={!starting}
          style={styles.fieldInput}
        />
      </View>
      {usd === null && <Notice text="The budget must be a number of dollars above 0." alert />}
      {!releaseOk && <Notice text="The release is a tag of the skills, such as v0.4.0." alert />}
      {failure && <Notice text={failure} alert />}
      <View style={styles.sheetActions}>
        <SmallButton label={starting ? 'Starting…' : 'Start /loop-design'} onPress={() => void start()} disabled={!canStart} primary />
        <SmallButton label="Cancel" onPress={onCancel} disabled={starting} />
      </View>
    </View>
  );
}

function estimateText(estimate: EstimateRead): string {
  if (estimate.kind === 'reading') return 'Asking the runner for an estimate…';
  if (estimate.kind === 'failed') return `The runner gave no estimate. ${estimate.message}`;
  const { answer } = estimate;
  if (!answer.estimate) return `No estimate yet: no ${answer.skill} session on ${answer.model} has been measured.`;
  const { usd, sessions } = answer.estimate;
  return `Estimate: about ${dollars(usd)}, the median of ${answer.skill}'s last ${sessions === 1 ? 'session' : `${sessions} sessions`} on ${answer.model}.`;
}

function Notice({ text, alert = false }: { text: string; alert?: boolean }) {
  return (
    <Text style={[styles.notice, alert && styles.alert]} accessibilityRole={alert ? 'alert' : 'text'}>
      {text}
    </Text>
  );
}

function SmallButton({
  label,
  hint,
  onPress,
  disabled = false,
  primary = false,
  selected,
}: {
  label: string;
  hint?: string;
  onPress: () => void;
  disabled?: boolean;
  primary?: boolean;
  selected?: boolean;
}) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityHint={hint}
      accessibilityState={{ disabled, ...(selected === undefined ? {} : { selected }) }}
      disabled={disabled}
      onPress={onPress}
      hitSlop={4}
      style={({ pressed }) => [
        styles.small,
        primary && styles.smallPrimary,
        selected && styles.smallSelected,
        pressed && { opacity: 0.8 },
        disabled && styles.smallDisabled,
      ]}
    >
      <Text style={[styles.smallLabel, primary && { color: colors.onAccent }]}>{label}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  page: { flex: 1, backgroundColor: colors.ground },
  header: {
    backgroundColor: colors.surface,
    borderBottomWidth: 1,
    borderBottomColor: colors.divider,
    paddingHorizontal: space.m,
    paddingBottom: space.m,
    gap: space.s,
  },
  headerRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: space.m },
  back: { minHeight: touchTarget, justifyContent: 'center', paddingHorizontal: space.s },
  backText: { ...type.body, fontFamily: fonts.sansMedium, color: colors.accent },
  heading: { gap: space.xs, paddingHorizontal: space.s },
  overline: { ...type.overline, color: colors.inkSubtle, textTransform: 'uppercase' },
  title: { ...type.title, color: colors.ink },
  sessionRow: { flexDirection: 'row', alignItems: 'center', gap: space.m },
  tile: { width: 40, height: 40, borderRadius: 9, backgroundColor: colors.ink, alignItems: 'center', justifyContent: 'center' },
  tileText: { ...type.mono, fontFamily: fonts.monoSemiBold, color: colors.onInk },
  sessionTitle: { ...type.heading, color: colors.ink },
  spend: { gap: space.xs, paddingTop: space.xs },
  spendText: { ...type.mono, fontFamily: fonts.monoMedium, color: colors.ink },
  bar: { height: 6, borderRadius: 3, backgroundColor: colors.border, overflow: 'hidden' },
  barFill: { height: 6, backgroundColor: colors.accent },
  members: { ...type.caption, color: colors.inkMuted, paddingHorizontal: space.s },
  content: { paddingHorizontal: space.l, paddingVertical: space.l, gap: space.m },
  waiting: { flexDirection: 'row', alignItems: 'center', gap: space.s, paddingVertical: space.l },
  muted: { ...type.bodySmall, color: colors.inkMuted },
  notice: { ...type.body, color: colors.inkMuted, paddingVertical: space.xs },
  alert: { color: verdict.CONTRADICTS.fg },
  day: { ...type.mono, color: colors.inkSubtle, alignSelf: 'center', paddingVertical: space.xs },
  line: { flexDirection: 'row', gap: space.s, alignItems: 'baseline', paddingLeft: space.xs },
  time: { ...type.mono, fontSize: 11, color: colors.inkMuted, width: 40, flexShrink: 0 },
  milestone: { ...type.body, color: colors.ink },
  narration: { gap: space.s },
  narrationText: { ...type.bodySmall, color: colors.inkMuted },
  narrationButton: {
    alignSelf: 'flex-start',
    marginLeft: 52,
    minHeight: 32,
    paddingHorizontal: space.s,
    borderRadius: radius.chip,
    backgroundColor: colors.inset,
    justifyContent: 'center',
  },
  narrationButtonText: { ...type.caption, fontFamily: fonts.sansMedium, color: colors.inkSecondary },
  bubbleRow: { flexDirection: 'row', gap: space.s, alignItems: 'flex-start' },
  avatar: { width: 28, height: 28, borderRadius: 14, backgroundColor: colors.accent, alignItems: 'center', justifyContent: 'center' },
  avatarSession: { borderRadius: 7, backgroundColor: colors.ink },
  avatarText: { ...type.caption, fontFamily: fonts.sansSemiBold, color: colors.onAccent },
  bubble: {
    flex: 1,
    gap: space.xs,
    paddingVertical: space.s,
    paddingHorizontal: space.m,
    borderRadius: radius.button,
    borderTopLeftRadius: 4,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
  },
  bubbleMirrored: { backgroundColor: colors.inset },
  author: { ...type.caption, fontFamily: fonts.sansSemiBold, color: colors.ink },
  authorDetail: { fontFamily: fonts.sans, color: colors.inkMuted },
  body: { ...type.body, color: colors.ink },
  marks: { gap: space.xs, paddingTop: space.xs },
  markedBy: { ...type.caption, fontFamily: fonts.sansMedium, color: colors.accent },
  markActions: { flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', gap: space.s },
  markNote: { ...type.caption, color: colors.inkMuted, flexShrink: 1 },
  footer: {
    backgroundColor: colors.surface,
    borderTopWidth: 1,
    borderTopColor: colors.divider,
    paddingHorizontal: space.l,
    paddingTop: space.s,
    gap: space.s,
  },
  watchers: { ...type.caption, color: colors.inkMuted },
  composerWrap: { gap: space.xs },
  composer: { flexDirection: 'row', alignItems: 'flex-end', gap: space.s },
  input: {
    flex: 1,
    minHeight: 46,
    maxHeight: 140,
    paddingHorizontal: space.m,
    paddingVertical: space.m,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: colors.borderStrong,
    backgroundColor: colors.inset,
    ...type.body,
    color: colors.ink,
  },
  send: { width: 46, height: 46, borderRadius: 12, backgroundColor: colors.accent, alignItems: 'center', justifyContent: 'center' },
  sendDisabled: { opacity: 0.4 },
  sheet: { gap: space.s, paddingVertical: space.xs },
  sheetLabel: { ...type.label, color: colors.accent, textTransform: 'uppercase' },
  quote: { ...type.bodySmall, color: colors.inkSecondary, backgroundColor: colors.inset, borderRadius: radius.chip, padding: space.s },
  code: { fontFamily: fonts.mono, fontSize: 13 },
  field: { flexDirection: 'row', alignItems: 'center', gap: space.m },
  fieldLabel: { ...type.bodySmall, color: colors.inkMuted, width: 104 },
  fieldInput: {
    flex: 1,
    minHeight: touchTarget,
    paddingHorizontal: space.m,
    borderRadius: radius.button,
    borderWidth: 1,
    borderColor: colors.borderStrong,
    ...type.mono,
    fontSize: 14,
    color: colors.ink,
  },
  sheetActions: { flexDirection: 'row', gap: space.s, paddingTop: space.xs },
  small: {
    minHeight: 32,
    paddingHorizontal: space.m,
    borderRadius: radius.button,
    borderWidth: 1,
    borderColor: colors.borderStrong,
    backgroundColor: colors.surface,
    alignItems: 'center',
    justifyContent: 'center',
  },
  smallPrimary: { backgroundColor: colors.accent, borderColor: colors.accent, minHeight: touchTarget },
  smallSelected: { borderColor: colors.accent, backgroundColor: colors.accentSoft },
  smallDisabled: { opacity: 0.5 },
  smallLabel: { ...type.button, fontSize: 13, color: colors.inkSecondary },
  grow: { flex: 1 },
  between: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'baseline', gap: space.s },
});
