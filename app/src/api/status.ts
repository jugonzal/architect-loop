// The status client: reads a project's status document from the status service, which serves exactly what the
// loop-status script writes with --json (command-center/D15), at GET /projects/{owner}/{repo}/status
// (command-center/D48). The types are generated from the schema in status.gen.ts; this file adds only the call
// and the checks a reader must make before trusting a document.

import type { Fetch } from './fetch';
import type { LoopStatus } from './status.gen';

export type * from './status.gen';

/** The status document, as the schema's title names it (LoopStatus). */
export type StatusDocument = LoopStatus;

/**
 * The schema version this build reads. The schema raises its version whenever a change would make a reader of
 * the previous one misread a document, so a build refuses any other version instead of guessing.
 */
export const SUPPORTED_SCHEMA_VERSION = 1;

export type StatusErrorKind = 'http' | 'not-json' | 'schema-version' | 'project';

export class StatusError extends Error {
  readonly kind: StatusErrorKind;
  readonly status: number | undefined;

  constructor(kind: StatusErrorKind, message: string, status?: number) {
    super(message);
    this.name = 'StatusError';
    this.kind = kind;
    this.status = status;
  }
}

/** A project key, owner/repo (command-center/D18). */
export type ProjectKey = `${string}/${string}`;

export function statusUrl(baseUrl: string, project: ProjectKey): string {
  const [owner, repo] = project.split('/');
  if (!owner || !repo) throw new Error(`A project is owner/repo, not ${project}`);
  return `${baseUrl.replace(/\/+$/, '')}/projects/${encodeURIComponent(owner)}/${encodeURIComponent(repo)}/status`;
}

/**
 * Checks what the schema says every reader must check before using a document: that it is for the schema
 * version this build reads, and for the project that was asked for. Everything else is the schema's to promise.
 */
export function parseStatus(value: unknown, project: ProjectKey): StatusDocument {
  if (typeof value !== 'object' || value === null || Array.isArray(value)) {
    throw new StatusError('not-json', 'The status document is not a JSON object');
  }
  const doc = value as { schema_version?: unknown; project?: unknown };
  if (doc.schema_version !== SUPPORTED_SCHEMA_VERSION) {
    throw new StatusError(
      'schema-version',
      `The status document is schema version ${String(doc.schema_version)}; this build reads version ` +
        `${SUPPORTED_SCHEMA_VERSION}. Update the app.`,
    );
  }
  if (doc.project !== project) {
    throw new StatusError('project', `Asked for ${project}, got a status document for ${String(doc.project)}`);
  }
  return value as StatusDocument;
}

export type StatusClient = {
  readonly project: ProjectKey;
  getStatus(): Promise<StatusDocument>;
};

export type StatusClientOptions = {
  /** The status service's URL for this build's environment, such as https://status-<number>.us-east1.run.app. */
  baseUrl: string;
  project: ProjectKey;
  /** The signed-in fetch (fetch.ts). */
  fetch: Fetch;
};

export function createStatusClient({ baseUrl, project, fetch }: StatusClientOptions): StatusClient {
  const url = statusUrl(baseUrl, project);
  return {
    project,
    async getStatus() {
      const response = await fetch(url, { headers: { Accept: 'application/json' } });
      if (!response.ok) {
        throw new StatusError('http', `GET ${url} answered ${response.status}`, response.status);
      }
      let body: unknown;
      try {
        body = await response.json();
      } catch {
        throw new StatusError('not-json', `GET ${url} did not answer JSON`, response.status);
      }
      return parseStatus(body, project);
    },
  };
}
