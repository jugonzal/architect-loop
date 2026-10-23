#!/usr/bin/env node
// Generates the app's typed client for each command center service it calls, src/api/<service>.gen.ts, from that
// service's OpenAPI file, services/<service>/openapi.yaml (command-center/D55). The OpenAPI file is the source of
// truth: change it, run `npm run generate:clients`, and commit both in the same change. `npm run check:clients`,
// and the test beside this file, fail when a committed client no longer matches its file.
//
// Each generated file holds the service's types (compiled with json-schema-to-typescript, as the status types are),
// a table of its operations' methods and paths, and a client with one method per operation. The client calls
// through the signed-in fetch (fetch.ts) by way of service.ts, so a screen only calls a method.
//
// Plain Node (CommonJS), so it runs without a TypeScript toolchain. Metro never bundles it: nothing in the app
// imports it.
'use strict';

const fs = require('fs');
const path = require('path');
const YAML = require('yaml');
const { compile } = require('json-schema-to-typescript');
// The prettier json-schema-to-typescript formats with, so the types and the client share one style and one version.
const prettier = require(
  require.resolve('prettier', { paths: [path.dirname(require.resolve('json-schema-to-typescript'))] }),
);

const STYLE = { parser: 'typescript', singleQuote: true, printWidth: 120, bracketSpacing: true, trailingComma: 'all' };

const REPO = path.resolve(__dirname, '../../..');
const API_DIR = __dirname;

/**
 * The services the app has a generated client for. Each one's client is generated once its OpenAPI file exists, so
 * `notify` is listed before its API is: `notifications` writes services/notify/openapi.yaml and generates
 * src/api/notify.gen.ts with this script (command-center/D55). The status service is not listed: its types come
 * from the status schema, by generate-status-types.js (command-center/D15).
 *
 * `skip` names the operations the app never calls, each with the reason; every other operation is a method.
 */
const SERVICES = {
  runner: { skip: {} },
  threads: {
    skip: {
      receiveGitHubWebhook: 'GitHub calls it, with a delivery signed with the webhook secret; the app never does.',
    },
  },
  notify: { skip: {} },
};

const METHODS = ['get', 'put', 'post', 'delete', 'patch'];
const JSON_TYPE = 'application/json';

function specPath(service, repo = REPO) {
  return path.join(repo, 'services', service, 'openapi.yaml');
}

function outputPath(service, apiDir = API_DIR) {
  return path.join(apiDir, `${service}.gen.ts`);
}

function pascal(name) {
  return name.replace(/(^|[-_])([a-z0-9])/g, (_, __, c) => c.toUpperCase());
}

function unsupported(service, where, what) {
  return new Error(`services/${service}/openapi.yaml, ${where}: ${what} is not supported by generate-clients.js`);
}

/** Follows a local $ref into components (parameters, responses, request bodies), as many times as it takes. */
function resolve(spec, value, service, where) {
  let current = value;
  for (let hops = 0; current && typeof current.$ref === 'string'; hops += 1) {
    const match = /^#\/components\/(parameters|responses|requestBodies)\/([^/]+)$/.exec(current.$ref);
    if (!match || hops > 10) throw unsupported(service, where, `the $ref ${current.$ref}`);
    current = spec.components?.[match[1]]?.[match[2]];
    if (!current) throw new Error(`services/${service}/openapi.yaml, ${where}: ${value.$ref} does not exist`);
  }
  return current;
}

/** A deep copy of a schema whose refs to components/schemas point at $defs, where json-schema-to-typescript looks. */
function rewriteRefs(schema, service, where) {
  if (Array.isArray(schema)) return schema.map((item) => rewriteRefs(item, service, where));
  if (!schema || typeof schema !== 'object') return schema;
  const copy = {};
  for (const [key, value] of Object.entries(schema)) {
    if (key === '$ref') {
      const match = /^#\/components\/schemas\/([^/]+)$/.exec(value);
      if (!match) throw unsupported(service, where, `the schema $ref ${value}`);
      copy.$ref = `#/$defs/${match[1]}`;
    } else {
      copy[key] = rewriteRefs(value, service, where);
    }
  }
  return copy;
}

/**
 * Makes `required` inside a oneOf or anyOf branch mean what JSON Schema says it means. A branch such as
 * `{required: [concern]}` beside the parent's `properties.concern` requires that property in that branch, but
 * json-schema-to-typescript types a branch only from its own properties, so the branch is given the parent's
 * schema for each property it requires. Without this, a dispatch that names no concern, loop or environment would
 * type-check (command-center/runner-dispatch C3).
 */
function normalizeBranches(schema) {
  if (Array.isArray(schema)) return schema.map(normalizeBranches);
  if (!schema || typeof schema !== 'object') return schema;
  const copy = {};
  for (const [key, value] of Object.entries(schema)) copy[key] = normalizeBranches(value);
  for (const keyword of ['oneOf', 'anyOf']) {
    if (!Array.isArray(copy[keyword]) || !copy.properties) continue;
    copy[keyword] = copy[keyword].map((branch) => {
      if (!branch || typeof branch !== 'object' || !Array.isArray(branch.required)) return branch;
      const properties = { ...(branch.properties || {}) };
      for (const name of branch.required) {
        if (!(name in properties) && name in copy.properties) properties[name] = copy.properties[name];
      }
      return { ...branch, properties };
    });
  }
  return copy;
}

function withDescription(schema, description) {
  if (!description) return schema;
  // A sibling of $ref would make json-schema-to-typescript inline the referenced type instead of naming it.
  return schema.$ref ? { description, allOf: [schema] } : { ...schema, description };
}

function objectSchema(properties, required) {
  return { type: 'object', additionalProperties: false, required, properties };
}

/** Every operation of the file, in the order it declares them, as the generator needs them. */
function operationsOf(service, spec, skip = {}) {
  const operations = [];
  const seen = new Set();
  for (const [route, item] of Object.entries(spec.paths || {})) {
    for (const method of Object.keys(item)) {
      if (!METHODS.includes(method)) {
        if (method !== 'parameters' && method !== 'summary' && method !== 'description') {
          throw unsupported(service, route, `the path item field ${method}`);
        }
        continue;
      }
      const op = item[method];
      const where = `${method.toUpperCase()} ${route}`;
      const id = op.operationId;
      if (!id) throw unsupported(service, where, 'an operation without an operationId');
      if (seen.has(id)) throw new Error(`services/${service}/openapi.yaml: operationId ${id} is used twice`);
      seen.add(id);
      if (id in skip) continue;

      const params = new Map();
      for (const raw of [...(item.parameters || []), ...(op.parameters || [])]) {
        const param = resolve(spec, raw, service, where);
        params.set(`${param.in}:${param.name}`, param);
      }
      const pathParams = [];
      const queryParams = [];
      for (const param of params.values()) {
        if (param.in === 'path') pathParams.push(param);
        else if (param.in === 'query') {
          if ((param.style && param.style !== 'form') || param.explode === false) {
            throw unsupported(service, where, `the query parameter style of ${param.name}`);
          }
          queryParams.push(param);
        } else throw unsupported(service, where, `the ${param.in} parameter ${param.name}`);
      }
      const templated = [...route.matchAll(/\{([^}]+)\}/g)].map((m) => m[1]);
      const named = pathParams.map((p) => p.name);
      if (templated.length !== named.length || templated.some((name) => !named.includes(name))) {
        throw new Error(`services/${service}/openapi.yaml, ${where}: its path parameters do not match its path`);
      }

      let body = null;
      if (op.requestBody) {
        const requestBody = resolve(spec, op.requestBody, service, where);
        const types = Object.keys(requestBody.content || {});
        if (types.length !== 1 || types[0] !== JSON_TYPE) {
          throw unsupported(service, where, `a request body of ${types.join(', ') || 'no content'}`);
        }
        body = { schema: requestBody.content[JSON_TYPE].schema || {}, required: requestBody.required === true };
      }

      const responses = [];
      for (const [status, raw] of Object.entries(op.responses || {})) {
        if (!/^[1-5][0-9][0-9]$/.test(status)) throw unsupported(service, where, `the response ${status}`);
        const response = resolve(spec, raw, service, `${where} ${status}`);
        const types = Object.keys(response.content || {});
        if (types.length > 1 || (types.length === 1 && types[0] !== JSON_TYPE)) {
          throw unsupported(service, `${where} ${status}`, `a response of ${types.join(', ')}`);
        }
        responses.push({
          status,
          description: response.description,
          schema: types.length ? response.content[JSON_TYPE].schema || {} : null,
        });
      }
      if (!responses.some((r) => r.status.startsWith('2'))) {
        throw new Error(`services/${service}/openapi.yaml, ${where}: it declares no success response`);
      }
      operations.push({ id, method: method.toUpperCase(), route, op, pathParams, queryParams, body, responses });
    }
  }
  return operations;
}

/** The schema json-schema-to-typescript compiles: each operation's request and its responses' bodies by status. */
function operationsSchema(service, spec, operations, typeName) {
  const properties = {};
  for (const operation of operations) {
    const where = `${operation.method} ${operation.route}`;
    const params = (list) =>
      Object.fromEntries(list.map((p) => [p.name, withDescription(rewriteRefs(p.schema || {}, service, where), p.description)]));
    const request = {};
    const requestRequired = [];
    if (operation.pathParams.length) {
      request.path = objectSchema(params(operation.pathParams), operation.pathParams.map((p) => p.name));
      requestRequired.push('path');
    }
    if (operation.queryParams.length) {
      const required = operation.queryParams.filter((p) => p.required).map((p) => p.name);
      request.query = objectSchema(params(operation.queryParams), required);
      if (required.length) requestRequired.push('query');
    }
    if (operation.body) {
      request.body = rewriteRefs(operation.body.schema, service, where);
      if (operation.body.required) requestRequired.push('body');
    }
    const entry = { description: operation.op.summary, required: ['responses'], properties: {} };
    if (Object.keys(request).length) {
      entry.properties.request = objectSchema(request, requestRequired);
      if (requestRequired.length) entry.required.push('request');
    }
    entry.properties.responses = objectSchema(
      Object.fromEntries(
        operation.responses.map((r) => [
          r.status,
          withDescription(r.schema ? rewriteRefs(r.schema, service, where) : { type: 'null' }, r.description),
        ]),
      ),
      operation.responses.map((r) => r.status),
    );
    properties[operation.id] = { type: 'object', additionalProperties: false, ...entry };
  }
  const schemas = {};
  for (const [name, schema] of Object.entries(spec.components?.schemas || {})) {
    schemas[name] = rewriteRefs(schema, service, `components.schemas.${name}`);
  }
  return normalizeBranches({
    title: typeName,
    description:
      `The ${service} service's operations, as services/${service}/openapi.yaml (version ${spec.info?.version}) ` +
      "declares them: each one's request, and its responses' bodies by status.",
    ...objectSchema(properties, operations.map((o) => o.id)),
    $defs: schemas,
  });
}

/** A doc comment of these lines; text from the OpenAPI file cannot end it early. */
function comment(text, indent = '') {
  const lines = text.trimEnd().replace(/\*\//g, '*\\/').split('\n');
  return [`${indent}/**`, ...lines.map((line) => `${indent} * ${line}`.trimEnd()), `${indent} */`].join('\n');
}

/** What the client needs of an operation: its success type, and whether it takes a request and must be given one. */
function signature(operation, types) {
  const success = operation.responses
    .filter((r) => r.status.startsWith('2'))
    .map((r) => `${types}['${operation.id}']['responses']['${r.status}']`)
    .join(' | ');
  const takesRequest = Boolean(operation.pathParams.length || operation.queryParams.length || operation.body);
  const needsRequest = Boolean(
    operation.pathParams.length || operation.queryParams.some((p) => p.required) || operation.body?.required,
  );
  return { success, takesRequest, needsRequest };
}

function clientSource(service, operations, names) {
  const { types, table, client, factory } = names;
  const lines = [
    comment(`The method, path and success statuses of each of the ${service} service's operations, which the client calls.`),
    `export const ${table}: { readonly [Operation in keyof ${types}]: OperationSpec } = {`,
  ];
  for (const operation of operations) {
    const ok = operation.responses
      .filter((r) => r.status.startsWith('2'))
      .map((r) => `${r.status}: '${r.schema ? 'json' : 'empty'}'`)
      .join(', ');
    lines.push(`  ${operation.id}: { method: '${operation.method}', path: ${JSON.stringify(operation.route)}, ok: { ${ok} } },`);
  }
  lines.push('};', '');

  lines.push(
    comment(
      `The ${service} service's client, generated from services/${service}/openapi.yaml: one method per operation\n` +
        'the app calls. Each call goes through the signed-in fetch the client was made with, to the base URL it was\n' +
        'made with, and resolves to the body of a success response. Any other answer rejects with a ServiceError\n' +
        `(service.ts) that carries the status and the body, typed for each status in ${types}. A client made with\n` +
        "no base URL never calls the service: each method rejects with a 'not-configured' ServiceError that says\n" +
        'which URL the build is missing.',
    ),
    `export interface ${client} {`,
  );
  for (const operation of operations) {
    const { success, takesRequest, needsRequest } = signature(operation, types);
    const summary = (operation.op.summary || operation.id).trim();
    const description = (operation.op.description || '').trim();
    lines.push(
      comment([summary, description, `\`${operation.method} ${operation.route}\``].filter(Boolean).join('\n\n'), '  '),
    );
    const parameter = takesRequest ? `request${needsRequest ? '' : '?'}: ${types}['${operation.id}']['request']` : '';
    lines.push(`  ${operation.id}(${parameter}): Promise<${success}>;`);
  }
  lines.push('}', '');

  lines.push(
    comment(
      `Makes the ${service} service's client from this build's URL for it (AppConfig.${service}Url, null while the\n` +
        'build has none) and the signed-in fetch (useSignedInFetch).',
    ),
    `export function ${factory}(options: ServiceClientOptions): ${client} {`,
    `  const call = operationCaller('${service}', ${table}, options);`,
    '  return {',
  );
  for (const operation of operations) {
    const { success, takesRequest } = signature(operation, types);
    lines.push(
      takesRequest
        ? `    ${operation.id}: (request) => call<${success}>('${operation.id}', request),`
        : `    ${operation.id}: () => call<${success}>('${operation.id}'),`,
    );
  }
  lines.push('  };', '}', '');
  return lines.join('\n');
}

/** The source of src/api/<service>.gen.ts, from the OpenAPI file at `repo`'s services/<service>/openapi.yaml. */
async function generate(service, { repo = REPO } = {}) {
  const config = SERVICES[service];
  if (!config) throw new Error(`generate-clients.js has no service ${service}; it knows ${Object.keys(SERVICES).join(', ')}`);
  const spec = YAML.parse(fs.readFileSync(specPath(service, repo), 'utf8'));
  if (!/^3\.1\./.test(String(spec.openapi))) {
    throw unsupported(service, 'openapi', `OpenAPI ${spec.openapi} (only 3.1 is)`);
  }
  const base = pascal(service);
  const names = {
    types: `${base}Operations`,
    table: `${service.toUpperCase().replace(/-/g, '_')}_OPERATIONS`,
    client: `${base}Client`,
    factory: `create${base}Client`,
  };
  const operations = operationsOf(service, spec, config.skip);
  const skipped = Object.entries(config.skip);
  const banner = [
    '/* eslint-disable */',
    `// Generated from services/${service}/openapi.yaml by src/api/generate-clients.js.`,
    '// Do not edit by hand: change the OpenAPI file, then run `npm run generate:clients` (command-center/D55).',
    ...skipped.map(([id, reason]) => `// Not a method here: ${id}. ${reason}`),
    '',
    "import { operationCaller, type OperationSpec, type ServiceClientOptions } from './service';",
  ].join('\n');
  // Only the schemas an operation reaches are emitted (unreachableDefinitions: false): the app needs no others, and
  // json-schema-to-typescript drops the properties of an unreached schema that has both properties and oneOf.
  const types = await compile(operationsSchema(service, spec, operations, names.types), names.types, {
    bannerComment: banner,
    additionalProperties: false,
    strictIndexSignatures: true,
    unreachableDefinitions: false,
    format: false,
  });
  for (const name of [names.table, names.client, names.factory]) {
    if (new RegExp(`^export (type|interface|const|function) ${name}\\b`, 'm').test(types)) {
      throw new Error(`services/${service}/openapi.yaml: a schema is named ${name}, which the generated client uses`);
    }
  }
  return prettier.format(`${types}\n\n${clientSource(service, operations, names)}`, {
    ...STYLE,
    filepath: `${service}.gen.ts`,
  });
}

/** The services whose client is generated: those listed in SERVICES whose OpenAPI file or client exists. */
function servicesPresent({ repo = REPO, apiDir = API_DIR } = {}) {
  return Object.keys(SERVICES).filter((s) => fs.existsSync(specPath(s, repo)) || fs.existsSync(outputPath(s, apiDir)));
}

/** What no longer matches: one line per client that differs from its file, or exists without it, or is missing. */
async function check({ repo = REPO, apiDir = API_DIR, services = servicesPresent({ repo, apiDir }) } = {}) {
  const problems = [];
  for (const service of services) {
    const output = `src/api/${service}.gen.ts`;
    const hasSpec = fs.existsSync(specPath(service, repo));
    const hasOutput = fs.existsSync(outputPath(service, apiDir));
    if (!hasSpec && !hasOutput) {
      problems.push(`services/${service}/openapi.yaml does not exist, so ${output} cannot be generated`);
    } else if (!hasSpec) {
      problems.push(`${output} exists, but services/${service}/openapi.yaml does not: delete the client or restore its file`);
    } else if (!hasOutput) {
      problems.push(`${output} is missing: run \`npm run generate:clients\``);
    } else if (fs.readFileSync(outputPath(service, apiDir), 'utf8') !== (await generate(service, { repo }))) {
      problems.push(`${output} does not match services/${service}/openapi.yaml: run \`npm run generate:clients\``);
    }
  }
  return problems;
}

async function main(argv) {
  const named = argv.filter((arg) => !arg.startsWith('--'));
  const services = named.length ? named : servicesPresent();
  if (argv.includes('--check')) {
    const problems = await check({ services });
    for (const problem of problems) process.stderr.write(`${problem}\n`);
    if (problems.length) return 1;
    process.stdout.write(`${services.map((s) => `src/api/${s}.gen.ts`).join(', ')} match their OpenAPI files\n`);
    return 0;
  }
  for (const service of services) {
    if (!fs.existsSync(specPath(service))) {
      process.stderr.write(`services/${service}/openapi.yaml does not exist, so src/api/${service}.gen.ts cannot be generated\n`);
      return 1;
    }
    fs.writeFileSync(outputPath(service), await generate(service));
    process.stdout.write(`wrote src/api/${service}.gen.ts\n`);
  }
  return 0;
}

module.exports = { SERVICES, generate, check, operationsOf, servicesPresent, specPath, outputPath };

if (require.main === module) {
  main(process.argv.slice(2)).then(
    (code) => process.exit(code),
    (error) => {
      process.stderr.write(String(error && error.stack ? error.stack : error) + '\n');
      process.exit(1);
    },
  );
}
