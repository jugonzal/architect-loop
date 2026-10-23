/* eslint-disable */
// Generated from services/runner/openapi.yaml by src/api/generate-clients.js.
// Do not edit by hand: change the OpenAPI file, then run `npm run generate:clients` (command-center/D55).

import { operationCaller, type OperationSpec, type ServiceClientOptions } from './service';

/**
 * A skill and exactly one thing to run it on (runner-dispatch C3): `loop-design`, `loop-build`,
 * `loop-prove` and `loop-status` on a concern, `loop-design` and `loop-status` on a loop, and `loop-ship`
 * on an environment.
 *
 */
export type DispatchRequest = {
  project: Project;
  skill: Skill;
  concern?: Concern;
  loop?: Loop;
  environment?: Environment;
  /**
   * Passed to the skill after the concern, loop or environment, as a person would type them.
   */
  arguments?: string;
  /**
   * The session's budget in dollars, a target it may pass by one model response (command-center/D21). A
   * budget above the ceiling in the runner's config is refused with a `budget-ceiling` refusal (409).
   *
   */
  budget_usd: number;
  /**
   * The tagged release of the skills the session runs, never the clone's own `plugin/` (command-center/D17).
   */
  plugin_release: string;
} & DispatchRequest1;
/**
 * The project's key, its repository as owner/name (command-center/D18).
 */
export type Project = string;
/**
 * The loop skill to run, without its slash.
 */
export type Skill = 'loop-design' | 'loop-build' | 'loop-prove' | 'loop-status' | 'loop-ship';
/**
 * The concern to run it on, as loop/concern.
 */
export type Concern = string;
/**
 * The loop to run it on, by its folder in docs/loops/.
 */
export type Loop = string;
/**
 * The environment to run it on, as a row of the project's LOOP.md §3 names it, such as `staging/runner` or `main`.
 */
export type Environment = string;
export type DispatchRequest1 =
  | {
      skill?: 'loop-design' | 'loop-build' | 'loop-prove' | 'loop-status';
      loop?: never;
      environment?: never;
      concern: Concern;
    }
  | {
      skill?: 'loop-design' | 'loop-status';
      concern?: never;
      environment?: never;
      loop: Loop;
    }
  | {
      skill?: 'loop-ship';
      concern?: never;
      loop?: never;
      environment: Environment;
    };

/**
 * The runner service's operations, as services/runner/openapi.yaml (version 0.2.0) declares them: each one's request, and its responses' bodies by status.
 */
export interface RunnerOperations {
  /**
   * The commit this runner was built from (command-center/D32).
   */
  getVersion: {
    responses: {
      /**
       * The commit this deployment serves.
       */
      '200': Version;
      /**
       * The deployment was not told which commit it serves.
       */
      '503': Problem;
    };
  };
  /**
   * Start a skill on a concern, a loop or an environment as a session sponsored by the caller.
   */
  dispatch: {
    request: {
      body: DispatchRequest;
    };
    responses: {
      /**
       * The session was claimed and its job started.
       */
      '201': Session;
      /**
       * The request is not a valid dispatch.
       */
      '400': Problem;
      /**
       * No GitHub token, or GitHub did not accept it.
       */
      '401': Problem;
      /**
       * The caller is not a collaborator on the project.
       */
      '403': Problem;
      /**
       * Refused. The body names what already exists.
       */
      '409': Refusal;
      /**
       * The project is not served by this runner, or the concern, the loop, the environment or the plugin
       * release does not exist on the project's main branch.
       *
       */
      '422': Problem;
      /**
       * GitHub or Cloud Run failed. When it was Cloud Run, the session had been claimed, and it ended with
       * outcome `error`, so the concern is free again.
       *
       */
      '502': Problem;
    };
  };
  /**
   * Sessions with their spend, every sponsor's, newest first.
   */
  listSessions: {
    request?: {
      query?: {
        /**
         * `active` (the default) lists sessions that are starting, running or stopping; `all` adds ended ones.
         */
        state?: 'active' | 'all';
        /**
         * Only this sponsor's sessions (a GitHub login).
         */
        sponsor?: string;
        /**
         * Only this project's sessions.
         */
        project?: Project;
      };
    };
    responses: {
      /**
       * The sessions, and the per-sponsor cap they count against.
       */
      '200': SessionList;
      /**
       * A query parameter is not valid.
       */
      '400': Problem;
      /**
       * No GitHub token, or GitHub did not accept it.
       */
      '401': Problem;
      /**
       * The caller is not a collaborator on the project.
       */
      '403': Problem;
      /**
       * GitHub did not answer as expected, so the runner could not tell who is calling.
       */
      '502': Problem;
    };
  };
  /**
   * One session, with its latest published spend and, once it has ended, its final message.
   */
  getSession: {
    request: {
      path: {
        id: string;
      };
    };
    responses: {
      /**
       * The session.
       */
      '200': Session;
      /**
       * No GitHub token, or GitHub did not accept it.
       */
      '401': Problem;
      /**
       * The caller is not a collaborator on the project.
       */
      '403': Problem;
      /**
       * No session has this id.
       */
      '404': Problem;
      /**
       * GitHub did not answer as expected, so the runner could not tell who is calling.
       */
      '502': Problem;
    };
  };
  /**
   * Ask a running session to stop. Only its sponsor may.
   */
  stopSession: {
    request: {
      path: {
        id: string;
      };
    };
    responses: {
      /**
       * The stop was requested. The session is `stopping`.
       */
      '202': Session;
      /**
       * No GitHub token, or GitHub did not accept it.
       */
      '401': Problem;
      /**
       * The caller is not a collaborator, or not this session's sponsor.
       */
      '403': Problem;
      /**
       * No session has this id.
       */
      '404': Problem;
      /**
       * The session has already ended.
       */
      '409': Problem;
      /**
       * GitHub did not answer as expected, so the runner could not tell who is calling.
       */
      '502': Problem;
    };
  };
  /**
   * What a skill is likely to spend on its model, before a start.
   */
  estimate: {
    request: {
      query: {
        skill: Skill;
        model?: string;
      };
    };
    responses: {
      /**
       * The estimate, or null when the pairing has none.
       */
      '200': EstimateAnswer;
      /**
       * The skill is missing or unknown.
       */
      '400': Problem;
      /**
       * No GitHub token, or GitHub did not accept it.
       */
      '401': Problem;
      /**
       * The caller is not a collaborator on the project.
       */
      '403': Problem;
      /**
       * GitHub did not answer as expected, so the runner could not tell who is calling.
       */
      '502': Problem;
    };
  };
}
export interface Version {
  commit: string;
}
export interface Problem {
  error:
    | 'unauthenticated'
    | 'not-a-collaborator'
    | 'invalid-request'
    | 'unknown-project'
    | 'unknown-concern'
    | 'unknown-loop'
    | 'unknown-environment'
    | 'unknown-release'
    | 'no-such-session'
    | 'not-the-sponsor'
    | 'already-ended'
    | 'launch-failed'
    | 'upstream-failed'
    | 'no-commit'
    | 'not-found'
    | 'method-not-allowed';
  message: string;
}
/**
 * Exactly one of `concern`, `loop` and `environment` is set, as in the dispatch that started it.
 */
export interface Session {
  id: string;
  project: Project;
  skill: Skill;
  concern: Concern | null;
  loop: Loop | null;
  environment: Environment | null;
  arguments: string;
  /**
   * The model from the runner's skill to model map (session-runner D5).
   */
  model: string;
  /**
   * The GitHub login of the person who dispatched it, from GET /user.
   */
  sponsor: string;
  budget_usd: number;
  plugin_release: string;
  /**
   * The branch the session's clone starts on: loop/concern for a concern, the project's main branch for a
   * loop or an environment, which pushes no branch of its own unless its skill opens a pull request.
   *
   */
  branch: string;
  state: 'starting' | 'running' | 'stopping' | 'ended';
  /**
   * How it ended, null until it has. `completed`: the skill finished. `budget`: it stopped at the first
   * response that crossed its budget. `sponsor`: its sponsor stopped it. `error`: it failed, or its job
   * could not start. `lost`: its job stopped publishing and the runner gave up on it.
   *
   */
  outcome: 'completed' | 'budget' | 'sponsor' | 'error' | 'lost' | null;
  created_at: string;
  started_at: string | null;
  ended_at: string | null;
  /**
   * The latest published spend, null until the job publishes its first.
   */
  spend: Spend | null;
  /**
   * Pull requests opened from branches the session pushed, found when it ends.
   */
  pull_requests: PullRequest[];
  /**
   * The session's last assistant message, kept when it ends (runner-dispatch C3): for a dispatched
   * `loop-ship`, its brief (app-inbox D1). Null until it ends, and when it ended before saying anything.
   *
   */
  final_message: string | null;
}
/**
 * What a session has spent so far, or in all. Always an estimate. While it runs (`basis: per-step usage`)
 * the runner sums each model response's usage at list price; input and cache tokens are exact, output
 * tokens are a placeholder until the end, so it runs low. At the end (`basis: sdk result`) it is the SDK's
 * own estimate, overshoot included.
 *
 */
export interface Spend {
  kind: 'estimate';
  basis: 'per-step usage' | 'sdk result';
  usd: number;
  /**
   * How far past its budget the session went, 0 when it did not. Null while it runs.
   */
  overshoot_usd: number | null;
  tokens: Tokens;
  wall_clock_s: number;
  as_of: string;
}
export interface Tokens {
  input: number;
  output: number;
  cache_creation: number;
  cache_read: number;
}
export interface PullRequest {
  number: number;
  url: string;
  head: string;
}
export interface Refusal {
  refused: 'open-pull-request' | 'running-session' | 'sponsor-cap' | 'budget-ceiling';
  /**
   * A sentence that names what already exists
   */
  message: string;
  /**
   * For `open-pull-request`, the concern's open pull requests.
   */
  pull_requests: PullRequest[];
  /**
   * For `running-session`, the running `loop-build` and `loop-design` sessions that hold the concern; for
   * `sponsor-cap`, every session the sponsor runs.
   *
   */
  sessions: Session[];
  /**
   * For `sponsor-cap`, the cap the sponsor reached.
   */
  cap?: number;
  /**
   * For `budget-ceiling`, the ceiling in the runner's config, in dollars (session-runner D8).
   */
  ceiling_usd?: number;
}
export interface SessionList {
  sessions: Session[];
  /**
   * How many sessions one sponsor may run at once, from the runner's config (command-center/D22).
   */
  cap_per_sponsor: number;
}
export interface EstimateAnswer {
  skill: Skill;
  model: string;
  estimate: Estimate | null;
}
/**
 * The median of the pairing's last measured sessions, at most 10 (command-center/D23).
 */
export interface Estimate {
  kind: 'estimate';
  usd: number;
  wall_clock_s: number;
  sessions: number;
}

/**
 * The method, path and success statuses of each of the runner service's operations, which the client calls.
 */
export const RUNNER_OPERATIONS: { readonly [Operation in keyof RunnerOperations]: OperationSpec } = {
  getVersion: { method: 'GET', path: '/version', ok: { 200: 'json' } },
  dispatch: { method: 'POST', path: '/sessions', ok: { 201: 'json' } },
  listSessions: { method: 'GET', path: '/sessions', ok: { 200: 'json' } },
  getSession: { method: 'GET', path: '/sessions/{id}', ok: { 200: 'json' } },
  stopSession: { method: 'POST', path: '/sessions/{id}/stop', ok: { 202: 'json' } },
  estimate: { method: 'GET', path: '/estimates', ok: { 200: 'json' } },
};

/**
 * The runner service's client, generated from services/runner/openapi.yaml: one method per operation
 * the app calls. Each call goes through the signed-in fetch the client was made with, to the base URL it was
 * made with, and resolves to the body of a success response. Any other answer rejects with a ServiceError
 * (service.ts) that carries the status and the body, typed for each status in RunnerOperations. A client made with
 * no base URL never calls the service: each method rejects with a 'not-configured' ServiceError that says
 * which URL the build is missing.
 */
export interface RunnerClient {
  /**
   * The commit this runner was built from (command-center/D32).
   *
   * `GET /version`
   */
  getVersion(): Promise<RunnerOperations['getVersion']['responses']['200']>;
  /**
   * Start a skill on a concern, a loop or an environment as a session sponsored by the caller.
   *
   * Only `loop-build` and `loop-design` hold the concern they run on (session-runner D6). Either is refused
   * (409) when the concern already has an open pull request or a running `loop-build` or `loop-design`
   * session; `loop-prove` and `loop-status` run beside them and hold nothing. Any dispatch is refused when the
   * caller already runs as many sessions as the per-sponsor cap in the runner's config (3 by default,
   * command-center/D22), counting every running session whatever its skill, or when its budget is above the
   * ceiling in the runner's config ($10 by default, session-runner D8). Each refusal names the pull requests
   * or sessions that exist, or the cap or the ceiling. The claim is atomic, so of two dispatches at once that
   * would each hold a concern at most one starts. A dispatch on a loop or an environment holds no concern,
   * so only the cap and the ceiling can refuse it.
   *
   * `POST /sessions`
   */
  dispatch(request: RunnerOperations['dispatch']['request']): Promise<RunnerOperations['dispatch']['responses']['201']>;
  /**
   * Sessions with their spend, every sponsor's, newest first.
   *
   * `GET /sessions`
   */
  listSessions(
    request?: RunnerOperations['listSessions']['request'],
  ): Promise<RunnerOperations['listSessions']['responses']['200']>;
  /**
   * One session, with its latest published spend and, once it has ended, its final message.
   *
   * `GET /sessions/{id}`
   */
  getSession(
    request: RunnerOperations['getSession']['request'],
  ): Promise<RunnerOperations['getSession']['responses']['200']>;
  /**
   * Ask a running session to stop. Only its sponsor may.
   *
   * The session sees the request the next time it publishes its spend, at most 10 seconds later, interrupts
   * its model, publishes its final estimate and ends with outcome `sponsor`. Its branch and pull request
   * stay for a person to close; the runner merges and deletes nothing.
   *
   * `POST /sessions/{id}/stop`
   */
  stopSession(
    request: RunnerOperations['stopSession']['request'],
  ): Promise<RunnerOperations['stopSession']['responses']['202']>;
  /**
   * What a skill is likely to spend on its model, before a start.
   *
   * The median of that skill and model's last 10 measured sessions (command-center/D23). A pairing with
   * no measured session has no estimate (`estimate` is null). The model is the one the runner's config maps
   * the skill to, unless `model` names another.
   *
   * `GET /estimates`
   */
  estimate(request: RunnerOperations['estimate']['request']): Promise<RunnerOperations['estimate']['responses']['200']>;
}

/**
 * Makes the runner service's client from this build's URL for it (AppConfig.runnerUrl, null while the
 * build has none) and the signed-in fetch (useSignedInFetch).
 */
export function createRunnerClient(options: ServiceClientOptions): RunnerClient {
  const call = operationCaller('runner', RUNNER_OPERATIONS, options);
  return {
    getVersion: () => call<RunnerOperations['getVersion']['responses']['200']>('getVersion'),
    dispatch: (request) => call<RunnerOperations['dispatch']['responses']['201']>('dispatch', request),
    listSessions: (request) => call<RunnerOperations['listSessions']['responses']['200']>('listSessions', request),
    getSession: (request) => call<RunnerOperations['getSession']['responses']['200']>('getSession', request),
    stopSession: (request) => call<RunnerOperations['stopSession']['responses']['202']>('stopSession', request),
    estimate: (request) => call<RunnerOperations['estimate']['responses']['200']>('estimate', request),
  };
}
