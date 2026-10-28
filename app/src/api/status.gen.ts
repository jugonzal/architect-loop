/* eslint-disable */
// Generated from plugin/skills/loop-status/scripts/status.schema.json by src/api/generate-status-types.js.
// Do not edit by hand: change the schema, then run `npm run generate:status` (command-center/D15).

/**
 * This interface was referenced by `LoopStatus`'s JSON-Schema
 * via the `definition` "text".
 */
export type Text = string;
/**
 * A commit, abbreviated to at least 7 hex digits or in full.
 *
 * This interface was referenced by `LoopStatus`'s JSON-Schema
 * via the `definition` "sha".
 */
export type Sha = string;
/**
 * The combined result of the checks on a commit: none when no check ran, unknown when it could not be read.
 *
 * This interface was referenced by `LoopStatus`'s JSON-Schema
 * via the `definition` "ci_state".
 */
export type CiState = 'success' | 'failure' | 'pending' | 'none' | 'unknown';
/**
 * An environment and the commit it serves. Exactly one of served and error is set: an environment that cannot be read is unknown, never assumed.
 *
 * This interface was referenced by `LoopStatus`'s JSON-Schema
 * via the `definition` "environment".
 */
export type Environment = {
  name: Text;
  served: string | null;
  error: string | null;
} & Environment1;
export type Environment1 =
  | {
      served?: string;
      error?: null;
    }
  | {
      served?: null;
      error?: string;
    };
/**
 * A loop's folder name or a concern's file name without .md.
 *
 * This interface was referenced by `LoopStatus`'s JSON-Schema
 * via the `definition` "id".
 */
export type Id = string;
/**
 * A loop's state, as step 5 of loop-status SKILL.md derives it, plus unknown when a fact it depends on cannot be read.
 *
 * This interface was referenced by `LoopStatus`'s JSON-Schema
 * via the `definition` "loop_state".
 */
export type LoopState = 'parked' | 'open' | 'backlog' | 'done' | 'active' | 'unknown';
/**
 * This interface was referenced by `LoopStatus`'s JSON-Schema
 * via the `definition` "verdict".
 */
export type Verdict = 'HOLDS' | 'CONTRADICTS' | 'UNPROVEN';
/**
 * A concern's state: exactly the rows of the derivation table in loop-status SKILL.md, in its order, plus unknown when a fact the state depends on cannot be read. Finer detail ('in review', 'proving') belongs in the reason, never in the state.
 *
 * This interface was referenced by `LoopStatus`'s JSON-Schema
 * via the `definition` "concern_state".
 */
export type ConcernState =
  | 'parked'
  | 'contradicted'
  | 'open'
  | 'blocked'
  | 'ready'
  | 'building'
  | 'merged'
  | 'shipped'
  | 'stale'
  | 'done'
  | 'unknown';
/**
 * The commit the concern's ships-to environment serves, or why it could not be read (exactly one of the two), and whether it serves every merge commit of the concern.
 *
 * This interface was referenced by `LoopStatus`'s JSON-Schema
 * via the `definition` "served".
 */
export type Served = {
  /**
   * The ships-to environment; null when the contract has none.
   */
  environment: string | null;
  commit: string | null;
  error: string | null;
  /**
   * Whether the served commit has every merge commit of the concern as an ancestor; false when nothing is merged; null when unknown.
   */
  serves: boolean | null;
} & Served1;
export type Served1 =
  | {
      commit?: string;
      error?: null;
    }
  | {
      commit?: null;
      error?: string;
      serves?: null;
    };
/**
 * Something that needs a person. detail's shape follows kind.
 *
 * This interface was referenced by `LoopStatus`'s JSON-Schema
 * via the `definition` "queue_item".
 */
export type QueueItem = {
  /**
   * A key that stays the same across runs while the item stands, such as <loop>/<concern>/Q1 or <owner>/<repo>#12.
   */
  id: string;
  kind: QueueKind;
  /**
   * One line to show for it.
   */
  title: string;
  /**
   * Why it is in the queue, from the facts.
   */
  why: string;
  /**
   * The loop it belongs to; null when it spans loops, as a ship can.
   */
  loop: string | null;
  /**
   * The concerns it is about.
   */
  concerns: ConcernRef[];
  /**
   * The concerns that finishing it unblocks, counting through needs across loops. Its length orders the queue.
   */
  unblocks: ConcernRef[];
  /**
   * The one person it waits on: the holder of its gate in LOOP.md §2 when it crosses one, otherwise the loop's owner. Null until addressing fills it.
   */
  waits_on: string | null;
  /**
   * The loop's members, who can see it but not act on it. Empty until addressing fills it.
   */
  visible_to: Text[];
  /**
   * The gate in LOOP.md §2 it crosses, or null.
   */
  gate: string | null;
  detail: {};
} & QueueItem1;
/**
 * What a queue item asks of a person: one kind for each item loop-status queues in step 6 and offers in its Record step. A person acts on the first four: answer a question, review a pull request, ship to an environment, or approve a record. The rest are shown read-only, with the command to run: a proof that waits on a person, a fact only a person can read (command-center/D76), a concern that leads to no one (command-center/D77), a contradiction that needs a call, and a loop-document pull request that check_loop_pr.sh refused.
 *
 * This interface was referenced by `LoopStatus`'s JSON-Schema
 * via the `definition` "queue_kind".
 */
export type QueueKind =
  'question' | 'review' | 'ship' | 'record' | 'proof' | 'fact' | 'stuck' | 'contradiction' | 'refused_pr';
/**
 * A concern, written <loop>/<concern>.
 *
 * This interface was referenced by `LoopStatus`'s JSON-Schema
 * via the `definition` "concern_ref".
 */
export type ConcernRef = string;
export type QueueItem1 =
  | {
      kind?: 'question';
      detail?: QuestionDetail;
    }
  | {
      kind?: 'review';
      detail?: ReviewDetail;
    }
  | {
      kind?: 'ship';
      detail?: ShipDetail;
    }
  | {
      kind?: 'record';
      detail?: RecordDetail;
    }
  | {
      kind?: 'proof';
      detail?: ProofDetail;
    }
  | {
      kind?: 'fact';
      detail?: FactDetail;
    }
  | {
      kind?: 'stuck';
      detail?: StuckDetail;
    }
  | {
      kind?: 'contradiction';
      detail?: ContradictionDetail;
    }
  | {
      kind?: 'refused_pr';
      detail?: RefusedPrDetail;
    };
/**
 * A concern's claim, written <loop>/<concern>/C<n>.
 *
 * This interface was referenced by `LoopStatus`'s JSON-Schema
 * via the `definition` "claim_ref".
 */
export type ClaimRef = string;

/**
 * What is true right now for every loop and concern of one project, as loop-status derives it from facts: the board, the queue of what needs a person, and what agents can start now. The loop-status script writes it with --json, and every reader of a project's status reads exactly this. schema_version is the version of this file; raise it whenever a change would make a reader of the previous version misread a document, and update every fixture and reader in the same change.
 */
export interface LoopStatus {
  /**
   * The version of this schema that the document was written for.
   */
  schema_version: 1;
  /**
   * The key of the project the document describes, usually its repository as owner/name. Every document describes exactly one project.
   */
  project: string;
  /**
   * When the facts were gathered, in UTC. It is one of the facts, so deriving twice from the same facts gives the same document.
   */
  as_of: string;
  main: Main;
  /**
   * Every environment in LOOP.md §3, lowest first, with the commit it serves or why that could not be read.
   */
  environments: Environment[];
  /**
   * Every loop in docs/loops/.
   */
  loops: Loop[];
  /**
   * What needs a person (the board's 'Needs you'), most unblocking first: sorted by the length of unblocks, longest first.
   */
  queue: QueueItem[];
  /**
   * Work an agent can start now without a person: ready concerns to build, shipped and stale ones to prove, incomplete contracts to design.
   */
  agents_can_start: Start[];
  /**
   * Documents whose text the facts contradict, and other drift the board flags.
   */
  drift: Drift[];
  /**
   * Facts that could not be read for the whole project, such as pull requests when the forge is unreachable. Whatever depends on them is unknown.
   */
  missing: MissingFact[];
}
/**
 * The main branch: its head and the result of its checks.
 *
 * This interface was referenced by `LoopStatus`'s JSON-Schema
 * via the `definition` "main".
 */
export interface Main {
  branch: Text;
  sha: Sha;
  ci: CiState;
}
/**
 * This interface was referenced by `LoopStatus`'s JSON-Schema
 * via the `definition` "loop".
 */
export interface Loop {
  id: Id;
  title: Text;
  /**
   * The loop's README, relative to the repository root.
   */
  path: string;
  state: LoopState;
  /**
   * The facts behind the state, in one line.
   */
  reason: string;
  /**
   * The command or action that moves the loop on, or null.
   */
  next: string | null;
  /**
   * The loop's owner: from its front matter, else LOOP.md's owner; null until known.
   */
  owner?: string | null;
  /**
   * The loop's members, from its front matter.
   */
  members?: Text[];
  /**
   * The loop's goals (G#).
   */
  goals: Claim[];
  concerns: Concern[];
}
/**
 * A claim (C#) or a goal (G#), with every evidence line about it.
 *
 * This interface was referenced by `LoopStatus`'s JSON-Schema
 * via the `definition` "claim".
 */
export interface Claim {
  id: string;
  text: Text;
  /**
   * True when the claim is struck through (superseded); it then counts for no state.
   */
  struck: boolean;
  /**
   * Its evidence lines, in file order; the last is the latest verdict.
   */
  evidence: Evidence[];
  /**
   * Whether it has a current HOLDS on the concern's ships-to environment (for a goal, on the loop's); null when that cannot be read.
   */
  current_holds: boolean | null;
}
/**
 * One evidence line: YYYY-MM-DD · C1 · HOLDS · rung 1 · staging @<sha> · <evidence>.
 *
 * This interface was referenced by `LoopStatus`'s JSON-Schema
 * via the `definition` "evidence".
 */
export interface Evidence {
  date: string;
  verdict: Verdict;
  rung: number;
  environment: Text;
  /**
   * The commit it cites; null for @? (migrated without a commit), which never counts as a HOLDS.
   */
  commit: string | null;
  text: Text;
}
/**
 * This interface was referenced by `LoopStatus`'s JSON-Schema
 * via the `definition` "concern".
 */
export interface Concern {
  id: Id;
  title: Text;
  /**
   * The concern's file, relative to the repository root.
   */
  path: string;
  contract: Contract;
  /**
   * The concern's claims (C#), in the order of Done when.
   */
  claims: Claim[];
  state: ConcernState;
  /**
   * The facts behind the state, in one line, such as which table row matched and why.
   */
  reason: string;
  /**
   * The table's Next for this state, as a command where it is one; null when there is nothing to do.
   */
  next: string | null;
  inputs: Inputs;
}
/**
 * The concern's front matter. An entry that is absent is an empty list or null.
 *
 * This interface was referenced by `LoopStatus`'s JSON-Schema
 * via the `definition` "contract".
 */
export interface Contract {
  needs: Text[];
  touches: Text[];
  effects: Text[];
  ships_to: string | null;
  /**
   * As written: #<n>, or <owner>/<repo>#<n>.
   */
  prs: Text[];
  /**
   * The D# that parks the concern.
   */
  parked: string | null;
}
/**
 * The facts the state came from. The fields named here have fixed meanings; the derivation may add other facts.
 *
 * This interface was referenced by `LoopStatus`'s JSON-Schema
 * via the `definition` "inputs".
 */
export interface Inputs {
  /**
   * A commit, abbreviated to at least 7 hex digits or in full.
   */
  main: string;
  served: Served;
  /**
   * The linked pull requests: by head branch, by Concern trailer in the body, or listed in prs.
   */
  prs: Pr[];
  /**
   * Commits on main that carry the concern's Concern trailer.
   */
  commits: Sha[];
  branch?: Branch;
  /**
   * The facts that could not be read, each with why; set whenever the state is unknown.
   */
  missing?: Text[];
  [k: string]: unknown | undefined;
}
/**
 * This interface was referenced by `LoopStatus`'s JSON-Schema
 * via the `definition` "pr".
 */
export interface Pr {
  /**
   * owner/name.
   */
  repository: string;
  number: number;
  url: Text;
  title: Text;
  head: Text;
  base: Text;
  state: 'open' | 'closed' | 'merged';
  draft: boolean;
  merge_commit: string | null;
  /**
   * Whether merge_commit is on its repository's main. Only then does the pull request count as merged. Null when it has no merge commit or that could not be read.
   */
  on_main: boolean | null;
  checks: CiState;
}
/**
 * The concern's branch, <loop>/<concern>.
 *
 * This interface was referenced by `LoopStatus`'s JSON-Schema
 * via the `definition` "branch".
 */
export interface Branch {
  name: Text;
  exists: boolean | null;
}
/**
 * An open question (Q#). Its options, its recommendation and its default are kept apart: the recommendation is the answer the file recommends, and the default is what happens if nobody answers. A question written before options were recorded has no options and no recommendation, and shows only the question, what it blocks and its default.
 *
 * This interface was referenced by `LoopStatus`'s JSON-Schema
 * via the `definition` "question_detail".
 */
export interface QuestionDetail {
  /**
   * <loop>/Q3 or <loop>/<concern>/Q1.
   */
  ref: string;
  question: Text;
  /**
   * The options the file records, in its order, each with its main consequence; none is pre-selected. Empty for a question written before options were recorded.
   */
  options: Option[];
  /**
   * The text of the option the file recommends, exactly as that option has it, or null when it recommends none; always null when there are no options, and never the default. JSON Schema cannot tie it to an option, so whatever writes a document must, and this schema's tests check it for every fixture.
   */
  recommendation: string | null;
  /**
   * What happens if nobody answers: the Questions table's 'Default if unanswered', as written; null when that cell is empty.
   */
  default: string | null;
  /**
   * What it blocks, as written in the Questions table.
   */
  blocks: Text[];
}
/**
 * One answer to a question, with its main consequence.
 *
 * This interface was referenced by `LoopStatus`'s JSON-Schema
 * via the `definition` "option".
 */
export interface Option {
  /**
   * The option, as the file writes it.
   */
  text: string;
  /**
   * What choosing it means, as the file writes it.
   */
  consequence: string;
}
/**
 * A pull request ready for review.
 *
 * This interface was referenced by `LoopStatus`'s JSON-Schema
 * via the `definition` "review_detail".
 */
export interface ReviewDetail {
  pr: Pr;
  /**
   * The body's 'How it was proven before the merge' section, as Markdown; null if the body has none.
   */
  proof: string | null;
}
/**
 * Merged concerns waiting to ship to an environment.
 *
 * This interface was referenced by `LoopStatus`'s JSON-Schema
 * via the `definition` "ship_detail".
 */
export interface ShipDetail {
  environment: Text;
  /**
   * The concerns' declared effects, as the steps a person performs.
   */
  manual_steps: Text[];
}
/**
 * Text to write on the person's yes, and where.
 *
 * This interface was referenced by `LoopStatus`'s JSON-Schema
 * via the `definition` "record_detail".
 */
export interface RecordDetail {
  path: Text;
  /**
   * The proposed text, as Markdown.
   */
  text: string;
}
/**
 * An UNPROVEN claim that waits on a person: the one its line's `· needs <who>: <what>` names, or the loop's owner when the line names no one (command-center/D74, D75). Shown read-only, with the command to run once that is to hand.
 *
 * This interface was referenced by `LoopStatus`'s JSON-Schema
 * via the `definition` "proof_detail".
 */
export interface ProofDetail {
  claim: ClaimRef;
  /**
   * The environment the claim must be proven on.
   */
  environment: string;
  /**
   * What the proof needs that no agent has, from its UNPROVEN evidence line.
   */
  missing: string;
  /**
   * Who can supply it: what the line's needs segment names (a login, owner, or gate:<key>), a person or role an older line's prose names, or owner when it names no one.
   */
  supplied_by: string;
  /**
   * The command to run once it is to hand, such as /loop-prove <loop>/<concern> <env>.
   */
  command: string;
}
/**
 * A fact only a person can read: a LOOP.md §3 row that agents may not read, or that has no served-commit command, while an unfinished concern's state rests on it (command-center/D76). Shown read-only, with the command to run once it can be read.
 *
 * This interface was referenced by `LoopStatus`'s JSON-Schema
 * via the `definition` "fact_detail".
 */
export interface FactDetail {
  /**
   * The fact, such as <environment>'s served commit.
   */
  fact: string;
  /**
   * The LOOP.md §3 row it belongs to.
   */
  environment: string;
  /**
   * Why an agent cannot read it, as the board's missing facts say.
   */
  error: string;
  /**
   * Who can read it: owner, the loop's owner.
   */
  supplied_by: string;
  /**
   * What makes it readable, as the first concern resting on it says.
   */
  next: string;
  /**
   * The command to run once it can be read: /loop-status <loop>.
   */
  command: string;
}
/**
 * A concern that is neither done nor parked and leads to no one: no other queue item, no step an agent can take alone, and no need that leads anywhere (command-center/D77). Shown read-only, so its loop's owner can say what moves it.
 *
 * This interface was referenced by `LoopStatus`'s JSON-Schema
 * via the `definition` "stuck_detail".
 */
export interface StuckDetail {
  concern: ConcernRef;
  state: ConcernState;
  /**
   * The concern's reason, from the facts.
   */
  reason: string;
  /**
   * The concern's next step, as the board gives it.
   */
  next: string;
  /**
   * The command to run once something leads from it: /loop-status <loop>/<concern>.
   */
  command: string;
}
/**
 * A claim whose latest verdict is CONTRADICTS, with no decision dated after it, so it needs a call: redesign, or roll back. Shown read-only, with the command to run.
 *
 * This interface was referenced by `LoopStatus`'s JSON-Schema
 * via the `definition` "contradiction_detail".
 */
export interface ContradictionDetail {
  claim: ClaimRef;
  evidence: Evidence1;
  /**
   * What the evidence contradicts: the design text it disproves, or the shared decision (<loop>/D#) it says it contradicts.
   */
  contradicts: string;
  /**
   * True when the evidence line says it contradicts a shared decision, which escalates to the loop as a question.
   */
  escalates: boolean;
  /**
   * The command to run, such as /loop-design <loop>/<concern>, or /loop-diagnose when the cause is unknown.
   */
  command: string;
}
/**
 * One evidence line: YYYY-MM-DD · C1 · HOLDS · rung 1 · staging @<sha> · <evidence>.
 */
export interface Evidence1 {
  date: string;
  verdict: Verdict;
  rung: number;
  environment: Text;
  /**
   * The commit it cites; null for @? (migrated without a commit), which never counts as a HOLDS.
   */
  commit: string | null;
  text: Text;
}
/**
 * A loop-document pull request that loop-status's check_loop_pr.sh refused, so no agent may merge it under LOOP.md §2.1. Shown read-only, with the command to run.
 *
 * This interface was referenced by `LoopStatus`'s JSON-Schema
 * via the `definition` "refused_pr_detail".
 */
export interface RefusedPrDetail {
  pr: Pr;
  /**
   * The lines the checker printed for why it refused, in its order.
   */
  failures: Text[];
  /**
   * The command to run, such as the checker again: scripts/check_loop_pr.sh --pr <n>.
   */
  command: string;
}
/**
 * This interface was referenced by `LoopStatus`'s JSON-Schema
 * via the `definition` "start".
 */
export interface Start {
  concern: ConcernRef;
  action: 'build' | 'prove' | 'design';
  /**
   * The command to run, such as /loop-build <loop>/<concern>.
   */
  command: string;
}
/**
 * This interface was referenced by `LoopStatus`'s JSON-Schema
 * via the `definition` "drift".
 */
export interface Drift {
  /**
   * The file and the place in it, or the concerns involved.
   */
  where: string;
  /**
   * What the text says, and what is actually true.
   */
  finding: string;
  /**
   * The command that established it.
   */
  checked: string;
}
/**
 * This interface was referenced by `LoopStatus`'s JSON-Schema
 * via the `definition` "missing_fact".
 */
export interface MissingFact {
  fact: Text;
  error: Text;
}
