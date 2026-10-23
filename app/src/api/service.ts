// What every generated service client (<service>.gen.ts, from generate-clients.js) calls with: it builds an
// operation's URL from the build's base URL for the service, sends the call through the signed-in fetch (fetch.ts),
// and turns the answer into the success body or a ServiceError (command-center/D55). A client made with no base URL
// never calls its service and says which URL the build is missing instead.

import type { Fetch } from './fetch';
import type { ProjectKey } from './status';

/** How a generated client calls one operation: its method, its path template, and its success statuses. */
export type OperationSpec = {
  readonly method: 'GET' | 'PUT' | 'POST' | 'DELETE' | 'PATCH';
  /** The path as the OpenAPI file writes it, such as /sessions/{id}. */
  readonly path: string;
  /** Each success status, and whether it answers a JSON body or nothing. */
  readonly ok: { readonly [status: number]: 'json' | 'empty' };
};

/** An operation's request, shaped as the generated <Service>Operations types shape it. */
export type OperationRequest = {
  readonly path?: object;
  readonly query?: object;
  readonly body?: unknown;
};

export type ServiceClientOptions = {
  /**
   * The service's URL for this build's environment, such as https://runner-<number>.us-east1.run.app, from the
   * build's config. Null or undefined when the build has none yet: the client then calls nothing.
   */
  baseUrl: string | null | undefined;
  /** The signed-in fetch (fetch.ts), which adds the person's token. */
  fetch: Fetch;
};

export type ServiceErrorKind = 'not-configured' | 'http' | 'not-json';

/**
 * Why a call did not resolve to a success body. For 'http', `status` is the service's answer and `body` its parsed
 * JSON body (null when it had none), typed for each status in the client's <Service>Operations.
 */
export class ServiceError extends Error {
  readonly service: string;
  readonly operation: string;
  readonly kind: ServiceErrorKind;
  readonly status: number | undefined;
  readonly body: unknown;

  constructor(
    service: string,
    operation: string,
    kind: ServiceErrorKind,
    message: string,
    { status, body = null }: { status?: number; body?: unknown } = {},
  ) {
    super(message);
    this.name = 'ServiceError';
    this.service = service;
    this.operation = operation;
    this.kind = kind;
    this.status = status;
    this.body = body;
  }
}

/** The variable that gives a build its URL for a service, as app/eas.json sets it per build profile. */
export function serviceUrlVariable(service: string): string {
  return `EXPO_PUBLIC_${service.toUpperCase().replace(/-/g, '_')}_URL`;
}

/** What the app says, instead of calling a service, when its build has no URL for it. */
export function serviceNotConfiguredMessage(service: string): string {
  return (
    `This build has no URL for the ${service} service yet, so the app does not call it. The owner sets ` +
    `${serviceUrlVariable(service)} in app/eas.json, in this build's profile.`
  );
}

/** The {owner}/{repo} path parameters every service keys a project by (command-center/D48). */
export function projectPath(project: ProjectKey): { owner: string; repo: string } {
  const [owner, repo, ...rest] = project.split('/');
  if (!owner || !repo || rest.length) throw new Error(`A project is owner/repo, not ${project}`);
  return { owner, repo };
}

type QueryValue = string | number | boolean;

function queryString(query: object | undefined): string {
  const parts: string[] = [];
  for (const [name, value] of Object.entries(query ?? {})) {
    if (value === undefined || value === null) continue;
    // The OpenAPI default for a query parameter, form style exploded: an array repeats its name.
    for (const item of (Array.isArray(value) ? value : [value]) as QueryValue[]) {
      parts.push(`${encodeURIComponent(name)}=${encodeURIComponent(String(item))}`);
    }
  }
  return parts.length ? `?${parts.join('&')}` : '';
}

/** The URL of one call: the base URL, the path with each {parameter} filled in and encoded, and the query. */
export function operationUrl(baseUrl: string, spec: OperationSpec, request: OperationRequest = {}): string {
  const values = (request.path ?? {}) as Record<string, unknown>;
  const path = spec.path.replace(/\{([^}]+)\}/g, (_, name: string) => {
    const value = values[name];
    if (value === undefined || value === null || value === '') {
      throw new Error(`${spec.method} ${spec.path} needs its ${name} path parameter`);
    }
    return encodeURIComponent(String(value));
  });
  return `${baseUrl.replace(/\/+$/, '')}${path}${queryString(request.query)}`;
}

async function readBody(response: Response): Promise<unknown> {
  try {
    return await response.json();
  } catch {
    return null;
  }
}

function problemMessage(body: unknown): string {
  const message = (body as { message?: unknown } | null)?.message;
  return typeof message === 'string' && message ? `: ${message}` : '';
}

/**
 * Binds a generated client's operation table to a base URL and the signed-in fetch. The generated client gives
 * each call its success type; this checks the answer's status against the table, not its body against the schema.
 */
export function operationCaller<Operation extends string>(
  service: string,
  operations: { readonly [name in Operation]: OperationSpec },
  { baseUrl, fetch }: ServiceClientOptions,
) {
  return async function call<Success>(operation: Operation, request?: OperationRequest): Promise<Success> {
    const spec = operations[operation];
    if (!baseUrl) {
      throw new ServiceError(service, operation, 'not-configured', serviceNotConfiguredMessage(service));
    }
    const url = operationUrl(baseUrl, spec, request);
    const headers: Record<string, string> = { Accept: 'application/json' };
    const init: RequestInit = { method: spec.method, headers };
    if (request?.body !== undefined) {
      headers['Content-Type'] = 'application/json';
      init.body = JSON.stringify(request.body);
    }
    const response = await fetch(url, init);
    const answers = spec.ok[response.status];
    if (answers === undefined) {
      const body = await readBody(response);
      throw new ServiceError(
        service,
        operation,
        'http',
        `${spec.method} ${url} answered ${response.status}${problemMessage(body)}`,
        { status: response.status, body },
      );
    }
    if (answers === 'empty') return undefined as Success;
    try {
      return (await response.json()) as Success;
    } catch {
      throw new ServiceError(service, operation, 'not-json', `${spec.method} ${url} did not answer JSON`, {
        status: response.status,
      });
    }
  };
}
