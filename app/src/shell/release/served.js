#!/usr/bin/env node
// Print the commit an app channel serves: the commit EAS recorded for the latest finished build of that channel's
// build profile, on iOS and on Android. This is the served-commit command of the staging/app and production/app
// rows in LOOP.md §3 (app-shell C3, command-center/D43). It reads the JSON that
// `eas build:list --build-profile <profile> --status finished --json --non-interactive` prints, on stdin.
//
// EAS records a build's commit as gitCommitHash, the `git rev-parse HEAD` of the checkout `eas build` ran in
// (eas-cli 22.4.0, build/metadata.js), and app/eas.json sets cli.requireCommit, so EAS refuses to build from
// uncommitted changes and the commit describes the build. Reading the list needs an Expo login or EXPO_TOKEN.
//
// A channel serves a commit only when its latest iOS and Android builds were both made from it. Otherwise this
// prints nothing on stdout, says why on stderr and exits 1, so the environment reads as unknown and is never
// guessed. With an expected SHA it also verifies a release: it exits 1 unless the served commit starts with it,
// as scripts/gcp/served.sh does for a service.
//
// Usage: eas build:list ... --json | node src/shell/release/served.js <profile> [<expected sha>]
'use strict';

const PLATFORMS = ['IOS', 'ANDROID'];

/** The commit the channel serves, or an error saying why there is none. */
function servedCommit(builds, profile) {
  if (!Array.isArray(builds)) return { error: 'the build list is not a JSON array' };
  const latest = {};
  for (const build of builds) {
    if (!build || build.buildProfile !== profile || build.status !== 'FINISHED') continue;
    const current = latest[build.platform];
    if (!current || String(build.createdAt) > String(current.createdAt)) latest[build.platform] = build;
  }
  for (const platform of PLATFORMS) {
    if (!latest[platform]) return { error: `no finished ${platform.toLowerCase()} build for profile ${profile}` };
    if (!/^[0-9a-f]{7,40}$/.test(String(latest[platform].gitCommitHash))) {
      return { error: `the latest ${platform.toLowerCase()} build for profile ${profile} records no commit` };
    }
  }
  const ios = latest.IOS.gitCommitHash;
  const android = latest.ANDROID.gitCommitHash;
  if (ios !== android) {
    return { error: `profile ${profile} serves different commits: ios ${ios}, android ${android}` };
  }
  return { commit: ios };
}

function main(argv, input) {
  if (argv.length < 1 || argv.length > 2) {
    return { code: 2, stderr: 'usage: eas build:list ... --json | node src/shell/release/served.js <profile> [<sha>]\n' };
  }
  const [profile, want] = argv;
  let builds;
  try {
    builds = JSON.parse(input);
  } catch {
    return { code: 1, stderr: `served: the build list for profile ${profile} is not JSON\n` };
  }
  const result = servedCommit(builds, profile);
  if (result.error) return { code: 1, stderr: `served: ${result.error}\n` };
  if (want && !result.commit.startsWith(want)) {
    return { code: 1, stderr: `served: profile ${profile} serves ${result.commit}, not ${want}\n` };
  }
  return { code: 0, stdout: `${result.commit}\n` };
}

module.exports = { servedCommit, main };

if (require.main === module) {
  let input = '';
  process.stdin.setEncoding('utf8');
  process.stdin.on('data', (chunk) => (input += chunk));
  process.stdin.on('end', () => {
    const { code, stdout = '', stderr = '' } = main(process.argv.slice(2), input);
    process.stdout.write(stdout);
    process.stderr.write(stderr);
    process.exitCode = code;
  });
}
