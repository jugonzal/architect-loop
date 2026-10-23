/* eslint-disable */
// Generated from services/threads/openapi.yaml by src/api/generate-clients.js.
// Do not edit by hand: change the OpenAPI file, then run `npm run generate:clients` (command-center/D55).
// Not a method here: receiveGitHubWebhook. GitHub calls it, with a delivery signed with the webhook secret; the app never does.

import { operationCaller, type OperationSpec, type ServiceClientOptions } from './service';

/**
 * A GitHub login.
 */
export type Login = string;
export type Name = string;
/**
 * `message` is what people write, and what a session writes to them. `milestone` is a step of a session
 * (started, branch opened, tests run, PR opened, stopped at a gate, finished). `narration` is everything
 * else a session says; clients collapse it to the milestones by default.
 *
 */
export type Kind = 'message' | 'milestone' | 'narration';
export type SessionId = string;

/**
 * The threads service's operations, as services/threads/openapi.yaml (version 1.0.0) declares them: each one's request, and its responses' bodies by status.
 */
export interface ThreadsOperations {
  /**
   * The commit this deployment was built from (command-center/D32).
   */
  getVersion: {
    responses: {
      /**
       * The commit.
       */
      '200': Version;
    };
  };
  /**
   * A loop's thread, with its members and watchers.
   */
  getLoopThread: {
    request: {
      path: {
        /**
         * The owner of the project's repository. A project is keyed by its repository (command-center/D18).
         */
        owner: Login;
        /**
         * The name of the project's repository.
         */
        repo: string;
        /**
         * A loop's folder name under `docs/loops/`.
         */
        loop: Name;
      };
    };
    responses: {
      /**
       * The thread.
       */
      '200': Thread;
      /**
       * The request is malformed, or a name, a parameter or the body is not valid.
       */
      '400': Error;
      /**
       * No token, a token GitHub does not accept, a service identity this deployment does not trust, or a webhook whose signature does not match.
       */
      '401': Error;
      /**
       * The caller is not a member of the project, or is the runner asking for something only a person may do.
       */
      '403': Error;
      /**
       * The project is not served here, or the message does not exist in it.
       */
      '404': Error;
      /**
       * GitHub (or Google's keys) could not be reached to identify the caller or check their access, so nothing is
       * answered; or this deployment is not configured yet, and only `/version` answers.
       *
       */
      '503': Error;
    };
  };
  /**
   * A page of a loop thread's messages, oldest first.
   */
  listLoopMessages: {
    request: {
      path: {
        /**
         * The owner of the project's repository. A project is keyed by its repository (command-center/D18).
         */
        owner: Login;
        /**
         * The name of the project's repository.
         */
        repo: string;
        /**
         * A loop's folder name under `docs/loops/`.
         */
        loop: Name;
      };
      query?: {
        /**
         * Return only messages whose `seq` is greater than this. Omit it to start at the beginning.
         */
        after?: number;
        /**
         * The most messages to return.
         */
        limit?: number;
        /**
         * Return only messages of these kinds, for example `kind=milestone` to collapse a session thread.
         */
        kind?: Kind[];
      };
    };
    responses: {
      /**
       * A page of messages, oldest first.
       */
      '200': MessagePage;
      /**
       * The request is malformed, or a name, a parameter or the body is not valid.
       */
      '400': Error;
      /**
       * No token, a token GitHub does not accept, a service identity this deployment does not trust, or a webhook whose signature does not match.
       */
      '401': Error;
      /**
       * The caller is not a member of the project, or is the runner asking for something only a person may do.
       */
      '403': Error;
      /**
       * The project is not served here, or the message does not exist in it.
       */
      '404': Error;
      /**
       * GitHub (or Google's keys) could not be reached to identify the caller or check their access, so nothing is
       * answered; or this deployment is not configured yet, and only `/version` answers.
       *
       */
      '503': Error;
    };
  };
  /**
   * Post a message to a loop's thread, as the signed-in person.
   */
  postLoopMessage: {
    request: {
      path: {
        /**
         * The owner of the project's repository. A project is keyed by its repository (command-center/D18).
         */
        owner: Login;
        /**
         * The name of the project's repository.
         */
        repo: string;
        /**
         * A loop's folder name under `docs/loops/`.
         */
        loop: Name;
      };
      body: NewMessage;
    };
    responses: {
      /**
       * The message as stored.
       */
      '201': Message;
      /**
       * The request is malformed, or a name, a parameter or the body is not valid.
       */
      '400': Error;
      /**
       * No token, a token GitHub does not accept, a service identity this deployment does not trust, or a webhook whose signature does not match.
       */
      '401': Error;
      /**
       * The caller is not a member of the project, or is the runner asking for something only a person may do.
       */
      '403': Error;
      /**
       * The project is not served here, or the message does not exist in it.
       */
      '404': Error;
      /**
       * GitHub (or Google's keys) could not be reached to identify the caller or check their access, so nothing is
       * answered; or this deployment is not configured yet, and only `/version` answers.
       *
       */
      '503': Error;
    };
  };
  /**
   * Watch a loop's thread. Watching twice is the same as once.
   */
  watchLoopThread: {
    request: {
      path: {
        /**
         * The owner of the project's repository. A project is keyed by its repository (command-center/D18).
         */
        owner: Login;
        /**
         * The name of the project's repository.
         */
        repo: string;
        /**
         * A loop's folder name under `docs/loops/`.
         */
        loop: Name;
      };
    };
    responses: {
      /**
       * The thread.
       */
      '200': Thread;
      /**
       * The request is malformed, or a name, a parameter or the body is not valid.
       */
      '400': Error;
      /**
       * No token, a token GitHub does not accept, a service identity this deployment does not trust, or a webhook whose signature does not match.
       */
      '401': Error;
      /**
       * The caller is not a member of the project, or is the runner asking for something only a person may do.
       */
      '403': Error;
      /**
       * The project is not served here, or the message does not exist in it.
       */
      '404': Error;
      /**
       * GitHub (or Google's keys) could not be reached to identify the caller or check their access, so nothing is
       * answered; or this deployment is not configured yet, and only `/version` answers.
       *
       */
      '503': Error;
    };
  };
  /**
   * Stop watching a loop's thread.
   */
  unwatchLoopThread: {
    request: {
      path: {
        /**
         * The owner of the project's repository. A project is keyed by its repository (command-center/D18).
         */
        owner: Login;
        /**
         * The name of the project's repository.
         */
        repo: string;
        /**
         * A loop's folder name under `docs/loops/`.
         */
        loop: Name;
      };
    };
    responses: {
      /**
       * The thread.
       */
      '200': Thread;
      /**
       * The request is malformed, or a name, a parameter or the body is not valid.
       */
      '400': Error;
      /**
       * No token, a token GitHub does not accept, a service identity this deployment does not trust, or a webhook whose signature does not match.
       */
      '401': Error;
      /**
       * The caller is not a member of the project, or is the runner asking for something only a person may do.
       */
      '403': Error;
      /**
       * The project is not served here, or the message does not exist in it.
       */
      '404': Error;
      /**
       * GitHub (or Google's keys) could not be reached to identify the caller or check their access, so nothing is
       * answered; or this deployment is not configured yet, and only `/version` answers.
       *
       */
      '503': Error;
    };
  };
  /**
   * A concern's thread, with its members and watchers.
   */
  getConcernThread: {
    request: {
      path: {
        /**
         * The owner of the project's repository. A project is keyed by its repository (command-center/D18).
         */
        owner: Login;
        /**
         * The name of the project's repository.
         */
        repo: string;
        /**
         * A loop's folder name under `docs/loops/`.
         */
        loop: Name;
        /**
         * A concern's file name in its loop's folder, without `.md`.
         */
        concern: Name;
      };
    };
    responses: {
      /**
       * The thread.
       */
      '200': Thread;
      /**
       * The request is malformed, or a name, a parameter or the body is not valid.
       */
      '400': Error;
      /**
       * No token, a token GitHub does not accept, a service identity this deployment does not trust, or a webhook whose signature does not match.
       */
      '401': Error;
      /**
       * The caller is not a member of the project, or is the runner asking for something only a person may do.
       */
      '403': Error;
      /**
       * The project is not served here, or the message does not exist in it.
       */
      '404': Error;
      /**
       * GitHub (or Google's keys) could not be reached to identify the caller or check their access, so nothing is
       * answered; or this deployment is not configured yet, and only `/version` answers.
       *
       */
      '503': Error;
    };
  };
  /**
   * A page of a concern thread's messages, oldest first, including mirrored review comments.
   */
  listConcernMessages: {
    request: {
      path: {
        /**
         * The owner of the project's repository. A project is keyed by its repository (command-center/D18).
         */
        owner: Login;
        /**
         * The name of the project's repository.
         */
        repo: string;
        /**
         * A loop's folder name under `docs/loops/`.
         */
        loop: Name;
        /**
         * A concern's file name in its loop's folder, without `.md`.
         */
        concern: Name;
      };
      query?: {
        /**
         * Return only messages whose `seq` is greater than this. Omit it to start at the beginning.
         */
        after?: number;
        /**
         * The most messages to return.
         */
        limit?: number;
        /**
         * Return only messages of these kinds, for example `kind=milestone` to collapse a session thread.
         */
        kind?: Kind[];
      };
    };
    responses: {
      /**
       * A page of messages, oldest first.
       */
      '200': MessagePage;
      /**
       * The request is malformed, or a name, a parameter or the body is not valid.
       */
      '400': Error;
      /**
       * No token, a token GitHub does not accept, a service identity this deployment does not trust, or a webhook whose signature does not match.
       */
      '401': Error;
      /**
       * The caller is not a member of the project, or is the runner asking for something only a person may do.
       */
      '403': Error;
      /**
       * The project is not served here, or the message does not exist in it.
       */
      '404': Error;
      /**
       * GitHub (or Google's keys) could not be reached to identify the caller or check their access, so nothing is
       * answered; or this deployment is not configured yet, and only `/version` answers.
       *
       */
      '503': Error;
    };
  };
  /**
   * Post a message to a concern's thread, as the signed-in person.
   */
  postConcernMessage: {
    request: {
      path: {
        /**
         * The owner of the project's repository. A project is keyed by its repository (command-center/D18).
         */
        owner: Login;
        /**
         * The name of the project's repository.
         */
        repo: string;
        /**
         * A loop's folder name under `docs/loops/`.
         */
        loop: Name;
        /**
         * A concern's file name in its loop's folder, without `.md`.
         */
        concern: Name;
      };
      body: NewMessage;
    };
    responses: {
      /**
       * The message as stored.
       */
      '201': Message;
      /**
       * The request is malformed, or a name, a parameter or the body is not valid.
       */
      '400': Error;
      /**
       * No token, a token GitHub does not accept, a service identity this deployment does not trust, or a webhook whose signature does not match.
       */
      '401': Error;
      /**
       * The caller is not a member of the project, or is the runner asking for something only a person may do.
       */
      '403': Error;
      /**
       * The project is not served here, or the message does not exist in it.
       */
      '404': Error;
      /**
       * GitHub (or Google's keys) could not be reached to identify the caller or check their access, so nothing is
       * answered; or this deployment is not configured yet, and only `/version` answers.
       *
       */
      '503': Error;
    };
  };
  /**
   * Watch a concern's thread. Watching twice is the same as once.
   */
  watchConcernThread: {
    request: {
      path: {
        /**
         * The owner of the project's repository. A project is keyed by its repository (command-center/D18).
         */
        owner: Login;
        /**
         * The name of the project's repository.
         */
        repo: string;
        /**
         * A loop's folder name under `docs/loops/`.
         */
        loop: Name;
        /**
         * A concern's file name in its loop's folder, without `.md`.
         */
        concern: Name;
      };
    };
    responses: {
      /**
       * The thread.
       */
      '200': Thread;
      /**
       * The request is malformed, or a name, a parameter or the body is not valid.
       */
      '400': Error;
      /**
       * No token, a token GitHub does not accept, a service identity this deployment does not trust, or a webhook whose signature does not match.
       */
      '401': Error;
      /**
       * The caller is not a member of the project, or is the runner asking for something only a person may do.
       */
      '403': Error;
      /**
       * The project is not served here, or the message does not exist in it.
       */
      '404': Error;
      /**
       * GitHub (or Google's keys) could not be reached to identify the caller or check their access, so nothing is
       * answered; or this deployment is not configured yet, and only `/version` answers.
       *
       */
      '503': Error;
    };
  };
  /**
   * Stop watching a concern's thread.
   */
  unwatchConcernThread: {
    request: {
      path: {
        /**
         * The owner of the project's repository. A project is keyed by its repository (command-center/D18).
         */
        owner: Login;
        /**
         * The name of the project's repository.
         */
        repo: string;
        /**
         * A loop's folder name under `docs/loops/`.
         */
        loop: Name;
        /**
         * A concern's file name in its loop's folder, without `.md`.
         */
        concern: Name;
      };
    };
    responses: {
      /**
       * The thread.
       */
      '200': Thread;
      /**
       * The request is malformed, or a name, a parameter or the body is not valid.
       */
      '400': Error;
      /**
       * No token, a token GitHub does not accept, a service identity this deployment does not trust, or a webhook whose signature does not match.
       */
      '401': Error;
      /**
       * The caller is not a member of the project, or is the runner asking for something only a person may do.
       */
      '403': Error;
      /**
       * The project is not served here, or the message does not exist in it.
       */
      '404': Error;
      /**
       * GitHub (or Google's keys) could not be reached to identify the caller or check their access, so nothing is
       * answered; or this deployment is not configured yet, and only `/version` answers.
       *
       */
      '503': Error;
    };
  };
  /**
   * A session's thread, with its sponsor, members and watchers.
   */
  getSessionThread: {
    request: {
      path: {
        /**
         * The owner of the project's repository. A project is keyed by its repository (command-center/D18).
         */
        owner: Login;
        /**
         * The name of the project's repository.
         */
        repo: string;
        /**
         * The runner's id for the session.
         */
        session: SessionId;
      };
    };
    responses: {
      /**
       * The thread.
       */
      '200': Thread;
      /**
       * The request is malformed, or a name, a parameter or the body is not valid.
       */
      '400': Error;
      /**
       * No token, a token GitHub does not accept, a service identity this deployment does not trust, or a webhook whose signature does not match.
       */
      '401': Error;
      /**
       * The caller is not a member of the project, or is the runner asking for something only a person may do.
       */
      '403': Error;
      /**
       * The project is not served here, or the message does not exist in it.
       */
      '404': Error;
      /**
       * GitHub (or Google's keys) could not be reached to identify the caller or check their access, so nothing is
       * answered; or this deployment is not configured yet, and only `/version` answers.
       *
       */
      '503': Error;
    };
  };
  /**
   * A page of a session thread's messages, oldest first. The runner reads the members' messages to a running
   * session with `after` set to the last `seq` it has seen.
   *
   */
  listSessionMessages: {
    request: {
      path: {
        /**
         * The owner of the project's repository. A project is keyed by its repository (command-center/D18).
         */
        owner: Login;
        /**
         * The name of the project's repository.
         */
        repo: string;
        /**
         * The runner's id for the session.
         */
        session: SessionId;
      };
      query?: {
        /**
         * Return only messages whose `seq` is greater than this. Omit it to start at the beginning.
         */
        after?: number;
        /**
         * The most messages to return.
         */
        limit?: number;
        /**
         * Return only messages of these kinds, for example `kind=milestone` to collapse a session thread.
         */
        kind?: Kind[];
      };
    };
    responses: {
      /**
       * A page of messages, oldest first.
       */
      '200': MessagePage;
      /**
       * The request is malformed, or a name, a parameter or the body is not valid.
       */
      '400': Error;
      /**
       * No token, a token GitHub does not accept, a service identity this deployment does not trust, or a webhook whose signature does not match.
       */
      '401': Error;
      /**
       * The caller is not a member of the project, or is the runner asking for something only a person may do.
       */
      '403': Error;
      /**
       * The project is not served here, or the message does not exist in it.
       */
      '404': Error;
      /**
       * GitHub (or Google's keys) could not be reached to identify the caller or check their access, so nothing is
       * answered; or this deployment is not configured yet, and only `/version` answers.
       *
       */
      '503': Error;
    };
  };
  /**
   * Post to a session's thread. A person posts as themselves. The runner posts as the session, and must name
   * the session's sponsor in `sponsor`; the first runner post sets the thread's sponsor, and a later one that
   * names a different sponsor is refused with 409.
   *
   */
  postSessionMessage: {
    request: {
      path: {
        /**
         * The owner of the project's repository. A project is keyed by its repository (command-center/D18).
         */
        owner: Login;
        /**
         * The name of the project's repository.
         */
        repo: string;
        /**
         * The runner's id for the session.
         */
        session: SessionId;
      };
      body: NewMessage;
    };
    responses: {
      /**
       * The message as stored.
       */
      '201': Message;
      /**
       * The request is malformed, or a name, a parameter or the body is not valid.
       */
      '400': Error;
      /**
       * No token, a token GitHub does not accept, a service identity this deployment does not trust, or a webhook whose signature does not match.
       */
      '401': Error;
      /**
       * The caller is not a member of the project, or is the runner asking for something only a person may do.
       */
      '403': Error;
      /**
       * The project is not served here, or the message does not exist in it.
       */
      '404': Error;
      /**
       * The runner named a sponsor other than the session's.
       */
      '409': Error;
      /**
       * GitHub (or Google's keys) could not be reached to identify the caller or check their access, so nothing is
       * answered; or this deployment is not configured yet, and only `/version` answers.
       *
       */
      '503': Error;
    };
  };
  /**
   * Watch a session's thread. Watching twice is the same as once.
   */
  watchSessionThread: {
    request: {
      path: {
        /**
         * The owner of the project's repository. A project is keyed by its repository (command-center/D18).
         */
        owner: Login;
        /**
         * The name of the project's repository.
         */
        repo: string;
        /**
         * The runner's id for the session.
         */
        session: SessionId;
      };
    };
    responses: {
      /**
       * The thread.
       */
      '200': Thread;
      /**
       * The request is malformed, or a name, a parameter or the body is not valid.
       */
      '400': Error;
      /**
       * No token, a token GitHub does not accept, a service identity this deployment does not trust, or a webhook whose signature does not match.
       */
      '401': Error;
      /**
       * The caller is not a member of the project, or is the runner asking for something only a person may do.
       */
      '403': Error;
      /**
       * The project is not served here, or the message does not exist in it.
       */
      '404': Error;
      /**
       * GitHub (or Google's keys) could not be reached to identify the caller or check their access, so nothing is
       * answered; or this deployment is not configured yet, and only `/version` answers.
       *
       */
      '503': Error;
    };
  };
  /**
   * Stop watching a session's thread.
   */
  unwatchSessionThread: {
    request: {
      path: {
        /**
         * The owner of the project's repository. A project is keyed by its repository (command-center/D18).
         */
        owner: Login;
        /**
         * The name of the project's repository.
         */
        repo: string;
        /**
         * The runner's id for the session.
         */
        session: SessionId;
      };
    };
    responses: {
      /**
       * The thread.
       */
      '200': Thread;
      /**
       * The request is malformed, or a name, a parameter or the body is not valid.
       */
      '400': Error;
      /**
       * No token, a token GitHub does not accept, a service identity this deployment does not trust, or a webhook whose signature does not match.
       */
      '401': Error;
      /**
       * The caller is not a member of the project, or is the runner asking for something only a person may do.
       */
      '403': Error;
      /**
       * The project is not served here, or the message does not exist in it.
       */
      '404': Error;
      /**
       * GitHub (or Google's keys) could not be reached to identify the caller or check their access, so nothing is
       * answered; or this deployment is not configured yet, and only `/version` answers.
       *
       */
      '503': Error;
    };
  };
  /**
   * One message, wherever it was posted, with its "record this?" marks.
   */
  getMessage: {
    request: {
      path: {
        /**
         * The owner of the project's repository. A project is keyed by its repository (command-center/D18).
         */
        owner: Login;
        /**
         * The name of the project's repository.
         */
        repo: string;
        /**
         * A message's `id`.
         */
        message: number;
      };
    };
    responses: {
      /**
       * The message.
       */
      '200': Message;
      /**
       * The request is malformed, or a name, a parameter or the body is not valid.
       */
      '400': Error;
      /**
       * No token, a token GitHub does not accept, a service identity this deployment does not trust, or a webhook whose signature does not match.
       */
      '401': Error;
      /**
       * The caller is not a member of the project, or is the runner asking for something only a person may do.
       */
      '403': Error;
      /**
       * The project is not served here, or the message does not exist in it.
       */
      '404': Error;
      /**
       * GitHub (or Google's keys) could not be reached to identify the caller or check their access, so nothing is
       * answered; or this deployment is not configured yet, and only `/version` answers.
       *
       */
      '503': Error;
    };
  };
  /**
   * Mark a message "record this?" as the signed-in person (command-center/D36). It changes nothing else: not
   * the message, not the thread, and not the repository. Marking twice is the same as once.
   *
   */
  markMessageForRecord: {
    request: {
      path: {
        /**
         * The owner of the project's repository. A project is keyed by its repository (command-center/D18).
         */
        owner: Login;
        /**
         * The name of the project's repository.
         */
        repo: string;
        /**
         * A message's `id`.
         */
        message: number;
      };
    };
    responses: {
      /**
       * The message.
       */
      '200': Message;
      /**
       * The request is malformed, or a name, a parameter or the body is not valid.
       */
      '400': Error;
      /**
       * No token, a token GitHub does not accept, a service identity this deployment does not trust, or a webhook whose signature does not match.
       */
      '401': Error;
      /**
       * The caller is not a member of the project, or is the runner asking for something only a person may do.
       */
      '403': Error;
      /**
       * The project is not served here, or the message does not exist in it.
       */
      '404': Error;
      /**
       * GitHub (or Google's keys) could not be reached to identify the caller or check their access, so nothing is
       * answered; or this deployment is not configured yet, and only `/version` answers.
       *
       */
      '503': Error;
    };
  };
  /**
   * Remove the signed-in person's own "record this?" mark from a message.
   */
  unmarkMessageForRecord: {
    request: {
      path: {
        /**
         * The owner of the project's repository. A project is keyed by its repository (command-center/D18).
         */
        owner: Login;
        /**
         * The name of the project's repository.
         */
        repo: string;
        /**
         * A message's `id`.
         */
        message: number;
      };
    };
    responses: {
      /**
       * The message.
       */
      '200': Message;
      /**
       * The request is malformed, or a name, a parameter or the body is not valid.
       */
      '400': Error;
      /**
       * No token, a token GitHub does not accept, a service identity this deployment does not trust, or a webhook whose signature does not match.
       */
      '401': Error;
      /**
       * The caller is not a member of the project, or is the runner asking for something only a person may do.
       */
      '403': Error;
      /**
       * The project is not served here, or the message does not exist in it.
       */
      '404': Error;
      /**
       * GitHub (or Google's keys) could not be reached to identify the caller or check their access, so nothing is
       * answered; or this deployment is not configured yet, and only `/version` answers.
       *
       */
      '503': Error;
    };
  };
}
export interface Version {
  /**
   * The commit SHA this deployment was built from, or `unknown` when it was not given one.
   */
  commit: string;
}
export interface Thread {
  /**
   * The project's key, its repository as `owner/repo`.
   */
  project: string;
  scope: 'loop' | 'concern' | 'session';
  /**
   * The thread's stable path on this service.
   */
  url: string;
  /**
   * The loop, for a loop or concern thread.
   */
  loop: string | null;
  /**
   * The concern, for a concern thread.
   */
  concern: string | null;
  /**
   * The session, for a session thread.
   */
  session: string | null;
  /**
   * For a session thread, the sponsor the runner named when it first posted; otherwise null.
   */
  sponsor: string | null;
  /**
   * The project's members, who may read, post and watch. They are the repository's collaborators.
   */
  members: Person[];
  /**
   * The members watching this thread.
   */
  watchers: Watcher[];
  /**
   * The `seq` of the thread's latest message, or 0 when it has none.
   */
  last_seq: number;
}
export interface Person {
  login: Login;
}
export interface Watcher {
  login: Login;
  since: string;
}
export interface Error {
  error: 'bad_request' | 'unauthorized' | 'forbidden' | 'not_found' | 'conflict' | 'unavailable' | 'internal';
  message: string;
}
export interface MessagePage {
  messages: Message[];
  /**
   * Pass this as `after` for the next page, or null when this page reached the newest message.
   */
  next_after: number | null;
}
export interface Message {
  /**
   * The message's id, unique in its project. It addresses the message under `/messages/{message}`.
   */
  id: number;
  /**
   * Its position in its thread, from 1. Each new message in a thread has a greater `seq` than every message already readable there.
   */
  seq: number;
  /**
   * The `url` of its thread.
   */
  thread: string;
  kind: Kind;
  author: PersonAuthor | SessionAuthor | GitHubAuthor;
  body: string;
  created_at: string;
  /**
   * The members who marked it "record this?", oldest first.
   */
  record_marks: RecordMark[];
  /**
   * For a message mirrored from GitHub, where it came from; otherwise null.
   */
  source: Source | null;
}
export interface PersonAuthor {
  type: 'person';
  login: Login;
}
export interface SessionAuthor {
  type: 'session';
  session: SessionId;
  sponsor: Login;
}
/**
 * Someone who commented on GitHub, mirrored here. They need not be a member: anyone may comment on a pull
 * request in a public repository. `association` is GitHub's `author_association`, such as `OWNER`,
 * `COLLABORATOR` or `NONE`.
 *
 */
export interface GitHubAuthor {
  type: 'github';
  login: string;
  association: string | null;
}
export interface RecordMark {
  login: Login;
  marked_at: string;
}
/**
 * Where a mirrored message came from.
 */
export interface Source {
  type: 'github_review' | 'github_review_comment';
  url: string;
  pull_request: number;
  /**
   * For a review comment, the file it is on.
   */
  path: string | null;
  /**
   * For a review, GitHub's state for it, such as `approved` or `changes_requested`.
   */
  review_state: string | null;
}
export interface NewMessage {
  body: string;
  /**
   * Defaults to `message`. Only a session may post a `milestone` or `narration`.
   */
  kind?: Kind & string;
  /**
   * Required from the runner and refused from a person. The login of the session's sponsor.
   */
  sponsor?: Login;
}

/**
 * The method, path and success statuses of each of the threads service's operations, which the client calls.
 */
export const THREADS_OPERATIONS: { readonly [Operation in keyof ThreadsOperations]: OperationSpec } = {
  getVersion: { method: 'GET', path: '/version', ok: { 200: 'json' } },
  getLoopThread: { method: 'GET', path: '/projects/{owner}/{repo}/loops/{loop}/thread', ok: { 200: 'json' } },
  listLoopMessages: {
    method: 'GET',
    path: '/projects/{owner}/{repo}/loops/{loop}/thread/messages',
    ok: { 200: 'json' },
  },
  postLoopMessage: {
    method: 'POST',
    path: '/projects/{owner}/{repo}/loops/{loop}/thread/messages',
    ok: { 201: 'json' },
  },
  watchLoopThread: {
    method: 'PUT',
    path: '/projects/{owner}/{repo}/loops/{loop}/thread/watchers/me',
    ok: { 200: 'json' },
  },
  unwatchLoopThread: {
    method: 'DELETE',
    path: '/projects/{owner}/{repo}/loops/{loop}/thread/watchers/me',
    ok: { 200: 'json' },
  },
  getConcernThread: {
    method: 'GET',
    path: '/projects/{owner}/{repo}/loops/{loop}/concerns/{concern}/thread',
    ok: { 200: 'json' },
  },
  listConcernMessages: {
    method: 'GET',
    path: '/projects/{owner}/{repo}/loops/{loop}/concerns/{concern}/thread/messages',
    ok: { 200: 'json' },
  },
  postConcernMessage: {
    method: 'POST',
    path: '/projects/{owner}/{repo}/loops/{loop}/concerns/{concern}/thread/messages',
    ok: { 201: 'json' },
  },
  watchConcernThread: {
    method: 'PUT',
    path: '/projects/{owner}/{repo}/loops/{loop}/concerns/{concern}/thread/watchers/me',
    ok: { 200: 'json' },
  },
  unwatchConcernThread: {
    method: 'DELETE',
    path: '/projects/{owner}/{repo}/loops/{loop}/concerns/{concern}/thread/watchers/me',
    ok: { 200: 'json' },
  },
  getSessionThread: { method: 'GET', path: '/projects/{owner}/{repo}/sessions/{session}/thread', ok: { 200: 'json' } },
  listSessionMessages: {
    method: 'GET',
    path: '/projects/{owner}/{repo}/sessions/{session}/thread/messages',
    ok: { 200: 'json' },
  },
  postSessionMessage: {
    method: 'POST',
    path: '/projects/{owner}/{repo}/sessions/{session}/thread/messages',
    ok: { 201: 'json' },
  },
  watchSessionThread: {
    method: 'PUT',
    path: '/projects/{owner}/{repo}/sessions/{session}/thread/watchers/me',
    ok: { 200: 'json' },
  },
  unwatchSessionThread: {
    method: 'DELETE',
    path: '/projects/{owner}/{repo}/sessions/{session}/thread/watchers/me',
    ok: { 200: 'json' },
  },
  getMessage: { method: 'GET', path: '/projects/{owner}/{repo}/messages/{message}', ok: { 200: 'json' } },
  markMessageForRecord: {
    method: 'PUT',
    path: '/projects/{owner}/{repo}/messages/{message}/record-marks/me',
    ok: { 200: 'json' },
  },
  unmarkMessageForRecord: {
    method: 'DELETE',
    path: '/projects/{owner}/{repo}/messages/{message}/record-marks/me',
    ok: { 200: 'json' },
  },
};

/**
 * The threads service's client, generated from services/threads/openapi.yaml: one method per operation
 * the app calls. Each call goes through the signed-in fetch the client was made with, to the base URL it was
 * made with, and resolves to the body of a success response. Any other answer rejects with a ServiceError
 * (service.ts) that carries the status and the body, typed for each status in ThreadsOperations. A client made with
 * no base URL never calls the service: each method rejects with a 'not-configured' ServiceError that says
 * which URL the build is missing.
 */
export interface ThreadsClient {
  /**
   * The commit this deployment was built from (command-center/D32).
   *
   * `GET /version`
   */
  getVersion(): Promise<ThreadsOperations['getVersion']['responses']['200']>;
  /**
   * A loop's thread, with its members and watchers.
   *
   * `GET /projects/{owner}/{repo}/loops/{loop}/thread`
   */
  getLoopThread(
    request: ThreadsOperations['getLoopThread']['request'],
  ): Promise<ThreadsOperations['getLoopThread']['responses']['200']>;
  /**
   * A page of a loop thread's messages, oldest first.
   *
   * `GET /projects/{owner}/{repo}/loops/{loop}/thread/messages`
   */
  listLoopMessages(
    request: ThreadsOperations['listLoopMessages']['request'],
  ): Promise<ThreadsOperations['listLoopMessages']['responses']['200']>;
  /**
   * Post a message to a loop's thread, as the signed-in person.
   *
   * `POST /projects/{owner}/{repo}/loops/{loop}/thread/messages`
   */
  postLoopMessage(
    request: ThreadsOperations['postLoopMessage']['request'],
  ): Promise<ThreadsOperations['postLoopMessage']['responses']['201']>;
  /**
   * Watch a loop's thread. Watching twice is the same as once.
   *
   * `PUT /projects/{owner}/{repo}/loops/{loop}/thread/watchers/me`
   */
  watchLoopThread(
    request: ThreadsOperations['watchLoopThread']['request'],
  ): Promise<ThreadsOperations['watchLoopThread']['responses']['200']>;
  /**
   * Stop watching a loop's thread.
   *
   * `DELETE /projects/{owner}/{repo}/loops/{loop}/thread/watchers/me`
   */
  unwatchLoopThread(
    request: ThreadsOperations['unwatchLoopThread']['request'],
  ): Promise<ThreadsOperations['unwatchLoopThread']['responses']['200']>;
  /**
   * A concern's thread, with its members and watchers.
   *
   * `GET /projects/{owner}/{repo}/loops/{loop}/concerns/{concern}/thread`
   */
  getConcernThread(
    request: ThreadsOperations['getConcernThread']['request'],
  ): Promise<ThreadsOperations['getConcernThread']['responses']['200']>;
  /**
   * A page of a concern thread's messages, oldest first, including mirrored review comments.
   *
   * `GET /projects/{owner}/{repo}/loops/{loop}/concerns/{concern}/thread/messages`
   */
  listConcernMessages(
    request: ThreadsOperations['listConcernMessages']['request'],
  ): Promise<ThreadsOperations['listConcernMessages']['responses']['200']>;
  /**
   * Post a message to a concern's thread, as the signed-in person.
   *
   * `POST /projects/{owner}/{repo}/loops/{loop}/concerns/{concern}/thread/messages`
   */
  postConcernMessage(
    request: ThreadsOperations['postConcernMessage']['request'],
  ): Promise<ThreadsOperations['postConcernMessage']['responses']['201']>;
  /**
   * Watch a concern's thread. Watching twice is the same as once.
   *
   * `PUT /projects/{owner}/{repo}/loops/{loop}/concerns/{concern}/thread/watchers/me`
   */
  watchConcernThread(
    request: ThreadsOperations['watchConcernThread']['request'],
  ): Promise<ThreadsOperations['watchConcernThread']['responses']['200']>;
  /**
   * Stop watching a concern's thread.
   *
   * `DELETE /projects/{owner}/{repo}/loops/{loop}/concerns/{concern}/thread/watchers/me`
   */
  unwatchConcernThread(
    request: ThreadsOperations['unwatchConcernThread']['request'],
  ): Promise<ThreadsOperations['unwatchConcernThread']['responses']['200']>;
  /**
   * A session's thread, with its sponsor, members and watchers.
   *
   * `GET /projects/{owner}/{repo}/sessions/{session}/thread`
   */
  getSessionThread(
    request: ThreadsOperations['getSessionThread']['request'],
  ): Promise<ThreadsOperations['getSessionThread']['responses']['200']>;
  /**
   * A page of a session thread's messages, oldest first. The runner reads the members' messages to a running
   * session with `after` set to the last `seq` it has seen.
   *
   * `GET /projects/{owner}/{repo}/sessions/{session}/thread/messages`
   */
  listSessionMessages(
    request: ThreadsOperations['listSessionMessages']['request'],
  ): Promise<ThreadsOperations['listSessionMessages']['responses']['200']>;
  /**
   * Post to a session's thread. A person posts as themselves. The runner posts as the session, and must name
   * the session's sponsor in `sponsor`; the first runner post sets the thread's sponsor, and a later one that
   * names a different sponsor is refused with 409.
   *
   * `POST /projects/{owner}/{repo}/sessions/{session}/thread/messages`
   */
  postSessionMessage(
    request: ThreadsOperations['postSessionMessage']['request'],
  ): Promise<ThreadsOperations['postSessionMessage']['responses']['201']>;
  /**
   * Watch a session's thread. Watching twice is the same as once.
   *
   * `PUT /projects/{owner}/{repo}/sessions/{session}/thread/watchers/me`
   */
  watchSessionThread(
    request: ThreadsOperations['watchSessionThread']['request'],
  ): Promise<ThreadsOperations['watchSessionThread']['responses']['200']>;
  /**
   * Stop watching a session's thread.
   *
   * `DELETE /projects/{owner}/{repo}/sessions/{session}/thread/watchers/me`
   */
  unwatchSessionThread(
    request: ThreadsOperations['unwatchSessionThread']['request'],
  ): Promise<ThreadsOperations['unwatchSessionThread']['responses']['200']>;
  /**
   * One message, wherever it was posted, with its "record this?" marks.
   *
   * `GET /projects/{owner}/{repo}/messages/{message}`
   */
  getMessage(
    request: ThreadsOperations['getMessage']['request'],
  ): Promise<ThreadsOperations['getMessage']['responses']['200']>;
  /**
   * Mark a message "record this?" as the signed-in person (command-center/D36). It changes nothing else: not
   * the message, not the thread, and not the repository. Marking twice is the same as once.
   *
   * `PUT /projects/{owner}/{repo}/messages/{message}/record-marks/me`
   */
  markMessageForRecord(
    request: ThreadsOperations['markMessageForRecord']['request'],
  ): Promise<ThreadsOperations['markMessageForRecord']['responses']['200']>;
  /**
   * Remove the signed-in person's own "record this?" mark from a message.
   *
   * `DELETE /projects/{owner}/{repo}/messages/{message}/record-marks/me`
   */
  unmarkMessageForRecord(
    request: ThreadsOperations['unmarkMessageForRecord']['request'],
  ): Promise<ThreadsOperations['unmarkMessageForRecord']['responses']['200']>;
}

/**
 * Makes the threads service's client from this build's URL for it (AppConfig.threadsUrl, null while the
 * build has none) and the signed-in fetch (useSignedInFetch).
 */
export function createThreadsClient(options: ServiceClientOptions): ThreadsClient {
  const call = operationCaller('threads', THREADS_OPERATIONS, options);
  return {
    getVersion: () => call<ThreadsOperations['getVersion']['responses']['200']>('getVersion'),
    getLoopThread: (request) => call<ThreadsOperations['getLoopThread']['responses']['200']>('getLoopThread', request),
    listLoopMessages: (request) =>
      call<ThreadsOperations['listLoopMessages']['responses']['200']>('listLoopMessages', request),
    postLoopMessage: (request) =>
      call<ThreadsOperations['postLoopMessage']['responses']['201']>('postLoopMessage', request),
    watchLoopThread: (request) =>
      call<ThreadsOperations['watchLoopThread']['responses']['200']>('watchLoopThread', request),
    unwatchLoopThread: (request) =>
      call<ThreadsOperations['unwatchLoopThread']['responses']['200']>('unwatchLoopThread', request),
    getConcernThread: (request) =>
      call<ThreadsOperations['getConcernThread']['responses']['200']>('getConcernThread', request),
    listConcernMessages: (request) =>
      call<ThreadsOperations['listConcernMessages']['responses']['200']>('listConcernMessages', request),
    postConcernMessage: (request) =>
      call<ThreadsOperations['postConcernMessage']['responses']['201']>('postConcernMessage', request),
    watchConcernThread: (request) =>
      call<ThreadsOperations['watchConcernThread']['responses']['200']>('watchConcernThread', request),
    unwatchConcernThread: (request) =>
      call<ThreadsOperations['unwatchConcernThread']['responses']['200']>('unwatchConcernThread', request),
    getSessionThread: (request) =>
      call<ThreadsOperations['getSessionThread']['responses']['200']>('getSessionThread', request),
    listSessionMessages: (request) =>
      call<ThreadsOperations['listSessionMessages']['responses']['200']>('listSessionMessages', request),
    postSessionMessage: (request) =>
      call<ThreadsOperations['postSessionMessage']['responses']['201']>('postSessionMessage', request),
    watchSessionThread: (request) =>
      call<ThreadsOperations['watchSessionThread']['responses']['200']>('watchSessionThread', request),
    unwatchSessionThread: (request) =>
      call<ThreadsOperations['unwatchSessionThread']['responses']['200']>('unwatchSessionThread', request),
    getMessage: (request) => call<ThreadsOperations['getMessage']['responses']['200']>('getMessage', request),
    markMessageForRecord: (request) =>
      call<ThreadsOperations['markMessageForRecord']['responses']['200']>('markMessageForRecord', request),
    unmarkMessageForRecord: (request) =>
      call<ThreadsOperations['unmarkMessageForRecord']['responses']['200']>('unmarkMessageForRecord', request),
  };
}
