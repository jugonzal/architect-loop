// Test-only stubs of the status client that serve the schema's own fixtures, tests/fixtures/status/*.json
// (command-center/D15). A screen's tests render against the same documents the schema's tests validate, so a
// fixture that changes with the schema changes every screen test with it.
//
// Never import this from app code: it reads the repository with Node's fs, which a phone does not have, and Metro
// cannot bundle files outside app/.

import * as fs from 'fs';
import * as path from 'path';

import { parseStatus, type ProjectKey, type StatusClient, type StatusDocument } from './status';

export const STATUS_FIXTURES_DIR = path.resolve(__dirname, '../../../tests/fixtures/status');

/** The names of every fixture, without .json, in sorted order. */
export function statusFixtureNames(): string[] {
  return fs
    .readdirSync(STATUS_FIXTURES_DIR)
    .filter((file) => file.endsWith('.json'))
    .map((file) => file.slice(0, -'.json'.length))
    .sort();
}

/** One fixture, parsed and checked the way the real client checks a service's answer. */
export function loadStatusFixture(name: string): StatusDocument {
  const file = path.join(STATUS_FIXTURES_DIR, `${name}.json`);
  const value: unknown = JSON.parse(fs.readFileSync(file, 'utf8'));
  const project = (value as { project?: unknown }).project;
  return parseStatus(value, String(project) as ProjectKey);
}

/** A status client that answers with one fixture, a fresh copy each call, so a test cannot change the next one's. */
export function createFixtureStatusClient(name: string): StatusClient {
  const doc = loadStatusFixture(name);
  return {
    project: doc.project as ProjectKey,
    async getStatus() {
      return structuredClone(doc);
    },
  };
}
