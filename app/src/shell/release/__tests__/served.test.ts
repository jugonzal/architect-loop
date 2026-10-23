// app-shell C3, before the merge: the served-commit command of the app's LOOP.md §3 rows prints the commit the
// channel's builds were made from, and refuses to guess. The builds here have the shape eas-cli 22.4.0 prints for
// `eas build:list --json` (its BuildFragment: platform IOS or ANDROID, status FINISHED, buildProfile,
// gitCommitHash, createdAt). Against real EAS builds it is proven after the merge.

import { execFileSync, spawnSync } from 'child_process';
import * as fs from 'fs';
import * as path from 'path';

const SCRIPT = path.resolve(__dirname, '../served.js');
const APP = path.resolve(__dirname, '../../../..');
const LOOP_MD = path.resolve(APP, '../LOOP.md');
const { main, servedCommit } = require('../served.js');

const A = 'a1b2c3d4e5f60718293a4b5c6d7e8f9012345678';
const B = 'b1b2c3d4e5f60718293a4b5c6d7e8f9012345678';

function build(platform: 'IOS' | 'ANDROID', commit: string | null, createdAt: string, extra: object = {}) {
  return { id: `${platform}-${createdAt}`, platform, status: 'FINISHED', buildProfile: 'staging', gitCommitHash: commit, createdAt, ...extra };
}

describe("an app channel's served commit", () => {
  it("is the commit both platforms' latest finished builds were made from", () => {
    const builds = [
      build('IOS', A, '2026-10-22T10:00:00.000Z'),
      build('ANDROID', B, '2026-10-21T09:00:00.000Z'),
      build('ANDROID', A, '2026-10-22T10:05:00.000Z'),
      build('IOS', B, '2026-10-21T09:00:00.000Z'),
    ];
    expect(servedCommit(builds, 'staging')).toEqual({ commit: A });
  });

  it('is unknown while iOS and Android serve different commits', () => {
    const builds = [build('IOS', A, '2026-10-22T10:00:00.000Z'), build('ANDROID', B, '2026-10-22T10:00:00.000Z')];
    expect(servedCommit(builds, 'staging').error).toMatch(/different commits: ios a1b2c3d.*, android b1b2c3d/);
  });

  it('is unknown until both platforms have a finished build', () => {
    expect(servedCommit([build('IOS', A, '2026-10-22T10:00:00.000Z')], 'staging').error).toBe(
      'no finished android build for profile staging',
    );
    expect(servedCommit([], 'staging').error).toBe('no finished ios build for profile staging');
  });

  it("ignores other profiles' builds and builds that did not finish", () => {
    const builds = [
      build('IOS', A, '2026-10-21T10:00:00.000Z'),
      build('ANDROID', A, '2026-10-21T10:00:00.000Z'),
      build('IOS', B, '2026-10-22T10:00:00.000Z', { buildProfile: 'production' }),
      build('ANDROID', B, '2026-10-22T10:00:00.000Z', { status: 'ERRORED' }),
    ];
    expect(servedCommit(builds, 'staging')).toEqual({ commit: A });
  });

  it('is unknown when a build records no commit', () => {
    const builds = [build('IOS', null, '2026-10-22T10:00:00.000Z'), build('ANDROID', A, '2026-10-22T10:00:00.000Z')];
    expect(servedCommit(builds, 'staging').error).toBe('the latest ios build for profile staging records no commit');
  });

  it('verifies a release: exits 1 unless the served commit starts with the expected one', () => {
    const input = JSON.stringify([build('IOS', A, '2026-10-22T10:00:00.000Z'), build('ANDROID', A, '2026-10-22T10:00:00.000Z')]);
    expect(main(['staging', A.slice(0, 7)], input)).toEqual({ code: 0, stdout: `${A}\n` });
    expect(main(['staging', B.slice(0, 7)], input)).toMatchObject({ code: 1, stderr: expect.stringContaining(`serves ${A}, not b1b2c3d`) });
    expect(main(['staging'], 'not json')).toMatchObject({ code: 1 });
    expect(main([], input)).toMatchObject({ code: 2 });
  });

  it('runs as the command in LOOP.md runs it, reading the list on stdin', () => {
    const input = JSON.stringify([build('IOS', A, '2026-10-22T10:00:00.000Z'), build('ANDROID', A, '2026-10-22T10:00:00.000Z')]);
    expect(execFileSync(process.execPath, [SCRIPT, 'staging'], { input, encoding: 'utf8' })).toBe(`${A}\n`);
    const failed = spawnSync(process.execPath, [SCRIPT, 'staging'], { input: '[]', encoding: 'utf8' });
    expect(failed.status).toBe(1);
    expect(failed.stdout).toBe('');
    expect(failed.stderr).toContain('no finished ios build');
  });
});

describe("the app's environments (command-center/D43)", () => {
  const eas = JSON.parse(fs.readFileSync(path.join(APP, 'eas.json'), 'utf8'));

  function rows(): Record<string, string[]> {
    const text = fs.readFileSync(LOOP_MD, 'utf8');
    const section = /^## 3\. .*?(?=^## )/ms.exec(text)?.[0] ?? '';
    const result: Record<string, string[]> = {};
    for (const line of section.split('\n')) {
      const cells = line.trim().split(/(?<!\\)\|/).slice(1, -1).map((c) => c.trim());
      if (cells.length && !/^[-: ]+$/.test(cells[0] ?? '')) result[(cells[0] ?? '').replace(/`/g, '')] = cells;
    }
    return result;
  }

  it.each([
    ['staging/app', 'staging'],
    ['production/app', 'production'],
  ])('%s has a LOOP.md row whose served-commit command reads EAS profile %s', (environment, profile) => {
    const row = rows()[environment];
    expect(row).toBeDefined();
    const served = row?.[5] ?? '';
    expect(served).toContain(`eas build:list --build-profile ${profile} --status finished`);
    expect(served).toContain('--json --non-interactive');
    expect(served).toContain(`node src/shell/release/served.js ${profile}`);
    expect(row?.[4]).toContain(`eas build --profile ${profile}`);
    expect(eas.build[profile].env.EXPO_PUBLIC_ENVIRONMENT).toBe(environment);
  });

  it('lists the app rows after the services, lowest environment first', () => {
    const names = Object.keys(rows());
    expect(names.indexOf('staging/app')).toBeGreaterThan(names.indexOf('staging/notify'));
    expect(names.indexOf('production/app')).toBeGreaterThan(names.indexOf('staging/app'));
    expect(names.indexOf('production/app')).toBeGreaterThan(names.indexOf('production/notify'));
  });

  it('builds only from committed work, so the recorded commit describes the build', () => {
    expect(eas.cli.requireCommit).toBe(true);
  });

  it('puts no secret in a build profile: only the public client ID, URLs and names', () => {
    // The services' URLs are Cloud Run's public URLs (command-center/D32, app-clients D1).
    const PUBLIC = [
      'EXPO_PUBLIC_ENVIRONMENT',
      'EXPO_PUBLIC_GITHUB_CLIENT_ID',
      'EXPO_PUBLIC_STATUS_URL',
      'EXPO_PUBLIC_RUNNER_URL',
      'EXPO_PUBLIC_THREADS_URL',
      'EXPO_PUBLIC_NOTIFY_URL',
      'EXPO_PUBLIC_PROJECT',
    ];
    for (const profile of Object.values<{ env?: Record<string, string> }>(eas.build)) {
      for (const name of Object.keys(profile.env ?? {})) {
        expect(PUBLIC).toContain(name);
      }
    }
  });
});
