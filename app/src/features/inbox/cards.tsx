// One card's body, by kind, after the Question and Review artboards (command-center/D4). Each body shows the item's
// facts as the status document carries them; a body the person can act on also offers its one start, through the
// start sheet, and follows the session that start makes (C2).
//
// - Question: its options with their consequences and the recommendation, none pre-selected, and its default. The
//   artboard's option picker and Record button become "Answer in a session": /loop-design asks the question in the
//   session's thread and the person answers there, so the decision is theirs (D3). A gated question asks for a
//   typed reason first (D4).
// - Review: the evidence first, then the pull request, which opens on GitHub: the app never merges (LOOP.md §2).
// - Ship: the manual steps, then the brief, which is a /loop-ship session's final report (D1), then "Deployed" on
//   the item that crosses deploy (command-center/D59).
// - Record: the proposed text and where it goes; approving starts the record step, which merges its own PR (D2).
// - Proof, contradiction, refused PR: their facts and the command to run, read-only (command-center/D34, D40).

import { useRouter } from 'expo-router';
import { useMemo, useState, type ReactNode } from 'react';
import { Linking, Text, TextInput, View } from 'react-native';

import type { Session } from '../../api/runner.gen';
import type { QueueItem, StatusDocument } from '../../api/status';
import { colors } from '../../theme';
import {
  answerPlan,
  briefPlan,
  deployedPlan,
  isDeployItem,
  REASON_MAX,
  recordPlan,
  targetName,
  type SessionPlan,
} from './dispatch';
import { useInbox } from './InboxStatus';
import { sameLogin, sessionThreadHref, shortSha, type InboxEntry } from './queue';
import { sessionSummary, useLatestSession, type Watch } from './sessions';
import { NO_RUNNER_MESSAGE, StartSheet } from './StartSheet';
import { Button, Card, Chip, Command, Fact, Notice, SectionLabel, styles } from './ui';

type Item<K extends QueueItem['kind']> = Extract<QueueItem, { kind?: K }> & { kind: K };

/** The body for an item, by its kind. */
export function ItemBody({ entry, doc }: { entry: InboxEntry; doc: StatusDocument }) {
  const { item } = entry;
  switch (item.kind) {
    case 'question':
      return <QuestionBody entry={entry} item={item as Item<'question'>} />;
    case 'review':
      return <ReviewBody item={item as Item<'review'>} />;
    case 'ship':
      return <ShipBody entry={entry} item={item as Item<'ship'>} doc={doc} />;
    case 'record':
      return <RecordBody entry={entry} item={item as Item<'record'>} />;
    case 'proof':
      return <ProofBody item={item as Item<'proof'>} />;
    case 'contradiction':
      return <ContradictionBody item={item as Item<'contradiction'>} />;
    case 'refused_pr':
      return <RefusedPrBody item={item as Item<'refused_pr'>} />;
  }
}

/** Who can finish an item, when it is not the person: whom it waits on, and why the person sees it at all. */
export function WhoNotice({ entry }: { entry: InboxEntry }) {
  const { login } = useInbox();
  const { item, waitsOn } = entry;
  if (entry.actionable) return null;
  if (waitsOn === null) {
    return (
      <Notice text="It waits on no one named, so no one can finish it here yet. The board's drift says why no one is named." />
    );
  }
  if (sameLogin(waitsOn, login)) {
    return <Notice text="It is yours, and read-only here: run its command from a terminal." />;
  }
  return (
    <Notice
      text={`Waits on @${waitsOn}. You see it as a member of ${item.loop ?? 'its loop'}; only @${waitsOn} can finish it.`}
    />
  );
}

function Title({ children }: { children: ReactNode }) {
  return (
    <Text style={styles.screenTitle} accessibilityRole="header">
      {children}
    </Text>
  );
}

/** A session the card follows: its state, sponsor, budget and spend, and what it said when it ended. */
function SessionStatus({
  watch,
  none,
  message,
  children,
  testID,
}: {
  watch: Watch;
  /** What to say when no session has done this work. */
  none: string;
  /** The heading of the session's final message, such as "The brief". */
  message: string;
  children?: (session: Session) => ReactNode;
  testID: string;
}) {
  switch (watch.kind) {
    case 'no-runner':
      return null;
    case 'looking':
      return <Text style={styles.bodyMuted}>Asking the runner for its sessions…</Text>;
    case 'none':
      return (
        <Text style={styles.bodyMuted} testID={`${testID}-none`}>
          {none}
        </Text>
      );
    case 'failed':
      return <Notice text={`The runner's sessions could not be read. ${watch.message}`} alert />;
    case 'session': {
      const { session, failure } = watch;
      return (
        <View style={styles.tight} testID={testID}>
          <Text style={styles.monoMuted} testID={`${testID}-summary`}>
            {sessionSummary(session)}
          </Text>
          {failure && <Notice text={`It could not be read again just now. ${failure}`} alert />}
          {session.state === 'ended' &&
            (session.final_message ? (
              <View style={styles.inset}>
                <Text style={styles.insetLabel}>{message}</Text>
                <Text style={styles.prose} selectable testID={`${testID}-message`}>
                  {session.final_message}
                </Text>
              </View>
            ) : (
              <Text style={styles.bodyMuted}>It ended without saying anything.</Text>
            ))}
          {session.pull_requests.map((pr) => (
            <Button
              key={pr.number}
              label={`Open PR #${pr.number} on GitHub`}
              kind="secondary"
              onPress={() => void Linking.openURL(pr.url)}
            />
          ))}
          {children?.(session)}
        </View>
      );
    }
  }
}

/** A card's one start: the button, and the start sheet once it is pressed. */
function Start({
  label,
  plan,
  intro,
  disabled = false,
  onStarted,
}: {
  label: string;
  plan: SessionPlan | null;
  intro: string;
  disabled?: boolean;
  onStarted: (session: Session) => void;
}) {
  const { runner } = useInbox();
  const [open, setOpen] = useState(false);
  if (!runner) return <Notice text={NO_RUNNER_MESSAGE} />;
  if (open && plan) {
    return (
      <StartSheet
        plan={plan}
        intro={intro}
        onCancel={() => setOpen(false)}
        onStarted={(session) => {
          setOpen(false);
          onStarted(session);
        }}
      />
    );
  }
  return <Button label={label} onPress={() => setOpen(true)} disabled={disabled || !plan} />;
}

// Question (D3, D4).

function QuestionBody({ entry, item }: { entry: InboxEntry; item: Item<'question'> }) {
  const router = useRouter();
  const { runner, project } = useInbox();
  const { detail } = item;
  const [reason, setReason] = useState('');
  // The session that answers this question, found by the question it names whatever reason it carried.
  const lookup = useMemo(() => answerPlan({ ...item, gate: null }), [item]);
  const { watch, adopt } = useLatestSession(entry.actionable ? runner : null, project, lookup);
  const plan = useMemo(() => {
    try {
      return answerPlan(item, reason);
    } catch {
      return null; // a gated question with no reason yet
    }
  }, [item, reason]);
  const openThread = (session: Session) => router.push(sessionThreadHref(session.id));

  return (
    <>
      <View style={styles.tight}>
        <SectionLabel text={entry.actionable ? 'Question for you' : 'Question'} />
        <Title>{detail.question}</Title>
      </View>
      <Text style={styles.body}>{item.why}</Text>
      <View style={styles.chips}>
        <Text style={styles.bodyMuted}>Blocks</Text>
        {detail.blocks.length > 0 ? (
          detail.blocks.map((claim) => <Chip key={claim} text={claim} />)
        ) : (
          <Text style={styles.bodyMuted}>nothing yet</Text>
        )}
        {item.gate && <Chip text={`gate: ${item.gate}`} tone="accent" />}
      </View>

      <View style={styles.group} accessibilityLabel="Options" testID="options">
        {detail.options.length === 0 ? (
          <Text style={styles.bodyMuted}>
            It was written before options were recorded, so it shows only what it blocks and its default.
          </Text>
        ) : (
          detail.options.map((option, index) => {
            const recommended = detail.recommendation === option.text;
            return (
              <View
                key={option.text}
                testID={`option-${index}`}
                accessible
                accessibilityLabel={`${option.text}${recommended ? ', recommended' : ''}. ${option.consequence}`}
                accessibilityState={{ selected: false }}
                style={[styles.card, styles.tight]}
              >
                <View style={styles.chips}>
                  <Text style={styles.label}>{option.text}</Text>
                  {recommended && <Chip text="RECOMMENDED" tone="accent" />}
                </View>
                <Text style={styles.bodyMuted}>{option.consequence}</Text>
              </View>
            );
          })
        )}
        {detail.options.length > 0 && (
          <Text style={styles.note}>
            Nothing is pre-selected: the answer is yours. You give it in the session's thread, where /loop-design asks
            the question.
          </Text>
        )}
        <Text style={styles.bodyMuted} testID="default">
          {detail.default ? `Default if unanswered: ${detail.default}` : 'No default if unanswered.'}
        </Text>
      </View>

      {entry.actionable && (
        <View style={styles.group}>
          {item.gate && (
            <View style={styles.tight}>
              <Text style={styles.label}>{`Reason (needed: the answer crosses the ${item.gate} gate)`}</Text>
              <TextInput
                accessibilityLabel="Reason"
                value={reason}
                onChangeText={setReason}
                maxLength={REASON_MAX}
                multiline
                placeholder="Why, in a line. It goes in the decision's notes."
                placeholderTextColor={colors.inkSubtle}
                style={styles.input}
              />
            </View>
          )}
          <SessionStatus
            watch={watch}
            none="No session has been asked this question yet."
            message="What the session said last"
            testID="answer-session"
          >
            {(session) => (
              <Button label="Open its thread" kind="secondary" onPress={() => openThread(session)} />
            )}
          </SessionStatus>
          <Start
            label="Answer in a session"
            plan={plan}
            disabled={plan === null}
            intro={`It starts /loop-design on ${targetName(lookup.target)}, which asks ${lookup.arguments} in the session's thread, where you answer.`}
            onStarted={(session) => {
              adopt(session);
              openThread(session);
            }}
          />
        </View>
      )}
    </>
  );
}

// Review.

function ReviewBody({ item }: { item: Item<'review'> }) {
  const { pr, proof } = item.detail;
  return (
    <>
      <View style={styles.tight}>
        <SectionLabel text="Review" />
        <Title>{pr.title}</Title>
        <Text style={styles.monoMuted}>
          {`PR #${pr.number} · ${pr.head} → ${pr.base}${pr.draft ? ' · draft' : ''}`}
        </Text>
      </View>
      <Card testID="evidence">
        <View style={styles.between}>
          <SectionLabel text="1 · Evidence" />
          <Text style={styles.bodyMuted}>read before the code</Text>
        </View>
        {proof ? (
          <Text style={styles.prose} selectable testID="evidence-text">
            {proof}
          </Text>
        ) : (
          <Text style={styles.bodyMuted}>Its body has no "How it was proven" section, so there is no evidence to read first.</Text>
        )}
      </Card>
      <Card testID="diff">
        <SectionLabel text="2 · The diff" />
        <View style={styles.chips}>
          <Chip text={`checks ${pr.checks}`} tone={pr.checks === 'success' ? 'holds' : pr.checks === 'failure' ? 'contradicts' : 'unproven'} />
        </View>
        <Text style={styles.bodyMuted}>
          The diff and the merge stay on GitHub: the app never merges.
        </Text>
        <Button label={`Open PR #${pr.number} on GitHub`} kind="secondary" onPress={() => void Linking.openURL(pr.url)} />
      </Card>
    </>
  );
}

// Ship (D1, command-center/D59).

function ShipBody({ entry, item, doc }: { entry: InboxEntry; item: Item<'ship'>; doc: StatusDocument }) {
  const { runner, project } = useInbox();
  const { environment, manual_steps: steps } = item.detail;
  const deploy = isDeployItem(item);
  const live = entry.actionable ? runner : null;
  const brief = useMemo(() => briefPlan(item), [item]);
  const deployed = useMemo(() => deployedPlan(item), [item]);
  const briefWatch = useLatestSession(live, project, brief);
  const verifyWatch = useLatestSession(live && deploy ? live : null, project, deploy ? deployed : null);
  const haveBrief =
    briefWatch.watch.kind === 'session' &&
    briefWatch.watch.session.state === 'ended' &&
    Boolean(briefWatch.watch.session.final_message);
  const deployItem = deploy
    ? undefined
    : doc.queue.find((other) => other.id !== item.id && other.kind === 'ship' && other.detail.environment === environment && isDeployItem(other));

  return (
    <>
      <View style={styles.tight}>
        <SectionLabel text={`Ship to ${environment}`} />
        <Title>{item.title}</Title>
      </View>
      <Text style={styles.body}>{item.why}</Text>
      <View style={styles.chips}>
        <Chip text={environment} />
        <Chip text={`gate: ${item.gate ?? 'none named yet'}`} tone="accent" />
      </View>

      <Card testID="manual-steps">
        <SectionLabel text="Manual steps" />
        {steps.length > 0 ? (
          steps.map((step, index) => (
            <Text key={step} style={styles.body}>
              {`${index + 1}. ${step}`}
            </Text>
          ))
        ) : (
          <Text style={styles.bodyMuted}>Its concerns declare none.</Text>
        )}
        <Text style={styles.bodyMuted}>
          {`The app performs none of them: ${entry.waitsOn ? `@${entry.waitsOn}` : 'the gate’s holder'} does, as LOOP.md says.`}
        </Text>
      </Card>

      <Card testID="brief">
        <SectionLabel text="The brief" />
        <SessionStatus
          watch={briefWatch.watch}
          none={`No brief yet. Preparing one starts /loop-ship ${environment}, whose final report is the brief.`}
          message="The brief"
          testID="brief-session"
        />
        {entry.actionable && (
          <Start
            label={briefWatch.watch.kind === 'session' ? 'Prepare a new brief' : 'Prepare the brief'}
            plan={brief}
            intro={`It starts /loop-ship ${environment}, which finds what goes out and writes the brief. It deploys nothing.`}
            onStarted={briefWatch.adopt}
          />
        )}
      </Card>

      {deploy ? (
        <Card testID="deployed">
          <SectionLabel text="Deployed" />
          <Text style={styles.bodyMuted}>
            {`Deploy it yourself, as LOOP.md says. Then "Deployed" starts /loop-ship ${environment} deployed, which reads what ${environment} serves and checks it against the brief.`}
          </Text>
          <SessionStatus
            watch={verifyWatch.watch}
            none="Not verified yet."
            message="The verification"
            testID="verify-session"
          />
          {entry.actionable && (
            <Start
              label="Deployed"
              plan={deployed}
              disabled={!haveBrief}
              intro={`It starts /loop-ship ${environment} deployed, which verifies the deploy read-only and records a ship line.`}
              onStarted={verifyWatch.adopt}
            />
          )}
          {entry.actionable && !haveBrief && <Text style={styles.bodyMuted}>Read the brief before you deploy.</Text>}
        </Card>
      ) : (
        <Text style={styles.bodyMuted} testID="deploy-elsewhere">
          {deployItem
            ? `The deploy itself is its own card, waiting on ${deployItem.waits_on ? `@${deployItem.waits_on}` : 'no one named'}.`
            : 'The deploy itself is its own card.'}
        </Text>
      )}
    </>
  );
}

// Record (D2).

function RecordBody({ entry, item }: { entry: InboxEntry; item: Item<'record'> }) {
  const { runner, project } = useInbox();
  const plan = useMemo(() => recordPlan(item), [item]);
  const { watch, adopt } = useLatestSession(entry.actionable ? runner : null, project, plan);
  const loop = 'loop' in plan.target ? plan.target.loop : '';
  return (
    <>
      <View style={styles.tight}>
        <SectionLabel text="Record" />
        <Title>{item.title}</Title>
      </View>
      <Text style={styles.body}>{item.why}</Text>
      <Fact label="Goes in" mono>
        {item.detail.path}
      </Fact>
      <Card testID="proposed-text">
        <SectionLabel text="The proposed text" />
        <Text style={styles.prose} selectable>
          {item.detail.text}
        </Text>
      </Card>
      <Text style={styles.note}>
        {`Approving starts /loop-status ${loop}'s record step. It writes this text in a loop-document PR and merges that PR itself, as LOOP.md §2.1 lets it, so you approve the text, not the PR's exact diff.`}
      </Text>
      {entry.actionable && (
        <>
          <SessionStatus watch={watch} none="Not approved yet." message="What the record step said" testID="record-session" />
          <Start
            label="Approve and record"
            plan={plan}
            intro={`It starts /loop-status ${loop}, telling its record step you said yes to this text.`}
            onStarted={adopt}
          />
        </>
      )}
    </>
  );
}

// The read-only kinds (command-center/D34, D40).

function ProofBody({ item }: { item: Item<'proof'> }) {
  const { detail } = item;
  return (
    <>
      <View style={styles.tight}>
        <SectionLabel text="Proof" quiet />
        <Title>{item.title}</Title>
      </View>
      <Text style={styles.body}>{item.why}</Text>
      <Card>
        <Fact label="Claim" mono>
          {detail.claim}
        </Fact>
        <Fact label="On">{detail.environment}</Fact>
        <Fact label="Needs">{detail.missing}</Fact>
        <Fact label="From">{detail.supplied_by}</Fact>
      </Card>
      <Command command={detail.command} />
    </>
  );
}

function ContradictionBody({ item }: { item: Item<'contradiction'> }) {
  const { detail } = item;
  const line = detail.evidence;
  return (
    <>
      <View style={styles.tight}>
        <SectionLabel text="Contradiction" quiet />
        <Title>{item.title}</Title>
      </View>
      <Text style={styles.body}>{item.why}</Text>
      <Card>
        <Fact label="Claim" mono>
          {detail.claim}
        </Fact>
        <Fact label="Evidence" mono>
          {`${line.date} · ${line.verdict} · rung ${line.rung} · ${line.environment} @${shortSha(line.commit)} · ${line.text}`}
        </Fact>
        <Fact label="Contradicts">{detail.contradicts}</Fact>
        <Fact label="Escalates">{detail.escalates ? 'yes, to the loop, as a question' : 'no'}</Fact>
      </Card>
      <Command command={detail.command} />
    </>
  );
}

function RefusedPrBody({ item }: { item: Item<'refused_pr'> }) {
  const { pr, failures, command } = item.detail;
  return (
    <>
      <View style={styles.tight}>
        <SectionLabel text="Refused PR" quiet />
        <Title>{item.title}</Title>
      </View>
      <Text style={styles.body}>{item.why}</Text>
      <Card>
        <Fact label="PR" mono>
          {`#${pr.number} · ${pr.head}`}
        </Fact>
        {failures.map((failure) => (
          <Text key={failure} style={styles.monoMuted} selectable>
            {failure}
          </Text>
        ))}
        <Button label={`Open PR #${pr.number} on GitHub`} kind="secondary" onPress={() => void Linking.openURL(pr.url)} />
      </Card>
      <Command command={command} />
    </>
  );
}
